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
  search      for every gap, the pre-built step: typed query, sources, mode
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
    foundation = [field("given", given, cat.basis("person", pid), {"variants": sorted({n[0] for n in p["names"][1:] if n[0]} | {a for a in p["aliases"]})}),
                  field("surname", surname, cat.basis("person", pid), {"variants": sorted({n[1] for n in p["names"][1:] if n[1]})}),
                  field("sex", sex, cat.basis("person", pid))]
    for label, e in (("birth", birth), ("death", death)):
        if e: foundation.append(field(label, {"year": e["year"], "date": e["date_text"], "place": e["place"]["text"] if e["place"] else None}, e["basis"]))
    foundation += [field("parents", [n for _, n in fam["parents"]], "lead" if fam["parents"] else None),
                   field("spouses", [n for _, n in fam["spouses"]], "lead" if fam["spouses"] else None),
                   field("children", [n for _, n in fam["children"]], "lead" if fam["children"] else None),
                   field("residences", [{"year": e["year"], "place": e["place"]["text"] if e["place"] else e["date_text"]} for e in ev if e["type"] == "Residence"], "mixed")]
    key_facts = ["given", "surname", "sex", "birth", "death", "parents", "spouses"]
    accepted = sum(1 for f in foundation if f["field"] in key_facts and f["basis"] == "accepted")
    baseline = {"key_facts_accepted": accepted, "key_facts": len(key_facts), "complete": accepted == len(key_facts)}

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
    fp = footprint(cat, pid)
    for dup in fp["duplicates"]: questions.append({"kind": "duplicate_person", "detail": dup["why"]})
    for u in fp["unlinked"]: questions.append({"kind": "unlinked_relative", "detail": u["why"]})
    uncited = [e for e in ev if not e["citations"]]
    if uncited: questions.append({"kind": "unverified_claim", "detail": f"{len(uncited)} event(s) with no record: " + ", ".join(f"{e['type']} {e['date_text'] or ''}".strip() for e in uncited[:6])})

    # ---- checklist rows
    own = cat.person_citations(pid)
    rel_cits = {}
    for group in ("spouses", "children", "parents", "siblings"):
        for rid, rname in fam[group]: rel_cits[rname] = cat.person_citations(rid)
    def status_of(pattern, household=False):
        rx = re.compile(pattern, re.I)
        held = next((c for c in own if c[2] and rx.search(c[0])), None)
        if held: return "held", None
        if any(rx.search(c[0]) for c in own): return "cited", None
        if household:
            for rname, cits in rel_cits.items():
                if any(c[2] and rx.search(c[0]) for c in cits): return "held", rname
                if any(rx.search(c[0]) for c in cits): return "cited", rname
        return "missing", None
    DEPENDS = {"D03": "B01"}                      # FamilySearch collections need the API approval tracked on B01
    def mode_for(ids):
        """{mode: [source ids]} — auto | assisted | awaiting approval, from the registry's Access/Status."""
        modes = collections.defaultdict(list)
        for sid in ids:
            s = cat.sources.get(sid, {}); gate = cat.sources.get(DEPENDS.get(sid, ""), {})
            if s.get("status") == "blocked-apply" or gate.get("status") == "blocked-apply": modes["awaiting approval"].append(sid)
            elif re.search(r"REST|API|bulk|SPARQL|loc\.gov", s.get("access", ""), re.I) and not re.search(r"NONE|no API", s.get("access", "")): modes["auto"].append(sid)
            else: modes["assisted"].append(sid)
        return dict(modes)
    A, B = [], []
    def row(group, record, pattern, sources, settles, query, household=False, na=None, instance=None):
        st, via = status_of(pattern, household) if pattern != "no-match" else ("missing", None)
        if na and st == "missing": st = "n/a"                     # a real citation beats the era rule
        r = {"record": record, "instance": instance, "status": st, "via": via, "settles": settles, "sources": sources,
             "na_reason": na if st == "n/a" else None, "note": (f"outside the usual window: {na}" if na and st != "n/a" else None)}
        if st in ("missing", "cited") and query:
            r["search"] = {"type": query[0], "fields": query[1], "sources": sources, "mode": {"fetch": sources} if st == "cited" else mode_for(sources),
                           "expect": settles, "basis": "accepted" if baseline["complete"] else "lead"}
        (A if group == "A" else B).append(r)
    fnd = {"given": given, "surname": surname, "variants": foundation[0]["variants"] + foundation[1]["variants"],
           "birth_year": b, "tolerance": 2, "state": home_state, "spouses": [n for _, n in fam["spouses"]], "parents": [n for _, n in fam["parents"]]}
    # A: census households (a foreign-born person is listed from the decade before their earliest US event)
    us_years = [e["year"] for e in ev if e["year"] and e["place"] and e["place"]["country"] == "united states"]
    census_from = b
    if foreign_born and us_years: census_from = max(b, min(us_years) - 10); notes.append(f"census rows start at {census_from}: earliest US event {min(us_years)}, arrival unknown")
    if b and in_us:
        for y in range(1790, 1951, 10):
            if not (census_from <= y <= (d or 9999)): continue
            if y == 1890: row("A", "census household", "no-match", ["D01"], "", None, na="1890 schedules lost", instance=str(y)); continue
            note = "head of household only; counted, not named" if y < 1850 else "everyone in the house: ages, birthplaces, relationships"
            row("A", "census household", MATCH["census"](y), ["D01", "D03"], note,
                ("household", {**fnd, "year": y, "place": next((e["place"]["text"] for e in ev if e["type"] == "Residence" and e["year"] and abs(e["year"] - y) <= 5 and e["place"]), None)}),
                household=True, instance=str(y))
        for st_, years in STATE_CENSUS.items():
            if st_ in states:
                for y in years:
                    if b <= y <= (d or 9999):
                        row("A", f"{st_.title()} state census", MATCH["state_census"](st_, y), ["C08" if st_ == "new york" else "C05"], "household off-decade",
                            ("household", {**fnd, "year": y, "state": st_}), household=True, instance=str(y))
    # A: marriage per family
    for f in fam["families"]:
        m = f["marriages"][0] if f["marriages"] else None
        my = m["year"] if m else None
        m_country = m["place"]["country"] if m and m["place"] and m["place"]["country"] else None
        st_ = (m["place"]["state"] if m and m["place"] else None) or home_state
        src = VITAL.get(st_ or "", {}).get("marriage", (None, None))
        if m_country and m_country != "united states": src = (None, None); st_ = None
        cited = any(c[0] and re.search(MATCH["marriage"], c[0]) for c in (m["citations"] if m else []) + own + rel_cits.get(f["spouse"] or "", []))
        r = {"record": "marriage record", "instance": f["spouse"], "status": "cited" if cited else "missing", "via": None,
             "settles": "date, place, both sets of parents, maiden name",
             "sources": [src[1]] if src[1] else (CHURCH.get(m_country, []) if m_country and m_country != "united states" else ["C03", "C05", "C06", "C07", "C08", "C09"]), "na_reason": None}
        if m_country and m_country != "united states": r["settles"] += f"; married in {m_country.title()}: church register"
        if my and src[0] and my < src[0]: r["settles"] += f"; before statewide registration in {st_.title()} ({src[0]}): county book or church register"
        if True:
            r["search"] = {"type": "couple", "fields": {**fnd, "spouse": f["spouse"], "year": my, "state": st_}, "sources": r["sources"],
                           "mode": {"fetch": r["sources"]} if cited else mode_for(r["sources"]), "expect": r["settles"], "basis": "accepted" if baseline["complete"] else "lead"}
        A.append(r)
    if d and d >= 1800: row("A", "obituary", MATCH["obituary"], ["H01", "H03", "H04"], "survivors, maiden names, places", ("obituary", {**fnd, "death_year": d, "place": death["place"]["text"] if death and death["place"] else home_state}))
    if d and b and d - b >= 21: row("A", "will / probate", MATCH["probate"], ["J03"], "heirs, spouse, children", ("probate", {**fnd, "death_year": d, "state": home_state}))
    row("A", "cemetery / family plot", MATCH["cemetery"], ["E01", "E03"], "burial, dates, who is buried together", ("subject_record", {**fnd, "death_year": d}), household=True)
    church_src = CHURCH.get(home_state or "", ["I03"]) if in_us else CHURCH.get(next(iter(countries), ""), [])
    row("A", "church register (baptisms, marriages, burials)", MATCH["church"], church_src, "parents, sponsors, dates, religion", ("household", {**fnd, "state": home_state}), household=True)
    if foreign_born and in_us:
        row("A", "passenger / emigration list", MATCH["passenger"], ["G01", "G04"] if (b or 0) < 1800 else ["G01", "G03"], "origin, who travelled together", ("household", {**fnd, "arrival_after": b}), household=True)
    if sex == "M" and b and (1818 <= b <= 1847 or 1725 <= b <= 1765):
        row("A", "pension file", MATCH["pension"], ["F03", "F04"], "marriage date/place, widow, children", ("subject_record", {**fnd}), household=True)
    if in_us and b and (d or 9999) - b >= 21 and home_state == "pennsylvania":
        row("A", "land deed / warrant", MATCH["deed"], ["J02"], "spouse (dower), heirs", ("subject_record", {**fnd, "state": home_state}), household=True)
    if in_us and b and 1822 <= (d or 1995): row("A", "city directory / tax list", MATCH["directory"], ["K01"], "residence, occupation, adult sons", ("subject_record", {**fnd}), household=True)
    row("A", "compiled genealogy / family history", MATCH["compiled"], ["L01", "L02", "L03"], "leads for everything; never proof", ("name", {**fnd}), household=True)
    # B: individual records
    for label, e, kind in (("death record", death, "death"), ("birth record", birth, "birth")):
        yr = e["year"] if e else (d if kind == "death" else b)
        country = (e["place"]["country"] if e and e["place"] and e["place"]["country"] else None) or ("united states" if in_us else next(iter(countries), None))
        st_ = (e["place"]["state"] if e and e["place"] else None) or home_state
        if country and country != "united states":
            civil = CIVIL_ABROAD.get(country)
            before_civil = civil and yr and yr < civil
            row("B", label, MATCH[f"{kind}_record"], CHURCH.get(country, []),
                f"date, parents; {country.title()} civil registration from {civil}, parish register before" if civil else "date, parents",
                ("subject_record", {**fnd, "year": yr, "country": country}), instance=str(yr) if yr else None,
                na=None if not before_civil else None); continue
        win = VITAL.get(st_ or "", {}).get(kind)
        if st_ and not win:
            row("B", label, MATCH[f"{kind}_record"], [], f"no registry row for {st_.title()} {kind} records yet; add one to data/data-sources.csv",
                ("subject_record", {**fnd, "year": yr, "state": st_}), instance=str(yr) if yr else None); continue
        if win and yr and yr < win[0]:
            row("B", label, MATCH[f"{kind}_record"], [win[1]], "exact date and place, parents", ("subject_record", {**fnd, "year": yr, "state": st_}),
                na=f"{st_.title()} statewide from {win[0]}; use church/town records", instance=str(yr)); continue
        row("B", label, MATCH[f"{kind}_record"], [win[1]] if win else ["C03", "C05", "C06", "C07", "C08", "C09", "C10"],
            "parents, informant, exact date and place" if kind == "death" else "exact date and place, parents", ("subject_record", {**fnd, "year": yr, "state": st_}), instance=str(yr) if yr else None)
    if d and d >= 1936: row("B", "Social Security (SSDI / SS-5)", MATCH["social_security"], ["C01", "C02"], "birth, parents (SS-5)", ("subject_record", {**fnd, "death_year": d}))
    if foreign_born and in_us and (b or 0) >= 1790: row("B", "naturalization", MATCH["naturalization"], ["G02"], "birthplace, arrival, origin", ("subject_record", {**fnd}))
    if sex == "M" and b:
        if 1872 <= b <= 1900: row("B", "WWI draft card", MATCH["draft_ww1"], ["F02"], "exact birth date/place, residence, next of kin", ("subject_record", {**fnd}))
        if 1877 <= b <= 1927: row("B", "WWII draft card", MATCH["draft_ww2"], ["F02"], "exact birth date/place, residence, employer", ("subject_record", {**fnd}))
        if 1818 <= b <= 1847: row("B", "Civil War draft registration", MATCH["draft_civil"], ["F03", "F02"], "age, birthplace, occupation", ("subject_record", {**fnd}))
    if any(e["type"] in ("Military Service", "Military Draft") for e in ev): row("B", "military service record", MATCH["military"], ["F01", "F02"], "service", ("subject_record", {**fnd}))
    return {"person": {"id": pid, "name": p["name"], "sex": sex, "span": [b, d], "notes": notes}, "baseline": baseline, "foundation": foundation,
            "questions": questions, "footprint": fp, "checklist": {"A": A, "B": B}}

# ---------------------------------------------------------------------------------------
def render(r):
    P = r["person"]; out = [f"{P['name']}  ({P['span'][0]}–{P['span'][1]})  sex {P['sex']}"]
    for n in P["notes"]: out.append(f"  note: {n}")
    bl = r["baseline"]; out.append(f"  baseline: {bl['key_facts_accepted']} of {bl['key_facts']} key facts Accepted" + ("" if bl["complete"] else "  -> searches run on leads only after review"))
    out.append("\nFOUNDATION")
    for f in r["foundation"]:
        v = f["value"]; v = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        out.append(f"  {f['field']:11} {str(v)[:70]:70} {f['basis'] or '-'}" + (f"  variants: {', '.join(f['variants'])}" if f.get("variants") else ""))
    out.append("\nQUESTIONS")
    for q in r["questions"] or [{"kind": "(none)"}]: out.append(f"  {q['kind']:20} {q.get('detail','')}")
    fp = r["footprint"]
    out.append(f"\nFOOTPRINT: records already on this family (fetch first)  [{fp['summary']['records']} records on {fp['summary']['relatives']} relatives; {fp['summary']['shared']} hold 2+ family members]")
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
            elif row.get("search"): tail = "; ".join(f"{m}: {', '.join(ids)}" for m, ids in row["search"]["mode"].items())
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
