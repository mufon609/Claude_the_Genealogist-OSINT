#!/usr/bin/env python3
"""Apply pending schema/migrations/*.sql to an existing catalog, in version order."""
import glob, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT
db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "catalog", "tree.db")
cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON")
done = {r[0] for r in cx.execute("SELECT version FROM schema_migration")}
key = lambda v: tuple(int(x) for x in v.split("."))
for path in sorted(glob.glob(os.path.join(ROOT, "schema", "migrations", "*.sql")), key=lambda p: key(os.path.basename(p)[:-4])):
    v = os.path.basename(path)[:-4]
    if v in done: continue
    with open(path, encoding="utf-8") as fh: cx.executescript("BEGIN;\n" + fh.read() + "\nCOMMIT;")
    print("applied", v)
print("schema at", max((r[0] for r in cx.execute("SELECT version FROM schema_migration")), key=key))
