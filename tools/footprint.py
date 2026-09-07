#!/usr/bin/env python3
"""Family footprint: the records already attached to a person's relatives, ranked
(docs/RESEARCH-WORKFLOW.md §3, Layer 0), with the duplicate check run first.

usage: tools/footprint.py "<person name or id>" [--tree slug] [--json]

Read-only. Reports, for one person:
  duplicates   persons in the tree that are probably the same individual
  unlinked     persons in the tree that may be the missing relative
  records      every record cited or held on a spouse, child, parent or sibling
               that is not already on the person, ranked by how many family
               members share it, then by how much it would settle
  collections  the collections those records come from, for same-collection searches
"""
import argparse, collections, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, resolve_tree
from catalog import Catalog, year

RELATION_NAMES = {"spouses": "spouse", "children": "child", "parents": "parent", "siblings": "sibling"}

def soundex(s):
    s = re.sub(r"[^a-z]", "", (s or "").lower())
    if not s: return ""
    codes = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"), **dict.fromkeys("dt", "3"), "l": "4", **dict.fromkeys("mn", "5"), "r": "6"}
    out, last = s[0].upper(), codes.get(s[0], "")
    for ch in s[1:]:
        c = codes.get(ch, "")
        if c and c != last: out += c
        if ch not in "hw": last = c
    return (out + "000")[:4]

def expect(collection, rel, subject_alive_in_year, subject_sex):
    """What a record about a relative is expected to say about the subject. Plain rules, by collection type."""
    c = collection or ""
    m = re.match(r"^(\d{4}) United States Federal Census", c)
    if m:
        y = int(m.group(1))
        if subject_alive_in_year(y):
            if y < 1850: return f"{y} household counted under the head; subject a tick mark unless head"
            return f"{y} household: subject's age, birthplace" + (", relationship to head" if y >= 1880 else "")
        if rel == "child" and y >= 1880: return f"{y} household of the child: 'birthplace of father/mother' column names where the subject was born"
        return f"{y} household of the {rel}: subject not alive; indirect only"
    if re.search(r"State Census", c): return f"state census household with the {rel}"
    if re.search(r"Death", c) and not re.search(r"Social Security", c):
        return {"child": "names the subject as parent" + (" with maiden name" if subject_sex == "F" else ""),
                "spouse": "subject as informant or spouse; burial place", "parent": "subject possibly informant; parent's own parents", "sibling": "names the same parents"}.get(rel, "death record of a relative")
    if re.search(r"Birth", c) and not re.search(r"Census", c):
        return {"child": "names both parents; mother's maiden name", "sibling": "names the same parents"}.get(rel, "birth record of a relative")
    if re.search(r"Marriage", c):
        return {"child": "names the subject as parent of the bride/groom", "spouse": "the subject's own marriage: parents of both", "parent": "the subject's parents' marriage: grandparents", "sibling": "names the same parents"}.get(rel, "marriage record")
    if re.search(r"Social Security", c):
        if re.search(r"Applications and Claims", c): return "SS-5 of the child names both parents incl. maiden name" if rel == "child" else "SS-5: parents of the relative"
        return f"SSDI: dates and last residence of the {rel} only"
    if re.search(r"Obituar", c): return f"obituary of the {rel}: survivors and predeceased, married names"
    if re.search(r"Wills|Probate", c): return {"parent": "the subject named as heir", "spouse": "subject as heir/executor", "child": "subject as heir if alive"}.get(rel, "heirs named")
    if re.search(r"Grave|Cemetery|Burial", c): return f"memorial of the {rel}: family plot, linked memorials"
    if re.search(r"Church|Mennonite|Presbyterian|Reformed|Parish", c): return "register entry names parents and sponsors" if rel == "child" else f"church register with the {rel}'s family"
    if re.search(r"Histories|History Books|Genealog|Cyclopedia|Surname|Membership", c): return "compiled lineage; subject likely included (a hint, not proof)"
    if re.search(r"Draft", c): return "next of kin / employer on the draft card" if rel in ("child", "spouse") else "draft card of a relative"
    if re.search(r"Directories", c): return "adults of the household, address"
    if re.search(r"Naturalization|Passenger|Immigration", c): return "family group, origin, arrival"
    return f"record about the {rel}; may name the subject"

def footprint(cat: Catalog, pid: str):
    p = cat.person(pid); fam = cat.family(pid); ev = cat.events(pid)
    given = p["names"][0][0] if p["names"] else None; surname = p["names"][0][1] if p["names"] else None
    dated = [e["year"] for e in ev if e["year"]]
    birth = next((e for e in ev if e["type"] == "Birth" and e["year"]), None); death = next((e for e in ev if e["type"] in ("Death", "Burial") and e["year"]), None)
    b = birth["year"] if birth else (min(dated) - 20 if dated else None)
    d = death["year"] if death else (b + 90 if b else None)
    alive = lambda y: (b is None) or (b <= y <= (d or 9999))
    states = {e["place"]["state"] for e in ev if e["place"] and e["place"]["state"]}
    relatives = [(rid, rname, RELATION_NAMES[g]) for g in ("spouses", "children", "parents", "siblings") for rid, rname in fam[g]]
    related_ids = {rid for rid, _, _ in relatives} | {pid}

    # ---- duplicates: same name and same birth year, or same name and a shared spouse/parent name
    duplicates, unlinked = [], []
    if surname:
        rows = cat.q("""SELECT p.id, p.display_name, n.given, n.surname FROM person p JOIN person_name n ON n.person_id=p.id AND n.is_primary
                        WHERE p.tree_id=? AND p.id<>?""", cat.tree_id, pid)
        my_spouses = {n.lower() for _, n in fam["spouses"]}; my_parents = {n.lower() for _, n in fam["parents"]}
        for oid, oname, ogiven, osurname in rows:
            if soundex(osurname) != soundex(surname): continue
            same_given = (ogiven or "").split(" ")[0].lower() == (given or "").split(" ")[0].lower()
            of = cat.family(oid); oev = cat.events(oid)
            ob = next((e["year"] for e in oev if e["type"] == "Birth" and e["year"]), None)
            o_spouses = {n.lower() for _, n in of["spouses"]}; o_parents = {n.lower() for _, n in of["parents"]}
            if same_given and b and ob and abs(ob - b) <= 1:
                duplicates.append({"id": oid, "name": oname, "why": f"{oname} [{oid[-6:]}]: same name, born {ob}"}); continue
            if same_given and ((my_spouses & o_spouses) or (my_parents & o_parents)):
                duplicates.append({"id": oid, "name": oname, "why": f"{oname} [{oid[-6:]}]: same name and the same spouse or parents"}); continue
            if oid in related_ids: continue
            ostates = {e["place"]["state"] for e in oev if e["place"] and e["place"]["state"]}
            if b and ob and abs(ob - b) <= 50 and (not states or not ostates or states & ostates):
                gen = "possible parent" if 15 <= b - ob <= 50 else ("possible child" if 15 <= ob - b <= 50 else "possible sibling or cousin")
                unlinked.append({"id": oid, "name": oname, "role": gen, "why": f"{oname} [{oid[-6:]}]: same surname, born {ob}" + (f", {', '.join(sorted(states & ostates)).title()}" if states & ostates else "") + f"; {gen}, not linked"})

    # ---- records on relatives
    own_keys = set()
    for cname, apid, held, _ in cat.person_citations(pid):
        if apid or held: own_keys.add(f"page:{cname}" if re.search(r"Federal Census|State Census", cname or "") else (apid or held))
    by_key = {}
    for rid, rname, rel in relatives:
        for cname, apid, held, cid in cat.person_citations(rid):
            key = apid or held
            if not key: continue
            if re.search(r"Federal Census|State Census", cname or ""): key = f"page:{cname}"   # one household page, many record ids
            r = by_key.setdefault(key, {"key": key, "apid": apid, "collection": cname, "collection_id": cid, "held": held or bool(cat.held_for(apid, rid)), "on": [], "on_subject": key in own_keys})
            if (rname, rel) not in r["on"]: r["on"].append((rname, rel))
    records = []
    for r in by_key.values():
        if r["on_subject"]: continue                     # already attached to the subject: it is on their own checklist
        rel_for_expect = r["on"][0][1]
        r["expect"] = expect(r["collection"], rel_for_expect, alive, p["sex"])
        m = re.match(r"^(\d{4}) United States Federal Census", r["collection"] or "")
        if m and b and int(m.group(1)) < b: continue      # a census before the subject was born says nothing about them
        decisive = 3 if re.search(r"names (the subject as parent|both parents|the same parents)|parents of both|named as heir", r["expect"]) else (2 if re.search(r"household: subject", r["expect"]) else 1)
        r["rank"] = (len(r["on"]), decisive, 1 if r["held"] else 0)
        records.append(r)
    records.sort(key=lambda r: r["rank"], reverse=True)
    collections_ = collections.Counter(r["collection"] for r in records if r["collection"])
    coll = [{"name": n, "count": c} for n, c in collections_.most_common()]
    return {"person": {"id": pid, "name": p["name"], "span": [b, d]},
            "summary": {"relatives": len(relatives), "records": len(records), "shared": sum(1 for r in records if len(r["on"]) > 1)},
            "duplicates": duplicates, "unlinked": unlinked, "records": records, "collections": coll}

def render(fp):
    P = fp["person"]; s = fp["summary"]
    out = [f"{P['name']}  ({P['span'][0]}–{P['span'][1]})", f"  {s['records']} records on {s['relatives']} relatives; {s['shared']} hold 2+ family members"]
    if fp["duplicates"]: out.append("\nDUPLICATES (resolve first)"); out += [f"  {x['why']}" for x in fp["duplicates"]]
    if fp["unlinked"]: out.append("\nUNLINKED, SAME SURNAME (hints)"); out += [f"  {x['why']}" for x in fp["unlinked"]]
    out.append("\nRECORDS ON RELATIVES, RANKED")
    for r in fp["records"]:
        flag = "H" if r["held"] else " "
        out.append(f"  [{flag}] {r['collection'][:46]:46} {len(r['on'])}x on " + ", ".join(f"{n} ({rel})" for n, rel in r["on"])[:48])
        out.append(f"        -> {r['expect']}")
    if fp["collections"]:
        out.append("\nSAME COLLECTIONS TO SEARCH FOR THE FAMILY"); out += [f"  {c['count']:2}  {c['name']}" for c in fp["collections"]]
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who"); ap.add_argument("--tree"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    pid = cat.find_person(a.who); bl = cat.baseline(pid)
    if not bl["complete"]:
        sys.exit(f"{cat.person(pid)['name']}: baseline not reviewed ({', '.join(bl['undecided'])} undecided); the footprint, duplicates and unlinked persons come after review")
    fp = footprint(cat, pid)
    print(json.dumps(fp, ensure_ascii=False, indent=1) if a.json else render(fp))

if __name__ == "__main__":
    main()
