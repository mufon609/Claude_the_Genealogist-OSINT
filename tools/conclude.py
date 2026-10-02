#!/usr/bin/env python3
"""What a decision about a document writes on the tree, and the standing rule that takes the decision when it is certain.

The owner decides documents, not facts: one decision per record about a person, is this them. Yes accepts everything the
record states about the person: its facts become Accepted assertions on the person's events and attributes (created from the
record when the tree had none), and the family links it states with people already matched on the same record are Accepted
too, unless the record is a page anyone can edit, where the memberships are created but their assertions stay Undecided, the
way a sibling placement already is. Where the record disagrees with the tree's own value the record's statement is still
accepted as what that record says, the tree's value stays, and the difference is a conflict question the generator raises
(Catalog.disagreements). A new person is created by the owner, or by the rule when a trusted record (T1–T2, or an obituary
once read) names them with a name in a stated family relationship to a person accepted on that record and nobody in the tree
fits after the fitting check (rule_creates). Anything less certain than the rule below is a card for the owner.

The standing rule (docs/RESEARCH-WORKFLOW.md §0 and §5–7): a record of a kind that identifies a person fully, from a source
nobody can edit at will (T1–T3), is accepted as the person's when the name agrees with the accepted name, at least two
accepted facts agree (birth date, death date, a burial or death place, a stated relationship to someone the record names who
fits a relative the tree already links on something besides that relationship, or is accepted on the record), each resting on
a trusted source or on the owner's own word, and nothing compared
disagrees; a date agreeing to the day, and a relationship the tree holds on trusted evidence, each count double. A page anyone
can edit (T4: a Find a Grave memorial, a WikiTree profile) identifies a person but never builds their facts: accepting it, by
the owner or by the rule, writes the persona link and the family links the page states, and every fact the page types is
written as an Undecided assertion, what the page says, never accepted and never ground for the rule, so a person's facts come
from primary documents only. The rule takes such an identity when the name agrees and at least three of birth date to the
day, death date to the day, burial place, and a stated parent or spouse who is that relative in the tree agree with the tree,
claimed or accepted; a claim whose own citation is the record under decision never counts (rests_elsewhere).
A page anyone can edit identifies a person but writes no accepted family link: the memberships it states are created where
the tree lacks them, each with an Undecided assertion, the way a sibling placement already is.
The rule acts on the owner's word, is recorded as such on the proposal and in the audit log, and the owner can reject what
it accepted: the link and every assertion it wrote turn rejected. The rule can also take a decision back (reconsider): every
decision it made is examined again as the rule stands now, oldest first, on the ground that stood before it, and one it would
no longer take is withdrawn, the record a card for the owner again; then every card still undecided is examined the same
way, and one the rule would now take is taken. Between the two, every current extraction whose undecided cards an older
matcher wrote (the matcher is versioned, match.MATCHER) is matched again: those cards close as superseded and the personas are
proposed again by the matcher as it stands.

The rule decides a conflict on an event's date or place when the classes favour one side without doubt (classes_decide,
docs/RESEARCH-WORKFLOW.md, the proof standard): one side holds the event first-hand, primary information from the record of
the event itself, and every other rests only on secondary or indeterminable information, a page anyone can edit or the
file's claim. It resolves such a conflict through the owner's own resolve, its reason in words as the note, after every
decision that changes a person's evidence and in reconsider, which also examines its earlier resolutions again and takes
back one it would no longer make, the event's value restored. Every other conflict is the owner's, and the owner's own
resolve, or a reopen, stands above the rule's.

usage: tools/conclude.py decide <proposal id> accept|reject [--note "…"]          the decision on a card, as the screen's Add / Ignore
       tools/conclude.py fact "<person>" <name|sex|birth|death|parents|spouses|children|event:<id>> accept|reject|undecided [--note "…"]
       tools/conclude.py assertion <assertion id> accept|reject|undecided [--note "…"]   one statement of one record, on its own
       tools/conclude.py place <persona fact id> --event <event id> [--note "…"]   a record's fact onto the event it belongs to: an undated one (Catalog.unplaced), or one asserted on the wrong event, moved
       tools/conclude.py facts "<person>"                                          every fact with its event id and every statement behind it with its id
       tools/conclude.py reconsider [--dry-run]                                   the rule re-examines its decisions and the cards it refused
       tools/conclude.py link "<person>" --spouse "<other>" --record <sha256> --note "…" [--marriage "14 AUG 1959"]
       tools/conclude.py link "<person>" --parent "<other>" [--parent "<other>"] --record <sha256> --note "…"
       tools/conclude.py divorce "<a>" "<b>" --date "BET 1950 AND 1959" --evidence <sha256>[:<persona fact id>][:<citation>] … --note "…"
       tools/conclude.py merge "<duplicate>" --into "<person>" --note "…"          close a duplicate_person question: the duplicate's row stays, out of every listing
       tools/conclude.py resolve <question id> --keep <assertion id> --note "…"    close a conflict question: the event keeps that statement's date or place
       tools/conclude.py reopen <question id> --note "…"                           a conflict the rule resolved, taken back and yours from now on
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
- place: the owner's answer to Catalog.unplaced, a record's undated fact written onto the event the owner means.
- resolve: the answer to a conflict question, the statement whose date or place the event keeps, with the reason: the owner's,
  or the rule's (rule_conflicts, classes_decide); take_back and reopen: a resolution of the rule's taken back.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, connect, dumps, now, parse_gedcom_date, resolve_tree, ulid
from catalog import Catalog, source_tier, split_name, tier_sql
from catalog import date_verdict, holds, place_verdict, same_surname
from catalog import key as surname_key
from match import MARRIED_IN_LAW, MATCHER, REL_OF, candidate, compare, fits_by_name_and_year, match, personas_of, split_persona_name
from plan import plan_person
from log_search import release_household
from backfill_aliases import classify, clean, key

SKIP = ("Unknown", "Age", "Identification Number", "Relationship")      # about the record or the page, not facts of the person
AUTOMATED = ("familysearch-record", "nara-1950-schedule", "va-gravesite", "nj-death-index", "ky-death-index", "ky-birth-index")   # a rule parser's own name, trusted for any collection it claims; a record read by hand or by the model is gated on its collection alone, never on who read it
IDENTIFYING = re.compile(r"census|\bbirths?\b|\bdeaths?\b|\bmarriages?\b|\bvital\b|certificate|social security|numident|\bdraft\b|military|veteran|gravesite|enlist|pension|memorial photograph|naturaliz", re.I)   # §0's automated kinds, and a gravestone's own inscription once read
NAMED_SURVIVORS = re.compile(r"obituary|newspaper", re.I)   # a kind that identifies a person only through who it names, once its text is read (docs/RESEARCH-WORKFLOW.md §0: "then the named survivors decide"); the rule's ground here is a stated relative, never a date or a place alone
EDITABLE = re.compile(r"(?:find a grave|billiongraves|member tree|family tree)(?!.*photograph)", re.I)    # a page anyone can edit, whoever indexes it; not the gravestone's own photograph, which is a primary source (T1) however it is archived
TRUSTED = ("T1", "T2", "T3")                            # a record the rule may act on or count: not one anyone can edit (T4)
EDITABLE_IDENTIFYING = ("findagrave-memorial", "wikitree-profile")   # a page anyone can edit that identifies a person (a memorial, a profile): the rule may take the identity, never a fact; a results page's row is a hint
FAMILY_WORD = re.compile(r"\bhalf\b|grand(?:son|daughter|child)|in-law", re.I)   # a stated family relationship the record files under 'other': a half sibling, a grandchild, an in-law; never "other relative" or a blank
IN_LAW = {"mother-in-law": "parent", "father-in-law": "parent", "son-in-law": "spouse", "daughter-in-law": "spouse", "brother-in-law": "sibling", "sister-in-law": "sibling"}   # the kind an in-law's own word resolves toward, once the relative it is in-law to is found (resolve_in_law)
RULE_ACTOR = {"persona_match": "rule:agrees-with-accepted", "new_person": "rule:creates-named-relative", "conflict": "rule:classes-favour-one-side"}   # the rule as the decider, by what it did
# An artifact's source is read from its own identity first (an ark is FamilySearch, a memorial id is Find a Grave), then from the row it was archived under (catalog.tier_sql).

def trusted_evidence(cx, tree_id, kind, ids, day=False, stating=None, without=()):
    """Whether an accepted assertion on any of these subjects rests on a trusted source (T1–T3) or on the owner's own word (a
    vouch, or the file's uncited claim the owner accepted, which is the same thing: no record, their knowledge); an accepted
    fact that rests only on a source anyone can edit does not count for the rule. stating "date" or "place": the assertion
    must itself state one (its persona fact's; the event's own for a vouch with no fact), so a record that states an event
    with no date or no place, asserted on the person's one event of the type, is never ground for a date or a place another
    source gave that event. day: the assertion must itself state a full date. without: proposal ids whose assertions do not
    count (a rule decision under reconsideration and every rule decision after it)."""
    q = _q(cx)
    skip = f"AND NOT (json_valid(a.notes) AND coalesce(json_extract(a.notes,'$.proposal'),'') IN ({','.join('?' * len(without))}))" if without else ""
    full = "AND length(coalesce(pf.date_start, CASE WHEN pf.id IS NULL THEN ev.date_start END)) = 10" if day else ""
    full += {"date": " AND coalesce(pf.date_start, pf.date_end, CASE WHEN pf.id IS NULL THEN coalesce(ev.date_start, ev.date_end) END) IS NOT NULL",
             "place": " AND coalesce(pf.place_string_id, CASE WHEN pf.id IS NULL THEN ev.place_id END) IS NOT NULL"}.get(stating, "")
    for sid in ids:
        if q.execute(f"""SELECT 1 FROM assertion a LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                         LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN event ev ON a.subject_kind='event' AND ev.id=a.subject_id
                         WHERE a.tree_id=? AND a.subject_kind=? AND a.subject_id=? AND a.status='accepted' {skip} {full}
                         AND (substr({tier_sql()},1,2) IN ('T1','T2','T3') OR (json_valid(a.notes) AND (json_extract(a.notes,'$.vouched')=1 OR json_extract(a.notes,'$.uncited')=1)))""",
                     (tree_id, kind, sid, *without)).fetchone(): return True
    return False
ANSWERABLE = ("missing_parents", "unverified_claim", "missing_fact")

def record_keys(cx, sha):
    """What identifies a record for a citation to name it: the record ids it holds (catalog.holds, its own apid first), its
    memorial ids and its URL."""
    a = cx.execute("SELECT locator_kind, locator_value FROM artifact WHERE sha256=?", (sha,)).fetchone()
    apids = set(holds(cx, sha)) | ({a[1]} if a and a[0] == "apid" and a[1] else set())
    memorials = {v for v, in cx.execute("SELECT value FROM artifact_locator WHERE artifact_sha256=? AND kind='memorial_id'", (sha,))}
    urls = {a[1]} if a and a[0] == "url" and a[1] else set()
    return apids, memorials, urls

def cites_record(notes, keys):
    """Whether a statement's own citation (an imported claim's notes: its record id and URL) is the record these keys name."""
    apids, memorials, urls = keys
    url = notes.get("url") or ""
    m = re.search(r"/memorial/(\d+)(?:/|$)", url)
    return bool((notes.get("apid") and notes["apid"] in apids) or (m and m.group(1) in memorials) or (url and url in urls))

def rests_elsewhere(cx, eid, sha, axis, value, day=False, keys=None):
    """Whether the event's value that a record's value agrees with stands on some statement other than the record under
    decision: a statement on the event that is not rejected, not the record's own and not a claim whose own citation is that
    record (docs/RESEARCH-WORKFLOW.md, the proof standard: such a claim never counts), giving a date (to the day, with day) or
    a place that agrees with value. A statement with no record fact of its own (the owner's word) stands for the event's own
    date and gives no place."""
    q = _q(cx); keys = keys or record_keys(cx, sha)
    ev = q.execute("SELECT date_text, date_start, date_end, date_qualifier FROM event WHERE id=?", (eid,)).fetchone()
    for r in q.execute("""SELECT a.artifact_sha256, a.notes, a.persona_fact_id, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw
                          FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected'""", (eid,)):
        if r["artifact_sha256"] == sha: continue
        try: notes = json.loads(r["notes"] or "{}")
        except ValueError: notes = {}
        if isinstance(notes, dict) and cites_record(notes, keys): continue
        if axis == "date":
            src = ev if r["persona_fact_id"] is None else r
            d = {"start": src["date_start"] or src["date_end"], "text": src["date_text"], "qualifier": src["date_qualifier"]}
            if not d["start"]: continue
            if date_verdict(value, d)[0] == "agrees" and (not day or (len(d["start"]) == 10 and "year only" not in (date_verdict(value, d)[1] or ""))): return True
        elif r["raw"] and place_verdict(value, r["raw"])[0] == "agrees": return True
    return False

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
    fact asserts the person's event of that type and year, within two years when either the fact's date or the event's own is
    marked about, estimated or calculated, created from the fact's date when there is none; an undated event
    fact (other than Residence, its own case below) asserts the person's one event of that type when there is exactly one,
    whatever its own date, rather than guess a year; with more than one, the fact is left unasserted rather than guessed onto
    either: the checklist's own "more than one event" conflict already stands, and Catalog.unplaced raises this fact of its
    own, naming the record and the type, until the person is left with one event of the type and the record is decided again;
    with none, an event is created as usual. An attribute fact (Occupation, Inscription, Religion, ...) asserts the person's attribute of that type
    with the same value, created when there is none. A fact the same record already asserts on the same subject with the same
    type, date, value and place is not asserted again, so a re-extraction adds only what is new; one the rule withdrew turns
    Accepted again on a trusted record and stays as it is on an editable page; one a person rejected stays rejected, whatever
    reads the record again. A value the page keeps beneath the one it shows (FamilySearch's edit history, a fact whose region
    marks it alternate) is written Undecided and marked so: what the page also says, kept and cited, never accepted with the
    record and never a conflict with the value the record shows. Returns how many were written."""
    q = _q(cx)
    n = 0
    sha = q.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()["artifact_sha256"]
    cite, status = _citation(cx, sha)
    def assert_(kind, sid, f):
        nonlocal n
        alt = "alternate" in json.loads(f["region_json"] or "{}")
        n += _state(q, tree_id, kind, sid, f, sha, cite, "undecided" if alt else status, by, ts, prop_id, {"alternate": True} if alt else None)
    for f in q.execute("""SELECT pf.id, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.calendar, pf.place_string_id, pf.region_json, et.kind
                           FROM persona_fact pf JOIN event_type et ON et.name=pf.fact_type WHERE pf.persona_id=?""", (persona_id,)):
        if f["fact_type"] in ("Name", "Sex"): assert_("person", person_id, f); continue
        if f["fact_type"] in SKIP or f["kind"] not in ("event", "attribute"): continue
        if f["kind"] == "event":
            fy = (f["date_start"] or f["date_end"] or "")[:4]           # an event corresponds by type and year; an undated fact only to an undated event
            all_events = q.execute("""SELECT e.id, e.date_start, e.date_end, e.date_qualifier FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                      WHERE ep.person_id=? AND e.event_type=?""", (person_id, f["fact_type"])).fetchall()
            if not fy and f["fact_type"] != "Residence":                 # undated: the person's one event of the type, never a guess between two or more
                events = all_events if len(all_events) == 1 else []
            else:
                events = _of_year(f, all_events)
                if not fy and f["fact_type"] == "Residence":              # a residence with no date is its own stay, never another record's: only one this record already asserts
                    events = [e for e in events if q.execute("SELECT 1 FROM assertion WHERE subject_kind='event' AND subject_id=? AND artifact_sha256=? AND persona_fact_id=?", (e["id"], sha, f["id"])).fetchone()]
            if not events and all_events and not fy and f["fact_type"] != "Residence": continue   # two or more already: the checklist's own conflict stands, no event guessed at
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

NEAR = ("calculated", "about", "estimated")                            # a date marked so stands for a year give or take two

def _of_year(f, events):
    """The events a dated fact corresponds to: those of its year, or within two years when either the fact's date or the
    event's own is marked about, estimated or calculated (a year worked out from an age, an event the tree dates about a
    year)."""
    fy = (f["date_start"] or f["date_end"] or "")[:4]
    ey = lambda e: (e["date_start"] or e["date_end"] or "")[:4]
    tol = lambda e: 2 if fy and (f["date_qualifier"] in NEAR or e["date_qualifier"] in NEAR) else 0
    return [e for e in events if ey(e) == fy or (tol(e) and ey(e).isdigit() and fy.isdigit() and abs(int(ey(e)) - int(fy)) <= tol(e))]

def _citation(cx, sha):
    """(citation words, status) a record's statements are written with: the collection's name, and Accepted from a record
    nobody can edit at will, Undecided from a page anyone can edit."""
    a = cx.execute("SELECT c.name, ar.original_filename FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id WHERE ar.sha256=?", (sha,)).fetchone()
    return (a[0] or a[1] or sha[:12]), ("undecided" if editable(cx, sha) else "accepted")

def _state(q, tree_id, kind, sid, f, sha, cite, status, by, ts, prop_id, extra=None):
    """One statement of a record's fact on a subject, written once: a statement the same record already makes on the same
    subject with the same type, date, value and place stands again when the rule had withdrawn it (undecided, on a trusted
    record) and otherwise stays as it is, a person's rejection included. Returns 1 when written, else 0."""
    old = q.execute("""SELECT a.id, a.status FROM assertion a JOIN persona_fact q ON q.id=a.persona_fact_id WHERE a.subject_kind=? AND a.subject_id=? AND a.artifact_sha256=?
                       AND q.fact_type=? AND coalesce(q.date_text,'')=coalesce(?,'') AND coalesce(q.value_text,'')=coalesce(?,'') AND coalesce(q.place_string_id,'')=coalesce(?,'')""",
                    (kind, sid, sha, f["fact_type"], f["date_text"], f["value_text"], f["place_string_id"])).fetchone()
    if old:
        if old["status"] == "undecided" and status == "accepted":
            q.execute("UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=?, notes=? WHERE id=?", (by, ts, dumps({"proposal": prop_id, **(extra or {})}), old["id"])); return 1
        return 0
    q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (ulid(), tree_id, kind, sid, f["id"], sha, cite, status, by, ts, dumps({"proposal": prop_id, **(extra or {})})))
    return 1

def assert_family_events(cx, tree_id, fid, persona_ids, sha, prop_id, by, ts):
    """A record's family facts (a Marriage, a Divorce: the event types of kind family_event) asserted on the family the record's
    spouse relation joins, once both partners are accepted on the record (link_family calls this then, so a fact on the
    first partner's persona waits for the second's acceptance): each persona's fact on the family's event of that type and
    year, the way assert_facts corresponds a person's event (within two years when either date is marked about, estimated or
    calculated), created from the fact's date when the family has none of the type; an undated fact on the family's one
    event of the type, and with several on none of them (the checklist's own count of marriage events stands). Accepted
    from a record nobody can edit at will, Undecided from a page anyone can edit; written once, as assert_facts writes.
    Returns how many were written."""
    q = _q(cx); n = 0
    cite, status = _citation(cx, sha)
    for pe in persona_ids:
        for f in q.execute("""SELECT pf.id, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.calendar, pf.place_string_id
                              FROM persona_fact pf JOIN event_type et ON et.name=pf.fact_type WHERE pf.persona_id=? AND et.kind='family_event'""", (pe,)).fetchall():
            all_events = q.execute("""SELECT e.id, e.date_start, e.date_end, e.date_qualifier FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                      WHERE ep.family_id=? AND e.event_type=?""", (fid, f["fact_type"])).fetchall()
            dated = bool(f["date_start"] or f["date_end"])
            events = _of_year(f, all_events) if dated else (all_events if len(all_events) == 1 else [])
            if not events and all_events and not dated: continue
            if not events:
                eid = ulid()
                q.execute("""INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at)
                              VALUES (?,?,?,?,?,?,?,?,?,?)""", (eid, tree_id, f["fact_type"], f["date_text"], f["date_start"], f["date_end"], f["date_qualifier"], f["calendar"], ts, ts))
                q.execute("INSERT INTO event_participant (id,event_id,family_id,role) VALUES (?,?,?,'family')", (ulid(), eid, fid))
                events = [{"id": eid}]
            for e in events: n += _state(q, tree_id, "event", e["id"], f, sha, cite, status, by, ts, prop_id)
    return n

def place(cx, tree_id, pf_id, event_id, by, note):
    """The owner's word on which of a person's events a record's fact belongs to: an undated fact, accepted onto a person with
    several events of its type and left unasserted by assert_facts (Catalog.unplaced), written onto the event the owner
    means, the way assert_facts writes any other statement (accepted from a record nobody can edit at will, undecided from a
    page anyone can); or a fact already asserted on another of the person's events of its type, moved to this one, its status
    kept. An event a move leaves with no statement but rejected ones (an event an older reading made of a misread value) leaves
    the person's events: its participant row goes, the event and its statements stay for the audit trail. Refused when the
    persona fact does not exist or its persona is not accepted to a person, the event is not this tree's, is of another type
    than the fact or belongs to another person, or the fact's statement is already on it. One audit row per change. Returns
    what was written, or an error."""
    q = _q(cx); ts = now()
    pf = q.execute("SELECT pf.*, pe.artifact_sha256 FROM persona_fact pf JOIN persona pe ON pe.id=pf.persona_id WHERE pf.id=?", (pf_id,)).fetchone()
    if not pf: return {"error": "no such persona fact"}
    pp = q.execute("SELECT pp.person_id FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?", (pf["persona_id"], tree_id)).fetchone()
    if not pp: return {"error": "this persona is not accepted to a person"}
    person_id = pp["person_id"]
    ev = q.execute("SELECT id, event_type FROM event WHERE id=? AND tree_id=?", (event_id, tree_id)).fetchone()
    if not ev: return {"error": "no such event in this tree"}
    if ev["event_type"] != pf["fact_type"]: return {"error": f"the event is {ev['event_type']}, the fact is {pf['fact_type']}"}
    if not q.execute("SELECT 1 FROM event_participant WHERE event_id=? AND person_id=?", (event_id, person_id)).fetchone(): return {"error": "the event belongs to another person"}
    had = q.execute("SELECT id, subject_id, status FROM assertion WHERE persona_fact_id=? AND subject_kind='event'", (pf_id,)).fetchone()
    if had and had["subject_id"] == event_id: return {"error": "the fact's statement is already on this event"}
    if had:                                                              # on another of the person's events of its type: moved, its status kept
        if not q.execute("SELECT 1 FROM event_participant ep JOIN event e ON e.id=ep.event_id WHERE e.id=? AND ep.person_id=? AND e.event_type=?",
                         (had["subject_id"], person_id, pf["fact_type"])).fetchone():
            return {"error": "the fact's statement is on an event that is not this person's of its type"}
        q.execute("UPDATE assertion SET subject_id=?, notes=json_set(coalesce(notes,'{}'),'$.placed_by_owner',?) WHERE id=?", (event_id, note, had["id"]))
        q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                  (ulid(), tree_id, ts, by, "update", "assertion", had["id"], dumps({"persona_fact": pf_id, "from_event": had["subject_id"], "event": event_id, "person": person_id, "note": note})))
        retired = None
        if not q.execute("SELECT 1 FROM assertion WHERE subject_kind='event' AND subject_id=? AND status<>'rejected'", (had["subject_id"],)).fetchone():
            q.execute("DELETE FROM event_participant WHERE event_id=? AND person_id=?", (had["subject_id"], person_id)); retired = had["subject_id"]
            q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                      (ulid(), tree_id, ts, by, "update", "event", retired, dumps({"left_person": person_id, "why": "no statement but rejected ones supports it once the record's own was placed elsewhere", "note": note})))
        plan_person(cx, tree_id, person_id, by)
        return {"ok": True, "assertion": had["id"], "status": had["status"], "person": person_id, "event": event_id, "moved_from": had["subject_id"], "retired": retired}
    cite, status = _citation(cx, pf["artifact_sha256"])
    aid = ulid()
    q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                  VALUES (?,?,'event',?,?,?,?,?,?,?,?)""", (aid, tree_id, event_id, pf_id, pf["artifact_sha256"], cite, status, by, ts, dumps({"note": note})))
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "insert", "assertion", aid, dumps({"persona_fact": pf_id, "event": event_id, "person": person_id, "status": status, "note": note})))
    plan_person(cx, tree_id, person_id, by)
    return {"ok": True, "assertion": aid, "status": status, "person": person_id, "event": event_id}

def shown_married(cx, tree_id, person_id, sha, written, canon_surname):
    """Whether the record shows this person married under `written`'s own surname: a wife under her husband's surname (the
    tree's own recorded spouse, claimed or accepted), a daughter or sister under her husband's, named beside a son-in-law
    or brother-in-law of that surname on the same record, or written "Mrs."."""
    if re.match(r"^\s*mrs\.?\b", written or "", re.I): return True
    rest = split_persona_name(written)[1]
    if not rest: return False
    ws = rest[-1]
    if ws == surname_key(canon_surname or ""): return False
    q = _q(cx)
    spouses = [surname_key(n.split()[-1]) for _, n in Catalog(cx, tree_id).family(person_id)["spouses"] if n and n.split()]
    if any(same_surname(ws, s) for s in spouses): return True
    eid = q.execute("SELECT extraction_id FROM persona WHERE artifact_sha256=? LIMIT 1", (sha,)).fetchone()
    if not eid: return False
    in_laws = [name for role, name in q.execute("SELECT role_in_record, name_text FROM persona WHERE extraction_id=?", (eid["extraction_id"],)) if MARRIED_IN_LAW.search(role or "")]
    return any(same_surname(ws, s) for name in in_laws for s in [split_persona_name(name)[1]] if s for s in [s[-1]])

def write_name_alias(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts):
    """The persona's own Name fact, when its words differ from the person's canonical name and are not already one of the
    person's own name rows (a birth or married name create_person already split out), becomes an alias at once: accepted,
    of the kind the difference is (backfill_aliases.classify, married_name when the record shows the person married under
    it: shown_married), the record's words as written. Returns the alias id, or None when there is nothing to write."""
    q = _q(cx)
    fact = q.execute("""SELECT id, value_text FROM persona_fact WHERE persona_id=? AND fact_type='Name' AND value_text IS NOT NULL
                        AND (region_json IS NULL OR json_extract(region_json,'$.alternate') IS NULL) LIMIT 1""", (persona_id,)).fetchone()   # the name the page shows, never one it keeps beneath
    if not fact or not fact["value_text"]: return None
    name = q.execute("SELECT given, surname, suffix FROM person_name WHERE person_id=? AND is_primary", (person_id,)).fetchone()
    if not name: return None
    canon = " ".join(x for x in (name["given"], name["surname"], name["suffix"]) if x)
    value = clean(fact["value_text"])
    if not value or key(value) == key(canon): return None
    if any(key(value) == key(" ".join(x for x in r if x))
           for r in q.execute("SELECT given, surname, suffix FROM person_name WHERE person_id=?", (person_id,))): return None
    if q.execute("SELECT 1 FROM alias WHERE entity_kind='person' AND entity_id=? AND value=?", (person_id, value)).fetchone(): return None
    kind, note = classify(fact["value_text"], name["given"], name["surname"], name["suffix"], married=shown_married(cx, tree_id, person_id, sha, fact["value_text"], name["surname"]))
    aid = ulid()
    cx.execute("""INSERT INTO alias (id,tree_id,entity_kind,entity_id,value,kind,status,source_persona_fact_id,source_artifact_sha256,added_by,added_at,notes)
                  VALUES (?,?,?,?,?,?,'accepted',?,?,?,?,?)""", (aid, tree_id, "person", person_id, value, kind, fact["id"], sha, by, ts, dumps({"proposal": prop_id, "note": note})))
    return aid

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

def resolve_in_law(cx, tree_id, y_pid, resolved_kind, x_surname):
    """The real family link an in-law's stated tie to the record's already-accepted Y resolves to (CLAUDE.md hard rule on
    in-laws): a parent of Y's spouse for a mother- or father-in-law, the spouse of a child of Y's for a son- or
    daughter-in-law, a sibling of Y's spouse or the spouse of a sibling of Y's for a brother- or sister-in-law, the spouse
    or the child (or the sibling) being one the tree already links to Y, claimed or accepted, so the same record's own
    persona need not itself be decided first. The one candidate resolves outright when Y has only the one; more than one is
    told apart by the in-law's own surname, and left ambiguous still, or with none, the link does not resolve. A candidate
    reached through only one uncertain step (Y's one spouse, in turn that spouse's siblings) is never widened to a guess
    among several: each step disambiguates on its own before the next is taken. Returns (kind to write, target person id) or
    None."""
    cat = Catalog(cx, tree_id)
    def name_keys_(pid):
        return {(surname_key(g), surname_key(s)) for g, s, *_ in cat.person(pid)["names"]} | {(surname_key(a.split()[0]), surname_key(a.split()[-1])) for a in cat.person(pid)["aliases"] if len(a.split()) > 1}
    def choose(pool):
        pool = list(dict.fromkeys(pool))
        if len(pool) == 1: return pool[0]
        matching = [c for c in pool if any(surname_key(x_surname) == s and s for _, s in name_keys_(c))]
        return matching[0] if len(matching) == 1 else None
    of = lambda pid, group: choose(oid for oid, _ in cat.family(pid)[group])
    if resolved_kind == "parent":
        spouse = of(y_pid, "spouses"); return ("parent", spouse) if spouse else None
    if resolved_kind == "spouse":
        child = of(y_pid, "children"); return ("spouse", child) if child else None
    if resolved_kind == "sibling":
        spouse = of(y_pid, "spouses")
        sib = of(spouse, "siblings") if spouse else None
        if sib: return ("sibling", sib)
        sib = of(y_pid, "siblings")
        partner = of(sib, "spouses") if sib else None
        if partner: return ("spouse", partner)
    return None

def link_family(cx, tree_id, pid, persona_id, sha, prop_id, by, ts, held_back=None):
    """Family links from the record's own relations, for a matched person as for a new one: where the record says this persona
    is the child, parent or spouse of a persona already accepted as a person in this tree, the membership exists (created when
    the tree lacks it, in a family of the right shape) and carries an Accepted assertion on the artifact, or an Undecided one
    when the artifact is a page anyone can edit (T4): such a page identifies a person but never builds their facts, so the
    membership is created but not accepted by the decision, the way a sibling placement already is. A parent-child relation is
    evidence on the child's membership; a spouse relation on both partners', and the family facts the two partners' personas
    state (a Marriage and its date) are asserted on that family's event (assert_family_events). A sibling stated on the record places the person
    as a child of the other's accepted parents with an Undecided assertion regardless of tier (the record states the sibling,
    not the parents), and only when the other is an accepted child of exactly one family and neither partner of it died,
    on accepted evidence, before the person was born (died_before; the reason goes into held_back when a list is given);
    otherwise a sibling gives no membership. An in-law's own stated tie (mother-, father-, son-, daughter-, brother- or sister-in-law), read only when the persona under decision is the in-law, is resolved through
    the relative it names (resolve_in_law) to the child, parent or spouse link it actually gives, written and evidenced the
    same way as a link the record states outright; a resolution that lands on a sibling goes through the sibling rule above,
    Undecided like any other. Unresolved, it writes nothing and the created person's card stands with no link. On a page
    anyone can edit, a relative the record relates to the subject but that the matcher never proposed a persona_match for (a
    memorial's listed relative, docs/RESEARCH-WORKFLOW.md §0) is still placed when their name and birth year plainly fit
    exactly one person of the tree (match.fits_by_name_and_year): the listed persona is linked to that person Undecided (so
    the membership traces to the persona, and their own record decides their identity later) and the membership follows the
    same path as any other relation above. A person whose link to the listed persona is rejected is no fit; fitting nobody or
    several writes nothing, as a sibling of no placed parents gives none. The trace link is written only where no row stands,
    and an earlier trace of the same decision to a person the persona no longer fits alone is withdrawn. A membership
    statement already there moves only from undecided to accepted (withdrawn, it stands again): a person's own decision on
    it, accepted or rejected, stays. Returns the links written: person, role, the other person, the page's own word, whether
    the membership is new, and "undecided" for a sibling placement or a link from a page anyone can edit."""
    q = _q(cx)
    out = []
    identity = editable(cx, sha)   # a page anyone can edit: the memberships it states stand, but their assertions do not
    cat = Catalog(cx, tree_id)
    listed_personas = None          # persona id -> persona dict of this extraction (match.personas_of shape), built once, only when needed
    def person_of(x):
        r = q.execute("SELECT pp.person_id FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?", (x, tree_id)).fetchone()
        if r: return r["person_id"]
        if not identity: return None          # a listed relative is never proposed only on a page anyone can edit
        nonlocal listed_personas
        if listed_personas is None:
            eid = q.execute("SELECT extraction_id FROM persona WHERE id=?", (persona_id,)).fetchone()["extraction_id"]
            listed_personas = {p["id"]: p for p in personas_of(cx, eid)}
        pr = listed_personas.get(x)
        if not pr: return None
        rejected = {r["person_id"] for r in q.execute("SELECT person_id FROM person_persona WHERE persona_id=? AND status='rejected'", (x,))}
        fits = [c for c in fits_by_name_and_year(cat, cx, tree_id, pr) if c != pid and c not in rejected]
        if len(fits) != 1: return None
        other_pid = fits[0]
        q.execute("DELETE FROM person_persona WHERE persona_id=? AND person_id<>? AND status='undecided' AND proposal_id=?", (x, other_pid, prop_id))   # this decision's earlier trace to a person the persona no longer fits alone
        q.execute("INSERT OR IGNORE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,'undecided',?,?,?)", (other_pid, x, prop_id, by, ts))
        return other_pid
    def member(fid, who, role):
        if q.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, who, role)).fetchone(): return False
        q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (fid, who, role)); return True
    def assert_(fid, who, role, other, as_written, new, status="accepted", placed=None):
        sid, cite = dumps([fid, who, role]), f"{as_written} on the record"
        notes = {"proposal": prop_id, **({"placed": placed} if placed else {})}
        old = q.execute("SELECT id, status FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256=? AND citation_text=?", (sid, sha, cite)).fetchone()
        if old:
            if old["status"] == "undecided" and status == "accepted": q.execute("UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=?, notes=? WHERE id=?", (by, ts, dumps(notes), old["id"]))
            else: return
        else: q.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                            VALUES (?,?,'family_member',?,?,?,?,?,?,?,?)""", (ulid(), tree_id, sid, persona_id, sha, cite, status, by, ts, dumps(notes)))
        out.append({"family": fid, "person": who, "role": role, "of": other, "as": as_written, "new": new, "undecided": status != "accepted", "placed": placed})
    one = lambda sql, args: next((f for f, in q.execute(sql, args)), None)
    x_surname = q.execute("SELECT name_text FROM persona WHERE id=?", (persona_id,)).fetchone()["name_text"]
    x_surname = (split_persona_name(x_surname)[1] or [""])[-1]
    rows = list(q.execute("""SELECT kind, value_text, persona_id, related_persona_id FROM persona_relation
                             WHERE (persona_id=? OR related_persona_id=?) AND kind IN ('child','parent','spouse','sibling','other')""", (persona_id, persona_id)).fetchall())
    for r in rows:
        mine = r["persona_id"] == persona_id                                   # (X, kind, Y) reads: X is the <kind> of Y
        y_persona = r["related_persona_id"] if mine else r["persona_id"]
        kind, as_written = r["kind"], r["value_text"] or r["kind"]
        other = None
        if kind == "other":
            resolved = IN_LAW.get((r["value_text"] or "").strip().lower())
            if not resolved: continue                                          # a half sibling, a grandchild, "other relative": not one of the six the rule resolves
            if not mine: continue                                              # the other persona is the in-law of this one: the tie is resolved from its side, when it is accepted
            y_pid = person_of(y_persona)
            if not y_pid: continue
            got = resolve_in_law(cx, tree_id, y_pid, resolved, x_surname)
            if not got: continue                                              # the relative it is in-law to does not resolve to one person: no link, the created person's card stands as is
            kind, other = got; mine = True                                    # resolve_in_law always reads "X is <kind> of other", whichever side the record's own row sat on
        else:
            other = person_of(y_persona)
        if not other or other == pid: continue
        if kind == "sibling":
            home = sibling_home(cx, tree_id, other)
            gone = died_before(cx, tree_id, home, pid, persona_id) if home else None
            if gone:                                                           # a parent of that home was dead before this one was born: a half sibling, perhaps, never placed under the couple
                if held_back is not None: held_back.append(f"not placed beside {q.execute('SELECT display_name FROM person WHERE id=?', (other,)).fetchone()['display_name']} as a child of the same parents: {gone}; a half sibling, perhaps")
                continue
            if home: assert_(home, pid, "child", other, f"{as_written} of {q.execute('SELECT display_name FROM person WHERE id=?', (other,)).fetchone()['display_name']}", member(home, pid, "child"), status="undecided", placed="sibling")
            continue
        if kind == "spouse":
            fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                         WHERE fm.person_id=? AND fm.role='partner'""", (other, pid))
            if fid is None: fid = one("""SELECT fm.family_id FROM family_member fm WHERE fm.person_id=? AND fm.role='partner'
                                         AND (SELECT COUNT(*) FROM family_member x WHERE x.family_id=fm.family_id AND x.role='partner')=1""", (other,))
            if fid is None: fid = new_family(cx, tree_id, other, ts)
            status = "undecided" if identity else "accepted"
            assert_(fid, pid, "partner", other, as_written, member(fid, pid, "partner"), status=status); assert_(fid, other, "partner", pid, as_written, False, status=status)
            assert_family_events(cx, tree_id, fid, [persona_id, y_persona], sha, prop_id, by, ts)   # the marriage the record dates, on the couple it joins: both partners now accepted on it
            continue
        child = pid if (kind == "child") == mine else other; parent = other if child == pid else pid
        fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                     WHERE fm.person_id=? AND fm.role='child'""", (parent, child)); new = False
        if fid is None:
            fid = one("""SELECT fm.family_id FROM family_member fm WHERE fm.person_id=? AND fm.role='child'
                         AND (SELECT COUNT(*) FROM family_member x WHERE x.family_id=fm.family_id AND x.role='partner')<2""", (child,))
            if fid is not None: new = member(fid, parent, "partner")
            else: fid = one("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (parent,)) or new_family(cx, tree_id, parent, ts); new = member(fid, child, "child")
        assert_(fid, child, "child", parent, as_written, new, status="undecided" if identity else "accepted")
    return out

def died_before(cx, tree_id, fid, pid, persona_id):
    """Why a person cannot be placed as a child of a family's couple, or None: a partner's death, accepted on a trusted record
    or the owner's word and stating its date, that comes before the person's earliest birth the tree or the record under
    decision gives (a mother's before it, a father's more than a year before it: a child can be born after the father's
    death, never after the mother's). The words name the parent, the death and the birth."""
    q = _q(cx)
    births = [r["date_start"] for r in q.execute("""SELECT e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                   WHERE ep.person_id=? AND e.event_type='Birth' AND e.date_start IS NOT NULL""", (pid,))]
    births += [r["date_start"] for r in q.execute("SELECT date_start FROM persona_fact WHERE persona_id=? AND fact_type='Birth' AND date_start IS NOT NULL", (persona_id,))]
    if not births: return None
    born = min(births)
    for partner, name, sex in q.execute("""SELECT fm.person_id, p.display_name, p.sex FROM family_member fm JOIN person p ON p.id=fm.person_id
                                          WHERE fm.family_id=? AND fm.role='partner' AND fm.person_id<>?""", (fid, pid)).fetchall():
        for e in q.execute("""SELECT e.id, e.date_text, e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id
                              WHERE ep.person_id=? AND e.event_type='Death' AND e.date_start IS NOT NULL""", (partner,)).fetchall():
            if not trusted_evidence(cx, tree_id, "event", [e["id"]], stating="date"): continue
            died = e["date_start"]
            if len(died) == 10 and len(born) == 10:
                y, rest = int(died[:4]), died[4:]
                before = (died < born) if sex != "M" else (f"{y + 1:04d}{rest}" < born)
            else:
                before = int(died[:4]) < int(born[:4]) - (1 if sex == "M" else 0)
            if before:
                text = q.execute("SELECT date_text FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type='Birth' AND e.date_start=? LIMIT 1", (pid, born)).fetchone()
                return f"{name}'s accepted death ({e['date_text']}) comes before the birth ({text['date_text'] if text else born})"
    return None

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
                elif place_verdict(a["raw"], tp)[0] == "disagrees": item["disagrees"] = f"place: the tree says {tp}"
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
    back from the geocoder's cached answer to the proposal's own queries; a gazetteer's own candidate with no geocoder twin,
    a GOV or Wikidata place the geocoder does not know, becomes a place of its own name and position under the string's
    country, carrying the gazetteer's id and dated names), its status and resolver the acting user, and the
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
        if cand.get("kind") == "gazetteer":                                  # a gazetteer's own place, no geocoder twin: its name and position under the string's country
            from resolve_places import write_gazetteer
            st = Store(cx); country = (pay.get("parsed") or {}).get("country")
            names = cand.get("names") or []
            name = next((n["name"] for n in names if not n.get("valid_to")), None) or (names[0]["name"] if names else cand.get("display_name", raw).split(" (")[0])
            ptype = cand.get("type") if cand.get("type") in ("town", "village", "hamlet", "city") else "village"
            leaf = st.place(name, ptype, st.place(country, "country", None) if country else None, cand.get("lat"), cand.get("lon"), cand["id"] if cand.get("source") == "wikidata" else None)
            write_gazetteer(cx, leaf, cand); place = cand.get("display_name")
        else:
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

def close_result_rows(cx, tree_id, person_id, by, ts, dry_run=False):
    """A results-page row (role result) that names this person is a hint on the page, its own record the document; once the
    person is accepted directly on the record the row's own ark or memorial id points at, the row's card is superseded: reject
    it, noted "the record itself is accepted", so the summary row does not sit open beside the record it only summarizes.
    Returns [(proposal id, persona's own name)] closed, or that would be (dry_run)."""
    q = _q(cx)
    closed = []
    for r in q.execute("""SELECT p.id, pe.region_json, pe.name_text FROM proposal p JOIN persona pe ON pe.id=json_extract(p.payload_json,'$.persona_id')
                          WHERE p.tree_id=? AND p.status='undecided' AND p.kind='persona_match' AND pe.role_in_record='result'
                          AND json_extract(p.payload_json,'$.person_id')=?""", (tree_id, person_id)):
        region = json.loads(r["region_json"] or "{}")
        kind, value = ("ark", region.get("ark")) if region.get("ark") else ("memorial_id", region.get("memorial_id")) if region.get("memorial_id") else (None, None)
        if not value: continue
        if not q.execute("""SELECT 1 FROM person_persona pp JOIN persona pe2 ON pe2.id=pp.persona_id
                            WHERE pp.person_id=? AND pp.status='accepted' AND pe2.artifact_sha256 IN
                            (SELECT artifact_sha256 FROM artifact_locator WHERE kind=? AND value=?)""", (person_id, kind, str(value))).fetchone(): continue
        if not dry_run:
            q.execute("UPDATE proposal SET status='rejected', decided_by=?, decided_at=?, decision_note=? WHERE id=?", (by, ts, "the record itself is accepted", r["id"]))
            q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                      (ulid(), tree_id, ts, by, "reject", "proposal", r["id"], dumps({"closed": "the record itself is accepted", "person": person_id})))
        closed.append((r["id"], r["name_text"]))
    return closed

def decide(cx, tree_id, prop_id, status, by, note=None, choice=None):
    """A decision on a proposal: is this record's persona this person (persona_match), or a person the tree does not have
    (new_person); or, on a place_resolution proposal, the owner's answer on a place string (decide_place, choice naming the
    candidate). Accepted: the link accepted, every fact the record states accepted onto the person (assert_facts), the
    family links it states with persons already matched on it accepted (link_family), the plans of the person and of the
    person the record was fetched for regenerated and the questions that closes marked answered (the regeneration logs a
    household record, a census page whichever way it arrived, found on the person's own step for its census year,
    plan_person through log_search.hold_household, so their row reads held and no runner searches that census again for a
    household the tree has read, the way the runner logs the household's other steps for a connector's answer); on a page
    anyone can edit the
    decision is an identity: the link accepted, the memberships it states created where the tree lacks them with an Undecided
    assertion, and the facts written undecided. Every other undecided results-page row (role result) naming this person that
    points at a record the person is now accepted on directly closes rejected, "the record itself is accepted"
    (close_result_rows): the summary row is superseded by its own record, not left open beside it. Rejected: the link rejected;
    for a new person nothing but the proposal. A proposal the rule accepted can be rejected by a person afterwards: the link,
    every assertion and the name alias the rule wrote turn rejected, and a step held by the record for this person is planned
    again; one the rule took back (withdraw) is accepted with everything it had written standing again, its name alias
    included. Either way, once the plans are regenerated, the rule goes over the conflicts of the people whose plans the
    decision changed (rule_conflicts): its own resolutions there examined again, every open conflict on an event's date or
    place decided where the classes favour one side without doubt. Returns what was written, or an error."""
    q = _q(cx)
    p = q.execute("SELECT * FROM proposal WHERE id=? AND tree_id=?", (prop_id, tree_id)).fetchone()
    if p and p["kind"] == "place_resolution" and status in ("accepted", "rejected"): return decide_place(cx, tree_id, p, status, by, note, choice)
    if not p or p["kind"] not in ("persona_match", "new_person") or status not in ("accepted", "rejected"): return {"error": "not a persona match, new person or place resolution, or bad status"}
    pay = json.loads(p["payload_json"]); persona_id, person_id = pay["persona_id"], pay.get("person_id"); ts = now(); n = 0; members = []; alias_id = None
    identity = editable(cx, pay["artifact_sha256"])                # a page anyone can edit: the identity and its links, never a fact
    if p["status"] != "undecided":
        if not (p["status"] == "accepted" and status == "rejected" and (p["decided_by"] or "").startswith("rule:")): return {"error": "already decided"}
        n = q.execute("UPDATE assertion SET status='rejected', asserted_by=?, asserted_at=? WHERE tree_id=? AND json_valid(notes) AND json_extract(notes,'$.proposal')=?", (by, ts, tree_id, prop_id)).rowcount
        q.execute("UPDATE alias SET status='rejected' WHERE tree_id=? AND json_valid(notes) AND json_extract(notes,'$.proposal')=?", (tree_id, prop_id))   # the name as the record writes it goes with the record
    q.execute("UPDATE proposal SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE id=?", (status, by, ts, note, prop_id))
    if p["kind"] == "new_person" and status == "accepted" and not person_id:   # created once; a decision the rule took back and that is taken again links the same person
        person_id = create_person(cx, tree_id, persona_id, ts)
        q.execute("UPDATE proposal SET payload_json=json_set(payload_json,'$.person_id',?) WHERE id=?", (person_id, prop_id))
    if person_id:
        for pe_id in same_personas(cx, persona_id):                # the decision is about the record: every reading's persona of this name and role takes it
            q.execute("INSERT OR REPLACE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (person_id, pe_id, status, prop_id, by, ts))
    answered = []
    if status == "accepted":
        n = q.execute(f"""UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=? WHERE tree_id=? AND status='undecided' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?
                          AND json_extract(notes,'$.placed') IS NULL AND json_extract(notes,'$.alternate') IS NULL AND {TRUSTED_ARTIFACT}""", (by, ts, tree_id, prop_id)).rowcount   # what the rule wrote and took back stands again; a sibling placement, a value the page keeps beneath the one it shows, and a fact or family link a page anyone can edit states, stay undecided
        q.execute("""UPDATE alias SET status='accepted', notes=json_set(notes,'$.proposal',?) WHERE tree_id=? AND entity_kind='person' AND entity_id=? AND source_artifact_sha256=?
                     AND status='undecided' AND json_valid(notes) AND json_extract(notes,'$.proposal') IS NOT NULL""", (prop_id, tree_id, person_id, pay["artifact_sha256"]))   # the name alias a withdrawn decision on this record left undecided stands again with this one
        m, sha = assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts); n += m
        alias_id = write_name_alias(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts)
        held_back = []
        members = link_family(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts, held_back=held_back)
        if held_back:                                              # what the record states and the decision did not write, said in the decision itself
            note = "; ".join([note] + held_back) if note else "; ".join(held_back)
            q.execute("UPDATE proposal SET decision_note=? WHERE id=?", (note, prop_id))
    for pid in dict.fromkeys([person_id, pay.get("subject_person_id")] + [m["of"] for m in members if m["role"] == "partner"]):   # a spouse joined on the record: the marriage it dates is now on their family too
        if pid: answered += answer_questions(cx, tree_id, pid, prop_id, by)
    released = release_household(cx, tree_id, person_id, pay["artifact_sha256"], by) if status == "rejected" and person_id and not identity else []   # a step the record held for this person is planned again
    if released: answered += answer_questions(cx, tree_id, person_id, prop_id, by)   # the plan sees the row open again
    people = [pid for pid in dict.fromkeys([person_id, pay.get("subject_person_id")] + [m["of"] for m in members if m["role"] == "partner"]) if pid]
    conflicts = rule_conflicts(cx, tree_id, by, people=people)   # the conflicts the decision opened or changed, and the rule's own resolutions that rest on what it changed
    if status == "accepted":                                     # the record's other personas come up next, against this person's relatives, on the current reading of the record
        eid = q.execute("SELECT extraction_id FROM persona WHERE id=?", (persona_id,)).fetchone()["extraction_id"]
        while (later := q.execute("SELECT superseded_by FROM extraction WHERE id=?", (eid,)).fetchone()["superseded_by"]): eid = later
        match_record(cx, eid, by.split(" for ", 1)[-1] if by.startswith("rule:") else by)
    closed_rows = close_result_rows(cx, tree_id, person_id, by, ts) if status == "accepted" and person_id else []
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "accept" if status == "accepted" else "reject", "proposal", prop_id,
               dumps({"kind": p["kind"], "persona": persona_id, "person": person_id, "identity": identity, "assertions": n, "alias": alias_id, "memberships": members, "answered": answered, "closed_rows": closed_rows, "released_steps": released, "note": note})))
    return {"ok": True, "status": status, "kind": p["kind"], "person": person_id, "persona": persona_id, "identity": identity, "assertions": n, "alias": alias_id, "memberships": members, "answered": answered, "closed_rows": closed_rows, "released_steps": released, "note": note,
            "conflicts": conflicts}

def _stands_for(cat, persona, cand, chosen):
    """Whether a persona on a page anyone can edit stands for a person of the tree as the relative the identity rule may count:
    it fits the person, or the given name and the surname agree and nothing compared disagrees (a memorial lists a relative by
    name and years alone)."""
    fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen)
    if fits: return True
    given = any(a.startswith("given name agrees") for a in agree)
    surname = any(a.startswith("surname agrees") for a in agree) or any(a.startswith("surname:") for a in absent)
    return given and surname and not disagree

FIELD_EVENT = {"birth date": ("Birth", "date", "birth"), "death date": ("Death", "date", "death"), "birth place": ("Birth", "place", "birth place"),
               "burial place": ("Burial", "place", "burial place"), "death place": ("Death", "place", "death place")}

def _grounded(cx, eid, kind, value):
    """Whether an Accepted assertion on this event itself disagrees with value ({start,text,qualifier} for a date, a raw
    string for a place): only such a value vetoes the rule (docs/RESEARCH-WORKFLOW.md §0); a disagreement with a bare claim
    does not, and decide() raises it as a conflict question once the record is taken on its other points. A vouch (the
    owner's own word, accepted with no persona_fact of its own: facts.vouch) accepts the event's own date as it stands, so
    it grounds a date comparison against the event's own fields; it carries no place, so it never grounds one."""
    q = _q(cx)
    rows = q.execute("""SELECT a.persona_fact_id, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.place_string_id, ps.raw
                         FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                         WHERE a.subject_kind='event' AND a.subject_id=? AND a.status='accepted'""", (eid,))
    if kind == "date":
        ev = q.execute("SELECT date_text, date_start, date_qualifier FROM event WHERE id=?", (eid,)).fetchone()
        for r in rows:
            if r["persona_fact_id"] is None: d = {"start": ev["date_start"], "text": ev["date_text"], "qualifier": ev["date_qualifier"]}
            elif r["date_start"] or r["date_end"]: d = {"start": r["date_start"] or r["date_end"], "text": r["date_text"], "qualifier": r["date_qualifier"]}
            else: continue
            if date_verdict(value, d)[0] == "disagrees": return True
        return False
    return any(place_verdict(value, r["raw"])[0] == "disagrees" for r in rows if r["persona_fact_id"] is not None and r["raw"])

def held_against(cx, tree_id, cand_id, other_id, kind, without=()):
    """Whether the tree holds, on an accepted statement resting on a trusted record or the owner's word (trusted_evidence),
    the state a stated relationship of the candidate to other contradicts: for a child, the candidate's own parents; for a
    parent, the other's parents; for a spouse, a spouse of the candidate's; for a sibling, both the candidate's parents and
    the other's. A link the file only claims, or no link at all, holds nothing against the record."""
    q = _q(cx)
    rows = lambda pid, role: [dumps([f, pid, role]) for f, in q.execute("SELECT family_id FROM family_member WHERE person_id=? AND role=?", (pid, role))]
    held = lambda pid, role: trusted_evidence(cx, tree_id, "family_member", rows(pid, role), without=without)
    if kind == "child": return held(cand_id, "child")
    if kind == "parent": return held(other_id, "child")
    if kind == "spouse": return held(cand_id, "partner")
    if kind == "sibling": return held(cand_id, "child") and held(other_id, "child")
    return True

def split_disagree(cx, tree_id, cand, persona, disagree, chosen, without=()):
    """Partition compare()'s disagreements into those grounded in an Accepted assertion on the very event or link compared
    (a veto), those against a bare claim (named in the decision note instead, never a veto) and a birth place that differs
    from an accepted one: a birth or death date, a death or burial place is checked against the event's own Accepted
    assertions, not the tree's displayed value, which may itself be an unaccepted claim; a stated relationship against what
    the tree holds of it on accepted evidence (held_against), so a family the file only claims is a claim here too; a birth
    place, secondary on nearly every record and never a point, never vetoes, and when it differs from an accepted value the
    difference is a conflict question once the record is taken; every other kind of disagreement (a name, a middle name, sex)
    vetoes. Returns (vetoes, claims, conflicts)."""
    rel = {}                                                         # a relationship line's own opening -> (kind, the related candidate), as compare() words it
    for kind, other_pid, as_written, other_name in persona["relations"]:
        if chosen.get(other_pid): rel[f"relationship disagrees: {as_written or kind} of {other_name},"] = (kind, chosen[other_pid])
    vetoes, claims, conflicts = [], [], []
    for d in disagree:
        field = next((f for f in FIELD_EVENT if d.startswith(f)), None)
        eid = cand["events"].get(FIELD_EVENT[field][0]) if field else None
        if field and eid and not _grounded(cx, eid, FIELD_EVENT[field][1], persona[FIELD_EVENT[field][2]]): claims.append(d)
        elif field == "birth place": conflicts.append(d)
        elif d.startswith("relationship disagrees"):
            kind, oc = next((v for k, v in rel.items() if d.startswith(k)), (None, None))
            (vetoes if oc is None or held_against(cx, tree_id, cand["id"], oc["id"], kind, without) else claims).append(d)
        else: vetoes.append(d)
    return vetoes, claims, conflicts

def claimed_relation_match(fam, relations, accepted_on_record):
    """Whether the persona's stated relationship names a persona already accepted on this very record as a person the tree
    links to the candidate by that relation, claimed or accepted (docs/RESEARCH-WORKFLOW.md §5-7): (group, other candidate,
    other name) when so, else None. accepted_on_record: persona id -> candidate, from person_persona rows already decided
    accepted on this extraction — not the fitting check's own guesses."""
    for kind, other_pid, _, other_name in relations:
        other_cand = accepted_on_record.get(other_pid)
        if not other_cand: continue
        group = {"child": "parents", "parent": "children", "spouse": "spouses", "sibling": "siblings"}.get(kind)
        if group and any(rid == other_cand["id"] for rid, _ in fam[group]): return group, other_cand, other_name
    return None

def rule_accepts(cx, tree_id, prop, without=()):
    """Whether the standing rule takes a persona-match proposal, and why, in words: (True, reason) or (False, why not). A
    record read by hand or by the model (extractor human:<user> or llm:<model>) is judged exactly like one a rule parsed: by
    the record's own kind and tier and by the facts that agree, never by who did the reading. The kind is the collection as the
    current reading names it (a parsed page's own heading), the artifact row's collection only when the reading gives none:
    artifact rows are written once, and an older parser's title stays on them. A record from a source nobody
    can edit at will (T1–T3), of a kind that identifies a person fully: the accepted name and two facts resting on trusted
    sources or the owner's word agree, and no birth or death date, death or burial place disagrees against the event's own
    Accepted assertion and no stated relationship against a link the tree holds on accepted evidence (a disagreement with
    a bare claim, the file's family included, is not a veto: it is named in the reason and the record is still taken,
    decide() raising the difference as a conflict question); a birth place never vetoes, and one differing from an accepted
    value is the same conflict question (split_disagree); every other disagreement still vetoes. An obituary or
    newspaper text is such a kind only once it is read
    (a bare citation stays a hint), and only on its own terms: at least one of the two points must be a stated relative who
    is that relative in the tree, on trusted evidence — dates and places alone are never enough for this kind, however many
    agree, because the named survivors are its ground (docs/RESEARCH-WORKFLOW.md §0). The name agrees in full when the record
    writes a wife under her married surname too (a wife under her husband's surname is not a surname disagreement, so not
    the surname's absence either), which is how her own obituary can name her at all. A page anyone can edit (T4) that
    identifies a person (a memorial, a profile): the identity alone, when the name agrees and three of birth date to the day,
    death date to the day, burial place and a stated parent or spouse who is that relative in the tree agree with the tree,
    claimed or accepted; its facts are then written undecided (assert_facts). A persona whose stated relationship is to a
    persona already accepted on this same record as a person the tree links to the candidate by that relation, claimed or
    accepted, is taken the same way though the candidate's own name is not yet accepted, once the given name and surname
    agree with the candidate's name (claimed or accepted) and a birth year agrees where both have one (claimed_relation_match):
    the record's own Name fact then documents the name, accepted with everything else the record states. A persona stated as
    a sibling of a person accepted on the record is taken so when the candidate is a child of that person's parents in the
    tree, claimed or accepted, or has no parents in the tree at all (nothing holds the sibling, nothing contradicts it) and the
    name agrees; accepting places them as a child of those parents with an undecided assertion (link_family). A sibling the
    tree holds counts as a relationship point like a parent or a spouse, on the trusted evidence of the child membership
    beside the other's. A stated relationship to a relative the tree links by a claim alone counts one point, never double, when
    that relative's own persona on the record fits them on more than a name (a date or a place agreeing beside it) or is already
    accepted on the record as them (the owner's ruling written beside "claims never count" in docs/RESEARCH-WORKFLOW.md §5-7);
    it is not an obituary's ground, whose named survivor must be held on trusted evidence.
    A persona the record relates to the one under decision stands for the relative it fits, and its stated
    relationship to that persona, read from either side of the row, is one of the things it fits on (a husband named with an
    age beside his wife fits the tree's husband by that relation); a relative counts once, however many rows relate the two.
    The relationship earns its point only when that persona is accepted on the record or stands for the relative on something
    besides the relationship, a date or a place resting on more than a claim citing this very record (grounded): a couple's
    index entry, two names and a date, is no proof of either. A date or a place an identity counts, too, must rest on more
    than a claim whose own citation is the page under decision (rests_elsewhere), and the reason names what was left out.
    without: proposal
    ids whose assertions and persona links are not ground (reconsider); a name accepted on nothing outside them is judged by
    that route, as it was taken, not as an accepted name resting on no trusted source."""
    q = _q(cx)
    pay = json.loads(prop["payload_json"]); pid, sha = pay.get("person_id"), pay["artifact_sha256"]
    if prop["kind"] not in ("persona_match", "new_person") or (prop["kind"] == "persona_match" and not pid): return False, "not a card the rule decides"
    x = q.execute(f"""SELECT x.name, x.kind AS extractor_kind, CASE WHEN json_valid(e.structured_json) THEN json_extract(e.structured_json,'$.collection') END AS read_collection, c.name AS collection, {tier_sql()} AS trust_tier, s.name AS source
                     FROM extraction e JOIN extractor x ON x.id=e.extractor_id JOIN artifact ar ON ar.sha256=e.artifact_sha256
                     LEFT JOIN collection c ON c.id=ar.collection_id LEFT JOIN source s ON s.id=ar.source_id WHERE e.id=?""", (pay["extraction_id"],)).fetchone()
    if not x: return False, "the record's extraction is gone"
    coll = x["read_collection"] or x["collection"] or ""             # the collection as the current reading names it (the page's own heading); the artifact row, written once at archive time, only when the reading gives none
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
    skip = f"AND coalesce(pp.proposal_id,'') NOT IN ({','.join('?' * len(without))})" if without else ""   # a link a decision under reconsideration wrote is not ground either
    chosen = {r["persona_id"]: candidate(cat, r["person_id"]) for r in q.execute(f"""SELECT pp.persona_id, pp.person_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                    JOIN person o ON o.id=pp.person_id WHERE pe.extraction_id=? AND pp.status='accepted' AND o.tree_id=? {skip}""", (pay["extraction_id"], tree_id, *without))}
    accepted_on_record = dict(chosen)                             # persona id -> candidate, genuinely decided on this record; the fitting loop below only guesses at a fit
    if prop["kind"] == "new_person": return rule_creates(cx, prop, persona, x, identity, survivors_kind, accepted_on_record)
    fam = cat.family(pid); cand = candidate(cat, pid)
    relatives = [candidate(cat, rid) for g in ("parents", "spouses", "children") for rid, _ in fam[g]]
    INV = {"child": "parent", "parent": "child", "spouse": "spouse", "sibling": "sibling"}
    def both_ways(p):
        """A persona's stated relationships read from either side of the persona_relation row: its own (the persona is the <kind>
        of the other) and the inverse of every row naming it (the other is the <kind> of the persona)."""
        rows = [(k, o, None, n) for k, o, _, n in p["relations"]]
        return rows + [(INV[r[0]], r[1], None, r[2]) for r in q.execute("""SELECT r.kind, r.persona_id, o.name_text FROM persona_relation r JOIN persona o ON o.id=r.persona_id
                                                                          WHERE r.related_persona_id=? AND r.kind IN ('child','parent','spouse','sibling')""", (p["id"],))]
    fitted = {}                                                    # other persona id -> (agree, disagree) against the relative it stands for, for the relationship point below
    others = {p["id"]: p for p in personas_of(cx, pay["extraction_id"])}
    for other in others.values():                                 # a persona the record relates to this one fits a relative the tree already links: it stands for that relative here
        if other["id"] == persona["id"] or other["id"] in chosen: continue
        as_related = {**other, "relations": both_ways(other)}    # its relation to the persona under decision, stated from either side, is one of the things it fits on (docs/RESEARCH-WORKFLOW.md §5-7)
        for c in relatives:
            fits, agree, disagree, absent, near = compare(cat, as_related, c, {persona["id"]: cand})
            if fits or (identity and _stands_for(cat, as_related, c, {persona["id"]: cand})): chosen[other["id"]] = c; fitted[other["id"]] = (agree, disagree); break
    keys = record_keys(cx, sha)
    def grounded(other_pid):
        """Whether the persona a stated relationship names earns the relationship its point: accepted on this record already,
        or standing for the tree's relative on something besides that relationship, a date or a place (an age is a birth
        year) that rests on more than a claim citing this very record (docs/RESEARCH-WORKFLOW.md, the proof standard). A
        persona that fits only through its relation to the one under decision, a name and the relationship, earns nothing:
        the relationship would be its own proof."""
        if other_pid in accepted_on_record: return True
        if other_pid not in fitted: return False
        c, other = chosen[other_pid], others[other_pid]
        for a in fitted[other_pid][0]:
            field = next((f for f in FIELD_EVENT if a.startswith(f + " agrees")), None)
            if field:
                et, axis, at = FIELD_EVENT[field]
                if c["events"].get(et) and rests_elsewhere(cx, c["events"][et], sha, axis, other[at], keys=keys): return True
            elif a.startswith("residence place agrees"):
                if any(e["place"] and place_verdict(other["residence place"], e["place"]["text"])[0] == "agrees" and rests_elsewhere(cx, e["id"], sha, "place", other["residence place"], keys=keys)
                       for e in cat.events(c["id"])): return True
            elif a.startswith("the same memorial"): return True
        return False
    fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen)
    vetoes, claims, conflicts = split_disagree(cx, tree_id, cand, persona, disagree, chosen, without)
    if vetoes: return False, "disagrees: " + "; ".join(vetoes)
    claim_note = (" (disagrees with the tree's own claim, not yet accepted: " + "; ".join(claims) + ")") if claims else ""
    claim_note += (" (the birth place differs from an accepted one, never a veto: a conflict question once the record is taken: " + "; ".join(conflicts) + ")") if conflicts else ""
    married = any(a.startswith("surname:") and "carries her husband's surname" in a for a in absent)   # a wife under her married name: not a disagreement, and not the surname's absence either
    if not any(a.startswith("given name agrees") for a in agree) or not (any(a.startswith("surname agrees") for a in agree) or married): return False, "the name does not agree in full"
    if any(a.startswith("surname agrees, one letter apart") for a in agree): return False, "the surname agrees one letter apart: an indexer's slip a person reads, not the rule's ground"
    relations = both_ways(persona)
    def joined(kind, other_pid):
        """The relative a stated relation names, when the tree links the two so, claimed or accepted: (group, candidate) or None."""
        oc = chosen.get(other_pid); group = {"child": "parents", "parent": "children", "spouse": "spouses", "sibling": "siblings"}.get(kind)
        return (group, oc) if oc and group and any(rid == oc["id"] for rid, _ in fam[group]) else None
    if identity:
        day = lambda t: any(a.startswith(f"{t} date agrees") and "year only" not in a for a in agree)   # both sides a full date, the same day
        points, own = [], []                                       # own: what agrees only with the file's claim citing this very page, never a point
        for t, w, et in (("birth", "birth date to the day", "Birth"), ("death", "death date to the day", "Death")):
            if day(t): (points if rests_elsewhere(cx, cand["events"][et], sha, "date", persona[t], day=True, keys=keys) else own).append(w)
        if any(a.startswith("burial place agrees") for a in agree):
            (points if cand["events"].get("Burial") and rests_elsewhere(cx, cand["events"]["Burial"], sha, "place", persona["burial place"], keys=keys) else own).append("burial place")
        named = set()
        for kind, other_pid, _, other_name in relations:
            j = joined(kind, other_pid) if kind != "sibling" else None     # a stated parent or spouse counts here, never a sibling
            if j and j[1]["id"] not in named and grounded(other_pid): named.add(j[1]["id"]); points.append(f"{REL_OF[j[0]]} {other_name}")
        own_note = ("; not counted: " + ", ".join(own) + ", which the tree has only from a claim citing this very page") if own else ""
        if len(points) < 3: return False, ("a page anyone can edit identifies a person only when the name and three of birth date to the day, death date to the day, burial place "
                                           "and a stated parent or spouse agree: here " + (", ".join(points) + (" agree" if len(points) > 1 else " agrees") if points else "the name alone agrees") + own_note)
        return True, "identity on a page anyone can edit: the name, " + ", ".join(points) + " agree with the tree; the page's facts are written undecided, never accepted" + own_note + claim_note
    if cat.basis("person", pid) != "accepted" or not trusted_evidence(cx, tree_id, "person", [pid], without=without):   # the name is a claim, or accepted on nothing the rule may count here: the route through a stated relationship
        rel = claimed_relation_match(fam, relations, accepted_on_record)
        unplaced = None if rel or fam["parents"] else next(((accepted_on_record[o], n) for k, o, _, n in relations if k == "sibling" and o in accepted_on_record), None)   # a stated sibling of someone accepted here, and the tree holds no parents to contradict it
        if not rel and not unplaced: return False, "the name is not accepted yet" if cat.basis("person", pid) != "accepted" else "the accepted name rests on no trusted source and not on your own word"
        if any(d.startswith("birth date disagrees") for d in disagree): return False, "the name is not accepted yet, and the birth year disagrees with the claimed relative's record"
        if unplaced: return True, f"a stated sibling: sibling {unplaced[1]}, already accepted on this record, and your tree holds no parents for {cand['name']}, so nothing contradicts it; the name and birth year agree, so the record's own name fact documents it, and they are placed beside {unplaced[1]} as a child of the same parents, undecided, where the tree holds those" + claim_note
        group, other_cand, other_name = rel
        return True, f"a claimed relationship: {REL_OF[group]} {other_name}, already accepted on this record, and your tree already links them so, claimed or accepted; the name and birth year agree, so the record's own name fact documents it" + claim_note
    points, rel_points = [], []
    ok = lambda t, what, day=False: bool(cand["events"].get(t)) and trusted_evidence(cx, tree_id, "event", [cand["events"][t]], day=day, stating=what, without=without)   # the event compared, not any of the type, on a statement of the date or place compared
    full = lambda t: len(((persona.get(t) or {}).get("start") or "")) == 10 and "year only" not in next((a for a in agree if a.startswith(f"{t} date agrees")), "")
    for a in agree:
        if a.startswith("birth date agrees") and ok("Birth", "date"): points += ["birth date to the day", "and the day"] if full("birth") and ok("Birth", "date", day=True) else ["birth date"]      # a date agreeing to the day, on a trusted statement of the day, counts double
        if a.startswith("death date agrees") and ok("Death", "date"): points += ["death date to the day", "and the day"] if full("death") and ok("Death", "date", day=True) else ["death date"]
        if a.startswith("death place agrees") and ok("Death", "place"): points.append("death place")
        if a.startswith("burial place agrees") and ok("Burial", "place"): points.append("burial place")
    named, bare = set(), []                                        # a relative counts once, however many rows of the record relate the two
    for kind, other_pid, _, other_name in relations:
        j = joined(kind, other_pid)
        if not j or j[1]["id"] in named: continue
        if not grounded(other_pid): bare.append(other_name); continue   # the relative's own persona stands for them on nothing but this relationship: no point
        group, oc = j; named.add(oc["id"])
        role = "child" if group in ("parents", "siblings") else "partner"; other_role = "child" if group in ("children", "siblings") else "partner"
        rows = [dumps([fid, who, r]) for fid, in q.execute("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role=?
                                                                WHERE fm.person_id=? AND fm.role=?""", (oc["id"], other_role, pid, role))
                for who, r in ((pid, role), (oc["id"], other_role))]   # the membership that joins these two, read from either side: the child's under the parent, a partner's beside the other, a sibling's child row beside the other's
        if trusted_evidence(cx, tree_id, "family_member", rows, without=without):
            pt = f"{REL_OF[group]} {other_name}"; points += [pt, "and the day"]; rel_points.append(pt)   # the relationship and the person it identifies: two points
        else:                                                      # grounded above: the relative's own persona fits on more than a name, so a link the file claims counts once
            points.append(f"{REL_OF[group]} {other_name} (a link the file claims, the relative's own persona here fitting on more than a name)")   # one point, never double, and not an obituary's ground
    bare_note = ("; the stated relationship to " + ", ".join(dict.fromkeys(bare)) + " is no point: the record gives nothing of them but the name and the relationship itself, and they are not accepted on it") if bare else ""
    if len(points) < 2: return False, "agrees with the accepted name" + (f" and {points[0]}" if points else "") + " only, counting facts from trusted sources; two are needed" + bare_note
    if survivors_kind and not rel_points: return False, "an obituary or newspaper text is ground only through who it names: " + (", ".join(p for p in points if p != "and the day") or "the name") + " agree, but none of the accepted relatives is among the survivors it names" + bare_note
    return True, "agrees with your accepted name, " + " and ".join(p for p in points if p != "and the day") + " from trusted sources; nothing disagrees against an accepted value" + claim_note

def rule_creates(cx, prop, persona, x, identity, survivors_kind, accepted_on_record):
    """Whether the rule creates the person a new_person card proposes, and why, in words (docs/RESEARCH-WORKFLOW.md §5–7): a
    trusted record (T1–T2, or an obituary once read) names them, with a name, in a stated family relationship (child, parent,
    spouse, sibling, half sibling, grandchild, in-law; never "other relative" or a blank) to a person accepted on the same
    record, and nobody in the tree fits after the fitting check — the matcher's own word, so a card an older matcher wrote is
    left for reconsider to propose again. A page anyone can edit names a person but never creates one: the owner does."""
    q = _q(cx)
    if identity: return False, "a page anyone can edit names a person but never creates one: the owner decides"
    tier = str(x["trust_tier"] or "")[:2]
    if tier not in ("T1", "T2") and not (survivors_kind and tier == "T3"): return False, f"a {tier or 'untiered'} record creates nobody: only a T1 or T2 record, or an obituary once read, and the owner otherwise"
    given, rest = split_persona_name(persona["name"])
    if not given or not rest or persona["name"] == "(unnamed)": return False, "the record gives no full name to create a person under"
    if prop["status"] == "undecided":
        v = q.execute("SELECT version FROM extractor WHERE id=?", (prop["generated_by"],)).fetchone()
        if not v or v["version"] != MATCHER[2]: return False, f"the matcher at {v['version'] if v else '?'} found nobody fitting; the matcher now at {MATCHER[2]} has not looked: reconsider proposes it again"
    stated = [(r["kind"], r["value_text"], r["persona_id"] if r["persona_id"] != persona["id"] else r["related_persona_id"])
              for r in q.execute("SELECT kind, value_text, persona_id, related_persona_id FROM persona_relation WHERE persona_id=? OR related_persona_id=?", (persona["id"], persona["id"]))]
    def resolves(word, other):
        in_law = IN_LAW.get((word or "").strip().lower())
        if not in_law: return True                                            # a half sibling, a grandchild: not an in-law, no link to resolve first
        x_surname = (split_persona_name(persona["name"])[1] or [""])[-1]
        return bool(resolve_in_law(cx, prop["tree_id"], accepted_on_record[other]["id"], in_law, x_surname))
    named = [(kind, word, other) for kind, word, other in stated
             if other in accepted_on_record and (kind in ("child", "parent", "spouse", "sibling") or (kind == "other" and FAMILY_WORD.search(word or "") and resolves(word, other)))]
    if not named:
        others = [word or kind for kind, word, other in stated if other in accepted_on_record]
        return False, ("the record relates them to a person accepted on it only as " + ", ".join(others) + ": not a family relationship the rule creates a person on, or an in-law tie that does not resolve to one person") if others \
               else "the record states no family relationship between them and a person accepted on it"
    kind, word, other = named[0]
    return True, f"{word or kind} of {accepted_on_record[other]['name']}, accepted on this record, whom nobody in the tree fits after the fitting check: created as a person with the record's facts"

def match_record(cx, eid, by, about=None):
    """The matcher on an extraction, then the standing rule on every proposal it wrote: those it takes are accepted on the
    owner's behalf, recorded as the rule. Returns (proposals written, proposals the rule accepted with the reason)."""
    q = _q(cx)
    written = match(cx, eid, by, about=about); taken = []
    for prop_id, kind, name, person_id in written:
        p = q.execute("SELECT * FROM proposal WHERE id=?", (prop_id,)).fetchone()
        ok, why = rule_accepts(cx, p["tree_id"], p)
        if ok: decide(cx, p["tree_id"], prop_id, "accepted", f"{RULE_ACTOR[p['kind']]} for {by}", note=why); taken.append((prop_id, name, why))
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

def _event_place_keys(q, eid, place_id):
    """What an event's place stands for, for a merge's own agreement check: the resolved place, or, unresolved, every raw
    string a non-rejected assertion gives it. Empty counts as absent, agreeing with anything."""
    if place_id: return {place_id}
    return {r[0].strip().lower() for r in q.execute("""SELECT ps.raw FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id
                     JOIN place_string ps ON ps.id=pf.place_string_id WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected'""", (eid,)).fetchall()}

def _fold_event(q, eid, into, moved):
    """An event's statements moved onto another of the same person, type and value; the event itself is left as it is."""
    ev = q.execute("SELECT event_type, date_start FROM event WHERE id=?", (eid,)).fetchone()
    n = q.execute("UPDATE assertion SET subject_id=? WHERE subject_kind='event' AND subject_id=?", (into, eid)).rowcount
    moved["events_folded"] += 1; moved["event_assertions_folded"] += n
    moved["folded_events"].append({"event_type": ev["event_type"], "date_start": ev["date_start"], "into_event_id": into, "assertions": n})

def _fold_family(q, fid, other, moved):
    """A family whose partners are exactly another's, folded into that one: each child's membership moves there, or, the
    child already being the other family's, joins it, the statements moving with it either way; the family's own events
    move; the partner memberships' statements fold onto the other family's own and the partner rows go, so the family row
    is left emptied for the audit trail."""
    for cid, in q.execute("SELECT person_id FROM family_member WHERE family_id=? AND role='child'", (fid,)).fetchall():
        if q.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role='child'", (other, cid)).fetchone():
            q.execute("DELETE FROM family_member WHERE family_id=? AND person_id=? AND role='child'", (fid, cid))
        else: q.execute("UPDATE family_member SET family_id=? WHERE family_id=? AND person_id=? AND role='child'", (other, fid, cid))
        q.execute("UPDATE assertion SET subject_id=? WHERE subject_kind='family_member' AND subject_id=?", (dumps([other, cid, "child"]), dumps([fid, cid, "child"])))
        moved["family_children_moved"] += 1
    moved["family_events_moved"] += q.execute("UPDATE event_participant SET family_id=? WHERE family_id=?", (other, fid)).rowcount
    for pid_, in q.execute("SELECT person_id FROM family_member WHERE family_id=? AND role='partner'", (fid,)).fetchall():
        q.execute("UPDATE assertion SET subject_id=? WHERE subject_kind='family_member' AND subject_id=?", (dumps([other, pid_, "partner"]), dumps([fid, pid_, "partner"])))
    q.execute("DELETE FROM family_member WHERE family_id=? AND role='partner'", (fid,))
    moved["families_folded"] += 1
    moved["folded_families"].append({"family_id": fid, "into_family_id": other})

def _partner_families(q, pid):
    """The families a person is a partner in, each with its set of partners."""
    return [(fid, {r[0] for r in q.execute("SELECT person_id FROM family_member WHERE family_id=? AND role='partner'", (fid,)).fetchall()})
            for fid, in q.execute("SELECT DISTINCT family_id FROM family_member WHERE person_id=? AND role='partner' ORDER BY family_id", (pid,)).fetchall()]

def complete_merge(cx, tree_id, dup_id, kept_id, by, note):
    """A merge made before a merge folded equal events and same-partner families, completed: the kept person's events of one
    type whose dates agree to the day and whose places agree or are absent fold into the one carrying the most statements
    (the earliest id on a tie), each folded event's participant returned to the duplicate's row, as a merge now leaves the
    duplicate's own; the kept person's partner families with the same partners fold into the earliest (_fold_family).
    Nothing else moves, and a merge already complete folds nothing. One audit row. Returns what folded."""
    q = _q(cx); ts = now()
    moved = {"events_folded": 0, "event_assertions_folded": 0, "families_folded": 0, "family_children_moved": 0, "family_events_moved": 0,
             "folded_events": [], "folded_families": []}
    groups = {}
    for eid, et, ds, place_id in q.execute("""SELECT e.id, e.event_type, e.date_start, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                               WHERE ep.person_id=? AND e.date_start IS NOT NULL ORDER BY e.id""", (kept_id,)).fetchall():
        n = q.execute("SELECT COUNT(*) FROM assertion WHERE subject_kind='event' AND subject_id=?", (eid,)).fetchone()[0]
        groups.setdefault((et, ds), []).append((-n, eid, place_id))
    for evs in groups.values():
        evs.sort(); _, keep, keep_place = evs[0]
        for _, eid, place_id in evs[1:]:
            a, b = _event_place_keys(q, eid, place_id), _event_place_keys(q, keep, keep_place)
            if a and b and not (a & b): continue
            _fold_event(q, eid, keep, moved)
            q.execute("UPDATE event_participant SET person_id=? WHERE event_id=? AND person_id=?", (dup_id, eid, kept_id))
    fams = _partner_families(q, kept_id)
    for i, (fid, partners) in enumerate(fams):
        into = next((f for f, ps in fams[:i] if ps == partners and q.execute("SELECT 1 FROM family_member WHERE family_id=? AND role='partner'", (f,)).fetchone()), None)
        if into: _fold_family(q, fid, into, moved)
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "update", "person", dup_id, dumps({"merge_completed": kept_id, "note": note, **moved})))
    return {"duplicate": dup_id, "kept": kept_id, "completed": True, **moved}

def merge(cx, tree_id, dup_id, kept_id, by, note):
    """Close a duplicate_person question (RESEARCH-WORKFLOW §2; the worked example's "merging the two Thomas entries closes
    the question"): the duplicate's persona links, assertions, event and family memberships, plan steps, search log rows and
    open questions move onto the person it duplicates, `person.merged_into` is set so the duplicate's own row stays for the
    audit trail but out of every listing, overview, plan and matcher run, and one `duplicate_person` proposal records the
    decision with the owner's note. A moved step the kept person's plan already has by step_key keeps whichever of the two
    carries search_log runs (neither carrying runs keeps the kept person's own); the other's log rows, if any, are repointed
    onto the survivor rather than lost. A dropped step or question is named in the audit row by its key, row (a step's) and
    rationale, and why it was dropped, the way plan.py's own audit row names what it drops.

    A duplicate's own event of a type the kept person also has, its date agreeing to the day and its place agreeing or
    absent, is folded: its assertions move onto the kept person's own event of that type, and the duplicate's event and its
    participant are left as they are, on the duplicate's row, so the kept person never carries two Birth or two Death
    events of one value. A differing value stays a second event. A duplicate's own family, once its membership
    has moved, whose partners are then exactly the kept person's own family's partners is folded the same way: its
    children's memberships and its own events move to that family, its partner memberships and their assertions fold onto
    the kept family's own, and the duplicate's family row is left emptied, with the duplicate, for the audit trail (a child of
    both joins the kept family's own membership). A pair already merged is completed instead (complete_merge). Returns what
    moved.""" 
    q = _q(cx)
    dup = q.execute("SELECT tree_id, merged_into, display_name FROM person WHERE id=?", (dup_id,)).fetchone()
    kept = q.execute("SELECT tree_id, merged_into, display_name FROM person WHERE id=?", (kept_id,)).fetchone()
    if not dup or not kept: raise ValueError("no such person in this tree")
    if dup["tree_id"] != tree_id or kept["tree_id"] != tree_id: raise ValueError("both persons must be in this tree")
    if dup_id == kept_id: raise ValueError("a person cannot be merged into themself")
    if dup["merged_into"] == kept_id: return complete_merge(cx, tree_id, dup_id, kept_id, by, note)
    if dup["merged_into"]: raise ValueError(f"{dup['display_name']} is already merged into another person")
    if kept["merged_into"]: raise ValueError(f"{kept['display_name']} is itself merged into another person")
    ts = now()
    moved = {"persona_links": 0, "assertions": 0, "event_participants": 0, "events_folded": 0, "event_assertions_folded": 0,
             "family_memberships": 0, "families_folded": 0, "family_children_moved": 0, "family_events_moved": 0,
             "plan_steps_moved": 0, "plan_steps_dropped": 0, "log_rows_repointed": 0, "questions_moved": 0, "questions_dropped": 0,
             "dropped_steps": [], "dropped_questions": [], "folded_events": [], "folded_families": []}   # each drop or fold named by its key/type/family, the way plan.py's own audit row does: the audit row is the only trace of it afterwards

    for persona_id, in q.execute("SELECT persona_id FROM person_persona WHERE person_id=?", (dup_id,)).fetchall():
        if q.execute("SELECT 1 FROM person_persona WHERE person_id=? AND persona_id=?", (kept_id, persona_id)).fetchone(): continue
        q.execute("UPDATE person_persona SET person_id=? WHERE person_id=? AND persona_id=?", (kept_id, dup_id, persona_id))
        moved["persona_links"] += 1

    for ep_id, eid, role, fam in q.execute("SELECT id, event_id, role, family_id FROM event_participant WHERE person_id=?", (dup_id,)).fetchall():
        dup_event = q.execute("SELECT event_type, date_start, place_id FROM event WHERE id=?", (eid,)).fetchone()
        fold_into = None
        if dup_event and dup_event["date_start"]:
            dup_places = _event_place_keys(q, eid, dup_event["place_id"])
            for kept_eid, kept_ds, kept_place_id in q.execute("""SELECT e.id, e.date_start, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                                 WHERE ep.person_id=? AND e.event_type=?""", (kept_id, dup_event["event_type"])).fetchall():
                if kept_ds != dup_event["date_start"]: continue
                kept_places = _event_place_keys(q, kept_eid, kept_place_id)
                if dup_places and kept_places and not (dup_places & kept_places): continue
                fold_into = kept_eid; break
        if fold_into:
            _fold_event(q, eid, fold_into, moved)
            continue                                          # the duplicate's own event and its participant stay as they are
        if q.execute("SELECT 1 FROM event_participant WHERE event_id=? AND role=? AND person_id=? AND family_id IS ?", (eid, role, kept_id, fam)).fetchone(): continue
        q.execute("UPDATE event_participant SET person_id=? WHERE id=?", (kept_id, ep_id))
        moved["event_participants"] += 1

    partner_fams = set()
    for fid, role in q.execute("SELECT family_id, role FROM family_member WHERE person_id=?", (dup_id,)).fetchall():
        if q.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, kept_id, role)).fetchone(): continue
        q.execute("UPDATE family_member SET person_id=? WHERE family_id=? AND person_id=? AND role=?", (kept_id, fid, dup_id, role))
        q.execute("UPDATE assertion SET subject_id=? WHERE subject_kind='family_member' AND subject_id=?", (dumps([fid, kept_id, role]), dumps([fid, dup_id, role])))
        moved["family_memberships"] += 1
        if role == "partner": partner_fams.add(fid)

    for fid in partner_fams:
        partners = {r[0] for r in q.execute("SELECT person_id FROM family_member WHERE family_id=? AND role='partner'", (fid,)).fetchall()}
        if kept_id not in partners: continue
        other = next((f for f, ps in _partner_families(q, kept_id) if f != fid and ps == partners), None)
        if other: _fold_family(q, fid, other, moved)

    moved["assertions"] = q.execute("UPDATE assertion SET subject_id=? WHERE subject_kind='person' AND subject_id=?", (kept_id, dup_id)).rowcount

    for step in q.execute("SELECT * FROM search_plan WHERE person_id=?", (dup_id,)).fetchall():
        existing = q.execute("SELECT id FROM search_plan WHERE person_id=? AND step_key=?", (kept_id, step["step_key"])).fetchone()
        if not existing:
            q.execute("UPDATE search_plan SET person_id=? WHERE id=?", (kept_id, step["id"])); moved["plan_steps_moved"] += 1
            continue
        dup_has_runs = q.execute("SELECT 1 FROM search_log WHERE plan_step_id=?", (step["id"],)).fetchone()
        kept_has_runs = q.execute("SELECT 1 FROM search_log WHERE plan_step_id=?", (existing["id"],)).fetchone()
        if dup_has_runs and not kept_has_runs:
            q.execute("DELETE FROM search_plan WHERE id=?", (existing["id"],))
            q.execute("UPDATE search_plan SET person_id=? WHERE id=?", (kept_id, step["id"])); moved["plan_steps_moved"] += 1
        else:
            moved["log_rows_repointed"] += q.execute("UPDATE search_log SET plan_step_id=? WHERE plan_step_id=?", (existing["id"], step["id"])).rowcount
            q.execute("DELETE FROM search_plan WHERE id=?", (step["id"],)); moved["plan_steps_dropped"] += 1
            moved["dropped_steps"].append({"step_key": step["step_key"], "row_key": step["row_key"], "rationale": step["rationale"],
                                           "reason": "the kept person's own step of this key carries search_log runs already" if kept_has_runs
                                                     else "the kept person's own step of this key is kept; neither carries a search_log run"})

    for question in q.execute("SELECT * FROM research_question WHERE subject_person_id=?", (dup_id,)).fetchall():
        if q.execute("SELECT 1 FROM research_question WHERE subject_person_id=? AND q_key=?", (kept_id, question["q_key"])).fetchone():
            moved["questions_dropped"] += 1
            moved["dropped_questions"].append({"q_key": question["q_key"], "kind": question["kind"],
                                               "reason": "the kept person already has an open question of this key"})
            continue
        q.execute("UPDATE research_question SET subject_person_id=? WHERE id=?", (kept_id, question["id"])); moved["questions_moved"] += 1

    q.execute("UPDATE person SET merged_into=?, updated_at=? WHERE id=?", (kept_id, ts, dup_id))
    human = q.execute("SELECT id FROM extractor WHERE kind='human' AND name='manual'").fetchone()[0]
    prop_id = ulid()
    q.execute("""INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status,decided_by,decided_at,decision_note)
                 VALUES (?,?,?,?,?,?,?,'accepted',?,?,?)""",
              (prop_id, tree_id, "duplicate_person", dumps({"duplicate_person_id": dup_id, "kept_person_id": kept_id, "moved": moved}), note, human, ts, by, ts, note))
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "update", "person", dup_id, dumps({"merged_into": kept_id, "proposal": prop_id, "note": note, **moved})))
    return {"proposal": prop_id, "duplicate": dup_id, "kept": kept_id, **moved}

CONFLICT_AXIS = re.compile(r"^(.+?) (date|place): ")              # a conflict line's own opening: the event type, lowercased, and the axis (Catalog.disagreements)

def resolve(cx, tree_id, qid, keep, by, note):
    """A conflict question closed with a written reason naming the value kept (docs/RESEARCH-WORKFLOW.md, the proof
    standard), by the owner, or by the rule acting for them (rule_conflicts, the reason its own words): the kept statement's
    date, or its place, becomes the event's own value (the event row's date fields, or its place_id), the question closes
    'resolved' with the resolution in its detail, who resolved it included (by), and one audit row names the value kept, the
    event's value before (was, so a resolution the rule takes back restores it) and every statement set aside. Evidence is
    untouched: each statement stays as it was, the ones set aside still accepted as what their records say. The difference
    then reads from the event's new value, the kept side now beside the tree: every line the catalog gives for that event and
    axis afterwards is that same difference, and is recorded closed 'resolved' under its own key, for every partner of a
    family's event too, so a regeneration reopens nothing; a statement that comes later makes another line, a question of its
    own. The owner resolving a question the rule resolved overrides the rule: the rule's resolution is taken back first
    (take_back), and nothing changes should the owner's be refused. Refused when the note is empty, the question is not an
    open conflict about an event's date or place, the statement is rejected, is not on the event the question is about, or
    gives no value on that axis, or the place it gives is not yet resolved to a place. Returns what was done, or an error."""
    from plan import q_key
    q = _q(cx); ts = now(); cat = Catalog(cx, tree_id)
    if not (note or "").strip(): return {"error": "a resolution needs your written reason (--note)"}
    rq = q.execute("SELECT * FROM research_question WHERE id=? AND tree_id=?", (qid, tree_id)).fetchone()
    rule_res = rule_resolution(rq)
    if rule_res and not by.startswith("rule:"):                        # the owner's own resolution over the rule's
        cx.execute("SAVEPOINT owner_over_rule")
        take_back(cx, tree_id, qid, by, f"the owner resolves it: {note}", ts)
        primary = rule_res.get("question") or qid
        reopened = q.execute("SELECT id FROM research_question WHERE id IN (?,?) AND status='open' ORDER BY id=? DESC", (qid, primary, qid)).fetchone()
        out = resolve(cx, tree_id, reopened["id"], keep, by, note) if reopened else {"error": "the rule's resolution is taken back, but the difference no longer reads as this question: resolve the question the plan now holds"}
        if "error" in out: cx.execute("ROLLBACK TO owner_over_rule")
        cx.execute("RELEASE owner_over_rule")
        return out
    if not rq or rq["kind"] != "conflict" or rq["status"] != "open": return {"error": "not an open conflict question in this tree"}
    detail = (json.loads(rq["detail_json"] or "{}") or {}).get("detail") or ""
    m = CONFLICT_AXIS.match(detail)
    if not m: return {"error": "this conflict is not about one event's date or place: no statement to keep (dismiss it with tools/log_search.py --dismiss)"}
    etype, axis = m.group(1), m.group(2)
    a = q.execute("""SELECT a.id, a.status, a.subject_kind, a.subject_id, a.artifact_sha256, a.citation_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier,
                            pf.calendar, ps.raw, ps.place_id FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                     WHERE a.id=? AND a.tree_id=?""", (keep, tree_id)).fetchone()
    if not a: return {"error": "no such statement in this tree"}
    if a["status"] == "rejected": return {"error": "the statement to keep is rejected"}
    ev = q.execute("SELECT * FROM event WHERE id=? AND tree_id=?", (a["subject_id"], tree_id)).fetchone() if a["subject_kind"] == "event" else None
    pid = rq["subject_person_id"]
    if not ev or ev["event_type"].lower() != etype or detail not in cat.disagreements(pid, event=ev["id"]): return {"error": "the statement is not on the event the question is about"}
    if axis == "date" and not (a["date_start"] or a["date_end"]): return {"error": "the statement gives no date to keep"}
    if axis == "place" and not a["raw"]: return {"error": "the statement gives no place to keep"}
    if axis == "place" and not a["place_id"]: return {"error": f"the place the statement gives, “{a['raw']}”, is not yet resolved to a place: answer its words first, then keep it"}
    kept_value = {"start": a["date_start"] or a["date_end"], "text": a["date_text"], "qualifier": a["date_qualifier"]} if axis == "date" else a["raw"]
    differs = lambda v: (date_verdict(kept_value, v)[0] if axis == "date" else place_verdict(kept_value, v)[0]) == "disagrees"
    set_aside = []
    for r in q.execute("""SELECT a.id, a.citation_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw FROM assertion a
                          JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected' AND a.id<>? AND pf.fact_type=?""", (ev["id"], keep, ev["event_type"])):
        v = {"start": r["date_start"] or r["date_end"], "text": r["date_text"], "qualifier": r["date_qualifier"]} if axis == "date" else r["raw"]
        if (v["start"] if axis == "date" else v) and differs(v): set_aside.append({"assertion": r["id"], "record": r["citation_text"], "value": r["date_text"] if axis == "date" else r["raw"]})
    was = {"date_text": ev["date_text"], "date_start": ev["date_start"], "date_end": ev["date_end"], "date_qualifier": ev["date_qualifier"]} if axis == "date" else {"place_id": ev["place_id"], "place": (cat.place(ev["id"], ev["place_id"]) or {}).get("text")}
    own = {"start": ev["date_start"] or ev["date_end"], "text": ev["date_text"], "qualifier": ev["date_qualifier"]} if axis == "date" else was["place"]
    if (own["start"] if axis == "date" else own) and differs(own):     # the event's own value, which the kept one replaces
        set_aside.insert(0, {"assertion": None, "record": "the tree's own value", "value": ev["date_text"] if axis == "date" else was["place"]})
    if axis == "date":
        q.execute("UPDATE event SET date_text=?, date_start=?, date_end=?, date_qualifier=?, calendar=coalesce(?, calendar), updated_at=? WHERE id=?",
                  (a["date_text"], a["date_start"], a["date_end"], a["date_qualifier"], a["calendar"], ts, ev["id"]))
    else: q.execute("UPDATE event SET place_id=?, updated_at=? WHERE id=?", (a["place_id"], ts, ev["id"]))
    resolution = {"kept": {"assertion": keep, "record": a["citation_text"], "value": a["date_text"] if axis == "date" else a["raw"]}, "set_aside": set_aside,
                  "event": ev["id"], "axis": axis, "was": was, "note": note, "by": by, "at": ts, "question": qid}
    people = [pid] + [r["person_id"] for r in q.execute("""SELECT fm.person_id FROM event_participant ep JOIN family_member fm ON fm.family_id=ep.family_id AND fm.role='partner'
                                                            WHERE ep.event_id=? AND fm.person_id<>?""", (ev["id"], pid))]
    closed = [qid]
    q.execute("UPDATE research_question SET status='closed', closed_reason='resolved', closed_at=?, detail_json=? WHERE id=?",
              (ts, dumps({**json.loads(rq["detail_json"] or "{}"), "resolution": resolution}), qid))
    for person in dict.fromkeys(people):                               # the same difference, read now from the kept side, and the partner's own question on a family's event
        lines = [detail] + [l for l in cat.disagreements(person, event=ev["id"]) if l.startswith(f"{etype} {axis}:")]
        for line in dict.fromkeys(lines):
            qd = {"kind": "conflict", "detail": line}; key = q_key(qd)
            row = q.execute("SELECT id, status, closed_reason FROM research_question WHERE subject_person_id=? AND q_key=?", (person, key)).fetchone()
            body = dumps({**qd, "resolution": resolution})
            if row and row["id"] == qid: continue
            if row and (row["status"] == "open" or row["closed_reason"] == "gap_gone"):
                q.execute("UPDATE research_question SET status='closed', closed_reason='resolved', closed_at=?, detail_json=? WHERE id=?", (ts, body, row["id"])); closed.append(row["id"])
            elif not row and line != detail:
                nid = ulid(); closed.append(nid)
                q.execute("INSERT INTO research_question (id,tree_id,subject_person_id,kind,q_key,detail_json,status,closed_reason,created_at,closed_at) VALUES (?,?,?,?,?,?,'closed','resolved',?,?)",
                          (nid, tree_id, person, "conflict", key, body, ts, ts))
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "update", "research_question", qid, dumps({**resolution, "questions_closed": closed})))
    for person in dict.fromkeys(people): plan_person(cx, tree_id, person, by)
    return {"ok": True, "question": qid, "event": ev["id"], "axis": axis, "kept": resolution["kept"], "set_aside": set_aside, "was": was, "questions_closed": closed}

FIRST_HAND = ("original", "derivative")         # the source classes the record of the event itself is read from: its own image, or an index or transcript of it

def rule_resolution(rq):
    """The resolution the rule wrote on a question row closed 'resolved' (its detail's resolution, by rule:…), else None."""
    if not rq or rq["kind"] != "conflict" or rq["status"] != "closed" or rq["closed_reason"] != "resolved": return None
    try: res = (json.loads(rq["detail_json"] or "{}") or {}).get("resolution")
    except ValueError: return None
    return res if isinstance(res, dict) and str(res.get("by") or "").startswith("rule:") else None

def owner_decided(cx, tree_id, ev, axis):
    """Words when the owner has spoken on this event's date or place: resolved a conflict on it, reopened one the rule had
    resolved (take_back's audit row, reopened), or dismissed one on it (a dismissal's line names the type and the axis, not
    the event, so a dismissal on any of the person's events of the type counts). The rule then leaves every conflict on it
    to the owner. None when the owner has not."""
    q = _q(cx); what = f"{ev['event_type'].lower()} {axis}"
    for r in q.execute("""SELECT json_extract(detail_json,'$.resolution.by') AS by FROM research_question WHERE tree_id=? AND kind='conflict' AND closed_reason='resolved'
                          AND json_valid(detail_json) AND json_extract(detail_json,'$.resolution.event')=? AND json_extract(detail_json,'$.resolution.axis')=?""", (tree_id, ev["id"], axis)):
        if not str(r["by"] or "").startswith("rule:"): return f"you resolved a difference on this {what} yourself: every later one is yours"
    if q.execute("""SELECT 1 FROM audit_log WHERE tree_id=? AND entity_kind='research_question' AND actor NOT LIKE 'rule:%' AND json_valid(diff_json)
                    AND json_extract(diff_json,'$.reopened') IS NOT NULL AND json_extract(diff_json,'$.event')=? AND json_extract(diff_json,'$.axis')=?""", (tree_id, ev["id"], axis)).fetchone():
        return f"you reopened the rule's resolution of this {what}: it is yours"
    people = [r["person_id"] for r in q.execute("""SELECT person_id FROM event_participant WHERE event_id=? AND person_id IS NOT NULL
                                                   UNION SELECT fm.person_id FROM event_participant ep JOIN family_member fm ON fm.family_id=ep.family_id AND fm.role='partner' WHERE ep.event_id=?""", (ev["id"], ev["id"]))]
    for r in q.execute(f"SELECT detail_json FROM research_question WHERE kind='conflict' AND closed_reason='dismissed' AND subject_person_id IN ({','.join('?' * len(people))})", people):
        try: d = (json.loads(r["detail_json"] or "{}") or {}).get("detail") or ""
        except ValueError: d = ""
        if d.startswith(what + ":"): return f"you dismissed a difference on this {what}: it is yours"
    return None

def classes_decide(cx, tree_id, eid, axis):
    """The rule's test on a conflict about one event's date or place (docs/RESEARCH-WORKFLOW.md §5–7, the proof standard:
    conflicts kept, cited, pointed out, then decided): (the assertion id of the statement it keeps, or None; why, a sentence
    in words from the classes). The statements on the event of its own type, rejected ones and the owner's own word aside,
    are read by their classes (data/evidence-classes.csv, catalog.evidence_classes), a place compared as the place its words
    are resolved to, as Catalog.disagreements compares it. A statement holds the event first-hand when it is primary
    information, accepted as the person's, from a record whose source class is original or derivative (the record of the
    event itself, or an index or transcript of it) and nobody can edit at will (T1–T3), direct evidence, and the event the
    record was made for: an event the table names primary for the record's kind (a census household's residence, a death
    record's death) for anyone on it, any other only for the person the record is about (Catalog.is_subject's reading: the
    persona others on the record relate to, never one relating to another), so a parent's birthplace on a child's birth
    register, primary by the table's row for the whole record, is no record of the parent's birth. The rule keeps the most
    specific first-hand statement, original before derivative, only when the classes favour its side without doubt: no
    statement that differs from it holds primary information, however it is held; none that differs is the owner's own
    word (the file's uncited claim the owner accepted), nor does a vouch stand for a tree's value that differs; and the
    statements that agree with it agree with one another, so a county kept while two towns in it still differ never closes
    a difference the classes do not decide. The sides that differ then rest only on secondary or indeterminable
    information, on a page anyone can edit, on an authored work or on the file's claim, and the reason names them
    (proof.sides). No first-hand statement, primary information against it, the owner's word against it, a difference left
    beside it, or an owner who has spoken on this event's date or place before (owner_decided): no decision, the conflict is
    the owner's, and the reason says which. A place is kept only once its words are resolved to a place, as resolve needs,
    the rule otherwise waiting on the owner's answer to the words."""
    from catalog import evidence_table
    from proof import axis_value, order, record_info, same_value, sides, specificity, subject_statements, words
    q = _q(cx); cat = Catalog(cx, tree_id); cache = {}
    ev = q.execute("SELECT * FROM event WHERE id=? AND tree_id=?", (eid, tree_id)).fetchone()
    if not ev: return None, "no such event in this tree"
    fact = ev["event_type"].lower()
    said = owner_decided(cx, tree_id, ev, axis)
    if said: return None, said
    sts, extra = [], {}
    for s in subject_statements(cat, "event", eid, want=ev["event_type"]):
        if s["status"] == "rejected": continue
        r = q.execute("""SELECT a.notes, ps.place_id, ps.status, pf.persona_id, NOT EXISTS (SELECT 1 FROM persona_relation pr WHERE pr.persona_id=pf.persona_id) AS own
                         FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE a.id=?""", (s["id"],)).fetchone()
        try: notes = json.loads(r["notes"]) if r["notes"] and r["notes"].startswith("{") else {}
        except ValueError: notes = {}
        extra[s["id"]] = {"notes": notes, "place_id": r["place_id"] if r["status"] == "accepted" else None, "own": bool(r["persona_id"] and r["own"])}
        resolved = extra[s["id"]]["place_id"]
        sts.append(dict(s, raw=s["place"], place=cat._place_chain(resolved)["text"] if resolved and s["place"] else s["place"]))
    vouched = any(s["kind"] == "vouch" and s["status"] == "accepted" for s in sts)
    valued = [s for s in sts if s["kind"] != "vouch" and axis_value(axis, s)]
    if not valued: return None, f"no statement on the {fact} gives a {axis}: nothing to decide"
    tree = {"start": ev["date_start"] or ev["date_end"], "text": ev["date_text"], "qualifier": ev["date_qualifier"]} if axis == "date" else (cat.place(eid, ev["place_id"]) or {}).get("text")
    if not ((tree or {}).get("start") if axis == "date" else tree): tree = None
    shown = lambda s: s["date"]["text"] if axis == "date" else s["raw"]
    trusted = lambda s: str(source_tier(cx, s["sha256"]) or "")[:2] in TRUSTED
    primary = lambda s: s["kind"] == "record" and (s["classes"] or {}).get("information") == "primary"
    owners_word = lambda s: s["kind"] == "file" and s["status"] == "accepted" and extra[s["id"]]["notes"].get("uncited")
    table = evidence_table()
    made_for = lambda s: any(r["field"] == ev["event_type"] and r.get("information") == "primary" for k in (s["classes"] or {}).get("kinds") or [] for r in table.get(k, []))   # the table names this event the record's own, for everyone on it (a census household's residence)
    def name(s):
        c = s["classes"] or {}; rec = record_info(cx, s["sha256"], cache)["name"]
        return f"the {c['original']} ({rec})" if c.get("original") else rec
    def rests(statements):
        parts = {}
        for s in statements:
            c = s["classes"] or {}
            if s["kind"] == "file": parts.setdefault("the file's claim", [])
            elif editable(cx, s["sha256"]): parts.setdefault("a page anyone can edit", []).append(name(s))
            elif c.get("source") == "authored": parts.setdefault("an authored work", []).append(name(s))
            elif c.get("information") == "secondary": parts.setdefault("secondary information", []).append(name(s))
            else: parts.setdefault("indeterminable information", []).append(name(s))
        return " and ".join(k + (f" ({'; '.join(dict.fromkeys(v))})" if v else "") for k, v in parts.items())
    def narrative(statements, only="", kept=None):
        """The sides these statements form, each with what it rests on, and the tree's own value when no statement gives it."""
        out = [f"{shown(g['statements'][0])} rests {only}on {rests(g['statements'])}" for g in sides(axis, statements)]
        if tree and not any(same_value(axis, tree, axis_value(axis, s)) for s in statements) and not (kept and same_value(axis, tree, kept)):
            out.append(f"the tree's own {tree['text'] if axis == 'date' else tree} rests {only}on no statement")
        return "; ".join(out)
    def not_first(s):
        """Why a primary statement does not hold the event first-hand, or None when it does."""
        c = s["classes"] or {}
        if s["status"] != "accepted": return "it is not accepted as this person's"
        if not trusted(s): return "it is a page anyone can edit"
        if c.get("source") not in FIRST_HAND: return f"its source is {c.get('source') or 'unclassed'}"
        if c.get("evidence") != "direct": return "it is indirect evidence"
        if not (extra[s["id"]]["own"] or made_for(s)): return f"the record was made for another person's event, and the {fact} it gives is a relative's"
        return None
    first = [s for s in valued if primary(s) and not_first(s) is None]
    if not first:
        held = next((s for s in valued if primary(s)), None)
        if held: return None, f"{name(held)} gives the {fact} as primary information, {shown(held)}, but {not_first(held)}: the conflict is yours"
        return None, f"no side holds primary information about the {fact}, so the classes favour none: {narrative(valued)}"
    keep = sorted(first, key=lambda s: (-specificity(axis, axis_value(axis, s)), order(s["classes"])))
    k = keep[0]; vk = axis_value(axis, k)
    beside = [s for s in valued if s is not k and same_value(axis, axis_value(axis, s), vk)]
    apart = [s for s in valued if s is not k and s not in beside]
    clash = next((s for s in apart if primary(s)), None)
    if clash: return None, f"primary information about the {fact} on more than one side: {name(k)} gives {shown(k)}, {name(clash)} {shown(clash)}"
    word = next((shown(s) for s in apart if owners_word(s)), None)
    if word is None and vouched and tree and not same_value(axis, tree, vk): word = tree["text"] if axis == "date" else tree   # a vouch stands for the tree's own value
    if word: return None, f"your own word stands on {word}, against {name(k)}'s {shown(k)}: the conflict is yours"
    left = next(((a, b) for i, a in enumerate(beside) for b in beside[i + 1:] if not same_value(axis, axis_value(axis, a), axis_value(axis, b))), None)
    if left: return None, f"{name(k)} states the {fact} first-hand only as {shown(k)}, which leaves {shown(left[0])} against {shown(left[1])}: the classes decide between none of them, so the conflict is yours"
    if axis == "place":
        placed = [s for s in keep if extra[s["id"]]["place_id"] and same_value(axis, axis_value(axis, s), vk) and specificity(axis, axis_value(axis, s)) >= specificity(axis, vk)]   # as fine a place as the one kept, never a coarser stand-in for it
        if not placed: return None, f"{name(k)} states the {fact} first-hand, but the place it gives, “{k['raw']}”, is not yet resolved to a place: the rule keeps it once its words are answered"
        k = placed[0]
    rest = narrative(apart, only="only ", kept=vk)
    return k["id"], f"{name(k)} states the {fact} first-hand, {shown(k)} ({words(k['classes'])}); " + (rest or "every other statement agrees with it")

def take_back(cx, tree_id, qid, by, why, ts, reopened=False):
    """A conflict the rule resolved, taken back: by the rule (rule_conflicts, when it would no longer resolve it so), or by
    the owner (reopen, or their own resolve over it). The event's date or place returns to what it was before the
    resolution (the resolution's own record of it, was), every question the resolution closed is set back to gap_gone so the
    plan reopens those whose difference is back, and one audit row says why and what was restored; reopened marks it the
    owner's reopen, after which the conflict on that date or place is the owner's (owner_decided). Evidence is untouched.
    Returns the question ids set back."""
    q = _q(cx)
    rq = q.execute("SELECT * FROM research_question WHERE id=? AND tree_id=?", (qid, tree_id)).fetchone()
    res = rule_resolution(rq)
    if not res: raise ValueError("not a conflict the rule resolved")
    primary, axis, was = res.get("question") or qid, res["axis"], res["was"]
    ev = q.execute("SELECT * FROM event WHERE id=?", (res["event"],)).fetchone()
    current = None
    if ev and axis == "date":
        current = {k: ev[k] for k in ("date_text", "date_start", "date_end", "date_qualifier")}
        q.execute("UPDATE event SET date_text=?, date_start=?, date_end=?, date_qualifier=?, updated_at=? WHERE id=?", (was["date_text"], was["date_start"], was["date_end"], was["date_qualifier"], ts, ev["id"]))
    elif ev:
        current = {"place_id": ev["place_id"]}
        q.execute("UPDATE event SET place_id=?, updated_at=? WHERE id=?", (was["place_id"], ts, ev["id"]))
    rows = q.execute("""SELECT id, subject_person_id FROM research_question WHERE tree_id=? AND closed_reason='resolved' AND json_valid(detail_json)
                        AND json_extract(detail_json,'$.resolution.question')=? AND json_extract(detail_json,'$.resolution.at')=?""", (tree_id, primary, res["at"])).fetchall()
    ids = [r["id"] for r in rows]
    q.execute(f"UPDATE research_question SET closed_reason='gap_gone' WHERE id IN ({','.join('?' * len(ids))})", ids)
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "update", "research_question", primary, dumps({"withdrawn": why, "event": res["event"], "axis": axis, "restored": was, "from": current,
                                                                                         "kept": res["kept"], "questions": ids, **({"reopened": why} if reopened else {})})))
    for person in dict.fromkeys(r["subject_person_id"] for r in rows): plan_person(cx, tree_id, person, by)
    return ids

def reopen(cx, tree_id, qid, by, note):
    """The owner reopens a conflict the rule resolved: taken back (take_back, reopened), the event's value back to what it was
    and the question open again, the owner's from now on; the rule never resolves that event's date or place again. Refused
    when the note is empty or the question is not one the rule resolved (the owner's own resolution stands as written).
    Returns what was done, or an error."""
    if not (note or "").strip(): return {"error": "a reopen needs your written reason (--note)"}
    rq = _q(cx).execute("SELECT * FROM research_question WHERE id=? AND tree_id=?", (qid, tree_id)).fetchone()
    res = rule_resolution(rq)
    if not res: return {"error": "not a conflict the rule resolved"}
    ids = take_back(cx, tree_id, qid, by, note, now(), reopened=True)
    st = _q(cx).execute("SELECT status FROM research_question WHERE id=?", (res.get("question") or qid,)).fetchone()
    return {"ok": True, "question": res.get("question") or qid, "event": res["event"], "axis": res["axis"], "restored": res["was"], "questions": ids, "open": bool(st and st["status"] == "open")}

def conflict_lines(cat, pid):
    """The person's conflict lines on an event's date or place as the catalog gives them now (Catalog.disagreements), each
    with its event and axis: [(line, event id, axis)]."""
    out = []
    for eid, in cat.q("""SELECT DISTINCT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                         WHERE ep.person_id=? OR ep.family_id IN (SELECT family_id FROM family_member WHERE person_id=? AND role='partner') ORDER BY e.event_type, e.date_start, e.id""", pid, pid):
        for line in cat.disagreements(pid, event=eid):
            m = CONFLICT_AXIS.match(line)
            if m: out.append((line, eid, m.group(2)))
    return out

def rule_conflicts(cx, tree_id, by, people=None, dry_run=False, known=None):
    """The rule on conflicts, acting for the owner (RULE_ACTOR conflict, "rule:… for <owner>"), over these people's (everyone's
    when people is None). First every conflict it resolved, examined again as it stands now, newest first on each event's
    date or place: one it would no longer resolve so (classes_decide keeps nothing, or a value on another side) is taken
    back (take_back), the event's value back to what it was; one the owner has spoken on since is left as it is. Then every
    open conflict on an event's date or place: where classes_decide keeps a statement it is resolved through resolve, the
    owner's own path, the rule's reason as the note; every other stays the owner's with the reason the rule left it. A person
    whose open conflict questions no longer read as the catalog does is planned again first, so the question resolved is
    the one the catalog gives; dry_run writes nothing and reads the catalog's own lines instead. Returns one row per
    resolution examined (kind resolution: kept, why) and per conflict decided or left (kind conflict: taken, why), each
    with the person, the question and its line; known, the questions the rule had resolved before a run that decides
    cards first (reconsider), makes a resolution written since, inside one of those decisions, a row of kind conflict
    taken, as one this pass wrote."""
    from plan import q_key
    q = _q(cx); ts = now(); cat = Catalog(cx, tree_id); out = []
    actor = f"{RULE_ACTOR['conflict']} for {by.split(' for ', 1)[-1] if by.startswith('rule:') else by}"
    name = lambda pid: (q.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone() or {"display_name": "?"})["display_name"]
    want = None if people is None else set(people)
    done = {}
    for rq in q.execute("""SELECT * FROM research_question WHERE tree_id=? AND kind='conflict' AND closed_reason='resolved' AND json_valid(detail_json)
                           AND json_extract(detail_json,'$.resolution.question')=id AND json_extract(detail_json,'$.resolution.by') LIKE 'rule:%'
                           ORDER BY json_extract(detail_json,'$.resolution.at') DESC, id DESC""", (tree_id,)).fetchall():
        if want is not None and rq["subject_person_id"] not in want: continue
        res = rule_resolution(rq); spot = (res["event"], res["axis"])
        if done.get(spot): continue                                      # a newer resolution on the same date or place stands: the older ones under it stand with it
        detail = (json.loads(rq["detail_json"]) or {}).get("detail")
        ev = q.execute("SELECT * FROM event WHERE id=?", (res["event"],)).fetchone()
        said = owner_decided(cx, tree_id, ev, res["axis"]) if ev else "the event is gone"
        if said:
            done[spot] = True; out.append({"kind": "resolution", "person": name(rq["subject_person_id"]), "question": rq["id"], "detail": detail, "kept": True, "why": said}); continue
        keep, why = classes_decide(cx, tree_id, res["event"], res["axis"])
        holds = keep is not None and (keep == res["kept"]["assertion"] or kept_agrees(cx, keep, res))
        if keep is not None and not holds: why = f"it would now keep another value: {why}"
        if not holds and not dry_run: take_back(cx, tree_id, rq["id"], actor, why, ts)
        done[spot] = holds
        if holds and known is not None and rq["id"] not in known:        # written during this run, inside a decision: told as resolved here
            out.append({"kind": "conflict", "person": name(rq["subject_person_id"]), "question": rq["id"], "detail": detail, "taken": True, "why": res.get("note") or why}); continue
        out.append({"kind": "resolution", "person": name(rq["subject_person_id"]), "question": rq["id"], "detail": detail, "kept": holds, "why": why})
    pids = list(dict.fromkeys(people)) if people is not None else \
           [r["subject_person_id"] for r in q.execute("SELECT DISTINCT subject_person_id FROM research_question WHERE tree_id=? AND kind='conflict' AND status='open' ORDER BY subject_person_id", (tree_id,))]
    opened = lambda pid: {(json.loads(r["detail_json"] or "{}") or {}).get("detail"): r["id"] for r in q.execute("SELECT id, detail_json FROM research_question WHERE subject_person_id=? AND kind='conflict' AND status='open'", (pid,))}
    for pid in pids:
        lines = conflict_lines(cat, pid); now_lines = {l for l, _, _ in lines}; open_ = opened(pid)
        if not dry_run and any(CONFLICT_AXIS.match(d or "") and d not in now_lines for d in open_):
            plan_person(cx, tree_id, pid, by); open_ = opened(pid)    # the questions as the catalog gives them now
        seen = set()
        for line, eid, axis in lines:
            if (eid, axis) in seen: continue
            qid = open_.get(line)
            if qid is None:
                if not dry_run: continue                                 # not an open question: resolved, dismissed or closed with its event and axis
                closed = q.execute("SELECT closed_reason FROM research_question WHERE subject_person_id=? AND q_key=? AND status='closed'", (pid, q_key({"kind": "conflict", "detail": line}))).fetchone()
                if closed and closed["closed_reason"] != "gap_gone": continue
            elif q.execute("SELECT status FROM research_question WHERE id=?", (qid,)).fetchone()["status"] != "open": seen.add((eid, axis)); continue
            seen.add((eid, axis))
            keep, why = classes_decide(cx, tree_id, eid, axis)
            taken = keep is not None
            if taken and not dry_run:
                r = resolve(cx, tree_id, qid, keep, actor, why)
                if "error" in r: taken, why = False, r["error"]
            out.append({"kind": "conflict", "person": name(pid), "question": qid, "detail": line, "taken": taken, "why": why})
    return out

def kept_agrees(cx, keep, res):
    """Whether the statement the rule would keep now gives the same value its resolution kept (another first-hand record of
    the same date or place, on the same side)."""
    from proof import same_value
    r = _q(cx).execute("""SELECT pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id
                          LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE a.id=?""", (keep,)).fetchone()
    if not r: return False
    kept = res["kept"]["value"]
    if res["axis"] == "date":
        k = _q(cx).execute("""SELECT pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id WHERE a.id=?""", (res["kept"]["assertion"],)).fetchone()
        if not k: return False
        return same_value("date", {"start": r["date_start"] or r["date_end"], "text": r["date_text"], "qualifier": r["date_qualifier"]},
                          {"start": k["date_start"] or k["date_end"], "text": k["date_text"], "qualifier": k["date_qualifier"]})
    return bool(r["raw"] and kept and same_value("place", r["raw"], kept))

def living(cx, tree_id, pid, word, by, note):
    """The owner's word on whether a person is alive, above the tier rule (docs/DATA-ARCHITECTURE.md §7 decision 3):
    person.living_override set to living or deceased, or cleared by unknown so the rule decides again; one audit row. Returns
    what was and is, with the default's reading afterwards."""
    q = _q(cx); ts = now()
    row = q.execute("SELECT living_override FROM person WHERE id=? AND tree_id=?", (pid, tree_id)).fetchone()
    if not row: raise ValueError("no such person in this tree")
    value = None if word == "unknown" else word
    q.execute("UPDATE person SET living_override=?, updated_at=? WHERE id=?", (value, ts, pid))
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "update", "person", pid, dumps({"living_override": {"was": row["living_override"], "now": value}, "note": note})))
    return {"was": row["living_override"], "now": value, **Catalog(cx, tree_id).living(pid)}

def withdraw(cx, tree_id, prop_id, by, why, ts):
    """The rule takes back a decision it would no longer make: the proposal and the persona link return to Undecided, every
    assertion the decision wrote returns to Undecided, and so does the name alias it wrote (an Accept later makes them
    Accepted again), the questions the decision answered are closed as gap_gone so the plan reopens the ones whose gap is
    back, and the audit row says why. The record is a card for the owner again. Returns how many assertions were taken
    back."""
    q = _q(cx)
    p = q.execute("SELECT * FROM proposal WHERE id=? AND tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%'", (prop_id, tree_id)).fetchone()
    if not p: raise ValueError("not a decision the rule made")
    pay = json.loads(p["payload_json"])
    n = q.execute("UPDATE assertion SET status='undecided' WHERE tree_id=? AND status='accepted' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?", (tree_id, prop_id)).rowcount
    q.execute("UPDATE alias SET status='undecided' WHERE tree_id=? AND status='accepted' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?", (tree_id, prop_id))
    q.execute("UPDATE proposal SET status='undecided', decided_by=NULL, decided_at=NULL, decision_note=? WHERE id=?", (f"the rule took its decision back: {why}", prop_id))
    ids = same_personas(cx, pay["persona_id"])                       # every reading's persona of this name and role on the record, the re-reads' included
    q.execute(f"UPDATE person_persona SET status='undecided', decided_by=NULL, decided_at=NULL WHERE person_id=? AND persona_id IN ({','.join('?' * len(ids))})", (pay["person_id"], *ids))
    q.execute("UPDATE research_question SET closed_reason='gap_gone', answered_by_proposal_id=NULL WHERE answered_by_proposal_id=?", (prop_id,))
    for pid in dict.fromkeys([pay.get("person_id"), pay.get("subject_person_id")]):
        if pid: plan_person(cx, tree_id, pid, by)
    q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
              (ulid(), tree_id, ts, by, "update", "proposal", prop_id, dumps({"withdrawn": why, "persona": pay["persona_id"], "person": pay["person_id"], "assertions": n})))
    return n

def repropose(cx, tree_id, by, ts, dry_run=False):
    """Every current extraction whose undecided cards an older matcher wrote is matched again: those cards close rejected with
    the note superseded, as a re-read closes the cards of the reading it supersedes, and the matcher as it stands now proposes
    the same personas again, the rule taking what it takes (match_record). A card the owner or the rule already decided is
    untouched. Returns (rows for the cards superseded, kind rematch, and the cards the rule took on the re-run, kind card)."""
    q = _q(cx); out = []; taken_rows = []
    current = q.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", MATCHER).fetchone()
    stale = [r["id"] for r in q.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND id IS NOT ?", (MATCHER[0], MATCHER[1], current["id"] if current else None))]
    if not stale: return out, taken_rows
    marks = ",".join("?" * len(stale))
    name = lambda pay: (q.execute("SELECT display_name FROM person WHERE id=?", (pay.get("person_id"),)).fetchone() or {"display_name": "(a new person)"})["display_name"]
    persona = lambda pay: q.execute("SELECT name_text FROM persona WHERE id=?", (pay["persona_id"],)).fetchone()["name_text"]
    eids = [r["id"] for r in q.execute(f"""SELECT DISTINCT e.id FROM proposal p JOIN extraction e ON e.id=json_extract(p.payload_json,'$.extraction_id')
                                            WHERE p.tree_id=? AND p.status='undecided' AND p.kind IN ('persona_match','new_person') AND p.generated_by IN ({marks}) AND e.superseded_by IS NULL
                                            ORDER BY e.ran_at, e.id""", (tree_id, *stale))]
    for eid in eids:
        old = q.execute(f"""SELECT p.id, p.payload_json, x.version FROM proposal p JOIN extractor x ON x.id=p.generated_by
                             WHERE p.tree_id=? AND p.status='undecided' AND p.kind IN ('persona_match','new_person') AND p.generated_by IN ({marks})
                             AND json_extract(p.payload_json,'$.extraction_id')=? ORDER BY p.created_at, p.id""", (tree_id, *stale, eid)).fetchall()
        for p in old:
            pay = json.loads(p["payload_json"])
            out.append({"proposal": p["id"], "person": name(pay), "persona": persona(pay), "kind": "rematch", "taken": True, "why": f"the matcher at {p['version']} wrote it; superseded, proposed again at {MATCHER[2]}"})
            if dry_run: continue
            q.execute("UPDATE proposal SET status='rejected', decided_by=?, decided_at=?, decision_note='superseded' WHERE id=?", (by, ts, p["id"]))
            q.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                      (ulid(), tree_id, ts, by, "reject", "proposal", p["id"], dumps({"closed": "superseded", "matcher": p["version"], "now": MATCHER[2], "extraction": eid})))
        if dry_run: continue
        written, taken = match_record(cx, eid, by)
        for prop_id, pname, why in taken:
            pay = json.loads(q.execute("SELECT payload_json FROM proposal WHERE id=?", (prop_id,)).fetchone()["payload_json"])
            taken_rows.append({"proposal": prop_id, "person": name(pay), "persona": pname, "kind": "card", "taken": True, "why": why})
    return out, taken_rows

def reconsider(cx, tree_id, by, dry_run=False):
    """Every decision the rule made, oldest first, examined again as the rule stands now, on the ground that stood before it:
    the assertions of that decision, of every rule decision after it and of every decision already withdrawn do not count, so
    each rests only on the owner's decisions and on earlier rule decisions that survived. One the rule would no longer take is
    withdrawn. Then every current extraction whose undecided cards an older matcher wrote is matched again (repropose): those
    cards close as superseded and the matcher as it stands now proposes the personas again. Then every persona-match card
    still undecided, oldest first, examined as the rule stands now: one it would now
    take is taken, recorded as the rule; a decision can open another card, so the pass repeats until nothing new is taken.
    Then the conflicts (rule_conflicts): every conflict the rule resolved examined again, one it would no longer resolve so
    taken back with the event's value restored, and every open conflict on an event's date or place resolved where the
    classes favour one side without doubt (classes_decide), the rest left to the owner with the reason.
    Last, every results-page row still undecided whose person is already accepted directly on the row's own record closes
    rejected (close_result_rows): a row can outlive the record it summarizes when the record was accepted before the row's
    own card was ever written, so this is swept on every run, not only at accept-time.
    Returns one row per decision, per card superseded, per card, per conflict and per closed row: kind (decision, rematch,
    card, resolution, conflict or row), the person, kept or taken, why; a card's rows the proposal and the persona, a
    conflict's the question and its line."""
    q = _q(cx); ts = now(); out = []; gone = []
    known = {r["id"] for r in q.execute("SELECT id FROM research_question WHERE tree_id=? AND closed_reason='resolved' AND json_valid(detail_json) AND json_extract(detail_json,'$.resolution.by') LIKE 'rule:%'", (tree_id,))}
    rows = q.execute("SELECT * FROM proposal WHERE tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%' ORDER BY decided_at, id", (tree_id,)).fetchall()
    ids = [r["id"] for r in rows]
    name = lambda pay: (q.execute("SELECT display_name FROM person WHERE id=?", (pay.get("person_id"),)).fetchone() or {"display_name": "(a new person)"})["display_name"]
    persona = lambda pay: q.execute("SELECT name_text FROM persona WHERE id=?", (pay["persona_id"],)).fetchone()["name_text"]
    for i, p in enumerate(rows):
        pay = json.loads(p["payload_json"])
        ok, why = rule_accepts(cx, tree_id, p, without=tuple(ids[i:] + gone))
        if not ok:
            gone.append(p["id"])
            if not dry_run: withdraw(cx, tree_id, p["id"], by, why, ts)
        out.append({"proposal": p["id"], "person": name(pay), "persona": persona(pay), "kind": "decision", "kept": ok, "why": why})
    rematched, retaken = repropose(cx, tree_id, by, ts, dry_run=dry_run)
    out += rematched
    cards = {r["proposal"]: r for r in retaken}                      # proposal id -> the row of its latest examination; the re-run's own decisions first
    taken = True
    while taken:
        taken = False
        for p in q.execute("SELECT * FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person') ORDER BY created_at, id", (tree_id,)).fetchall():
            if p["id"] in cards and cards[p["id"]]["taken"]: continue
            pay = json.loads(p["payload_json"]); ok, why = rule_accepts(cx, tree_id, p)
            if ok and not dry_run: decide(cx, tree_id, p["id"], "accepted", f"{RULE_ACTOR[p['kind']]} for {by}", note=why); taken = True
            cards[p["id"]] = {"proposal": p["id"], "person": name(pay), "persona": persona(pay), "kind": "card", "taken": ok, "why": why}
    conflicts = rule_conflicts(cx, tree_id, by, dry_run=dry_run, known=known)   # its resolutions examined again, then every open conflict on a date or a place
    rows_out = []; seen = set()
    for p in q.execute("SELECT * FROM proposal WHERE tree_id=? AND status='undecided' AND kind='persona_match'", (tree_id,)).fetchall():
        pid = json.loads(p["payload_json"]).get("person_id")
        if not pid or pid in seen: continue
        seen.add(pid)
        for rid, rname in close_result_rows(cx, tree_id, pid, f"rule:record-accepted for {by}", ts, dry_run=dry_run):
            rows_out.append({"proposal": rid, "person": q.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()["display_name"], "persona": rname,
                              "kind": "row", "taken": True, "why": "the record itself is accepted"})
    return out + list(cards.values()) + conflicts + rows_out

def main():
    ap = argparse.ArgumentParser(description="The standing rule's decisions examined again; the owner's word on a family link, a divorce, a duplicate or whether a person is alive.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dc = sub.add_parser("decide", help="the decision on a card: is this record's persona this person (or a new person)"); dc.add_argument("proposal"); dc.add_argument("verdict", choices=["accept", "reject"]); dc.add_argument("--note")
    fc = sub.add_parser("fact", help="a key fact of a person decided: accept touches held evidence or is your own word (a vouch); reject and undecided touch every assertion behind it")
    fc.add_argument("person"); fc.add_argument("field"); fc.add_argument("verdict", choices=["accept", "reject", "undecided"]); fc.add_argument("--note")
    ac = sub.add_parser("assertion", help="one statement of one record on one subject, decided on its own (a fact decision touches every statement behind the fact)")
    ac.add_argument("assertion"); ac.add_argument("verdict", choices=["accept", "reject", "undecided"]); ac.add_argument("--note")
    pc = sub.add_parser("place", help="a record's fact onto the event the owner means: an undated one (Catalog.unplaced), or one asserted on another event of its type, moved; an event left with no statement but rejected ones leaves the person")
    pc.add_argument("persona_fact"); pc.add_argument("--event", required=True, dest="event"); pc.add_argument("--note")
    ls = sub.add_parser("facts", help="a person's key facts, events and attributes with their ids, and every statement behind each with its id, status and record"); ls.add_argument("person")
    r = sub.add_parser("reconsider", help="the rule re-examines every decision it made, every card still undecided and every conflict: a decision or a resolution it would no longer make is taken back, a card or a conflict it would now decide is decided")
    r.add_argument("--dry-run", action="store_true", help="report only")
    l = sub.add_parser("link", help="place a person in a family on your own word, on a record that stops short of naming both parties")
    l.add_argument("person"); g = l.add_mutually_exclusive_group(required=True); g.add_argument("--spouse"); g.add_argument("--parent", action="append")
    l.add_argument("--record", required=True, help="sha256 of the archived record"); l.add_argument("--note", required=True, help="your reason, kept on the assertion")
    l.add_argument("--marriage", help="the marriage date the record gives, GEDCOM form (14 AUG 1959)")
    d = sub.add_parser("divorce", help="a Divorce event between two people, with the evidence you name")
    d.add_argument("a"); d.add_argument("b"); d.add_argument("--date", help="GEDCOM form (BET 1950 AND 1959)")
    d.add_argument("--evidence", action="append", required=True, help="sha256[:persona fact id][:citation words]"); d.add_argument("--note", required=True)
    mg = sub.add_parser("merge", help="close a duplicate_person question: move the duplicate's evidence links onto the person it duplicates")
    mg.add_argument("duplicate"); mg.add_argument("--into", dest="kept", required=True); mg.add_argument("--note", required=True, help="why these are the same person, kept on the proposal")
    lv = sub.add_parser("living", help="your own word on whether a person is alive, above the tier rule; unknown clears it so the rule decides again")
    lv.add_argument("person"); lv.add_argument("word", choices=["living", "deceased", "unknown"]); lv.add_argument("--note", required=True, help="your reason, kept on the audit row")
    rs = sub.add_parser("resolve", help="close a conflict question with your reason, the statement whose date or place the event keeps named; the others stay as their records say; over the rule's own resolution, yours stands")
    rs.add_argument("question"); rs.add_argument("--keep", required=True, help="the assertion id of the statement kept (tools/conclude.py facts lists them)"); rs.add_argument("--note", required=True, help="your reason, kept on the question and the audit row")
    ro = sub.add_parser("reopen", help="a conflict the rule resolved, taken back: the event's value as it was, the question open again and yours from now on")
    ro.add_argument("question"); ro.add_argument("--note", required=True, help="your reason, kept on the audit row")
    for x in (dc, fc, ac, pc, ls, r, l, d, mg, lv, rs, ro):
        x.add_argument("--tree"); x.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); x.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    cx.execute("BEGIN")
    try:
        if a.cmd == "decide":
            res = decide(cx, tree_id, a.proposal, "accepted" if a.verdict == "accept" else "rejected", a.by, note=a.note)
            if "error" in res: raise SystemExit(res["error"])
            who = cx.execute("SELECT display_name FROM person WHERE id=?", (res["person"],)).fetchone()
            print(f"{res['status']}: {res['kind'].replace('_', ' ')} {who[0] if who else ''}; {res['assertions']} assertion(s), {len(res['memberships'])} family link(s), {len(res['answered'])} question(s) answered")
            if res["status"] == "accepted" and res["identity"]: print("    an identity on a page anyone can edit: the link accepted; the family links and every fact it states are written undecided, never accepted")
            if res["status"] == "accepted" and res["person"]:
                sha = cx.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (res["persona"],)).fetchone()[0]
                for f in record_says(cx, tree_id, res["person"], sha): print(f"    {f['status']:9} {f['fact']}" + (f"  [conflict: {f['disagrees']}]" if f["disagrees"] else ""))
            nm = lambda i: cx.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()[0]
            for m in res["memberships"]:
                if m.get("placed") == "sibling": print("   ", f"{nm(m['person'])} placed beside {nm(m['of'])} as a child of the same parents, undecided: the record states a sibling, not the parents")
                elif m.get("undecided"): print("   ", f"{nm(m['person'])} {'child' if m['role'] == 'child' else 'spouse'} of {nm(m['of'])}: a page anyone can edit states it, undecided" + ("" if m["new"] else "; this record cited as evidence on the link"))
                else: print("   ", f"{nm(m['person'])} {'child' if m['role'] == 'child' else 'spouse'} of {nm(m['of'])}: " + ("a new link, on this record" if m["new"] else "this record accepted as evidence on the link"))
            left = cx.execute("SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND json_extract(payload_json,'$.artifact_sha256')=(SELECT json_extract(payload_json,'$.artifact_sha256') FROM proposal WHERE id=?)", (tree_id, a.proposal)).fetchone()[0]
            print(f"    {left} card(s) still waiting on this record" if left else "    nothing else waits on this record")
            for rid, rname in res["closed_rows"]: print("   ", f"{rname} (result), a results-page row for {nm(res['person'])}, closed rejected: the record itself is accepted [{rid[-6:]}]")
            for x in res["conflicts"]:
                if x["kind"] == "conflict" and x["taken"]: print("   ", f"the rule resolved {x['person']}'s {x['detail'].split(':', 1)[0]}: {x['why']}")
                elif x["kind"] == "resolution" and not x["kept"]: print("   ", f"the rule took back its resolution of {x['person']}'s {x['detail'].split(':', 1)[0]}: {x['why']}")
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
        elif a.cmd == "place":
            res = place(cx, tree_id, a.persona_fact, a.event, a.by, a.note)
            if "error" in res: raise SystemExit(res["error"])
            who = cx.execute("SELECT display_name FROM person WHERE id=?", (res["person"],)).fetchone()[0]
            print(f"persona fact {a.persona_fact[-6:]} placed on event {res['event']}: {res['status']}, {who} [{res['person'][-6:]}]; plan regenerated")
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
                if x["kind"] in ("resolution", "conflict"):
                    verdict = ("kept" if x["kept"] else "would take back" if a.dry_run else "taken back") if x["kind"] == "resolution" \
                              else ("would resolve" if a.dry_run else "resolved") if x["taken"] else "left to you"
                    print(f"{verdict:19} {x['person']} [{x['question'][-6:] if x['question'] else 'no question yet'}] {x['detail']}: {x['why']}"); continue
                verdict = ("kept" if x["kept"] else "would withdraw" if a.dry_run else "withdrawn") if x["kind"] == "decision" \
                          else ("would close" if a.dry_run else "closed") if x["kind"] == "row" else ("would propose again" if a.dry_run else "proposed again") if x["kind"] == "rematch" \
                          else ("would take" if x["taken"] and a.dry_run else "taken" if x["taken"] else "refused")
                print(f"{verdict:19} {x['person']} <- {x['persona']} [{x['proposal'][-6:]}]: {x['why']}")
            if not rows: print("the rule has made no decision in this tree, and no card or conflict waits")
            else: print(f"{sum(1 for x in rows if x['kind'] == 'decision')} decision(s) examined, {sum(1 for x in rows if x['kind'] == 'rematch')} older card(s) {'it would propose again' if a.dry_run else 'proposed again'}, "
                        f"{sum(1 for x in rows if x['kind'] == 'card' and x['taken'])} card(s) {'it would take' if a.dry_run else 'taken'}, "
                        f"{sum(1 for x in rows if x['kind'] == 'card' and not x['taken'])} refused, "
                        f"{sum(1 for x in rows if x['kind'] == 'resolution' and not x['kept'])} of {sum(1 for x in rows if x['kind'] == 'resolution')} resolution(s) {'it would take back' if a.dry_run else 'taken back'}, "
                        f"{sum(1 for x in rows if x['kind'] == 'conflict' and x['taken'])} conflict(s) {'it would resolve' if a.dry_run else 'resolved'}, "
                        f"{sum(1 for x in rows if x['kind'] == 'conflict' and not x['taken'])} left to you, {sum(1 for x in rows if x['kind'] == 'row')} results row(s) {'it would close' if a.dry_run else 'closed'}")
        elif a.cmd == "link":
            pid = cat.find_person(a.person)
            marriage = None
            if a.marriage: marriage = {"date_text": a.marriage, **{k: v for k, v in parse_gedcom_date(a.marriage).items() if k != "calendar"}}
            if marriage: marriage["qualifier"] = marriage.pop("date_qualifier")
            if a.spouse: fid = link_on_word(cx, tree_id, pid, cat.find_person(a.spouse), "spouse", a.record, a.by, a.note, marriage=marriage)
            else: fid = link_on_word(cx, tree_id, pid, [cat.find_person(x) for x in a.parent], "child", a.record, a.by, a.note)
            print(f"family {fid}: {a.person} placed on your word; the record {a.record[:12]} carries the assertion")
        elif a.cmd == "divorce":
            ev = []
            for e in a.evidence:
                parts = e.split(":", 2); ev.append((parts[0], parts[1] or None if len(parts) > 1 else None, parts[2] if len(parts) > 2 else "the record's own words"))
            eid = divorce(cx, tree_id, cat.find_person(a.a), cat.find_person(a.b), a.date, ev, a.by, a.note)
            print(f"divorce event {eid} between {a.a} and {a.b}")
        elif a.cmd == "resolve":
            res = resolve(cx, tree_id, a.question, a.keep, a.by, a.note)
            if "error" in res: raise SystemExit(res["error"])
            print(f"resolved: the event's {res['axis']} is now {res['kept']['value']} ({res['kept']['record']}); set aside, as their records say: "
                  + ("; ".join(f"{s['value']} ({s['record']})" for s in res["set_aside"]) or "nothing") + f"; {len(res['questions_closed'])} question(s) closed")
        elif a.cmd == "reopen":
            res = reopen(cx, tree_id, a.question, a.by, a.note)
            if "error" in res: raise SystemExit(res["error"])
            was = res["restored"].get("date_text") if res["axis"] == "date" else res["restored"].get("place")
            print(f"reopened: the rule's resolution taken back, the event's {res['axis']} {was or 'empty'} again; the question is " + ("open" if res["open"] else "closed: the difference no longer reads as it did")
                  + f"; the rule leaves this {res['axis']} to you from now on")
        elif a.cmd == "living":
            pid = cat.find_person(a.person); res = living(cx, tree_id, pid, a.word, a.by, a.note)
            print(f"{cx.execute('SELECT display_name FROM person WHERE id=?', (pid,)).fetchone()[0]} [{pid[-6:]}]: living_override {res['was'] or 'none'} -> {res['now'] or 'none'}; "
                  f"the default now reads {res['status']} ({res['reason']}); the plan next: tools/plan.py")
        else:
            kept_id = cat.find_person(a.kept)
            six = re.search(r"\[([A-Z0-9]{6})\]\s*$", a.duplicate)          # a duplicate already merged into this person is named among those merged into them, by name or six characters
            already = [i for i, n in cx.execute("SELECT id, display_name FROM person WHERE tree_id=? AND merged_into=?", (tree_id, kept_id)) if n == a.duplicate or (six and i.endswith(six.group(1)))]
            res = merge(cx, tree_id, already[0] if len(already) == 1 else cat.find_person(a.duplicate), kept_id, a.by, a.note)
            if res.get("completed"):
                print(f"{a.duplicate} already merged into {a.kept}; completed: {res['events_folded']} event(s) folded ({res['event_assertions_folded']} statement(s) moved), "
                      f"{res['families_folded']} family(ies) folded ({res['family_children_moved']} child membership(s), {res['family_events_moved']} family event(s))")
            else: print(f"{a.duplicate} merged into {a.kept}: {res['persona_links']} persona link(s), {res['assertions']} assertion(s), "
                  f"{res['event_participants']} event participant(s), {res['family_memberships']} family membership(s), "
                  f"{res['plan_steps_moved']} plan step(s) moved ({res['plan_steps_dropped']} dropped as already on the kept person's plan, "
                  f"{res['log_rows_repointed']} log row(s) repointed onto it), {res['questions_moved']} question(s) moved "
                  f"({res['questions_dropped']} already open on the kept person); proposal {res['proposal']}")
        cx.commit()
    except Exception:
        cx.rollback(); raise

if __name__ == "__main__": main()
