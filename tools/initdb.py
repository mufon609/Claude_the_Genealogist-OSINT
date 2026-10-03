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
from treelib import SCHEMA_VERSION, archive_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def requery_questions(cx: sqlite3.Connection) -> None:
    """Every research_question row's key recomputed from its own detail_json with plan.q_key, open and closed alike: the
    catalog's one-time correction of rows an older, truncating q_key wrote."""
    from plan import q_key
    for rid, detail in cx.execute("SELECT id, detail_json FROM research_question").fetchall():
        cx.execute("UPDATE research_question SET q_key=? WHERE id=?", (q_key(json.loads(detail)), rid))

def allow_resolved(cx: sqlite3.Connection) -> None:
    """research_question.closed_reason accepts 'resolved', a conflict the owner closed naming the value kept
    (tools/conclude.py resolve). SQLite changes a CHECK only by building the table again: the table as schema/catalog.sql
    now defines it is created beside the old, every row copied across unchanged, the old dropped and the new renamed, with
    foreign keys off for the swap and every reference checked after it."""
    import re
    ddl = re.search(r"CREATE TABLE research_question \(.*?\n\);", read("schema/catalog.sql"), re.S).group(0)
    cx.commit(); cx.execute("PRAGMA foreign_keys=OFF")
    cx.execute(ddl.replace("CREATE TABLE research_question (", "CREATE TABLE research_question_rebuilt (", 1))
    cols = ", ".join(r[1] for r in cx.execute("PRAGMA table_info(research_question)"))
    cx.execute(f"INSERT INTO research_question_rebuilt ({cols}) SELECT {cols} FROM research_question")
    cx.execute("DROP TABLE research_question")
    cx.execute("ALTER TABLE research_question_rebuilt RENAME TO research_question")
    cx.execute("CREATE INDEX ix_question_person ON research_question(subject_person_id, status)")
    bad = cx.execute("PRAGMA foreign_key_check").fetchall()
    if bad: raise SystemExit(f"research_question rebuilt with {len(bad)} broken reference(s); nothing committed")
    cx.commit(); cx.execute("PRAGMA foreign_keys=ON")

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
     [allow_resolved]),
    ("0.7.5", "person_persona: the links a decision spread to another row of the same name and role on its page removed; a decision reaches only its own entry of the page",
     [unspread_links]),
    ("0.7.6", "event: a person's or a family's events of one type that are one event folded into one; one statement, one event",
     [fold_events]),
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
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
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
