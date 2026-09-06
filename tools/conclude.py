#!/usr/bin/env python3
"""What a decision about a document writes on the tree, and the standing rule that takes the decision when it is certain.

The owner decides documents, not facts: one decision per record about a person, is this them. Yes accepts everything the
record states about the person: its facts become Accepted assertions on the person's events and attributes (created from the
record when the tree had none), and the family links it states with people already matched on the same record are Accepted
too. Where the record disagrees with the tree's own value the record's statement is still accepted as what that record says,
the tree's value stays, and the difference is a conflict question the generator raises (Catalog.disagreements). A new person
is never created without the owner. Anything less certain than the rule below is a card for the owner.

The standing rule (docs/RESEARCH-WORKFLOW.md §0 and §5–7): a record of a kind that identifies a person fully is accepted as
the person's when the name agrees with the accepted name, at least two accepted facts agree (birth date, death date, a
burial or death place, a stated relationship to someone already matched on the record), and nothing compared disagrees.
The rule acts on the owner's word, is recorded as such on the proposal and in the audit log, and the owner can reject what
it accepted: the link and every assertion it wrote turn rejected.

- decide: a person's (or the rule's) decision on a proposal, with everything that follows from it.
- match_record: the matcher on an extraction, then the rule on every proposal it wrote.
- rule_accepts: whether the rule takes a proposal, and why or why not, in words.
- settle: a match accepted before the document rule gets its assertions Accepted as the rule now says.
- assert_facts, link_family, create_person: the writes themselves, shared with the extractor when a re-run carries a link.
"""
import json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import dumps, now, ulid
from catalog import Catalog
from catalog import date_verdict, place_verdict
from match import REL_OF, candidate, compare, match, personas_of
from plan import plan_person

SKIP = ("Unknown", "Age", "Identification Number")      # about the record or the page, not facts of the person
AUTOMATED = ("findagrave-memorial", "familysearch-record", "nara-1950-schedule")   # parsers of documents that identify a person fully (§0)
ANSWERABLE = ("missing_parents", "unverified_claim", "missing_fact")

class _q:
    """execute() on a fresh cursor each time, rows readable by column name whatever the caller's connection does, so a query
    inside a loop over another query's rows does not consume that loop."""
    def __init__(self, cx): self.cx = cx
    def execute(self, sql, args=()):
        c = self.cx.cursor(); c.row_factory = sqlite3.Row; return c.execute(sql, args)

def assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts):
    """Accepted assertions from a persona's facts to the person, the document having been accepted as theirs. Name and Sex assert the person row. An event fact asserts the
    person's event of that type and year, created from the fact's date when there is none; an attribute fact (Occupation,
    Inscription, Religion, ...) asserts the person's attribute of that type with the same value, created when there is none.
    A fact the same record already asserts on the same subject with the same type, date, value and place is not asserted
    again, so a re-extraction adds only what is new. Returns how many were written."""
    q = _q(cx)
    n = 0
    sha = q.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()["artifact_sha256"]
    a = q.execute("SELECT c.name, ar.original_filename FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id WHERE ar.sha256=?", (sha,)).fetchone()
    cite = a["name"] or a["original_filename"] or sha[:12]
    def assert_(kind, sid, f):
        nonlocal n
        if q.execute("""SELECT 1 FROM assertion a JOIN persona_fact q ON q.id=a.persona_fact_id WHERE a.subject_kind=? AND a.subject_id=? AND a.artifact_sha256=?
                         AND q.fact_type=? AND coalesce(q.date_text,'')=coalesce(?,'') AND coalesce(q.value_text,'')=coalesce(?,'') AND coalesce(q.place_string_id,'')=coalesce(?,'')""",
                      (kind, sid, sha, f["fact_type"], f["date_text"], f["value_text"], f["place_string_id"])).fetchone(): return
        q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                      VALUES (?,?,?,?,?,?,?,'accepted',?,?,?)""", (ulid(), tree_id, kind, sid, f["id"], sha, cite, by, ts, dumps({"proposal": prop_id}))); n += 1
    for f in q.execute("""SELECT pf.id, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.calendar, pf.place_string_id, et.kind
                           FROM persona_fact pf JOIN event_type et ON et.name=pf.fact_type WHERE pf.persona_id=?""", (persona_id,)):
        if f["fact_type"] in ("Name", "Sex"): assert_("person", person_id, f); continue
        if f["fact_type"] in SKIP or f["kind"] not in ("event", "attribute"): continue
        if f["kind"] == "event":
            fy = (f["date_start"] or f["date_end"] or "")[:4]           # an event corresponds by type and year; an undated fact only to an undated event
            events = [e for e in q.execute("""SELECT e.id, e.date_start, e.date_end FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                               WHERE ep.person_id=? AND e.event_type=?""", (person_id, f["fact_type"]))
                      if (e["date_start"] or e["date_end"] or "")[:4] == fy]
        else:                                                            # an attribute corresponds by type and value
            events = q.execute("""SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                   WHERE ep.person_id=? AND e.event_type=? AND coalesce(e.description,'')=coalesce(?,'')""", (person_id, f["fact_type"], f["value_text"])).fetchall()
        if not events:
            eid = ulid()
            q.execute("""INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,description,created_at,updated_at)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (eid, tree_id, f["fact_type"], f["date_text"], f["date_start"], f["date_end"], f["date_qualifier"], f["calendar"],
                                                              f["value_text"] if f["kind"] == "attribute" else None, ts, ts))
            q.execute("INSERT INTO event_participant (id,event_id,person_id,role) VALUES (?,?,?,'primary')", (ulid(), eid, person_id))
            events = [{"id": eid}]
        for e in events: assert_("event", e["id"], f)
    return n, sha

def create_person(cx, tree_id, persona_id, ts):
    """A person in this tree from a persona: the name as written split into given names and a surname; a maiden name the
    record marks becomes the birth surname and the written surname a married name. Returns the person id."""
    q = _q(cx)
    pe = q.execute("SELECT name_text, sex, region_json FROM persona WHERE id=?", (persona_id,)).fetchone()
    region = json.loads(pe["region_json"] or "{}"); parts = (pe["name_text"] or "").split()
    given, surname = (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else (pe["name_text"], None)
    pid = ulid()
    q.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tree_id, pe["sex"], pe["name_text"], ts, ts))
    if region.get("maiden") and surname and region["maiden"] != surname:
        g = given.replace(region["maiden"], "").strip()
        q.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (ulid(), pid, g, region["maiden"], f"{region['maiden']}, {g}".lower()))
        q.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'married',?,?,0,?)", (ulid(), pid, g, surname, f"{surname}, {g}".lower()))
    else:
        q.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (ulid(), pid, given, surname, f"{surname or ''}, {given}".lower()))
    return pid

def new_family(cx, tree_id, partner, ts):
    q = _q(cx)
    fid = ulid(); q.execute("INSERT INTO family (id,tree_id,created_at,updated_at) VALUES (?,?,?,?)", (fid, tree_id, ts, ts))
    q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid, partner)); return fid

def link_family(cx, tree_id, pid, persona_id, sha, prop_id, by, ts):
    """Family links from the record's own relations, for a matched person as for a new one: where the record says this persona
    is the child, parent or spouse of a persona already accepted as a person in this tree, the membership exists (created when
    the tree lacks it, in a family of the right shape) and carries an Accepted assertion on the artifact. A parent-child
    relation is evidence on the child's membership; a spouse relation on both partners'. A sibling gives no membership.
    Returns the links written: person, role, the other person, the page's own word, whether the membership is new."""
    q = _q(cx)
    out = []
    def person_of(x):
        r = q.execute("SELECT pp.person_id FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?", (x, tree_id)).fetchone()
        return r["person_id"] if r else None
    def member(fid, who, role):
        if q.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, who, role)).fetchone(): return False
        q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (fid, who, role)); return True
    def assert_(fid, who, role, other, as_written, new):
        sid, cite = dumps([fid, who, role]), f"{as_written} on the record"
        if q.execute("SELECT 1 FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256=? AND citation_text=?", (sid, sha, cite)).fetchone(): return
        q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                      VALUES (?,?,'family_member',?,?,?,?,'accepted',?,?,?)""", (ulid(), tree_id, sid, persona_id, sha, cite, by, ts, dumps({"proposal": prop_id})))
        out.append({"family": fid, "person": who, "role": role, "of": other, "as": as_written, "new": new})
    one = lambda sql, args: next((f for f, in q.execute(sql, args)), None)
    for r in q.execute("""SELECT kind, value_text, persona_id, related_persona_id FROM persona_relation
                           WHERE (persona_id=? OR related_persona_id=?) AND kind IN ('child','parent','spouse')""", (persona_id, persona_id)).fetchall():
        mine = r["persona_id"] == persona_id                                   # (X, kind, Y) reads: X is the <kind> of Y
        other = person_of(r["related_persona_id"] if mine else r["persona_id"])
        if not other or other == pid: continue
        as_written = r["value_text"] or r["kind"]
        if r["kind"] == "spouse":
            fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                         WHERE fm.person_id=? AND fm.role='partner'""", (other, pid))
            if fid is None: fid = one("""SELECT fm.family_id FROM family_member fm WHERE fm.person_id=? AND fm.role='partner'
                                         AND (SELECT COUNT(*) FROM family_member x WHERE x.family_id=fm.family_id AND x.role='partner')=1""", (other,))
            if fid is None: fid = new_family(cx, tree_id, other, ts)
            assert_(fid, pid, "partner", other, as_written, member(fid, pid, "partner")); assert_(fid, other, "partner", pid, as_written, False)
            continue
        child = pid if (r["kind"] == "child") == mine else other; parent = other if child == pid else pid
        fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                     WHERE fm.person_id=? AND fm.role='child'""", (parent, child)); new = False
        if fid is None:
            fid = one("""SELECT fm.family_id FROM family_member fm WHERE fm.person_id=? AND fm.role='child'
                         AND (SELECT COUNT(*) FROM family_member x WHERE x.family_id=fm.family_id AND x.role='partner')<2""", (child,))
            if fid is not None: new = member(fid, parent, "partner")
            else: fid = one("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (parent,)) or new_family(cx, tree_id, parent, ts); new = member(fid, child, "child")
        assert_(fid, child, "child", parent, as_written, new)
    return out

def record_says(cx, tree_id, pid, sha):
    """What a held record states about a person, as the assertions it made: each with a label and, for an event, whether the
    record's value disagrees with the event's own value (date compared as dates, place as the matcher compares it)."""
    q = _q(cx)
    cat = Catalog(cx, tree_id); name = lambda i: q.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()["display_name"]
    out = []
    for a in q.execute("""SELECT a.id, a.status, a.subject_kind, a.subject_id, a.citation_text, pf.fact_type, pf.date_text, pf.date_start, pf.date_qualifier, pf.value_text, ps.raw
                          FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          WHERE a.tree_id=? AND a.artifact_sha256=?
                          AND ((a.subject_kind='person' AND a.subject_id=?) OR (a.subject_kind='event' AND a.subject_id IN (SELECT event_id FROM event_participant WHERE person_id=?))
                               OR (a.subject_kind='family_member' AND a.subject_id LIKE ?)) ORDER BY a.subject_kind, a.asserted_at""", (tree_id, sha, pid, pid, f'%"{pid}"%')):
        item = {"id": a["id"], "status": a["status"], "disagrees": None, "link": a["subject_kind"] == "family_member"}
        if item["link"]:
            fid, who, role = json.loads(a["subject_id"])
            item["fact"] = (("parents link" if role == "child" else "spouse link") if who == pid else f"{name(who)}'s spouse link") + f" ({a['citation_text']})"
        else:
            item["fact"] = " ".join(x for x in (a["fact_type"], a["date_text"] or a["value_text"] or "", a["raw"] or "") if x).strip()
            if a["subject_kind"] == "event":
                ev = q.execute("SELECT id, date_text, date_start, date_qualifier, place_id FROM event WHERE id=?", (a["subject_id"],)).fetchone()
                dv, _ = date_verdict({"start": a["date_start"], "text": a["date_text"], "qualifier": a["date_qualifier"]}, {"start": ev["date_start"], "text": ev["date_text"], "qualifier": ev["date_qualifier"]})
                tp = cat.place(ev["id"], ev["place_id"])["text"] if ev["place_id"] else None
                if dv == "disagrees": item["disagrees"] = f"date: the tree says {ev['date_text']}"
                elif place_verdict(a["raw"], tp) == "disagrees": item["disagrees"] = f"place: the tree says {tp}"
        out.append(item)
    return out

def settle(cx, tree_id, prop_id, by, ts):
    """A match accepted before the document rule: every assertion the decision wrote turns Accepted, as accepting the document
    now does. Returns how many changed."""
    q = _q(cx)
    n = q.execute("""UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=? WHERE tree_id=? AND status='undecided' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?""",
                  (by, ts, tree_id, prop_id)).rowcount
    if n: q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                    (ulid(), tree_id, ts, by, "accept", "proposal", prop_id, dumps({"settled": n})))
    return n

def answer_questions(cx, tree_id, pid, prop_id, by):
    """Regenerate the person's plan; a question of an answerable kind that the regeneration closes was answered by the
    proposal: closed_reason answered, answered_by_proposal_id set. Other kinds stay as the planner closed them."""
    q = _q(cx)
    st = plan_person(cx, tree_id, pid, by); answered = []
    for qid in st.get("closed", []):
        r = q.execute("SELECT kind FROM research_question WHERE id=?", (qid,)).fetchone()
        if r and r["kind"] in ANSWERABLE:
            q.execute("UPDATE research_question SET closed_reason='answered', answered_by_proposal_id=? WHERE id=?", (prop_id, qid)); answered.append(qid)
    return answered

def decide(cx, tree_id, prop_id, status, by, note=None):
    """A decision on a proposal: is this record's persona this person (persona_match), or a person the tree does not have
    (new_person). Accepted: the link accepted, every fact the record states accepted onto the person (assert_facts), the
    family links it states with persons already matched on it accepted (link_family), the plans of the person and of the
    person the record was fetched for regenerated and the questions that closes marked answered. Rejected: the link rejected;
    for a new person nothing but the proposal. A proposal the rule accepted can be rejected by a person afterwards: the link
    and every assertion the rule wrote turn rejected. Returns what was written, or an error."""
    q = _q(cx)
    p = q.execute("SELECT * FROM proposal WHERE id=? AND tree_id=?", (prop_id, tree_id)).fetchone()
    if not p or p["kind"] not in ("persona_match", "new_person") or status not in ("accepted", "rejected"): return {"error": "not a persona match or new person, or bad status"}
    pay = json.loads(p["payload_json"]); persona_id, person_id = pay["persona_id"], pay.get("person_id"); ts = now(); n = 0; members = []
    if p["status"] != "undecided":
        if not (p["status"] == "accepted" and status == "rejected" and (p["decided_by"] or "").startswith("rule:")): return {"error": "already decided"}
        n = q.execute("UPDATE assertion SET status='rejected', asserted_by=?, asserted_at=? WHERE tree_id=? AND json_valid(notes) AND json_extract(notes,'$.proposal')=?", (by, ts, tree_id, prop_id)).rowcount
    q.execute("UPDATE proposal SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE id=?", (status, by, ts, note, prop_id))
    if p["kind"] == "new_person" and status == "accepted": person_id = create_person(cx, tree_id, persona_id, ts)
    if person_id:
        q.execute("INSERT OR REPLACE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (person_id, persona_id, status, prop_id, by, ts))
    answered = []
    if status == "accepted":
        n, sha = assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts)
        members = link_family(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts)
    for pid in dict.fromkeys([person_id, pay.get("subject_person_id")]):
        if pid: answered += answer_questions(cx, tree_id, pid, prop_id, by)
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "accept" if status == "accepted" else "reject", "proposal", prop_id,
               dumps({"kind": p["kind"], "persona": persona_id, "person": person_id, "assertions": n, "memberships": members, "answered": answered, "note": note})))
    return {"ok": True, "status": status, "kind": p["kind"], "person": person_id, "persona": persona_id, "assertions": n, "memberships": members, "answered": answered, "note": note}

def rule_accepts(cx, tree_id, prop):
    """Whether the standing rule takes a persona-match proposal, and why, in words: (True, reason) or (False, why not)."""
    q = _q(cx)
    pay = json.loads(prop["payload_json"]); pid, sha = pay.get("person_id"), pay["artifact_sha256"]
    if prop["kind"] != "persona_match" or not pid: return False, "a new person is the owner's decision"
    x = q.execute("""SELECT x.name, c.name AS collection FROM extraction e JOIN extractor x ON x.id=e.extractor_id JOIN artifact ar ON ar.sha256=e.artifact_sha256
                     LEFT JOIN collection c ON c.id=ar.collection_id WHERE e.id=?""", (pay["extraction_id"],)).fetchone()
    if not x or x["name"] not in AUTOMATED: return False, f"a {x['name'] if x else 'record'} is a hint until a person reads it"
    yr = re.search(r"\b(1[78]\d\d)\b", x["collection"] or "")
    if x["name"] == "familysearch-record" and yr and int(yr.group(1)) < 1850: return False, "a census before 1850 names only the head"
    cat = Catalog(cx, tree_id)
    persona = next((p for p in personas_of(cx, pay["extraction_id"]) if p["id"] == pay["persona_id"]), None)
    if not persona: return False, "persona not found"
    chosen = {r["persona_id"]: candidate(cat, r["person_id"]) for r in q.execute("""SELECT pp.persona_id, pp.person_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                    JOIN person o ON o.id=pp.person_id WHERE pe.extraction_id=? AND pp.status='accepted' AND o.tree_id=?""", (pay["extraction_id"], tree_id))}
    cand = candidate(cat, pid); fits, agree, disagree, absent = compare(cat, persona, cand, chosen)
    if disagree: return False, "disagrees: " + "; ".join(disagree)
    if not any(a.startswith("given name agrees") for a in agree) or not any(a.startswith("surname agrees") for a in agree): return False, "the name does not agree in full"
    if cat.basis("person", pid) != "accepted": return False, "the name is not accepted yet"
    ev = cat.events(pid); basis = cat.key_fact_basis(pid, ev); points = []
    for a in agree:
        if a.startswith("birth date agrees") and basis.get("birth") == "accepted": points.append("birth date")
        if a.startswith("death date agrees") and basis.get("death") == "accepted": points.append("death date")
        if a.startswith("death place agrees") and basis.get("death") == "accepted": points.append("death place")
        if a.startswith("burial place agrees") and any(e["type"] == "Burial" and e["basis"] == "accepted" for e in ev): points.append("burial place")
    fam = cat.family(pid)
    for kind, other_pid, _, other_name in persona["relations"]:
        oc = chosen.get(other_pid); group = {"child": "parents", "parent": "children", "spouse": "spouses"}.get(kind)
        if oc and group and any(rid == oc["id"] for rid, _ in fam[group]) and cat.link_basis(pid, group) == "accepted": points.append(f"{REL_OF[group]} {other_name}")
    if len(points) < 2: return False, "agrees with the accepted name" + (f" and {points[0]}" if points else "") + " only; two accepted facts are needed"
    return True, "agrees with your accepted name, " + " and ".join(points) + "; nothing disagrees"

def match_record(cx, eid, by):
    """The matcher on an extraction, then the standing rule on every proposal it wrote: those it takes are accepted on the
    owner's behalf, recorded as the rule. Returns (proposals written, proposals the rule accepted with the reason)."""
    q = _q(cx)
    written = match(cx, eid, by); taken = []
    for prop_id, kind, name, person_id in written:
        p = q.execute("SELECT * FROM proposal WHERE id=?", (prop_id,)).fetchone()
        ok, why = rule_accepts(cx, p["tree_id"], p)
        if ok: decide(cx, p["tree_id"], prop_id, "accepted", f"rule:agrees-with-accepted for {by}", note=why); taken.append((prop_id, name, why))
    return written, taken
