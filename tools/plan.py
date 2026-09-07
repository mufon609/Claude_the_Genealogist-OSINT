#!/usr/bin/env python3
"""Materialize a person's questions and steps into the catalog (research_question, search_plan).

usage: tools/plan.py "<person>" [--tree slug]      tools/plan.py --all [--tree slug]

Questions are fact-level (missing parents, no surname, conflict, ...). A step
belongs to the person and a checklist row: a fetch of a record the tree already
cites (one per citation, with its locator), or a typed search for a missing row.
Footprint records on relatives become fetch steps under the fact-level question
they serve. A fetch is re-targeted to the free holder of the citation's
collection (data/holders.csv): the step's locator source is the holder and its
fields are the citation's own details (collection, the name the citation sits
on, the page text's parts, the memorial URL), basis citation. A citation whose
collection has no free holder stays a fetch step with mode blocked and the
reason in its rationale. Idempotent: questions and steps are keyed, so re-running updates what
changed, adds what is new, drops steps no longer generated unless they were run,
marks a fetch step done when its record is in the archive (under the step's
record id or under another id naming the same census page: a household's page
is held for every member cited on it), keeps done steps, and closes questions
whose gap has gone (closed_reason 'gap_gone'). A question a person dismissed or answered stays closed. Nothing
here runs a search. Before writing anything the plan checks that every holder
in data/holders.csv and every source id the checklist emits is a row in the
catalog's source table, and stops with one line naming the missing ids and the
sync command (tools/initdb.py --sync-sources) when the registry is out of step.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, resolve_tree, ulid
from catalog import Catalog, dbid_of
from checklist import build

FOOTPRINT_HOME = ("missing_parents", "identity_incomplete", "missing_spouse", "unverified_claim")
ANCESTRY = "B02"

def q_key(q):
    """Stable key: kind plus the other person's id when the question is about one, else kind plus detail."""
    if q.get("other_id"): return q["kind"] + ":" + q["other_id"]
    return q["kind"] + ":" + re.sub(r"\s+", " ", (q.get("detail") or "")).strip()[:120]

def citation_fields(collection, cited, name):
    """The citation's own details as query fields, each {value, basis 'citation'}: the collection, the name the citation sits on,
    every 'Label: value' part of the page text under its label, the rest of the page text under 'citation', the memorial URL."""
    f = lambda v: {"value": v, "basis": "citation"}
    out = {"collection": f(collection)}
    if name: out["name"] = f(name)
    rest = []
    for part in (cited.get("page") or "").split("; "):
        m = re.fullmatch(r"([A-Za-z][A-Za-z .]{0,40}): (.+)", part.strip())
        if m and m.group(1).lower() not in out: out[m.group(1).lower()] = f(m.group(2).strip())
        elif part.strip(): rest.append(part.strip())
    if rest: out["citation"] = f("; ".join(rest))
    if cited.get("url"): out["url"] = f(cited["url"])
    return out

def fetch_step(cat, row_key, query_type, apid, collection, collection_id, on, expected, where, sources, name, question_key=None):
    cited = cat.cited().get(apid, {})
    holder = (cat.holders.get(dbid_of(apid)) or [None])[0]
    names = cited.get("names") or []
    fields = citation_fields(collection, cited, names[0] if names else name)
    if holder: source, mode, why = holder["HolderSourceId"], "fetch", f"fetch the record at {holder['HolderCollection']}"
    else: source, mode, why = ANCESTRY, "blocked", "blocked: no free holder of this collection yet, and Ancestry needs a membership this account lacks"
    return {"step_key": f"fetch:{apid}", "row_key": row_key, "question_key": question_key, "kind": "fetch", "query_type": query_type, "query_json": dumps(fields),
            "locator_source_id": source, "locator_kind": "apid", "locator_value": apid, "collection_id": collection_id, "on_json": dumps(on),
            "sources_json": dumps(sources), "mode": mode, "expected": expected, "rationale": f"{where}; {why}"}

MEMORIAL = re.compile(r"/memorial/(\d+)(?:/|$)")
REL_TO = {"parent": "child", "child": "parent", "spouse": "spouse", "sibling": "sibling"}      # the record's subject, seen from the persona

def linked_records(cx, tree_id, cat, pid, me):
    """Fetch steps for the records a held record links from a persona accepted as this person: a Find a Grave memorial lists its
    family members with each one's own memorial, so once the owner has said the listed parent is John Y Davidson, John's own
    memorial is a lead on John (docs/RESEARCH-WORKFLOW.md §0), under his cemetery row, with the linked record's own identity as
    the locator and the page's words as its fields (basis record). Nothing is generated for a persona only proposed."""
    out = []; q = cx.cursor(); q.row_factory = sqlite3.Row
    col = q.execute("SELECT id, name FROM collection WHERE name LIKE 'U.S., Find a Grave%' ORDER BY name LIMIT 1").fetchone()
    for r in q.execute("""SELECT pe.name_text, pe.role_in_record, pe.region_json, s.display_name AS subject FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                           JOIN extraction e ON e.id=pe.extraction_id JOIN persona sub ON sub.extraction_id=e.id AND sub.role_in_record='memorial'
                           LEFT JOIN person_persona sp ON sp.persona_id=sub.id AND sp.status='accepted' LEFT JOIN person s ON s.id=sp.person_id
                           WHERE pp.person_id=? AND pp.status='accepted' AND e.superseded_by IS NULL AND pe.role_in_record<>'memorial'""", (pid,)):
        m = MEMORIAL.search((json.loads(r["region_json"] or "{}").get("url") or ""))
        if not m: continue
        mid = m.group(1); url = f"https://www.findagrave.com/memorial/{mid}/"
        subject = r["subject"] or "the memorial's subject"; rel = REL_TO.get(r["role_in_record"], r["role_in_record"])
        fields = {"collection": {"value": col["name"] if col else "Find a Grave", "basis": "record"}, "name": {"value": r["name_text"], "basis": "record"},
                  "url": {"value": url, "basis": "record"}, "linked from": {"value": f"{subject}'s memorial, where {r['name_text']} is listed under {r['role_in_record']}", "basis": "record"}}
        out.append({"step_key": f"fetch:memorial:{mid}", "row_key": "cemetery / family plot:", "question_key": None, "kind": "fetch", "query_type": "subject_record",
                    "query_json": dumps(fields), "locator_source_id": "E01", "locator_kind": "memorial_id", "locator_value": mid, "collection_id": col["id"] if col else None,
                    "on_json": dumps([[subject, rel]]), "sources_json": dumps(["E01"]), "mode": "fetch", "expected": "the person's own memorial: name, dates, cemetery, plot, the family it links",
                    "rationale": f"named on {subject}'s memorial with a link to their own; fetch it by the one-call method"})
    return out

class RegistryOutOfStep(Exception):
    """A source id the plan would write is not in the catalog's source table."""

def check_registry(cx, cat, r=None):
    """Every holder in data/holders.csv and every source id the checklist emits must be a row in source, or the plan would
    write a step against a missing row and fail on a foreign key. Raises RegistryOutOfStep naming the ids and the fix."""
    ids = {h["HolderSourceId"] for rows in cat.holders.values() for h in rows}
    if r: ids |= {sid for grp in ("A", "B") for row in r["checklist"][grp] for sid in row.get("sources") or []}
    have = {row[0] for row in cx.execute("SELECT id FROM source")}
    missing = sorted(ids - have)
    if missing: raise RegistryOutOfStep(f"registry out of step with the catalog: source id(s) {', '.join(missing)} not in the source table; run python3 tools/initdb.py --sync-sources --db <this catalog>")

def plan_person(cx, tree_id, pid, by):
    cat = Catalog(cx, tree_id); r = build(cat, pid); ts = now(); me = r["person"]["name"]
    check_registry(cx, cat, r)
    wanted = {q_key(q): (q["kind"], dumps(q)) for q in r["questions"]}
    fetches, searches = [], []
    for grp in ("A", "B"):
        for row in r["checklist"][grp]:
            s = row.get("search")
            if not s: continue
            rk = f"{row['record']}:{row.get('instance') or ''}"
            if row["status"] == "cited":
                for c in row["citations"]:
                    where = "cited on " + ", ".join(n for n, _ in c["on"]) if c["on"] else "cited on this person"
                    fetches.append(fetch_step(cat, rk, s["type"], c["apid"], c["collection"], c["collection_id"], c["on"], row["settles"], where, row["sources"],
                                              c["on"][0][0] if c["on"] else me))
            else:
                searches.append({"step_key": f"search:{rk}", "row_key": rk, "question_key": None, "kind": "search", "query_type": s["type"], "query_json": dumps(s["fields"]),
                                 "locator_source_id": None, "locator_kind": None, "locator_value": None, "collection_id": None, "on_json": None,
                                 "sources_json": dumps(s["sources"]), "mode": s["mode"], "expected": s["expect"], "rationale": f"{row['record']} is missing for this person"})
    for lk in linked_records(cx, tree_id, cat, pid, me):                # a held record that names this person and links their own record: a lead
        if not any(lk["locator_value"] in (json.loads(f["query_json"]).get("url") or {}).get("value", "") for f in fetches): fetches.append(lk)
    home = next((k for k in wanted if wanted[k][0] in FOOTPRINT_HOME), None)
    have = {st["locator_value"] for st in fetches}
    for rec in r["footprint"]["records"][:12]:
        if not rec.get("apid") or rec["apid"] in have: continue
        fetches.append(fetch_step(cat, f"footprint:{rec['apid']}", "footprint_record", rec["apid"], rec["collection"], rec.get("collection_id"), rec["on"], rec["expect"],
                                  "already on " + ", ".join(f"{n} ({rel})" for n, rel in rec["on"]), [ANCESTRY], rec["on"][0][0] if rec["on"] else me, home))
    stats = {"questions_new": 0, "questions_kept": 0, "questions_closed": 0, "questions_left_closed": 0, "steps_new": 0, "steps_kept": 0, "steps_dropped": 0, "steps_done_by_archive": 0}
    existing = {row[1]: row[0] for row in cx.execute("SELECT id, q_key FROM research_question WHERE subject_person_id=? AND status='open'", (pid,))}
    qid_by_key = {}
    for key, (kind, detail) in wanted.items():
        if key in existing: qid = existing[key]; cx.execute("UPDATE research_question SET detail_json=? WHERE id=?", (detail, qid)); stats["questions_kept"] += 1
        else:
            closed = cx.execute("SELECT id, closed_reason FROM research_question WHERE subject_person_id=? AND q_key=?", (pid, key)).fetchone()
            if closed and closed[1] != "gap_gone": stats["questions_left_closed"] += 1; continue      # a person dismissed or answered it
            if closed: qid = closed[0]; cx.execute("UPDATE research_question SET status='open', closed_reason=NULL, closed_at=NULL, detail_json=? WHERE id=?", (detail, qid))
            else: qid = ulid(); cx.execute("INSERT INTO research_question (id,tree_id,subject_person_id,kind,q_key,detail_json,status,created_at) VALUES (?,?,?,?,?,?,'open',?)", (qid, tree_id, pid, kind, key, detail, ts))
            stats["questions_new"] += 1
        qid_by_key[key] = qid
    stats["closed"] = []                                                 # the ids closed by this run, for a caller that knows what answered them
    for key, qid in existing.items():
        if key not in wanted:
            cx.execute("UPDATE research_question SET status='closed', closed_reason='gap_gone', closed_at=? WHERE id=?", (ts, qid)); stats["questions_closed"] += 1; stats["closed"].append(qid)
    have_steps = {row[1]: row[0] for row in cx.execute("SELECT id, step_key FROM search_plan WHERE person_id=?", (pid,))}
    seen, wanted_keys = {}, set()
    for seq, st in enumerate(fetches + searches, 1):
        n = seen[st["step_key"]] = seen.get(st["step_key"], 0) + 1      # two identical steps (e.g. two spouses of the same name)
        if n > 1: st["step_key"] += f":{n}"
        wanted_keys.add(st["step_key"])
        qid = qid_by_key.get(st["question_key"]) if st["question_key"] else None
        cols = (st["row_key"], qid, seq, st["kind"], st["query_type"], st["query_json"], st["locator_source_id"], st["locator_kind"], st["locator_value"],
                st["collection_id"], st["on_json"], st["sources_json"], st["mode"], st["expected"], st["rationale"])
        if st["step_key"] in have_steps:
            cx.execute("""UPDATE search_plan SET row_key=?, question_id=?, seq=?, kind=?, query_type=?, query_json=?, locator_source_id=?, locator_kind=?, locator_value=?,
                          collection_id=?, on_json=?, sources_json=?, mode=?, expected=?, rationale=? WHERE id=?""", cols + (have_steps[st["step_key"]],)); stats["steps_kept"] += 1
        else:
            cx.execute("""INSERT INTO search_plan (row_key,question_id,seq,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,collection_id,on_json,sources_json,mode,expected,rationale,
                          id,person_id,step_key,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'planned',?)""", cols + (ulid(), pid, st["step_key"], ts)); stats["steps_new"] += 1
    held = cat.held_apids()                                              # a fetch step whose record is in the archive is done, whichever household member's id it was archived under
    for sid, lkind, lval in cx.execute("SELECT id, locator_kind, locator_value FROM search_plan WHERE person_id=? AND kind='fetch' AND status='planned'", (pid,)).fetchall():
        if (lkind == "apid" and lval in held) or (lkind and lkind != "apid" and lval and cx.execute("""SELECT 1 FROM artifact WHERE locator_kind=? AND locator_value=?
                UNION SELECT 1 FROM artifact_locator WHERE kind=? AND value=?""", (lkind, lval, lkind, lval)).fetchone()):
            cx.execute("UPDATE search_plan SET status='done' WHERE id=?", (sid,)); stats["steps_done_by_archive"] += 1
    for skey, sid in have_steps.items():                                 # a step the generator no longer produces goes, unless it was run or is done
        if skey not in wanted_keys and not cx.execute("SELECT 1 FROM search_plan sp WHERE sp.id=? AND (sp.status='done' OR EXISTS (SELECT 1 FROM search_log l WHERE l.plan_step_id=sp.id))", (sid,)).fetchone():
            cx.execute("DELETE FROM search_plan WHERE id=?", (sid,)); stats["steps_dropped"] += 1
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "search_plan", pid, dumps(stats)))
    return stats

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who", nargs="?"); ap.add_argument("--tree"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="rule:plan@0.1.0")
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    pids = [r[0] for r in cx.execute("SELECT id FROM person WHERE tree_id=? ORDER BY display_name", (tree_id,))] if a.all else [cat.find_person(a.who or sys.exit("give a person or --all"))]
    total = {}
    for pid in pids:
        cx.execute("BEGIN")
        try: st = plan_person(cx, tree_id, pid, a.by)
        except RegistryOutOfStep as e: cx.rollback(); sys.exit(str(e))
        cx.commit()
        for k, v in st.items():
            if isinstance(v, int): total[k] = total.get(k, 0) + v
        if not a.all: print(cat.person(pid)["name"], dumps(st))
    if a.all: print(len(pids), "persons", dumps(total))

if __name__ == "__main__": main()
