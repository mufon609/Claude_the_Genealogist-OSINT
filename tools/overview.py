"""The tree as confirmed: the people the owner has accepted, laid out from the home person upward, one row per generation,
and what waits on each. Shared by the screen's overview and `tools/tree.py overview`.

Confirmed means: the home person, and every person reached from them by a parents link the owner accepted (the family_member
assertions behind it accepted, on a record or on the owner's word). The walk stops at the last accepted link; beyond it the
file's claim of parents is named on the card as a claim, and the people it names stay outside until a decision puts them in.
"""
from treelib import dumps
from catalog import Catalog
from facts import KEY_FACTS, fact_status

def person_card(cx, cat, pid):
    """One person as the overview shows them: name, years, how many key facts are accepted, the spouses the owner accepted
    with the marriage and divorce dates accepted on the family, the spouses the file claims as claims, and what waits."""
    name, sex = cx.execute("SELECT display_name, sex FROM person WHERE id=?", (pid,)).fetchone()
    ev = cat.events(pid); b = next((e["year"] for e in ev if e["type"] == "Birth"), None); d = next((e["year"] for e in ev if e["type"] == "Death"), None)
    fam = cat.family(pid); spouses, claimed = [], []
    for f in fam["families"]:
        if not f["spouse_id"]: continue
        if cat.basis("family_member", dumps([f["id"], pid, "partner"])) == "accepted" and cat.basis("family_member", dumps([f["id"], f["spouse_id"], "partner"])) == "accepted":
            spouses.append({"id": f["spouse_id"], "name": f["spouse"], "married": [m["year"] for m in f["marriages"] if m["year"] and m["basis"] == "accepted"],
                            "divorced": [x["date"] or str(x["year"]) for x in f["divorces"] if x["basis"] == "accepted"]})
        else: claimed.append(f["spouse"])
    return {"id": pid, "name": name, "sex": sex, "span": [b, d], "accepted": sum(1 for f in KEY_FACTS if fact_status(cx, pid, f) == "accepted"), "key_facts": len(KEY_FACTS),
            "spouses": spouses, "claimed_spouses": claimed, **cat.waiting(pid)}

def people(cx, tree_id, q=""):
    cat = Catalog(cx, tree_id)
    return [person_card(cx, cat, pid) for pid, in cx.execute("SELECT id FROM person WHERE tree_id=? AND merged_into IS NULL AND display_name LIKE ? ORDER BY display_name", (tree_id, f"%{q}%"))]

from conclude import trusted_evidence

def link_trusted(cx, tree_id, pid):
    """Whether the person's parents link rests on a trusted record (T1–T3) or on the owner's own word, rather than on a page
    anyone can edit alone."""
    rows = [dumps([fid, pid, "child"]) for fid, in cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='child'", (pid,))]
    return trusted_evidence(cx, tree_id, "family_member", rows)

def overview(cx, tree_id):
    """The tree overview: the people the owner has confirmed, laid out from the home person upward one row per generation, a
    card's parents above it (father then mother). The walk follows a parents link only where the owner accepted it, so the tree
    ends at the last accepted link; beyond it the file's claim of parents is named on the card as a claim, and the people it
    names stay out of the tree until a decision puts them in. A link resting on an editable source alone is said so."""
    cat = Catalog(cx, tree_id)
    home = cx.execute("SELECT home_person_id FROM tree WHERE id=?", (tree_id,)).fetchone()[0]
    if not home: return {"home": None, "generations": [], "others": people(cx, tree_id), "unconfirmed": 0}
    gens, seen, row = [], set(), [home]
    while row and len(gens) < 12:
        cards = []
        for pid in row:
            if pid in seen: continue
            seen.add(pid); c = person_card(cx, cat, pid)
            parents = sorted(cat.family(pid)["parents"], key=lambda x: 0 if (cx.execute("SELECT sex FROM person WHERE id=?", (x[0],)).fetchone() or [""])[0] == "M" else 1)
            accepted = fact_status(cx, pid, "parents") == "accepted"
            c["parents"] = [p for p, _ in parents] if accepted else []
            c["link_trusted"] = link_trusted(cx, tree_id, pid) if accepted else None
            c["claimed_parents"] = [n for _, n in parents] if parents and not accepted else []
            cards.append(c)
        gens.append(cards); row = [p for c in cards for p in c["parents"]]
    others = [c for c in people(cx, tree_id) if c["id"] not in seen]
    return {"home": home, "generations": gens, "others": [c for c in others if c["documents"] or c["conflicts"]], "unconfirmed": len(others)}


def render(o, cx):
    """The overview as text: one line per person, generation by generation, then the count of the file's people outside."""
    labels = ["you", "parents", "grandparents", "great-grandparents", "great-great-grandparents"]
    out = []
    if not o["home"]: return "no home person set: tools/tree.py home \"<person>\""
    for i, gen in enumerate(o["generations"]):
        out.append(f"-- {labels[i] if i < len(labels) else f'{i} generations back'}")
        for c in gen:
            waits = [f"{c['documents']} document(s) to decide" if c["documents"] else None, f"{c['conflicts']} conflict(s)" if c["conflicts"] else None,
                     "rests on sources anyone can edit" if c["editable_only"] else None, "parents link rests on an editable source" if c["link_trusted"] is False else None]
            sp = "; ".join(f"spouse {x['name']}" + (f" m. {', '.join(map(str, x['married']))}" if x["married"] else "") for x in c["spouses"])
            claim = ("the file names parents " + " and ".join(c["claimed_parents"]) + ": not confirmed") if c["claimed_parents"] else ("" if c["parents"] else "no parents claimed")
            out.append(f"  {c['name']} ({c['span'][0] or '?'}-{c['span'][1] or ''}) [{c['id'][-6:]}]  {c['accepted']} of {c['key_facts']} key facts" + (f"; {sp}" if sp else "") +
                       ("; " + "; ".join(w for w in waits if w) if any(waits) else "") + (f"\n      edge: {claim}" if claim else ""))
    out.append(f"-- {o['unconfirmed']} more people in the file, not connected by an accepted link; {len(o['others'])} of them with a document or a conflict waiting")
    return "\n".join(out)
