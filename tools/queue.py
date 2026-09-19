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

An open question names the next person only when a turn can still act on them: no plan has been made for them
yet (a turn's own first move), or their plan still has a step a turn can advance. A step is that when a connector
can run it and it has no run since the plan last wrote its fields (tools/run_step.py's own runnable steps), or when
it is fetched by hand, carries a link the fetch list prints (tools/fetches.py list), a file name the list can print whole
(fetches.unnamed: a name still wanting a year the citation does not carry is one no save can be made under) and has no
such run either. A person already planned
with no such step, whose open question is now only the owner's (a card to decide, a conflict, a baseline nobody has
vouched or decided, an assisted search with no link to open, an auto step run on these fields already (a run logged
error, the source not answering, is not such a run), a fetch logged blocked, a fetch whose page the list cannot name) is
passed over: named, with why, but never named next, since
running a turn on them would do nothing.
Without --all, prints the first person found and stops (queue.py --all lists the rest).
"""
import argparse, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, resolve_tree
from catalog import Catalog
from overview import overview
import run_step, fetches

def advanceable(cx, cat, tree_id):
    """(the people with a step a turn can advance, {person id: [why a page of theirs cannot be fetched]}). A step a turn can
    advance is one the runner takes now (run_step.runnable: a connector can run it and it has no run since the plan last
    wrote its fields), or one on the fetch list a turn can open (fetches.openable: a link to open, a file name the list
    prints whole, and this person's own step in the entry with no run on unchanged fields either). An open entry the list
    cannot name (fetches.unnamed) advances nobody: its reason is kept, per person, for the pass-over line."""
    people = {r["person_id"] for r in run_step.runnable(cx, cat, tree_id)}
    owner = dict(cx.execute("SELECT sp.id, sp.person_id FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=?", (tree_id,)).fetchall())
    unnamed = {}
    for e in fetches.openable(cx, tree_id):
        for sid in e["open_step_ids"]:
            if sid not in owner: continue
            if e["unnamed"]: unnamed.setdefault(owner[sid], []).append(e["unnamed"])
            else: people.add(owner[sid])
    return people, unnamed

def edge(cx, tree_id):
    """([{id, name, reason}], [{id, name, reason}]): the queue a turn can act on, in order, then everyone passed over
    (named once each, first reason it surfaces under). A person with no plan yet is always actionable (a turn's own
    first move makes one); one already planned is actionable only while a step of theirs is one a turn can advance
    (advanceable) -- otherwise their open question is the owner's alone and they are passed over, not named next, a page of
    theirs the list cannot name said so in the reason."""
    cat = Catalog(cx, tree_id); ov = overview(cx, tree_id); out, passed = [], []; seen = set()
    can, unnamed = advanceable(cx, cat, tree_id)
    def add(pid, name, reason):
        if pid in seen: return
        seen.add(pid)
        planned_before = cat.q("SELECT 1 FROM search_plan WHERE person_id=? LIMIT 1", pid)
        if planned_before and pid not in can:
            passed.append({"id": pid, "name": name, "reason": "; ".join([f"nothing left for a turn to run or fetch: {reason}"] + unnamed.get(pid, []))})
        else:
            out.append({"id": pid, "name": name, "reason": reason})
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
    return out, passed

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--tree"); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row; tree_id, slug = resolve_tree(cx, a.tree)
    q, passed = edge(cx, tree_id)
    if a.json: print(dumps({"next": q if a.all else q[:1], "passed_over": passed})); return
    for e in passed: print(f"passed over: {e['name']} [{e['id'][-6:]}]  {e['reason']}")
    if not q: print("nothing at the edge: every confirmed person is settled, and the file names nobody else waiting"); return
    if a.all:
        for e in q: print(f"{e['name']} [{e['id'][-6:]}]  {e['reason']}")
    else:
        e = q[0]; print(f"{e['name']} [{e['id'][-6:]}]  {e['reason']}")

if __name__ == "__main__": main()
