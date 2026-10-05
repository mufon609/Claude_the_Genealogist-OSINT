#!/usr/bin/env python3
"""Per-person research checklist and gap generator (docs/RESEARCH-CHECKLIST.md).

usage: tools/checklist.py "<person name or id>" [--tree slug] [--json]
       tools/checklist.py --all [--tree slug]          # one line per person

Read-only. For one person it reports:
  foundation  the facts search would be seeded with, each marked accepted or claim
              (an Undecided fact is a claim; nothing runs on claims until reviewed; a date or a place
              is accepted only as far as an accepted statement gives it, Catalog.value_basis, and a
              birth or death showing more than that is accepted in part, the claim said in words), and the
              living default's reading of the person (Catalog.living: the tier, held death
              evidence, the owner's word), which sets a search step's mode
  questions   generated from gaps in the tree (missing parents, no surname, ...)
  checklist   Group A (records that hold several family members) then Group B
              (records about this person), each row gated by era, place and sex
              and marked held / cited / missing / n/a; a cited row names the
              relative the citation sits on when it is not on this person
  search      for every gap, the pre-built step: typed query, sources, mode;
              every query field is {value, basis accepted|claim|row|citation|record}, rejected
              facts are omitted. Before the baseline is reviewed only fetch
              steps for cited records exist: no search steps, no footprint,
              no unlinked persons (docs/RESEARCH-WORKFLOW.md §2); the duplicate
              check and the limits of one life (an identity question) run for
              every person, reviewed or not.
"""
import argparse, collections, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, resolve_tree
from catalog import Catalog, ONCE, US_STATES, US_NAMES, jurisdictions, year
from footprint import duplicates, footprint
from connectors import answers

# where which records exist and who holds them, by state or country: reference data (data/jurisdictions.csv), never a family's own places
J = jurisdictions()
VITAL, STATE_CENSUS, CHURCH, CIVIL_ABROAD, LAND, PASSENGER = J["vital"], J["state_census"], J["church"], J["civil"], J["land"], J["passenger"]
ANY_STATE = lambda kind: list(dict.fromkeys(v[kind][1] for v in VITAL.values() if kind in v and v[kind][1]))   # a record whose state is unknown: every state's holder of that kind the data knows
# what a citation's collection name must match for a row to count as cited/held
MATCH = {"census": lambda y: rf"^{y} United States Federal Census", "state_census": lambda st, y: rf"State Census.*{y}",
         "marriage": r"Marriage", "church": r"Church|Parish|Catholic|Reformed|Mennonite|Presbyterian|Lutheran|Methodist|Baptist|Episcopal|Moravian|Quaker|Friends|Congregational|Evangelical|Synagogue|Jewish|Orthodox",
         "probate": r"Wills|Probate", "obituary": r"Obituar", "cemetery": r"Grave|Cemetery|Burial|Gravesites",
         "passenger": r"Passenger|Immigration|Emigration|Hamburg", "pension": r"Pension", "deed": r"Land|Deed|Warrant",
         "directory": r"Directories", "compiled": r"Histories|History Books|Genealog|Cyclopedia|Surname|Membership",
         "death_record": r"(?<!Security )Death (Certificate|Record|Index)", "birth_record": r"Birth (Certificate|Record|Index)",
         "social_security": r"Social Security", "naturalization": r"Naturalization", "draft_ww1": r"World War I ",
         "draft_ww2": r"World War II Draft", "draft_civil": r"Civil War Draft", "military": r"Army|Navy|Veterans", "enlistment": r"World War II Army Enlistment"}

PARENT_ROWS = ("birth record", "death record", "obituary")   # the rows whose record names the person's parents (docs/RESEARCH-CHECKLIST.md, Group B's B1 and the obituary)
CHILDHOOD = 21                                               # a census of a year before the person turned this, the household their parents headed

def names_parents(row_key, born):
    """Whether a plan step's row is a record that names the person's parents: a birth or death record, an obituary, or a census
    of the household in a year of the person's childhood (born the given year; none counts when the birth year is unknown)."""
    record, _, instance = (row_key or "").partition(":")
    if record in PARENT_ROWS: return True
    return record == "census household" and bool(born) and instance.isdigit() and int(instance) - born < CHILDHOOD

# ---------------------------------------------------------------------------------------
def build(cat: Catalog, pid: str):
    p = cat.person(pid); ev = cat.events(pid); fam = cat.family(pid)
    given, surname = (p["names"][0][0], p["names"][0][1]) if p["names"] else (None, None)
    first = lambda t: next((e for e in ev if e["type"] == t), None)
    birth, death, burial = cat.canonical_event(ev, "Birth"), cat.canonical_event(ev, "Death"), first("Burial")
    dated = [e["year"] for e in ev if e["year"]]
    b = birth["year"] if birth and birth["year"] else None
    d = (death["year"] if death and death["year"] else None) or (burial["year"] if burial and burial["year"] else None)
    notes = []
    if b is None and dated: b = min(dated) - 20; notes.append(f"birth year estimated as {b} from earliest dated event")
    known_death = d                                               # the death the tree states; the assumed lifespan below gates era rows only, never a search for a death
    life = cat.living(pid); living = life["status"] != "deceased"   # the living default (docs/DATA-ARCHITECTURE.md §7 decision 3): a living or unknown person's searches are assisted, never auto
    if d is None and b: d = b + 90; notes.append(f"no death: lifespan assumed to {d}")
    places = [e["place"] for e in ev if e["place"]]
    us_state = lambda pl: pl["state"] if pl and pl["country"] == "united states" else None   # a place's first-level unit is a US state only within the United States: a province, a prefecture or England is not
    countries = {pl["country"] for pl in places if pl["country"]}; states = [s for s in map(us_state, places) if s]
    home_state = collections.Counter(states).most_common(1)[0][0] if states else None
    in_us = "united states" in countries                          # the country decides, never a first-level unit
    abroad = bool(countries) and not in_us                        # every place the tree gives lies outside the United States; a person with no place known is not abroad
    foreign_born = bool(birth and birth["place"] and birth["place"]["country"] and birth["place"]["country"] != "united states")
    sex = p["sex"]

    # ---- what of each event's value is accepted (docs/RESEARCH-WORKFLOW.md §5–7): a date or a place is accepted only as far as an accepted statement gives it
    readings = {}
    def reading(e):
        """Catalog.value_basis of an event some accepted statement stands behind, read once; None for any other."""
        if not e or e.get("basis") != "accepted": return None
        if e["id"] not in readings: readings[e["id"]] = cat.value_basis(e["id"])
        return readings[e["id"]]
    def year_basis(e):
        """accepted when an accepted statement gives the event's year (its date whole, or to the month or the year); rejected
        for an event every statement of which is rejected; claim otherwise."""
        if e and e.get("basis") == "rejected": return "rejected"
        r = reading(e)
        return "accepted" if r and r["date"] and r["date"]["level"] is not None else "claim"
    def place_basis(e, whole=True):
        """accepted when an accepted statement gives the event's place whole, or with whole False at least its last part below
        the country (the state); rejected for an event every statement of which is rejected; claim otherwise."""
        if e and e.get("basis") == "rejected": return "rejected"
        r = reading(e)
        return "accepted" if r and r["place"] and r["place"]["level"] is not None and (r["place"]["level"] == 0 or not whole) else "claim"
    def value_word(e):
        """accepted when all an event shows is accepted, accepted in part when some of it is a claim, else the event's basis."""
        r = reading(e)
        if r is None: return e["basis"] if e else None
        return "accepted in part" if cat.claim_words(r) else "accepted"

    # ---- foundation
    def field(label, value, basis, extra=None):
        return {"field": label, "value": value, "basis": basis, **(extra or {})}
    foundation = [field("name", " ".join(x for x in (given, surname) if x) or None, cat.basis("person", pid),
                        {"given": given, "surname": surname, "variants": sorted({" ".join(x for x in (n[0], n[1]) if x) for n in p["names"][1:]} | set(p["aliases"]))}),
                  field("sex", sex, cat.basis("person", pid)),
                  field("living", life["status"] + (", confirm with tools/conclude.py living" if life["status"] == "unknown" else ""), life["reason"])]
    for label, e in (("birth", birth), ("death", death)):
        if e: foundation.append(field(label, {"year": e["year"], "date": e["date_text"], "place": e["place"]["text"] if e["place"] else None}, value_word(e),
                                      {"claimed": cat.claim_words(reading(e))}))   # the parts that are a claim, in words, for the screen to say beside the value
    stays = [e for e in ev if e["type"] == "Residence"]
    foundation += [field("parents", [n for _, n in fam["parents"]], cat.link_basis(pid, "parents")),
                   field("spouses", [n for _, n in fam["spouses"]], cat.link_basis(pid, "spouses")),
                   field("children", [n for _, n in fam["children"]], cat.link_basis(pid, "children")),
                   field("residences", [{"year": e["year"], "place": e["place"]["text"] if e["place"] else e["date_text"], "basis": value_word(e)} for e in stays],
                         "accepted" if ev and all(value_word(e) == "accepted" for e in stays) else "claim")]
    baseline = cat.baseline(pid, ev); reviewed = baseline["complete"]
    # ---- the fields every query is built from: {value, basis}; a rejected or absent fact is left out
    def F(value, basis):
        return None if basis == "rejected" or value in (None, "", []) else {"value": value, "basis": basis or "claim"}
    def PLACES(place, basis, year=None):
        """A search step's place field, every accurate name in order (docs/RESEARCH-WORKFLOW.md §3, Catalog.place_search_names):
        the name valid at year first, then the person's own as-written strings for it, then its current name, then every other
        dated name; a place with no place_id (never resolved) gives its bare text alone. None for a rejected or absent place."""
        if not place or basis == "rejected": return None
        names = cat.place_search_names(place.get("place_id"), year=year, person_id=pid) if place.get("place_id") else ([place["text"]] if place.get("text") else [])
        return {"value": names, "basis": basis or "claim"} if names else None
    ROW = lambda v: {"value": v, "basis": "row"}                  # set by the checklist row, not a fact about the person
    bb = year_basis(birth) if birth and birth["year"] else "claim"    # an estimated year is a claim
    db = year_basis(death) if death and death["year"] else (year_basis(burial) if burial and burial["year"] else "claim")
    sb = "accepted" if any(e["place"] and us_state(e["place"]) == home_state and place_basis(e, whole=False) == "accepted" for e in ev) else "claim"
    fields = lambda **extra: {k: v for k, v in {**fnd, **extra}.items() if v is not None}

    # ---- questions from gaps in the tree
    questions = []
    if not fam["parents"]: questions.append({"kind": "missing_parents"})
    if not surname or (given and not surname): questions.append({"kind": "identity_incomplete", "detail": "no surname"})
    if not fam["spouses"] and b and (d or 9999) - b >= 21: questions.append({"kind": "missing_spouse"})
    for label, e in (("birth", birth), ("death", death)):
        if not e or not e["year"]: questions.append({"kind": "missing_fact", "detail": f"{label} date"})
        elif not e["place"]: questions.append({"kind": "missing_fact", "detail": f"{label} place"})
    for etype, n in collections.Counter(e["type"] for e in ev if e["type"] in ONCE).items():
        if n > 1: questions.append({"kind": "conflict", "detail": f"more than one {etype.lower()} event"})
    for said in cat.disagreements(pid): questions.append({"kind": "conflict", "detail": said})   # an accepted record says something else than the tree
    for said in cat.unplaced(pid): questions.append({"kind": "conflict", "detail": said})         # an accepted record's fact whose event is the owner's choice: assert_facts guessed at none of them
    for f in fam["families"]:
        if len(f["marriages"]) > 1: questions.append({"kind": "conflict", "detail": f"{len(f['marriages'])} marriage events with {f['spouse']}"})
    for said in cat.beyond_life(pid): questions.append({"kind": "identity", "detail": said})       # a link or an accepted statement beyond the limits of one life: is this the same person
    fp = footprint(cat, pid) if reviewed else {"summary": {"relatives": 0, "records": 0, "shared": 0}, "duplicates": duplicates(cat, pid), "unlinked": [], "records": [], "collections": [], "gated": True}
    for dup in fp["duplicates"]: questions.append({"kind": "duplicate_person", "detail": dup["why"], "other_id": dup["id"]})   # the duplicate check runs for every person, reviewed or not
    if any(q["kind"] in ("missing_parents", "missing_spouse", "identity_incomplete") for q in questions):
        for u in fp["unlinked"]: questions.append({"kind": "unlinked_relative", "detail": u["why"], "other_id": u["id"]})
    uncited = [e for e in ev if not e["citations"]]
    if uncited: questions.append({"kind": "unverified_claim", "detail": f"{len(uncited)} event(s) with no record: " + ", ".join(f"{e['type']} {e['date_text'] or ''}".strip() for e in uncited[:6])})

    # ---- checklist rows
    own = cat.person_citations(pid); own_subject = cat.person_citations(pid, subject_only=True); fetched = cat.fetched_rows(pid)
    rel_cits = {}
    for group, rel in (("spouses", "spouse"), ("children", "child"), ("parents", "parent"), ("siblings", "sibling")):
        for rid, rname in fam[group]: rel_cits[rname] = (rel, cat.person_citations(rid))
    def status_of(pattern, household=False):
        # a one-person row (household=False) is held only by its own subject (docs/RESEARCH-CHECKLIST.md §3): a relative
        # merely named on a record (a survivor, a listed relative) never holds it, so own_subject is used, not own
        rx = re.compile(pattern, re.I); pool = own if household else own_subject
        held = next((c for c in pool if c[2] and rx.search(c[0])), None)
        if held: return "held", None
        if any(rx.search(c[0]) for c in pool): return "cited", None
        if household:
            for rname, (rel, cits) in rel_cits.items():
                cits = [c for c in cits if not (c[2] and c[1] and not cat.held_for(c[1], pid))]   # a held record on the relative that does not name this person is not their household
                if any(c[2] and rx.search(c[0]) for c in cits): return "held", rname
                if any(rx.search(c[0]) for c in cits): return "cited", rname
        return "missing", None
    DEPENDS = {"D03": "B01"}                      # FamilySearch collections need the API approval tracked on B01
    def modes_for(ids, record):
        """The mode of a search step at each of its sources: auto where a built connector (registry column) answers this row
        (connectors.answers), assisted for a living or unknown person's, awaiting_approval where the source waits on an
        application (its status or its gate's is blocked-apply), else assisted."""
        waits = lambda sid, s: s.get("status") == "blocked-apply" or cat.sources.get(DEPENDS.get(sid, ""), {}).get("status") == "blocked-apply"
        out = {}
        for sid in ids:
            s = cat.sources.get(sid, {})
            if s.get("connector") and answers(s["connector"], record): out[sid] = "assisted" if living else "auto"
            else: out[sid] = "awaiting_approval" if waits(sid, s) else "assisted"
        return out
    def mode_for(ids, record):
        """One mode for a search step: auto when the loop searches at one of its sources at least, awaiting_approval when every
        source waits on an application, else assisted."""
        modes = modes_for(ids, record).values()
        if "auto" in modes: return "auto"
        return "awaiting_approval" if modes and all(m == "awaiting_approval" for m in modes) else "assisted"
    def cited_on(pattern, household):
        """The citations behind a row: [{apid, collection, collection_id, on: [[name, relation]]}], own first, then relatives'.
        A census page carries one record id per family member; those collapse to one citation per page."""
        rx = re.compile(pattern, re.I); out = {}
        people = [(None, None, own)] + ([(rname, rel, cits) for rname, (rel, cits) in rel_cits.items()] if household else [])
        for rname, rel, cits in people:
            for cname, apid, held, cid in cits:
                if not apid or not rx.search(cname or ""): continue
                if rname and held and not cat.held_for(apid, pid): continue        # the relative's record is held and does not name this person: not their household
                key = f"page:{cname}" if re.search(r"Federal Census|State Census", cname) else apid
                c = out.setdefault(key, {"apid": apid, "collection": cname, "collection_id": cid, "on": []})
                if rname and [rname, rel] not in c["on"]: c["on"].append([rname, rel])
        return list(out.values())
    A, B = [], []
    def row(group, record, pattern, sources, settles, query, household=False, na=None, instance=None, us=False):
        st, via = status_of(pattern, household) if pattern != "no-match" else ("missing", None)
        if f"{record}:{instance or ''}" in fetched and (household or fetched[f"{record}:{instance or ''}"]): st, via = "held", None   # a done step archived the record; for a row about one person, a record on the person
        if us and abroad and st == "missing": return              # a United States record is not looked for a person whose places all lie elsewhere; one the tree cites or holds stays
        if na and st == "missing": st = "n/a"                     # a real citation beats the era rule
        r = {"record": record, "instance": instance, "status": st, "via": via, "settles": settles, "sources": sources,
             "na_reason": na if st == "n/a" else None, "note": (f"outside the usual window: {na}" if na and st != "n/a" else None),
             "citations": cited_on(pattern, household) if st in ("cited", "held") and pattern != "no-match" else []}
        if query and (st == "cited" or (st == "missing" and reviewed)):
            r["search"] = {"type": query[0], "fields": query[1], "sources": sources, "mode": "fetch" if st == "cited" else mode_for(sources, record), "free_mode": mode_for(sources, record), "modes": modes_for(sources, record), "expect": settles}
        (A if group == "A" else B).append(r)
    nb = cat.basis("person", pid)
    fnd = {"given": F(given, nb), "surname": F(surname, nb), "sex": F(sex, nb), "variants": F(foundation[0]["variants"], "claim"),
           "birth_year": {**F(b, bb), "tolerance": 2} if F(b, bb) else None, "state": F(home_state, sb),
           "spouses": F([n for _, n in fam["spouses"]], cat.link_basis(pid, "spouses")), "parents": F([n for _, n in fam["parents"]], cat.link_basis(pid, "parents"))}
    # A: census households (a foreign-born person is listed from the decade before their earliest US event)
    us_years = [e["year"] for e in ev if e["year"] and e["place"] and e["place"]["country"] == "united states"]
    census_from = b
    if foreign_born and us_years: census_from = max(b, min(us_years) - 10); notes.append(f"census rows start at {census_from}: earliest US event {min(us_years)}, arrival unknown")
    if b and in_us:
        for y in range(1790, 1951, 10):
            if not (census_from <= y <= (d or 9999)): continue
            if y == 1890: row("A", "census household", "no-match", ["D01"], "", None, na="1890 schedules lost", instance=str(y)); continue
            note = "head of household only; counted, not named" if y < 1850 else "everyone in the house: ages, birthplaces, relationships"
            near = next((e for e in ev if e["type"] == "Residence" and e["year"] and abs(e["year"] - y) <= 5 and e["place"]), None)
            row("A", "census household", MATCH["census"](y), ["D05" if y == 1950 else "D01", "D03"], note,
                ("household", fields(year=ROW(y), place=PLACES(near["place"], place_basis(near), year=y) if near else None)),
                household=True, instance=str(y))
        for st_, (years, holders) in STATE_CENSUS.items():
            if st_ in states:
                for y in years:
                    if b <= y <= (d or 9999):
                        row("A", f"{st_.title()} state census", MATCH["state_census"](st_, y), holders, "household off-decade",
                            ("household", fields(year=ROW(y), state=ROW(st_))), household=True, instance=str(y))
    # A: marriage per family
    for f in fam["families"]:
        m = f["marriages"][0] if f["marriages"] else None
        my = m["year"] if m else None
        m_country = m["place"]["country"] if m and m["place"] and m["place"]["country"] else None
        st_ = us_state(m["place"] if m else None) or home_state
        src = VITAL.get(st_ or "", {}).get("marriage", (None, None))
        if m_country and m_country != "united states": src = (None, None); st_ = None
        mcits, seen_apids = [], set()                                  # one citation per record id: the event's, then the person's own, then the spouse's
        for c in (m["citations"] if m else []) + own + rel_cits.get(f["spouse"] or "", ("", []))[1]:
            if c[1] in seen_apids: continue
            if c[1]: seen_apids.add(c[1])
            mcits.append(c)
        cited = any(c[0] and re.search(MATCH["marriage"], c[0]) for c in mcits)
        r = {"record": "marriage record", "instance": f["spouse"], "status": "held" if f"marriage record:{f['spouse'] or ''}" in fetched else ("cited" if cited else "missing"), "via": None,
             "settles": "date, place, both sets of parents, maiden name",
             "sources": [src[1]] if src[1] else (CHURCH.get(m_country, []) if m_country and m_country != "united states" else ANY_STATE("marriage")), "na_reason": None,
             "citations": [{"apid": c[1], "collection": c[0], "collection_id": c[3], "on": [] if c in own or c in (m["citations"] if m else []) else [[f["spouse"], "spouse"]]}
                           for c in mcits if c[1] and c[0] and re.search(MATCH["marriage"], c[0])]}
        if m_country and m_country != "united states": r["settles"] += f"; married in {m_country.title()}: church register"
        if my and src[0] and my < src[0]: r["settles"] += f"; before statewide registration in {st_.title()} ({src[0]}): county book or church register"
        if r["status"] == "cited" or (r["status"] == "missing" and reviewed):
            mb = year_basis(m) if m else "claim"
            r["search"] = {"type": "couple", "fields": fields(spouse=F(f["spouse"], cat.link_basis(pid, "spouses")), year=F(my, mb), state=F(st_, place_basis(m, whole=False) if m and m["place"] else sb)),
                           "sources": r["sources"], "mode": "fetch" if cited else mode_for(r["sources"], r["record"]), "free_mode": mode_for(r["sources"], r["record"]), "modes": modes_for(r["sources"], r["record"]), "expect": r["settles"]}
        A.append(r)
    dplace = PLACES(death["place"], place_basis(death), year=d) if death and death["place"] else F(home_state, sb)
    if known_death and known_death >= 1800:
        row("A", "obituary", MATCH["obituary"], ([] if abroad else (["H05"] if known_death >= 1999 else []) + ["H01", "H07", "H03"]) + ["H04"], "survivors, maiden names, places",
            ("obituary", fields(death_year=F(d, db), place=dplace)))   # the United States papers (H05, Legacy.com, from 1999 on, searched first for a death in its window; H01, H07, H03) for any person but one whose places all lie abroad; Newspapers.com (H04) reaches beyond them
    if known_death and b and known_death - b >= 21: row("A", "will / probate", MATCH["probate"], ["J03"], "heirs, spouse, children", ("probate", fields(death_year=F(d, db))), us=True)
    row("A", "cemetery / family plot", MATCH["cemetery"], ["E01"] + ([] if abroad else ["E03"]), "burial, dates, who is buried together", ("subject_record", fields(death_year=F(d, db) if known_death else None)))   # a memorial is about one person: held through the person's own, the plot's relatives are leads on it
    church_src = CHURCH.get(home_state or "", []) if in_us or not countries else CHURCH.get(next(iter(countries), ""), [])   # a place with no church row names no holder
    row("A", "church register (baptisms, marriages, burials)", MATCH["church"], church_src, "parents, sponsors, dates, religion", ("household", fields()), household=True)
    if foreign_born and in_us:
        lists = list(dict.fromkeys(s for j, lo, hi, rows in PASSENGER if j in ("*", home_state) and (lo is None or (b or 0) >= lo) and (hi is None or (b or 0) <= hi) for s in rows))
        row("A", "passenger / emigration list", MATCH["passenger"], lists, "origin, who travelled together", ("household", fields(arrival_after=F(b, bb))), household=True)
    if sex == "M" and b and (1818 <= b <= 1847 or 1725 <= b <= 1765):
        row("A", "pension file", MATCH["pension"], ["F03", "F04"], "marriage date/place, widow, children", ("subject_record", fields()), household=True, us=True)
    if in_us and b and (d or 9999) - b >= 21 and home_state in LAND:
        row("A", "land deed / warrant", MATCH["deed"], LAND[home_state], "spouse (dower), heirs", ("subject_record", fields()), household=True)
    towns, tb = [], "accepted"                                     # the localities the person's events name, for a directory's title
    for e in ev:
        if not (e.get("place") and e["place"]["text"]): continue
        t = re.sub(r"^(Town|City|Village|Borough|Township) of ", "", e["place"]["text"].split(" < ")[0].split(",")[0].strip())
        if t and not re.search(r"\d", t) and t.lower() not in US_STATES and t.lower() not in US_NAMES and not re.search(r"\bcounty\b", t, re.I) and t not in towns: towns.append(t)
        if place_basis(e) != "accepted": tb = "claim"
    if in_us and b and 1822 <= (d or 1995): row("A", "city directory / tax list", MATCH["directory"], ["K01"], "residence, occupation, adult sons", ("subject_record", fields(towns=F(towns, tb) if towns else None)), household=True)
    row("A", "compiled genealogy / family history", MATCH["compiled"], ["L01", "L02", "L03", "B04"], "hints for everything; never proof", ("name", fields()), household=True)
    # B: individual records
    for label, e, kind in (("death record", death, "death"), ("birth record", birth, "birth")):
        if kind == "death" and (e["year"] if e and e["year"] else d or 0) > datetime.date.today().year: continue   # a death still to come (the lifespan assumed to a year not yet reached, or a stated one) has no record to search for
        yr = e["year"] if e else (None if kind == "death" else b); yb = year_basis(e) if e and e["year"] else (db if kind == "death" else bb)   # the year of a death nobody stated is not assumed from a lifespan: it is no claim
        country = (e["place"]["country"] if e and e["place"] and e["place"]["country"] else None) or ("united states" if in_us else next(iter(countries), None))
        st_ = us_state(e["place"] if e else None) or home_state; stb = place_basis(e, whole=False) if e and us_state(e["place"]) else sb
        if country and country != "united states":
            civil = CIVIL_ABROAD.get(country)
            before_civil = civil and yr and yr < civil
            row("B", label, MATCH[f"{kind}_record"], CHURCH.get(country, []),
                f"date, parents; {country.title()} civil registration from {civil}, parish register before" if civil else "date, parents",
                ("subject_record", fields(year=F(yr, yb), country=F(country, yb))), instance=str(yr) if yr else None); continue
        win = VITAL.get(st_ or "", {}).get(kind)
        if st_ and not win:
            row("B", label, MATCH[f"{kind}_record"], [], f"no registry row for {st_.title()} {kind} records yet; add one to data/data-sources.csv",
                ("subject_record", fields(year=F(yr, yb), state=F(st_, stb))), instance=str(yr) if yr else None); continue
        if win and yr and yr < win[0]:
            row("B", label, MATCH[f"{kind}_record"], [win[1]], "exact date and place, parents", ("subject_record", fields(year=F(yr, yb), state=F(st_, stb))),
                na=f"{st_.title()} statewide from {win[0]}; use church/town records", instance=str(yr)); continue
        row("B", label, MATCH[f"{kind}_record"], [win[1]] if win else ANY_STATE(kind),   # no state known: every state's holder the data knows, searched in turn
            "parents, informant, exact date and place" if kind == "death" else "exact date and place, parents", ("subject_record", fields(year=F(yr, yb), state=F(st_, stb))), instance=str(yr) if yr else None)
    if known_death and known_death >= 1936: row("B", "Social Security (SSDI / SS-5)", MATCH["social_security"], ["C01", "C02"], "birth, parents (SS-5)", ("subject_record", fields(death_year=F(d, db))), us=True)
    if foreign_born and in_us and (b or 0) >= 1790: row("B", "naturalization", MATCH["naturalization"], ["G02"], "birthplace, arrival, origin", ("subject_record", fields()))
    if sex == "M" and b:
        if 1872 <= b <= 1900: row("B", "WWI draft card", MATCH["draft_ww1"], ["F02"], "exact birth date/place, residence, next of kin", ("subject_record", fields()), us=True)
        if 1877 <= b <= 1927: row("B", "WWII draft card", MATCH["draft_ww2"], ["F02"], "exact birth date/place, residence, employer", ("subject_record", fields()), us=True)
        if 1895 <= b <= 1927 and sex == "M": row("B", "WWII Army enlistment", MATCH["enlistment"], ["F01"], "birth year and state, residence county at enlistment, enlistment date and place, education, marital status", ("subject_record", fields()), us=True)
        if 1818 <= b <= 1847: row("B", "Civil War draft registration", MATCH["draft_civil"], ["F03", "F02"], "age, birthplace, occupation", ("subject_record", fields()), us=True)
    if any(e["type"] in ("Military Service", "Military Draft") for e in ev): row("B", "military service record", MATCH["military"], ["F01", "F02"], "service", ("subject_record", fields()), us=True)
    return {"person": {"id": pid, "name": p["name"], "sex": sex, "span": [b, d], "notes": notes}, "baseline": baseline, "foundation": foundation,
            "questions": questions, "footprint": fp, "checklist": {"A": A, "B": B}}

# ---------------------------------------------------------------------------------------
def render(r):
    P = r["person"]; out = [f"{P['name']}  ({P['span'][0]}–{P['span'][1]})  sex {P['sex']}"]
    for n in P["notes"]: out.append(f"  note: {n}")
    bl = r["baseline"]; out.append(f"  baseline: {bl['key_facts_accepted']} of {bl['key_facts']} key facts Accepted" + ("" if bl["complete"] else f"; undecided: {', '.join(bl['undecided'])}  -> review unlocks searches, the footprint and leads; fetching cited records is open"))
    out.append("\nFOUNDATION")
    for f in r["foundation"]:
        v = f["value"]
        if f["field"] == "residences":                                # one stay per line, nothing cut short
            out.append(f"  {f['field']:11} {len(v)} stay(s)")
            for e in v: out.append(f"      {str(e['year'] or '?'):6} {(e['place'] or '?')[:64]:64} {e['basis'] or '-'}")
            continue
        v = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        out.append(f"  {f['field']:11} {str(v)[:70]:70} {f['basis'] or '-'}" + (f"  variants: {', '.join(f['variants'])}" if f.get("variants") else ""))
        for c in f.get("claimed") or []: out.append(f"  {'':11} {c}")
    out.append("\nQUESTIONS")
    for q in r["questions"] or [{"kind": "(none)"}]: out.append(f"  {q['kind']:20} {q.get('detail','')}")
    fp = r["footprint"]
    out.append("\nFOOTPRINT: shown after the baseline is reviewed" if fp.get("gated") else f"\nFOOTPRINT: records already on this family (fetch first)  [{fp['summary']['records']} records on {fp['summary']['relatives']} relatives; {fp['summary']['shared']} hold 2+ family members]")
    for rec in fp["records"][:10]:
        who = ", ".join(f"{n} ({rel})" for n, rel in rec["on"]); flag = "H" if rec["held"] else ("c" if rec["on_subject"] else " ")
        out.append(f"  [{flag}] {rec['collection'][:40]:40} on {who[:52]:52} -> {rec['expect']}")
    if len(fp["records"]) > 10: out.append(f"  … {len(fp['records'])-10} more")
    if fp["collections"]:
        out.append("  same collections to search for the family: " + "; ".join(f"{c['name'][:40]} ({c['count']})" for c in fp["collections"][:5]))
    for grp, title in (("A", "A. RECORDS THAT HOLD SEVERAL FAMILY MEMBERS (first)"), ("B", "B. RECORDS ABOUT THIS PERSON")):
        out.append(f"\n{title}")
        for row in r["checklist"][grp]:
            inst = f" {row['instance']}" if row.get("instance") else ""
            via = f" (on {row['via']})" if row.get("via") else ""
            if row["status"] == "n/a": tail = f"n/a: {row['na_reason']}"
            elif not row["sources"]: tail = row["settles"]
            elif row.get("search"): tail = f"{row['search']['mode']}: {', '.join(row['sources'])}"
            else: tail = ", ".join(row["sources"])
            if row.get("note"): tail += f"   ({row['note']})"
            out.append(f"  [{ {'held':'H','cited':'c','missing':' ','n/a':'-'}[row['status']] }] {row['record']+inst:44} {row['status']+via:26} {tail}")
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who", nargs="?"); ap.add_argument("--tree"); ap.add_argument("--json", action="store_true"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args()
    cx = connect(a.db); tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    if a.all:
        rows = []
        for pid, name in cat.q("SELECT id, display_name FROM person WHERE tree_id=? AND merged_into IS NULL ORDER BY display_name", tree_id):
            r = build(cat, pid); A = r["checklist"]["A"]; B = r["checklist"]["B"]
            gaps = lambda rows: sum(1 for x in rows if x["status"] == "missing"); cited = lambda rows: sum(1 for x in rows if x["status"] == "cited")
            rows.append({"id": pid, "person": name, "decided": 7 - len(r["baseline"]["undecided"]) if r["baseline"].get("undecided") is not None else None, "baseline_complete": r["baseline"]["complete"],
                         "A_missing": gaps(A), "A_to_fetch": cited(A), "B_missing": gaps(B), "B_to_fetch": cited(B), "questions": len(r["questions"])})
        if a.json: print(json.dumps(rows, ensure_ascii=False, indent=1)); return
        for x in rows: print(f"{x['person'][:30]:30} [{x['id'][-6:]}] {'reviewed ' if x['baseline_complete'] else 'to review'} A: {x['A_missing']:2} missing {x['A_to_fetch']:2} to fetch | B: {x['B_missing']:2} missing {x['B_to_fetch']:2} to fetch | questions {x['questions']}")
        return
    if not a.who: sys.exit("give a person name/id or --all")
    r = build(cat, cat.find_person(a.who))
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else render(r))

if __name__ == "__main__":
    main()
