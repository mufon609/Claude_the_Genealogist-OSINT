#!/usr/bin/env python3
"""Attach every file in the inbox to the steps it fulfils, by the record's own identity.

usage: tools/attach_inbox.py [--tree slug] [--db catalog/tree.db] [--by user:<you>] [file ...]

For each file (all inbox files when none are named): the record's identity is read from the file (a Find a Grave memorial
id, a FamilySearch ark), every fetch step whose citation carries it is found, the file is archived once and a found run is
logged on each of those steps, then the extractor and the matcher run once. A file whose identity matches no step stays in
the inbox and is reported. Prints one line per file: identity, steps fulfilled with their people, artifact hash,
extraction id, proposals written. Re-running changes nothing: attached files have left the inbox, and a copy of an archived
file logs no step twice. See tools/attach.py, which the person screen shares.
"""
import argparse, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, resolve_tree
from attach import attach_inbox, line
from catalog import Catalog

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="*"); ap.add_argument("--tree"); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown")); ap.add_argument("--about", help="the person the named file is about, on the owner's word, when no step cites it")
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.about and not a.files: ap.error("--about names the person one file is about: name the file too")
    about = Catalog(cx, tree_id).find_person(a.about) if a.about else None
    cx.execute("BEGIN")
    try: results = attach_inbox(cx, tree_id, slug, a.by, a.files or None, about=about); cx.commit()
    except Exception: cx.rollback(); raise
    for r in results: print(line(r))
    if not results: print("inbox empty")

if __name__ == "__main__": main()
