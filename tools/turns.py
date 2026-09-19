#!/usr/bin/env python3
"""The loop run without a hand on it: turn after turn from the queue, pausing for the owner's browser session.

usage: tools/turns.py [--turns N] [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]
       tools/turns.py --resume [--turns N] [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]

docs/RESEARCH-WORKFLOW.md §8: tools/queue.py names the next person at the edge of the confirmed tree and tools/turn.py runs
one person's plan end to end; this runner asks the queue, runs the turn with turn.py's own code (plan, every connector step,
the standing rule's decisions, the tail of collect, attach, reconsider and the plan again), prints the turn's report, and
asks the queue again. A turn that pauses on pages to save in the browser (turn.start leaves its state beside the database)
stops the runner with that list printed and the turn's state kept, as turn.py does; the session at the owner's browser saves
them and calls the runner again with --resume, which resumes the paused turn (turn.resume, its report) and goes on to the
next person. The runner stops when the queue names nobody a turn can act on, when a turn pauses, or after --turns N turns
(the resumed turn counted). A person the queue names again whose last turn held nothing new for them (the count of records
held on their plan and accepted on their personas, before and after) is passed over for the rest of the run with that
reason, so a queue that keeps naming a person with nothing left to bring in does not run them again and again.

Its own state, the turns run with each person's held count before and after, and the people passed over, lives beside the
turn's state file on the same pattern (<db>.loop-state.json; nothing here is catalog data), kept across the pause and
cleared when the run ends. The runner writes nothing of its own: every catalog write is one of the tools' under its own
name (plan_person as rule:plan, run_step.run as agent:run_step, collect, attach, reconsider and decide under --by). A
connector's challenge at a holder is a run logged error, the source did not answer, and the turn goes on (the step stays
runnable and the next turn asks the source again); a challenge in the owner's browser is the session's pause, outside this
runner. At the end a summary in words: the turns run, the people passed over and why, and what is left for the owner (the
queue's own pass-overs, whose open question is the owner's alone, and a paused turn's pages).
"""
import argparse, importlib.util, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, now, resolve_tree
import turn

def queue_module():
    """tools/queue.py loaded by path: importing it by name would shadow the standard library's queue."""
    spec = importlib.util.spec_from_file_location("tree_queue", os.path.join(os.path.dirname(os.path.abspath(__file__)), "queue.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def state_path(db_path): return db_path + ".loop-state.json"

def save_state(db_path, st):
    with open(state_path(db_path), "w", encoding="utf-8") as fh: json.dump(st, fh)

def load_state(db_path):
    try:
        with open(state_path(db_path), encoding="utf-8") as fh: return json.load(fh)
    except FileNotFoundError: return None

def clear_state(db_path):
    try: os.remove(state_path(db_path))
    except FileNotFoundError: pass

def held_count(cx, pid):
    """How many records the person holds: the artifacts found runs on their own steps name, and those their accepted personas
    are on, counted once each. Read-only; what a turn is measured by, before and after."""
    shas = {s for js, in cx.execute("SELECT l.artifacts_json FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE sp.person_id=? AND l.outcome='found' AND l.artifacts_json IS NOT NULL", (pid,)) for s in json.loads(js or "[]")}
    shas |= {s for s, in cx.execute("SELECT pe.artifact_sha256 FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id WHERE pp.person_id=? AND pp.status='accepted'", (pid,))}
    return len(shas)

def name_of(cx, pid): return cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0]

def next_person(cx, tree_id, st):
    """The queue's first person this run can still act on, or None: one passed over earlier in the run is skipped, and one
    named again whose last turn held nothing new is passed over now, with that reason, for the rest of the run."""
    q, _ = queue_module().edge(cx, tree_id)
    passed = {p["person_id"] for p in st["passed"]}
    for e in q:
        if e["id"] in passed: continue
        last = next((t for t in reversed(st["turns"]) if t["person_id"] == e["id"]), None)
        if last and last.get("held_after") is not None and last["held_after"] == last["held_before"]:
            st["passed"].append({"person_id": e["id"], "person": e["name"], "reason": "named again by the queue, and the last turn on them held nothing new"})
            passed.add(e["id"]); continue
        return e
    return None

def summary(cx, tree_id, st, stopped):
    _, owners = queue_module().edge(cx, tree_id)
    out = [f"loop: {len(st['turns'])} turn(s) run; stopped: {stopped}", "", "turns:"]
    for t in st["turns"]:
        held = f"held {t['held_before']} -> {t['held_after']}" if t.get("held_after") is not None else f"held {t['held_before']} before; paused"
        out.append(f"  {t['person']} [{t['person_id'][-6:]}]: {held}" + (", nothing new" if t.get("held_after") == t["held_before"] else ""))
    out += ["", "passed over this run:"] + ([f"  {p['person']} [{p['person_id'][-6:]}]: {p['reason']}" for p in st["passed"]] or ["  nobody"])
    out += ["", "left for the owner:"]
    left = [f"  {e['name']} [{e['id'][-6:]}]: {e['reason']}" for e in owners]
    if turn.load_state(st["db"]) if st.get("db") else False: left.append("  a turn is paused on pages to save in the browser: tools/fetches.py list, then tools/turns.py --resume")
    out += left or ["  nothing: every confirmed person is settled, or a turn can still act on them"]
    return "\n".join(out)

def run(cx, tree_id, slug, by, db, turns=None, resume=False):
    """Turn after turn (turn.start) from the queue's edge, the paused turn resumed first when asked (turn.resume). Returns the
    run's state once it stops."""
    paused = turn.load_state(db); st = load_state(db)
    if resume:
        if not paused or paused["tree_id"] != tree_id: sys.exit("no paused turn on this tree: tools/turns.py")
        if not st or st["tree_id"] != tree_id: st = {"tree_id": tree_id, "tree": slug, "started_at": now(), "turns": [], "passed": []}
        st["db"] = db
        t = next((t for t in reversed(st["turns"]) if t["person_id"] == paused["person_id"] and t.get("held_after") is None), None)
        if not t: t = {"person_id": paused["person_id"], "person": paused["person"], "held_before": held_count(cx, paused["person_id"])}; st["turns"].append(t)
        turn.resume(cx, tree_id, slug, by, db)
        t["held_after"] = held_count(cx, paused["person_id"]); save_state(db, st)
    else:
        if paused and paused["tree_id"] == tree_id: sys.exit(f"a turn on {paused['person']} is paused on pages to save in the browser: save them, then tools/turns.py --resume")
        st = {"tree_id": tree_id, "tree": slug, "started_at": now(), "turns": [], "passed": [], "db": db}
    stopped = None
    while True:
        if turns is not None and len(st["turns"]) >= turns: stopped = f"{turns} turn(s) done (--turns)"; break
        e = next_person(cx, tree_id, st)
        if not e: stopped = "the queue names nobody a turn can act on"; break
        t = {"person_id": e["id"], "person": e["name"], "reason": e["reason"], "held_before": held_count(cx, e["id"])}; st["turns"].append(t); save_state(db, st)
        print(f"\n== turn {len(st['turns'])}: {e['name']} [{e['id'][-6:]}]  {e['reason']}\n")
        turn.start(cx, tree_id, slug, e["id"], by, db)
        if turn.load_state(db):
            save_state(db, st); stopped = "a turn paused on pages to save in the browser; save them, then tools/turns.py --resume"; break
        t["held_after"] = held_count(cx, e["id"]); save_state(db, st)
    print("\n" + summary(cx, tree_id, st, stopped))
    if not turn.load_state(db): clear_state(db)
    return st

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resume", action="store_true"); ap.add_argument("--turns", type=int)
    ap.add_argument("--tree"); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree)
    run(cx, tree_id, slug, a.by, a.db, turns=a.turns, resume=a.resume)

if __name__ == "__main__": main()
