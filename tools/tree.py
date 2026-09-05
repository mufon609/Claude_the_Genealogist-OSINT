#!/usr/bin/env python3
"""Manage trees (profiles).

  tools/tree.py create <slug> --name "Ahearn Family Tree" [--description ...]
  tools/tree.py list
  tools/tree.py use <slug>          # sets catalog/.active-tree
  tools/tree.py show [<slug>]
"""
import argparse, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ACTIVE_TREE_FILE, ROOT, active_tree_slug, dumps, now, tree_dir, ulid

def connect(db):
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); return cx

def cmd_create(cx, a):
    if cx.execute("SELECT 1 FROM tree WHERE slug=?", (a.slug,)).fetchone():
        sys.exit(f"tree '{a.slug}' already exists")
    ts = now(); tid = ulid()
    cx.execute("INSERT INTO tree (id,slug,name,description,settings_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
               (tid, a.slug, a.name, a.description, dumps({"living_years": 100}), ts, ts))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id) VALUES (?,?,?,?,?,?,?)",
               (ulid(), tid, ts, a.by, "insert", "tree", tid))
    cx.commit()
    d = tree_dir(a.slug)
    for sub in ("imports", "exports"): os.makedirs(os.path.join(d, sub), exist_ok=True)
    with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# {a.name}\n\nslug: `{a.slug}`\n\n"
                 "- `imports/` named copies of files ingested into this tree (the archive holds the hashed master)\n"
                 "- `exports/` GEDCOM 7 / Gramps XML snapshots\n")
    print(f"created tree '{a.slug}' ({tid}) at trees/{a.slug}/")
    if not active_tree_slug():
        cmd_use(cx, a)

def cmd_list(cx, a):
    active = active_tree_slug()
    rows = cx.execute("""SELECT t.slug, t.name, t.created_at,
                                (SELECT COUNT(*) FROM person p WHERE p.tree_id=t.id),
                                (SELECT COUNT(*) FROM tree_import i WHERE i.tree_id=t.id)
                         FROM tree t ORDER BY t.slug""").fetchall()
    if not rows: print("no trees"); return
    for slug, name, created, np, ni in rows:
        print(f"{'*' if slug == active else ' '} {slug:16} {name:32} persons={np:<5} imports={ni:<3} created {created[:10]}")

def cmd_use(cx, a):
    if not cx.execute("SELECT 1 FROM tree WHERE slug=?", (a.slug,)).fetchone():
        sys.exit(f"tree '{a.slug}' does not exist")
    os.makedirs(os.path.dirname(ACTIVE_TREE_FILE), exist_ok=True)
    with open(ACTIVE_TREE_FILE, "w", encoding="utf-8") as fh: fh.write(a.slug + "\n")
    print(f"active tree: {a.slug}")

def cmd_show(cx, a):
    slug = a.slug or active_tree_slug()
    if not slug: sys.exit("no active tree")
    t = cx.execute("SELECT id,slug,name,description,settings_json,created_at FROM tree WHERE slug=?", (slug,)).fetchone()
    if not t: sys.exit(f"tree '{slug}' does not exist")
    tid = t[0]
    q = lambda s: cx.execute(s, (tid,)).fetchone()[0]
    print(f"{t[1]}: {t[2]}\n  id {tid}\n  settings {t[4]}\n  created {t[5]}")
    print(f"  persons {q('SELECT COUNT(*) FROM person WHERE tree_id=?')}  families {q('SELECT COUNT(*) FROM family WHERE tree_id=?')}  "
          f"events {q('SELECT COUNT(*) FROM event WHERE tree_id=?')}  assertions {q('SELECT COUNT(*) FROM assertion WHERE tree_id=?')}")
    print(f"  undecided proposals {q('SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status=\"undecided\"')}")
    for r in cx.execute("SELECT imported_at, artifact_sha256, original_path FROM tree_import WHERE tree_id=? ORDER BY imported_at", (tid,)):
        print(f"  import {r[0][:10]} {r[1][:12]}… {os.path.relpath(r[2], ROOT) if r[2] else ''}")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("slug"); c.add_argument("--name", required=True); c.add_argument("--description")
    sub.add_parser("list")
    u = sub.add_parser("use"); u.add_argument("slug")
    sh = sub.add_parser("show"); sh.add_argument("slug", nargs="?")
    a = ap.parse_args()
    cx = connect(a.db)
    {"create": cmd_create, "list": cmd_list, "use": cmd_use, "show": cmd_show}[a.cmd](cx, a)

if __name__ == "__main__":
    main()
