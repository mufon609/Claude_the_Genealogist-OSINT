#!/usr/bin/env python3
"""The pages waiting to be fetched by hand at every holder, and the pages that came back.

usage: tools/fetches.py next [K] [--tree slug] [--db catalog/tree.db]
       tools/fetches.py list [--all] [--json] [--tree slug] [--db catalog/tree.db]
       tools/fetches.py collect [--folder DIR] [--by user:<you>] [--tree slug] [--db catalog/tree.db]

The fetch list is tools/fetch_list.py (`next`, the browser session's own list of the next K pages, one line each with the
link, the file name to save under and the save script's call; `list`, every page, hiding the ones whose steps have all been
run on unchanged fields unless --all); `collect` is arrival.collect, the pages saved in the data root's own downloads/
folder (or --folder) taken into inbox/ and attached, one line printed per file.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, downloads_dir, dumps, resolve_tree
from attach import line
from fetch_list import annotated, next_lines, page_call
from arrival import collect

def main():
    ap = argparse.ArgumentParser(description="The pages waiting to be saved by hand, and collect: the pages saved in the data root's downloads/ folder (the browser's "
                                             "download location, set once), or --folder, taken into inbox/ and attached; the owner's own download folder is never read.")
    ap.add_argument("cmd", choices=["next", "list", "collect"]); ap.add_argument("count", nargs="?", type=int, default=5, help="next: how many pages")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--all", action="store_true", help="list: the pages already run on unchanged fields too"); ap.add_argument("--tree")
    ap.add_argument("--db", default=DB); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument("--folder", help="collect: the folder to take saved pages from, instead of the data root's downloads/ folder (the browser's download location, set once)")
    a = ap.parse_args()
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.cmd == "next": print("\n".join(next_lines(cx, tree_id, a.count)))
    elif a.cmd == "list":
        every = annotated(cx, tree_id); rows = every if a.all else [e for e in every if e["open_step_ids"] or not e["url"]]
        if a.json: print(dumps(rows)); return
        last = None
        for e in rows:
            if e["holder"] != last: print(f"-- {e['holder']}"); last = e["holder"]
            print(f"{'lead ' if e['lead'] else 'cited'} {e['url']}  {', '.join(e['people'])}  ({e['steps']} step{'s' if e['steps'] > 1 else ''}: {', '.join(e['rows'])})  save as {e['save_as']}" + ("  (an image: tools/save_image.js in its own tab)" if e["how"] == "image" else "")
                  + ("  [already run on unchanged fields]" if a.all and e["url"] and not e["open_step_ids"] else "")
                  + (f"  call {page_call(e)}" if e["url"] and e["how"] != "image" else ""))
        print(f"{len(rows)} page(s) to fetch, one tab per page; then tools/fetches.py collect" + (f" ({len(every) - len(rows)} already run on unchanged fields, hidden: --all)" if len(every) > len(rows) else ""))
    else:
        names, results = collect(cx, tree_id, slug, a.by, folder=a.folder)
        for r in results: print(line(r))
        if not names: print(f"nothing saved in {a.folder or downloads_dir()}")

if __name__ == "__main__": main()
