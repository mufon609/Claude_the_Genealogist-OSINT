#!/usr/bin/env python3
"""Manage trees (profiles).

  tools/tree.py create <slug> --name "Doe Family Tree" [--description ...]
  tools/tree.py list
  tools/tree.py use <slug>          # sets catalog/.active-tree, written whole
  tools/tree.py show [<slug>]
  tools/tree.py overview [<slug>]      the tree as confirmed: home person upward, key facts accepted, the edge; where the tree comes from
  tools/tree.py home "<person>" [--tree <slug>]   # the person the tree overview starts from, named as every tool names one
"""
import argparse, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import Catalog
from treelib import ACTIVE_TREE_FILE, DB, ROOT, active_tree_slug, connect, dumps, exports_dir, imports_dir, now, tree_dir, ulid, write_text_whole

def cmd_create(cx, a):
    if cx.execute("SELECT 1 FROM tree WHERE slug=?", (a.slug,)).fetchone():
        sys.exit(f"tree '{a.slug}' already exists")
    ts = now(); tid = ulid()
    cx.execute("INSERT INTO tree (id,slug,name,description,settings_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
               (tid, a.slug, a.name, a.description, dumps({}), ts, ts))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id) VALUES (?,?,?,?,?,?,?)",
               (ulid(), tid, ts, a.by, "insert", "tree", tid))
    cx.commit()
    d = tree_dir(a.slug); os.makedirs(d, exist_ok=True)
    for sub in (imports_dir(a.slug), exports_dir(a.slug)): os.makedirs(sub, exist_ok=True)
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
    write_text_whole(ACTIVE_TREE_FILE, a.slug + "\n")
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
    kinds = ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in cx.execute("SELECT kind, COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' GROUP BY kind ORDER BY kind", (tid,)))
    print(f"  undecided proposals {q('SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status=\"undecided\"')}" + (f" ({kinds}; persona matches and new persons are cards, place resolutions wait on a decision path)" if kinds else ""))
    for r in cx.execute("SELECT imported_at, artifact_sha256, original_path FROM tree_import WHERE tree_id=? ORDER BY imported_at", (tid,)):
        print(f"  import {r[0][:10]} {r[1][:12]}… {os.path.relpath(r[2], ROOT) if r[2] else ''}")

def cmd_overview(cx, a):
    """The tree as confirmed, from the home person upward, with the edge where the file's claims stop being accepted."""
    from overview import overview, render
    slug = a.slug or active_tree_slug()
    t = cx.execute("SELECT id FROM tree WHERE slug=?", (slug,)).fetchone()
    if not t: sys.exit(f"tree '{slug}' does not exist")
    cx.row_factory = sqlite3.Row
    print(render(overview(cx, t[0]), cx))

def cmd_home(cx, a):
    """The home person: the overview lays the family out from them. Named as every tool names a person (Catalog.find_person): the
    id, the six characters of it ("Name [ABC123]" or alone), the exact name or a substring with one match; a person merged into
    another is no match, so the home person is never a duplicate the merge moved everything off."""
    slug = a.tree or active_tree_slug()
    t = cx.execute("SELECT id FROM tree WHERE slug=?", (slug,)).fetchone()
    if not t: sys.exit(f"tree '{slug}' does not exist")
    pid = Catalog(cx, t[0]).find_person(a.person)
    cx.execute("UPDATE tree SET home_person_id=?, updated_at=? WHERE id=?", (pid, now(), t[0]))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)", (ulid(), t[0], now(), a.by, "update", "tree", t[0], dumps({"home_person_id": pid})))
    cx.commit(); print(f"home person of {slug}: {cx.execute('SELECT display_name FROM person WHERE id=?', (pid,)).fetchone()[0]}")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default=DB)
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("slug"); c.add_argument("--name", required=True); c.add_argument("--description")
    sub.add_parser("list")
    u = sub.add_parser("use"); u.add_argument("slug")
    sh = sub.add_parser("show"); sh.add_argument("slug", nargs="?")
    ov = sub.add_parser("overview", help="the tree as confirmed, from the home person upward, its edge, and where the tree comes from"); ov.add_argument("slug", nargs="?")
    hm = sub.add_parser("home"); hm.add_argument("person"); hm.add_argument("--tree")
    a = ap.parse_args()
    cx = connect(a.db)
    {"create": cmd_create, "list": cmd_list, "use": cmd_use, "show": cmd_show, "overview": cmd_overview, "home": cmd_home}[a.cmd](cx, a)

if __name__ == "__main__":
    main()
