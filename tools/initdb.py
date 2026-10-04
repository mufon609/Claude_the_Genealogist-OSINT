#!/usr/bin/env python3
"""Create the catalog database and seed reference tables.

usage: tools/initdb.py [--db catalog/tree.db] [--force]
       tools/initdb.py --sync-sources [--db catalog/tree.db]
       tools/initdb.py --sync-event-types [--db catalog/tree.db]
       tools/initdb.py --migrate [--db catalog/tree.db]

Applies schema/catalog.sql, schema/seed_event_type.sql, schema/sqlite_extras.sql,
then seeds `source` from data/data-sources.csv, a `human` extractor, and the
local storage target. --sync-sources rewrites an existing catalog's source rows
from the CSV (the registry is reference data) and each collection's trust tier from
the registry's ServedAs column, and touches nothing else. --migrate
brings an existing catalog's own structure up to schema/catalog.sql's current
version, one column or index at a time, and runs any one-time data correction a
later version needs (a row-by-row fix of what an older version wrote, never a decision); each schema
version this catalog lacks runs once and is recorded in schema_migration. Stdlib only.
"""
import argparse, csv, datetime as dt, json, os, sqlite3, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, SCHEMA_VERSION, archive_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def requery_questions(cx: sqlite3.Connection) -> None:
    """Every research_question row's key recomputed from its own detail_json with plan.q_key, open and closed alike: the
    catalog's one-time correction of rows an older, truncating q_key wrote."""
    from plan import q_key
    for rid, detail in cx.execute("SELECT id, detail_json FROM research_question").fetchall():
        cx.execute("UPDATE research_question SET q_key=? WHERE id=?", (q_key(json.loads(detail)), rid))

def rebuild_table(cx: sqlite3.Connection, table: str) -> None:
    """A table built again as schema/catalog.sql now defines it, for a CHECK the schema widens. SQLite changes a CHECK only by
    building the table again: the table as schema/catalog.sql defines it is created beside the old, every row copied across
    unchanged, the old dropped and the new renamed, its indexes made again, with foreign keys off for the swap and every
    reference checked after it."""
    import re
    sql = read("schema/catalog.sql")
    ddl = re.search(rf"CREATE TABLE {table} \(.*?\n\);", sql, re.S).group(0)
    indexes = re.findall(rf"^CREATE INDEX [^\n]*? ON {table}\([^\n]*;$", sql, re.M)
    cx.commit(); cx.execute("PRAGMA foreign_keys=OFF")
    cx.execute(ddl.replace(f"CREATE TABLE {table} (", f"CREATE TABLE {table}_rebuilt (", 1))
    cols = ", ".join(r[1] for r in cx.execute(f"PRAGMA table_info({table})"))
    cx.execute(f"INSERT INTO {table}_rebuilt ({cols}) SELECT {cols} FROM {table}")
    cx.execute(f"DROP TABLE {table}")
    cx.execute(f"ALTER TABLE {table}_rebuilt RENAME TO {table}")
    for index in indexes: cx.execute(index)
    bad = cx.execute("PRAGMA foreign_key_check").fetchall()
    if bad: raise SystemExit(f"{table} rebuilt with {len(bad)} broken reference(s); nothing committed")
    cx.commit(); cx.execute("PRAGMA foreign_keys=ON")

def rebuild_questions(cx: sqlite3.Connection) -> None:
    """research_question built again (rebuild_table) for a CHECK it widens: closed_reason accepting 'resolved', a conflict the
    owner closed naming the value kept (tools/conclude.py resolve), and kind accepting 'identity', a link or a statement
    beyond the limits of one life (Catalog.beyond_life)."""
    rebuild_table(cx, "research_question")

def unread_runs(cx: sqlite3.Connection) -> None:
    """search_log accepts the outcome 'unread' (rebuild_table), and the catalog's one-time correction of the runs an older
    attach logged found for a web page no parser reads: a found run whose every artifact is a record whose every extraction
    is the failed one for a file no parser claims (log_search.unread_record; an image, a record a parser or the model or a
    person read, a file no parser was asked to read, stays found) is an unread run, its note beginning with
    log_search.UNREAD, one audit row per run under the migration's own actor, naming the step, the person, the holder and
    the page, the run as it stood in diff_json. Refused, nothing written, when such a run sits on a step standing done: the
    run may have closed it, and whether the step stands is the owner's, so each such step is named."""
    from log_search import UNREAD, unread_record
    actor, ts = "migration:0.7.8", now()
    runs = []
    live = " AND superseded_by IS NULL" if "superseded_by" in [r[1] for r in cx.execute("PRAGMA table_info(search_log)")] else ""   # a run a later row restates is not read, and stays as it is
    for lid, tree, step, shas, source, notes in cx.execute(f"""SELECT id, tree_id, plan_step_id, artifacts_json, source_id, notes FROM search_log
                                                               WHERE outcome='found' AND artifacts_json IS NOT NULL{live} ORDER BY executed_at, id""").fetchall():
        shas = json.loads(shas)
        if shas and all(unread_record(cx, s) for s in shas): runs.append((lid, tree, step, shas, source, notes))
    done = [f"step {step} ({cx.execute('SELECT p.display_name FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=?', (step,)).fetchone()[0]}, "
            f"{source}) stands done with run {lid} on the unread page {', '.join(s[:12] for s in shas)}" for lid, _, step, shas, source, _ in runs
            if step and cx.execute("SELECT status FROM search_plan WHERE id=?", (step,)).fetchone()[0] == "done"]
    if done: raise SystemExit("0.7.8 refused, nothing written: a step stands done with a run to correct: " + "; ".join(done))
    rebuild_table(cx, "search_log")
    for lid, tree, step, shas, source, notes in runs:
        now_notes = UNREAD + (f"; {notes}" if notes else "")
        cx.execute("UPDATE search_log SET outcome='unread', notes=? WHERE id=?", (now_notes, lid))
        person = cx.execute("SELECT p.display_name FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=?", (step,)).fetchone() if step else None
        cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                   (ulid(), tree, ts, actor, "update", "search_log", lid,
                    json.dumps({"was": {"outcome": "found", "notes": notes}, "now": {"outcome": "unread", "notes": now_notes}, "step": step, "person": person[0] if person else None,
                                "holder": source, "artifacts": shas, "why": "a web page no parser reads is held, not found: nothing a program knows was read from it"})))

def unspread_links(cx: sqlite3.Connection) -> None:
    """The catalog's one-time correction of the person_persona rows an older decision spread to another entry of its page:
    it wrote its link on every persona of the decided persona's name and role on the record, another row of the same name
    among them, and an older re-read moved a link to the first new persona of that name and role (a decision reaches its own
    entry of the page alone, catalog.persona_key). A spread row carries the decision's proposal, belongs to the decided
    person, and its persona is another entry of the page than the decided persona: it is removed, never having been anyone's
    decision. The decided persona and the same entry on the page's other readings keep theirs, and a listed relative's
    undecided trace (conclude.link_family), being another person's, stays. A spread row whose persona has a decision of its
    own for that person (a page that named the person twice, each decided) is that decision's link and stays, as that
    decision left it: its status, proposal and decider. Refused, nothing written, when anything accepted on the row's person
    rests on a row it would remove: a statement of its persona's facts, a family link written from it or from a persona the
    record relates to it, a name alias from it. One audit row per row removed or restored, the row as it stood in
    diff_json, under the migration's own actor."""
    from catalog import page_entries
    actor, ts = "migration:0.7.5", now()
    keys = {}
    def key(sha, pid):
        if sha not in keys: keys[sha] = {p: k for p, _, _, _, k in page_entries(cx, sha)}
        return keys[sha][pid]
    merged = lambda pids: set(pids) | {m for p in pids for m, in cx.execute("SELECT merged_into FROM person WHERE id=? AND merged_into IS NOT NULL", (p,))}
    remove, restore = [], []
    for person, persona, status, prop, by, at, sha, src, payload_person, tree in cx.execute("""
            SELECT pp.person_id, pp.persona_id, pp.status, pp.proposal_id, pp.decided_by, pp.decided_at, pe.artifact_sha256, src.id, json_extract(pr.payload_json,'$.person_id'), p.tree_id
            FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN person p ON p.id=pp.person_id JOIN proposal pr ON pr.id=pp.proposal_id
            JOIN persona src ON src.id=json_extract(pr.payload_json,'$.persona_id')
            WHERE pr.kind IN ('persona_match','new_person') AND src.artifact_sha256=pe.artifact_sha256 AND src.id<>pe.id ORDER BY pe.artifact_sha256, pp.persona_id""").fetchall():
        decided = merged({payload_person} - {None} | {p for p, in cx.execute("SELECT person_id FROM person_persona WHERE persona_id=? AND proposal_id=?", (src, prop))})
        if person not in decided or key(sha, persona) == key(sha, src): continue
        row = {"person_id": person, "persona_id": persona, "status": status, "proposal_id": prop, "decided_by": by, "decided_at": at}
        entry = [p for p, k in keys[sha].items() if k == key(sha, persona)]
        own = cx.execute(f"""SELECT pr.id, pr.status, pr.decided_by, pr.decided_at FROM proposal pr
                             WHERE pr.kind IN ('persona_match','new_person') AND json_extract(pr.payload_json,'$.persona_id') IN ({','.join('?' * len(entry))})
                             AND json_extract(pr.payload_json,'$.person_id') IN (SELECT ? UNION SELECT id FROM person WHERE merged_into=?)
                             AND EXISTS (SELECT 1 FROM audit_log l WHERE l.entity_kind='proposal' AND l.entity_id=pr.id AND l.action IN ('accept','reject') AND json_extract(l.diff_json,'$.persona') IS NOT NULL)
                             ORDER BY coalesce(pr.decided_at, pr.created_at) DESC, pr.id DESC LIMIT 1""", (*entry, person, person)).fetchone()   # a decision conclude.decide made on this entry, by its own audit row
        if own: restore.append((tree, row, src, {"status": own[1], "proposal_id": own[0], "decided_by": own[2], "decided_at": own[3]}))
        else: remove.append((tree, row, src, sha))
    resting = []
    for tree, row, src, sha in remove:                     # what is accepted on the row's person, written from the row's persona or through it
        person, persona = row["person_id"], row["persona_id"]
        theirs = """((a.subject_kind='person' AND a.subject_id=:person)
                     OR (a.subject_kind='event' AND a.subject_id IN (SELECT ep.event_id FROM event_participant ep WHERE ep.person_id=:person
                         OR ep.family_id IN (SELECT family_id FROM family_member WHERE person_id=:person)))
                     OR (a.subject_kind='family_member' AND (json_extract(a.subject_id,'$[1]')=:person
                         OR EXISTS (SELECT 1 FROM family_member fm WHERE fm.family_id=json_extract(a.subject_id,'$[0]') AND fm.person_id=:person))))"""
        args = {"person": person, "persona": persona, "sha": sha}
        resting += [f"assertion {a} from {persona}'s own fact" for a, in cx.execute(f"""SELECT a.id FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id
                    WHERE pf.persona_id=:persona AND a.status='accepted' AND {theirs}""", args)]
        resting += [f"family link {a} written from {persona}, or through it" for a, in cx.execute(f"""SELECT a.id FROM assertion a WHERE a.status='accepted' AND a.artifact_sha256=:sha
                    AND a.persona_id IN (SELECT :persona UNION SELECT persona_id FROM persona_relation WHERE related_persona_id=:persona UNION SELECT related_persona_id FROM persona_relation WHERE persona_id=:persona)
                    AND {theirs}""", args)]
        resting += [f"alias {a} from {persona}'s name" for a, in cx.execute("""SELECT al.id FROM alias al JOIN persona_fact pf ON pf.id=al.source_persona_fact_id
                    WHERE pf.persona_id=:persona AND al.status='accepted' AND al.entity_kind='person' AND al.entity_id=:person""", args)]
    if resting: raise SystemExit("0.7.5 refused, nothing written: accepted evidence rests on a link it would remove: " + "; ".join(resting))
    for tree, row, src, now_ in restore:
        cx.execute("UPDATE person_persona SET status=?, proposal_id=?, decided_by=?, decided_at=? WHERE person_id=? AND persona_id=?",
                   (now_["status"], now_["proposal_id"], now_["decided_by"], now_["decided_at"], row["person_id"], row["persona_id"]))
        cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                   (ulid(), tree, ts, actor, "update", "person_persona", json.dumps([row["person_id"], row["persona_id"]]),
                    json.dumps({"was": row, "now": now_, "spread_from": src, "why": "a decision on another entry of the page had written over this entry's own decision"})))
    for tree, row, src, _ in remove:
        cx.execute("DELETE FROM person_persona WHERE person_id=? AND persona_id=?", (row["person_id"], row["persona_id"]))
        cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                   (ulid(), tree, ts, actor, "delete", "person_persona", json.dumps([row["person_id"], row["persona_id"]]),
                    json.dumps({"removed": row, "spread_from": src, "why": "a decision on another entry of the page, spread by name and role; never a decision of its own"})))

def same_records(cx: sqlite3.Connection) -> None:
    """The same_record table, insert-only like the rest of the evidence layer, and code's joins of the copies the archive
    already holds written once (conclude.join_copies, the joins every reading writes from now on), under the migration's own
    actor. Nothing decided changes: a decision on one copy reaches the others when tools/conclude.py reconsider carries it."""
    from conclude import join_copies
    ddl = read("schema/catalog.sql"); extras = read("schema/sqlite_extras.sql")
    script = ddl[ddl.index("CREATE TABLE same_record"):ddl.index("CREATE INDEX ix_same_record_b")] + "CREATE INDEX ix_same_record_b ON same_record(b_sha256, b_entry);\n" + \
             extras[extras.index("CREATE TRIGGER trg_same_record_no_update"):]
    for word in ("TABLE", "INDEX", "TRIGGER"): script = script.replace(f"CREATE {word} ", f"CREATE {word} IF NOT EXISTS ")   # a catalog born with the table, replaying its migrations, keeps it
    cx.executescript(script)
    for sha, in cx.execute("SELECT DISTINCT artifact_sha256 FROM extraction WHERE status<>'failed' AND superseded_by IS NULL ORDER BY artifact_sha256").fetchall():
        join_copies(cx, sha, "migration:0.7.9")

def fold_events(cx: sqlite3.Connection) -> None:
    """The catalog's one-time fold of the events an older import and older decisions wrote apart (docs/RESEARCH-WORKFLOW.md
    §5–7, one statement, one event): every listed person's events of one type, and every family's, that are one event
    (catalog.same_event: places agreeing or one absent, and the type held once in a life or the dates one) folded into one by
    conclude.fold, as a merge folds them and the import and every decision now keep them: the statements and notes moved onto
    the kept event as they are, a record fact's second statement left where it was, the folded event out of the owner's
    events with its row kept. One audit row per event folded, under the migration's own actor, naming the owner, the type,
    both events with their values, what moved, what stayed and what the kept event took. Refused, nothing written, when a
    fold would set aside a value the owner resolved: two events of one group each carrying the owner's word (conclude.fold_plan)."""
    from conclude import fold, fold_plan
    actor = "migration:0.7.6"
    owners = [(tree, ("person", p)) for tree, p in cx.execute("SELECT tree_id, id FROM person WHERE merged_into IS NULL ORDER BY id").fetchall()] + \
             [(tree, ("family", f)) for tree, f in cx.execute("""SELECT DISTINCT e.tree_id, ep.family_id FROM event_participant ep JOIN event e ON e.id=ep.event_id
                                                                 WHERE ep.family_id IS NOT NULL ORDER BY ep.family_id""").fetchall()]
    plans = [(tree, owner, fold_plan(cx, tree, owner)) for tree, owner in owners]
    refused = [g["refused"] for _, _, groups in plans for g in groups if g["refused"]]
    if refused: raise SystemExit("0.7.6 refused, nothing written: " + "; ".join(refused))
    for tree, owner, groups in plans:
        if groups: fold(cx, tree, owner, actor=actor)

def person_decisions(cx: sqlite3.Connection) -> list:
    """A person's own decisions on statements (docs/RESEARCH-WORKFLOW.md §5–7) as the audit log records them, the latest on
    each statement last: (assertion id, status, actor, at, kind). A key fact decided (tools/conclude.py fact): the statements
    it vouched; otherwise the ones it stamped, every one behind the fact that already held an accept it repeats, and for a
    reject or an undecided every one behind the fact that existed then. One statement decided (tools/conclude.py assertion).
    A session's hand decision on named statements (set_back undecided, restored accepted). A card rejected by a person: the
    statements the rejection stamped. The owner's word on a link or a divorce (a vouched statement no fact decision names),
    at its writing. A person is user:<name> or agent:<session> for user:<name>."""
    from facts import fact_subjects
    person = lambda actor: actor.startswith("user:") or (actor.startswith("agent:") and " for user:" in actor)
    def born(ulid_):                                                  # when a statement was written, from its own id
        ms = 0
        for ch in ulid_[:10]: ms = ms * 32 + _B32.index(ch)
        return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for r in cx.execute("SELECT actor, at, entity_id, diff_json FROM audit_log WHERE entity_kind='person' ORDER BY id").fetchall():
        actor, at, pid, d = r[0], r[1], r[2], json.loads(r[3] or "{}")
        if not person(actor) or not isinstance(d, dict): continue
        if d.get("fact"):
            if d.get("vouched"): out += [(a, d["status"], actor, at, "fact") for a in d["vouched"]]; continue
            for kind, sid in fact_subjects(cx, pid, d["fact"]):
                for a, status, by, by_at in cx.execute("SELECT id, status, asserted_by, asserted_at FROM assertion WHERE subject_kind=? AND subject_id=?", (kind, sid)).fetchall():
                    if (by, by_at) == (actor, at) or (born(a) <= at and (d["status"] != "accepted" or (status == "accepted" and by_at < at))): out.append((a, d["status"], actor, at, "fact"))
        out += [(a, "undecided", actor, at, "set back") for a in d.get("set_back", [])] + [(a, "accepted", actor, at, "restored") for a in d.get("restored", [])]
    for actor, at, a, d in cx.execute("SELECT actor, at, entity_id, diff_json FROM audit_log WHERE entity_kind='assertion' AND json_valid(diff_json) AND json_extract(diff_json,'$.now') IS NOT NULL ORDER BY id").fetchall():
        if person(actor): out.append((a, json.loads(d)["now"], actor, at, "assertion"))
    for actor, at, prop in cx.execute("""SELECT actor, at, entity_id FROM audit_log WHERE entity_kind='proposal' AND action='reject' AND json_valid(diff_json)
                                         AND json_extract(diff_json,'$.kind') IS NOT NULL AND json_extract(diff_json,'$.closed') IS NULL ORDER BY id""").fetchall():
        if person(actor): out += [(a, "rejected", actor, at, "card rejected") for a, in cx.execute("""SELECT id FROM assertion WHERE json_valid(notes) AND json_extract(notes,'$.proposal')=?
                                                                                                     AND asserted_by=? AND asserted_at=?""", (prop, actor, at))]
    named = {x[0] for x in out}
    out += [(a, status, by, at, "owner's word") for a, status, by, at in cx.execute("SELECT id, status, asserted_by, asserted_at FROM assertion WHERE json_valid(notes) AND json_extract(notes,'$.vouched')").fetchall()
            if a not in named]
    return sorted(out, key=lambda x: x[3])

def person_decided(cx: sqlite3.Connection) -> None:
    """assertion.person_decided, and the catalog's one-time record of the statements whose status a person's own decision on
    them set (person_decisions): each statement whose status is still the one its latest person decision gave it, with no
    later stamp but a person decision's, is marked; its asserted_by and asserted_at become that decision's when they name
    no person decision on it (an accept the decision repeated without stamping it). One audit row per statement marked,
    under the migration's own actor. A statement a machine has changed since keeps its status, unmarked: listing those is
    the owner's review, not a correction. Nothing decided changes."""
    if "person_decided" not in [r[1] for r in cx.execute("PRAGMA table_info(assertion)")]:
        cx.execute("ALTER TABLE assertion ADD COLUMN person_decided BOOLEAN NOT NULL DEFAULT FALSE")
    decisions = person_decisions(cx); stamps = {(a, actor, at) for a, _, actor, at, _ in decisions}
    latest = {a: (status, actor, at, kind) for a, status, actor, at, kind in decisions}
    ts = now()
    for a, (status, actor, at, kind) in latest.items():
        row = cx.execute("SELECT tree_id, status, asserted_by, asserted_at FROM assertion WHERE id=?", (a,)).fetchone()
        if not row or row[1] != status: continue
        mine = (a, row[2], row[3]) in stamps
        if row[3] > at and not mine: continue                            # set since by something other than a person's decision on it
        if mine: cx.execute("UPDATE assertion SET person_decided=TRUE WHERE id=?", (a,))
        else: cx.execute("UPDATE assertion SET person_decided=TRUE, asserted_by=?, asserted_at=? WHERE id=?", (actor, at, a))
        cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                   (ulid(), row[0], ts, "migration:0.8.0", "update", "assertion", a,
                    json.dumps({"person_decided": True, "decision": {"kind": kind, "by": actor, "at": at, "status": status},
                                **({} if mine else {"stamp": {"was": [row[2], row[3]], "now": [actor, at]}})})))

INSERT_ONLY = ("artifact_locator", "tombstone", "extractor", "extraction", "persona_relation", "search_log", "audit_log")   # the tables 0.8.1 makes insert-only

def insert_only(cx: sqlite3.Connection) -> None:
    """search_log.superseded_by, and schema/sqlite_extras.sql's insert-only triggers on the archive's locators and tombstones, the
    extractors, extractions and relations of the evidence, the research log and the audit trail (docs/DATA-ARCHITECTURE.md §1):
    every UPDATE refused but the write-once superseded_by on extraction and search_log, every DELETE refused. No row changes."""
    import re
    if "superseded_by" not in [r[1] for r in cx.execute("PRAGMA table_info(search_log)")]:   # a catalog whose search_log an earlier rebuild made from today's DDL has it
        cx.execute("ALTER TABLE search_log ADD COLUMN superseded_by TEXT REFERENCES search_log(id)")
    extras = read("schema/sqlite_extras.sql")
    for table in INSERT_ONLY:
        for trigger in re.findall(rf"^CREATE TRIGGER trg_{table}_\w+ BEFORE (?:UPDATE|DELETE).*?^END;", extras, re.S | re.M):
            cx.execute(trigger.replace("CREATE TRIGGER ", "CREATE TRIGGER IF NOT EXISTS ", 1))

# One entry per schema version added after the catalog's first release: (version, note, statements), a statement either
# SQL or a callable(cx) for a correction SQL alone cannot make.
# Applied in order to a catalog whose schema_migration lacks that version; already-applied versions are skipped.
MIGRATIONS = [
    ("0.7.2", "person.merged_into: tools/conclude.py merge points a duplicate at the person it duplicates",
     ["ALTER TABLE person ADD COLUMN merged_into TEXT REFERENCES person(id)",
      "CREATE INDEX ix_person_merged_into ON person(merged_into) WHERE merged_into IS NOT NULL"]),
    ("0.7.3", "research_question.q_key recomputed from detail_json with plan.q_key, dropping the 120-character truncation an older key wrote",
     [requery_questions]),
    ("0.7.4", "research_question.closed_reason accepts 'resolved': a conflict the owner closes with a written reason naming the value kept",
     [rebuild_questions]),
    ("0.7.5", "person_persona: the links a decision spread to another row of the same name and role on its page removed; a decision reaches only its own entry of the page",
     [unspread_links]),
    ("0.7.6", "event: a person's or a family's events of one type that are one event folded into one; one statement, one event",
     [fold_events]),
    ("0.7.7", "research_question.kind accepts 'identity': a family link or an accepted statement beyond the limits of one life",
     [rebuild_questions]),
    ("0.7.8", "search_log.outcome accepts 'unread': a web page archived that no parser reads is held on its step's log, the step stays planned; the runs an older attach logged found for such a page are corrected",
     [unread_runs]),
    ("0.7.9", "same_record: two archived copies of one record joined on what they share of the record itself, code's joins of the copies already held written once; tools/conclude.py reconsider then carries each decision to every copy",
     [same_records]),
    ("0.8.0", "assertion.person_decided: a statement whose status a person's own decision on it set, which no acceptance of its record, re-read, carry or withdrawal changes; the statements the audit log shows a person decided marked",
     [person_decided]),
    ("0.8.1", "insert-only: artifact_locator, tombstone, extractor, extraction, persona_relation, search_log and audit_log take no UPDATE but a write-once superseded_by on extraction and search_log, and no DELETE; search_log.superseded_by names the row restating a run read again or carried by a merge",
     [insert_only]),
]

def migrate(cx: sqlite3.Connection) -> list:
    """Every migration this catalog's schema_migration lacks, applied in order. Returns the versions applied."""
    have = {v for v, in cx.execute("SELECT version FROM schema_migration")}
    applied = []
    for version, note, statements in MIGRATIONS:
        if version in have: continue
        for stmt in statements: stmt(cx) if callable(stmt) else cx.execute(stmt)
        cx.execute("INSERT INTO schema_migration (version, applied_at, notes) VALUES (?,?,?)", (version, now(), note))
        applied.append(version)
    return applied

def ulid() -> str:
    """Crockford-base32 ULID: 48-bit ms timestamp + 80 random bits."""
    n = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    out = []
    for _ in range(26):
        out.append(_B32[n & 31]); n >>= 5
    return "".join(reversed(out))

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()

def seed_sources(cx: sqlite3.Connection) -> int:
    """The registry rows from data/data-sources.csv into source: inserted on a fresh catalog, replaced on --sync-sources."""
    path = os.path.join(ROOT, "data", "data-sources.csv")
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ts = now()
    cx.executemany(
        """INSERT INTO source (id, category, data_type, name, provider, cost, access, url,
                               coverage, terms, trust_tier, priority, status, connector,
                               record_release_rule, notes, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET category=excluded.category, data_type=excluded.data_type, name=excluded.name, provider=excluded.provider,
             cost=excluded.cost, access=excluded.access, url=excluded.url, coverage=excluded.coverage, terms=excluded.terms, trust_tier=excluded.trust_tier,
             priority=excluded.priority, status=excluded.status, connector=excluded.connector, record_release_rule=excluded.record_release_rule,
             notes=excluded.notes, updated_at=excluded.updated_at""",
        [(r["ID"], r["Category"], r["DataType"], r["Source"], r["Provider"], r["Cost"],
          r["Access"], r["URL"], r["Coverage"], r["Terms"], r["TrustTier"], r["Priority"],
          r["Status"], r.get("Connector") or None, r.get("RecordRelease") or None, r["Notes"], ts) for r in rows])
    return len(rows)

def sync_collection_tiers(cx: sqlite3.Connection) -> int:
    """Every collection's trust_tier from the data (catalog.collection_tier: the registry row whose ServedAs names the
    collection's holder and its name's words), cleared where the data gives none, so the column says only what the data
    says. Returns how many collections changed."""
    from catalog import collection_tier, served_as
    served, n = served_as(), 0
    for cid, sid, name, tier in cx.execute("SELECT id, source_id, name, trust_tier FROM collection").fetchall():
        t = collection_tier(sid, name, served)
        if t != tier: cx.execute("UPDATE collection SET trust_tier=? WHERE id=?", (t, cid)); n += 1
    return n

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--force", action="store_true", help="overwrite an existing db")
    ap.add_argument("--sync-sources", action="store_true", help="bring an existing catalog's source rows and collection tiers up to data/data-sources.csv; nothing else changes")
    ap.add_argument("--sync-event-types", action="store_true", help="add the event types schema/seed_event_type.sql has that an existing catalog lacks; nothing else changes")
    ap.add_argument("--migrate", action="store_true", help="bring an existing catalog's structure up to schema/catalog.sql's current version; nothing decided changes")
    a = ap.parse_args()

    if a.sync_sources:
        cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
        n = seed_sources(cx); t = sync_collection_tiers(cx); cx.commit()
        print(f"{a.db}: {n} source rows in step with data/data-sources.csv; {t} collection tier(s) changed"); return 0
    if a.sync_event_types:
        cx = sqlite3.connect(a.db)
        before = cx.execute("SELECT COUNT(*) FROM event_type").fetchone()[0]
        cx.executescript(read("schema/seed_event_type.sql").replace("INSERT INTO event_type", "INSERT OR IGNORE INTO event_type")); cx.commit()
        print(f"{a.db}: {cx.execute('SELECT COUNT(*) FROM event_type').fetchone()[0] - before} event type(s) added"); return 0
    if a.migrate:
        cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
        applied = migrate(cx); cx.commit()
        print(f"{a.db}: schema {', '.join(applied) if applied else 'already current'}"); return 0
    if os.path.exists(a.db):
        if not a.force:
            print(f"refusing to overwrite {a.db} (use --force)", file=sys.stderr); return 2
        os.remove(a.db)
    os.makedirs(os.path.dirname(a.db), exist_ok=True)

    cx = sqlite3.connect(a.db)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA foreign_keys=ON")
    cx.executescript(read("schema/catalog.sql"))
    cx.executescript(read("schema/seed_event_type.sql"))
    cx.executescript(read("schema/sqlite_extras.sql"))

    n_src = seed_sources(cx)
    ts = now()
    cx.execute("INSERT INTO extractor (id, kind, name, version, created_at) VALUES (?,?,?,?,?)",
               (ulid(), "human", "manual", "1", ts))
    cx.execute("""INSERT INTO storage_target (name, kind, uri, is_master, object_lock, enabled, notes)
                  VALUES ('local','local',?,1,0,1,'primary on-disk archive')""",
               ("file://" + archive_dir(),))
    cx.execute("""INSERT INTO storage_target (name, kind, uri, is_master, object_lock, enabled, notes)
                  VALUES ('s3-master','s3','s3://CHANGE-ME/tree/bags',0,1,0,
                          'disabled until project is finished; Versioning + Object Lock compliance, lifecycle to Deep Archive @30d')""")
    for version, note, _ in MIGRATIONS:                 # schema/catalog.sql already carries every migration's structure: recorded applied, never re-run, so a fresh catalog is never born behind
        cx.execute("INSERT INTO schema_migration (version, applied_at, notes) VALUES (?,?,?)", (version, ts, note))
    if SCHEMA_VERSION not in {v for v, _, _ in MIGRATIONS}:
        cx.execute("INSERT INTO schema_migration (version, applied_at, notes) VALUES (?,?,?)", (SCHEMA_VERSION, ts, "initial"))
    cx.commit()

    n_tables = cx.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    n_views  = cx.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'").fetchone()[0]
    n_types  = cx.execute("SELECT COUNT(*) FROM event_type").fetchone()[0]
    print(f"{a.db}\n  schema {SCHEMA_VERSION}: {n_tables} tables, {n_views} views\n"
          f"  seeded: {n_src} sources, {n_types} event types, 2 storage targets\n"
          f"  no trees yet: create one with tools/tree.py create <slug> --name '...'")
    cx.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
