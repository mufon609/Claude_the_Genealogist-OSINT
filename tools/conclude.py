#!/usr/bin/env python3
"""What a decision about a document writes on the tree, and the standing rule that takes the decision when it is certain.

The owner decides documents, not facts: one decision per record about a person, is this them. Yes accepts everything the
record states about the person: its facts become Accepted assertions on the person's events and attributes (created from the
record when the tree had none), and the family links it states with people already matched on the same record are Accepted
too. Where the record disagrees with the tree's own value the record's statement is still accepted as what that record says,
the tree's value stays, and the difference is a conflict question the generator raises (Catalog.disagreements). A new person
is never created without the owner. Anything less certain than the rule below is a card for the owner.

The standing rule (docs/RESEARCH-WORKFLOW.md §0 and §5–7): a record of a kind that identifies a person fully, from a source
nobody can edit at will (T1–T3), is accepted as the person's when the name agrees with the accepted name, at least two
accepted facts agree (birth date, death date, a burial or death place, a stated relationship to someone the record names who
fits a relative the tree already links), each resting on a trusted source or on the owner's own word, and nothing compared
disagrees; a date agreeing to the day, and a relationship the tree holds on trusted evidence, each count double. A page anyone
can edit (T4: a Find a Grave memorial, a WikiTree profile) identifies a person but never builds their facts: accepting it, by
the owner or by the rule, writes the persona link and the family links the page states, and every fact the page types is
written as an Undecided assertion, what the page says, never accepted and never ground for the rule, so a person's facts come
from primary documents only. The rule takes such an identity when the name agrees and at least three of birth date to the
day, death date to the day, burial place, and a stated parent or spouse who is that relative in the tree agree with the tree,
claimed or accepted.
The rule acts on the owner's word, is recorded as such on the proposal and in the audit log, and the owner can reject what
it accepted: the link and every assertion it wrote turn rejected. The rule can also take a decision back (reconsider): every
decision it made is examined again as the rule stands now, oldest first, on the ground that stood before it, and one it would
no longer take is withdrawn, the record a card for the owner again; then every card still undecided is examined the same
way, and one the rule would now take is taken.

usage: tools/conclude.py decide <proposal id> accept|reject [--note "…"]          the decision on a card, as the screen's Add / Ignore
       tools/conclude.py fact "<person>" <name|sex|birth|death|parents|spouses|children|event:<id>> accept|reject|undecided [--note "…"]
       tools/conclude.py assertion <assertion id> accept|reject|undecided [--note "…"]   one statement of one record, on its own
       tools/conclude.py facts "<person>"                                          every fact with its event id and every statement behind it with its id
       tools/conclude.py reconsider [--dry-run]                                   the rule re-examines its decisions and the cards it refused
       tools/conclude.py link "<person>" --spouse "<other>" --record <sha256> --note "…" [--marriage "14 AUG 1959"]
       tools/conclude.py link "<person>" --parent "<other>" [--parent "<other>"] --record <sha256> --note "…"
       tools/conclude.py divorce "<a>" "<b>" --date "BET 1950 AND 1959" --evidence <sha256>[:<persona fact id>][:<citation>] … --note "…"
       common: [--tree slug] [--db catalog/tree.db] [--by user:<you>]

- decide: a person's (or the rule's) decision on a proposal, with everything that follows from it; a command too, as is a
  key fact's decision (tools/facts.py).
- match_record: the matcher on an extraction, then the rule on every proposal it wrote.
- rule_accepts: whether the rule takes a proposal, and why or why not, in words.
- reconsider, withdraw: the rule's decisions examined again; one it would no longer take, taken back; a card it would now take, taken.
- link_on_word, divorce: the owner's word placing a person in a family on a record, or ending a marriage.
- same_personas: a decision, a withdrawal or a rejection applies to every reading's persona of that name and role on the record.
- decide_place: the owner's answer on a place string the resolver left undecided, which real place its words mean or that they are
  not a place, applied wherever the same words appear.
- assert_facts, link_family, create_person: the writes themselves, shared with the extractor when a re-run carries a link.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, parse_gedcom_date, resolve_tree, ulid
from catalog import Catalog, source_tier, split_name, tier_sql
from catalog import date_verdict, place_verdict
from match import REL_OF, candidate, compare, match, personas_of
from plan import plan_person

SKIP = ("Unknown", "Age", "Identification Number", "Relationship")      # about the record or the page, not facts of the person
AUTOMATED = ("familysearch-record", "nara-1950-schedule", "va-gravesite")   # a rule parser's own name, trusted for any collection it claims; a record read by hand or by the model is gated on its collection alone, never on who read it
IDENTIFYING = re.compile(r"census|\bbirths?\b|\bdeaths?\b|\bmarriages?\b|\bvital\b|certificate|social security|numident|\bdraft\b|military|veteran|gravesite|enlist|pension|memorial photograph", re.I)   # §0's automated kinds, and a gravestone's own inscription once read
NAMED_SURVIVORS = re.compile(r"obituary|newspaper", re.I)   # a kind that identifies a person only through who it names, once its text is read (docs/RESEARCH-WORKFLOW.md §0: "then the named survivors decide"); the rule's ground here is a stated relative, never a date or a place alone
EDITABLE = re.compile(r"(?:find a grave|billiongraves|member tree|family tree)(?!.*photograph)", re.I)    # a page anyone can edit, whoever indexes it; not the gravestone's own photograph, which is a primary source (T1) however it is archived
TRUSTED = ("T1", "T2", "T3")                            # a record the rule may act on or count: not one anyone can edit (T4)
EDITABLE_IDENTIFYING = ("findagrave-memorial", "wikitree-profile")   # a page anyone can edit that identifies a person (a memorial, a profile): the rule may take the identity, never a fact; a results page's row is a hint
# An artifact's source is read from its own identity first (an ark is FamilySearch, a memorial id is Find a Grave), then from the row it was archived under (catalog.tier_sql).

def trusted_evidence(cx, tree_id, kind, ids, day=False, without=()):
    """Whether an accepted assertion on any of these subjects rests on a trusted source (T1–T3) or on the owner's own word (a
    vouch, or the file's uncited claim the owner accepted, which is the same thing: no record, their knowledge); an accepted
    fact that rests only on a source anyone can edit does not count for the rule. day: the assertion must itself state a full
    date (its persona fact's; the event's own for a vouch with no fact). without: proposal ids whose assertions do not count
    (a rule decision under reconsideration and every rule decision after it)."""
    q = _q(cx)
    skip = f"AND NOT (json_valid(a.notes) AND json_extract(a.notes,'$.proposal') IN ({','.join('?' * len(without))}))" if without else ""
    full = "AND length(coalesce(pf.date_start, CASE WHEN pf.id IS NULL THEN ev.date_start END)) = 10" if day else ""
    for sid in ids:
        if q.execute(f"""SELECT 1 FROM assertion a LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                         LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN event ev ON a.subject_kind='event' AND ev.id=a.subject_id
                         WHERE a.tree_id=? AND a.subject_kind=? AND a.subject_id=? AND a.status='accepted' {skip} {full}
                         AND (substr({tier_sql()},1,2) IN ('T1','T2','T3') OR (json_valid(a.notes) AND (json_extract(a.notes,'$.vouched')=1 OR json_extract(a.notes,'$.uncited')=1)))""",
                     (tree_id, kind, sid, *without)).fetchone(): return True
    return False
ANSWERABLE = ("missing_parents", "unverified_claim", "missing_fact")

def editable(cx, sha):
    """Whether an artifact is a page anyone can edit (T4 by its own identity or its row): a decision on it is an identity, the
    persona link and the family links it states; its facts are written Undecided, never accepted by the decision."""
    return str(source_tier(cx, sha) or "")[:2] == "T4"

TRUSTED_ARTIFACT = f"substr((SELECT {tier_sql('ar', 's')} FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=assertion.artifact_sha256),1,2) IN ('T1','T2','T3')"   # in an UPDATE on assertion: the statement's record is one nobody can edit at will

class _q:
    """execute() on a fresh cursor each time, rows readable by column name whatever the caller's connection does, so a query
    inside a loop over another query's rows does not consume that loop."""
    def __init__(self, cx): self.cx = cx
    def execute(self, sql, args=()):
        c = self.cx.cursor(); c.row_factory = sqlite3.Row; return c.execute(sql, args)

def same_personas(cx, persona_id):
    """Every persona on the same record with the same name and role as this one, across every extraction of the record, itself
    included: a decision is about the record, whose bytes do not change between readings, so it applies to each reading's
    persona of that name and role, and a withdrawal or a rejection resets them all. The earlier readings' links are history;
    readers of accepted links join on current extractions only."""
    q = _q(cx)
    pe = q.execute("SELECT artifact_sha256, name_text, role_in_record FROM persona WHERE id=?", (persona_id,)).fetchone()
    return [r["id"] for r in q.execute("SELECT id FROM persona WHERE artifact_sha256=? AND name_text IS ? AND role_in_record IS ?", (pe["artifact_sha256"], pe["name_text"], pe["role_in_record"]))]

def assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts):
    """Assertions from a persona's facts to the person, the document having been accepted as theirs: Accepted from a record
    nobody can edit at will, Undecided from a page anyone can edit (what the page says, never accepted by the decision and never
    ground for the rule, so the person's facts come from primary documents only). Name and Sex assert the person row. An event
    fact asserts the person's event of that type and year, created from the fact's date when there is none; an attribute fact
    (Occupation, Inscription, Religion, ...) asserts the person's attribute of that type with the same value, created when there
    is none. A fact the same record already asserts on the same subject with the same type, date, value and place is not asserted
    again, so a re-extraction adds only what is new; one the rule withdrew turns Accepted again on a trusted record and stays
    as it is on an editable page. Returns how many were written."""
    q = _q(cx)
    n = 0
    sha = q.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()["artifact_sha256"]
    a = q.execute("SELECT c.name, ar.original_filename FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id WHERE ar.sha256=?", (sha,)).fetchone()
    cite = a["name"] or a["original_filename"] or sha[:12]
    status = "undecided" if editable(cx, sha) else "accepted"
    def assert_(kind, sid, f):
        nonlocal n
        old = q.execute("""SELECT a.id, a.status FROM assertion a JOIN persona_fact q ON q.id=a.persona_fact_id WHERE a.subject_kind=? AND a.subject_id=? AND a.artifact_sha256=?
                           AND q.fact_type=? AND coalesce(q.date_text,'')=coalesce(?,'') AND coalesce(q.value_text,'')=coalesce(?,'') AND coalesce(q.place_string_id,'')=coalesce(?,'')""",
                        (kind, sid, sha, f["fact_type"], f["date_text"], f["value_text"], f["place_string_id"])).fetchone()
        if old and (old["status"] == status or status == "undecided"): return          # the statement is there; on an editable page it stays as it stands
        if old: q.execute("UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=?, notes=? WHERE id=?", (by, ts, dumps({"proposal": prop_id}), old["id"])); n += 1; return   # the record's statement, withdrawn earlier, stands again
        q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (ulid(), tree_id, kind, sid, f["id"], sha, cite, status, by, ts, dumps({"proposal": prop_id}))); n += 1
    for f in q.execute("""SELECT pf.id, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.calendar, pf.place_string_id, et.kind
                           FROM persona_fact pf JOIN event_type et ON et.name=pf.fact_type WHERE pf.persona_id=?""", (persona_id,)):
        if f["fact_type"] in ("Name", "Sex"): assert_("person", person_id, f); continue
        if f["fact_type"] in SKIP or f["kind"] not in ("event", "attribute"): continue
        if f["kind"] == "event":
            fy = (f["date_start"] or f["date_end"] or "")[:4]           # an event corresponds by type and year; an undated fact only to an undated event
            tol = 2 if f["date_qualifier"] in ("calculated", "about", "estimated") and fy else 0   # a year worked out from an age lands on the event within two years
            ey = lambda e: (e["date_start"] or e["date_end"] or "")[:4]
            events = [e for e in q.execute("""SELECT e.id, e.date_start, e.date_end FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                              WHERE ep.person_id=? AND e.event_type=?""", (person_id, f["fact_type"]))
                      if ey(e) == fy or (tol and ey(e).isdigit() and abs(int(ey(e)) - int(fy)) <= tol)]
            if not fy and f["fact_type"] == "Residence":                 # a residence with no date is its own stay, never another record's: only one this record already asserts
                events = [e for e in events if q.execute("SELECT 1 FROM assertion WHERE subject_kind='event' AND subject_id=? AND artifact_sha256=? AND persona_fact_id=?", (e["id"], sha, f["id"])).fetchone()]
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
    region = json.loads(pe["region_json"] or "{}")
    given, surname, suffix = split_name(pe["name_text"])                 # the right way round whichever way the record wrote it; a suffix is not a surname
    text = " ".join(x for x in (given, surname, suffix) if x)
    pid = ulid()
    q.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tree_id, pe["sex"], text, ts, ts))
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
    relation is evidence on the child's membership; a spouse relation on both partners'. A sibling stated on the record places
    the person as a child of the other's accepted parents with an Undecided assertion (the record states the sibling, not the
    parents), and only when the other is an accepted child of exactly one family; otherwise a sibling gives no membership.
    Returns the links written: person, role, the other person, the page's own word, whether the membership is new, and
    "undecided" for a sibling placement."""
    q = _q(cx)
    out = []
    def person_of(x):
        r = q.execute("SELECT pp.person_id FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?", (x, tree_id)).fetchone()
        return r["person_id"] if r else None
    def member(fid, who, role):
        if q.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, who, role)).fetchone(): return False
        q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (fid, who, role)); return True
    def assert_(fid, who, role, other, as_written, new, status="accepted"):
        sid, cite = dumps([fid, who, role]), f"{as_written} on the record"
        notes = {"proposal": prop_id, **({"placed": "sibling"} if status != "accepted" else {})}
        old = q.execute("SELECT id, status FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256=? AND citation_text=?", (sid, sha, cite)).fetchone()
        if old and old["status"] == status: return
        if old: q.execute("UPDATE assertion SET status=?, asserted_by=?, asserted_at=?, notes=? WHERE id=?", (status, by, ts, dumps(notes), old["id"]))
        else: q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                            VALUES (?,?,'family_member',?,?,?,?,?,?,?,?)""", (ulid(), tree_id, sid, persona_id, sha, cite, status, by, ts, dumps(notes)))
        out.append({"family": fid, "person": who, "role": role, "of": other, "as": as_written, "new": new, "undecided": status != "accepted"})
    one = lambda sql, args: next((f for f, in q.execute(sql, args)), None)
    for r in q.execute("""SELECT kind, value_text, persona_id, related_persona_id FROM persona_relation
                           WHERE (persona_id=? OR related_persona_id=?) AND kind IN ('child','parent','spouse','sibling')""", (persona_id, persona_id)).fetchall():
        mine = r["persona_id"] == persona_id                                   # (X, kind, Y) reads: X is the <kind> of Y
        other = person_of(r["related_persona_id"] if mine else r["persona_id"])
        if not other or other == pid: continue
        as_written = r["value_text"] or r["kind"]
        if r["kind"] == "sibling":
            home = sibling_home(cx, tree_id, other)
            if home: assert_(home, pid, "child", other, f"{as_written} of {q.execute('SELECT display_name FROM person WHERE id=?', (other,)).fetchone()['display_name']}", member(home, pid, "child"), status="undecided")
            continue
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

def sibling_home(cx, tree_id, pid):
    """The one family a person is an accepted child of, where a sibling stated on a record can be placed; None when the link
    is not accepted or the person is a child in more than one family."""
    cat = Catalog(cx, tree_id)
    fams = [f for f, in _q(cx).execute("SELECT family_id FROM family_member WHERE person_id=? AND role='child'", (pid,)) if cat.basis("family_member", dumps([f, pid, "child"])) == "accepted"]
    return fams[0] if len(fams) == 1 else None

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

def decide_place(cx, tree_id, p, status, by, note, choice):
    """The owner's answer on a place string the resolver left undecided (a place_resolution proposal): which real place its
    words mean (accepted, with the candidate chosen from the proposal by its index), or that they are not a place (rejected,
    the reason kept in the string's notes). The answer is about the words, so it applies to every fact carrying the same
    string: an accepted string takes its place_id from the candidate's hierarchy (resolve_places.Store, the candidate read
    back from the geocoder's cached answer to the proposal's own queries), its status and resolver the acting user, and the
    resolver's apply_to_events fills every event whose strings are all resolved; a rejected string stays rejected wherever it
    appears and no event takes it. One audit row on the string, the proposal decided. Returns what was written, or an error."""
    from resolve_places import Store, apply_to_events, nominatim
    q = _q(cx); pay = json.loads(p["payload_json"]); psid, raw = pay["place_string_id"], pay["raw"]; ts = now()
    if p["status"] != "undecided": return {"error": "already decided"}
    ps = q.execute("SELECT status, place_id FROM place_string WHERE id=?", (psid,)).fetchone()
    if not ps: return {"error": "the place string is gone"}
    events = [r["id"] for r in q.execute("""SELECT DISTINCT e.id FROM event e JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                             WHERE e.tree_id=? AND pf.place_string_id=? AND a.status<>'rejected'""", (tree_id, psid))]
    leaf = place = None
    if status == "accepted":
        cands = pay.get("candidates") or []
        try: cand = cands[int(choice)]
        except (TypeError, ValueError, IndexError): return {"error": "choose one of the resolver's candidates for these words, or say they are not a place"}
        full = next((c for qy in pay.get("queries") or [] for c in nominatim(qy) if f"{c.get('osm_type')}/{c.get('osm_id')}" == cand.get("osm")), None)
        if full is None: return {"error": f"the geocoder's answer naming {cand.get('display_name')} is not in the cache and the geocoder did not give it again"}
        leaf = Store(cx).hierarchy(full); place = cand.get("display_name")
        if not q.execute("SELECT 1 FROM place_name WHERE place_id=? AND name=?", (leaf, raw)).fetchone():
            q.execute("INSERT INTO place_name (id,place_id,name,is_primary) VALUES (?,?,?,?)", (ulid(), leaf, raw, False))
        q.execute("UPDATE place_string SET place_id=?, status='accepted', resolver=?, resolved_at=?, notes=? WHERE id=?",
                  (leaf, by, ts, dumps({"how": "chosen on the person screen", "match": cand, "proposal": p["id"], "note": note}), psid))
    else:
        q.execute("UPDATE place_string SET place_id=NULL, status='rejected', resolver=?, resolved_at=?, notes=? WHERE id=?",
                  (by, ts, dumps({"reason": note or "not a place", "proposal": p["id"]}), psid))
    q.execute("UPDATE proposal SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE id=?", (status, by, ts, note, p["id"]))
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "accept" if status == "accepted" else "reject", "place_string", psid,
               dumps({"raw": raw, "from": {"status": ps["status"], "place_id": ps["place_id"]}, "to": {"status": status, "place_id": leaf}, "place": place, "proposal": p["id"], "events": len(events), "note": note})))
    placed = 0
    if status == "accepted":
        apply_to_events(cx, tree_id, by, ts)
        placed = sum(1 for e in events if q.execute("SELECT place_id FROM event WHERE id=?", (e,)).fetchone()["place_id"])
    n = f"{len(events)} fact{'s' if len(events) != 1 else ''} carr{'y' if len(events) != 1 else 'ies'} these words"
    summary = (f"\u201c{raw}\u201d means {place}: {n}, {placed} now placed" + ("" if placed == len(events) else f", {len(events) - placed} waiting on another string of theirs")) if status == "accepted" \
              else f"\u201c{raw}\u201d is not a place: {n}, none takes it"
    return {"ok": True, "kind": "place_resolution", "status": status, "raw": raw, "place": place, "place_id": leaf, "events": len(events), "placed": placed, "summary": summary}

def decide(cx, tree_id, prop_id, status, by, note=None, choice=None):
    """A decision on a proposal: is this record's persona this person (persona_match), or a person the tree does not have
    (new_person); or, on a place_resolution proposal, the owner's answer on a place string (decide_place, choice naming the
    candidate). Accepted: the link accepted, every fact the record states accepted onto the person (assert_facts), the
    family links it states with persons already matched on it accepted (link_family), the plans of the person and of the
    person the record was fetched for regenerated and the questions that closes marked answered; on a page anyone can edit the
    decision is an identity: the link and the family links are accepted, the facts written undecided. Rejected: the link rejected;
    for a new person nothing but the proposal. A proposal the rule accepted can be rejected by a person afterwards: the link
    and every assertion the rule wrote turn rejected; one the rule took back (withdraw) is accepted with everything it had
    written standing again. Returns what was written, or an error."""
    q = _q(cx)
    p = q.execute("SELECT * FROM proposal WHERE id=? AND tree_id=?", (prop_id, tree_id)).fetchone()
    if p and p["kind"] == "place_resolution" and status in ("accepted", "rejected"): return decide_place(cx, tree_id, p, status, by, note, choice)
    if not p or p["kind"] not in ("persona_match", "new_person") or status not in ("accepted", "rejected"): return {"error": "not a persona match, new person or place resolution, or bad status"}
    pay = json.loads(p["payload_json"]); persona_id, person_id = pay["persona_id"], pay.get("person_id"); ts = now(); n = 0; members = []
    identity = editable(cx, pay["artifact_sha256"])                # a page anyone can edit: the identity and its links, never a fact
    if p["status"] != "undecided":
        if not (p["status"] == "accepted" and status == "rejected" and (p["decided_by"] or "").startswith("rule:")): return {"error": "already decided"}
        n = q.execute("UPDATE assertion SET status='rejected', asserted_by=?, asserted_at=? WHERE tree_id=? AND json_valid(notes) AND json_extract(notes,'$.proposal')=?", (by, ts, tree_id, prop_id)).rowcount
    q.execute("UPDATE proposal SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE id=?", (status, by, ts, note, prop_id))
    if p["kind"] == "new_person" and status == "accepted": person_id = create_person(cx, tree_id, persona_id, ts)
    if person_id:
        for pe_id in same_personas(cx, persona_id):                # the decision is about the record: every reading's persona of this name and role takes it
            q.execute("INSERT OR REPLACE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (person_id, pe_id, status, prop_id, by, ts))
    answered = []
    if status == "accepted":
        n = q.execute(f"""UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=? WHERE tree_id=? AND status='undecided' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?
                          AND json_extract(notes,'$.placed') IS NULL AND (subject_kind='family_member' OR {TRUSTED_ARTIFACT})""", (by, ts, tree_id, prop_id)).rowcount   # what the rule wrote and took back stands again; a sibling placement, and a fact an editable page states, stay undecided
        m, sha = assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts); n += m
        members = link_family(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts)
    for pid in dict.fromkeys([person_id, pay.get("subject_person_id")]):
        if pid: answered += answer_questions(cx, tree_id, pid, prop_id, by)
    if status == "accepted":                                     # the record's other personas come up next, against this person's relatives
        eid = q.execute("SELECT extraction_id FROM persona WHERE id=?", (persona_id,)).fetchone()["extraction_id"]
        match_record(cx, eid, by.split(" for ")[-1] if by.startswith("rule:") else by)
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "accept" if status == "accepted" else "reject", "proposal", prop_id,
               dumps({"kind": p["kind"], "persona": persona_id, "person": person_id, "identity": identity, "assertions": n, "memberships": members, "answered": answered, "note": note})))
    return {"ok": True, "status": status, "kind": p["kind"], "person": person_id, "persona": persona_id, "identity": identity, "assertions": n, "memberships": members, "answered": answered, "note": note}

def _stands_for(cat, persona, cand, chosen):
    """Whether a persona on a page anyone can edit stands for a person of the tree as the relative the identity rule may count:
    it fits the person, or the given name and the surname agree and nothing compared disagrees (a memorial lists a relative by
    name and years alone)."""
    fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen)
    if fits: return True
    given = any(a.startswith("given name agrees") for a in agree)
    surname = any(a.startswith("surname agrees") for a in agree) or any(a.startswith("surname:") for a in absent)
    return given and surname and not disagree

def rule_accepts(cx, tree_id, prop, without=()):
    """Whether the standing rule takes a persona-match proposal, and why, in words: (True, reason) or (False, why not). A
    record read by hand or by the model (extractor human:<user> or llm:<model>) is judged exactly like one a rule parsed: by
    the record's own kind and tier and by the facts that agree, never by who did the reading. A record from a source nobody
    can edit at will (T1–T3), of a kind that identifies a person fully: the accepted name and two facts resting on trusted
    sources or the owner's word agree, nothing disagrees. An obituary or newspaper text is such a kind only once it is read
    (a bare citation stays a hint), and only on its own terms: at least one of the two points must be a stated relative who
    is that relative in the tree, on trusted evidence — dates and places alone are never enough for this kind, however many
    agree, because the named survivors are its ground (docs/RESEARCH-WORKFLOW.md §0). The name agrees in full when the record
    writes a wife under her married surname too (a wife under her husband's surname is not a surname disagreement, so not
    the surname's absence either), which is how her own obituary can name her at all. A page anyone can edit (T4) that
    identifies a person (a memorial, a profile): the identity alone, when the name agrees and three of birth date to the day,
    death date to the day, burial place and a stated parent or spouse who is that relative in the tree agree with the tree,
    claimed or accepted; its facts are then written undecided (assert_facts). without: proposal ids whose assertions are not
    ground (reconsider)."""
    q = _q(cx)
    pay = json.loads(prop["payload_json"]); pid, sha = pay.get("person_id"), pay["artifact_sha256"]
    if prop["kind"] != "persona_match" or not pid: return False, "a new person is the owner's decision"
    x = q.execute(f"""SELECT x.name, x.kind AS extractor_kind, c.name AS collection, {tier_sql()} AS trust_tier, s.name AS source FROM extraction e JOIN extractor x ON x.id=e.extractor_id JOIN artifact ar ON ar.sha256=e.artifact_sha256
                     LEFT JOIN collection c ON c.id=ar.collection_id LEFT JOIN source s ON s.id=ar.source_id WHERE e.id=?""", (pay["extraction_id"],)).fetchone()
    if not x: return False, "the record's extraction is gone"
    coll = x["collection"] or ""
    identity = str(x["trust_tier"] or "")[:2] not in TRUSTED             # a page anyone can edit: the identity may be taken, its facts never
    survivors_kind = bool(NAMED_SURVIVORS.search(coll))                  # an obituary or newspaper text: identifying only once read, and only through who it names
    if identity:
        if x["name"] not in EDITABLE_IDENTIFYING: return False, f"a row on a {x['source'] or 'T4'} page anyone can edit is a hint until its own record is read: the owner decides it"
    else:
        if x["extractor_kind"] == "rule" and x["name"] not in AUTOMATED: return False, f"a {coll or x['name']} record is a hint until a person reads it"
        if EDITABLE.search(coll): return False, f"a {coll} record is a hint until a person reads it"
        if not (IDENTIFYING.search(coll) or survivors_kind): return False, f"a {coll or x['name']} record is a hint until a person reads it, and then only for who it names"
        yr = re.search(r"\b(1[78]\d\d)\b", coll)
        if re.search("census", coll, re.I) and yr and int(yr.group(1)) < 1850: return False, "a census before 1850 names only the head"
    cat = Catalog(cx, tree_id)
    persona = next((p for p in personas_of(cx, pay["extraction_id"]) if p["id"] == pay["persona_id"]), None)
    if not persona: return False, "persona not found"
    chosen = {r["persona_id"]: candidate(cat, r["person_id"]) for r in q.execute("""SELECT pp.persona_id, pp.person_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                    JOIN person o ON o.id=pp.person_id WHERE pe.extraction_id=? AND pp.status='accepted' AND o.tree_id=?""", (pay["extraction_id"], tree_id))}
    fam = cat.family(pid)
    relatives = [candidate(cat, rid) for g in ("parents", "spouses", "children") for rid, _ in fam[g]]
    for other in personas_of(cx, pay["extraction_id"]):           # a persona the record relates to this one fits a relative the tree already links: it stands for that relative here
        if other["id"] == persona["id"] or other["id"] in chosen: continue
        fit = next((c for c in relatives if (_stands_for(cat, other, c, {}) if identity else compare(cat, other, c, {})[0])), None)
        if fit: chosen[other["id"]] = fit
    cand = candidate(cat, pid); fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen)
    if disagree: return False, "disagrees: " + "; ".join(disagree)
    married = any(a.startswith("surname:") and "carries her husband's surname" in a for a in absent)   # a wife under her married name: not a disagreement, and not the surname's absence either
    if not any(a.startswith("given name agrees") for a in agree) or not (any(a.startswith("surname agrees") for a in agree) or married): return False, "the name does not agree in full"
    if any(a.startswith("surname agrees, one letter apart") for a in agree): return False, "the surname agrees one letter apart: an indexer's slip a person reads, not the rule's ground"
    INV = {"child": "parent", "parent": "child", "spouse": "spouse"}
    relations = [(k, o, None, n) for k, o, _, n in persona["relations"]]      # the persona is the <kind> of the other
    relations += [(INV[r[0]], r[1], None, r[2]) for r in q.execute("""SELECT r.kind, r.persona_id, o.name_text FROM persona_relation r JOIN persona o ON o.id=r.persona_id
                                                                         WHERE r.related_persona_id=? AND r.kind IN ('child','parent','spouse')""", (persona["id"],))]   # the other is the <kind> of the persona
    def joined(kind, other_pid):
        """The relative a stated relation names, when the tree links the two so, claimed or accepted: (group, candidate) or None."""
        oc = chosen.get(other_pid); group = {"child": "parents", "parent": "children", "spouse": "spouses"}.get(kind)
        return (group, oc) if oc and group and any(rid == oc["id"] for rid, _ in fam[group]) else None
    if identity:
        day = lambda t: any(a.startswith(f"{t} date agrees") and "year only" not in a for a in agree)   # both sides a full date, the same day
        points = [w for t, w in (("birth", "birth date to the day"), ("death", "death date to the day")) if day(t)]
        if any(a.startswith("burial place agrees") for a in agree): points.append("burial place")
        named = set()
        for kind, other_pid, _, other_name in relations:
            j = joined(kind, other_pid)
            if j and j[1]["id"] not in named: named.add(j[1]["id"]); points.append(f"{REL_OF[j[0]]} {other_name}")
        if len(points) < 3: return False, ("a page anyone can edit identifies a person only when the name and three of birth date to the day, death date to the day, burial place "
                                           "and a stated parent or spouse agree: here " + (", ".join(points) + (" agree" if len(points) > 1 else " agrees") if points else "the name alone agrees"))
        return True, "identity on a page anyone can edit: the name, " + ", ".join(points) + " agree with the tree; the page's facts are written undecided, never accepted"
    if cat.basis("person", pid) != "accepted": return False, "the name is not accepted yet"
    if not trusted_evidence(cx, tree_id, "person", [pid], without=without): return False, "the accepted name rests on no trusted source and not on your own word"
    points, rel_points = [], []
    ok = lambda t, day=False: bool(cand["events"].get(t)) and trusted_evidence(cx, tree_id, "event", [cand["events"][t]], day=day, without=without)   # the event compared, not any of the type
    full = lambda t: len(((persona.get(t) or {}).get("start") or "")) == 10 and "year only" not in next((a for a in agree if a.startswith(f"{t} date agrees")), "")
    for a in agree:
        if a.startswith("birth date agrees") and ok("Birth"): points += ["birth date to the day", "and the day"] if full("birth") and ok("Birth", day=True) else ["birth date"]      # a date agreeing to the day, on a trusted statement of the day, counts double
        if a.startswith("death date agrees") and ok("Death"): points += ["death date to the day", "and the day"] if full("death") and ok("Death", day=True) else ["death date"]
        if a.startswith("death place agrees") and ok("Death"): points.append("death place")
        if a.startswith("burial place agrees") and ok("Burial"): points.append("burial place")
    for kind, other_pid, _, other_name in relations:
        j = joined(kind, other_pid)
        if not j: continue
        group, oc = j
        role = "child" if group == "parents" else "partner"; other_role = "child" if group == "children" else "partner"
        rows = [dumps([fid, pid, role]) for fid, in q.execute("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role=?
                                                                WHERE fm.person_id=? AND fm.role=?""", (oc["id"], other_role, pid, role))]   # the membership that joins these two
        if trusted_evidence(cx, tree_id, "family_member", rows, without=without):
            pt = f"{REL_OF[group]} {other_name}"; points += [pt, "and the day"]; rel_points.append(pt)   # the relationship and the person it identifies: two points
    if len(points) < 2: return False, "agrees with the accepted name" + (f" and {points[0]}" if points else "") + " only, counting facts from trusted sources; two are needed"
    if survivors_kind and not rel_points: return False, "an obituary or newspaper text is ground only through who it names: " + (", ".join(p for p in points if p != "and the day") or "the name") + " agree, but none of the accepted relatives is among the survivors it names"
    return True, "agrees with your accepted name, " + " and ".join(p for p in points if p != "and the day") + " from trusted sources; nothing disagrees"

def match_record(cx, eid, by, about=None):
    """The matcher on an extraction, then the standing rule on every proposal it wrote: those it takes are accepted on the
    owner's behalf, recorded as the rule. Returns (proposals written, proposals the rule accepted with the reason)."""
    q = _q(cx)
    written = match(cx, eid, by, about=about); taken = []
    for prop_id, kind, name, person_id in written:
        p = q.execute("SELECT * FROM proposal WHERE id=?", (prop_id,)).fetchone()
        ok, why = rule_accepts(cx, p["tree_id"], p)
        if ok: decide(cx, p["tree_id"], prop_id, "accepted", f"rule:agrees-with-accepted for {by}", note=why); taken.append((prop_id, name, why))
    return written, taken

def link_on_word(cx, tree_id, pid, other, kind, sha, by, note, marriage=None):
    """The owner places a person in a family by their own word, on a record that stops short of naming both parties in full
    (an index that gives the spouse's surname by four letters): the membership is created in a family of the right shape and
    carries one Accepted assertion on the artifact, vouched, with the owner's reason; a marriage the record dates becomes the
    family's Marriage event with the same assertion. kind is 'spouse' (other is the spouse) or 'child' (other is one parent
    or a list of both): the child joins the family that pairs the named parents; a parent with several families needs both
    named; a family made here for two parents asserts their partnership on the same word. Returns the family id."""
    q = _q(cx); ts = now()
    one = lambda sql, args: next((f for f, in q.execute(sql, args)), None)
    if kind == "spouse":
        fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                     WHERE fm.person_id=? AND fm.role='partner'""", (other, pid))
        if fid is None: fid = new_family(cx, tree_id, other, ts)
        rows = [(fid, pid, "partner"), (fid, other, "partner")]
    else:
        parents = list(other) if isinstance(other, (list, tuple)) else [other]
        fids = [f for f, in q.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (parents[0],))
                if all(q.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role='partner'", (f, x)).fetchone() for x in parents[1:])]
        if len(fids) > 1: raise ValueError("the parent has more than one family: name both parents")
        fid = fids[0] if fids else new_family(cx, tree_id, parents[0], ts)
        rows = [(fid, pid, "child")] + ([(fid, x, "partner") for x in parents if x != parents[0]] if not fids else [])
    for f, who, role in rows:
        if not q.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (f, who, role)).fetchone():
            q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (f, who, role))
        q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                     VALUES (?,?,'family_member',?,?,?,'accepted',?,?,?)""", (ulid(), tree_id, dumps([f, who, role]), sha, "the owner's word on this record", by, ts, dumps({"vouched": True, "note": note})))
    if marriage:
        eid = ulid()
        q.execute("INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at) VALUES (?,?,'Marriage',?,?,?,?,?,?,?)",
                  (eid, tree_id, marriage.get("date_text"), marriage.get("date_start"), marriage.get("date_end"), marriage.get("qualifier"), "gregorian", ts, ts))
        q.execute("INSERT INTO event_participant (id,event_id,family_id,role) VALUES (?,?,?,'family')", (ulid(), eid, fid))
        q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                     VALUES (?,?,'event',?,?,?,?,'accepted',?,?,?)""", (ulid(), tree_id, eid, marriage.get("persona_fact_id"), sha, marriage.get("citation") or "the record's marriage entry", by, ts, dumps({"vouched": True, "note": note})))
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)", (ulid(), tree_id, ts, by, "accept", "family", fid, dumps({"link": kind, "person": pid, "other": other, "record": sha, "note": note, "marriage": bool(marriage)})))
    return fid

def divorce(cx, tree_id, a, b, date_text, evidence, by, note):
    """The couple's family gets a Divorce event, dated as the records allow ("BET 1950 AND 1959"), with one Accepted assertion per
    piece of evidence the owner names: (artifact sha, persona_fact id or None, citation words). A divorced couple stays a family in
    the tree, so the children keep both parents; the event is what the screen shows between the two lines."""
    q = _q(cx); ts = now()
    fid = next((f for f, in q.execute("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                                          WHERE fm.person_id=? AND fm.role='partner'""", (b, a))), None)
    if fid is None: raise ValueError("no family joins these two")
    from treelib import parse_gedcom_date
    d = parse_gedcom_date(date_text) if date_text else {"date_start": None, "date_end": None, "date_qualifier": None}
    eid = ulid()
    q.execute("INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at) VALUES (?,?,'Divorce',?,?,?,?,?,?,?)",
              (eid, tree_id, date_text, d["date_start"], d["date_end"], d["date_qualifier"], "gregorian", ts, ts))
    q.execute("INSERT INTO event_participant (id,event_id,family_id,role) VALUES (?,?,?,'family')", (ulid(), eid, fid))
    for sha, pf, cite in evidence:
        q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                     VALUES (?,?,'event',?,?,?,?,'accepted',?,?,?)""", (ulid(), tree_id, eid, pf, sha, cite, by, ts, dumps({"vouched": True, "note": note})))
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)", (ulid(), tree_id, ts, by, "accept", "event", eid, dumps({"divorce": [a, b], "date": date_text, "note": note})))
    return eid

def withdraw(cx, tree_id, prop_id, by, why, ts):
    """The rule takes back a decision it would no longer make: the proposal and the persona link return to Undecided, every
    assertion the decision wrote returns to Undecided (an Accept later makes them Accepted again), the questions the decision
    answered are closed as gap_gone so the plan reopens the ones whose gap is back, and the audit row says why. The record is
    a card for the owner again. Returns how many assertions were taken back."""
    q = _q(cx)
    p = q.execute("SELECT * FROM proposal WHERE id=? AND tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%'", (prop_id, tree_id)).fetchone()
    if not p: raise ValueError("not a decision the rule made")
    pay = json.loads(p["payload_json"])
    n = q.execute("UPDATE assertion SET status='undecided' WHERE tree_id=? AND status='accepted' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?", (tree_id, prop_id)).rowcount
    q.execute("UPDATE proposal SET status='undecided', decided_by=NULL, decided_at=NULL, decision_note=? WHERE id=?", (f"the rule took its decision back: {why}", prop_id))
    ids = same_personas(cx, pay["persona_id"])                       # every reading's persona of this name and role on the record, the re-reads' included
    q.execute(f"UPDATE person_persona SET status='undecided', decided_by=NULL, decided_at=NULL WHERE person_id=? AND persona_id IN ({','.join('?' * len(ids))})", (pay["person_id"], *ids))
    q.execute("UPDATE research_question SET closed_reason='gap_gone', answered_by_proposal_id=NULL WHERE answered_by_proposal_id=?", (prop_id,))
    for pid in dict.fromkeys([pay.get("person_id"), pay.get("subject_person_id")]):
        if pid: plan_person(cx, tree_id, pid, by)
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "update", "proposal", prop_id, dumps({"withdrawn": why, "persona": pay["persona_id"], "person": pay["person_id"], "assertions": n})))
    return n

def reconsider(cx, tree_id, by, dry_run=False):
    """Every decision the rule made, oldest first, examined again as the rule stands now, on the ground that stood before it:
    the assertions of that decision, of every rule decision after it and of every decision already withdrawn do not count, so
    each rests only on the owner's decisions and on earlier rule decisions that survived. One the rule would no longer take is
    withdrawn. Then every persona-match card still undecided, oldest first, examined as the rule stands now: one it would now
    take is taken, recorded as the rule; a decision can open another card, so the pass repeats until nothing new is taken.
    Returns one row per decision and per card: proposal, person, persona, kind (decision or card), kept or taken, why."""
    q = _q(cx); ts = now(); out = []; gone = []
    rows = q.execute("SELECT * FROM proposal WHERE tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%' ORDER BY decided_at, id", (tree_id,)).fetchall()
    ids = [r["id"] for r in rows]
    name = lambda pay: (q.execute("SELECT display_name FROM person WHERE id=?", (pay["person_id"],)).fetchone() or {"display_name": "?"})["display_name"]
    persona = lambda pay: q.execute("SELECT name_text FROM persona WHERE id=?", (pay["persona_id"],)).fetchone()["name_text"]
    for i, p in enumerate(rows):
        pay = json.loads(p["payload_json"])
        ok, why = rule_accepts(cx, tree_id, p, without=tuple(ids[i:] + gone))
        if not ok:
            gone.append(p["id"])
            if not dry_run: withdraw(cx, tree_id, p["id"], by, why, ts)
        out.append({"proposal": p["id"], "person": name(pay), "persona": persona(pay), "kind": "decision", "kept": ok, "why": why})
    cards = {}                                                       # proposal id -> the row of its latest examination
    taken = True
    while taken:
        taken = False
        for p in q.execute("SELECT * FROM proposal WHERE tree_id=? AND status='undecided' AND kind='persona_match' ORDER BY created_at, id", (tree_id,)).fetchall():
            if p["id"] in cards and cards[p["id"]]["taken"]: continue
            pay = json.loads(p["payload_json"]); ok, why = rule_accepts(cx, tree_id, p)
            if ok and not dry_run: decide(cx, tree_id, p["id"], "accepted", f"rule:agrees-with-accepted for {by}", note=why); taken = True
            cards[p["id"]] = {"proposal": p["id"], "person": name(pay), "persona": persona(pay), "kind": "card", "taken": ok, "why": why}
    return out + list(cards.values())

def main():
    ap = argparse.ArgumentParser(description="The standing rule's decisions examined again; the owner's word on a family link or a divorce.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dc = sub.add_parser("decide", help="the decision on a card: is this record's persona this person (or a new person)"); dc.add_argument("proposal"); dc.add_argument("verdict", choices=["accept", "reject"]); dc.add_argument("--note")
    fc = sub.add_parser("fact", help="a key fact of a person decided: accept touches held evidence or is your own word (a vouch); reject and undecided touch every assertion behind it")
    fc.add_argument("person"); fc.add_argument("field"); fc.add_argument("verdict", choices=["accept", "reject", "undecided"]); fc.add_argument("--note")
    ac = sub.add_parser("assertion", help="one statement of one record on one subject, decided on its own (a fact decision touches every statement behind the fact)")
    ac.add_argument("assertion"); ac.add_argument("verdict", choices=["accept", "reject", "undecided"]); ac.add_argument("--note")
    ls = sub.add_parser("facts", help="a person's key facts, events and attributes with their ids, and every statement behind each with its id, status and record"); ls.add_argument("person")
    r = sub.add_parser("reconsider", help="the rule re-examines every decision it made and every card still undecided; a decision it would no longer take is withdrawn, a card it would now take is taken")
    r.add_argument("--dry-run", action="store_true", help="report only")
    l = sub.add_parser("link", help="place a person in a family on your own word, on a record that stops short of naming both parties")
    l.add_argument("person"); g = l.add_mutually_exclusive_group(required=True); g.add_argument("--spouse"); g.add_argument("--parent", action="append")
    l.add_argument("--record", required=True, help="sha256 of the archived record"); l.add_argument("--note", required=True, help="your reason, kept on the assertion")
    l.add_argument("--marriage", help="the marriage date the record gives, GEDCOM form (14 AUG 1959)")
    d = sub.add_parser("divorce", help="a Divorce event between two people, with the evidence you name")
    d.add_argument("a"); d.add_argument("b"); d.add_argument("--date", help="GEDCOM form (BET 1950 AND 1959)")
    d.add_argument("--evidence", action="append", required=True, help="sha256[:persona fact id][:citation words]"); d.add_argument("--note", required=True)
    for x in (dc, fc, ac, ls, r, l, d):
        x.add_argument("--tree"); x.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); x.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    cx.execute("BEGIN")
    try:
        if a.cmd == "decide":
            res = decide(cx, tree_id, a.proposal, "accepted" if a.verdict == "accept" else "rejected", a.by, note=a.note)
            if "error" in res: raise SystemExit(res["error"])
            who = cx.execute("SELECT display_name FROM person WHERE id=?", (res["person"],)).fetchone()
            print(f"{res['status']}: {res['kind'].replace('_', ' ')} {who[0] if who else ''}; {res['assertions']} assertion(s), {len(res['memberships'])} family link(s), {len(res['answered'])} question(s) answered")
            if res["status"] == "accepted" and res["identity"]: print("    an identity on a page anyone can edit: the link and the family links it states are accepted; its facts are written undecided, never accepted")
            if res["status"] == "accepted" and res["person"]:
                sha = cx.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (res["persona"],)).fetchone()[0]
                for f in record_says(cx, tree_id, res["person"], sha): print(f"    {f['status']:9} {f['fact']}" + (f"  [conflict: {f['disagrees']}]" if f["disagrees"] else ""))
            nm = lambda i: cx.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()[0]
            for m in res["memberships"]: print("   ", f"{nm(m['person'])} placed beside {nm(m['of'])} as a child of the same parents, undecided: the record states a sibling, not the parents" if m.get("undecided") else f"{nm(m['person'])} {'child' if m['role'] == 'child' else 'spouse'} of {nm(m['of'])}: " + ("a new link, on this record" if m["new"] else "this record accepted as evidence on the link"))
            left = cx.execute("SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND json_extract(payload_json,'$.artifact_sha256')=(SELECT json_extract(payload_json,'$.artifact_sha256') FROM proposal WHERE id=?)", (tree_id, a.proposal)).fetchone()[0]
            print(f"    {left} card(s) still waiting on this record" if left else "    nothing else waits on this record")
        elif a.cmd == "fact":
            from facts import decide_fact
            pid = cat.find_person(a.person)
            res = decide_fact(cx, tree_id, pid, a.field, {"accept": "accepted", "reject": "rejected", "undecided": "undecided"}[a.verdict], a.note, a.by)
            if "error" in res: raise SystemExit(res["error"])
            print(f"{a.field} {res['status']}: {res['assertions']} assertion(s) touched" + (f", {len(res['vouched'])} written on your own word" if res["vouched"] else "") + (f", {len(res['answered'])} question(s) answered" if res["answered"] else ""))
            from facts import evidence_rows
            for e in evidence_rows(cx, pid, a.field): print(f"    {e['id'][-6:]} {e['status']:9} {e['tier'] or '-':5} {e['citation'] or ''}" + (" (your own word)" if e["vouched"] else " (the file's uncited claim)" if e["uncited"] else ""))
        elif a.cmd == "assertion":
            row = cx.execute("SELECT id, subject_kind, subject_id, status, citation_text FROM assertion WHERE id=? AND tree_id=?", (a.assertion, tree_id)).fetchone()
            if not row: raise SystemExit("no such assertion in this tree")
            status = {"accept": "accepted", "reject": "rejected", "undecided": "undecided"}[a.verdict]; ts = now()
            cx.execute("UPDATE assertion SET status=?, asserted_by=?, asserted_at=? WHERE id=?", (status, a.by, ts, row["id"]))
            cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                       (ulid(), tree_id, ts, a.by, {"accepted": "accept", "rejected": "reject", "undecided": "update"}[status], "assertion", row["id"], dumps({"was": row["status"], "now": status, "subject": [row["subject_kind"], row["subject_id"]], "note": a.note})))
            people = [r[0] for r in cx.execute("SELECT person_id FROM event_participant WHERE event_id=? AND person_id IS NOT NULL", (row["subject_id"],))] if row["subject_kind"] == "event" \
                     else [row["subject_id"]] if row["subject_kind"] == "person" else [json.loads(row["subject_id"])[1]] if row["subject_kind"] == "family_member" else []
            for pid in people: plan_person(cx, tree_id, pid, a.by)
            print(f"assertion {row['id'][-6:]} on {row['subject_kind']} ({row['citation_text'] or ''}): {row['status']} -> {status}; plan regenerated for {len(people)} person(s)")
        elif a.cmd == "facts":
            from facts import KEY_FACTS, evidence_rows, fact_status
            pid = cat.find_person(a.person); print(cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0], f"[{pid[-6:]}]")
            rows = [(f, f, None) for f in KEY_FACTS] + [(f"event:{e['id']}", f"{e['event_type'].lower()} {e['date_text'] or ''} {cat.place(e['id'], e['place_id'])['text'] if e['place_id'] else ''} {e['description'] or ''}".strip(), e["id"])
                                                        for e in cx.execute("""SELECT e.id, e.event_type, e.date_text, e.place_id, e.description FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                                               WHERE ep.person_id=? AND e.event_type NOT IN ('Birth','Death') ORDER BY e.date_start, e.event_type""", (pid,))]
            for field, label, eid in rows:
                st = fact_status(cx, pid, field)
                if st is None and eid is None: print(f"  {label:11} no claim"); continue
                print(f"  {label[:60]:60} {st or '-':9}" + (f"  event:{eid}" if eid else ""))
                for e in evidence_rows(cx, pid, field): print(f"      {e['id']} {e['status']:9} {e['tier'] or '-':5} {(e['citation'] or '')[:60]}" + (" (your own word)" if e["vouched"] else " (the file's uncited claim)" if e["uncited"] else "") + ("" if e["held"] else "  not held"))
        elif a.cmd == "reconsider":
            rows = reconsider(cx, tree_id, a.by, dry_run=a.dry_run)
            for x in rows:
                verdict = ("kept" if x["kept"] else "would withdraw" if a.dry_run else "withdrawn") if x["kind"] == "decision" else ("would take" if x["taken"] and a.dry_run else "taken" if x["taken"] else "refused")
                print(f"{verdict:15} {x['person']} <- {x['persona']} [{x['proposal'][-6:]}]: {x['why']}")
            if not rows: print("the rule has made no decision in this tree, and no card waits")
            else: print(f"{sum(1 for x in rows if x['kind'] == 'decision')} decision(s) examined, {sum(1 for x in rows if x['kind'] == 'card' and x['taken'])} card(s) {'it would take' if a.dry_run else 'taken'}, {sum(1 for x in rows if x['kind'] == 'card' and not x['taken'])} refused")
        elif a.cmd == "link":
            pid = cat.find_person(a.person)
            marriage = None
            if a.marriage: marriage = {"date_text": a.marriage, **{k: v for k, v in parse_gedcom_date(a.marriage).items() if k != "calendar"}}
            if marriage: marriage["qualifier"] = marriage.pop("date_qualifier")
            if a.spouse: fid = link_on_word(cx, tree_id, pid, cat.find_person(a.spouse), "spouse", a.record, a.by, a.note, marriage=marriage)
            else: fid = link_on_word(cx, tree_id, pid, [cat.find_person(x) for x in a.parent], "child", a.record, a.by, a.note)
            print(f"family {fid}: {a.person} placed on your word; the record {a.record[:12]} carries the assertion")
        else:
            ev = []
            for e in a.evidence:
                parts = e.split(":", 2); ev.append((parts[0], parts[1] or None if len(parts) > 1 else None, parts[2] if len(parts) > 2 else "the record's own words"))
            eid = divorce(cx, tree_id, cat.find_person(a.a), cat.find_person(a.b), a.date, ev, a.by, a.note)
            print(f"divorce event {eid} between {a.a} and {a.b}")
        cx.commit()
    except Exception:
        cx.rollback(); raise

if __name__ == "__main__": main()
