#!/usr/bin/env python3
"""The memorials waiting to be fetched, and the pages that came back.

usage: tools/memorials.py list [--json] [--tree slug] [--db catalog/tree.db]
       tools/memorials.py collect [--by user:<you>] [--tree slug] [--db catalog/tree.db]

Find a Grave forbids automation, so a memorial is saved one page at a time in the owner's own browser by the page-saves-itself
method (docs/RESEARCH-WORKFLOW.md §4), one tab per page. `list` prints every memorial a planned fetch step at Find a Grave
points at, once, with the people whose steps it fulfils: the leads from held records first (a persona accepted as a person,
whose memorial the record links), then the file's citations. That is the list a browser session works through. `collect`
moves every saved memorial page from the browser's download folder into inbox/ and attaches each by its own identity
(tools/attach.py): archived once, logged found on every step that cites it, extracted, matched, the rule run.
"""
import argparse, json, os, re, shutil, sqlite3, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, inbox_dir, resolve_tree
from attach import attach_inbox, line

MEMORIAL = re.compile(r"/memorial/(\d+)(?:/|$)")

def waiting(cx, tree_id):
    """Memorials with a planned fetch step at Find a Grave, once each: id, url, the people and rows waiting on it, and whether
    it is a lead from a held record (locator memorial_id) or the file's citation (locator apid)."""
    out = {}
    for s in cx.execute("""SELECT sp.id, sp.locator_kind, sp.locator_value, sp.query_json, sp.row_key, p.display_name FROM search_plan sp JOIN person p ON p.id=sp.person_id
                           WHERE p.tree_id=? AND sp.kind='fetch' AND sp.mode='fetch' AND sp.status='planned' AND sp.locator_source_id='E01' ORDER BY sp.seq""", (tree_id,)):
        url = (json.loads(s["query_json"] or "{}").get("url") or {}).get("value") or ""
        m = MEMORIAL.search(url); mid = s["locator_value"] if s["locator_kind"] == "memorial_id" else (m.group(1) if m else None)
        if not mid: continue
        e = out.setdefault(mid, {"memorial": mid, "url": f"https://www.findagrave.com/memorial/{mid}/", "lead": False, "people": [], "steps": 0})
        e["steps"] += 1; e["lead"] = e["lead"] or s["locator_kind"] == "memorial_id"
        if s["display_name"] not in e["people"]: e["people"].append(s["display_name"])
    return sorted(out.values(), key=lambda e: (not e["lead"], -e["steps"], e["memorial"]))

def downloads_dir():
    try: return subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=5).stdout.strip() or os.path.expanduser("~/Downloads")
    except Exception: return os.path.expanduser("~/Downloads")

def collect(cx, tree_id, slug, by):
    """Every findagrave-memorial-<id>.html in the download folder: moved to inbox/, then attached. Returns the attach results."""
    names = []
    for f in sorted(os.listdir(downloads_dir())):
        if re.fullmatch(r"findagrave-memorial-\d+\.html", f):
            shutil.move(os.path.join(downloads_dir(), f), os.path.join(inbox_dir(), f)); names.append(f)
    return names, (attach_inbox(cx, tree_id, slug, by, names) if names else [])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["list", "collect"]); ap.add_argument("--json", action="store_true"); ap.add_argument("--tree")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.cmd == "list":
        rows = waiting(cx, tree_id)
        if a.json: print(dumps(rows)); return
        for e in rows: print(f"{'lead ' if e['lead'] else 'cited'} {e['url']}  {', '.join(e['people'])}  ({e['steps']} step{'s' if e['steps'] > 1 else ''})")
        print(f"{len(rows)} memorial(s) to fetch, one tab per page; then tools/memorials.py collect")
    else:
        cx.execute("BEGIN")
        try: names, results = collect(cx, tree_id, slug, a.by); cx.commit()
        except Exception: cx.rollback(); raise
        for r in results: print(line(r))
        if not names: print(f"nothing saved in {downloads_dir()}")

if __name__ == "__main__": main()
