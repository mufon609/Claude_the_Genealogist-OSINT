#!/usr/bin/env python3
"""Create the catalog database and seed reference tables.

usage: tools/initdb.py [--db catalog/tree.db] [--force]
       tools/initdb.py --sync-sources [--db catalog/tree.db]
       tools/initdb.py --sync-event-types [--db catalog/tree.db]

Applies schema/catalog.sql, schema/seed_event_type.sql, schema/sqlite_extras.sql,
then seeds `source` from data/data-sources.csv, a `human` extractor, and the
local storage target. --sync-sources rewrites an existing catalog's source rows
from the CSV (the registry is reference data) and touches nothing else. Stdlib only.
"""
import argparse, csv, datetime as dt, os, sqlite3, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import archive_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_VERSION = "0.7.1"
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

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

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    ap.add_argument("--force", action="store_true", help="overwrite an existing db")
    ap.add_argument("--sync-sources", action="store_true", help="bring an existing catalog's source rows up to data/data-sources.csv; nothing else changes")
    ap.add_argument("--sync-event-types", action="store_true", help="add the event types schema/seed_event_type.sql has that an existing catalog lacks; nothing else changes")
    a = ap.parse_args()

    if a.sync_sources:
        cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
        n = seed_sources(cx); cx.commit(); print(f"{a.db}: {n} source rows in step with data/data-sources.csv"); return 0
    if a.sync_event_types:
        cx = sqlite3.connect(a.db)
        before = cx.execute("SELECT COUNT(*) FROM event_type").fetchone()[0]
        cx.executescript(read("schema/seed_event_type.sql").replace("INSERT INTO event_type", "INSERT OR IGNORE INTO event_type")); cx.commit()
        print(f"{a.db}: {cx.execute('SELECT COUNT(*) FROM event_type').fetchone()[0] - before} event type(s) added"); return 0
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
    cx.execute("INSERT INTO schema_migration (version, applied_at, notes) VALUES (?,?,?)",
               (SCHEMA_VERSION, ts, "initial"))
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
