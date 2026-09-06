#!/usr/bin/env python3
"""Decision cards: every Undecided proposal about a person as one card, in plain text or as data.

usage: tools/cards.py "<person>" [--tree slug] [--db catalog/tree.db] [--json]
       tools/cards.py --all [--tree slug] [--json]          # every person with an Undecided proposal

One card per proposal, in the shape the owner approved (docs/DIRECTOR-HANDOVER.md, the decision card): a one-line
highlight of what the record is and the links it makes; the person and the fact or link with the file's claim; the record
with its holder, collection, own identity and trust tier; the primary document as the archived path and the holder's page;
what the record says field by field against the tree's claim, as agrees, disagrees or absent; the relationships the record
states and who on it is already matched or accepted; what accepting closes, from the person's open questions when the step
carries one and from the checklist row otherwise; anything odd. No scores. The person screen's proposal panel shows the same
card from card() and render() here, so the two never drift. Nothing here writes.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DATA_ROOT, ROOT, object_path, resolve_tree
from catalog import Catalog, fetch_target, year

REL_WORD = {"parent": "parent", "child": "child", "spouse": "spouse", "sibling": "sibling"}

def _key(s): return re.sub(r"[^a-z]", "", (s or "").lower())
def _tokens(s): return [t for t in re.split(r"[,\s]+", (s or "").lower()) if re.sub(r"[^a-z]", "", t)]

COUNTRY = re.compile(r"\b(united states of america|united states|u\.s\.a\.|u\.s\.|usa|us)\b", re.I)

def _place_verdict(record, tree):
    """agrees when the tree's place (its last two named parts below the country, e.g. town and county) is found in the record's
    place text, or the record's first part in the tree's; the tree's own resolved chain reads 'Town < County < State < Country'
    and the country's spellings are one."""
    if not record or not tree: return "absent"
    norm = lambda s: COUNTRY.sub("usa", s.lower())
    tparts = [p.strip() for p in re.split(r"<|,", norm(tree)) if p.strip()]; rlow = _key(norm(record))
    below = [p for p in tparts if p != "usa"] or tparts
    if all(_key(p) in rlow for p in below[-2:]): return "agrees"
    rparts = [p.strip() for p in norm(record).split(",") if p.strip()]
    if rparts and _key(rparts[0]) in _key(norm(tree)): return "agrees"
    return "disagrees"

def _date_verdict(rec_start, tree_start):
    if not rec_start or not tree_start: return "absent"
    if rec_start == tree_start: return "agrees"
    return "agrees" if rec_start[:4] == tree_start[:4] else "disagrees"

def _fmt(date_text, place): return ", ".join(x for x in (date_text, place) if x) or None

def persona_facts(cx, persona_id):
    return [dict(r) for r in cx.execute("""SELECT pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, ps.raw AS place, pf.region_json
                                           FROM persona_fact pf LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pf.persona_id=? ORDER BY pf.id""", (persona_id,))]

def persona_status(cx, tree_id, persona_id):
    """How a persona on the record stands to the tree: accepted as <person>, proposed as <person>, proposed as a new person,
    rejected, or no proposal."""
    pp = cx.execute("""SELECT pp.status, p.display_name FROM person_persona pp JOIN person p ON p.id=pp.person_id WHERE pp.persona_id=? AND p.tree_id=?""", (persona_id, tree_id)).fetchone()
    if pp and pp["status"] == "accepted": return f"accepted as {pp['display_name']}"
    pr = cx.execute("""SELECT pr.kind, pr.status, c.display_name FROM proposal pr LEFT JOIN person c ON c.id=json_extract(pr.payload_json,'$.person_id')
                       WHERE pr.tree_id=? AND json_extract(pr.payload_json,'$.persona_id')=? ORDER BY pr.created_at DESC LIMIT 1""", (tree_id, persona_id)).fetchone()
    if not pr: return "no proposal"
    if pr["status"] == "undecided": return f"proposed as {pr['display_name']}" if pr["kind"] == "persona_match" else "proposed as a new person"
    return f"{pr['status']}: {pr['kind'].replace('_', ' ')}" + (f" {pr['display_name']}" if pr["display_name"] else "")

def card(cx, tree_id, prop_id):
    """The decision card for one proposal, as data."""
    cx.row_factory = sqlite3.Row
    p = cx.execute("SELECT * FROM proposal WHERE id=? AND tree_id=?", (prop_id, tree_id)).fetchone()
    if not p or p["kind"] not in ("persona_match", "new_person"): return None
    pay = json.loads(p["payload_json"]); cat = Catalog(cx, tree_id)
    pe = cx.execute("SELECT id, name_text, sex, role_in_record, region_json, artifact_sha256 FROM persona WHERE id=?", (pay["persona_id"],)).fetchone()
    sha = pe["artifact_sha256"]
    a = cx.execute("""SELECT a.sha256, a.mime, a.trust_tier, a.locator_kind, a.locator_value, a.original_filename, a.retrieved_at, a.source_id, s.name AS source_name, c.name AS collection
                      FROM artifact a LEFT JOIN source s ON s.id=a.source_id LEFT JOIN collection c ON c.id=a.collection_id WHERE a.sha256=?""", (sha,)).fetchone()
    own_ids = [f"{r['kind']} {r['value']}" for r in cx.execute("SELECT kind, value FROM artifact_locator WHERE artifact_sha256=?", (sha,))]
    mem = next((json.loads(r["region_json"] or "{}").get("memorial_id") for r in cx.execute("SELECT region_json FROM persona WHERE artifact_sha256=? AND role_in_record='memorial'", (sha,))), None)
    if mem: own_ids.append(f"memorial {mem}")
    cited = cat.cited().get(a["locator_value"], {}) if a["locator_kind"] == "apid" else {}
    page = fetch_target(a["locator_value"], cited.get("url"))["url"] if a["locator_kind"] == "apid" else None
    ORDER = {"Name": 0, "Sex": 1, "Birth": 2, "Death": 3, "Burial": 4, "Age": 5}
    facts = sorted(persona_facts(cx, pe["id"]), key=lambda f: ORDER.get(f["fact_type"], 9))
    # ---- the person and the file's claim
    person_id = pay.get("person_id"); person = None; fields = []
    if person_id:
        pr = cat.person(person_id); ev = cat.events(person_id)
        first = lambda t: next((e for e in ev if e["type"] == t), None)
        claim = {"name": pr["name"], "sex": pr["sex"]}
        for t in ("Birth", "Death", "Burial"):
            e = first(t); claim[t.lower()] = {"date": e["date_text"], "start": (cx.execute("SELECT date_start FROM event WHERE id=?", (e["id"],)).fetchone() or [None])[0], "place": e["place"]["text"] if e and e["place"] else None} if e else None
        person = {"id": person_id, "name": pr["name"], "span": [year(claim["birth"]["start"]) if claim["birth"] else None, year(claim["death"]["start"]) if claim["death"] else None], "claim": claim}
        # field by field
        name_f = next((f for f in facts if f["fact_type"] == "Name"), None)
        if name_f:
            rt = _tokens(name_f["value_text"]); keys = {(_key(n[0].split()[0]) if n[0] else "", _key(n[1])) for n in pr["names"]}
            given_ok = any(g and rt and _key(rt[0]) == g for g, _ in keys); sur_ok = any(s and _key(t) == s for t in rt[1:] for _, s in keys)
            fields.append({"field": "Name", "record": name_f["value_text"], "tree": pr["name"], "verdict": "agrees" if given_ok and sur_ok else ("disagrees" if rt else "absent")})
        sx = pe["sex"] or next((f["value_text"] for f in facts if f["fact_type"] == "Sex"), None)
        fields.append({"field": "Sex", "record": sx, "tree": pr["sex"], "verdict": "absent" if not (sx and pr["sex"] in ("M", "F")) else ("agrees" if sx[:1].upper() == pr["sex"] else "disagrees")})
        for t in ("Birth", "Death", "Burial"):                  # a date and a place are two fields: each agrees, disagrees or is absent on its own
            f = next((x for x in facts if x["fact_type"] == t), None); c = claim[t.lower()]
            if not f and not c: continue
            fields.append({"field": f"{t} date", "record": f["date_text"] if f else None, "tree": c["date"] if c else None, "verdict": _date_verdict(f["date_start"] if f else None, c["start"] if c else None)})
            fields.append({"field": f"{t} place", "record": f["place"] if f else None, "tree": c["place"] if c else None, "verdict": _place_verdict(f["place"] if f else None, c["place"] if c else None)})
            if f and f["value_text"]: fields.append({"field": t, "record": f["value_text"], "tree": None, "verdict": "absent"})
        for f in facts:
            if f["fact_type"] in ("Name", "Sex", "Birth", "Death", "Burial", "Identification Number"): continue
            fields.append({"field": f["fact_type"] if f["fact_type"] != "Unknown" else (json.loads(f["region_json"] or "{}").get("labels") or ["Unknown"])[0], "record": " ".join(x for x in (f["value_text"], f["date_text"], f["place"]) if x), "tree": None, "verdict": "absent"})
    else:
        for f in facts:
            if f["fact_type"] == "Identification Number": continue
            fields.append({"field": f["fact_type"], "record": " ".join(x for x in (f["value_text"], f["date_text"], f["place"]) if x), "tree": None, "verdict": "absent"})
    # ---- relationships the record states, both ways, with how the other persona stands
    rels = []
    for r in cx.execute("SELECT r.kind, r.value_text, o.id AS oid, o.name_text AS other FROM persona_relation r JOIN persona o ON o.id=r.related_persona_id WHERE r.persona_id=?", (pe["id"],)):
        rels.append({"direction": "is", "kind": r["kind"], "as_written": r["value_text"], "other": r["other"], "other_status": persona_status(cx, tree_id, r["oid"]), "mapped": r["kind"] in REL_WORD})
    for r in cx.execute("SELECT r.kind, r.value_text, o.id AS oid, o.name_text AS other FROM persona_relation r JOIN persona o ON o.id=r.persona_id WHERE r.related_persona_id=?", (pe["id"],)):
        rels.append({"direction": "has", "kind": r["kind"], "as_written": r["value_text"], "other": r["other"], "other_status": persona_status(cx, tree_id, r["oid"]), "mapped": r["kind"] in REL_WORD})
    # ---- what accepting closes
    closes = []; subject = pay.get("subject_person_id")
    if person_id:
        held = cat.held_apids(); ids = {k for k, v in held.items() if v == sha}
        for st in cx.execute("SELECT id, row_key, question_id, status FROM search_plan WHERE person_id=? AND kind='fetch' ORDER BY seq", (person_id,)):
            loc = cx.execute("SELECT locator_kind, locator_value FROM search_plan WHERE id=?", (st["id"],)).fetchone()
            if not ((loc["locator_kind"] == "apid" and loc["locator_value"] in ids) or (loc["locator_kind"] != "apid" and cx.execute("SELECT 1 FROM artifact WHERE sha256=? AND locator_kind=? AND locator_value=?", (sha, loc["locator_kind"], loc["locator_value"])).fetchone())): continue
            q = cx.execute("SELECT kind, detail_json FROM research_question WHERE id=? AND status='open'", (st["question_id"],)).fetchone() if st["question_id"] else None
            if q: closes.append(f"the question {q['kind']} {json.loads(q['detail_json'] or '{}').get('detail') or ''}".strip() + f" ({st['row_key'].split(':')[0]} row)")
            else: closes.append(f"the {st['row_key'].split(':')[0]} row for {person['name']}: this record is the fetch")
        evidence = [f"{f['fact_type']} {f['date_text'] or f['value_text'] or ''}".strip() for f in facts if f["fact_type"] in ("Name", "Birth", "Death", "Burial") and (f["date_text"] or f["value_text"] or f["place"])]
        if evidence: closes.append("held evidence to accept on: " + ", ".join(evidence))
        for q in cx.execute("SELECT kind, detail_json FROM research_question WHERE subject_person_id=? AND status='open' AND kind IN ('unverified_claim','missing_fact')", (person_id,)):
            d = json.loads(q["detail_json"] or "{}").get("detail") or ""
            if q["kind"] == "unverified_claim" and any(f["fact_type"] in d for f in facts if f["fact_type"] in ("Birth", "Death", "Burial")): closes.append(f"the question unverified_claim: {d}")
            if q["kind"] == "missing_fact" and any(f["fact_type"].lower() == d.split()[0] and (f["date_text"] if "date" in d else f["place"]) for f in facts): closes.append(f"the question missing_fact: {d}")
    else:
        joins = [r for r in rels if r["direction"] == "is" and r["kind"] in ("child", "parent", "spouse")]
        for r in joins:
            if r["other_status"].startswith("accepted as "): closes.append(f"creates {pe['name_text']} in this tree as {REL_WORD[r['kind']]} of {r['other_status'][12:]} (the record's {r['as_written']})")
            elif r["other_status"].startswith("proposed as "): closes.append(f"creates {pe['name_text']} in this tree; joins the family of {r['other_status'][12:]} as {REL_WORD[r['kind']]} once that match is accepted (the record's {r['as_written']})")
            else: closes.append(f"creates {pe['name_text']} in this tree; the record's {r['as_written']} of {r['other']}, who is {r['other_status']}")
        for r in [r for r in rels if r["direction"] == "is" and r["kind"] == "sibling"]:
            closes.append(f"creates {pe['name_text']} in this tree with no family link yet: the record's {r['as_written']} of {r['other']} ({r['other_status']}) places nobody until the parents are stated")
        if not joins and not any(r["direction"] == "is" and r["kind"] == "sibling" for r in rels): closes.append(f"creates {pe['name_text']} in this tree with no family link: the record states none the matcher maps")
    # ---- anything odd
    odd = [f"{f['field']} disagrees: record {f['record']}, tree {f['tree']}" for f in fields if f["verdict"] == "disagrees"]
    m = re.search(r"Also fits: (.+?)\.$", p["rationale"] or "")
    if m: odd.append(f"also fits {m.group(1)}")
    odd += [f"the record's heading {r['as_written']!r} is not one the matcher maps to a family link" for r in rels if not r["mapped"]]
    if person and person["span"][0]:
        for f in facts:
            if f["fact_type"] in ("Death", "Burial", "Residence") and year(f["date_start"]) and year(f["date_start"]) < person["span"][0]: odd.append(f"{f['fact_type']} {f['date_text']} is before the tree's birth year {person['span'][0]}")
    if person and fields and fields[0]["field"] == "Name" and fields[0]["verdict"] == "agrees" and _key(_tokens(fields[0]["record"])[-1]) not in {_key(n[1]) for n in cat.person(person_id)["names"]}: odd.append(f"the record writes the name as {fields[0]['record']}; the tree has {person['name']}")
    if person and any(f["field"] == "Sex" and f["verdict"] == "absent" for f in fields) and not person["claim"]["sex"]: odd.append("the tree has no sex for this person")
    if a["mime"] and not a["mime"].startswith("text/html"): odd.append(f"the record is {a['mime']}, transcribed by hand")
    # ---- highlight
    links = [f"{REL_WORD.get(r['kind'], r['kind'])} of {r['other']} ({r['other_status']})" for r in rels if r["direction"] == "is"] or \
            [f"{r['other']} as {r['as_written'].lower()} ({r['other_status']})" for r in rels if r["direction"] == "has"]
    rec_name = f"{a['source_name'] or a['source_id'] or 'record'}" + (f", {own_ids[-1]}" if own_ids else "")
    what = f"{pe['name_text']} ({pe['role_in_record']}) on {rec_name}"
    highlight = (f"{what} may be {person['name']}" if person else f"{what} is nobody in the tree yet") + (": " + "; ".join(links[:4]) if links else "") + ("" if len(links) <= 4 else f"; and {len(links) - 4} more")
    subj = cx.execute("SELECT display_name FROM person WHERE id=?", (subject,)).fetchone() if subject else None
    return {"id": p["id"], "kind": p["kind"], "status": p["status"], "highlight": highlight, "person": person, "subject": subj["display_name"] if subj else None,
            "persona": {"id": pe["id"], "name": pe["name_text"], "role": pe["role_in_record"], "sex": pe["sex"]},
            "record": {"holder": a["source_name"], "holder_id": a["source_id"], "collection": a["collection"], "identity": [f"{a['locator_kind']} {a['locator_value']}"] + own_ids, "tier": a["trust_tier"],
                       "archived": os.path.relpath(object_path(sha), DATA_ROOT), "sha256": sha, "page": page, "retrieved_at": a["retrieved_at"], "filename": a["original_filename"]},
            "fields": fields, "relationships": rels, "closes": closes, "odd": odd or ["nothing"], "rationale": p["rationale"]}

def render(c):
    """The card as plain text."""
    w = 10; L = lambda k, v: f"{k:<{w}}{v}"
    out = [f"CARD {c['id']}  [{c['kind'].replace('_', ' ')}]", L("", c["highlight"])]
    if c["person"]:
        cl = c["person"]["claim"]; claim = "; ".join(x for x in [f"born {_fmt(cl['birth']['date'], cl['birth']['place'])}" if cl["birth"] else None, f"died {_fmt(cl['death']['date'], cl['death']['place'])}" if cl["death"] else None,
                                                              f"buried {_fmt(cl['burial']['date'], cl['burial']['place'])}" if cl["burial"] else None] if x) or "no dates"
        out.append(L("Person", f"{c['person']['name']}  file's claim: {claim}"))
    else: out.append(L("Person", f"nobody yet; the record is about the family of {c['subject']}" if c["subject"] else "nobody yet"))
    r = c["record"]; out.append(L("Record", f"{r['holder'] or r['holder_id']}; {r['collection'] or 'collection unknown'}; {', '.join(r['identity'])}; tier {r['tier']}"))
    out.append(L("Document", f"{r['archived']}" + (f"  |  {r['page']}" if r["page"] else "")))
    for i, f in enumerate(c["fields"]):
        out.append(L("Fields" if i == 0 else "", f"{f['field']:<14}{f['verdict']:<11}record: {f['record'] or '-'}" + (f"  |  tree: {f['tree']}" if f["tree"] else "")))
    if not c["fields"]: out.append(L("Fields", "the record states nothing beyond the name"))
    for i, rl in enumerate(c["relationships"]):
        line = (f"{rl['as_written'] or rl['kind']} of {rl['other']}" if rl["direction"] == "is" else f"{rl['other']} listed under {rl['as_written'] or rl['kind']}") + f"  ({rl['other_status']})" + ("" if rl["mapped"] else "  [heading not mapped]")
        out.append(L("Relations" if i == 0 else "", line))
    if not c["relationships"]: out.append(L("Relations", "none stated"))
    for i, x in enumerate(c["closes"]): out.append(L("Closes" if i == 0 else "", x))
    if not c["closes"]: out.append(L("Closes", "nothing on the plan"))
    for i, x in enumerate(c["odd"]): out.append(L("Odd" if i == 0 else "", x))
    out.append(L("Matcher", c["rationale"] or ""))
    return "\n".join(out)

def cards_for(cx, tree_id, pid=None):
    """Undecided proposals for one person (as the matched person or the subject of a new-person proposal), or for everyone."""
    if pid: rows = cx.execute("""SELECT id FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person')
                                 AND (json_extract(payload_json,'$.person_id')=? OR (json_extract(payload_json,'$.person_id') IS NULL AND json_extract(payload_json,'$.subject_person_id')=?)) ORDER BY created_at""", (tree_id, pid, pid)).fetchall()
    else: rows = cx.execute("SELECT id FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person') ORDER BY created_at", (tree_id,)).fetchall()
    return [c for c in (card(cx, tree_id, r[0]) for r in rows) if c]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who", nargs="?"); ap.add_argument("--all", action="store_true"); ap.add_argument("--tree"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.row_factory = sqlite3.Row; tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    if not a.all and not a.who: sys.exit("give a person or --all")
    out = cards_for(cx, tree_id, None if a.all else cat.find_person(a.who))
    if a.json: print(json.dumps(out, ensure_ascii=False, indent=1)); return
    if not out: print("no undecided proposal" + ("" if a.all else " for this person")); return
    print("\n\n".join(render(c) for c in out))

if __name__ == "__main__": main()
