#!/usr/bin/env python3
"""One person's plan, run end to end; the people who wait on pages to save in the browser, and their turns finished.

usage: tools/turn.py "<person>" [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]
       tools/turn.py --resume [--tree slug] [--db catalog/tree.db] [--by agent:<you> for user:<you>]

docs/RESEARCH-WORKFLOW.md §8: a turn is one person's plan run end to end. `tools/plan.py` first (self-recording,
`rule:plan@0.1.0`), then every step a connector can run that has no run since the plan last wrote its fields
(`tools/run_step.py`'s own runnable steps narrowed to this person, self-recording as `agent:run_step`, one commit per
step as the runner does). A run that fails is an error run and the turn goes on: run_step.run logs the connector that
cannot build its requests, or the record whose reading or matching raises, as an error run with the exception, its row
kept and the step left runnable. Then the tail in the same call (finish): `tools/fetches.py collect` moves what was saved
in the data root's downloads/ folder into the inbox and attaches it by identity, `tools/attach_inbox.py` takes whatever
else the inbox holds, one file per transaction both (a file that fails is rolled back alone, stays where it was, and is
named with the exception in the report), the place resolver (`tools/resolve_places.py`) reads the place strings the
turn's new records brought and the strings behind this person's own events, through its cache and the public endpoint's
rate (a string it accepts is placed, one it cannot settle is a card on the person's fact row, and the events whose
strings are all resolved take their place before the rule goes over the conflicts), `tools/conclude.py reconsider`
re-examines the rule's decisions and every card still undecided, and the plan is regenerated for the person once more.
The opening plan and each part of the tail run in a transaction of their own (guarded): one that fails is rolled back
alone and named in the report with its exception, and the turn goes on to its next part. A turn that fails anywhere
else stops there, what it had not committed rolled back, and names its exception (start_guarded: the runner's turn and a
turn run by hand alike; the hand-run process then exits with a failure status).

Last, the person's own fetch list at holders with no connector (`tools/fetches.py list`, narrowed to steps on this
person's plan that carry a link to open) is printed under the report, and the person waits on those pages: their entry
is kept beside the database as `<db>.turn-state.json` (on the pattern of `catalog/.active-tree`; nothing here is catalog
data), one entry for each person who waits, the file gone when nobody does. Nothing about a person who waits stops
anyone else's turn. The file is written whole (treelib.write_json_whole): a stop in the middle of the write leaves the
state as it was. A collect, in any turn's tail or in `--resume`, credits each file to the people whose steps it
reached, and finishes the turns of the people who wait that it reached: the resolver reads the strings behind their own
events beside the rest, the plan is regenerated for them, and their own report follows, with the files credited to them
and the pages they still wait on. A person whose page came in some other way (attached by hand with
`tools/attach_inbox.py`, logged on the person screen) has a run on that step since they began to wait: the next turn or
resume finishes their turn the same way, their report naming what those runs hold. `--resume` is that alone, with no turn of its own; the resolver, `reconsider` and the
plans run only when a file came in. A state in the one-turn shape (a `person_id` at its top: one turn paused on its
pages) is read as that person waiting on the pages the fetch list holds for them now, and written back in the shape
above.

The turn writes nothing of its own: every catalog write happens inside `plan_person`, `run_step.run`,
`fetches.collect`, `attach_inbox`, `resolve_places.resolve_strings` or `reconsider`, each under its own name in `--by` as it always is; the turn
only calls them in order and reports what came back, in words, never a score. What a turn leaves for the owner
are the conflict questions it raised, the cards the rule did not take and the pages to save in the browser
(docs/RESEARCH-WORKFLOW.md §8). Its report names each conflict the rule resolved or took back while it ran, one line
each (the person, the date or place kept, the rule's reason and the question id `tools/conclude.py reopen` gives it back
by; conclude.rule_conflict_changes reads them from the audit log after the last row there when the turn began), every
source that did not answer once, with what it was asked and what it said (a connector step logged error stays runnable,
and a place string the geocoder did not answer stays unresolved, so the next turn asks that source again), and every run
or part of the tail that failed, with its exception. A connector's answer no reader parses (a challenge page served in
place of the answer) is a source that did not answer, its exception named in what the source said (tools/run_step.py).
A file left in the inbox that fulfils no step is named once per run (the runner passes the files already named,
tools/turns.py), not in every turn's report.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, resolve_tree, write_json_whole
from catalog import Catalog
from plan import plan_person
import run_step
import fetches
from attach import attach_each, inbox_files, line
from conclude import reconsider, rule_conflict_changes, rule_conflict_line
from resolve_places import resolve_strings

RUNNER, PLANNER = "agent:run_step", "rule:plan@0.1.0"

# ---------------------------------------------------------------- the people who wait on pages to save in the browser

def state_path(db_path): return db_path + ".turn-state.json"

def read_state(db_path):
    """Every entry kept beside the database, of every tree: {tree_id, person_id, person, since, steps}, `since` the moment
    the person began to wait and `steps` the steps of the pages they wait on. A state in the one-turn shape (a person_id
    at its top) is that person's entry, since its started_at and steps None: the pages the fetch list holds for them now."""
    try:
        with open(state_path(db_path), encoding="utf-8") as fh: st = json.load(fh)
    except FileNotFoundError:
        return []
    if "waiting" in st: return st["waiting"]
    one = {"tree_id": st["tree_id"], "person_id": st["person_id"], "person": st.get("person")}
    return [{**one, "since": st.get("started_at"), "steps": None}]

def write_state(db_path, entries):
    """The entries kept beside the database; with none, the file is removed."""
    if not entries:
        try: os.remove(state_path(db_path))
        except FileNotFoundError: pass
        return
    write_json_whole(state_path(db_path), {"waiting": entries})

def own_steps(cx, pid):
    """Every step on a person's plan, by id."""
    return {sid for sid, in cx.execute("SELECT id FROM search_plan WHERE person_id=?", (pid,))}

def waiting_for(cx, tree_id, pid, entries=None):
    """The pages a person waits on: tools/fetches.py's own openable list (a link to open, steps with no run since the plan
    last wrote their fields; read when not given), narrowed to the entries where one of this person's own steps is still
    unrun (a shared census page naming relatives is still this person's page). An entry with no link, or already saved or
    logged on this person's step with unchanged fields, is not one they wait on, whatever other people's steps on the same
    page still wait."""
    entries = fetches.openable(cx, tree_id) if entries is None else entries
    mine = own_steps(cx, pid)
    return [e for e in entries if mine & set(e["open_step_ids"])]

def waiting(cx, db_path, tree_id, entries=None):
    """The people of this tree who wait: {person id: {person, since, steps, pages}}, steps the ones of theirs their entry
    names (every one of their own when it names none) that are still open on the fetch list (fetches.openable, read when not
    given), pages the list's entries holding one of them. A person none of whose steps is still open waits no more: a page
    of theirs has been saved, or their plan has changed."""
    entries = fetches.openable(cx, tree_id) if entries is None else entries
    out = {}
    for w in read_state(db_path):
        if w["tree_id"] != tree_id: continue
        mine = own_steps(cx, w["person_id"])
        named = mine if w.get("steps") is None else mine & set(w["steps"])
        pages = [e for e in entries if named & set(e["open_step_ids"])]
        steps = named & {s for e in pages for s in e["open_step_ids"]}
        if steps: out[w["person_id"]] = {"person": w.get("person"), "since": w.get("since"), "steps": steps, "pages": pages}
    return out

def waits(cx, db_path, tree_id):
    """{person id: the steps they wait on}, for the queue (tools/queue.py edge)."""
    return {pid: w["steps"] for pid, w in waiting(cx, db_path, tree_id).items()}

def set_waiting(cx, db_path, tree_id, people):
    """Each of these people waits on the pages the fetch list holds for them now, or waits no more when it holds none; every
    other entry of this tree is read again (waiting), so one none of whose pages is still open is dropped, and the other
    trees' entries are kept as they are. A person already waiting keeps the moment they began. Returns (the pages each of
    these people waits on, the people who waited before and wait no more, as {person, since})."""
    entries = fetches.openable(cx, tree_id)
    state = read_state(db_path)
    before = [w for w in state if w["tree_id"] == tree_id]
    others = [w for w in state if w["tree_id"] != tree_id]
    kept = waiting(cx, db_path, tree_id, entries)
    pages = {}
    for pid in people:
        pages[pid] = waiting_for(cx, tree_id, pid, entries)
        steps = own_steps(cx, pid) & {s for e in pages[pid] for s in e["open_step_ids"]}
        if not steps:
            kept.pop(pid, None)
            continue
        since = kept[pid]["since"] if pid in kept else now()
        kept[pid] = {"person": pid_name(cx, pid), "since": since, "steps": steps}
    mine = []
    for pid, w in kept.items():
        mine.append({"tree_id": tree_id, "person_id": pid, "person": w["person"], "since": w["since"], "steps": sorted(w["steps"])})
    write_state(db_path, others + mine)
    gone = []
    for w in before:
        if w["person_id"] in kept or w["person_id"] in people: continue
        gone.append({"person": w.get("person"), "since": w.get("since")})
    return pages, gone

def credited(cx, results, people):
    """The files each of these people's steps were reached by: {person id: [the results of the files]}."""
    out = {}
    for r in results:
        sids = [s[0] for s in r.get("steps") or []]
        if not sids: continue
        marks = ",".join("?" * len(sids))
        owners = {pid for pid, in cx.execute(f"SELECT DISTINCT person_id FROM search_plan WHERE id IN ({marks})", sids)}
        for pid in sorted(owners & set(people)):
            out.setdefault(pid, []).append(r)
    return out

# ---------------------------------------------------------------- the turn's parts

def last_audit(cx):
    """The id of the last audit row: where a turn's own writes begin."""
    return cx.execute("SELECT coalesce(max(id), '') FROM audit_log").fetchone()[0]

def person_ids(cx, tree_id):
    return {r[0]: r[1] for r in cx.execute("SELECT id, display_name FROM person WHERE tree_id=? AND merged_into IS NULL", (tree_id,))}

def guarded(cx, failures, what, act, transaction=True):
    """act() in a transaction of its own (or, with transaction False, a part that keeps one transaction per file of its own,
    as it is): committed and its value returned; or, when it raises, what it had not committed rolled back, the failure
    named in `failures` with its exception, and None returned, so the turn goes on to its next part."""
    if transaction: cx.execute("BEGIN")
    try:
        out = act()
        if transaction: cx.commit()
        return out
    except (Exception, SystemExit) as e:
        if cx.in_transaction: cx.rollback()
        said = f"{what} failed ({type(e).__name__}: {e})"
        failures.append(f"{said}: what it had not committed is rolled back, and the next turn runs it again")
        return None

def connector_steps(cx, cat, tree_id, pid):
    """The runner's own runnable steps (tools/run_step.py), narrowed to this person's plan: those a connector can take."""
    return [r for r in run_step.runnable(cx, cat, tree_id) if r["person_id"] == pid]

def run_connectors(cx, cat, tree_id, pid):
    """Every step this person's own plan can run at a connector, one commit per step, as tools/run_step.py --all does. A run
    that fails is an error run in the result (run_step.run), never an exception. An earlier step's own accept regenerates
    the plan in the same request (docs/RESEARCH-WORKFLOW.md §5-7) and can drop a later step already queued here, or add
    one; steps are read fresh before each run rather than as one snapshot, so a step gone by the time its turn comes is
    skipped, never run against a row that no longer exists, and a step the regeneration newly opens still gets its turn."""
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

def new_place_strings(cx, tree_id, people, since):
    """The place strings no resolver has read yet that this call should: those the persons of a record archived since it
    began carry (not the tree's own imported file: it is no record the call brought), and those behind these people's own
    events (their non-rejected assertions, a marriage included), as (place string id, words) by the words."""
    marks = ",".join("?" * len(people)) or "NULL"                   # no people: the records' strings alone
    return cx.execute(f"""SELECT DISTINCT ps.id, ps.raw FROM place_string ps JOIN persona_fact pf ON pf.place_string_id=ps.id JOIN persona pe ON pe.id=pf.persona_id
        WHERE ps.status='undecided' AND ps.place_id IS NULL AND ps.resolver IS NULL
          AND (pe.artifact_sha256 IN (SELECT sha256 FROM artifact WHERE created_at>=? AND sha256 NOT IN (SELECT artifact_sha256 FROM tree_import))
               OR pf.id IN (SELECT a.persona_fact_id FROM assertion a JOIN event_participant ep ON a.subject_kind='event' AND a.subject_id=ep.event_id
                            WHERE a.tree_id=? AND a.status<>'rejected'
                              AND (ep.person_id IN ({marks}) OR ep.family_id IN (SELECT family_id FROM family_member WHERE person_id IN ({marks}) AND role='partner'))))
        ORDER BY ps.raw""", (since or "9999", tree_id, *people, *people)).fetchall()

def resolve_places(cx, tree_id, people, since, by):
    """The place resolver on the strings new_place_strings names: what it accepted, rejected as no place and left a card, and
    the geocoder's silence if it did not answer (the strings it left stay unresolved, asked again by the next turn). None
    when there is nothing to read."""
    rows = new_place_strings(cx, tree_id, people, since)
    if not rows: return None
    stats, report, unanswered = resolve_strings(cx, tree_id, by, rows)
    return {"strings": len(rows), "accepted": stats["accepted"], "rejected": stats["rejected"], "cards": stats["undecided"] + stats["no_candidates"], "unanswered": unanswered}

def finish(cx, tree_id, slug, by, db, pid=None, since=None):
    """The tail: fetches.py collect, attach_inbox.py on whatever else the inbox holds, each one file per transaction (a
    file that fails is rolled back alone, left where it was and named in the report); each file credited to the people
    who wait whose steps it reached (credited; the turn's own person apart); the place resolver on the new place strings
    of this turn's person and of those people (before the rule goes over the conflicts, so an event the answers place is
    compared as placed); conclude.py reconsider; the plan regenerated for each of them. Each part guarded. The people who
    waited and wait no more, though no file of this call's reached them (a page attached by hand, or logged on the person
    screen, while they waited), are finished the same way, credited with no file. With no person of its own (a resume), the
    resolver, reconsider and the plans run only when a file came in or such a person is there. Returns {results (every
    file the collect and the attach took, one each), own (the files the call reports itself: those its own person's steps
    were reached by, and those that reached nobody who waits), credited ({person id: their files}, for the people who
    wait), ended ({person id: their entry}, those of them whose pages came in outside the call), places, recon, plans
    ({person id: the plan's stats}), failures}."""
    out = {"results": [], "own": [], "credited": {}, "ended": {}, "places": None, "recon": [], "plans": {}, "failures": []}
    waiting_now = waiting(cx, db, tree_id)                          # read before the collect: a page it takes is no longer open
    who_waits = set(waiting_now) - {pid}
    for w in read_state(db):                                        # a page of a person who waits already run (attached by hand, logged on the person screen): it came in outside this call's collect
        if w["tree_id"] != tree_id or w["person_id"] == pid: continue
        mine = own_steps(cx, w["person_id"])
        closed = (mine if w.get("steps") is None else mine & set(w["steps"])) - waiting_now.get(w["person_id"], {}).get("steps", set())
        if closed and came_in_lines(cx, w["person_id"], w.get("since"), closed): out["ended"][w["person_id"]] = {**w, "closed": closed}
    took = guarded(cx, out["failures"], "the collect", lambda: fetches.collect(cx, tree_id, slug, by), transaction=False)
    names, collected = took or ([], [])
    inbox = lambda: attach_each(cx, tree_id, slug, by, [f for f in inbox_files() if f not in names])
    left = guarded(cx, out["failures"], "the inbox's attach", inbox, transaction=False)
    out["results"] = collected + (left or [])
    reached = credited(cx, out["results"], who_waits | ({pid} if pid else set()))
    out["credited"] = {**{w: [] for w in out["ended"]}, **{w: rs for w, rs in reached.items() if w != pid}}
    theirs = {id(r) for rs in out["credited"].values() for r in rs}
    mine = {id(r) for r in reached.get(pid, [])}
    out["own"] = [r for r in out["results"] if id(r) in mine or id(r) not in theirs]
    if not pid and not any(not r.get("left") for r in out["results"]) and not out["ended"]: return out
    people = ([pid] if pid else []) + list(out["credited"])
    began = min([since] + [w["since"] for w in out["ended"].values() if w.get("since")])        # a page that came in while they waited brought its place strings then
    out["places"] = guarded(cx, out["failures"], "the place resolver", lambda: resolve_places(cx, tree_id, people, began, by))
    out["recon"] = guarded(cx, out["failures"], "reconsider", lambda: reconsider(cx, tree_id, by)) or []
    for p in people:
        plan = lambda p=p: plan_person(cx, tree_id, p, PLANNER)
        out["plans"][p] = guarded(cx, out["failures"], f"the plan for {pid_name(cx, p)}", plan)
    return out

# ---------------------------------------------------------------- the report, in words

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

def held_lines(conn_runs, results):
    """What was fetched and archived, in words: the connector runs that found something or found nothing, then the pages
    the browser session brought back. A run that got no answer is told once, by unanswered_lines; a run that failed once,
    by failed_lines."""
    out = []
    for run in conn_runs:
        for r in run["results"]:
            if "error" in r: out.append(f"  {run['row_key']}: {r['error']}"); continue
            if r.get("outcome") == "found":
                out.append(f"  {run['row_key']} at {r['connector']}: found, {len(r.get('artifacts') or [])} artifact(s), {len(r.get('extracted') or [])} record(s) read")
            elif r.get("outcome") and r["outcome"] != "error": out.append(f"  {run['row_key']} at {r['connector']}: {r['outcome']}")
    for r in results:
        if not r.get("left"): out.append("  " + line(r))
    return out

def decided_lines(conn_runs, results, recon):
    out = []
    for run in conn_runs:
        for r in run["results"]:
            for e in r.get("extracted") or []:
                if e.get("accepted_by_rule"): out.append(f"  {run['row_key']}: the rule took {e['accepted_by_rule']} of {e['proposals']} proposal(s)")
    for r in results:
        if r.get("accepted_by_rule"): out.append(f"  {r['file']}: the rule took {len(r['accepted_by_rule'])} proposal(s)" if isinstance(r["accepted_by_rule"], list) else f"  {r['file']}: the rule took {r['accepted_by_rule']} proposal(s)")
    for row in recon:
        if row["kind"] == "card" and row["taken"]: out.append(f"  reconsider: the rule took {row['person']} / {row['persona']}: {row['why']}")
        elif row["kind"] == "decision" and not row["kept"]: out.append(f"  reconsider: withdrew {row['person']} / {row['persona']}: {row['why']}")
    return out

def unanswered_lines(cx, conn_runs):
    """The connector runs logged error this turn because the source did not answer, one line for each such source: the
    registry's name of the runs' own source, the rows of the steps it was asked on and what it said first. Such a run does
    not count as a run on the step's fields (log_search.ran_unchanged), so the step stays runnable and the next turn asks
    the source again. A run that failed in the runner's own work is told by failed_lines."""
    by = {}
    for run in conn_runs:
        for r in run["results"]:
            if r.get("outcome") != "error" or not r.get("log") or r.get("failed"): continue
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

def failed_lines(conn_runs, failures):
    """The runs whose own reading, matching or requests failed (run_step.run: an error run, the exception under `failed`),
    one line each, then each part of the turn that failed (guarded), with its exception."""
    out = []
    for run in conn_runs:
        for r in run["results"]:
            if not r.get("failed"): continue
            out.append(f"  {run['row_key']} at {r['connector']}: {r['failed']}; logged error, the step stays runnable and the next turn runs it again")
    return out + [f"  {f}" for f in failures]

def person_left_lines(cx, cat, pid):
    """This person's own open work, as the owner has it to do."""
    w = cat.waiting(pid); bl = cat.baseline(pid); name = pid_name(cx, pid)
    out = []
    if not bl["complete"]: out.append(f"  {name}: {len(bl['undecided'])} key fact(s) still undecided: {', '.join(bl['undecided'])}")
    if w["documents"]: out.append(f"  {name}: {w['documents']} document(s) still waiting for a decision")
    if w["conflicts"]: out.append(f"  {name}: {w['conflicts']} conflict question(s) open")
    if w["needs_hand"]: out.append(f"  {name}: {w['needs_hand']} planned step(s) only a hand can take: a page to save in the browser, an assisted search, a film browsed by hand")
    return out

def call_left_lines(results, recon, watch, reported):
    """What a call leaves beside one person's work: any file left in the inbox that fulfilled no step (named once per run:
    `reported` holds the files an earlier report of the run already named), and reconsider's own cards named for the people
    in `watch` (this turn's person, or someone it created). Reconsider examines the whole tree, not one person's turn, so a
    card naming somebody else is counted, not listed: that count was already there, or wasn't, before this turn ran."""
    out = []
    for r in results:
        if r.get("left") and r["file"] not in reported: out.append("  " + line(r)); reported.add(r["file"])
    elsewhere = 0
    for row in recon:
        if row["kind"] != "card" or row["taken"]: continue
        if row["person"] in watch: out.append(f"  reconsider: a card for {row['person']} / {row['persona']}, the rule does not take it: {row['why']}")
        else: elsewhere += 1
    if elsewhere: out.append(f"  {elsewhere} card(s) elsewhere in the tree the rule still does not take, unrelated to this turn (tools/cards.py \"<person>\")")
    return out

def pid_name(cx, pid): return cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0]

def pages_lines(pages):
    """The pages a person waits on, one line each as tools/fetches.py next prints them, with how they are taken."""
    if not pages: return []
    head = f"waits on {len(pages)} page(s) to save in the browser, one tab each; "
    head += "the next tools/turns.py, or tools/turn.py --resume, takes what is saved:"
    return ["", head] + ["  " + fetches.page_line(e) for e in pages]

def gone_lines(gone):
    """The people who waited and wait no more, none of their pages open on the fetch list now."""
    if not gone: return []
    head = "waits no more (none of their pages is open on the fetch list now: saved, or the plan has changed):"
    return ["", head] + [f"  {g['person']} (waiting since {g['since']})" for g in gone]

def rule_lines(cx, tree_id, tail, mark):
    """What the rule decided in the call beyond the files: the place resolver's answer and the conflicts it resolved or took back."""
    conflicts = ["  " + rule_conflict_line(x) for x in rule_conflict_changes(cx, tree_id, mark)]
    return places_decided_lines(tail["places"]) + conflicts

def created_lines(cx, tree_id, before_ids):
    return [f"  {n} [{i[-6:]}]" for i, n in person_ids(cx, tree_id).items() if i not in before_ids]

def watched(cx, tree_id, before_ids, tail, pid=None):
    """The people whose cards a call's report names one by one: its own person, the people it created, and the people who
    waited whose turns it finished."""
    names = {n for i, n in person_ids(cx, tree_id).items() if i not in before_ids}
    return names | {pid_name(cx, p) for p in list(tail["credited"]) + ([pid] if pid else [])}

def report(cx, tree_id, pid, before_ids, conn_runs, tail, pages, failures, reported, mark, gone=()):
    """The turn's own report, in words: held, decided, created, left, the pages its person waits on, the plan."""
    reported = set() if reported is None else reported
    cat = Catalog(cx, tree_id)
    results = tail["own"]
    out = [f"turn: {pid_name(cx, pid)}", "", "held:"]
    out += held_lines(conn_runs, results) or ["  nothing new archived"]
    out += ["", "decided:"]
    decided = decided_lines(conn_runs, results, tail["recon"]) + rule_lines(cx, tree_id, tail, mark)
    out += decided or ["  nothing for the rule to take"]
    out += ["", "created:"]
    out += created_lines(cx, tree_id, before_ids) or ["  nobody"]
    out += ["", "left:"]
    left = person_left_lines(cx, cat, pid)
    left += call_left_lines(results, tail["recon"], watched(cx, tree_id, before_ids, tail, pid), reported)
    left += unanswered_lines(cx, conn_runs) + failed_lines(conn_runs, failures) + places_left_lines(cx, tail["places"])
    out += left or ["  nothing outstanding on this person"]
    out += pages_lines(pages) + gone_lines(gone)
    out += ["", f"plan: {dumps(tail['plans'].get(pid))}"]
    return "\n".join(out)

def came_in_lines(cx, pid, since, steps):
    """What the runs logged on these steps of a person since they began to wait hold, in words: the pages that came in outside
    the collect that finishes their turn (attached by hand, logged on the person screen)."""
    marks = ",".join("?" * len(steps)) or "NULL"
    out = []
    for row_key, source, outcome, arts in cx.execute(f"""SELECT sp.row_key, l.source_id, l.outcome, l.artifacts_json FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id
                                                         WHERE sp.person_id=? AND sp.id IN ({marks}) AND l.executed_at>=? AND l.superseded_by IS NULL AND l.artifacts_json IS NOT NULL
                                                         ORDER BY l.executed_at, l.id""", (pid, *steps, since or "")):
        n = len(json.loads(arts or "[]"))
        if n: out.append(f"  {row_key} at {source}: {outcome}, {n} artifact(s), taken in outside the collect")
    return out

def finished_report(cx, tree_id, pid, tail, pages):
    """The report of a person who waited whose turn a collect finished: the files credited to them, what the rule took on
    them, what is left for the owner, the pages they still wait on, the plan regenerated for them. For a person whose pages
    came in outside the collect, what their steps' runs hold since they began to wait stands for the files, and what the rule
    took is the audit log's."""
    cat = Catalog(cx, tree_id)
    results = tail["credited"][pid]
    ended = tail["ended"].get(pid)
    out = [f"turn: {pid_name(cx, pid)} [{pid[-6:]}], finished on the pages saved for them", "", "held:"]
    out += held_lines([], results) + (came_in_lines(cx, pid, ended.get("since"), ended["closed"]) if ended else []) or ["  nothing new archived"]
    out += ["", "decided:"]
    out += decided_lines([], results, [r for r in tail["recon"] if r["person"] == pid_name(cx, pid)] if ended else []) or ["  nothing for the rule to take"]
    out += ["", "left:"]
    out += person_left_lines(cx, cat, pid) or ["  nothing outstanding on this person"]
    out += pages_lines(pages) or ["", "waits on no page now"]
    out += ["", f"plan: {dumps(tail['plans'].get(pid))}"]
    return "\n".join(out)

def resume_report(cx, tree_id, before_ids, tail, reported, mark, gone, db):
    """A resume's own report: the files that reached nobody who waits, what the rule decided in the call, who was created,
    what is left; with nothing saved, who waits on how many pages."""
    reported = set() if reported is None else reported
    if not any(not r.get("left") for r in tail["results"]) and not tail["failures"] and not tail["ended"]:
        w = waiting(cx, db, tree_id)
        pages = {e["url"] for x in w.values() for e in x["pages"]}
        said = f"{len(w)} person(s) wait on {len(pages)} page(s) to save in the browser (tools/fetches.py next)"
        out = [f"resume: nothing saved in the browser has come in; {said if w else 'nobody waits on a page to save in the browser'}"]
        left = call_left_lines(tail["results"], [], set(), reported)
        if left: out += ["", "left:"] + left
        return "\n".join(out + gone_lines(gone))
    results = tail["own"]
    out = ["resume: the pages saved in the browser", "", "held, for nobody who waits:"]
    out += held_lines([], results) or ["  nothing"]
    out += ["", "decided:"]
    decided = decided_lines([], results, tail["recon"]) + rule_lines(cx, tree_id, tail, mark)
    out += decided or ["  nothing for the rule to take"]
    out += ["", "created:"]
    out += created_lines(cx, tree_id, before_ids) or ["  nobody"]
    out += ["", "left:"]
    left = call_left_lines(tail["results"], tail["recon"], watched(cx, tree_id, before_ids, tail), reported)
    left += failed_lines([], tail["failures"]) + places_left_lines(cx, tail["places"])
    out += left or ["  nothing"]
    out += gone_lines(gone)
    return "\n".join(out)

# ---------------------------------------------------------------- a turn, and a resume

def start(cx, tree_id, slug, pid, by, db, reported=None):
    """One turn on a person: the plan, every connector step, the tail, the report and the pages the person waits on, then
    the reports of the people who wait whose turns the tail's collect finished. Returns the tail."""
    before = person_ids(cx, tree_id)
    since = now()
    mark = last_audit(cx)
    failures = []
    guarded(cx, failures, "the plan", lambda: plan_person(cx, tree_id, pid, PLANNER))
    conn_runs = run_connectors(cx, Catalog(cx, tree_id), tree_id, pid)
    tail = finish(cx, tree_id, slug, by, db, pid, since)
    pages, gone = set_waiting(cx, db, tree_id, [pid] + list(tail["credited"]))
    failures += tail["failures"]
    print(report(cx, tree_id, pid, before, conn_runs, tail, pages[pid], failures, reported, mark, gone))
    for w in tail["credited"]:
        print("\n" + finished_report(cx, tree_id, w, tail, pages[w]))
    return tail

def start_guarded(cx, tree_id, slug, pid, by, db, reported=None):
    """One turn (start) that fails outside its runs and its tail's parts stops there: what it had not committed is rolled back,
    the failure printed with its exception, and its text returned; None when the turn ran."""
    try:
        start(cx, tree_id, slug, pid, by, db, reported=reported)
        return None
    except (Exception, SystemExit) as ex:
        if cx.in_transaction: cx.rollback()
        why = f"the turn failed ({type(ex).__name__}: {ex}): it stopped there, what it had not committed rolled back"
        print(f"turn: {pid_name(cx, pid)}\n\n{why}")
        return why

def resume(cx, tree_id, slug, by, db, reported=None):
    """Whatever has been saved in the browser taken in, each file credited, and the turns of the people who wait that it
    reached finished, each with its report after the resume's own. Returns the tail."""
    before = person_ids(cx, tree_id)
    since = now()
    mark = last_audit(cx)
    tail = finish(cx, tree_id, slug, by, db, None, since)
    pages, gone = set_waiting(cx, db, tree_id, list(tail["credited"]))
    print(resume_report(cx, tree_id, before, tail, reported, mark, gone, db))
    for w in tail["credited"]:
        print("\n" + finished_report(cx, tree_id, w, tail, pages[w]))
    return tail

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
        if start_guarded(cx, tree_id, slug, pid, a.by, a.db): sys.exit(1)

if __name__ == "__main__": main()
