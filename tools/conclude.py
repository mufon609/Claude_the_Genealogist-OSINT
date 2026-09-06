#!/usr/bin/env python3
"""What an accepted persona writes on the tree, and the one decision that accepts a record's facts.

A person's decision that a persona is (or newly is) a person in the tree is recorded by the screen; the writes that follow
live here so the extractor can repeat them when a re-run of a parser carries a decided link forward. Everything written is
Undecided except in accept_record_facts, which is itself a person's decision.

- assert_facts: one Undecided assertion per persona fact onto the person (Name, Sex) or onto the person's event of that type,
  created from the fact when the person has none; a fact of type Unknown, Age or Identification Number asserts nothing.
- link_family: the family links the record states between this persona and personas already accepted as persons on the same
  record, each with an Undecided assertion on the artifact.
- create_person: a person in this tree from a persona, the name as written.
- accept_record_facts: Accepted on every Undecided assertion a held record makes on a person that does not disagree with a
  value already Accepted; what it did not touch is returned with the reason.
"""
import json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import dumps, ulid
from catalog import Catalog
from match import date_verdict, place_verdict

SKIP = ("Unknown", "Age", "Identification Number")      # about the record or the page, not facts of the person

class _q:
    """execute() on a fresh cursor each time, rows readable by column name whatever the caller's connection does, so a query
    inside a loop over another query's rows does not consume that loop."""
    def __init__(self, cx): self.cx = cx
    def execute(self, sql, args=()):
        c = self.cx.cursor(); c.row_factory = sqlite3.Row; return c.execute(sql, args)

def assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts):
    """Undecided assertions from a persona's facts to the person. Name and Sex assert the person row. An event fact asserts the
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
                      VALUES (?,?,?,?,?,?,?,'undecided',?,?,?)""", (ulid(), tree_id, kind, sid, f["id"], sha, cite, by, ts, dumps({"proposal": prop_id}))); n += 1
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
    the tree lacks it, in a family of the right shape) and carries an Undecided assertion on the artifact. A parent-child
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
                      VALUES (?,?,'family_member',?,?,?,?,'undecided',?,?,?)""", (ulid(), tree_id, sid, persona_id, sha, cite, by, ts, dumps({"proposal": prop_id})))
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

def record_facts(cx, tree_id, pid, sha):
    """The Undecided assertions a held record makes on a person, each with a label and, for an event, whether the record's
    value disagrees with a value already Accepted on that event (date compared as dates, place as the matcher compares it).
    What accept_record_facts would do, before it is done."""
    q = _q(cx)
    cat = Catalog(cx, tree_id); name = lambda i: q.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()["display_name"]
    out = []
    for a in q.execute("""SELECT a.id, a.subject_kind, a.subject_id, a.citation_text, pf.fact_type, pf.date_text, pf.date_start, pf.date_qualifier, pf.value_text, ps.raw
                           FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                           WHERE a.tree_id=? AND a.artifact_sha256=? AND a.status='undecided'
                           AND ((a.subject_kind='person' AND a.subject_id=?) OR (a.subject_kind='event' AND a.subject_id IN (SELECT event_id FROM event_participant WHERE person_id=?))
                                OR (a.subject_kind='family_member' AND a.subject_id LIKE ?)) ORDER BY a.subject_kind, a.asserted_at""", (tree_id, sha, pid, pid, f'%"{pid}"%')):
        item = {"id": a["id"], "disagrees": None, "link": a["subject_kind"] == "family_member"}
        if a["subject_kind"] == "family_member":
            fid, who, role = json.loads(a["subject_id"])
            item["fact"] = ("parents link" if role == "child" else "spouse link") if who == pid else f"{name(who)}'s spouse link"
            item["fact"] += f" ({a['citation_text']})"
        else:
            item["fact"] = " ".join(x for x in (a["fact_type"], a["date_text"] or a["value_text"] or "", a["raw"] or "") if x).strip()
            if a["subject_kind"] == "event" and q.execute("SELECT 1 FROM assertion WHERE subject_kind='event' AND subject_id=? AND status='accepted'", (a["subject_id"],)).fetchone():
                ev = q.execute("SELECT id, date_text, date_start, date_qualifier, place_id FROM event WHERE id=?", (a["subject_id"],)).fetchone()
                dv, _ = date_verdict({"start": a["date_start"], "text": a["date_text"], "qualifier": a["date_qualifier"]}, {"start": ev["date_start"], "text": ev["date_text"], "qualifier": ev["date_qualifier"]})
                pv = place_verdict(a["raw"], cat.place(ev["id"], ev["place_id"])["text"] if ev["place_id"] else None)
                if dv == "disagrees": item["disagrees"] = f"date: record {a['date_text']}, tree {ev['date_text']} (Accepted)"
                elif pv == "disagrees": item["disagrees"] = f"place: record {a['raw']}, tree {cat.place(ev['id'], ev['place_id'])['text']} (Accepted)"
        out.append(item)
    return out

def accept_record_facts(cx, tree_id, pid, sha, by, ts):
    """One decision by a person: Accepted on every Undecided assertion this held record makes on the person's facts that does
    not disagree with a value already Accepted. A family link the record states is left for its own decision, because the
    membership row stands for a couple and a record may name only one of them. Returns what was accepted and what was left,
    with the reason, and writes one audit row naming the record."""
    q = _q(cx)
    accepted, left = [], []
    for item in record_facts(cx, tree_id, pid, sha):
        if item["disagrees"]: left.append({"fact": item["fact"], "reason": item["disagrees"]}); continue
        if item["link"]: left.append({"fact": item["fact"], "reason": "a family link is decided on its own: the row stands for a couple and a record may name one of them"}); continue
        q.execute("UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=? WHERE id=?", (by, ts, item["id"])); accepted.append(item["fact"])
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "accept", "person", pid, dumps({"record": sha, "accepted": accepted, "left": left})))
    return {"accepted": accepted, "left": left}
