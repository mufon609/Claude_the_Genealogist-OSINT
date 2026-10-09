#!/usr/bin/env python3
"""Two people's relationship through the family links the tree has accepted (docs/RULE.md, "The proof standard"): the
path between them, one link per line with the record it rests on and the proof's reading of that record, the
relationship in words, and the chain's standing, its least-proven link's. Read-only, no model.

usage: tools/kin.py "<person>" "<person>" [--all] [--json] [--tree slug] [--db catalog/tree.db]

An accepted link is what the queue and the overview call one (tools/queue.py, tools/overview.py): a parent when the
child's parents fact is accepted (Catalog.link_basis) and the parent is a partner of a family the child stands in
(Catalog.family, a membership not rejected); a spouse when both partner memberships are accepted (Catalog.basis) in a
family the file names or a record confirmed (Catalog.family with word). Never a claim, a sibling placement, an indexer's
grouping or a page anyone can edit on its own: those are undecided, and an undecided membership is no link here.

Each link's standing is the proof's reading of the record(s) that assert it: the statements on the membership the link is
evidence on (a parent-child link the child's, a spouse link both partners'), grouped by record as tools/proof.py groups
them, the best accepted group first, printed with its class words (source, information, evidence, the relationship stated
or computed) and whether its source is one the rule trusts (T1-T3, never a page anyone can edit); a link the owner vouched,
or accepted as the file's uncited claim, rests on their own word. STANDING below is the one order the chain's links are
compared in, best first; the chain's standing is its weakest link's, and nothing printed to a person is a number.

Several paths: the shortest by links, among those the one whose weakest link is strongest; --all prints the other paths
within a few links of it, at most five, in the same order. The relationship is read off the path's shape: up a generations
and down b through a shared parent gives parent, grandparent, sibling, aunt or uncle, niece or nephew, nth cousin m times
removed, "half" when the two sides share one parent only; a path through a spouse link is related by marriage through
that couple; a path down to a child and up to the child's other parent is related through that child. WORDS below is the
vocabulary.

With no accepted path the answer is never "no": the nearest path the file claims (the links claimed or accepted,
Catalog.family with word) is printed, each link not yet accepted with what would prove it, the checklist's own records
for that link (a record naming the child's parents, tools/checklist.py names_parents; the marriage record for a spouse
link), each with the checklist's status (held, cited, missing); when the file claims no path either, the people on each
side at whom the links end, whose parents nobody names, and for one of the two whose own parents nobody names the records
that would. When an accepted path exists but the file claims a shorter one, that claim follows the chain the same way, so
the owner reads what is owed. --json prints the chain.
Implements [rule.proof.6].
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, resolve_tree
from catalog import Catalog, tier_sql
from checklist import build as checklist, names_parents
from conflicts import order, subject_statements, words
from proof import groups
from rule import TRUSTED

STANDING = ("a record the rule trusts", "your own word", "the file's claim, accepted", "a page anyone can edit", "a record withdrawn from the evidence")   # a link's standing, best first; within one, the classes' own order (conflicts.order)

SLACK = 2                                                        # the other paths printed: within this many links of the shortest
CAP = 200                                                        # the most paths enumerated between two people

WORDS = {                                                        # the vocabulary, by the other person's sex: male, female, unknown
    "parent": ("father", "mother", "parent"), "child": ("son", "daughter", "child"), "spouse": ("husband", "wife", "spouse"),
    "sibling": ("brother", "sister", "sibling"), "pibling": ("uncle", "aunt", "aunt or uncle"), "nibling": ("nephew", "niece", "niece or nephew"),
}
ORDINAL = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
REMOVED = ("once", "twice", "three times", "four times", "five times", "six times", "seven times", "eight times", "nine times", "ten times")

def by_sex(kind, sex):
    """The word of a kind for a person of this sex."""
    return WORDS[kind][0 if sex == "M" else 1 if sex == "F" else 2]

class People(dict):
    """{person id: {id, name, sex}}, read from the catalog on first use."""
    def __init__(self, cat): super().__init__(); self.cat = cat
    def __missing__(self, pid):
        r = self.cat.q("SELECT id, display_name, sex FROM person WHERE id=?", pid)[0]
        self[pid] = {"id": r[0], "name": r[1], "sex": r[2]}
        return self[pid]

# ---------------------------------------------------------------- the links
def family_joining(cat, child, parent, word):
    """The family in which child stands as child under parent, by the test Catalog.family reads memberships with: not rejected,
    or with word claimed or accepted (on_word); the first by id when several do."""
    counts = cat.on_word if word else (lambda f, p, r: not cat.link_rejected(f, p, r))
    for fid, in cat.q("""SELECT fm.family_id FROM family_member fm JOIN family_member p ON p.family_id=fm.family_id AND p.person_id=? AND p.role='partner'
                         WHERE fm.person_id=? AND fm.role='child' ORDER BY fm.family_id""", parent, child):
        if counts(fid, child, "child") and counts(fid, parent, "partner"): return fid
    return None

def graph(cat, word=False):
    """{person id: {other id: (kind, family id)}} over the tree's people (merged ones aside), kind being what the other is to
    the person: parent, child or spouse. The accepted links, as the overview lists a confirmed card's parents and spouses and
    the queue reads the confirmed tree: a parent where the person's parents fact is accepted (Catalog.link_basis) and the
    parent a partner of a family the person stands in (Catalog.family); a spouse where both partner memberships are accepted
    (Catalog.basis) among the families the file names or a record confirmed. With word, the links the file claims or a record
    confirmed instead (Catalog.family with word), accepted or not.
    Implements [rule.proof.6]."""
    out = {}
    def add(a, b, kind, fid): out.setdefault(a, {}).setdefault(b, (kind, fid))
    for pid, in cat.q("SELECT id FROM person WHERE tree_id=? AND merged_into IS NULL ORDER BY id", cat.tree_id):
        fam = cat.family(pid, word=word)
        parents = fam["parents"] if word or cat.link_basis(pid, "parents") == "accepted" else []
        for ppid, _ in parents:
            fid = family_joining(cat, pid, ppid, word)
            add(pid, ppid, "parent", fid); add(ppid, pid, "child", fid)
        for f in (fam if word else cat.family(pid, word=True))["families"]:
            if not f["spouse_id"]: continue
            if not word and not (cat.basis("family_member", dumps([f["id"], pid, "partner"])) == "accepted"
                                 and cat.basis("family_member", dumps([f["id"], f["spouse_id"], "partner"])) == "accepted"): continue
            add(pid, f["spouse_id"], "spouse", f["id"]); add(f["spouse_id"], pid, "spouse", f["id"])
    return out

def distances(g, start):
    """{person id: links from start} over the graph, by breadth-first walk."""
    dist, frontier = {start: 0}, [start]
    while frontier:
        nxt = []
        for pid in frontier:
            for other in g.get(pid, {}):
                if other not in dist: dist[other] = dist[pid] + 1; nxt.append(other)
        frontier = nxt
    return dist

def paths(g, a, b, slack=SLACK, cap=CAP):
    """Every simple path from a to b over the graph within slack links of the shortest, at most cap of them, as lists of
    person ids; none when no chain of links joins them. Branches that cannot reach b within the budget are cut by b's
    distances, and a person's neighbours are walked in id order, so the walk is the same every run."""
    dist = distances(g, b)
    if a not in dist: return []
    budget, out = dist[a] + slack, []
    def walk(node, path):
        if len(out) >= cap: return
        if node == b: out.append(path[:]); return
        for other in sorted(g.get(node, {})):
            if other in path or other not in dist or len(path) + dist[other] > budget: continue
            path.append(other); walk(other, path); path.pop()
    walk(a, [a])
    return out

# ---------------------------------------------------------------- a link's standing
def trusted_record(cat, sha):
    """Whether an archived record's effective trust tier (catalog.tier_sql) is one the rule may act on (rule.TRUSTED)."""
    r = cat.q(f"SELECT substr({tier_sql()},1,2) FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?", sha)
    return bool(r) and r[0][0] in TRUSTED

def rank(st):
    """Where a link's standing falls in STANDING's order, then whether its relationship is the record's own statement, then the
    classes' own order (conflicts.order): the key the chain's links are compared by, never shown."""
    return STANDING.index(st["basis"]), 0 if (st["classes"] or {}).get("relationship") != "computed" else 1, order(st["classes"])

def standing(cat, who, x, y, kind, fid, cache):
    """The proof's reading of what the link from x to y (y the person's kind: parent, child or spouse) rests on: the statements
    on the membership the link is evidence on, grouped by record as the proof groups them (proof.groups), the best accepted
    group of a trusted source first, then of any source, in the classes' own order. {basis: a STANDING word, record: the best
    record's label, classes, said: what the accepted statements of that record say, trusted: whether the rule counts it as
    ground, records: each copy with its citation, words: the line's words}.
    Implements [rule.proof.1], [rule.proof.6]."""
    child = x if kind == "parent" else y if kind == "child" else None
    subjects = [dumps([fid, child, "child"])] if child else [dumps([fid, x, "partner"]), dumps([fid, y, "partner"])]
    sts = []
    for sid in subjects: sts += subject_statements(cat, "family_member", sid, None, who[y if kind != "child" else x]["name"])
    gs = groups(cat.cx, cat.tree_id, "parents" if child else "spouses", sts, None, cache)
    for g in gs: g["trusted"] = any(trusted_record(cat, r["sha256"]) for r in g["records"])
    live = sorted((g for g in gs if g["status"] == "accepted" and not g["withdrawn"]), key=lambda g: (not g["trusted"], order(g["classes"])))
    gone = [g for g in gs if g["status"] == "accepted" and g["withdrawn"]]
    own = any(s["status"] == "accepted" and (s["kind"] == "vouch" or (s["kind"] == "file" and not s["apid"])) for s in sts)   # a vouch, or the file's uncited claim: the owner's knowledge, as the rule counts it
    claim = any(s["status"] == "accepted" and s["kind"] == "file" and s["apid"] for s in sts)
    best = live[0] if live else None
    if best and best["trusted"]: basis = STANDING[0]
    elif own: basis = STANDING[1]
    elif claim: basis = STANDING[2]
    elif best: basis = STANDING[3]
    elif gone: basis, best = STANDING[4], gone[0]
    else: basis = STANDING[2]                                     # an accepted membership whose statements the proof reads as none of these: read as the file's
    c = best["classes"] if best and basis in (STANDING[0], STANDING[3], STANDING[4]) else None
    said = list(dict.fromkeys(s["said"] for s in best["statements"] if s["status"] == "accepted" and s["said"])) if c is not None else []
    out = {"basis": basis, "record": best["label"] if c is not None else None, "classes": c, "said": said, "trusted": basis in (STANDING[0], STANDING[1]),
           "records": [{k: r[k] for k in ("sha256", "name", "locator", "citation")} for r in best["records"]] if c is not None else []}
    if c is None: out["words"] = basis
    else:
        out["words"] = f"{best['label']}: {words(c)}; accepted" + (f" [{'; '.join(said)}]" if said else "") + \
                       (", withdrawn from the evidence" if basis == STANDING[4] else "; a source the rule trusts" if basis == STANDING[0] else "; a page anyone can edit")
    return out

def proves(cat, who, x, y, kind, lists):
    """What would prove a link not yet accepted, from the checklist's own rows: for a parent link, the child's rows whose record
    names their parents (checklist.names_parents: a birth or death record, an obituary, a census of their childhood's
    household), each with the checklist's status; for a spouse link, the marriage record row for that spouse, else every
    marriage record row. lists caches each person's checklist.
    Implements [rule.proof.6]."""
    pid = x if kind != "child" else y
    if pid not in lists: lists[pid] = checklist(cat, pid)
    rows = lists[pid]["checklist"]["A"] + lists[pid]["checklist"]["B"]
    if kind == "spouse":
        marriages = [w for w in rows if w["record"] == "marriage record"]
        rows = [w for w in marriages if w.get("instance") == who[y]["name"]] or marriages
    else:
        born = next((e["year"] for e in cat.events(pid) if e["type"] == "Birth" and e["year"]), None)
        rows = [w for w in rows if names_parents(f"{w['record']}:{w.get('instance') or ''}", born)]
    return [{"record": w["record"], "instance": w.get("instance"), "status": w["status"]} for w in rows if w["status"] != "n/a"]

# ---------------------------------------------------------------- the relationship in words
def shape(kinds):
    """(up, down, turn): the links up to parents before any other, the links down to children after them, and the index on the
    path of a child it goes down to and then up from (to the child's other parent), or None; a path through a spouse link
    has no shape."""
    if "spouse" in kinds: return None
    up = next((i for i, k in enumerate(kinds) if k != "parent"), len(kinds))
    down = next((i for i, k in enumerate(kinds[up:]) if k != "child"), len(kinds) - up)
    return up, down, (up + down if up + down < len(kinds) else None)

def relationship(who, g, path, kinds):
    """The relationship of the path's last person to its first, in words (WORDS), read off the path's shape: ancestor,
    descendant, sibling, aunt or uncle, niece or nephew, cousin by degree and removal, "half" where the two sides share one
    parent only at the top of the path (the graph's parents of the two children there); by marriage through the first
    couple a spouse link joins; through a child the path goes down to and up from. {words, sentence, up, down, half,
    through: the people the sentence names}."""
    a, b = who[path[0]], who[path[-1]]
    if len(kinds) == 1 and kinds[0] == "spouse":
        w = by_sex("spouse", b["sex"]); return {"words": w, "sentence": f"{b['name']} is {a['name']}'s {w}", "up": 0, "down": 0, "half": False, "through": []}
    if "spouse" in kinds:
        i = kinds.index("spouse"); x, y = who[path[i]], who[path[i + 1]]
        w = f"related by marriage through {x['name']} and {y['name']}"
        return {"words": w, "sentence": f"{a['name']} and {b['name']} are {w}", "up": 0, "down": 0, "half": False, "through": [x["id"], y["id"]]}
    up, down, turn = shape(kinds)
    if turn is not None:
        c, p1, p2 = who[path[turn]], who[path[turn - 1]], who[path[turn + 1]]
        w = f"related through {c['name']}, a child of {p1['name']} and of {p2['name']}"
        return {"words": w, "sentence": f"{a['name']} and {b['name']} are {w}", "up": 0, "down": 0, "half": False, "through": [c["id"], p1["id"], p2["id"]]}
    half = False
    if up and down:                                               # the two children of the top person on the path: full when a second parent is theirs both
        c1, c2 = path[up - 1], path[up + 1]
        shared = {o for o, (k, _) in g.get(c1, {}).items() if k == "parent"} & {o for o, (k, _) in g.get(c2, {}).items() if k == "parent"}
        half = len(shared) < 2
    great = lambda n: "great-" * n
    if not down: w = by_sex("parent", b["sex"]) if up == 1 else great(up - 2) + "grand" + by_sex("parent", b["sex"])
    elif not up: w = by_sex("child", b["sex"]) if down == 1 else great(down - 2) + "grand" + by_sex("child", b["sex"])
    elif up == 1 and down == 1: w = by_sex("sibling", b["sex"])
    elif down == 1: w = great(up - 2) + by_sex("pibling", b["sex"])
    elif up == 1: w = great(down - 2) + by_sex("nibling", b["sex"])
    else:
        degree, removed = min(up, down) - 1, abs(up - down)
        w = f"{ORDINAL[degree - 1] if degree <= len(ORDINAL) else f'{degree}th'} cousins" + (f" {REMOVED[removed - 1] if removed <= len(REMOVED) else f'{removed} times'} removed" if removed else "")
    mutual = w.endswith("cousins") or w.endswith("removed")
    if half: w = ("half " if mutual else "half-") + w
    sentence = f"{a['name']} and {b['name']} are {w}" if mutual else f"{b['name']} is {a['name']}'s {w}"
    return {"words": w, "sentence": sentence, "up": up, "down": down, "half": half, "through": [path[up]] if up and down else []}

# ---------------------------------------------------------------- the chain
def chain(cat, who, g, accepted, path, cache, lists, stand):
    """One path as the tool prints it: its links (each the two people, the other's relation to the person, the family, whether
    it is accepted, its standing when it is and what would prove it when not), the relationship in words, and the chain's
    standing, its weakest link's by STANDING's order; the words of a path the file claims are the file's. stand caches each
    link's standing across the paths.
    Implements [rule.proof.6]."""
    links, kinds = [], []
    for x, y in zip(path, path[1:]):
        kind, fid = g[x][y]; kinds.append(kind)
        link = {"from": who[x], "to": who[y], "kind": kind, "relation": by_sex(kind, who[y]["sex"]), "family": fid,
                "accepted": y in accepted.get(x, {}) and accepted[x][y][0] == kind}
        if link["accepted"]:
            if frozenset((x, y)) not in stand: stand[frozenset((x, y))] = standing(cat, who, x, y, kind, accepted[x][y][1], cache)
            link["standing"] = stand[frozenset((x, y))]
        else: link["proves"] = proves(cat, who, x, y, kind, lists)
        links.append(link)
    weakest = max((l for l in links if l["accepted"]), key=lambda l: rank(l["standing"]), default=None)
    return {"people": [who[p]["name"] for p in path], "links": links, "relationship": relationship(who, g, path, kinds), "all_accepted": all(l["accepted"] for l in links),
            "standing": {"basis": weakest["standing"]["basis"], "link": [weakest["from"]["name"], weakest["to"]["name"]], "words": weakest["standing"]["words"]} if weakest else None,
            "owed": sum(1 for l in links if not l["accepted"])}

def chain_key(c):
    """The order chains come in: the fewest links, then the strongest weakest link, then the people's names."""
    return len(c["links"]), max((rank(l["standing"]) for l in c["links"] if l["accepted"]), default=(len(STANDING),)), c["people"]

def links_end(who, g, start):
    """The people a chain of the graph's links reaches from start whose parents nobody names in it: where the links end on
    that side, by name."""
    return sorted(who[p]["name"] for p in distances(g, start) if not any(k == "parent" for k, _ in g.get(p, {}).values()))

def build(cat, a, b):
    """The answer for two people, as a dict: the chain through accepted links (the shortest, among those the one whose
    weakest link is strongest), the other paths within SLACK links of it (at most five, in the same order), and the nearest
    path the file claims where no accepted path exists or the claimed one is shorter; with no path either way, where the
    links end on each side and, for one of the two whose own parents nobody names, the records that would.
    Implements [rule.proof.6]."""
    if a == b: sys.exit("name two different people")
    who, accepted, claimed = People(cat), graph(cat), graph(cat, word=True)
    cache, lists, stand = {}, {}, {}
    found = sorted((chain(cat, who, accepted, accepted, p, cache, lists, stand) for p in paths(accepted, a, b)), key=chain_key)
    best, others = (found[0], found[1:6]) if found else (None, [])
    nearest = min((chain(cat, who, claimed, accepted, p, cache, lists, stand) for p in paths(claimed, a, b, slack=0)), key=chain_key, default=None)
    if best and nearest and len(nearest["links"]) >= len(best["links"]): nearest = None
    out = {"a": who[a], "b": who[b], "accepted": bool(best), "chain": best, "others": others, "claimed": nearest}
    if not best and not nearest:
        out["links_end"] = {p: links_end(who, claimed, p) for p in (a, b)}
        out["parents_owed"] = {p: proves(cat, who, p, None, "parent", lists) for p in (a, b) if not any(k == "parent" for k, _ in claimed.get(p, {}).values())}
    return out

# ---------------------------------------------------------------- the written form
def rows_text(rows):
    """Checklist rows in words: the record with its instance and the checklist's status, "census household 1940 (held)"."""
    return ", ".join(f"{r['record']}{' ' + str(r['instance']) if r['instance'] else ''} ({r['status']})" for r in rows)

def link_line(l):
    """One link as a line: the other person, their relation to the person, and the standing or what is owed."""
    head = f"  {l['to']['name']} is the {l['relation']} of {l['from']['name']}: "
    if l["accepted"]: return head + l["standing"]["words"]
    return head + "not yet accepted; what would prove it: " + (rows_text(l["proves"]) or "no row of the checklist names a record for it")

def chain_lines(c, claimed=False):
    """A chain's lines: its links, the relationship and its standing (a claimed chain's relationship as the file claims it)."""
    out = [link_line(l) for l in c["links"]]
    out.append(f"  {'the relationship the file claims' if claimed else 'relationship'}: {c['relationship']['sentence']}")
    if c["standing"] and not claimed: out.append(f"  standing: its weakest link's, {c['standing']['link'][0]} to {c['standing']['link'][1]}: {c['standing']['words']}")
    return out

def render(r, all=False):
    """The answer as text: the chain through accepted links, link by link, its relationship and standing; with all, the other
    paths; the file's shorter or only claimed path with what each unaccepted link owes; or where the links end."""
    a, b, best = r["a"]["name"], r["b"]["name"], r["chain"]
    n = lambda c: f"{len(c['links'])} link{'s' if len(c['links']) != 1 else ''}"
    out = []
    if best:
        out.append(f"{a} and {b}, through accepted links, {n(best)}:"); out += chain_lines(best)
        if all:
            for c in r["others"]: out.append(f"another path, {n(c)}:"); out += chain_lines(c)
            if not r["others"]: out.append("every other path through accepted links lies more than a few links beyond it, or there is none")
    if r["claimed"]:
        c = r["claimed"]
        out.append(f"the file claims a shorter path, {n(c)}, {c['owed']} of them not yet accepted:" if best else
                   f"{a} and {b} are not yet joined by accepted links; the nearest path the file claims, {n(c)}, {c['owed']} of them not yet accepted:")
        out += chain_lines(c, claimed=True)
    if not best and not r["claimed"]:
        out.append(f"{a} and {b} are not yet joined by accepted links, nor by links the file claims; a path would open where the links end:")
        for pid, name in ((r["a"]["id"], a), (r["b"]["id"], b)):
            at = r["links_end"][pid]
            out.append(f"  on {name}'s side the links end at {', '.join(at) if at else 'nobody'}: nobody names their parents")
            if pid in r["parents_owed"]: out.append(f"  the records that would name {name}'s parents: {rows_text(r['parents_owed'][pid]) or 'none on the checklist'}")
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(description="Two people's relationship through the family links the tree has accepted: read-only, written by code.")
    ap.add_argument("a", metavar="person"); ap.add_argument("b", metavar="person"); ap.add_argument("--all", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--tree"); ap.add_argument("--db", default=DB)
    x = ap.parse_args()
    cx = connect(x.db); tree_id, _ = resolve_tree(cx, x.tree); cat = Catalog(cx, tree_id)
    r = build(cat, cat.find_person(x.a), cat.find_person(x.b))
    print(json.dumps(r, ensure_ascii=False, indent=1) if x.json else render(r, all=x.all))

if __name__ == "__main__":
    main()
