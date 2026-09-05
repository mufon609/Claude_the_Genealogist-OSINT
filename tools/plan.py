#!/usr/bin/env python3
"""Materialize a person's questions and steps into the catalog (research_question, search_plan).

usage: tools/plan.py "<person>" [--tree slug]      tools/plan.py --all [--tree slug]

Questions are fact-level (missing parents, no surname, conflict, ...). A step
belongs to the person and a checklist row: a fetch of a record the tree already
cites (one per citation, with its locator), or a typed search for a missing row.
Footprint records on relatives become fetch steps under the fact-level question
they serve. Idempotent: questions and steps are keyed, so re-running updates what
changed, adds what is new, drops steps no longer generated unless they were run,
and closes questions whose gap has gone (closed_reason 'gap_gone'). A question a
person dismissed or answered stays closed. Nothing here runs a search.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, resolve_tree, ulid
from catalog import Catalog
from checklist import build

FOOTPRINT_HOME = ("missing_parents", "identity_incomplete", "missing_spouse", "unverified_claim")
ANCESTRY = "B02"

def q_key(q):
    """Stable key: kind plus the other person's id when the question is about one, else kind plus detail."""
    if q.get("other_id"): return q["kind"] + ":" + q["other_id"]
    return q["kind"] + ":" + re.sub(r"\s+", " ", (q.get("detail") or "")).strip()[:120]

def fetch_step(row_key, query_type, apid, collection_id, on, expected, rationale, sources, question_key=None):
    return {"step_key": f"fetch:{apid}", "row_key": row_key, "question_key": question_key, "kind": "fetch", "query_type": query_type, "query_json": "{}",
            "locator_source_id": ANCESTRY, "locator_kind": "apid", "locator_value": apid, "collection_id": collection_id, "on_json": dumps(on),
            "sources_json": dumps(sources), "mode": "fetch", "expected": expected, "rationale": rationale}

def plan_person(cx, tree_id, pid, by):
    cat = Catalog(cx, tree_id); r = build(cat, pid); ts = now()
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
                    fetches.append(fetch_step(rk, s["type"], c["apid"], c["collection_id"], c["on"], row["settles"], f"{where}; fetch the record", row["sources"]))
            else:
                searches.append({"step_key": f"search:{rk}", "row_key": rk, "question_key": None, "kind": "search", "query_type": s["type"], "query_json": dumps(s["fields"]),
                                 "locator_source_id": None, "locator_kind": None, "locator_value": None, "collection_id": None, "on_json": None,
                                 "sources_json": dumps(s["sources"]), "mode": s["mode"], "expected": s["expect"], "rationale": f"{row['record']} is missing for this person"})
    home = next((k for k in wanted if wanted[k][0] in FOOTPRINT_HOME), None)
    have = {st["locator_value"] for st in fetches}
    for rec in r["footprint"]["records"][:12]:
        if not rec.get("apid") or rec["apid"] in have: continue
        fetches.append(fetch_step(f"footprint:{rec['apid']}", "footprint_record", rec["apid"], rec.get("collection_id"), rec["on"], rec["expect"],
                                  "already on " + ", ".join(f"{n} ({rel})" for n, rel in rec["on"]), [ANCESTRY], home))
    stats = {"questions_new": 0, "questions_kept": 0, "questions_closed": 0, "questions_left_closed": 0, "steps_new": 0, "steps_kept": 0, "steps_dropped": 0}
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
    for key, qid in existing.items():
        if key not in wanted:
            cx.execute("UPDATE research_question SET status='closed', closed_reason='gap_gone', closed_at=? WHERE id=?", (ts, qid)); stats["questions_closed"] += 1
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
    for skey, sid in have_steps.items():                                 # a step the generator no longer produces goes, unless it was run
        if skey not in wanted_keys and not cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=?", (sid,)).fetchone():
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
        cx.execute("BEGIN"); st = plan_person(cx, tree_id, pid, a.by); cx.commit()
        for k, v in st.items(): total[k] = total.get(k, 0) + v
        if not a.all: print(cat.person(pid)["name"], dumps(st))
    if a.all: print(len(pids), "persons", dumps(total))

if __name__ == "__main__": main()
