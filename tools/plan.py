#!/usr/bin/env python3
"""Materialize a person's questions and search steps into the catalog (research_question, search_plan).

usage: tools/plan.py "<person>" [--tree slug]      tools/plan.py --all [--tree slug]

Idempotent: questions and steps are keyed, so re-running updates what changed,
adds what is new, drops steps no longer generated unless they were run, and
closes questions whose gap has gone (closed_reason 'gap_gone'). A question a
person dismissed or answered stays closed. Steps come
from tools/checklist.py (Group A and B gaps, cited records to fetch) and
tools/footprint.py (Layer 0 records on relatives). Nothing here runs a search.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, resolve_tree, ulid
from catalog import Catalog
from checklist import build

LAYER = {"footprint_record": 0, "footprint_collection": 1, "subject_record": 2, "household": 3, "couple": 2, "name": 4, "surname_locality": 5, "obituary": 2, "probate": 2}
FOOTPRINT_HOME = ("missing_parents", "identity_incomplete", "missing_spouse", "unverified_claim")

def q_key(q):
    """Stable key: kind plus the other person's id when the question is about one, else kind plus detail."""
    if q.get("other_id"): return q["kind"] + ":" + q["other_id"]
    return q["kind"] + ":" + re.sub(r"\s+", " ", (q.get("detail") or "")).strip()[:120]

def plan_person(cx, tree_id, pid, by):
    cat = Catalog(cx, tree_id); r = build(cat, pid); ts = now()
    wanted = {}                                       # q_key -> (kind, detail_json)
    for q in r["questions"]: wanted[q_key(q)] = (q["kind"], dumps(q))
    steps_by_q = {}                                   # q_key -> [step dicts]
    for grp in ("A", "B"):
        for row in r["checklist"][grp]:
            if row["status"] not in ("missing", "cited") or not row.get("search"): continue
            key = f"missing_record:{row['record']}:{row.get('instance') or ''}"
            wanted[key] = ("missing_record", dumps({"record": row["record"], "instance": row.get("instance"), "group": grp, "status": row["status"], "via": row.get("via"), "settles": row["settles"]}))
            s = row["search"]
            steps_by_q.setdefault(key, []).append({"step_key": f"{s['type']}:{','.join(s['sources'])}:{row.get('instance') or ''}",
                "layer": 0 if row["status"] == "cited" else LAYER.get(s["type"], 2), "query_type": s["type"], "query_json": dumps(s["fields"]),
                "sources_json": dumps(s["sources"]), "mode_json": dumps(s["mode"]), "expected": s["expect"],
                "rationale": (f"cited on {row['via']}; fetch the record" if row.get("via") else "cited; fetch the record") if row["status"] == "cited" else f"{row['record']} is missing for this person"})
    home = next((k for k in wanted if wanted[k][0] in FOOTPRINT_HOME), None)
    if home:
        for rec in r["footprint"]["records"][:12]:
            steps_by_q.setdefault(home, []).append({"step_key": f"footprint_record:{rec['key']}", "layer": 0, "query_type": "footprint_record",
                "query_json": dumps({"record": rec["key"], "apid": rec.get("apid"), "collection": rec["collection"], "on": rec["on"]}),
                "sources_json": dumps(["B02"] if rec.get("apid") else []), "mode_json": dumps({"fetch": ["B02"]} if rec.get("apid") else {"held": []}),
                "expected": rec["expect"], "rationale": "already on " + ", ".join(f"{n} ({rel})" for n, rel in rec["on"])})
    stats = {"questions_new": 0, "questions_kept": 0, "questions_closed": 0, "questions_left_closed": 0, "steps_new": 0, "steps_kept": 0, "steps_dropped": 0}
    existing = {row[1]: row[0] for row in cx.execute("SELECT id, q_key FROM research_question WHERE subject_person_id=? AND status='open'", (pid,))}
    for key, (kind, detail) in wanted.items():
        if key in existing: qid = existing[key]; cx.execute("UPDATE research_question SET detail_json=? WHERE id=?", (detail, qid)); stats["questions_kept"] += 1
        else:
            closed = cx.execute("SELECT id, closed_reason FROM research_question WHERE subject_person_id=? AND q_key=?", (pid, key)).fetchone()
            if closed and closed[1] != "gap_gone": stats["questions_left_closed"] += 1; continue      # a person dismissed or answered it
            if closed: qid = closed[0]; cx.execute("UPDATE research_question SET status='open', closed_reason=NULL, closed_at=NULL, detail_json=? WHERE id=?", (detail, qid))
            else: qid = ulid(); cx.execute("INSERT INTO research_question (id,tree_id,subject_person_id,kind,q_key,detail_json,status,created_at) VALUES (?,?,?,?,?,?,'open',?)", (qid, tree_id, pid, kind, key, detail, ts))
            stats["questions_new"] += 1
        have = {row[1]: row[0] for row in cx.execute("SELECT id, step_key FROM search_plan WHERE question_id=?", (qid,))}
        seen = {}
        for seq, st in enumerate(steps_by_q.get(key, []), 1):
            n = seen[st["step_key"]] = seen.get(st["step_key"], 0) + 1      # two identical steps under one question (e.g. two spouses of the same name)
            if n > 1: st["step_key"] += f":{n}"
            if st["step_key"] in have:
                cx.execute("UPDATE search_plan SET seq=?, query_json=?, sources_json=?, mode_json=?, expected=?, rationale=? WHERE id=?",
                           (seq, st["query_json"], st["sources_json"], st["mode_json"], st["expected"], st["rationale"], have[st["step_key"]])); stats["steps_kept"] += 1
            else:
                cx.execute("""INSERT INTO search_plan (id,question_id,seq,layer,step_key,query_type,query_json,sources_json,mode_json,expected,status,rationale,created_at)
                              VALUES (?,?,?,?,?,?,?,?,?,?,'planned',?,?)""", (ulid(), qid, seq, st["layer"], st["step_key"], st["query_type"], st["query_json"], st["sources_json"], st["mode_json"], st["expected"], st["rationale"], ts))
                stats["steps_new"] += 1
        wanted_keys = {st["step_key"] for st in steps_by_q.get(key, [])}
        for skey, sid in have.items():                                   # a step the generator no longer produces goes, unless it was run
            if skey not in wanted_keys and not cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=?", (sid,)).fetchone():
                cx.execute("DELETE FROM search_plan WHERE id=?", (sid,)); stats["steps_dropped"] += 1
    for key, qid in existing.items():
        if key not in wanted:
            cx.execute("UPDATE research_question SET status='closed', closed_reason='gap_gone', closed_at=? WHERE id=?", (ts, qid)); stats["questions_closed"] += 1
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "research_question", pid, dumps(stats)))
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
