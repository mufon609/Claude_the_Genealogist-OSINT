#!/usr/bin/env python3
"""The loop run without a hand on it: turn after turn from the queue; a person whose pages wait for the browser waits, the loop does not.

usage: tools/turns.py [--turns N] [--detail] [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]

docs/RESEARCH-WORKFLOW.md §8: tools/queue.py names the next person at the edge of the confirmed tree and tools/turn.py runs
one person's plan end to end; this runner first does what tools/turn.py --resume does (whatever has been saved in the
browser is taken in, each file credited to the people whose steps it reached, and the turns of the people who wait that it
reached are finished, turn.resume), then asks the queue, runs the turn with turn.py's own code (plan, every connector step,
the standing rule's decisions, the tail of collect, attach, places, reconsider and the plan again, the pages its person
waits on), prints the turn's report, and asks the queue again. A turn that leaves pages to save in the browser never stops
the runner: its person waits (turn.set_waiting keeps them beside the database), the queue passes them over while every
step a turn could advance for them is one of those pages, and the runner goes on to the next person; nobody waiting ever
makes it refuse. The runner stops when the queue names nobody a turn can act on, or after --turns N turns (--turns 0
finishes the turns of the people who wait and starts none). It refuses to start on a tree with no home person
(tools/tree.py home), as the queue does. A person the queue names again whose last turn held nothing new for them (the
count of records held on their plan and accepted on their personas no higher after than before: a reconsider that
withdraws an acceptance lowers it) is passed over for the rest of the run with that reason, so a queue that keeps naming a person with nothing left to bring in does not run them again and
again. One person's failure never stops the next person's turn: a run or a part of the tail that fails is named in the
turn's report (tools/turn.py), and a turn that fails anywhere else stops there, what it had not committed rolled back, is
named with its exception, and its person is passed over for the rest of the run with that reason.

The run's own count (the turns run with each person's held count before and after, the people passed over and the files
left in the inbox that a report has already named, each named once per run) lives in the run and ends with it. The runner
writes nothing of its own: every catalog write is one of the tools' under its own name (plan_person as rule:plan,
run_step.run as agent:run_step, collect, attach, reconsider and decide under --by). A connector's challenge at a holder is a
run logged error, the source did not answer, and the turn goes on (the step stays runnable and the next turn asks the
source again); a challenge in the owner's browser is the session's pause, outside this runner. At the end a summary in
words: the turns run, the people who waited whose turns it finished (in the opening resume, or in a turn's tail when a page of
theirs came in while the run went on), the people this run passed over and why, the people
who wait on pages to save in the browser with how many pages, and what is left for the owner, as counts by kind (the people
whose open question is the owner's alone: documents to decide, conflicts open, key facts undecided, family links the file
names and nobody has accepted); --detail names each of those people with the reason, as tools/queue.py --all does, and
each person who waits with their pages.
"""
import argparse, importlib.util, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, now, resolve_tree
from catalog import Catalog
import turn

def queue_module():
    """tools/queue.py loaded by path: importing it by name would shadow the standard library's queue."""
    spec = importlib.util.spec_from_file_location("tree_queue", os.path.join(os.path.dirname(os.path.abspath(__file__)), "queue.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def held_count(cx, pid):
    """How many records the person holds: the artifacts found and unread runs on their own steps name (a record no parser reads is
    held all the same), and those their accepted personas are on, counted once each. Read-only; what a turn is measured by,
    before and after."""
    shas = {s for js, in cx.execute("SELECT l.artifacts_json FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE sp.person_id=? AND l.outcome IN ('found','unread') AND l.artifacts_json IS NOT NULL AND l.superseded_by IS NULL", (pid,)) for s in json.loads(js or "[]")}
    shas |= {s for s, in cx.execute("SELECT pe.artifact_sha256 FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id WHERE pp.person_id=? AND pp.status='accepted'", (pid,))}
    return len(shas)

def name_of(cx, pid): return cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0]

def next_person(cx, tree_id, st, db):
    """The queue's first person this run can still act on, or None: the queue passes over the people who wait on pages
    (turn.waits); one passed over earlier in the run is skipped, and one named again whose last turn held nothing new is
    passed over now, with that reason, for the rest of the run."""
    q, _ = queue_module().edge(cx, tree_id, turn.waits(cx, db, tree_id))
    passed = {p["person_id"] for p in st["passed"]}
    for e in q:
        if e["id"] in passed: continue
        last = next((t for t in reversed(st["turns"]) if t["person_id"] == e["id"]), None)
        if last and last.get("held_after") is not None and last["held_after"] <= last["held_before"]:
            st["passed"].append({"person_id": e["id"], "person": e["name"], "reason": "named again by the queue, and the last turn on them held nothing new"})
            passed.add(e["id"]); continue
        return e
    return None

def owner_counts(cx, tree_id, owners):
    """The people whose open question is the owner's alone (the queue's pass-overs) counted by kind, one line each, a person under
    every kind that holds for them: documents to decide, conflicts open, key facts undecided on a confirmed person, a family
    link the file names and nobody has accepted."""
    cat = Catalog(cx, tree_id); waiting = {e["id"]: cat.waiting(e["id"]) for e in owners}
    docs = [w["documents"] for w in waiting.values() if w["documents"]]; conflicts = [w["conflicts"] for w in waiting.values() if w["conflicts"]]
    facts = [e for e in owners if e["kind"] == "open question" and cat.baseline(e["id"])["undecided"]]; links = [e for e in owners if e["kind"] != "open question"]
    return ([f"documents to decide: {sum(docs)}, on {len(docs)} person(s)"] if docs else []) + ([f"conflicts open: {sum(conflicts)}, on {len(conflicts)} person(s)"] if conflicts else []) + \
           ([f"key facts undecided: {len(facts)} person(s)"] if facts else []) + ([f"family links the file names, not yet accepted: {len(links)} person(s)"] if links else [])

def waiting_lines(cx, tree_id, db, detail):
    """The people who wait on pages to save in the browser: how many, on how many pages; with detail each of them, their
    pages and since when."""
    w = turn.waiting(cx, db, tree_id)
    if not w: return ["  nobody"]
    pages = {e["url"] for x in w.values() for e in x["pages"]}
    out = [f"  {len(w)} person(s) wait on {len(pages)} page(s): tools/fetches.py next names them, and the next run takes what is saved"]
    if detail: out += [f"    {x['person']} [{pid[-6:]}]: {len(x['pages'])} page(s), waiting since {x['since']}" for pid, x in w.items()]
    return out

def summary(cx, tree_id, st, stopped, db, detail=False):
    _, owners = queue_module().edge(cx, tree_id, turn.waits(cx, db, tree_id))
    out = [f"loop: {len(st['turns'])} turn(s) run; stopped: {stopped}", "", "turns:"]
    for t in st["turns"]:
        held = f"held {t['held_before']} -> {t['held_after']}" + (", nothing new" if t["held_after"] <= t["held_before"] else "")
        out.append(f"  {t['person']} [{t['person_id'][-6:]}]: " + (f"failed; {held}" if t.get("failed") else held))
    out += ["", "finished on the pages saved for them:"] + ([f"  {p['person']} [{p['person_id'][-6:]}]" for p in st["finished"]] or ["  nobody"])
    out += ["", "passed over this run:"] + ([f"  {p['person']} [{p['person_id'][-6:]}]: {p['reason']}" for p in st["passed"]] or ["  nobody"])
    out += ["", "waiting on pages to save in the browser:"] + waiting_lines(cx, tree_id, db, detail)
    out += ["", "left for the owner:"]
    left = []
    if detail: left += [f"  {e['name']} [{e['id'][-6:]}]: {e['reason']}" for e in owners]
    elif owners:
        left.append(f"  {len(owners)} person(s) whose open question is the owner's alone (tools/queue.py --all names each with why; --detail here):")
        left += [f"    {x}" for x in owner_counts(cx, tree_id, owners)]
    out += left or ["  nothing: every confirmed person is settled, or a turn can still act on them"]
    return "\n".join(out)

def one_turn(cx, tree_id, slug, by, db, e, t, reported):
    """One person's turn (turn.start). Returns (its tail, None), the tail naming the people who waited whose turns its collect
    finished; or, for a turn that fails outside its runs and its tail's parts, (None, the failure): what it had not committed
    is rolled back, the failure printed and kept on the turn, for the caller to pass them over (turn.start_guarded, as a turn
    run by hand is)."""
    tail, why = turn.start_guarded(cx, tree_id, slug, e["id"], by, db, reported=reported)
    if why: t["failed"] = why
    return tail, why

def finished(cx, st, tail):
    """The people who waited whose turns a tail finished (its credited), added to the run's count once each, in the order met."""
    seen = {p["person_id"] for p in st["finished"]}
    st["finished"] += [{"person_id": pid, "person": name_of(cx, pid)} for pid in (tail or {}).get("credited", {}) if pid not in seen]

def run(cx, tree_id, slug, by, db, turns=None, detail=False):
    """What has been saved for the people who wait taken in first (turn.resume), then turn after turn (turn.start) from the
    queue's edge. Returns the run's count once it stops."""
    queue_module().require_home(cx, tree_id)                   # the loop walks the confirmed tree from the home person: none set, nothing runs
    st = {"tree_id": tree_id, "tree": slug, "started_at": now(), "turns": [], "passed": [], "finished": []}
    reported = set()                                           # the files left in the inbox that a report of this run has named
    finished(cx, st, turn.resume(cx, tree_id, slug, by, db, reported=reported))
    stopped = None
    while True:
        if turns is not None and len(st["turns"]) >= turns: stopped = f"{turns} turn(s) done (--turns)"; break
        e = next_person(cx, tree_id, st, db)
        if not e: stopped = "the queue names nobody a turn can act on"; break
        t = {"person_id": e["id"], "person": e["name"], "reason": e["reason"], "held_before": held_count(cx, e["id"])}; st["turns"].append(t)
        print(f"\n== turn {len(st['turns'])}: {e['name']} [{e['id'][-6:]}]  {e['reason']}\n")
        tail, why = one_turn(cx, tree_id, slug, by, db, e, t, reported)
        finished(cx, st, tail)
        if why: st["passed"].append({"person_id": e["id"], "person": e["name"], "reason": why})
        t["held_after"] = held_count(cx, e["id"])
    st["reported"] = sorted(reported)
    print("\n" + summary(cx, tree_id, st, stopped, db, detail))
    return st

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, help="how many turns to run; 0 finishes the turns of the people who wait and starts none")
    ap.add_argument("--detail", action="store_true", help="the summary also names every person left for the owner, with the reason, and every person who waits")
    ap.add_argument("--tree"); ap.add_argument("--db", default=DB)
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree)
    run(cx, tree_id, slug, a.by, a.db, turns=a.turns, detail=a.detail)

if __name__ == "__main__": main()
