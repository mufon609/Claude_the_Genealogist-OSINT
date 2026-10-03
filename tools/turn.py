#!/usr/bin/env python3
"""One person's plan, run end to end, and resumed after the owner's browser session.

usage: tools/turn.py "<person>" [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]
       tools/turn.py --resume [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]

docs/RESEARCH-WORKFLOW.md §8: a turn is one person's plan run end to end. `tools/plan.py` first (self-recording,
`rule:plan@0.1.0`), then every step a connector can run that has no run since the plan last wrote its fields
(`tools/run_step.py`'s own runnable steps narrowed to this person, self-recording as `agent:run_step`, one commit per
step as the runner does). What is left after that is the person's own fetch list at holders with no connector
(`tools/fetches.py list`, narrowed to steps on this person's plan that carry a link to open): printed with the pause
line below, the turn's state (which person, which tree) kept beside the
database as `<db>.turn-state.json` (on the pattern of `catalog/.active-tree`; nothing here is catalog data, so
nothing is written to the catalog by pausing), and the process exits for the owner's browser session. A
challenge at a holder pauses the same way (docs/RESEARCH-WORKFLOW.md §4): it does not stop the turn, and passing
it is the owner's own hand.

`--resume` picks up the paused turn: `tools/fetches.py collect` moves what was saved into the inbox and attaches
it by identity, `tools/attach_inbox.py` takes whatever collect's own naming left behind, the place resolver
(`tools/resolve_places.py`) reads the place strings the turn's new records brought and the strings behind this person's own
events, through its cache and the public endpoint's rate (a string it accepts is placed, one it cannot settle is a card on
the person's fact row, and the events whose strings are all resolved take their place before the rule goes over the
conflicts), `tools/conclude.py reconsider` re-examines the rule's decisions and every card still undecided, and the plan is
regenerated for the person once more. When a turn has nothing to fetch, `--resume` is not needed: the same tail runs in the
same call, right after the connector steps.

The turn writes nothing of its own: every catalog write happens inside `plan_person`, `run_step.run`,
`fetches.collect`, `attach_inbox`, `resolve_places.resolve_strings` or `reconsider`, each under its own name in `--by` as it always is; the turn
only calls them in order and reports what came back, in words, never a score. What a turn leaves for the owner
are the conflict questions it raised and the cards the rule did not take (docs/RESEARCH-WORKFLOW.md §8), and its
report names every source that did not answer once, with what it was asked and what it said: a connector step (a run
logged error) stays runnable, and a place string the geocoder did not answer stays unresolved, so the next turn asks that
source again. A file left in the inbox that fulfils no step is
named once per run (the runner passes the files already named, tools/turns.py), not in every turn's report.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, resolve_tree
from catalog import Catalog
from plan import plan_person
import run_step
import fetches
from attach import attach_inbox as attach_inbox_files, line
from conclude import reconsider
from resolve_places import resolve_strings

RUNNER, PLANNER = "agent:run_step", "rule:plan@0.1.0"

def state_path(db_path): return db_path + ".turn-state.json"

def save_state(db_path, tree_id, slug, pid, name, before_ids, held, decided, unanswered=(), since=None):
    """Kept beside the database, not in the catalog: which person, who existed before the turn started (so a person a
    connector step created before the pause is still reported as created once the turn is resumed), the held/decided
    lines the connector steps already earned before the pause and the sources that did not answer, and when the turn began
    (`since`, what the records it brought are told by), so the final report covers the whole turn, not just what --resume
    itself does."""
    with open(state_path(db_path), "w", encoding="utf-8") as fh:
        json.dump({"tree_id": tree_id, "tree": slug, "person_id": pid, "person": name, "started_at": now(), "since": since,
                   "before_ids": before_ids, "held": held, "decided": decided, "unanswered": list(unanswered)}, fh)

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
    """The pages the turn pauses on: tools/fetches.py's own openable list (a link to open, steps with no run since the plan
    last wrote their fields), narrowed to the entries where one of this person's own steps is still unrun (a shared census
    page naming relatives is still this person's page). An entry with no link, or already saved or logged on this person's
    step with unchanged fields, is not one the turn pauses on, whatever other people's steps on the same page still wait."""
    entries = fetches.openable(cx, tree_id)
    mine = {sid for sid, in cx.execute("SELECT id FROM search_plan WHERE person_id=?", (pid,))}
    return [e for e in entries if mine & set(e["open_step_ids"])]

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

def new_place_strings(cx, tree_id, pid, since):
    """The place strings no resolver has read yet that this turn should: those the persons of a record archived since the turn
    began carry (not the tree's own imported file: it is no record the turn brought), and those behind this person's own events
    (their non-rejected assertions, a marriage included), as (place string id, words) by the words."""
    return cx.execute("""SELECT DISTINCT ps.id, ps.raw FROM place_string ps JOIN persona_fact pf ON pf.place_string_id=ps.id JOIN persona pe ON pe.id=pf.persona_id
        WHERE ps.status='undecided' AND ps.place_id IS NULL AND ps.resolver IS NULL
          AND (pe.artifact_sha256 IN (SELECT sha256 FROM artifact WHERE created_at>=? AND sha256 NOT IN (SELECT artifact_sha256 FROM tree_import))
               OR pf.id IN (SELECT a.persona_fact_id FROM assertion a JOIN event_participant ep ON a.subject_kind='event' AND a.subject_id=ep.event_id
                            WHERE a.tree_id=? AND a.status<>'rejected' AND (ep.person_id=? OR ep.family_id IN (SELECT family_id FROM family_member WHERE person_id=? AND role='partner'))))
        ORDER BY ps.raw""", (since or "9999", tree_id, pid, pid)).fetchall()

def resolve_places(cx, tree_id, pid, since, by):
    """The place resolver on the strings new_place_strings names, in one transaction: what it accepted, rejected as no place and
    left a card, and the geocoder's silence if it did not answer (the strings it left stay unresolved, asked again by the next
    turn). None when there is nothing to read."""
    rows = new_place_strings(cx, tree_id, pid, since)
    if not rows: return None
    cx.execute("BEGIN")
    try: stats, report, unanswered = resolve_strings(cx, tree_id, by, rows); cx.commit()
    except Exception: cx.rollback(); raise
    return {"strings": len(rows), "accepted": stats["accepted"], "rejected": stats["rejected"], "cards": stats["undecided"] + stats["no_candidates"], "unanswered": unanswered}

def places_decided_lines(places):
    """What the resolver settled for the turn, in words."""
    if not places or not (places["accepted"] or places["rejected"]): return []
    return [f"  places: {places['accepted']} of {places['strings']} new place string(s) resolved by the geocoder's answer" + (f", {places['rejected']} set aside as no place" if places["rejected"] else "")]

def places_left_lines(cx, places):
    """What the resolver leaves: the cards it wrote for the owner (on the person's fact rows), and the geocoder that did not answer,
    named once with how many strings it left."""
    out = []
    if not places: return out
    if places["cards"]: out.append(f"  places: {places['cards']} place string(s) the resolver could not settle, a card on the fact row for the owner")
    if places["unanswered"]:
        n = (cx.execute("SELECT name FROM source WHERE id='N06'").fetchone() or ["OpenStreetMap Nominatim"])[0]
        k = len(places["unanswered"]["strings"])
        out.append(f"  {n} (N06) did not answer ({places['unanswered']['said'][:200]}) on {k} place string{'s' if k != 1 else ''}; {'they stay' if k != 1 else 'it stays'} unresolved, the next turn asks it again")
    return out

def finish(cx, tree_id, slug, pid, by, since=None):
    """The shared tail: fetches.py collect, attach_inbox.py on whatever it leaves, the place resolver on the new place strings
    (before the rule goes over the conflicts, so an event the answers place is compared as placed), conclude.py reconsider, the
    plan regenerated for the person. Runs whether a turn had nothing to fetch or is resuming after one that did."""
    cx.execute("BEGIN")
    try: names, collect_results = fetches.collect(cx, tree_id, slug, by); cx.commit()
    except Exception: cx.rollback(); raise
    cx.execute("BEGIN")
    try: left_results = attach_inbox_files(cx, tree_id, slug, by); cx.commit()
    except Exception: cx.rollback(); raise
    places = resolve_places(cx, tree_id, pid, since, by)
    cx.execute("BEGIN")
    try: recon = reconsider(cx, tree_id, by); cx.commit()
    except Exception: cx.rollback(); raise
    cat = Catalog(cx, tree_id)
    cx.execute("BEGIN")
    try: plan_stats = plan_person(cx, tree_id, pid, PLANNER); cx.commit()
    except Exception: cx.rollback(); raise
    return names, collect_results, left_results, recon, plan_stats, places

def held_lines(conn_runs, collect_results, left_results):
    """What was fetched and archived this turn, in words: the connector runs that found something or found nothing, then the
    pages the browser session brought back. A run that got no answer is told once, by unanswered_lines."""
    out = []
    for run in conn_runs:
        for r in run["results"]:
            if "error" in r: out.append(f"  {run['row_key']}: {r['error']}"); continue
            if r.get("outcome") == "found":
                out.append(f"  {run['row_key']} at {r['connector']}: found, {len(r.get('artifacts') or [])} artifact(s), {len(r.get('extracted') or [])} record(s) read")
            elif r.get("outcome") and r["outcome"] != "error": out.append(f"  {run['row_key']} at {r['connector']}: {r['outcome']}")
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

def unanswered_lines(cx, conn_runs):
    """The connector runs logged error this turn, one line for each source that did not answer: the registry's name of the
    runs' own source, the rows of the steps it was asked on and what it said first. Such a run does not count as a run on the
    step's fields (log_search.ran_unchanged), so the step stays runnable and the next turn asks the source again."""
    by = {}
    for run in conn_runs:
        for r in run["results"]:
            if r.get("outcome") != "error" or not r.get("log"): continue
            row = cx.execute("SELECT s.id, s.name FROM search_log l LEFT JOIN source s ON s.id=l.source_id WHERE l.id=?", (r["log"],)).fetchone()
            name = f"{row[1]} ({row[0]})" if row and row[0] else r.get("connector") or "the source"
            e = by.setdefault(name, {"rows": [], "said": []})
            if run["row_key"] not in e["rows"]: e["rows"].append(run["row_key"])
            e["said"] += [m for m in (r.get("errors") or []) if m not in e["said"]]
    out = []
    for name, e in by.items():
        said = (e["said"][0] if e["said"] else "no response")[:200] + (f"; and {len(e['said']) - 1} more" if len(e["said"]) > 1 else "")
        out.append(f"  {name} did not answer ({said}) on {', '.join(e['rows'])}; the step{'s stay' if len(e['rows']) > 1 else ' stays'} runnable, the next turn asks it again")
    return out

def left_lines(cx, cat, pid, collect_results, left_results, recon, watch, reported):
    """What the turn leaves for the owner (docs/RESEARCH-WORKFLOW.md §8): this person's own open work, any file left in the
    inbox that fulfilled no step (named once per run: `reported` holds the files an earlier report of the run already named),
    and reconsider's own cards named for this turn (this person or someone it created). Reconsider examines the whole tree, not one person's turn, so a card naming somebody else is
    counted, not listed: that count was already there, or wasn't, before this turn ran."""
    w = cat.waiting(pid); bl = cat.baseline(pid)
    out = []
    if not bl["complete"]: out.append(f"  {pid_name(cx, pid)}: {len(bl['undecided'])} key fact(s) still undecided: {', '.join(bl['undecided'])}")
    if w["documents"]: out.append(f"  {pid_name(cx, pid)}: {w['documents']} document(s) still waiting for a decision")
    if w["conflicts"]: out.append(f"  {pid_name(cx, pid)}: {w['conflicts']} conflict question(s) open")
    if w["needs_hand"]: out.append(f"  {pid_name(cx, pid)}: {w['needs_hand']} planned step(s) only a hand can take: a page to save in the browser, an assisted search, a film browsed by hand")
    for r in collect_results + left_results:
        if r.get("left") and r["file"] not in reported: out.append("  " + line(r)); reported.add(r["file"])
    here, elsewhere = 0, 0
    for row in recon:
        if row["kind"] != "card" or row["taken"]: continue
        if row["person"] in watch: out.append(f"  reconsider: a card for {row['person']} / {row['persona']}, the rule does not take it: {row['why']}"); here += 1
        else: elsewhere += 1
    if elsewhere: out.append(f"  {elsewhere} card(s) elsewhere in the tree the rule still does not take, unrelated to this turn (tools/cards.py \"<person>\")")
    return out

def pid_name(cx, pid): return cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0]

def report(cx, tree_id, pid, before_ids, conn_runs, waits, collect_results, left_results, recon, plan_stats, pre_held=(), pre_decided=(), pre_unanswered=(), reported=None, places=None):
    reported = set() if reported is None else reported
    cat = Catalog(cx, tree_id)
    after_ids = person_ids(cx, tree_id)
    created = [(i, n) for i, n in after_ids.items() if i not in before_ids]
    out = [f"turn: {pid_name(cx, pid)}", "", "held:"]
    hl = list(pre_held) + held_lines(conn_runs, collect_results, left_results)
    out += hl or ["  nothing new archived"]
    out += ["", "decided:"]
    dl = list(pre_decided) + decided_lines(conn_runs, collect_results, left_results, recon) + places_decided_lines(places)
    out += dl or ["  nothing for the rule to take"]
    out += ["", "created:"]
    out += [f"  {n} [{i[-6:]}]" for i, n in created] or ["  nobody"]
    out += ["", "left:"]
    watch = {pid_name(cx, pid)} | {n for _, n in created}
    ll = left_lines(cx, cat, pid, collect_results, left_results, recon, watch, reported) + list(pre_unanswered) + unanswered_lines(cx, conn_runs) + places_left_lines(cx, places)
    out += ll or ["  nothing outstanding on this person"]
    if waits: out += ["", f"still to fetch by hand (nothing saved for {len(waits)} page(s) yet): run tools/fetches.py list"]
    out += ["", f"plan: {dumps(plan_stats)}"]
    return "\n".join(out)

def start(cx, tree_id, slug, pid, by, db, reported=None):
    before = person_ids(cx, tree_id); since = now()
    cx.execute("BEGIN")
    try: plan_stats = plan_person(cx, tree_id, pid, PLANNER); cx.commit()
    except Exception: cx.rollback(); raise
    cat = Catalog(cx, tree_id)
    conn_runs = run_connectors(cx, cat, tree_id, pid)
    waits = waiting_for(cx, tree_id, pid)
    if waits:
        held, decided, unanswered = held_lines(conn_runs, [], []), decided_lines(conn_runs, [], [], []), unanswered_lines(cx, conn_runs)
        save_state(db, tree_id, slug, pid, pid_name(cx, pid), before, held, decided, unanswered, since)
        print(f"turn: {pid_name(cx, pid)}\n" + "\n".join(fetches.page_line(e) for e in waits) + f"\n\n{len(waits)} page(s) to fetch, one tab per page; save these, then run tools/turn.py --resume")
        if held or decided: print("\n(so far this turn -- held:\n" + "\n".join(held or ["  nothing yet"]) + "\ndecided:\n" + "\n".join(decided or ["  nothing yet"]) + ")")
        if unanswered: print("\nnot answered:\n" + "\n".join(unanswered))
        return
    names, collect_results, left_results, recon, final_stats, places = finish(cx, tree_id, slug, pid, by, since)
    print(report(cx, tree_id, pid, before, conn_runs, [], collect_results, left_results, recon, final_stats, reported=reported, places=places))

def resume(cx, tree_id, slug, by, db, reported=None):
    st = load_state(db)
    if not st or st["tree_id"] != tree_id: sys.exit("no paused turn on this tree: tools/turn.py \"<person>\"")
    pid = st["person_id"]; before = st.get("before_ids") or person_ids(cx, tree_id)
    names, collect_results, left_results, recon, final_stats, places = finish(cx, tree_id, slug, pid, by, st.get("since"))
    clear_state(db)
    print(report(cx, tree_id, pid, before, [], [], collect_results, left_results, recon, final_stats, pre_held=st.get("held") or (), pre_decided=st.get("decided") or (),
                 pre_unanswered=st.get("unanswered") or (), reported=reported, places=places))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who", nargs="?"); ap.add_argument("--resume", action="store_true")
    ap.add_argument("--tree"); ap.add_argument("--db", default=DB)
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    if bool(a.who) == bool(a.resume): sys.exit("give a person, or --resume, not both")
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.resume: resume(cx, tree_id, slug, a.by, a.db)
    else:
        cat = Catalog(cx, tree_id); pid = cat.find_person(a.who)
        start(cx, tree_id, slug, pid, a.by, a.db)

if __name__ == "__main__": main()
