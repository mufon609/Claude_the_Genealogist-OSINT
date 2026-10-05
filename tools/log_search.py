#!/usr/bin/env python3
"""Record the outcome of a search step, including nothing found; dismiss a question.

usage: tools/log_search.py --step <search_plan id> --outcome found|none|blocked|error [--artifact sha256 ...] [--note ...] [--query '{...}']
       tools/log_search.py --question <research_question id> --source <registry id> --outcome ... --query '{...}'   (a search not on the plan)
       tools/log_search.py --dismiss <research_question id> [--note ...]   (--note is required for a conflict: its written reason)
       tools/log_search.py --list "<person>"

The query recorded is exactly what was run: the step's fields after the person's
include/revise unless --query overrides them. A 'found' outcome marks the step done
(a fetch step only when the page is the record it cites, holds_record); 'none' leaves
it planned so it can be retried with different fields, and the log shows it was
tried; 'unread' is a record archived that no parser reads, a web page or a connector's
JSON or text response alike (unread_record): tools/attach.py and tools/run_step.py write
it, never a hand, the record is held on the step's log and the step stays planned.
A dismissed question stays closed when the plan is regenerated.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, resolve_tree, ulid, year_field, year_in
from catalog import Catalog

def rendered_query(query_json, revisions_json):
    """The step's fields ({value, basis} each) after the person's include/revise: an excluded field is dropped,
    a revised value replaces the tree's and is a claim of the searcher that remembers what it revised. A revised year field
    (treelib.year_field) is read as the year it gives (treelib.year_in: "1880?" stored before the screen refused it is 1880),
    so every reader of the fields, the runner, the connectors and the attach, is given a year."""
    fields = json.loads(query_json or "{}"); rev = json.loads(revisions_json or "{}")
    out = {}
    for k, v in fields.items():
        f = v if isinstance(v, dict) and "basis" in v else {"value": v, "basis": "claim"}
        r = rev.get(k) or {}
        if r.get("include") is False: continue
        if r.get("value") not in (None, ""):
            value = year_in(r["value"]) if year_field(k) and year_in(r["value"]) is not None else r["value"]
            f = {"value": value, "basis": "claim", "revised_from": f["value"]}
        out[k] = f
    return out

REOPENED = "reopened: "                                   # the note prefix of a reopen's log row: what a later reader of the log looks for

def same_fields(rendered, ran, outcome=None):
    """Whether a run's fields as logged are the step's rendered fields now, value for value: the same query again. What the run
    added beside the step's fields is not the step's (surname_variants, the alias table's spellings, basis record; a results
    page's fields as searched, basis run); a place field tried name by name is the same when the names tried are the step's
    own names, or, for a run that stopped at a hit (the run stops at the first name that gets a hit and never tries the rest,
    whatever the outcome: found, or none because the hits were a book the Archive lends or a listing none of whose rows fits
    anyone), the step's names up to and including the one that got it; a name added or dropped before that point, or any name
    added after a run that tried them all, is a change, as is a field the step has dropped or added since. A run says that it
    stopped at a hit by `stopped_at_hit` beside `tried` on its logged place field; a run logged before the mark existed is
    read by its outcome, which is the run's: found stopped at its hit. A run with a name the source did not answer
    (`unanswered` beside `tried`) never asked the step's fields in full, so it is not the same query: the name is asked again."""
    for k, f in rendered.items():
        r = ran.get(k)
        if r is None: return False
        if not isinstance(r, dict): r = {"value": r}
        if r.get("tried"):
            if r.get("unanswered"): return False
            names = f["value"] if isinstance(f["value"], list) else [f["value"]]
            tried = list(r["tried"])
            stopped = r["stopped_at_hit"] if "stopped_at_hit" in r else outcome == "found"
            if tried != names[:len(tried)] or (len(tried) < len(names) and not stopped): return False
        elif r.get("value") != f["value"]: return False
    return all(k in rendered for k, v in ran.items() if not (isinstance(v, dict) and v.get("basis") in ("run", "record")))

def step_source(step):
    """The source a run of the step is logged under when the run names none: the step's holder (a fetch step's locator source),
    else the first of its row's sources. What a page saved by hand is logged under, and what the fetch list reads."""
    return step["locator_source_id"] or (json.loads(step["sources_json"] or "[]") or [None])[0]

def latest_answer(cx, step, source_id=None):
    """The step's latest run the source answered: (outcome, executed_at, fields as logged, the artifacts it holds), or None. A
    reopen's own row is bookkeeping, not a run, and a run logged error is a source that did not answer (a timeout, a challenge,
    a reset connection): both are looked past. With a source named, that source's own rows alone (search_log.source_id): a step
    whose sources have two connectors is answered by each on its own; with none, the latest answer whatever its source."""
    for q, note, outcome, sid, at, arts in cx.execute("SELECT query_json, notes, outcome, source_id, executed_at, artifacts_json FROM search_log WHERE plan_step_id=? AND superseded_by IS NULL ORDER BY executed_at DESC, id DESC", (step["id"],)):
        if (note or "").startswith(REOPENED) or outcome == "error": continue
        if source_id and sid != source_id: continue
        return outcome, at, json.loads(q or "{}"), json.loads(arts or "[]")
    return None

def ran_unchanged(cx, step, rendered, source_id=None):
    """Whether the step's latest run the source answered (latest_answer) asked these very fields: nothing has changed on the step
    since, so running it again at that source would be the same query blind. A found, none or unread run (an unread record
    is held: the step is not asked for it again) before an error on the same fields still closes the step at that source; a
    source whose runs are all errors is asked again. Read per source: one
    connector's none run on the step's fields does not close the step at another source, which is asked until it answers."""
    a = latest_answer(cx, step, source_id)
    return a is not None and same_fields(rendered, a[2], a[0])

HOUSEHOLD = "the household's record, accepted onto "     # the note prefix of a run written when a household record's persona is accepted onto a person
ON_WORD = "on the owner's word about "                 # the note prefix of the run attach.on_word writes: the owner's word that a record is a person's, never reopened by the plan

def holds_record(cx, sha):
    """Whether an archived file is a record a fetch step's found run may close the step with: a file never parsed (an image, a
    photograph of the stone) is what was fetched; a page is one when its current reading (the latest not superseded) is
    complete and not a pointing listing (extract.POINTING_LISTINGS). A listing that points at records is not one, and a
    page no parser read holds nothing, so neither closes the step it was logged on."""
    from extract import POINTING_LISTINGS
    e = cx.execute("""SELECT e.status, x.name FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.artifact_sha256=? AND e.superseded_by IS NULL
                      ORDER BY e.ran_at DESC, e.id DESC LIMIT 1""", (sha,)).fetchone()
    return True if not e else e[0] == "complete" and e[1] not in POINTING_LISTINGS

UNREAD = "no parser reads this record"                  # the note prefix of an unread run: the record is held and holds nothing a program knows

def unread_record(cx, sha):
    """Whether an archived record is one nobody has read, whatever its form (a web page, a connector's JSON or text response):
    its every extraction is the failed one tools/extract.py writes for a file no parser claims, and at least one exists. A
    record a parser claimed or the model or a person read through the transcription path (an extraction of its own, complete
    or partial) is not; nor is an image, which the transcription path reads and no parser does, whatever extraction it
    carries; nor a file no parser was asked to read (an item's metadata, a search's own response: the runner reads neither
    as a record), which carries none. Those runs stay as they are. A run whose records are all such records (the attach's
    one page, a connector's run's records) is logged `unread`, not `found`: the records are held on the step's log and the
    step stays planned."""
    mime = cx.execute("SELECT mime FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if not mime or (mime[0] or "").startswith("image/"): return False
    return {s for s, in cx.execute("SELECT status FROM extraction WHERE artifact_sha256=?", (sha,))} == {"failed"}

def restate(cx, by, log_id, outcome=None, note=None, step_id=None):
    """A run read again, as a new row: the run's own moment, actor, source, fields and artifacts restated, with the outcome its
    records are read as (outcome), its note begun with what they were read as (note, the run's own note kept after it), or on
    another step (step_id: a merge carrying the duplicate's run onto the kept person's step); the old row's superseded_by,
    written once, names the new one, and every reader reads the rows whose superseded_by is empty (search_log is insert-only,
    schema/sqlite_extras.sql). One audit row under `by` naming the row superseded. Returns the new row's id."""
    old = cx.execute("SELECT tree_id, plan_step_id, question_id, executed_at, executed_by, source_id, query_json, outcome, artifacts_json, notes FROM search_log WHERE id=? AND superseded_by IS NULL", (log_id,)).fetchone()
    if not old: raise SystemExit(f"no run {log_id} that is not superseded")
    tree, step, question, at, executed_by, source, query, was, arts, notes = old
    lid, outcome, step = ulid(), outcome or was, step_id or step
    notes = "; ".join(x for x in (note, notes) if x) or None
    cx.execute("""INSERT INTO search_log (id,tree_id,plan_step_id,question_id,executed_at,executed_by,source_id,query_json,outcome,artifacts_json,notes)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (lid, tree, step, question, at, executed_by, source, query, outcome, arts, notes))
    cx.execute("UPDATE search_log SET superseded_by=? WHERE id=?", (lid, log_id))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree, now(), by, "insert", "search_log", lid, dumps({"step": step, "outcome": outcome, "artifacts": json.loads(arts or "[]"), "supersedes": log_id,
                                                                           "was": {"outcome": was, **({"step": old[1]} if step != old[1] else {})}})))
    return lid

def hold_unread(cx, by, log_id):
    """A run already logged found whose records no parser reads (unread_record) is an unread run: restated (restate) with the
    outcome unread and its note begun with UNREAD, the records held on the step's log. The caller, which logged the run before
    the records were read, returns any step the run marked done to the status it had. Returns the new row's id."""
    return restate(cx, by, log_id, outcome="unread", note=UNREAD)

def closed_by_pointers(cx, step_id):
    """Whether a step's found runs, since it was last reopened, are all pages that point at its record or hold nothing
    (not holds_record): the step stands done on listings or pages no parser read alone (an unread run, the attach's and the runner's word
    for a record no parser reads, is not a found run and closes nothing). False when it has no found run since, when
    a found run carries no artifact (a hand's found: the owner's word) or is the owner's word about a record (ON_WORD), or
    when any found run carries a record."""
    since = cx.execute("SELECT coalesce(max(id), '') FROM search_log WHERE plan_step_id=? AND notes LIKE ? AND superseded_by IS NULL", (step_id, REOPENED + "%")).fetchone()[0]
    runs = cx.execute("SELECT artifacts_json, notes FROM search_log WHERE plan_step_id=? AND outcome='found' AND id > ? AND superseded_by IS NULL", (step_id, since)).fetchall()
    if not runs: return False
    for arts, note in runs:
        shas = json.loads(arts or "[]")
        if not shas or (note or "").startswith(ON_WORD) or any(holds_record(cx, s) for s in shas): return False
    return True

def hold_household(cx, tree_id, person_id, sha, by):
    """A household record (a census page, whichever way it arrived: a connector's answer, a page saved by hand, a search's
    result) accepted onto a person holds that person's own checklist row for its census year: every planned step of theirs
    on that row (extract.household_row) is logged found with the record, the way tools/run_step.py logs the household's other
    steps for a connector's answer, so catalog.fetched_rows reads the row held and no runner searches that census again for a
    household the tree has read. Returns the step ids logged; a step already logged with this record is left as it is."""
    from extract import household_row
    e = cx.execute("SELECT structured_json FROM extraction WHERE artifact_sha256=? AND status<>'failed' AND superseded_by IS NULL ORDER BY ran_at DESC LIMIT 1", (sha,)).fetchone()
    row = household_row(json.loads(e[0] or "{}")) if e else None
    if not row: return []
    name = cx.execute("SELECT display_name FROM person WHERE id=?", (person_id,)).fetchone()[0]
    out = []
    for sid, qj, rj in cx.execute("SELECT id, query_json, revisions_json FROM search_plan WHERE person_id=? AND row_key=? AND status='planned' ORDER BY seq", (person_id, row)).fetchall():
        if cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json LIKE ? AND superseded_by IS NULL", (sid, f'%"{sha}"%')).fetchone(): continue
        log(cx, tree_id, by, step_id=sid, outcome="found", artifacts=[sha], note=f"{HOUSEHOLD}{name}", query=rendered_query(qj, rj))
        out.append(sid)
    return out

def release_household(cx, tree_id, person_id, sha, by):
    """The steps hold_household logged found with this record for this person are planned again (reopen) once the record's
    persona is rejected for them: the record no longer holds their row. Returns the step ids reopened."""
    out = []
    for sid, in cx.execute("""SELECT DISTINCT l.plan_step_id FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id
                              WHERE sp.person_id=? AND sp.status='done' AND l.outcome='found' AND l.notes LIKE ? AND l.artifacts_json LIKE ? AND l.superseded_by IS NULL
                              AND NOT EXISTS (SELECT 1 FROM search_log r WHERE r.plan_step_id=l.plan_step_id AND r.notes LIKE ? AND r.id > l.id AND r.superseded_by IS NULL)""",
                           (person_id, HOUSEHOLD + "%", f'%"{sha}"%', REOPENED + "%")).fetchall():
        reopen(cx, tree_id, by, sid, "the record's persona is rejected for this person: it no longer holds the row"); out.append(sid)
    return out

def reopen(cx, tree_id, by, step_id, note):
    """A step marked done by a run that did not hold its record after all is planned again; the run's log row stays as what
    happened and a new row, its note under REOPENED, says why the step reopened. From that row on, the earlier found run no
    longer names the person as one the record was fetched for (match.persons_for reads the reopen). The reopen row carries
    the source of the run it reopens, the step's latest run that is not itself a reopen; a step with no run takes log()'s
    own fallback, the step's holder or first source."""
    st = cx.execute("SELECT id, status FROM search_plan WHERE id=?", (step_id,)).fetchone()
    if not st: raise SystemExit(f"no step {step_id}")
    cx.execute("UPDATE search_plan SET status='planned' WHERE id=?", (step_id,))
    last = next((sid for sid, n in cx.execute("SELECT source_id, notes FROM search_log WHERE plan_step_id=? AND superseded_by IS NULL ORDER BY executed_at DESC, id DESC", (step_id,))
                 if not (n or "").startswith(REOPENED)), None)
    return log(cx, tree_id, by, step_id=step_id, source_id=last, outcome="none", note=f"{REOPENED}{note}")

def log(cx, tree_id, by, step_id=None, question_id=None, source_id=None, outcome="none", artifacts=None, note=None, query=None, done=True):
    """One run of a step (or of a question with no step) into search_log; a found run marks the step done unless done is
    False (a fetch step answered at a source other than its holder: the pages found are held, the cited record is not; or by
    a page that is not the record it cites, a listing that points at one: tools/attach.py marks the step done itself once the
    page is read, holds_record); an unread run (unread_record) marks no step done."""
    ts = now()
    if step_id:
        st = cx.execute("SELECT id, question_id, query_json, sources_json, revisions_json, locator_source_id FROM search_plan WHERE id=?", (step_id,)).fetchone()
        if not st: raise SystemExit(f"no step {step_id}")
        st = dict(zip(("id", "question_id", "query_json", "sources_json", "revisions_json", "locator_source_id"), st))   # a plain tuple or a Row alike
        question_id = st["question_id"]; query = query or rendered_query(st["query_json"], st["revisions_json"]); source_id = source_id or step_source(st)
    if question_id and not cx.execute("SELECT 1 FROM research_question WHERE id=? AND tree_id=?", (question_id, tree_id)).fetchone(): raise SystemExit("question not in this tree")
    lid = ulid()
    cx.execute("""INSERT INTO search_log (id,tree_id,plan_step_id,question_id,executed_at,executed_by,source_id,query_json,outcome,artifacts_json,notes)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (lid, tree_id, step_id, question_id, ts, by, source_id, dumps(query or {}), outcome, dumps(artifacts) if artifacts else None, note))
    if step_id and outcome == "found" and done: cx.execute("UPDATE search_plan SET status='done' WHERE id=?", (step_id,))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "insert", "search_log", lid, dumps({"step": step_id, "outcome": outcome, "artifacts": artifacts or []})))
    return lid

def dismiss(cx, tree_id, by, question_id, note=None):
    """Close a question as dismissed by a person; the planner never reopens it. A conflict is never dismissed without a
    written reason (docs/RESEARCH-WORKFLOW.md §5–7): note is required for one and refused when it is empty. The reason, who
    gave it and when are kept on the closed question (its detail's dismissal) and on the audit row. A dismissal keeps neither
    side of a conflict and changes no event: keeping a statement is tools/conclude.py resolve."""
    ts = now()
    q = cx.execute("SELECT kind, detail_json FROM research_question WHERE id=? AND tree_id=? AND status='open'", (question_id, tree_id)).fetchone()
    if not q: raise SystemExit("no open question with that id in this tree")
    note = (note or "").strip() or None
    if q[0] == "conflict" and not note:
        raise SystemExit("a conflict is dismissed with a written reason (--note); to keep one side of it use tools/conclude.py resolve")
    detail = {**json.loads(q[1] or "{}"), "dismissal": {"note": note, "by": by, "at": ts}}
    cx.execute("UPDATE research_question SET status='closed', closed_reason='dismissed', closed_at=?, detail_json=? WHERE id=?", (ts, dumps(detail), question_id))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "research_question", question_id, dumps({"status": "closed", "closed_reason": "dismissed", "note": note})))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--step"); ap.add_argument("--question"); ap.add_argument("--source"); ap.add_argument("--outcome", choices=["found", "none", "blocked", "error"])
    ap.add_argument("--artifact", action="append"); ap.add_argument("--note"); ap.add_argument("--query"); ap.add_argument("--list"); ap.add_argument("--dismiss"); ap.add_argument("--reopen", help="a step marked done in error: planned again, with --note saying why"); ap.add_argument("--tree")
    ap.add_argument("--db", default=DB); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db); tree_id, slug = resolve_tree(cx, a.tree)
    if a.list:
        cat = Catalog(cx, tree_id); pid = cat.find_person(a.list)
        print(f"{'step id':26}  {'kind':6} {'mode':17} {'status':8} {'row':34} {'locator':20} runs (outcome@date)  -- rationale")
        for row in cx.execute("""SELECT sp.id, sp.kind, sp.mode, sp.status, sp.row_key, sp.locator_value, sp.rationale,
                                        (SELECT GROUP_CONCAT(l.outcome || '@' || substr(l.executed_at,1,10), ' ') FROM search_log l WHERE l.plan_step_id=sp.id AND l.superseded_by IS NULL)
                                 FROM search_plan sp WHERE sp.person_id=? ORDER BY sp.seq""", (pid,)):
            print(f"{row[0]}  {row[1]:6} {row[2]:17} {row[3]:8} {row[4][:34]:34} {(row[5] or '')[:20]:20} {row[7] or ''}  -- {row[6][:50]}")
        return
    if a.dismiss:
        cx.execute("BEGIN"); dismiss(cx, tree_id, a.by, a.dismiss, a.note); cx.commit(); print("dismissed", a.dismiss); return
    if a.reopen:
        if not a.note: sys.exit("--note says why the step reopens")
        cx.execute("BEGIN"); lid = reopen(cx, tree_id, a.by, a.reopen, a.note); cx.commit(); print("reopened", a.reopen, "log", lid); return
    if not a.outcome: sys.exit("--outcome required")
    cx.execute("BEGIN"); lid = log(cx, tree_id, a.by, a.step, a.question, a.source, a.outcome, a.artifact, a.note, json.loads(a.query) if a.query else None); cx.commit()
    print("logged", lid, a.outcome)

if __name__ == "__main__": main()
