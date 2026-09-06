#!/usr/bin/env python3
"""Per-person research checklist and gap generator (docs/RESEARCH-CHECKLIST.md).

usage: tools/checklist.py "<person name or id>" [--tree slug] [--json]
       tools/checklist.py --all [--tree slug]          # one line per person

Read-only. For one person it reports:
  foundation  the facts search would be seeded with, each marked accepted or lead
              (an Undecided fact is a lead; nothing runs on leads until reviewed)
  questions   generated from gaps in the tree (missing parents, no surname, ...)
  checklist   Group A (records that hold several family members) then Group B
              (records about this person), each row gated by era, place and sex
              and marked held / cited / missing / n/a; a cited row names the
              relative the citation sits on when it is not on this person
  search      for every gap, the pre-built step: typed query, sources, mode;
              every query field is {value, basis accepted|lead|row}, rejected
              facts are omitted. Before the baseline is reviewed only fetch
              steps for cited records exist: no search steps, no footprint,
              no duplicate or unlinked leads (docs/RESEARCH-WORKFLOW.md §2).
"""
import argparse, collections, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, resolve_tree
from catalog import Catalog, US_STATES, US_NAMES, year
from footprint import footprint

# statewide civil registration windows (year from) and the registry row that covers them
VITAL = {"pennsylvania": {"birth": (1906, "C03"), "death": (1906, "C03"), "marriage": (1885, "C03")},
         "massachusetts": {"birth": (1841, "C05"), "death": (1841, "C05"), "marriage": (1841, "C05")},
         "kentucky": {"birth": (1911, "C06"), "death": (1911, "C06"), "marriage": (1852, "C06")},
         "tennessee": {"birth": (1908, "C07"), "death": (1908, "C07"), "marriage": (1780, "C07")},
         "new york": {"birth": (1881, "C08"), "death": (1881, "C08"), "marriage": (1881, "C08")},
         "new jersey": {"birth": (1848, "C09"), "death": (1848, "C09"), "marriage": (1848, "C09")},
         "ohio": {"birth": (1908, "C10"), "death": (1908, "C10"), "marriage": (1800, "C10")}}
STATE_CENSUS = {"new york": [1855, 1865, 1875, 1892, 1905, 1915, 1925], "massachusetts": [1855, 1865]}
CHURCH = {"pennsylvania": ["I01", "I02", "I03"], "ireland": ["I08"], "netherlands": ["I07"], "germany": ["I04", "I05", "I06"], "poland": ["I09"]}
CIVIL_ABROAD = {"ireland": 1864, "netherlands": 1811, "germany": 1876, "poland": 1874}   # civil registration begins; before that: parish registers
# what a citation's collection name must match for a row to count as cited/held
MATCH = {"census": lambda y: rf"^{y} United States Federal Census", "state_census": lambda st, y: rf"State Census.*{y}",
         "marriage": r"Marriage", "church": r"Church|Mennonite|Presbyterian|Parish|Catholic|Reformed",
         "probate": r"Wills|Probate", "obituary": r"Obituar", "cemetery": r"Grave|Cemetery|Burial|Gravesites",
         "passenger": r"Passenger|Immigration|Emigration|Hamburg", "pension": r"Pension", "deed": r"Land|Deed|Warrant",
         "directory": r"Directories", "compiled": r"Histories|History Books|Genealog|Cyclopedia|Surname|Membership",
         "death_record": r"(?<!Security )Death (Certificate|Record|Index)", "birth_record": r"Birth (Certificate|Record|Index)",
         "social_security": r"Social Security", "naturalization": r"Naturalization", "draft_ww1": r"World War I ",
         "draft_ww2": r"World War II Draft", "draft_civil": r"Civil War Draft", "military": r"Enlistment|Army|Navy|Veterans"}

# ---------------------------------------------------------------------------------------
def build(cat: Catalog, pid: str):
    p = cat.person(pid); ev = cat.events(pid); fam = cat.family(pid)
    given, surname = (p["names"][0][0], p["names"][0][1]) if p["names"] else (None, None)
    first = lambda t: next((e for e in ev if e["type"] == t), None)
    birth, death, burial = first("Birth"), first("Death"), first("Burial")
    dated = [e["year"] for e in ev if e["year"]]
    b = birth["year"] if birth and birth["year"] else None
    d = (death["year"] if death and death["year"] else None) or (burial["year"] if burial and burial["year"] else None)
    notes = []
    if b is None and dated: b = min(dated) - 20; notes.append(f"birth year estimated as {b} from earliest dated event")
    if d is None and b: d = b + 90; notes.append(f"no death: lifespan assumed to {d}")
    places = [e["place"] for e in ev if e["place"]]
    countries = {pl["country"] for pl in places if pl["country"]}; states = [pl["state"] for pl in places if pl["state"]]
    home_state = collections.Counter(states).most_common(1)[0][0] if states else None
    in_us = "united states" in countries or bool(states)
    foreign_born = bool(birth and birth["place"] and birth["place"]["country"] and birth["place"]["country"] != "united states")
    sex = p["sex"]

    # ---- foundation
    def field(label, value, basis, extra=None):
        return {"field": label, "value": value, "basis": basis, **(extra or {})}
    foundation = [field("name", " ".join(x for x in (given, surname) if x) or None, cat.basis("person", pid),
                        {"given": given, "surname": surname, "variants": sorted({" ".join(x for x in (n[0], n[1]) if x) for n in p["names"][1:]} | set(p["aliases"]))}),
                  field("sex", sex, cat.basis("person", pid))]
    for label, e in (("birth", birth), ("death", death)):
        if e: foundation.append(field(label, {"year": e["year"], "date": e["date_text"], "place": e["place"]["text"] if e["place"] else None}, e["basis"]))
    foundation += [field("parents", [n for _, n in fam["parents"]], cat.link_basis(pid, "parents")),
                   field("spouses", [n for _, n in fam["spouses"]], cat.link_basis(pid, "spouses")),
                   field("children", [n for _, n in fam["children"]], cat.link_basis(pid, "children")),
                   field("residences", [{"year": e["year"], "place": e["place"]["text"] if e["place"] else e["date_text"]} for e in ev if e["type"] == "Residence"], "mixed")]
    baseline = cat.baseline(pid, ev); reviewed = baseline["complete"]
    # ---- the fields every query is built from: {value, basis}; a rejected or absent fact is left out
    def F(value, basis):
        return None if basis == "rejected" or value in (None, "", []) else {"value": value, "basis": basis or "lead"}
    ROW = lambda v: {"value": v, "basis": "row"}                  # set by the checklist row, not a fact about the person
    bb = birth["basis"] if birth and birth["year"] else "lead"    # an estimated year is a lead
    db = death["basis"] if death and death["year"] else (burial["basis"] if burial and burial["year"] else "lead")
    sb = "accepted" if any(e["basis"] == "accepted" and e["place"] and e["place"]["state"] == home_state for e in ev) else "lead"
    fields = lambda **extra: {k: v for k, v in {**fnd, **extra}.items() if v is not None}

    # ---- questions from gaps in the tree
    questions = []
    if not fam["parents"]: questions.append({"kind": "missing_parents"})
    if not surname or (given and not surname): questions.append({"kind": "identity_incomplete", "detail": "no surname"})
    if not fam["spouses"] and b and (d or 9999) - b >= 21: questions.append({"kind": "missing_spouse"})
    for label, e in (("birth", birth), ("death", death)):
        if not e or not e["year"]: questions.append({"kind": "missing_fact", "detail": f"{label} date"})
        elif not e["place"]: questions.append({"kind": "missing_fact", "detail": f"{label} place"})
    if sum(1 for e in ev if e["type"] == "Birth") > 1: questions.append({"kind": "conflict", "detail": "more than one birth event"})
    for f in fam["families"]:
        if len(f["marriages"]) > 1: questions.append({"kind": "conflict", "detail": f"{len(f['marriages'])} marriage events with {f['spouse']}"})
    fp = footprint(cat, pid) if reviewed else {"summary": {"relatives": 0, "records": 0, "shared": 0}, "duplicates": [], "unlinked": [], "records": [], "collections": [], "gated": True}
    for dup in fp["duplicates"]: questions.append({"kind": "duplicate_person", "detail": dup["why"], "other_id": dup["id"]})
    if any(q["kind"] in ("missing_parents", "missing_spouse", "identity_incomplete") for q in questions):
        for u in fp["unlinked"]: questions.append({"kind": "unlinked_relative", "detail": u["why"], "other_id": u["id"]})
    uncited = [e for e in ev if not e["citations"]]
    if uncited: questions.append({"kind": "unverified_claim", "detail": f"{len(uncited)} event(s) with no record: " + ", ".join(f"{e['type']} {e['date_text'] or ''}".strip() for e in uncited[:6])})

    # ---- checklist rows
    own = cat.person_citations(pid); fetched = cat.fetched_rows(pid)
    rel_cits = {}
    for group, rel in (("spouses", "spouse"), ("children", "child"), ("parents", "parent"), ("siblings", "sibling")):
        for rid, rname in fam[group]: rel_cits[rname] = (rel, cat.person_citations(rid))
    def status_of(pattern, household=False):
        rx = re.compile(pattern, re.I)
        held = next((c for c in own if c[2] and rx.search(c[0])), None)
        if held: return "held", None
        if any(rx.search(c[0]) for c in own): return "cited", None
        if household:
            for rname, (rel, cits) in rel_cits.items():
                if any(c[2] and rx.search(c[0]) for c in cits): return "held", rname
                if any(rx.search(c[0]) for c in cits): return "cited", rname
        return "missing", None
    DEPENDS = {"D03": "B01"}                      # FamilySearch collections need the API approval tracked on B01
    def mode_for(ids):
        """One mode for a search step: auto only when a source has a built connector (registry column), awaiting_approval
        when every source waits on an application (its status or its gate's is blocked-apply), else assisted."""
        srcs = [cat.sources.get(sid, {}) for sid in ids]
        if any(s.get("connector") for s in srcs): return "auto"
        waits = lambda sid, s: s.get("status") == "blocked-apply" or cat.sources.get(DEPENDS.get(sid, ""), {}).get("status") == "blocked-apply"
        if ids and all(waits(sid, s) for sid, s in zip(ids, srcs)): return "awaiting_approval"
        return "assisted"
    def cited_on(pattern, household):
        """The citations behind a row: [{apid, collection, collection_id, on: [[name, relation]]}], own first, then relatives'.
        A census page carries one record id per family member; those collapse to one citation per page."""
        rx = re.compile(pattern, re.I); out = {}
        people = [(None, None, own)] + ([(rname, rel, cits) for rname, (rel, cits) in rel_cits.items()] if household else [])
        for rname, rel, cits in people:
            for cname, apid, held, cid in cits:
                if not apid or not rx.search(cname or ""): continue
                key = f"page:{cname}" if re.search(r"Federal Census|State Census", cname) else apid
                c = out.setdefault(key, {"apid": apid, "collection": cname, "collection_id": cid, "on": []})
                if rname and [rname, rel] not in c["on"]: c["on"].append([rname, rel])
        return list(out.values())
    A, B = [], []
    def row(group, record, pattern, sources, settles, query, household=False, na=None, instance=None):
        st, via = status_of(pattern, household) if pattern != "no-match" else ("missing", None)
        if f"{record}:{instance or ''}" in fetched: st, via = "held", None   # a done step (fetch or search) archived the record
        if na and st == "missing": st = "n/a"                     # a real citation beats the era rule
        r = {"record": record, "instance": instance, "status": st, "via": via, "settles": settles, "sources": sources,
             "na_reason": na if st == "n/a" else None, "note": (f"outside the usual window: {na}" if na and st != "n/a" else None),
             "citations": cited_on(pattern, household) if st in ("cited", "held") and pattern != "no-match" else []}
        if query and (st == "cited" or (st == "missing" and reviewed)):
            r["search"] = {"type": query[0], "fields": query[1], "sources": sources, "mode": "fetch" if st == "cited" else mode_for(sources), "expect": settles}
        (A if group == "A" else B).append(r)
    nb = cat.basis("person", pid)
    fnd = {"given": F(given, nb), "surname": F(surname, nb), "sex": F(sex, nb), "variants": F(foundation[0]["variants"], "lead"),
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
                ("household", fields(year=ROW(y), place=F(near["place"]["text"], near["basis"]) if near else None)),
                household=True, instance=str(y))
        for st_, years in STATE_CENSUS.items():
            if st_ in states:
                for y in years:
                    if b <= y <= (d or 9999):
                        row("A", f"{st_.title()} state census", MATCH["state_census"](st_, y), ["C08" if st_ == "new york" else "C05"], "household off-decade",
                            ("household", fields(year=ROW(y), state=ROW(st_))), household=True, instance=str(y))
    # A: marriage per family
    for f in fam["families"]:
        m = f["marriages"][0] if f["marriages"] else None
        my = m["year"] if m else None
        m_country = m["place"]["country"] if m and m["place"] and m["place"]["country"] else None
        st_ = (m["place"]["state"] if m and m["place"] else None) or home_state
        src = VITAL.get(st_ or "", {}).get("marriage", (None, None))
        if m_country and m_country != "united states": src = (None, None); st_ = None
        mcits = (m["citations"] if m else []) + own + rel_cits.get(f["spouse"] or "", ("", []))[1]
        cited = any(c[0] and re.search(MATCH["marriage"], c[0]) for c in mcits)
        r = {"record": "marriage record", "instance": f["spouse"], "status": "held" if f"marriage record:{f['spouse'] or ''}" in fetched else ("cited" if cited else "missing"), "via": None,
             "settles": "date, place, both sets of parents, maiden name",
             "sources": [src[1]] if src[1] else (CHURCH.get(m_country, []) if m_country and m_country != "united states" else ["C03", "C05", "C06", "C07", "C08", "C09"]), "na_reason": None,
             "citations": [{"apid": c[1], "collection": c[0], "collection_id": c[3], "on": [] if c in own or c in (m["citations"] if m else []) else [[f["spouse"], "spouse"]]}
                           for c in mcits if c[1] and c[0] and re.search(MATCH["marriage"], c[0])]}
        if m_country and m_country != "united states": r["settles"] += f"; married in {m_country.title()}: church register"
        if my and src[0] and my < src[0]: r["settles"] += f"; before statewide registration in {st_.title()} ({src[0]}): county book or church register"
        if r["status"] == "cited" or (r["status"] == "missing" and reviewed):
            mb = m["basis"] if m else "lead"
            r["search"] = {"type": "couple", "fields": fields(spouse=F(f["spouse"], cat.link_basis(pid, "spouses")), year=F(my, mb), state=F(st_, mb if m and m["place"] else sb)),
                           "sources": r["sources"], "mode": "fetch" if cited else mode_for(r["sources"]), "expect": r["settles"]}
        A.append(r)
    dplace = F(death["place"]["text"], death["basis"]) if death and death["place"] else F(home_state, sb)
    if d and d >= 1800: row("A", "obituary", MATCH["obituary"], ["H01", "H03", "H04"], "survivors, maiden names, places", ("obituary", fields(death_year=F(d, db), place=dplace)))
    if d and b and d - b >= 21: row("A", "will / probate", MATCH["probate"], ["J03"], "heirs, spouse, children", ("probate", fields(death_year=F(d, db))))
    row("A", "cemetery / family plot", MATCH["cemetery"], ["E01", "E03"], "burial, dates, who is buried together", ("subject_record", fields(death_year=F(d, db))), household=True)
    church_src = CHURCH.get(home_state or "", ["I03"]) if in_us or not countries else CHURCH.get(next(iter(countries), ""), [])   # no place at all: the tree's US default
    row("A", "church register (baptisms, marriages, burials)", MATCH["church"], church_src, "parents, sponsors, dates, religion", ("household", fields()), household=True)
    if foreign_born and in_us:
        row("A", "passenger / emigration list", MATCH["passenger"], ["G01", "G04"] if (b or 0) < 1800 else ["G01", "G03"], "origin, who travelled together", ("household", fields(arrival_after=F(b, bb))), household=True)
    if sex == "M" and b and (1818 <= b <= 1847 or 1725 <= b <= 1765):
        row("A", "pension file", MATCH["pension"], ["F03", "F04"], "marriage date/place, widow, children", ("subject_record", fields()), household=True)
    if in_us and b and (d or 9999) - b >= 21 and home_state == "pennsylvania":
        row("A", "land deed / warrant", MATCH["deed"], ["J02"], "spouse (dower), heirs", ("subject_record", fields()), household=True)
    if in_us and b and 1822 <= (d or 1995): row("A", "city directory / tax list", MATCH["directory"], ["K01"], "residence, occupation, adult sons", ("subject_record", fields()), household=True)
    row("A", "compiled genealogy / family history", MATCH["compiled"], ["L01", "L02", "L03"], "leads for everything; never proof", ("name", fields()), household=True)
    # B: individual records
    for label, e, kind in (("death record", death, "death"), ("birth record", birth, "birth")):
        yr = e["year"] if e else (d if kind == "death" else b); yb = e["basis"] if e and e["year"] else (db if kind == "death" else bb)
        country = (e["place"]["country"] if e and e["place"] and e["place"]["country"] else None) or ("united states" if in_us else next(iter(countries), None))
        st_ = (e["place"]["state"] if e and e["place"] else None) or home_state; stb = e["basis"] if e and e["place"] and e["place"]["state"] else sb
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
        row("B", label, MATCH[f"{kind}_record"], [win[1]] if win else ["C03", "C05", "C06", "C07", "C08", "C09", "C10"],
            "parents, informant, exact date and place" if kind == "death" else "exact date and place, parents", ("subject_record", fields(year=F(yr, yb), state=F(st_, stb))), instance=str(yr) if yr else None)
    if d and d >= 1936: row("B", "Social Security (SSDI / SS-5)", MATCH["social_security"], ["C01", "C02"], "birth, parents (SS-5)", ("subject_record", fields(death_year=F(d, db))))
    if foreign_born and in_us and (b or 0) >= 1790: row("B", "naturalization", MATCH["naturalization"], ["G02"], "birthplace, arrival, origin", ("subject_record", fields()))
    if sex == "M" and b:
        if 1872 <= b <= 1900: row("B", "WWI draft card", MATCH["draft_ww1"], ["F02"], "exact birth date/place, residence, next of kin", ("subject_record", fields()))
        if 1877 <= b <= 1927: row("B", "WWII draft card", MATCH["draft_ww2"], ["F02"], "exact birth date/place, residence, employer", ("subject_record", fields()))
        if 1818 <= b <= 1847: row("B", "Civil War draft registration", MATCH["draft_civil"], ["F03", "F02"], "age, birthplace, occupation", ("subject_record", fields()))
    if any(e["type"] in ("Military Service", "Military Draft") for e in ev): row("B", "military service record", MATCH["military"], ["F01", "F02"], "service", ("subject_record", fields()))
    return {"person": {"id": pid, "name": p["name"], "sex": sex, "span": [b, d], "notes": notes}, "baseline": baseline, "foundation": foundation,
            "questions": questions, "footprint": fp, "checklist": {"A": A, "B": B}}

# ---------------------------------------------------------------------------------------
def render(r):
    P = r["person"]; out = [f"{P['name']}  ({P['span'][0]}–{P['span'][1]})  sex {P['sex']}"]
    for n in P["notes"]: out.append(f"  note: {n}")
    bl = r["baseline"]; out.append(f"  baseline: {bl['key_facts_accepted']} of {bl['key_facts']} key facts Accepted" + ("" if bl["complete"] else f"; undecided: {', '.join(bl['undecided'])}  -> review unlocks searches, the footprint and leads; fetching cited records is open"))
    out.append("\nFOUNDATION")
    for f in r["foundation"]:
        v = f["value"]; v = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        out.append(f"  {f['field']:11} {str(v)[:70]:70} {f['basis'] or '-'}" + (f"  variants: {', '.join(f['variants'])}" if f.get("variants") else ""))
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
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    if a.all:
        for pid, name in cat.q("SELECT id, display_name FROM person WHERE tree_id=? ORDER BY display_name", tree_id):
            r = build(cat, pid); A = r["checklist"]["A"]; B = r["checklist"]["B"]
            gaps = lambda rows: sum(1 for x in rows if x["status"] == "missing"); cited = lambda rows: sum(1 for x in rows if x["status"] == "cited")
            print(f"{name[:34]:34} A: {gaps(A):2} missing {cited(A):2} to fetch | B: {gaps(B):2} missing {cited(B):2} to fetch | questions {len(r['questions'])}")
        return
    if not a.who: sys.exit("give a person name/id or --all")
    r = build(cat, cat.find_person(a.who))
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else render(r))

if __name__ == "__main__":
    main()
