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

REOPENED = "reopened: "                                   # the note prefix of a reopen's log row: what a later reader of the log looks for

def same_fields(rendered, ran):
    """Whether a run's fields as logged are the step's rendered fields now, value for value: the same query again. What the run
    added beside the step's fields is not the step's (surname_variants, the alias table's spellings, basis record; a results
    page's fields as searched, basis run); a place field tried name by name is the same when the names tried are the step's
    own names; a field the step has dropped or added since is a change."""
    for k, f in rendered.items():
        r = ran.get(k)
        if r is None: return False
        if not isinstance(r, dict): r = {"value": r}
        if k == "place" and r.get("tried"):
            names = f["value"] if isinstance(f["value"], list) else [f["value"]]
            if list(r["tried"]) != list(names): return False
        elif r.get("value") != f["value"]: return False
    return all(k in rendered for k, v in ran.items() if not (isinstance(v, dict) and v.get("basis") in ("run", "record")))

def step_source(step):
    """The source a run of the step is logged under when the run names none: the step's holder (a fetch step's locator source),
    else the first of its row's sources. What a page saved by hand is logged under, and what the fetch list reads."""
    return step["locator_source_id"] or (json.loads(step["sources_json"] or "[]") or [None])[0]

def latest_answer(cx, step, source_id=None):
    """The step's latest run the source answered: (outcome, executed_at, fields as logged), or None. A reopen's own row is
    bookkeeping, not a run, and a run logged error is a source that did not answer (a timeout, a challenge, a reset
    connection): both are looked past. With a source named, that source's own rows alone (search_log.source_id): a step whose
    sources have two connectors is answered by each on its own; with none, the latest answer whatever its source."""
    for q, note, outcome, sid, at in cx.execute("SELECT query_json, notes, outcome, source_id, executed_at FROM search_log WHERE plan_step_id=? ORDER BY executed_at DESC, id DESC", (step["id"],)):
        if (note or "").startswith(REOPENED) or outcome == "error": continue
        if source_id and sid != source_id: continue
        return outcome, at, json.loads(q or "{}")
    return None

def ran_unchanged(cx, step, rendered, source_id=None):
    """Whether the step's latest run the source answered (latest_answer) asked these very fields: nothing has changed on the step
    since, so running it again at that source would be the same query blind. A found or none run before an error on the same
    fields still closes the step at that source; a source whose runs are all errors is asked again. Read per source: one
    connector's none run on the step's fields does not close the step at another source, which is asked until it answers."""
    a = latest_answer(cx, step, source_id)
    return a is not None and same_fields(rendered, a[2])

HOUSEHOLD = "the household's record, accepted onto "     # the note prefix of a run written when a household record's persona is accepted onto a person

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
        if cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json LIKE ?", (sid, f'%"{sha}"%')).fetchone(): continue
        log(cx, tree_id, by, step_id=sid, outcome="found", artifacts=[sha], note=f"{HOUSEHOLD}{name}", query=rendered_query(qj, rj))
        out.append(sid)
    return out

def release_household(cx, tree_id, person_id, sha, by):
    """The steps hold_household logged found with this record for this person are planned again (reopen) once the record's
    persona is rejected for them: the record no longer holds their row. Returns the step ids reopened."""
    out = []
    for sid, in cx.execute("""SELECT DISTINCT l.plan_step_id FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id
                              WHERE sp.person_id=? AND sp.status='done' AND l.outcome='found' AND l.notes LIKE ? AND l.artifacts_json LIKE ?
                              AND NOT EXISTS (SELECT 1 FROM search_log r WHERE r.plan_step_id=l.plan_step_id AND r.notes LIKE ? AND r.id > l.id)""",
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
    last = next((sid for sid, n in cx.execute("SELECT source_id, notes FROM search_log WHERE plan_step_id=? ORDER BY executed_at DESC, id DESC", (step_id,))
                 if not (n or "").startswith(REOPENED)), None)
    return log(cx, tree_id, by, step_id=step_id, source_id=last, outcome="none", note=f"{REOPENED}{note}")

def log(cx, tree_id, by, step_id=None, question_id=None, source_id=None, outcome="none", artifacts=None, note=None, query=None, done=True):
    """One run of a step (or of a question with no step) into search_log; a found run marks the step done unless done is
    False (a fetch step answered at a source other than its holder: the pages found are held, the cited record is not)."""
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
    """Close a question as dismissed by a person; the planner never reopens it."""
    ts = now()
    if not cx.execute("SELECT 1 FROM research_question WHERE id=? AND tree_id=? AND status='open'", (question_id, tree_id)).fetchone(): raise SystemExit("no open question with that id in this tree")
    cx.execute("UPDATE research_question SET status='closed', closed_reason='dismissed', closed_at=? WHERE id=?", (ts, question_id))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "research_question", question_id, dumps({"status": "closed", "closed_reason": "dismissed", "note": note or None})))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--step"); ap.add_argument("--question"); ap.add_argument("--source"); ap.add_argument("--outcome", choices=["found", "none", "blocked", "error"])
    ap.add_argument("--artifact", action="append"); ap.add_argument("--note"); ap.add_argument("--query"); ap.add_argument("--list"); ap.add_argument("--dismiss"); ap.add_argument("--reopen", help="a step marked done in error: planned again, with --note saying why"); ap.add_argument("--tree")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); tree_id, slug = resolve_tree(cx, a.tree)
    if a.list:
        cat = Catalog(cx, tree_id); pid = cat.find_person(a.list)
        print(f"{'step id':26}  {'kind':6} {'mode':17} {'status':8} {'row':34} {'locator':20} runs (outcome@date)  -- rationale")
        for row in cx.execute("""SELECT sp.id, sp.kind, sp.mode, sp.status, sp.row_key, sp.locator_value, sp.rationale,
                                        (SELECT GROUP_CONCAT(l.outcome || '@' || substr(l.executed_at,1,10), ' ') FROM search_log l WHERE l.plan_step_id=sp.id)
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
