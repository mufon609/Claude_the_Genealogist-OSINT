#!/usr/bin/env python3
"""The next person at the edge of the confirmed tree, in the overview's own order.

usage: tools/queue.py [--tree slug] [--db catalog/tree.db] [--json]
       tools/queue.py --all [--tree slug] [--db catalog/tree.db] [--json]

Read-only (docs/RESEARCH-WORKFLOW.md §8; CLAUDE.md "Working the repo" > "Working a person" §1). Walks
tools/tree.py overview's own order, the home person's line first, generation by generation (a card's parents
father then mother), then the file's other people in the order overview lists them. At each confirmed card the
edge is: a parent or spouse the file names whose link is not yet accepted, taken before the card's own person
(never a person two links from anyone confirmed); else the card's own person when a document waits to be
decided, a conflict is open, or a key fact is still undecided (an open question). A card with none of these is
settled and the walk moves on to the next. The file's other people (not reached by an accepted parents link)
come after the confirmed line, in tools/tree.py overview's own "others" order, and only the ones a document or a
conflict already waits on (overview's own filter), so nobody surfaces two links from anyone confirmed.
Without --all, prints the first person found and stops (queue.py --all lists the rest).
"""
import argparse, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, resolve_tree
from catalog import Catalog
from overview import overview

def edge(cx, tree_id):
    """The queue, in order: [{id, name, reason}], each person named once (first reason it surfaces under)."""
    cat = Catalog(cx, tree_id); ov = overview(cx, tree_id); out = []; seen = set()
    def add(pid, name, reason):
        if pid in seen: return
        seen.add(pid); out.append({"id": pid, "name": name, "reason": reason})
    for gen in ov["generations"]:
        for c in gen:
            pid = c["id"]; fam = cat.family(pid)
            if cat.link_basis(pid, "parents") != "accepted":
                for ppid, pname in fam["parents"]:
                    add(ppid, pname, f"parent the file names for {c['name']}, link not yet accepted")
            for f in fam["families"]:
                if not f["spouse_id"]: continue
                both = (cat.basis("family_member", dumps([f["id"], pid, "partner"])) == "accepted"
                        and cat.basis("family_member", dumps([f["id"], f["spouse_id"], "partner"])) == "accepted")
                if not both: add(f["spouse_id"], f["spouse"], f"spouse the file names for {c['name']}, link not yet accepted")
            w = cat.waiting(pid); bl = cat.baseline(pid)
            if w["documents"] or w["conflicts"] or not bl["complete"]:
                why = []
                if not bl["complete"]: why.append(f"{len(bl['undecided'])} key fact(s) undecided")
                if w["documents"]: why.append(f"{w['documents']} document(s) to decide")
                if w["conflicts"]: why.append(f"{w['conflicts']} conflict(s) open")
                add(pid, c["name"], "confirmed, with an open question: " + ", ".join(why))
    for c in ov["others"]:
        add(c["id"], c["name"], "named in the file, no accepted link to anyone confirmed yet, with a document or a conflict waiting")
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--tree"); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); tree_id, slug = resolve_tree(cx, a.tree)
    q = edge(cx, tree_id)
    if a.json: print(dumps(q if a.all else q[:1])); return
    if not q: print("nothing at the edge: every confirmed person is settled, and the file names nobody else waiting"); return
    if a.all:
        for e in q: print(f"{e['name']} [{e['id'][-6:]}]  {e['reason']}")
    else:
        e = q[0]; print(f"{e['name']} [{e['id'][-6:]}]  {e['reason']}")

if __name__ == "__main__": main()
