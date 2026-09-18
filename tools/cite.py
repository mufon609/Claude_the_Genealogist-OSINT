#!/usr/bin/env python3
"""A record the owner cites on their own word: a fetch step on the person's plan, with the citation's own details.

usage: tools/cite.py "<person>" --row "census household:1950" --holder D05 --field "surname=Evers" --field "census place=East Northport, Suffolk County, New York"
                     --field "enumeration district=52-133A" --field "page=5" --field "year=1950" [--field "collection=…"] [--type household|subject_record]
                     [--note "…"] [--tree slug] [--db catalog/tree.db] [--by user:<you>]

The file cites nothing for the person and nothing is archived yet, but the owner knows the record exists at a holder (a
census schedule they have seen: the place, the enumeration district, the sheet). The step carries those details as the
owner gives them, each field basis 'owner', and the holder as its locator source, so `tools/run_step.py <step id>` asks the
holder's connector for it exactly as it asks for a record the file cites (docs/RESEARCH-WORKFLOW.md §4: the lookup at the
holder uses the citation's own details only), and what comes back is fetched for this person and read by the extractor,
the matcher and the standing rule like any other record. The planner never drops the step. Prints the step id.
"""
import argparse, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, resolve_tree
from catalog import Catalog
from attach import cite_on_word

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who"); ap.add_argument("--row", required=True, help="the checklist row: 'census household:1950', 'death record:1986'")
    ap.add_argument("--holder", required=True, help="the registry id of the holder to ask (data/data-sources.csv)"); ap.add_argument("--field", action="append", default=[], help="'label=value', the citation's own detail")
    ap.add_argument("--type", choices=["household", "subject_record"]); ap.add_argument("--note"); ap.add_argument("--tree")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    fields = {}
    for f in a.field:
        if "=" not in f: ap.error(f"--field wants 'label=value': {f}")
        k, v = f.split("=", 1); fields[k] = v
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    pid = cat.find_person(a.who)
    cx.execute("BEGIN")
    try: sid = cite_on_word(cx, tree_id, pid, a.row, a.holder, fields, a.by, note=a.note, query_type=a.type)
    except ValueError as e: cx.rollback(); sys.exit(str(e))
    cx.commit()
    print(f"step {sid} on {cat.person(pid)['name']}: {a.row} at {a.holder}, on the owner's word; run it with tools/run_step.py {sid}")

if __name__ == "__main__": main()
