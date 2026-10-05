#!/usr/bin/env python3
"""The next person at the edge of the confirmed tree, in the overview's own order.

usage: tools/queue.py [--tree slug] [--db catalog/tree.db] [--json]
       tools/queue.py --all [--tree slug] [--db catalog/tree.db] [--json]

Read-only (docs/RESEARCH-WORKFLOW.md §8; CLAUDE.md "Working the repo" > "Working a person" §1). The edge is the
confirmed tree's, and the confirmed tree starts at the tree's home person: a tree with none set is refused, saying so
(tools/tree.py home "<person>"), rather than walking the file's people in no order that means anything. Walks
tools/tree.py overview's own order, the home person's line first, generation by generation (a card's parents
father then mother), then the file's other people in the order overview lists them. At each confirmed card the
edge is: a parent or spouse the file names whose link is not yet accepted, taken before the card's own person
(never a person two links from anyone confirmed); else the card's own person when a document waits to be
decided, a conflict is open, or a key fact is still undecided (an open question); else the card's own person when
nobody has accepted their parents and the file names none, for the records that name parents (checklist.names_parents:
a birth or death record, an obituary, a census of their childhood's household), which their plan puts first, so the tree
grows past the file on evidence: a parent such a record names is created by the rule and is the next card above. A card
with none of these is settled and the walk moves on to the next. The file's other people (not reached by an accepted parents link)
come after the confirmed line, in tools/tree.py overview's own "others" order: only the ones a document or a
conflict already waits on and who are one link (a parent, a child or a spouse the file names) from someone confirmed,
the nearest first and, among those, the one reached from the earlier card of the confirmed walk; a person further from
the confirmed tree is never named, and their questions wait with them.

An open question names the next person only when a turn can still act on them: no plan has been made for them
yet (a turn's own first move), or their plan still has a step a turn can advance. A step is that when a connector
can run it and its source has no run since the plan last wrote its fields (tools/run_step.py's own runnable steps, each
source's runs read on their own), or when
it is fetched by hand, carries a link the fetch list prints (tools/fetches.py list) and has no such run either. A person
already planned with no such step, whose open question is now only the owner's (a card to decide, a conflict, a baseline
nobody has vouched or decided, an assisted search with no link to open, an auto step run on these fields already (a run
logged error, the source not answering, is not such a run), a fetch logged blocked) is passed over: named, with why, but
never named next, since running a turn on them would do nothing.
A person at the edge for their parents' records is named only while one of those steps is one a turn can advance (or no
plan has been made for them yet), and passed over otherwise. A person who waits on pages to save in the browser (a turn
named them: tools/turn.py, its state beside the database) is passed over while every step a turn could advance for them is
one of those pages, with the number of pages: a turn would name the same pages again. Once a page of theirs has been saved
its run is logged on their step, which is then no page they wait on, and they are read as anyone is; a step their plan opens
that is not one of those pages names them sooner.
Without --all, prints the first person found and the number passed over (queue.py --all lists the rest, each passed-over
person with the reason).
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, resolve_tree
from catalog import Catalog
from checklist import names_parents
from overview import overview
from turn import waits
import run_step, fetches

def advanceable(cx, cat, tree_id):
    """The steps a turn can advance, by id: one the runner takes now (run_step.runnable: a connector can run it and it has no
    run since the plan last wrote its fields), or one on the fetch list a turn can open (fetches.openable: a link to open, and
    this person's own step in the entry with no run on unchanged fields either); and the fetch list's entries, read once."""
    steps = {r["id"] for r in run_step.runnable(cx, cat, tree_id)}
    entries = fetches.openable(cx, tree_id)
    for e in entries: steps.update(e["open_step_ids"])
    return steps, entries

def require_home(cx, tree_id):
    """The tree's home person, or a refusal that names the command that sets one: the confirmed tree is walked from them."""
    slug, home = cx.execute("SELECT slug, home_person_id FROM tree WHERE id=?", (tree_id,)).fetchone()
    if not home: sys.exit(f"tree '{slug}' has no home person: the queue walks the confirmed tree from them. Set one with: python3 tools/tree.py home \"<person>\" --tree {slug}")
    return home

def edge(cx, tree_id, waits=None):
    """([{id, name, reason, kind}], [{id, name, reason, kind}]): the queue a turn can act on, in order, then everyone passed
    over (named once each, first reason it surfaces under; kind says which: "parent link" or "spouse link" the file names and
    nobody has accepted, "open question" on a confirmed person, "parents records" for a confirmed person whose parents nobody
    has accepted and the file names none, "unlinked" for a person the file names with no accepted link to anyone confirmed). A person with no plan yet is always actionable (a turn's own
    first move makes one); one already planned is actionable only while a step of theirs is one a turn can advance
    (advanceable) -- otherwise their open question is the owner's alone and they are passed over, not named next. waits:
    {person id: the steps of the pages they wait on} (tools/turn.py waits): a person all of whose steps a turn could advance
    are pages they wait on is passed over too, with the number of pages, since a turn would name the same pages again;
    once a page of theirs has been saved its step is no longer one a turn can advance, and they are read as anyone is."""
    require_home(cx, tree_id)
    cat = Catalog(cx, tree_id); ov = overview(cx, tree_id); out, passed = [], []; seen = set()
    can, entries = advanceable(cx, cat, tree_id)
    waits = waits or {}
    def add(pid, name, reason, kind, counts=lambda row_key: True):
        """counts: which of the person's steps answer the reason (all of them, or the records that name parents)."""
        if pid in seen: return
        seen.add(pid)
        planned = cat.q("SELECT id, row_key FROM search_plan WHERE person_id=?", pid)
        open_steps = {sid for sid, rk in planned if sid in can and counts(rk)}
        waited = open_steps & set(waits.get(pid, ()))
        if planned and not open_steps:
            passed.append({"id": pid, "name": name, "reason": f"nothing left for a turn to run or fetch: {reason}", "kind": kind})
        elif planned and open_steps == waited:
            pages = [e for e in entries if waited & set(e["open_step_ids"])]
            why = f"waits on {len(pages)} page(s) to save in the browser: {reason}"
            passed.append({"id": pid, "name": name, "reason": why, "kind": kind, "waits": len(pages)})
        else:
            out.append({"id": pid, "name": name, "reason": reason, "kind": kind})
    for gen in ov["generations"]:
        for c in gen:
            pid = c["id"]; fam = cat.family(pid)
            if cat.link_basis(pid, "parents") != "accepted":
                for ppid, pname in fam["parents"]:
                    add(ppid, pname, f"parent the file names for {c['name']}, link not yet accepted", "parent link")
            for f in fam["families"]:
                if not f["spouse_id"]: continue
                both = (cat.basis("family_member", dumps([f["id"], pid, "partner"])) == "accepted"
                        and cat.basis("family_member", dumps([f["id"], f["spouse_id"], "partner"])) == "accepted")
                if not both: add(f["spouse_id"], f["spouse"], f"spouse the file names for {c['name']}, link not yet accepted", "spouse link")
            w = cat.waiting(pid); bl = cat.baseline(pid)
            if w["documents"] or w["conflicts"] or not bl["complete"]:
                why = []
                if not bl["complete"]: why.append(f"{len(bl['undecided'])} key fact(s) undecided")
                if w["documents"]: why.append(f"{w['documents']} document(s) to decide")
                if w["conflicts"]: why.append(f"{w['conflicts']} conflict(s) open")
                add(pid, c["name"], "confirmed, with an open question: " + ", ".join(why), "open question")
            elif cat.link_basis(pid, "parents") != "accepted" and not fam["parents"]:
                born = c["span"][0]
                add(pid, c["name"], "confirmed, no parents accepted and the file names none: the records that name parents", "parents records",
                    counts=lambda row_key, born=born: names_parents(row_key, born))
    for c in ov["others"]:
        add(c["id"], c["name"], "named in the file, no accepted link to anyone confirmed yet, with a document or a conflict waiting", "unlinked")
    return out, passed

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--tree"); ap.add_argument("--db", default=DB)
    a = ap.parse_args()
    cx = connect(a.db, rows=True); tree_id, slug = resolve_tree(cx, a.tree)
    q, passed = edge(cx, tree_id, waits(cx, a.db, tree_id))
    if a.json: print(dumps({"next": q if a.all else q[:1], "passed_over": passed})); return
    if a.all:
        for e in passed: print(f"passed over: {e['name']} [{e['id'][-6:]}]  {e['reason']}")
    if not q: print("nothing at the edge: every confirmed person is settled, and the file names nobody else waiting")
    else:
        for e in (q if a.all else q[:1]): print(f"{e['name']} [{e['id'][-6:]}]  {e['reason']}")
    if passed and not a.all: print(f"{len(passed)} passed over (tools/queue.py --all)")

if __name__ == "__main__": main()
