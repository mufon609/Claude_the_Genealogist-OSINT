#!/usr/bin/env python3
"""Match the personas of an extraction against the tree and write proposals.

usage: tools/match.py <extraction id> [--about "<person>"] [--db catalog/tree.db] [--by user:<you>]

The matcher is tools/matcher.py (the persons the record was fetched for and their relatives as candidates, each persona compared
with each on name, sex, dates and places, one persona_match or new_person proposal each, its rationale in words). --about names
the person the record is about on the owner's word, when no step or link names them: a fetch step on their plan, done with a
found run naming the record (attach.on_word), so every later reading finds them. Prints each proposal with its rationale.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect
from catalog import Catalog
from matcher import match

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extraction")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument(
        "--about",
        help="the person the record is about on the owner's word, when no step or link names them: a fetch step on their plan, done with a found run naming the record"
    )
    a = ap.parse_args()
    cx = connect(a.db)
    about = None
    cx.execute("BEGIN")
    # the owner's word: a fetch step on their plan, done with a found run naming the record, so every later reading finds them
    if a.about:
        from attach import on_word
        from treelib import resolve_tree
        tree_id, _ = resolve_tree(cx, None)
        about = [Catalog(cx, tree_id).find_person(a.about)]
        on_word(
            cx,
            tree_id,
            about[0],
            cx.execute("SELECT artifact_sha256 FROM extraction WHERE id=?", (a.extraction,)).fetchone()[0],
            a.by
        )
    written = match(cx, a.extraction, a.by, about=about)
    cx.commit()
    for prop, kind, name, person_id in written:
        print(f"{prop}  {kind:14} {name}")
        print("   ", cx.execute("SELECT rationale FROM proposal WHERE id=?", (prop,)).fetchone()[0])
    if not written:
        print("no new proposals")

if __name__ == "__main__":
    main()
