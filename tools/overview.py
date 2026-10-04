"""The tree as confirmed: the people the owner has accepted, laid out from the home person upward, one row per generation,
and what waits on each. Shared by the screen's overview and `tools/tree.py overview`.

Confirmed means: the home person, and every person reached from them by a parents link the owner accepted (the family_member
assertions behind it accepted, on a record or on the owner's word). The walk stops at the last accepted link; beyond it the
file's claim of parents is named on the card as a claim, and the people it names stay outside until a decision puts them in.
A card's years and a marriage's are the events' own; one no accepted statement gives is said to be a claim.
The summary says where the tree comes from (origins): the people the file brought in and those a record did, and the
accepted documents by what fetched them, so the owner sees whether the file or the evidence is building the tree.
"""
import json
from treelib import dumps
from catalog import Catalog
from facts import KEY_FACTS, fact_status

def person_card(cx, cat, pid):
    """One person as the overview shows them: name, years, how many key facts are accepted, the spouses the owner accepted
    with the marriage and divorce dates on the family that an accepted statement stands behind, the spouses the file claims as
    claims, and what waits. A year, or a marriage's or a divorce's date, shown though no accepted statement gives it is said
    to be a claim (docs/RESEARCH-WORKFLOW.md §5–7, what of an event's value is accepted): claimed_years, and ", a claim" on
    the marriage's or divorce's own date."""
    name, sex = cx.execute("SELECT display_name, sex FROM person WHERE id=?", (pid,)).fetchone()
    ev = cat.events(pid)
    be, de = next((e for e in ev if e["type"] == "Birth"), None), next((e for e in ev if e["type"] == "Death"), None)
    b, d = be["year"] if be else None, de["year"] if de else None
    def given(e, level=("whole", "month", "year")):
        """Whether an accepted statement gives the event's date to one of these levels (Catalog.value_basis)."""
        r = cat.value_basis(e["id"]) if e["basis"] == "accepted" else None
        return bool(r and r["date"] and r["date"]["level"] in level)
    fam = cat.family(pid); spouses, claimed = [], []
    for f in fam["families"]:
        if not f["spouse_id"]: continue
        if cat.basis("family_member", dumps([f["id"], pid, "partner"])) == "accepted" and cat.basis("family_member", dumps([f["id"], f["spouse_id"], "partner"])) == "accepted":
            married = [m["year"] if given(m) else f"{m['year']}, a claim" for m in f["marriages"] if m["year"] and m["basis"] == "accepted"]
            divorced = [(x["date"] or str(x["year"])) + ("" if given(x, ("whole",)) else ", a claim") for x in f["divorces"] if x["basis"] == "accepted"]
            spouses.append({"id": f["spouse_id"], "name": f["spouse"], "married": married, "divorced": divorced})
        else: claimed.append(f["spouse"])
    return {"id": pid, "name": name, "sex": sex, "span": [b, d], "claimed_years": [e["year"] for e in (be, de) if e and e["year"] and not given(e)],
            "accepted": sum(1 for f in KEY_FACTS if fact_status(cx, pid, f) == "accepted"), "key_facts": len(KEY_FACTS),
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

def origins(cx, tree_id):
    """Where the tree comes from. The people (merged ones aside) by what brought them in: the file (the import gives each
    person the file's own record id, external_id *gedcom_xref) or a record (a decision on a record's card created them,
    conclude.create_person). The accepted documents (a record a person of the tree is accepted on, on its current reading;
    the file itself aside) by what fetched them, read from the runs that first held the document (its earliest run's
    moment; a reopen's row and a household's bookkeeping row aside) and their steps' field bases: by hand (a run on the
    owner's word, a step the owner wrote, basis owner, or no run at all), else a fetch step on the file's citation (basis
    citation), else a fetch step on a lead a held record made (basis record: a memorial a page lists, a results row's own
    record, a photograph), else a search step. One page reaching several steps at once is counted by the first of those."""
    from log_search import HOUSEHOLD, ON_WORD, REOPENED
    people = {"file": 0, "record": 0}
    for xref, in cx.execute("""SELECT EXISTS (SELECT 1 FROM external_id x WHERE x.entity_kind='person' AND x.entity_id=p.id AND x.system LIKE '%gedcom_xref')
                               FROM person p WHERE p.tree_id=? AND p.merged_into IS NULL""", (tree_id,)):
        people["file" if xref else "record"] += 1
    ORDER = ("hand", "citation", "lead", "search")
    first = {}                                                   # sha256 -> (moment of its earliest run, the classes of the runs at that moment)
    for arts, at, note, kind, q in cx.execute("""SELECT sl.artifacts_json, sl.executed_at, sl.notes, sp.kind, sp.query_json FROM search_log sl LEFT JOIN search_plan sp ON sp.id=sl.plan_step_id
                                                 WHERE sl.tree_id=? AND sl.artifacts_json IS NOT NULL AND sl.superseded_by IS NULL ORDER BY sl.executed_at, sl.id""", (tree_id,)):
        if (note or "").startswith((REOPENED, HOUSEHOLD)): continue
        bases = {v.get("basis") for v in json.loads(q or "{}").values() if isinstance(v, dict)}
        cls = "hand" if kind is None or (note or "").startswith(ON_WORD) or "owner" in bases else "search" if kind == "search" else "lead" if "record" in bases else "citation"
        for sha in json.loads(arts or "[]"):
            if first.setdefault(sha, (at, set()))[0] == at: first[sha][1].add(cls)
    docs = dict.fromkeys(ORDER, 0)
    for sha, in cx.execute("""SELECT DISTINCT pe.artifact_sha256 FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN extraction e ON e.id=pe.extraction_id
                              JOIN person p ON p.id=pp.person_id WHERE pp.status='accepted' AND p.tree_id=? AND e.superseded_by IS NULL
                              AND pe.artifact_sha256 NOT IN (SELECT artifact_sha256 FROM tree_import WHERE tree_id=?)""", (tree_id, tree_id)):
        classes = first.get(sha, (None, {"hand"}))[1]
        docs[next(c for c in ORDER if c in classes)] += 1
    return {"people": people, "documents": docs}

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
    return {"home": home, "generations": gens, "others": [c for c in others if c["documents"] or c["conflicts"]], "unconfirmed": len(others), "origins": origins(cx, tree_id)}


def render(o, cx):
    """The overview as text: one line per person, generation by generation, then the count of the file's people outside and
    where the tree comes from (origins)."""
    labels = ["you", "parents", "grandparents", "great-grandparents", "great-great-grandparents"]
    out = []
    if not o["home"]: return "no home person set: tools/tree.py home \"<person>\""
    for i, gen in enumerate(o["generations"]):
        out.append(f"-- {labels[i] if i < len(labels) else f'{i} generations back'}")
        for c in gen:
            waits = [f"{c['documents']} document(s) to decide" if c["documents"] else None, f"{c['conflicts']} conflict(s)" if c["conflicts"] else None,
                     f"{c['leads']} lead(s) waiting" if c["leads"] else None,
                     "rests on sources anyone can edit" if c["editable_only"] else None, "parents link rests on an editable source" if c["link_trusted"] is False else None]
            sp = "; ".join(f"spouse {x['name']}" + (f" m. {', '.join(map(str, x['married']))}" if x["married"] else "") for x in c["spouses"])
            claim = ("the file names parents " + " and ".join(c["claimed_parents"]) + ": not confirmed") if c["claimed_parents"] else ("" if c["parents"] else "no parents claimed")
            years = (f"; {' and '.join(map(str, c['claimed_years']))} a claim") if c["claimed_years"] else ""   # a year no accepted statement gives
            out.append(f"  {c['name']} ({c['span'][0] or '?'}-{c['span'][1] or ''}) [{c['id'][-6:]}]  {c['accepted']} of {c['key_facts']} key facts" + years + (f"; {sp}" if sp else "") +
                       ("; " + "; ".join(w for w in waits if w) if any(waits) else "") + (f"\n      edge: {claim}" if claim else ""))
    out.append(f"-- {o['unconfirmed']} more people in the file, not connected by an accepted link; {len(o['others'])} of them with a document or a conflict waiting")
    p, d = o["origins"]["people"], o["origins"]["documents"]
    out.append(f"-- where the tree comes from: {p['file'] + p['record']} people, {p['file']} brought in by the file and {p['record']} by a record")
    out.append(f"   {sum(d.values())} accepted documents, {d['citation']} fetched for the file's citations, {d['lead']} for leads in held records, {d['search']} by searches, {d['hand']} by hand")
    return "\n".join(out)
