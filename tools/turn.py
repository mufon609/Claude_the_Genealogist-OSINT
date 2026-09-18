#!/usr/bin/env python3
"""One person's plan, run end to end, and resumed after the owner's browser session.

usage: tools/turn.py "<person>" [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]
       tools/turn.py --resume [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]

docs/RESEARCH-WORKFLOW.md §8: a turn is one person's plan run end to end. `tools/plan.py` first (self-recording,
`rule:plan@0.1.0`), then every step a connector can run (`tools/run_step.py`'s own runnable steps narrowed to this
person, self-recording as `agent:run_step`, one commit per step as the runner does). What is left after that is
the person's own fetch list at holders with no connector (`tools/fetches.py list`, narrowed to steps on this
person's plan): printed with the pause line below, the turn's state (which person, which tree) kept beside the
database as `<db>.turn-state.json` (on the pattern of `catalog/.active-tree`; nothing here is catalog data, so
nothing is written to the catalog by pausing), and the process exits for the owner's browser session. A
challenge at a holder pauses the same way (docs/RESEARCH-WORKFLOW.md §4): it does not stop the turn, and passing
it is the owner's own hand.

`--resume` picks up the paused turn: `tools/fetches.py collect` moves what was saved into the inbox and attaches
it by identity, `tools/attach_inbox.py` takes whatever collect's own naming left behind, `tools/conclude.py
reconsider` re-examines the rule's decisions and every card still undecided, and the plan is regenerated for the
person once more. When a turn has nothing to fetch, `--resume` is not needed: the same tail runs in the same
call, right after the connector steps.

The turn writes nothing of its own: every catalog write happens inside `plan_person`, `run_step.run`,
`fetches.collect`, `attach_inbox`, or `reconsider`, each under its own name in `--by` as it always is; the turn
only calls them in order and reports what came back, in words, never a score. What a turn leaves for the owner
are the conflict questions it raised and the cards the rule did not take (docs/RESEARCH-WORKFLOW.md §8).
"""
import argparse, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, resolve_tree
from catalog import Catalog
from plan import plan_person
import run_step
import fetches
from attach import attach_inbox as attach_inbox_files, line
from conclude import reconsider

RUNNER, PLANNER = "agent:run_step", "rule:plan@0.1.0"

def state_path(db_path): return db_path + ".turn-state.json"

def save_state(db_path, tree_id, slug, pid, name, before_ids, held, decided):
    """Kept beside the database, not in the catalog: which person, who existed before the turn started (so a person a
    connector step created before the pause is still reported as created once the turn is resumed), and the held/decided
    lines the connector steps already earned before the pause, so the final report covers the whole turn, not just what
    --resume itself does."""
    with open(state_path(db_path), "w", encoding="utf-8") as fh:
        json.dump({"tree_id": tree_id, "tree": slug, "person_id": pid, "person": name, "started_at": now(),
                   "before_ids": before_ids, "held": held, "decided": decided}, fh)

def load_state(db_path):
    try:
        with open(state_path(db_path), encoding="utf-8") as fh: return json.load(fh)
    except FileNotFoundError: return None

def clear_state(db_path):
    try: os.remove(state_path(db_path))
    except FileNotFoundError: pass

def person_ids(cx, tree_id):
    return {r[0]: r[1] for r in cx.execute("SELECT id, display_name FROM person WHERE tree_id=? AND merged_into IS NULL", (tree_id,))}

def connector_steps(cx, cat, tree_id, pid):
    """The runner's own runnable steps (tools/run_step.py), narrowed to this person's plan: those a connector can take."""
    return [r for r in run_step.runnable(cx, cat, tree_id) if r["person_id"] == pid]

def waiting_for(cx, tree_id, pid):
    """tools/fetches.py's own waiting list, narrowed to the entries that touch this person's plan (a shared census page
    naming relatives is still this person's page)."""
    entries = fetches.waiting(cx, tree_id)
    mine = {sid for sid, in cx.execute("SELECT id FROM search_plan WHERE person_id=?", (pid,))}
    return [e for e in entries if mine & set(e["step_ids"])]

def run_connectors(cx, cat, tree_id, pid):
    """Every step this person's own plan can run at a connector, one commit per step, as tools/run_step.py --all does.
    An earlier step's own accept regenerates the plan in the same request (docs/RESEARCH-WORKFLOW.md §5-7) and can drop
    a later step already queued here, or add one; steps are read fresh before each run rather than as one snapshot, so a
    step gone by the time its turn comes is skipped, never run against a row that no longer exists, and a step the
    regeneration newly opens still gets its turn."""
    out = []; ran = set()
    while True:
        todo = [st for st in connector_steps(cx, cat, tree_id, pid) if st["id"] not in ran]
        if not todo: break
        st = todo[0]; ran.add(st["id"])
        cx.execute("BEGIN")
        try: res = run_step.run(cx, cat, tree_id, st, RUNNER); cx.commit()
        except Exception: cx.rollback(); raise
        out.append({"step": st["id"], "row_key": st["row_key"], "results": res})
    return out

def finish(cx, tree_id, slug, pid, by):
    """The shared tail: fetches.py collect, attach_inbox.py on whatever it leaves, conclude.py reconsider, the plan
    regenerated for the person. Runs whether a turn had nothing to fetch or is resuming after one that did."""
    cx.execute("BEGIN")
    try: names, collect_results = fetches.collect(cx, tree_id, slug, by); cx.commit()
    except Exception: cx.rollback(); raise
    cx.execute("BEGIN")
    try: left_results = attach_inbox_files(cx, tree_id, slug, by); cx.commit()
    except Exception: cx.rollback(); raise
    cx.execute("BEGIN")
    try: recon = reconsider(cx, tree_id, by); cx.commit()
    except Exception: cx.rollback(); raise
    cat = Catalog(cx, tree_id)
    cx.execute("BEGIN")
    try: plan_stats = plan_person(cx, tree_id, pid, PLANNER); cx.commit()
    except Exception: cx.rollback(); raise
    return names, collect_results, left_results, recon, plan_stats

def held_lines(conn_runs, collect_results, left_results):
    """What was fetched and archived this turn, in words: the connector runs that found something, then the pages the
    browser session brought back."""
    out = []
    for run in conn_runs:
        for r in run["results"]:
            if "error" in r: out.append(f"  {run['row_key']}: {r['error']}"); continue
            if r.get("outcome") == "found":
                out.append(f"  {run['row_key']} at {r['connector']}: found, {len(r.get('artifacts') or [])} artifact(s), {len(r.get('extracted') or [])} record(s) read")
            elif r.get("outcome"): out.append(f"  {run['row_key']} at {r['connector']}: {r['outcome']}")
    for r in collect_results + left_results:
        if not r.get("left"): out.append("  " + line(r))
    return out

def decided_lines(conn_runs, collect_results, left_results, recon):
    out = []
    for run in conn_runs:
        for r in run["results"]:
            for e in r.get("extracted") or []:
                if e.get("accepted_by_rule"): out.append(f"  {run['row_key']}: the rule took {e['accepted_by_rule']} of {e['proposals']} proposal(s)")
    for r in collect_results + left_results:
        if r.get("accepted_by_rule"): out.append(f"  {r['file']}: the rule took {len(r['accepted_by_rule'])} proposal(s)" if isinstance(r["accepted_by_rule"], list) else f"  {r['file']}: the rule took {r['accepted_by_rule']} proposal(s)")
    for row in recon:
        if row["kind"] == "card" and row["taken"]: out.append(f"  reconsider: the rule took {row['person']} / {row['persona']}: {row['why']}")
        elif row["kind"] == "decision" and not row["kept"]: out.append(f"  reconsider: withdrew {row['person']} / {row['persona']}: {row['why']}")
        elif row["kind"] == "row": out.append(f"  reconsider: closed a results-page row for {row['person']} ({row['persona']}), the record itself is accepted")
    return out

def left_lines(cx, cat, pid, collect_results, left_results, recon, watch):
    """What the turn leaves for the owner (docs/RESEARCH-WORKFLOW.md §8): this person's own open work, any file the
    browser session brought back that fulfilled no step, and reconsider's own cards named for this turn (this person or
    someone it created). Reconsider examines the whole tree, not one person's turn, so a card naming somebody else is
    counted, not listed: that count was already there, or wasn't, before this turn ran."""
    w = cat.waiting(pid); bl = cat.baseline(pid)
    out = []
    if not bl["complete"]: out.append(f"  {pid_name(cx, pid)}: {len(bl['undecided'])} key fact(s) still undecided: {', '.join(bl['undecided'])}")
    if w["documents"]: out.append(f"  {pid_name(cx, pid)}: {w['documents']} document(s) still waiting for a decision")
    if w["conflicts"]: out.append(f"  {pid_name(cx, pid)}: {w['conflicts']} conflict question(s) open")
    if w["needs_hand"]: out.append(f"  {pid_name(cx, pid)}: {w['needs_hand']} step(s) still need a hand (assisted, not yet run)")
    for r in collect_results + left_results:
        if r.get("left"): out.append("  " + line(r))
    here, elsewhere = 0, 0
    for row in recon:
        if row["kind"] != "card" or row["taken"]: continue
        if row["person"] in watch: out.append(f"  reconsider: a card for {row['person']} / {row['persona']}, the rule does not take it: {row['why']}"); here += 1
        else: elsewhere += 1
    if elsewhere: out.append(f"  {elsewhere} card(s) elsewhere in the tree the rule still does not take, unrelated to this turn (tools/cards.py \"<person>\")")
    return out

def pid_name(cx, pid): return cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0]

def report(cx, tree_id, pid, before_ids, conn_runs, waits, collect_results, left_results, recon, plan_stats, pre_held=(), pre_decided=()):
    cat = Catalog(cx, tree_id)
    after_ids = person_ids(cx, tree_id)
    created = [(i, n) for i, n in after_ids.items() if i not in before_ids]
    out = [f"turn: {pid_name(cx, pid)}", "", "held:"]
    hl = list(pre_held) + held_lines(conn_runs, collect_results, left_results)
    out += hl or ["  nothing new archived"]
    out += ["", "decided:"]
    dl = list(pre_decided) + decided_lines(conn_runs, collect_results, left_results, recon)
    out += dl or ["  nothing for the rule to take"]
    out += ["", "created:"]
    out += [f"  {n} [{i[-6:]}]" for i, n in created] or ["  nobody"]
    out += ["", "left:"]
    watch = {pid_name(cx, pid)} | {n for _, n in created}
    ll = left_lines(cx, cat, pid, collect_results, left_results, recon, watch)
    out += ll or ["  nothing outstanding on this person"]
    if waits: out += ["", f"still to fetch by hand (nothing saved for {len(waits)} page(s) yet): run tools/fetches.py list"]
    out += ["", f"plan: {dumps(plan_stats)}"]
    return "\n".join(out)

def start(cx, tree_id, slug, pid, by, db):
    before = person_ids(cx, tree_id)
    cx.execute("BEGIN")
    try: plan_stats = plan_person(cx, tree_id, pid, PLANNER); cx.commit()
    except Exception: cx.rollback(); raise
    cat = Catalog(cx, tree_id)
    conn_runs = run_connectors(cx, cat, tree_id, pid)
    waits = waiting_for(cx, tree_id, pid)
    if waits:
        held, decided = held_lines(conn_runs, [], []), decided_lines(conn_runs, [], [], [])
        save_state(db, tree_id, slug, pid, pid_name(cx, pid), before, held, decided)
        lines = [f"-- {e['holder']}\n{'lead ' if e['lead'] else 'cited'} {e['url']}  {', '.join(e['people'])}  save as {e['save_as']}" +
                 ("  (an image: tools/save_image.js in its own tab)" if e["how"] == "image" else "") for e in waits]
        print(f"turn: {pid_name(cx, pid)}\n" + "\n".join(lines) + f"\n\n{len(waits)} page(s) to fetch, one tab per page; save these, then run tools/turn.py --resume")
        if held or decided: print("\n(so far this turn -- held:\n" + "\n".join(held or ["  nothing yet"]) + "\ndecided:\n" + "\n".join(decided or ["  nothing yet"]) + ")")
        return
    names, collect_results, left_results, recon, final_stats = finish(cx, tree_id, slug, pid, by)
    print(report(cx, tree_id, pid, before, conn_runs, [], collect_results, left_results, recon, final_stats))

def resume(cx, tree_id, slug, by, db):
    st = load_state(db)
    if not st or st["tree_id"] != tree_id: sys.exit("no paused turn on this tree: tools/turn.py \"<person>\"")
    pid = st["person_id"]; before = st.get("before_ids") or person_ids(cx, tree_id)
    names, collect_results, left_results, recon, final_stats = finish(cx, tree_id, slug, pid, by)
    clear_state(db)
    print(report(cx, tree_id, pid, before, [], [], collect_results, left_results, recon, final_stats, pre_held=st.get("held") or (), pre_decided=st.get("decided") or ()))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who", nargs="?"); ap.add_argument("--resume", action="store_true")
    ap.add_argument("--tree"); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    if bool(a.who) == bool(a.resume): sys.exit("give a person, or --resume, not both")
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.resume: resume(cx, tree_id, slug, a.by, a.db)
    else:
        cat = Catalog(cx, tree_id); pid = cat.find_person(a.who)
        start(cx, tree_id, slug, pid, a.by, a.db)

if __name__ == "__main__": main()
