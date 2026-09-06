#!/usr/bin/env python3
"""Record the outcome of a search step, including nothing found; dismiss a question.

usage: tools/log_search.py --step <search_plan id> --outcome found|none|blocked|error [--artifact sha256 ...] [--note ...] [--query '{...}']
       tools/log_search.py --question <research_question id> --source <registry id> --outcome ... --query '{...}'   (a search not on the plan)
       tools/log_search.py --dismiss <research_question id> [--note ...]
       tools/log_search.py --list "<person>"

The query recorded is exactly what was run: the step's fields after the person's
include/revise unless --query overrides them. A 'found' outcome marks the step done;
'none' leaves it planned so it can be retried with different fields, and the log
shows it was tried. A dismissed question stays closed when the plan is regenerated.
"""
import argparse, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, resolve_tree, ulid
from catalog import Catalog

def rendered_query(query_json, revisions_json):
    """The step's fields ({value, basis} each) after the person's include/revise: an excluded field is dropped,
    a revised value replaces the tree's and is a claim of the searcher that remembers what it revised."""
    fields = json.loads(query_json or "{}"); rev = json.loads(revisions_json or "{}")
    out = {}
    for k, v in fields.items():
        f = v if isinstance(v, dict) and "basis" in v else {"value": v, "basis": "claim"}
        r = rev.get(k) or {}
        if r.get("include") is False: continue
        if r.get("value") not in (None, ""): f = {"value": r["value"], "basis": "claim", "revised_from": f["value"]}
        out[k] = f
    return out

def log(cx, tree_id, by, step_id=None, question_id=None, source_id=None, outcome="none", artifacts=None, note=None, query=None):
    ts = now()
    if step_id:
        st = cx.execute("SELECT id, question_id, query_json, sources_json, revisions_json, locator_source_id FROM search_plan WHERE id=?", (step_id,)).fetchone()
        if not st: raise SystemExit(f"no step {step_id}")
        question_id = st[1]; query = query or rendered_query(st[2], st[4]); source_id = source_id or st[5] or (json.loads(st[3]) or [None])[0]
    if question_id and not cx.execute("SELECT 1 FROM research_question WHERE id=? AND tree_id=?", (question_id, tree_id)).fetchone(): raise SystemExit("question not in this tree")
    lid = ulid()
    cx.execute("""INSERT INTO search_log (id,tree_id,plan_step_id,question_id,executed_at,executed_by,source_id,query_json,outcome,artifacts_json,notes)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (lid, tree_id, step_id, question_id, ts, by, source_id, dumps(query or {}), outcome, dumps(artifacts) if artifacts else None, note))
    if step_id and outcome == "found": cx.execute("UPDATE search_plan SET status='done' WHERE id=?", (step_id,))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "insert", "search_log", lid, dumps({"step": step_id, "outcome": outcome, "artifacts": artifacts or []})))
    return lid

def dismiss(cx, tree_id, by, question_id, note=None):
    """Close a question as dismissed by a person; the planner never reopens it."""
    ts = now()
    if not cx.execute("SELECT 1 FROM research_question WHERE id=? AND tree_id=? AND status='open'", (question_id, tree_id)).fetchone(): raise SystemExit("no open question with that id in this tree")
    cx.execute("UPDATE research_question SET status='closed', closed_reason='dismissed', closed_at=? WHERE id=?", (ts, question_id))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "research_question", question_id, dumps({"status": "closed", "closed_reason": "dismissed", "note": note or None})))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--step"); ap.add_argument("--question"); ap.add_argument("--source"); ap.add_argument("--outcome", choices=["found", "none", "blocked", "error"])
    ap.add_argument("--artifact", action="append"); ap.add_argument("--note"); ap.add_argument("--query"); ap.add_argument("--list"); ap.add_argument("--dismiss"); ap.add_argument("--tree")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); tree_id, slug = resolve_tree(cx, a.tree)
    if a.list:
        cat = Catalog(cx, tree_id); pid = cat.find_person(a.list)
        for row in cx.execute("""SELECT sp.id, sp.kind, sp.mode, sp.status, sp.row_key, sp.locator_value, sp.rationale,
                                        (SELECT GROUP_CONCAT(l.outcome || '@' || substr(l.executed_at,1,10), ' ') FROM search_log l WHERE l.plan_step_id=sp.id)
                                 FROM search_plan sp WHERE sp.person_id=? ORDER BY sp.seq""", (pid,)):
            print(f"{row[0]}  {row[1]:6} {row[2]:17} {row[3]:8} {row[4][:34]:34} {(row[5] or '')[:20]:20} {row[7] or ''}  -- {row[6][:50]}")
        return
    if a.dismiss:
        cx.execute("BEGIN"); dismiss(cx, tree_id, a.by, a.dismiss, a.note); cx.commit(); print("dismissed", a.dismiss); return
    if not a.outcome: sys.exit("--outcome required")
    cx.execute("BEGIN"); lid = log(cx, tree_id, a.by, a.step, a.question, a.source, a.outcome, a.artifact, a.note, json.loads(a.query) if a.query else None); cx.commit()
    print("logged", lid, a.outcome)

if __name__ == "__main__": main()
