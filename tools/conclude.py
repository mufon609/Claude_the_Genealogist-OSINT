#!/usr/bin/env python3
"""What a decision about a document writes on the tree, and the standing rule that takes the decision when it is certain.

The owner decides documents, not facts: one decision per record about a person, is this them. Yes accepts everything the
record states about the person: its facts become Accepted assertions on the person's events and attributes (created from the
record when the tree had none), and the family links it states with people already matched on the same record are Accepted
too, unless the record is a page anyone can edit or the link is one the record's indexer computed, where the memberships are
created but their assertions stay Undecided, the way a sibling placement already is. Where the record disagrees with the
tree's own value the record's statement is still accepted as what that record says, the tree's value stays, and the
difference is a conflict question the generator raises (Catalog.disagreements). A new person is created by the owner, or by
the rule when a trusted record (T1–T2, or an obituary once read) names them with a name in a family relationship it states
to a person accepted on that record and nobody in the tree fits after the fitting check (rule_creates); a creation is judged
on its record's current reading by those same terms, and a card putting the entry it made a person from to that person
is judged as that creation (made_here). Anything less certain than the rule below is a card for the owner.

The standing rule (docs/RESEARCH-WORKFLOW.md §0 and §5–7, rule_accepts): a record of a kind data/evidence-classes.csv gives
the automated standing, from a source nobody can edit at will (T1–T3), is accepted as the person's when the name agrees with
the accepted name, the facts that agree make two points on the tree's own statements (ground: a date to the day or a
relationship counting double whatever its information class, a statement of any copy of the record, or of the same person's record of the same event from the same original, no ground) and nothing compared disagrees against an accepted value. A page anyone can edit (T4: a Find a Grave
memorial, a WikiTree profile) identifies a person but never builds their facts: accepting it, by the owner or by the rule,
writes the persona link and the memberships the page states, Undecided, and every fact the page types as an Undecided
assertion; the rule takes such an identity on the name and three of birth day, death day, burial place, a stated parent or
spouse, the relatives the page lists one of the four at most and only one the tree links so, claimed or accepted
(claimed_or_accepted). Whatever the route, identity is tested before the rule takes a record or creates a person from it
(identity_refused, docs/DATA-ARCHITECTURE.md §7 decision 12): nobody else of the tree fits the persona as well, the person holds no other
persona on that reading of the record, and nothing the record would add falls outside the person's accepted life
(data/life-limits.csv); a test that fails is a refusal with its reason. The rule acts on the owner's word, is recorded as
such on the proposal and in the audit log, and the owner can reject what it accepted: the link and every assertion it wrote turn rejected, with the family links it was one of the two acceptances for (links_resting_on). The rule can also take a decision back (reconsider): every
decision it made is examined again as the rule stands now, in the order it took them, on the ground that stood before it, and one it would
no longer take is withdrawn, the record a card for the owner again, with the family links it was one of the two acceptances for
(links_resting_on), which no later decision stands on; then every card still undecided is examined the same
way, and one the rule would now take is taken. Between the two, every undecided card the evidence has passed by is matched
again (rematch): one an older matcher wrote (the matcher is versioned, match.MATCHER), one left on a reading of its record
read again since, and one the matcher would no longer put to that person as the person's evidence now stands close as
superseded, and their records' current readings are matched again, the matcher proposing the personas afresh as it
stands; a card it still puts to the same person keeps its id and takes the matcher's words as they now read. Every
decision that changes a person's evidence matches that person's cards again the same way as it is taken (rematch_people:
a card, a key fact, one statement, a place's words, a resolution or a reopen, a placement, a link, a divorce, a merge).

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
       tools/conclude.py place <persona fact id> --event <event id> [--note "…"]   a record's fact onto the event it belongs to: one whose event is your choice (Catalog.unplaced), or one asserted on the wrong event, moved
       tools/conclude.py facts "<person>"                                          every fact with its event id and every statement behind it with its id
       tools/conclude.py reconsider [--dry-run]                                   the rule re-examines its decisions and the cards it refused; the cards the evidence has passed by matched again
       tools/conclude.py link "<person>" --spouse "<other>" --record <sha256> --note "…" [--marriage "14 AUG 1959"]
       tools/conclude.py link "<person>" --parent "<other>" [--parent "<other>"] --record <sha256> --note "…"
       tools/conclude.py divorce "<a>" "<b>" --date "BET 1950 AND 1959" --evidence <sha256>[:<persona fact id>][:<citation>] … --note "…"
       tools/conclude.py merge "<duplicate>" --into "<person>" --note "…"          close a duplicate_person question: the duplicate's row stays, out of every listing
       tools/conclude.py resolve <question id> --keep <assertion id> --note "…"    close a conflict question: the event keeps that statement's date or place
       tools/conclude.py reopen <question id> --note "…"                           a conflict the rule resolved, taken back and yours from now on
       tools/conclude.py copies <file>[@<number>] <file>[@<number>] --note "…"    two archived files (a listing's row by its number) one record on your word
       tools/conclude.py apart <file>[@<number>] <file>[@<number>] --note "…"     two records on your word, above what code found: what one carried to the other given back
       common: [--tree slug] [--db catalog/tree.db] [--by user:<you>]

- decide: a person's (or the rule's) decision on a proposal, with everything that follows from it; a command too, as is a
  key fact's decision (tools/facts.py).
- match_record: the matcher on an extraction, then the rule on every proposal it wrote.
- rule_accepts: whether the rule takes a proposal, and why or why not, in words: on its points (rule_points), then identity tested
  (identity_refused: fits_as_well, a second persona on the reading, outside_life); ground: the tree's statements a point stands on.
- reconsider, withdraw: the rule's decisions examined again; one it would no longer take, taken back with the family links it was
  one of the two acceptances for (links_resting_on); a card it would now take, taken.
- rematch, rematch_people: the undecided cards the evidence has passed by matched again, for everyone (reconsider) or for the
  people a decision changed: closed as superseded and their records matched again, or their rationale the matcher's words as
  they now read.
- link_on_word, divorce: the owner's word placing a person in a family on a record, or ending a marriage.
- same_personas: a decision, a withdrawal or a rejection applies to every reading's persona of that entry of the record (its record
  id, else its role, row and name), never to another row of the same name.
- join_copies, carry, copies_on_word: one record is one source wherever it is held (docs/DATA-ARCHITECTURE.md §7 decision 15):
  code's joins of two archived copies of one record (same_record), each decision carried to every copy's persona of its
  entry, and the owner's word joining two copies or keeping two apart; record_self and copy_cards, the record under
  decision as the rule counts it, once, and as every copy holds it.
- decide_place: the owner's answer on a place string the resolver left undecided, which real place its words mean or that they are
  not a place, applied wherever the same words appear, and to every other string whose card offers the same places (the same
  question put another way), each its own audit row; --alone answers one string only.
- assert_facts, link_family, create_person: the writes themselves, shared with the extractor when a re-run carries a link; one statement on one event.
- a person's own decision on a statement (docs/RESEARCH-WORKFLOW.md §5–7: a key fact or the statement decided, a vouch, the
  owner's word on a link or a divorce, a card's rejection) sets assertion.person_decided; every writer here reads it, and
  no acceptance of a record, re-read, carry, withdrawal or give-back changes such a statement. asserted_by names who set the
  status a statement has.
- place: the owner's answer to Catalog.unplaced, a record's fact written onto the event the owner means.
- fold, fold_plan: a person's or a family's events of one type that are one event folded into one, as a merge and tools/initdb.py's migration of an older catalog fold them.
- resolve: the answer to a conflict question, the statement whose date or place the event keeps, with the reason: the owner's,
  or the rule's (rule_conflicts, classes_decide); take_back and reopen: a resolution of the rule's taken back.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, parse_gedcom_date, resolve_tree, ulid
from catalog import Catalog, current_entry, page_entries, persona_key, source_tier, split_name, tier_sql
from catalog import (
    MARKS,
    ONCE,
    RECORD_FACTS,
    Finding,
    date_span,
    date_verdict,
    evidence_classes,
    fuller_date,
    holds,
    life_limits,
    parent_limit,
    place_verdict,
    record_kinds,
    record_original,
    record_standing,
    relation_classes,
    same_event,
    same_surname
)
from catalog import key as surname_key
from match import (
    MARRIED_IN_LAW,
    MATCHER,
    REL_OF,
    candidate,
    compare,
    fits_by_name_and_year,
    match,
    personas_of,
    said,
    split_persona_name
)
from plan import plan_person
from log_search import release_household, restate
from backfill_aliases import classify, clean, key

# the kind (data/evidence-classes.csv) that identifies a person only through who it names (docs/RESEARCH-WORKFLOW.md §0: "then the named survivors decide"): the rule's ground there is a stated relative, never a date or a place alone
NAMED_SURVIVORS = "obituary"
# a census before this year names the head and counts the rest: a hint (docs/RESEARCH-WORKFLOW.md §0)
HEAD_ONLY = ("census household", 1850)
# a register entry identifies a person only when it is dated and names their parents (docs/RESEARCH-WORKFLOW.md §0)
DATED_WITH_PARENTS = "church register (baptisms, marriages, burials)"
TRUSTED = ("T1", "T2", "T3")  # a record the rule may act on or count: not one anyone can edit (T4)
# a stated family relationship the record files under 'other': a half sibling, a grandchild, an in-law; never "other relative" or a blank
FAMILY_WORD = re.compile(r"\bhalf\b|grand(?:son|daughter|child)|in-law", re.I)
# the kind an in-law's own word resolves toward, once the relative it is in-law to is found (resolve_in_law)
IN_LAW = {
    "mother-in-law": "parent",
    "father-in-law": "parent",
    "son-in-law": "spouse",
    "daughter-in-law": "spouse",
    "brother-in-law": "sibling",
    "sister-in-law": "sibling"
}
# the rule as the decider, by what it did
RULE_ACTOR = {
    "persona_match": "rule:agrees-with-accepted",
    "new_person": "rule:creates-named-relative",
    "conflict": "rule:classes-favour-one-side"
}
# An artifact's source is read from its own identity first (an ark is FamilySearch, a memorial id is Find a Grave), then from the row it was archived under (catalog.tier_sql).

def marked(a="a"):
    """The SQL true of a statement, the assertion row under alias a, that carries one of the MARKS."""
    return f"(json_valid({a}.notes) AND coalesce(" + ", ".join(
        f"json_extract({a}.notes,'$.{m}')" for m in MARKS
    ) + ") IS NOT NULL)"

def unless(without):
    """The SQL leaving out of a reading of assertion a the statements reconsider does not count, and its arguments: every
    statement a decision in without wrote, and every statement whose own id is in without (a family link a withdrawal earlier
    in the same pass takes back: links_resting_on)."""
    if not without:
        return "", ()
    marks = ",".join("?" * len(without))
    return f"AND NOT (json_valid(a.notes) AND coalesce(json_extract(a.notes,'$.proposal'),'') IN ({marks})) AND a.id NOT IN ({marks})", (*without, *without)

def trusted_evidence(cx, tree_id, kind, ids, day=False, stating=None, without=()):
    """Whether an accepted assertion on any of these subjects rests on a trusted source (T1–T3) or on the owner's own word (a
    vouch, or the file's uncited claim the owner accepted, which is the same thing: no record, their knowledge); an accepted
    fact that rests only on a source anyone can edit does not count for the rule. stating "date" or "place": the assertion
    must itself state one (its persona fact's; the event's own for a vouch with no fact), so a record that states an event
    with no date or no place, asserted on the person's one event of the type, is never ground for a date or a place another
    source gave that event. day: the assertion must itself state a full date. A statement carrying one of the MARKS (a sibling
    placement, a value the page keeps beneath, a link the indexer computed) never counts, whatever its status. without:
    proposal ids whose assertions do not count (a rule decision under reconsideration and every rule decision after it), and
    statements that do not (unless)."""
    q = _q(cx)
    skip, skipped = unless(without)
    full = "AND length(coalesce(pf.date_start, CASE WHEN pf.id IS NULL THEN ev.date_start END)) = 10" if day else ""
    full += {
        "date": " AND coalesce(pf.date_start, pf.date_end, CASE WHEN pf.id IS NULL THEN coalesce(ev.date_start, ev.date_end) END) IS NOT NULL",
        "place": " AND coalesce(pf.place_string_id, CASE WHEN pf.id IS NULL THEN ev.place_id END) IS NOT NULL"
    }.get(stating, "")
    for sid in ids:
        if q.execute(f"""SELECT 1 FROM assertion a LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                         LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN event ev ON a.subject_kind='event' AND ev.id=a.subject_id
                         WHERE a.tree_id=? AND a.subject_kind=? AND a.subject_id=? AND a.status='accepted' AND NOT {marked()} {skip} {full}
                         AND (substr({tier_sql()},1,2) IN ('T1','T2','T3') OR (json_valid(a.notes) AND (json_extract(a.notes,'$.vouched')=1 OR json_extract(a.notes,'$.uncited')=1)))""", (tree_id, kind, sid, *skipped)).fetchone():
            return True
    return False
ANSWERABLE = ("missing_parents", "unverified_claim", "missing_fact")

def record_keys(cx, sha, copies=()):
    """What identifies a record for a citation to name it: the record ids it holds (catalog.holds, its own apid first), its
    memorial ids and its URL, and the same of every other copy of the record given (same_record)."""
    apids, memorials, urls = set(), set(), set()
    for s in dict.fromkeys([sha, *copies]):
        a = cx.execute("SELECT locator_kind, locator_value FROM artifact WHERE sha256=?", (s,)).fetchone()
        apids |= set(holds(cx, s)) | ({a[1]} if a and a[0] == "apid" and a[1] else set())
        memorials |= {
            v
            for v, in cx.execute(
                "SELECT value FROM artifact_locator WHERE artifact_sha256=? AND kind='memorial_id'", (s,)
            )
        }
        urls |= {a[1]} if a and a[0] == "url" and a[1] else set()
    return apids, memorials, urls

def record_self(cx, tree_id, sha, persona_id, pid):
    """What the record under decision is, for the rule's one-source test (ground, rests_elsewhere, not_the_files_word): copies, every file that is
    a copy of it (same_record, the file itself among them); original, the words of the original its classes name
    (catalog.record_original); year, its own year; and owners, the people it is the record of: the person under decision
    when the persona is the record's own (no relation of its own to another persona on it), else the people accepted on its
    own persons, on any copy."""
    from catalog import copy_entry, record_copies, record_owners
    shas = {c[0] for c in record_copies(cx, tree_id, *copy_entry(cx, persona_id))} | {sha}
    own = not cx.execute("SELECT 1 FROM persona_relation WHERE persona_id=?", (persona_id,)).fetchone()
    owners = {pid} if own and pid else set().union(*(record_owners(cx, tree_id, s) for s in shas))
    return {"copies": shas, "original": record_original(cx, sha), "year": record_kinds(cx, sha)[1], "owners": owners}

def cites_record(notes, keys):
    """Whether a statement's own citation (an imported claim's notes: its record id and URL) is the record these keys name."""
    apids, memorials, urls = keys
    url = notes.get("url") or ""
    m = re.search(r"/memorial/(\d+)(?:/|$)", url)
    return bool(
        (notes.get("apid") and notes["apid"] in apids) or (m and m.group(1) in memorials) or (url and url in urls)
    )

def rests_elsewhere(cx, eid, sha, axis, value, keys=None, copies=()):
    """Whether the event's value that a related persona's value agrees with stands on some statement other than the record
    under decision, so that the persona stands for the tree's relative on more than the relationship the record states
    (rule_points, grounded): a statement on the event that is not rejected, not the record's own (on any of its copies) and
    not a claim whose own citation is that record (docs/RESEARCH-WORKFLOW.md, the proof standard: such a claim never counts),
    giving a date or a place that agrees with value (gives)."""
    q = _q(cx)
    keys = keys or record_keys(cx, sha)
    ev = q.execute("SELECT date_text, date_start, date_end, date_qualifier FROM event WHERE id=?", (eid,)).fetchone()
    for r in q.execute(f"""SELECT {STATEMENT_COLUMNS} FROM assertion a {STATEMENT_JOINS}
                           WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected'""", (eid,)):
        if r["artifact_sha256"] == sha or r["artifact_sha256"] in copies:
            continue
        if cites_record(_notes(r), keys):
            continue
        if gives(ev, r, axis, value):
            return True
    return False

# a statement on an event as gives() reads it
STATEMENT_COLUMNS = "a.id, a.status, a.artifact_sha256, a.notes, a.persona_fact_id, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw"
STATEMENT_JOINS = (
    "LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id"
)

def _notes(r):
    """An assertion row's notes as a dict, {} when they are none or not an object."""
    try:
        notes = json.loads(r["notes"] or "{}")
    except ValueError:
        return {}
    return notes if isinstance(notes, dict) else {}

def gives(ev, r, axis, value, day=False):
    """Whether a statement on an event (r: STATEMENT_COLUMNS; ev: the event's own date fields) gives a date that agrees with
    value (to the day, with day) or a place that does. A statement with no record fact of its own (the owner's word) stands
    for the event's own date and gives no place."""
    if axis == "date":
        src = ev if r["persona_fact_id"] is None else r
        d = {
            "start": src["date_start"] or src["date_end"],
            "end": src["date_end"],
            "text": src["date_text"],
            "qualifier": src["date_qualifier"]
        }
        if not d["start"]:
            return False
        f = date_verdict(value, d)
        return f.verdict == "agrees" and (not day or (len(d["start"]) == 10 and not f.only))
    return bool(r["raw"]) and place_verdict(value, r["raw"]).verdict == "agrees"

def not_the_files_word(r, rec, keys, without=(), claim_only=False):
    """What keeps a statement on the tree (an assertion row: id, status, artifact_sha256, notes, imported) from standing
    claimed or accepted (docs/RESEARCH-WORKFLOW.md §5–7), or None when it stands: the file's claim, the import's own
    statement (on a file this tree imported, tree_import) not rejected, stands; with claim_only nothing else does, otherwise
    an accepted statement does too. Never one from the record under decision on any of its copies (rec: record_self,
    "self"), one carrying one of the MARKS (the mark's own name), one a decision in without wrote or one in without itself
    (reconsider, unless: "without"), or a claim whose own citation is that record (keys: record_keys, "cites"); anything
    else not accepted is "undecided", and an accepted statement read for the claim alone "accepted"."""
    notes = _notes(r)
    if r["artifact_sha256"] in rec["copies"]:
        return "self"
    mark = next((m for m in MARKS if notes.get(m) is not None), None)
    if mark:
        return mark
    if r["id"] in without or notes.get("proposal") in without:
        return "without"
    if r["imported"]:
        return "cites" if cites_record(notes, keys) else None
    if r["status"] != "accepted":
        return "undecided"
    return "accepted" if claim_only else None

def ground(cx, tree_id, kind, ids, sha, rec, axis=None, value=None, tree=None, without=()):
    """The tree's statements the standing rule may stand on for one point about the record under decision (sha; rec, what it
    is: record_self): accepted assertions on these subjects (the event compared, or the memberships joining two people)
    resting on a trusted source (T1–T3) or on the owner's own word (a vouch, or the file's uncited claim the owner accepted),
    never a statement carrying one of the MARKS (a sibling placement, a value the page keeps beneath, a link the indexer
    computed), the record itself on any of its copies (same_record: one record is one source wherever it is held), a claim whose
    own citation is it, or a statement from the same original about the same person's same event: a record whose classes
    name the same original (catalog.evidence_classes, record_original), the record of the same person (record_owners) and,
    where both give one, of the same year, which the code cannot show to be another copy of it and still counts once with it
    (two indexes of one certificate, two papers' obituaries of one death), never by the kind alone, which two people's
    records share. With axis, the statement must give a date or a place that agrees with value, a date whatever the event
    itself shows (docs/RESEARCH-WORKFLOW.md §5–7, what of an event's value is accepted), a place at the level of the tree's
    own (tree), so the place the event shows is given whole by the statement; never one a standing resolution set aside
    (catalog.set_aside); a vouch standing for the event's own date and place. without: proposal ids whose assertions do
    not count, and statements that do not (reconsider, unless). Returns (statements, shared): each statement {day: it gives
    value's very day, information: its information class in words, or the owner's own word}, and in words what was left out
    as one source with the record."""
    from catalog import record_owners, set_aside
    q = _q(cx)
    keys = record_keys(cx, sha, rec["copies"])
    cat = Catalog(cx, tree_id)
    out, shared = [], []
    seen, aside = {}, {}
    def same_original(s, c):
        """Whether a statement's record (s), whose classes are c, is the same person's record of the same event as the one under decision."""
        if not (rec["original"] and c and c.get("original") == rec["original"]):
            return False
        if s not in seen:
            seen[s] = (record_owners(cx, tree_id, s), record_kinds(cx, s)[1])
        owners, yr = seen[s]
        return bool(owners & rec["owners"]) and (not yr or not rec["year"] or yr == rec["year"])
    skip, skipped = unless(without)
    for sid in ids:
        for r in q.execute(f"""SELECT a.id, a.artifact_sha256, a.notes, a.persona_fact_id, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw,
                                      ev.date_text AS ev_text, ev.date_start AS ev_start, ev.date_end AS ev_end, ev.date_qualifier AS ev_qualifier, ev.id AS ev_id, ev.place_id AS ev_place,
                                      substr({tier_sql()},1,2) IN ('T1','T2','T3') AS trusted
                               FROM assertion a LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                               LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                               LEFT JOIN event ev ON a.subject_kind='event' AND ev.id=a.subject_id
                               WHERE a.tree_id=? AND a.subject_kind=? AND a.subject_id=? AND a.status='accepted' AND NOT {marked()} {skip} ORDER BY a.asserted_at, a.id""", (tree_id, kind, sid, *skipped)).fetchall():
            if r["artifact_sha256"] == sha:
                continue
            try:
                notes = json.loads(r["notes"] or "{}")
            except ValueError:
                notes = {}
            notes = notes if isinstance(notes, dict) else {}
            word = bool(notes.get("vouched") or notes.get("uncited"))
            if not (r["trusted"] or word) or cites_record(notes, keys):
                continue
            day = False
            if axis == "date":
                own = r["persona_fact_id"] is None
                d = {
                    "start": r["ev_start" if own else "date_start"] or r["ev_end" if own else "date_end"],
                    "end": r["ev_end" if own else "date_end"],
                    "text": r["ev_text" if own else "date_text"],
                    "qualifier": r["ev_qualifier" if own else "date_qualifier"]
                }
                if not d["start"] or date_verdict(value, d).verdict != "agrees":
                    continue
                day = len(d["start"]) == 10 and len((value or {}).get("start") or "") == 10
            elif axis == "place":
                raw = (
                    r["raw"]
                    if r["persona_fact_id"]
                    else (cat.place(r["ev_id"], r["ev_place"])["text"] if r["ev_place"] else None)
                )
                names = cat.dated_names(r["ev_place"])  # the tree's own place's former names, on either side
                if not raw or place_verdict(value, raw, dated_names=names).verdict != "agrees":
                    continue
                f = place_verdict(raw, tree, dated_names=names)
                # a statement coarser than the tree's own place is no ground for it
                if f.verdict != "agrees" or f.coarser is not None:
                    continue
            if axis and kind == "event":
                if sid not in aside:
                    aside[sid] = set_aside(cx, sid, axis)
                # the event's value was decided against it
                if r["id"] in aside[sid]:
                    continue
            if r["artifact_sha256"] in rec["copies"]:
                shared.append("another copy of this record")
                continue
            c = None if notes.get("vouched") else evidence_classes(cx, r["id"])
            if same_original(r["artifact_sha256"], c):
                shared.append(f"the {rec['original']}, the original this record was copied from")
                continue
            out.append(
                {
                    "id": r["id"],
                    "day": day,
                    "information": "your own word" if word else (c or {}).get("information") or "indeterminable"
                }
            )
    return out, list(dict.fromkeys(shared))

def editable(cx, sha):
    """Whether an artifact is a page anyone can edit (T4 by its own identity or its row): a decision on it is an identity, the
    persona link and the family links it states; its facts are written Undecided, never accepted by the decision."""
    return str(source_tier(cx, sha) or "")[:2] == "T4"

# in an UPDATE on assertion: the statement's record is one nobody can edit at will
TRUSTED_ARTIFACT = f"substr((SELECT {tier_sql('ar', 's')} FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=assertion.artifact_sha256),1,2) IN ('T1','T2','T3')"
# in an UPDATE on assertion: a statement a decision accepts with its record, and so the one a withdrawal takes back; one carrying a mark (MARKS), and a fact or family link a page anyone can edit states, are written undecided and stay so
ACCEPTED_WITH_RECORD = f"NOT {marked('assertion')} AND " + TRUSTED_ARTIFACT

class _q:
    """execute() on a fresh cursor each time, rows readable by column name whatever the caller's connection does, so a query
    inside a loop over another query's rows does not consume that loop."""
    def __init__(self, cx):
        self.cx = cx
    def execute(self, sql, args=()):
        c = self.cx.cursor()
        c.row_factory = sqlite3.Row
        return c.execute(sql, args)

def same_personas(cx, persona_id):
    """Every persona of the same entry of the record as this one (catalog.persona_key: its record id, else its role, row and
    name), across every extraction of the record, itself included: a decision is about one entry of the record, whose bytes do
    not change between readings, so it applies to each reading's persona of that entry, and a withdrawal or a rejection resets
    them all. Another row of the same name is another entry and never takes it. The earlier readings' links are history;
    readers of accepted links join on current extractions only."""
    sha = cx.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()[0]
    entries = page_entries(cx, sha)
    k = next(key for pid, _, _, _, key in entries if pid == persona_id)
    return [pid for pid, _, _, _, key in entries if key == k]

# ---------------------------------------------------------------- one record, wherever it is held
def _number(cx, persona_id, region_key, reading):
    """(the number's digits, its year) a numbered entry gives its record (catalog.NUMBERS): the year the index files it under
    ("14205 /1946"), else the year of the entry's own dated event, else the reading's record year."""
    digits, _, filed = region_key[1].partition("/")
    yr = filed.strip() or next((d[:4] for d, in cx.execute("""SELECT date_start FROM persona_fact WHERE persona_id=? AND fact_type IN ('Death','Birth','Marriage')
                                                               AND length(date_start)>=4 AND coalesce(date_qualifier,'') NOT IN ('calculated','estimated') ORDER BY rowid""", (persona_id,))), None) or record_kinds(cx, cx.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()[0], reading)[1]
    return re.sub(r"\D", "", digits).lstrip("0"), yr

def join_copies(cx, sha, by, ts=None):
    """Code's joins of one archived file to the other copies of its record (docs/DATA-ARCHITECTURE.md §7 decision 15,
    same_record), each written once and shared by every tree: archived under one record id (an Ancestry apid or a
    FamilySearch ark, the artifact's own or one artifact_locator gives it); one FamilySearch entry id on both readings (each
    person of a FamilySearch record has one, so the bride's page and the groom's of one marriage are one record); one
    certificate number of one year (a state index's line and the certificate's image whose reading gives the number), the
    two numbered entries agreeing by name. A join by record id stands only where an entry of each current reading agrees with
    one of the other's by name (catalog.entry_on), and code never joins a page anyone can edit to a record nobody can, nor a
    row of a search's results, whose own record is the document (docs/RESEARCH-WORKFLOW.md §0). Returns the rows written:
    (other sha256, basis, shared)."""
    from catalog import NUMBERS, copy_entry, current_reading, entry_on, names_agree
    q = _q(cx)
    ts = ts or now()
    out = []
    mine = current_reading(cx, sha)
    if not mine:
        return out
    tier = editable(cx, sha)
    def known(a, b):
        return q.execute(
            """SELECT 1 FROM same_record WHERE tree_id IS NULL AND ((a_sha256=? AND a_entry=? AND b_sha256=? AND b_entry=?) OR (a_sha256=? AND a_entry=? AND b_sha256=? AND b_entry=?))""",
            (*a, *b, *b, *a)
        ).fetchone()
    def write(a, b, basis, shared):
        if a == b or known(a, b):
            return
        q.execute(
            """INSERT INTO same_record (id,tree_id,a_sha256,a_entry,b_sha256,b_entry,same,basis,shared,decided_by,decided_at) VALUES (?,NULL,?,?,?,?,1,?,?,?,?)""",
            (ulid(), *a, *b, basis, shared, by, ts)
        )
        q.execute(
            "INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
            (
                ulid(),
                ts,
                by,
                "insert",
                "same_record",
                a[0],
                dumps({"copy": a, "of": b, "basis": basis, "shared": shared})
            )
        )
        out.append((b[0], basis, shared))
    ROWS = "coalesce(role_in_record,'')<>'result'"  # a search's results row points at a record and is none
    people = q.execute(
        f"SELECT id, name_text, role_in_record, sequence, region_json FROM persona WHERE extraction_id=? AND {ROWS} ORDER BY sequence, id",
        (mine,)
    ).fetchall()
    keyed = [(p, persona_key(p["role_in_record"], p["sequence"], p["name_text"], p["region_json"])) for p in people]
    def other_reading(o):
        r = current_reading(cx, o)
        return r if r and o != sha and editable(cx, o) == tier else None
    locs = {tuple(r) for r in q.execute("""SELECT locator_kind, locator_value FROM artifact WHERE sha256=? AND locator_kind IN ('apid','ark') AND locator_value IS NOT NULL
                                           UNION SELECT kind, value FROM artifact_locator WHERE artifact_sha256=? AND kind IN ('apid','ark')""", (sha, sha))}
    for kind, value in sorted(locs):
        for o, in q.execute("""SELECT sha256 FROM artifact WHERE locator_kind=? AND locator_value=? UNION SELECT artifact_sha256 FROM artifact_locator WHERE kind=? AND value=?
                               ORDER BY 1""", (kind, value, kind, value)).fetchall():
            theirs = other_reading(o)
            if (
                theirs
                and any(
                    t and q.execute(f"SELECT 1 FROM persona WHERE id=? AND {ROWS}", (t,)).fetchone()
                    for t in (entry_on(cx, p["id"], theirs) for p in people)
                )
            ):
                write((sha, ""), (o, ""), "citation", f"{kind} {value}")
    for p, k in keyed:
        if k[0] == "ark":
            for o, in q.execute(
                "SELECT DISTINCT artifact_sha256 FROM persona WHERE region_json LIKE ? AND artifact_sha256<>? ORDER BY 1",
                (f"%{k[1].rsplit(':', 1)[-1]}%", sha)
            ).fetchall():
                theirs = other_reading(o)
                hit = (
                    theirs
                    and next(
                        (
                            r
                            for r in q.execute(
                                f"SELECT name_text, role_in_record, sequence, region_json FROM persona WHERE extraction_id=? AND {ROWS}",
                                (theirs,)
                            )
                            if persona_key(r["role_in_record"], r["sequence"], r["name_text"], r["region_json"]) == k
                        ),
                        None
                    )
                )
                if hit and names_agree(p["name_text"], hit["name_text"]):
                    write((sha, ""), (o, ""), "entry", f"entry {k[1]}")
        elif k[0] in NUMBERS:
            digits, yr = _number(cx, p["id"], k, mine)
            if not (digits and yr):
                continue
            for o, in q.execute(
                "SELECT DISTINCT artifact_sha256 FROM persona WHERE region_json LIKE ? AND artifact_sha256<>? ORDER BY 1",
                (f"%{digits}%", sha)
            ).fetchall():
                theirs = other_reading(o)
                if not theirs:
                    continue
                for r in q.execute(
                    f"SELECT id, name_text, role_in_record, sequence, region_json FROM persona WHERE extraction_id=? AND {ROWS}",
                    (theirs,)
                ).fetchall():
                    rk = persona_key(r["role_in_record"], r["sequence"], r["name_text"], r["region_json"])
                    if (
                        rk[0] in NUMBERS
                        and _number(cx, r["id"], rk, theirs) == (digits, yr)
                        and names_agree(p["name_text"], r["name_text"])
                    ):
                        write(copy_entry(cx, p["id"]), copy_entry(cx, r["id"]), "number", f"number {digits} of {yr}")
    return out

def carry(cx, by, sha, trees=None, dry_run=False, settle=True):
    """A decision on one copy's entry of a record carried to every other copy's persona of that entry (docs/DATA-ARCHITECTURE.md
    §7 decision 15): the record's copies (catalog.record_copies, every copy of a record the file or one of its rows is a copy
    of), and on each the persona of the same entry (catalog.entry_on: its record id, else its name, a record's own person
    being a page's subject and an image's deceased alike), every reading's persona of it taking the decision's link, under
    the decision's own proposal, so a rejection or a withdrawal reaches it as it reaches the copy decided. An accepted one
    asserts the copy's facts and family links onto the person as the decision did (assert_facts, write_name_alias,
    link_family, the decision's own actor and proposal), so the reading of an image with no card of its own is decided with
    the page. A link on a copy that carries the same decision follows its status; one a person or the rule decided otherwise
    on that copy is never undone, and is said so, nor is a statement of the copy whose status a person decided on its own
    (person_decided). settle: the people whose evidence changed have their plans regenerated,
    their conflicts gone over by the rule and their cards matched again, as a decision does (decide does that itself, so it
    carries with settle off). Returns one row per link carried: tree, proposal, person, persona, copy, status, and kept for a
    copy decided otherwise."""
    from catalog import copy_entry, current_reading, entry_on, record_copies
    q = _q(cx)
    ts = now()
    rows = []
    trees = trees or [t for t, in q.execute("SELECT id FROM tree ORDER BY id")]
    nodes = [(sha, "")] + [tuple(n) for n in q.execute("""SELECT a_sha256, a_entry FROM same_record WHERE a_sha256=? AND a_entry<>'' UNION
                                                          SELECT b_sha256, b_entry FROM same_record WHERE b_sha256=? AND b_entry<>''""", (sha, sha))]
    def on_copy(node):
        """The personas of a copy's current reading: the whole reading, or the one row a listing's copy is."""
        r = current_reading(cx, node[0])
        if not r:
            return r, []
        ps = [p for p, in q.execute("SELECT id FROM persona WHERE extraction_id=? ORDER BY sequence, id", (r,))]
        return r, ps if not node[1] else [p for p in ps if copy_entry(cx, p) == tuple(node)]
    for tree_id in trees:
        touched = {}
        done = set()
        for node in nodes:
            copies = record_copies(cx, tree_id, *node)
            if len(copies) < 2 or tuple(copies[0]) in done:
                continue
            done.update(tuple(c) for c in copies)
            readings = {c: on_copy(c) for c in copies}
            for c in copies:
                for p in readings[c][1]:
                    for src in q.execute("""SELECT pp.person_id, pp.status, pp.proposal_id, pp.decided_by, pp.decided_at FROM person_persona pp JOIN person o ON o.id=pp.person_id
                                            WHERE pp.persona_id=? AND o.tree_id=? AND pp.status IN ('accepted','rejected') AND pp.proposal_id IS NOT NULL""", (p, tree_id)).fetchall():
                        for d in copies:
                            if d == c or not readings[d][0]:
                                continue
                            target = entry_on(cx, p, readings[d][0])
                            if not target or target not in readings[d][1]:
                                continue
                            had = q.execute(
                                "SELECT status, proposal_id FROM person_persona WHERE person_id=? AND persona_id=?",
                                (src["person_id"], target)
                            ).fetchone()
                            if had and had["status"] != "undecided" and had["proposal_id"] != src["proposal_id"]:
                                if had["status"] != src["status"]:
                                    rows.append(
                                        {
                                            "tree": tree_id,
                                            "proposal": src["proposal_id"],
                                            "person": src["person_id"],
                                            "persona": target,
                                            "copy": d[0],
                                            "status": src["status"],
                                            "kept": had["status"]
                                        }
                                    )
                                continue
                            if had and had["status"] == src["status"] and had["proposal_id"] == src["proposal_id"]:
                                continue
                            rows.append(
                                {
                                    "tree": tree_id,
                                    "proposal": src["proposal_id"],
                                    "person": src["person_id"],
                                    "persona": target,
                                    "copy": d[0],
                                    "status": src["status"],
                                    "kept": None
                                }
                            )
                            if dry_run:
                                continue
                            for pe in same_personas(cx, target):
                                old = q.execute(
                                    "SELECT status, proposal_id FROM person_persona WHERE person_id=? AND persona_id=?",
                                    (src["person_id"], pe)
                                ).fetchone()
                                if old and old["status"] != "undecided" and old["proposal_id"] != src["proposal_id"]:
                                    continue
                                q.execute(
                                    "INSERT OR REPLACE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)",
                                    (
                                        src["person_id"],
                                        pe,
                                        src["status"],
                                        src["proposal_id"],
                                        src["decided_by"],
                                        src["decided_at"]
                                    )
                                )
                            n = 0
                            if src["status"] == "accepted":
                                n = assert_facts(
                                    cx, tree_id, src["person_id"], target, src["proposal_id"], src["decided_by"], ts
                                )[0]
                                write_name_alias(
                                    cx,
                                    tree_id,
                                    src["person_id"],
                                    target,
                                    d[0],
                                    src["proposal_id"],
                                    src["decided_by"],
                                    ts
                                )
                                link_family(
                                    cx,
                                    tree_id,
                                    src["person_id"],
                                    target,
                                    d[0],
                                    src["proposal_id"],
                                    src["decided_by"],
                                    ts
                                )
                            q.execute(
                                "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                                (
                                    ulid(),
                                    tree_id,
                                    ts,
                                    by,
                                    "update",
                                    "proposal",
                                    src["proposal_id"],
                                    dumps(
                                        {
                                            "carried": {"from": p, "to": target, "copy": d[0], "of": c[0]},
                                            "status": src["status"],
                                            "person": src["person_id"],
                                            "assertions": n
                                        }
                                    )
                                )
                            )
                            touched.setdefault(src["person_id"], src["proposal_id"])
        if settle and touched and not dry_run:
            for pid, prop in touched.items():
                answer_questions(cx, tree_id, pid, prop, by)
            rule_conflicts(cx, tree_id, by, people=list(touched))
            rematch_people(cx, tree_id, by, list(touched))
    return rows

def assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts):
    """Assertions from a persona's facts to the person, the document having been accepted as theirs: Accepted from a record
    nobody can edit at will, Undecided from a page anyone can edit (what the page says, never accepted by the decision and never
    ground for the rule, so the person's facts come from primary documents only). Name and Sex assert the person row. One
    statement, one event (docs/RESEARCH-WORKFLOW.md §5–7): an event fact asserts the one event of its type that
    Catalog.event_for chooses among the person's: the one event of a type a life holds once whatever its date or place, the
    one event of another type for an undated fact, else the event whose own date agrees most closely with the fact's among
    those whose places agree with it; created from the fact's date when the person has none that fits, but never beside
    another of a type a life holds once; and left unasserted when the choice is the owner's (two or more equally close, an
    undated fact among several, a fact of a type a life holds once fitting none of several), which Catalog.unplaced raises
    as a conflict question naming the record and the events, for tools/conclude.py place to answer. A residence with no date
    is its own stay, never another record's. An attribute fact (Occupation, Inscription, Religion, ...) asserts the person's
    attribute of that type with the same value, chosen the same way among several of that value, created when there is
    none. A fact the record already states on one of the person's events (Catalog.stated_on: an earlier reading's statement,
    or one the owner placed) stays there, and a fact the same record already asserts on the same subject with the same type,
    date, value and place is not asserted again, so a re-extraction adds only what is new; one the rule withdrew turns
    Accepted again on a trusted record and stays as it is on an editable page, and one closed with its card as superseded
    (rematch) takes this decision's status; one whose status a person decided on its own (person_decided) stays as the person
    left it, whatever reads the record again or carries a decision to it. A value
    the page keeps beneath the one it shows (FamilySearch's edit history, a fact whose region marks it alternate) is written
    Undecided and marked so: what the page also says, kept and cited, never accepted with the record and never a conflict
    with the value the record shows. Returns how many were written."""
    q = _q(cx)
    cat = Catalog(cx, tree_id)
    n = 0
    sha = q.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()["artifact_sha256"]
    cite, status = _citation(cx, sha)
    def assert_(kind, sid, f):
        nonlocal n
        alt = "alternate" in json.loads(f["region_json"] or "{}")
        n += _state(
            q,
            tree_id,
            kind,
            sid,
            f,
            sha,
            cite,
            "undecided" if alt else status,
            by,
            ts,
            prop_id,
            {"alternate": True} if alt else None
        )
    for f in q.execute("""SELECT pf.id, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.calendar, pf.place_string_id, pf.region_json, et.kind
                           FROM persona_fact pf JOIN event_type et ON et.name=pf.fact_type WHERE pf.persona_id=?""", (persona_id,)).fetchall():
        if f["fact_type"] in ("Name", "Sex"):
            assert_("person", person_id, f)
            continue
        if f["fact_type"] in RECORD_FACTS or f["kind"] not in ("event", "attribute"):
            continue
        eid = cat.stated_on(sha, f, person=person_id)
        if eid is None and not (f["fact_type"] == "Residence" and not (f["date_start"] or f["date_end"])):
            events = cat.owner_events(f["fact_type"], person=person_id)
            if f["kind"] == "attribute":
                events = [e for e in events if (e["value"] or "") == (f["value_text"] or "")]
            eid, choice = cat.event_for(f, events, once=f["fact_type"] in ONCE or f["kind"] == "attribute")
            # the owner's choice: Catalog.unplaced raises it
            if choice:
                continue
        if eid is None:
            eid = ulid()
            q.execute(
                """INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,description,created_at,updated_at)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    eid,
                    tree_id,
                    f["fact_type"],
                    f["date_text"],
                    f["date_start"],
                    f["date_end"],
                    f["date_qualifier"],
                    f["calendar"],
                    f["value_text"] if f["kind"] == "attribute" else None,
                    ts,
                    ts
                )
            )
            q.execute(
                "INSERT INTO event_participant (id,event_id,person_id,role) VALUES (?,?,?,'primary')",
                (ulid(), eid, person_id)
            )
        assert_("event", eid, f)
    return n, sha

def _citation(cx, sha):
    """(citation words, status) a record's statements are written with: the collection's name, and Accepted from a record
    nobody can edit at will, Undecided from a page anyone can edit."""
    a = cx.execute(
        "SELECT c.name, ar.original_filename FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id WHERE ar.sha256=?",
        (sha,)
    ).fetchone()
    return (a[0] or a[1] or sha[:12]), ("undecided" if editable(cx, sha) else "accepted")

def _state(q, tree_id, kind, sid, f, sha, cite, status, by, ts, prop_id, extra=None):
    """One statement of a record's fact on a subject, written once: a statement the same record already makes on the same
    subject with the same type, date, value and place stands again when the rule had withdrawn it or its card closed
    (undecided, on a trusted record), and otherwise stays as it is; one whose status a person decided on its own
    (person_decided) stays as the person left it, undecided included. Returns 1 when written, else 0."""
    old = q.execute("""SELECT a.id, a.status, a.notes, a.person_decided FROM assertion a JOIN persona_fact q ON q.id=a.persona_fact_id WHERE a.subject_kind=? AND a.subject_id=? AND a.artifact_sha256=?
                       AND q.fact_type=? AND coalesce(q.date_text,'')=coalesce(?,'') AND coalesce(q.value_text,'')=coalesce(?,'') AND coalesce(q.place_string_id,'')=coalesce(?,'')""", (kind, sid, sha, f["fact_type"], f["date_text"], f["value_text"], f["place_string_id"])).fetchone()
    if old:
        if old["status"] == "undecided" and status == "accepted" and not old["person_decided"]:
            q.execute(
                "UPDATE assertion SET status=?, asserted_by=?, asserted_at=?, notes=? WHERE id=?",
                (status, by, ts, dumps({"proposal": prop_id, **(extra or {})}), old["id"])
            )
            return 1
        return 0
    q.execute(
        """INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (ulid(), tree_id, kind, sid, f["id"], sha, cite, status, by, ts, dumps({"proposal": prop_id, **(extra or {})}))
    )
    return 1

def assert_family_events(cx, tree_id, fid, persona_ids, sha, prop_id, by, ts, computed=False):
    """A record's family facts (a Marriage, a Divorce: the event types of kind family_event) asserted on the family the record's
    spouse relation joins, once both partners are accepted on the record (link_family calls this then, so a fact on the
    first partner's persona waits for the second's acceptance): each persona's fact on the one event of the family that
    Catalog.event_for chooses, as assert_facts chooses a person's (the event whose date agrees most closely, among those
    whose places agree; the one event for an undated fact), the fact the record already states on one of the family's events
    staying there, created from the fact's date when the family has none that fits, and left unasserted when the choice is
    the owner's (Catalog.unplaced). Accepted from a record nobody can edit at will, Undecided from a page anyone can edit or
    when the couple is one the record's indexer computed (marked so, as the link is); written once, as assert_facts writes.
    Returns how many were written."""
    q = _q(cx)
    n = 0
    cat = Catalog(cx, tree_id)
    cite, status = _citation(cx, sha)
    if computed:
        status = "undecided"
    for pe in persona_ids:
        for f in q.execute("""SELECT pf.id, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.calendar, pf.place_string_id
                              FROM persona_fact pf JOIN event_type et ON et.name=pf.fact_type WHERE pf.persona_id=? AND et.kind='family_event'""", (pe,)).fetchall():
            eid = cat.stated_on(sha, f, family=fid)
            if eid is None:
                eid, choice = cat.event_for(f, cat.owner_events(f["fact_type"], family=fid))
                # the owner's choice: Catalog.unplaced raises it
                if choice:
                    continue
            if eid is None:
                eid = ulid()
                q.execute(
                    """INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at)
                              VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        eid,
                        tree_id,
                        f["fact_type"],
                        f["date_text"],
                        f["date_start"],
                        f["date_end"],
                        f["date_qualifier"],
                        f["calendar"],
                        ts,
                        ts
                    )
                )
                q.execute(
                    "INSERT INTO event_participant (id,event_id,family_id,role) VALUES (?,?,?,'family')",
                    (ulid(), eid, fid)
                )
            n += _state(
                q,
                tree_id,
                "event",
                eid,
                f,
                sha,
                cite,
                status,
                by,
                ts,
                prop_id,
                {"computed": True} if computed else None
            )
    return n

def place(cx, tree_id, pf_id, event_id, by, note):
    """The owner's word on which of a person's events, or of a family's they are a partner in, a record's fact belongs to: a
    fact accepted onto the person and left unasserted because the choice was theirs (Catalog.unplaced: an undated fact among
    several events of its type, a dated one fitting two or more equally, one of a type a life holds once fitting none of
    several), written onto the event the owner means, the way assert_facts writes any other statement (accepted from a
    record nobody can edit at will, undecided from a page anyone can); or a fact already asserted on another of those events
    of its type (its own statement, or the record's same statement through an earlier reading, Catalog.stated_on), moved to
    this one, its status kept. An event a move leaves with no statement but rejected ones (an event an older reading made of a
    misread value) leaves the person's or the family's events: its participant row goes, the event and its statements stay
    for the audit trail. Refused when the persona fact does not exist or its persona is not accepted to a person, the event
    is not this tree's, is of another type than the fact or belongs to another person or family, or the fact's statement is
    already on it. One audit row per change; the plans of the person, and of the other partner on a family's event, are
    regenerated. Returns what was written, or an error."""
    q = _q(cx)
    ts = now()
    cat = Catalog(cx, tree_id)
    pf = q.execute(
        "SELECT pf.*, pe.artifact_sha256 FROM persona_fact pf JOIN persona pe ON pe.id=pf.persona_id WHERE pf.id=?",
        (pf_id,)
    ).fetchone()
    if not pf:
        return {"error": "no such persona fact"}
    pp = q.execute(
        "SELECT pp.person_id FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?",
        (pf["persona_id"], tree_id)
    ).fetchone()
    if not pp:
        return {"error": "this persona is not accepted to a person"}
    person_id = pp["person_id"]
    ev = q.execute("SELECT id, event_type FROM event WHERE id=? AND tree_id=?", (event_id, tree_id)).fetchone()
    if not ev:
        return {"error": "no such event in this tree"}
    if ev["event_type"] != pf["fact_type"]:
        return {"error": f"the event is {ev['event_type']}, the fact is {pf['fact_type']}"}
    mine = """SELECT ep.person_id, ep.family_id FROM event_participant ep JOIN event e ON e.id=ep.event_id WHERE e.id=? AND e.event_type=?
              AND (ep.person_id=? OR ep.family_id IN (SELECT family_id FROM family_member WHERE person_id=? AND role='partner'))"""
    owner = q.execute(mine, (event_id, pf["fact_type"], person_id, person_id)).fetchone()
    if not owner:
        return {"error": "the event belongs to another person"}
    had = q.execute(
        "SELECT id, subject_id, status FROM assertion WHERE persona_fact_id=? AND subject_kind='event' ORDER BY asserted_at, id",
        (pf_id,)
    ).fetchone()
    if not had:  # the record's same statement, written through an earlier reading of it
        on = (
            cat.stated_on(pf["artifact_sha256"], pf, person=person_id)
            if owner["person_id"]
            else cat.stated_on(pf["artifact_sha256"], pf, family=owner["family_id"])
        )
        had = (
            q.execute(
                """SELECT a.id, a.subject_id, a.status FROM assertion a JOIN persona_fact x ON x.id=a.persona_fact_id WHERE a.subject_kind='event' AND a.subject_id=? AND a.artifact_sha256=?
                           AND x.fact_type=? AND coalesce(x.date_text,'')=coalesce(?,'') AND coalesce(x.value_text,'')=coalesce(?,'') AND coalesce(x.place_string_id,'')=coalesce(?,'')
                           ORDER BY a.asserted_at, a.id""",
                (on, pf["artifact_sha256"], pf["fact_type"], pf["date_text"], pf["value_text"], pf["place_string_id"])
            ).fetchone()
            if on
            else None
        )
    if had and had["subject_id"] == event_id:
        return {"error": "the fact's statement is already on this event"}
    people = [person_id] + (
        [
            r["person_id"]
            for r in q.execute(
                "SELECT person_id FROM family_member WHERE family_id=? AND role='partner' AND person_id<>?",
                (owner["family_id"], person_id)
            )
        ]
        if owner["family_id"]
        else []
    )
    if had:  # on another of the person's events of its type, or the family's: moved, its status kept
        was = q.execute(mine, (had["subject_id"], pf["fact_type"], person_id, person_id)).fetchone()
        if not was:
            return {"error": "the fact's statement is on an event that is not this person's of its type"}
        q.execute(
            "UPDATE assertion SET subject_id=?, notes=json_set(coalesce(notes,'{}'),'$.placed_by_owner',?) WHERE id=?",
            (event_id, note, had["id"])
        )
        q.execute(
            "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                ulid(),
                tree_id,
                ts,
                by,
                "update",
                "assertion",
                had["id"],
                dumps(
                    {
                        "persona_fact": pf_id,
                        "from_event": had["subject_id"],
                        "event": event_id,
                        "person": person_id,
                        "note": note
                    }
                )
            )
        )
        retired = None
        if not q.execute(
            "SELECT 1 FROM assertion WHERE subject_kind='event' AND subject_id=? AND status<>'rejected'",
            (had["subject_id"],)
        ).fetchone():
            q.execute(
                "DELETE FROM event_participant WHERE event_id=? AND (person_id=? OR family_id=?)",
                (had["subject_id"], was["person_id"], was["family_id"])
            )
            retired = had["subject_id"]
            q.execute(
                "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                (
                    ulid(),
                    tree_id,
                    ts,
                    by,
                    "update",
                    "event",
                    retired,
                    dumps(
                        {
                            "left_person": was["person_id"],
                            "left_family": was["family_id"],
                            "why": "no statement but rejected ones supports it once the record's own was placed elsewhere",
                            "note": note
                        }
                    )
                )
            )
        for p_ in people:
            plan_person(cx, tree_id, p_, by)
        return {
            "ok": True,
            "assertion": had["id"],
            "status": had["status"],
            "person": person_id,
            "event": event_id,
            "moved_from": had["subject_id"],
            "retired": retired
        }
    cite, status = _citation(cx, pf["artifact_sha256"])
    aid = ulid()
    q.execute(
        """INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                  VALUES (?,?,'event',?,?,?,?,?,?,?,?)""",
        (aid, tree_id, event_id, pf_id, pf["artifact_sha256"], cite, status, by, ts, dumps({"note": note}))
    )
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "insert",
            "assertion",
            aid,
            dumps({"persona_fact": pf_id, "event": event_id, "person": person_id, "status": status, "note": note})
        )
    )
    for p_ in people:
        plan_person(cx, tree_id, p_, by)
    return {"ok": True, "assertion": aid, "status": status, "person": person_id, "event": event_id}

def shown_married(cx, tree_id, person_id, sha, written, canon_surname):
    """Whether the record shows this person married under `written`'s own surname: a wife under her husband's surname (the
    tree's own recorded spouse, claimed or accepted), a daughter or sister under her husband's, named beside a son-in-law
    or brother-in-law of that surname on the same record, or written "Mrs."."""
    if re.match(r"^\s*mrs\.?\b", written or "", re.I):
        return True
    rest = split_persona_name(written)[1]
    if not rest:
        return False
    ws = rest[-1]
    if ws == surname_key(canon_surname or ""):
        return False
    q = _q(cx)
    spouses = [
        surname_key(n.split()[-1]) for _, n in Catalog(cx, tree_id).family(person_id)["spouses"] if n and n.split()
    ]
    if any(same_surname(ws, s) for s in spouses):
        return True
    eid = q.execute("SELECT extraction_id FROM persona WHERE artifact_sha256=? LIMIT 1", (sha,)).fetchone()
    if not eid:
        return False
    in_laws = [
        name
        for role, name in q.execute(
            "SELECT role_in_record, name_text FROM persona WHERE extraction_id=?", (eid["extraction_id"],)
        )
        if MARRIED_IN_LAW.search(role or "")
    ]
    return any(same_surname(ws, s) for name in in_laws for s in [split_persona_name(name)[1]] if s for s in [s[-1]])

def write_name_alias(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts):
    """The persona's own Name fact, when its words differ from the person's canonical name and are not already one of the
    person's own name rows (a birth or married name create_person already split out), becomes an alias at once: accepted,
    of the kind the difference is (backfill_aliases.classify, married_name when the record shows the person married under
    it: shown_married), the record's words as written. Returns the alias id, or None when there is nothing to write."""
    q = _q(cx)
    # the name the page shows, never one it keeps beneath
    fact = q.execute("""SELECT id, value_text FROM persona_fact WHERE persona_id=? AND fact_type='Name' AND value_text IS NOT NULL
                        AND (region_json IS NULL OR json_extract(region_json,'$.alternate') IS NULL) LIMIT 1""", (persona_id,)).fetchone()
    if not fact or not fact["value_text"]:
        return None
    name = q.execute(
        "SELECT given, surname, suffix FROM person_name WHERE person_id=? AND is_primary", (person_id,)
    ).fetchone()
    if not name:
        return None
    canon = " ".join(x for x in (name["given"], name["surname"], name["suffix"]) if x)
    value = clean(fact["value_text"])
    if not value or key(value) == key(canon):
        return None
    if any(key(value) == key(" ".join(x for x in r if x))
           for r in q.execute("SELECT given, surname, suffix FROM person_name WHERE person_id=?", (person_id,))):
        return None
    if q.execute(
        "SELECT 1 FROM alias WHERE entity_kind='person' AND entity_id=? AND value=?", (person_id, value)
    ).fetchone():
        return None
    kind, note = classify(
        fact["value_text"],
        name["given"],
        name["surname"],
        name["suffix"],
        married=shown_married(cx, tree_id, person_id, sha, fact["value_text"], name["surname"])
    )
    aid = ulid()
    cx.execute(
        """INSERT INTO alias (id,tree_id,entity_kind,entity_id,value,kind,status,source_persona_fact_id,source_artifact_sha256,added_by,added_at,notes)
                  VALUES (?,?,?,?,?,?,'accepted',?,?,?,?,?)""",
        (
            aid,
            tree_id,
            "person",
            person_id,
            value,
            kind,
            fact["id"],
            sha,
            by,
            ts,
            dumps({"proposal": prop_id, "note": note})
        )
    )
    return aid

def create_person(cx, tree_id, persona_id, ts):
    """A person in this tree from a persona: the name as written split into given names and a surname; a maiden name the
    record marks becomes the birth surname and the written surname a married name. Returns the person id."""
    q = _q(cx)
    pe = q.execute("SELECT name_text, sex, region_json FROM persona WHERE id=?", (persona_id,)).fetchone()
    region = json.loads(pe["region_json"] or "{}")
    # the right way round whichever way the record wrote it; a suffix is not a surname
    given, surname, suffix = split_name(pe["name_text"])
    text = " ".join(x for x in (given, surname, suffix) if x)
    pid = ulid()
    q.execute(
        "INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        (pid, tree_id, pe["sex"], text, ts, ts)
    )
    if region.get("maiden") and surname and region["maiden"] != surname:
        g = given.replace(region["maiden"], "").strip()
        q.execute(
            "INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)",
            (ulid(), pid, g, region["maiden"], f"{region['maiden']}, {g}".lower())
        )
        q.execute(
            "INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'married',?,?,0,?)",
            (ulid(), pid, g, surname, f"{surname}, {g}".lower())
        )
    else:
        q.execute(
            "INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)",
            (ulid(), pid, given, surname, f"{surname or ''}, {given}".lower())
        )
    return pid

def new_family(cx, tree_id, partner, ts):
    q = _q(cx)
    fid = ulid()
    q.execute("INSERT INTO family (id,tree_id,created_at,updated_at) VALUES (?,?,?,?)", (fid, tree_id, ts, ts))
    q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid, partner))
    return fid

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
        return {(surname_key(g), surname_key(s)) for g, s, *_ in cat.person(pid)["names"]} | {
            (surname_key(a.split()[0]), surname_key(a.split()[-1]))
            for a in cat.person(pid)["aliases"]
            if len(a.split()) > 1
        }
    def choose(pool):
        pool = list(dict.fromkeys(pool))
        if len(pool) == 1:
            return pool[0]
        matching = [c for c in pool if any(surname_key(x_surname) == s and s for _, s in name_keys_(c))]
        return matching[0] if len(matching) == 1 else None
    of = lambda pid, group: choose(oid for oid, _ in cat.family(pid)[group])
    if resolved_kind == "parent":
        spouse = of(y_pid, "spouses")
        return ("parent", spouse) if spouse else None
    if resolved_kind == "spouse":
        child = of(y_pid, "children")
        return ("spouse", child) if child else None
    if resolved_kind == "sibling":
        spouse = of(y_pid, "spouses")
        sib = of(spouse, "siblings") if spouse else None
        if sib:
            return ("sibling", sib)
        sib = of(y_pid, "siblings")
        partner = of(sib, "spouses") if sib else None
        if partner:
            return ("spouse", partner)
    return None

def link_family(cx, tree_id, pid, persona_id, sha, prop_id, by, ts, held_back=None):
    """Family links from the record's own relations, for a matched person as for a new one: where the record says this persona
    is the child, parent or spouse of a persona already accepted as a person in this tree, the membership exists (created when
    the tree lacks it, in a family of the right shape) and carries an Accepted assertion on the artifact, or an Undecided one
    when the artifact is a page anyone can edit (T4): such a page identifies a person but never builds their facts, so the
    membership is created but not accepted by the decision, the way a sibling placement already is. A relationship the record's
    indexer computed rather than the record stating it (catalog.relation_classes: FamilySearch's own relatives-table groupings)
    is written the same way, Undecided and marked computed, with the reason in held_back; a stated relationship between the same
    two on the record is read first, and the computed one adds nothing beside it. A parent-child relation is
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
    statement already there moves only from undecided to accepted (withdrawn, it stands again): one whose status a person
    decided on its own (person_decided) stays as the person left it. Returns
    the links written: person, role, the other person, the page's own word, whether the membership is new, "undecided" for
    a sibling placement, a link from a page anyone can edit or one the indexer computed, and "computed" for the last."""
    q = _q(cx)
    out = []
    identity = editable(cx, sha)  # a page anyone can edit: the memberships it states stand, but their assertions do not
    cat = Catalog(cx, tree_id)
    # persona id -> persona dict of this extraction (match.personas_of shape), built once, only when needed
    listed_personas = None
    def person_of(x):
        r = q.execute(
            "SELECT pp.person_id FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?",
            (x, tree_id)
        ).fetchone()
        if r:
            return r["person_id"]
        # a listed relative is never proposed only on a page anyone can edit
        if not identity:
            return None
        nonlocal listed_personas
        if listed_personas is None:
            eid = q.execute("SELECT extraction_id FROM persona WHERE id=?", (persona_id,)).fetchone()["extraction_id"]
            listed_personas = {p["id"]: p for p in personas_of(cx, eid)}
        pr = listed_personas.get(x)
        if not pr:
            return None
        rejected = {
            r["person_id"]
            for r in q.execute("SELECT person_id FROM person_persona WHERE persona_id=? AND status='rejected'", (x,))
        }
        fits = [c for c in fits_by_name_and_year(cat, cx, tree_id, pr) if c != pid and c not in rejected]
        if len(fits) != 1:
            return None
        other_pid = fits[0]
        # this decision's earlier trace to a person the persona no longer fits alone
        q.execute(
            "DELETE FROM person_persona WHERE persona_id=? AND person_id<>? AND status='undecided' AND proposal_id=?",
            (x, other_pid, prop_id)
        )
        q.execute(
            "INSERT OR IGNORE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,'undecided',?,?,?)",
            (other_pid, x, prop_id, by, ts)
        )
        return other_pid
    def member(fid, who, role):
        if q.execute(
            "SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, who, role)
        ).fetchone():
            return False
        q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (fid, who, role))
        return True
    def assert_(fid, who, role, other, as_written, new, status="accepted", placed=None, computed=False):
        sid, cite = dumps([fid, who, role]), f"{as_written} on the record"
        # the record states this link itself
        if (
            computed
            and q.execute(
                "SELECT 1 FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256=? AND status='accepted'",
                (sid, sha)
            ).fetchone()
        ):
            return
        notes = {
            "proposal": prop_id, **({"placed": placed} if placed else {}), **({"computed": True} if computed else {})
        }
        old = q.execute(
            "SELECT id, status, notes, person_decided FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256=? AND citation_text=?",
            (sid, sha, cite)
        ).fetchone()
        if old:
            if old["status"] == "undecided" and status == "accepted" and not old["person_decided"]:
                q.execute(
                    "UPDATE assertion SET status=?, asserted_by=?, asserted_at=?, notes=? WHERE id=?",
                    (status, by, ts, dumps(notes), old["id"])
                )
            else:
                return
        else:
            q.execute(
                """INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                            VALUES (?,?,'family_member',?,?,?,?,?,?,?,?)""",
                (ulid(), tree_id, sid, persona_id, sha, cite, status, by, ts, dumps(notes))
            )
        out.append(
            {
                "family": fid,
                "person": who,
                "role": role,
                "of": other,
                "as": as_written,
                "new": new,
                "undecided": status != "accepted",
                "placed": placed,
                "computed": computed
            }
        )
    name = lambda i: q.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()["display_name"]
    def indexer(as_written, other):
        if held_back is not None:
            held_back.append(
                f"the link to {name(other)} ({as_written}) written undecided: the record's indexer, not the record, states it"
            )
    one = lambda sql, args: next((f for f, in q.execute(sql, args)), None)
    x_surname = q.execute("SELECT name_text FROM persona WHERE id=?", (persona_id,)).fetchone()["name_text"]
    x_surname = (split_persona_name(x_surname)[1] or [""])[-1]
    rows = list(q.execute("""SELECT kind, value_text, persona_id, related_persona_id FROM persona_relation
                             WHERE (persona_id=? OR related_persona_id=?) AND kind IN ('child','parent','spouse','sibling','other')""", (persona_id, persona_id)).fetchall())
    # the stated first
    rows = sorted(
        (
            (
                r,
                relation_classes(
                    cx, r["persona_id"], r["related_persona_id"], r["kind"], r["value_text"]
                )["relationship"] == "computed"
            )
            for r in rows
        ),
        key=lambda rc: rc[1]
    )
    for r, computed in rows:
        mine = r["persona_id"] == persona_id  # (X, kind, Y) reads: X is the <kind> of Y
        y_persona = r["related_persona_id"] if mine else r["persona_id"]
        kind, as_written = r["kind"], r["value_text"] or r["kind"]
        other = None
        if kind == "other":
            resolved = IN_LAW.get((r["value_text"] or "").strip().lower())
            # a half sibling, a grandchild, "other relative": not one of the six the rule resolves
            if not resolved:
                continue
            # the other persona is the in-law of this one: the tie is resolved from its side, when it is accepted
            if not mine:
                continue
            y_pid = person_of(y_persona)
            if not y_pid:
                continue
            got = resolve_in_law(cx, tree_id, y_pid, resolved, x_surname)
            # the relative it is in-law to does not resolve to one person: no link, the created person's card stands as is
            if not got:
                continue
            # resolve_in_law always reads "X is <kind> of other", whichever side the record's own row sat on
            kind, other = got
            mine = True
        else:
            other = person_of(y_persona)
        if not other or other == pid:
            continue
        if kind == "sibling":
            home = sibling_home(cx, tree_id, other)
            gone = died_before(cx, tree_id, home, pid, persona_id) if home else None
            # a parent of that home was dead before this one was born: a half sibling, perhaps, never placed under the couple
            if gone:
                if held_back is not None:
                    held_back.append(
                        f"not placed beside {name(other)} as a child of the same parents: {gone}; a half sibling, perhaps"
                    )
                continue
            if home:
                assert_(
                    home,
                    pid,
                    "child",
                    other,
                    f"{as_written} of {name(other)}",
                    member(home, pid, "child"),
                    status="undecided",
                    placed="sibling"
                )
            continue
        if kind == "spouse":
            fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                         WHERE fm.person_id=? AND fm.role='partner'""", (other, pid))
            if fid is None:
                fid = one("""SELECT fm.family_id FROM family_member fm WHERE fm.person_id=? AND fm.role='partner'
                                         AND (SELECT COUNT(*) FROM family_member x WHERE x.family_id=fm.family_id AND x.role='partner')=1""", (other,))
            if fid is None:
                fid = new_family(cx, tree_id, other, ts)
            status = "undecided" if identity or computed else "accepted"
            n = len(out)
            assert_(
                fid, pid, "partner", other, as_written, member(fid, pid, "partner"), status=status, computed=computed
            )
            assert_(fid, other, "partner", pid, as_written, False, status=status, computed=computed)
            if computed and not identity and len(out) > n:
                indexer(as_written, other)
            # the marriage the record dates, on the couple it joins: both partners now accepted on it
            assert_family_events(cx, tree_id, fid, [persona_id, y_persona], sha, prop_id, by, ts, computed=computed)
            continue
        child = pid if (kind == "child") == mine else other
        parent = other if child == pid else pid
        fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                     WHERE fm.person_id=? AND fm.role='child'""", (parent, child))
        new = False
        if fid is None:
            fid = one("""SELECT fm.family_id FROM family_member fm WHERE fm.person_id=? AND fm.role='child'
                         AND (SELECT COUNT(*) FROM family_member x WHERE x.family_id=fm.family_id AND x.role='partner')<2""", (child,))
            if fid is not None:
                new = member(fid, parent, "partner")
            else:
                fid = (
                    one("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (parent,))
                    or new_family(cx, tree_id, parent, ts)
                )
                new = member(fid, child, "child")
        n = len(out)
        assert_(
            fid,
            child,
            "child",
            parent,
            as_written,
            new,
            status="undecided" if identity or computed else "accepted",
            computed=computed
        )
        if computed and not identity and len(out) > n:
            indexer(as_written, other)
    return out

def died_before(cx, tree_id, fid, pid, persona_id):
    """Why a person cannot be placed as a child of a family's couple, or None: a partner's death, accepted on a trusted record
    or the owner's word and stating its date, that comes before the person's earliest birth the tree or the record under
    decision gives (a mother's before it, a father's more than a year before it: a child can be born after the father's
    death, never after the mother's). The words name the parent, the death and the birth."""
    q = _q(cx)
    births = [r["date_start"] for r in q.execute("""SELECT e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                   WHERE ep.person_id=? AND e.event_type='Birth' AND e.date_start IS NOT NULL""", (pid,))]
    births += [
        r["date_start"]
        for r in q.execute(
            "SELECT date_start FROM persona_fact WHERE persona_id=? AND fact_type='Birth' AND date_start IS NOT NULL",
            (persona_id,)
        )
    ]
    if not births:
        return None
    born = min(births)
    for partner, name, sex in q.execute(
        """SELECT fm.person_id, p.display_name, p.sex FROM family_member fm JOIN person p ON p.id=fm.person_id
                                          WHERE fm.family_id=? AND fm.role='partner' AND fm.person_id<>?""", (fid, pid)
    ).fetchall():
        for e in q.execute(
            """SELECT e.id, e.date_text, e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id
                              WHERE ep.person_id=? AND e.event_type='Death' AND e.date_start IS NOT NULL""", (partner,)
        ).fetchall():
            if not trusted_evidence(cx, tree_id, "event", [e["id"]], stating="date"):
                continue
            died = e["date_start"]
            if len(died) == 10 and len(born) == 10:
                y, rest = int(died[:4]), died[4:]
                before = (died < born) if sex != "M" else (f"{y + 1:04d}{rest}" < born)
            else:
                before = int(died[:4]) < int(born[:4]) - (1 if sex == "M" else 0)
            if before:
                text = q.execute(
                    "SELECT date_text FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type='Birth' AND e.date_start=? LIMIT 1",
                    (pid, born)
                ).fetchone()
                return f"{name}'s accepted death ({e['date_text']}) comes before the birth ({text['date_text'] if text else born})"
    return None

def sibling_home(cx, tree_id, pid):
    """The one family a person is an accepted child of, where a sibling stated on a record can be placed; None when the link
    is not accepted or the person is a child in more than one family."""
    cat = Catalog(cx, tree_id)
    fams = [
        f
        for f, in _q(cx).execute("SELECT family_id FROM family_member WHERE person_id=? AND role='child'", (pid,))
        if cat.basis("family_member", dumps([f, pid, "child"])) == "accepted"
    ]
    return fams[0] if len(fams) == 1 else None

def record_says(cx, tree_id, pid, sha):
    """What a held record states about a person, as the assertions it made: each with a label and, for an event, whether the
    record's value disagrees with the event's own value (date compared as dates, place as the matcher compares it)."""
    q = _q(cx)
    cat = Catalog(cx, tree_id)
    name = lambda i: q.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()["display_name"]
    out = []
    for a in q.execute("""SELECT a.id, a.status, a.subject_kind, a.subject_id, a.citation_text, pf.fact_type, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.value_text, ps.raw
                          FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          WHERE a.tree_id=? AND a.artifact_sha256=?
                          AND ((a.subject_kind='person' AND a.subject_id=?) OR (a.subject_kind='event' AND a.subject_id IN (SELECT event_id FROM event_participant WHERE person_id=?))
                               OR (a.subject_kind='family_member' AND a.subject_id LIKE ?)) ORDER BY a.subject_kind, a.asserted_at""", (tree_id, sha, pid, pid, f'%"{pid}"%')):
        item = {"id": a["id"], "status": a["status"], "disagrees": None, "link": a["subject_kind"] == "family_member"}
        if item["link"]:
            fid, who, role = json.loads(a["subject_id"])
            item["fact"] = (
                ("parents link" if role == "child" else "spouse link") if who == pid else f"{name(who)}'s spouse link"
            ) + f" ({a['citation_text']})"
        else:
            item["fact"] = " ".join(
                x for x in (a["fact_type"], a["date_text"] or a["value_text"] or "", a["raw"] or "") if x
            ).strip()
            if a["subject_kind"] == "event":
                ev = q.execute(
                    "SELECT id, date_text, date_start, date_end, date_qualifier, place_id FROM event WHERE id=?",
                    (a["subject_id"],)
                ).fetchone()
                dv = date_verdict(
                    {
                        "start": a["date_start"],
                        "end": a["date_end"],
                        "text": a["date_text"],
                        "qualifier": a["date_qualifier"]
                    },
                    {
                        "start": ev["date_start"],
                        "end": ev["date_end"],
                        "text": ev["date_text"],
                        "qualifier": ev["date_qualifier"]
                    }
                ).verdict
                tp = cat.place(ev["id"], ev["place_id"])["text"] if ev["place_id"] else None
                if dv == "disagrees":
                    item["disagrees"] = f"date: the tree says {ev['date_text']}"
                elif place_verdict(a["raw"], tp).verdict == "disagrees":
                    item["disagrees"] = f"place: the tree says {tp}"
        out.append(item)
    return out

def answer_questions(cx, tree_id, pid, prop_id, by):
    """Regenerate the person's plan; a question of an answerable kind that the regeneration closes was answered by the
    proposal: closed_reason answered, answered_by_proposal_id set. Other kinds stay as the planner closed them."""
    q = _q(cx)
    st = plan_person(cx, tree_id, pid, by)
    answered = []
    for qid in st.get("closed", []):
        r = q.execute("SELECT kind FROM research_question WHERE id=?", (qid,)).fetchone()
        if r and r["kind"] in ANSWERABLE:
            q.execute(
                "UPDATE research_question SET closed_reason='answered', answered_by_proposal_id=? WHERE id=?",
                (prop_id, qid)
            )
            answered.append(qid)
    return answered

def decide_place(cx, tree_id, p, status, by, note, choice, kind=None, alone=False):
    """The owner's answer on a place card, which is the answer on every card that asks the same (resolve_places.place_groups:
    cards offering the same places, the same of them verified, are one question put to different spellings): each string of the
    group is decided alike by decide_place_string, accepted to the place the choice names on its own card (found by the
    candidate, not its number) or rejected with the same reason, each with its own audit row. kind classifies how the string
    answered on differs from the place's own name; the others' variant_kind is left unclassified. alone decides this card's
    string only. Then the cards of the people whose facts carry the words are matched again (rematch_people). Returns the
    answer on this card with `also` the answers on the others, a summary of all and `rematched`, or an error, in which case
    the caller rolls back what was written."""
    from resolve_places import candidate_key, place_groups
    others = [] if alone else [g for g in place_groups(cx, tree_id).get(p["id"], []) if g["proposal"] != p["id"]]
    first = decide_place_string(cx, tree_id, p, status, by, note, choice, kind)
    if "error" in first:
        return first
    q = _q(cx)
    key = (
        candidate_key(json.loads(p["payload_json"])["candidates"][int(choice)])
        if status == "accepted" and others
        else None
    )
    also = []
    for g in others:
        sp = q.execute("SELECT * FROM proposal WHERE id=?", (g["proposal"],)).fetchone()
        at = (
            next(
                (i for i, c in enumerate(json.loads(sp["payload_json"])["candidates"]) if candidate_key(c) == key), None
            )
            if key
            else None
        )
        r = decide_place_string(cx, tree_id, sp, status, by, note, at)
        if "error" in r:
            return r
        also.append(r)
    if also:
        first = {
            **first,
            "also": also,
            "summary": "; ".join(
                [first["summary"]] + [r["summary"] for r in also]
            ) + f" (the same question put {len(also) + 1} ways, answered alike)"
        }
    events = [e for r in [first] + also for e in r["event_ids"]]
    people = [
        r["person_id"]
        for e in events
        for r in q.execute("SELECT person_id FROM event_participant WHERE event_id=? AND person_id IS NOT NULL", (e,))
    ]
    return {**first, "rematched": rematch_people(cx, tree_id, by, people)}

def decide_place_string(cx, tree_id, p, status, by, note, choice, kind=None):
    """The owner's answer on a place string the resolver left undecided (a place_resolution proposal): which real place its
    words mean (accepted, with the candidate chosen from the proposal by its index), or that they are not a place (rejected,
    the reason kept in the string's notes). The answer is about the words, so it applies to every fact carrying the same
    string: an accepted string takes its place_id from the candidate's hierarchy (resolve_places.Store, the candidate read
    back from the geocoder's cached answer to the proposal's own queries; a gazetteer's own candidate with no geocoder twin,
    a GOV or Wikidata place the geocoder does not know, becomes a place of its own name and position under the string's
    country, carrying the gazetteer's id and dated names), its status and resolver the acting user, and the
    resolver's apply_to_events fills every event whose strings are all resolved; a rejected string stays rejected wherever it
    appears and no event takes it. kind classifies how an accepted string differs from the place's own name
    (place_string.variant_kind: a typo, a jurisdiction error, …; docs/DATA-ARCHITECTURE.md §8). One audit row on the string,
    the proposal decided. Returns what was written, or an error."""
    from resolve_places import Store, apply_to_events, nominatim
    q = _q(cx)
    pay = json.loads(p["payload_json"])
    psid, raw = pay["place_string_id"], pay["raw"]
    ts = now()
    if p["status"] != "undecided":
        return {"error": "already decided"}
    ps = q.execute("SELECT status, place_id FROM place_string WHERE id=?", (psid,)).fetchone()
    if not ps:
        return {"error": "the place string is gone"}
    events = [r["id"] for r in q.execute("""SELECT DISTINCT e.id FROM event e JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                             WHERE e.tree_id=? AND pf.place_string_id=? AND a.status<>'rejected'""", (tree_id, psid))]
    leaf = place = None
    if status == "accepted":
        cands = pay.get("candidates") or []
        try:
            cand = cands[int(choice)]
        except (TypeError, ValueError, IndexError):
            return {"error": "choose one of the resolver's candidates for these words, or say they are not a place"}
        # a gazetteer's own place, no geocoder twin: its name and position under the string's country
        if cand.get("kind") == "gazetteer":
            from resolve_places import write_gazetteer
            st = Store(cx)
            country = (pay.get("parsed") or {}).get("country")
            names = cand.get("names") or []
            name = (
                next((n["name"] for n in names if not n.get("valid_to")), None)
                or (names[0]["name"] if names else cand.get("display_name", raw).split(" (")[0])
            )
            ptype = cand.get("type") if cand.get("type") in ("town", "village", "hamlet", "city") else "village"
            leaf = st.place(
                name,
                ptype,
                st.place(country, "country", None) if country else None,
                cand.get("lat"),
                cand.get("lon"),
                cand["id"] if cand.get("source") == "wikidata" else None
            )
            write_gazetteer(cx, leaf, cand)
            place = cand.get("display_name")
        else:
            full = next(
                (
                    c
                    for qy in pay.get("queries") or []
                    for c in nominatim(qy)
                    if f"{c.get('osm_type')}/{c.get('osm_id')}" == cand.get("osm")
                ),
                None
            )
            if full is None:
                return {
                    "error": f"the geocoder's answer naming {cand.get('display_name')} is not in the cache and the geocoder did not give it again"
                }
            leaf = Store(cx).hierarchy(full)
            place = cand.get("display_name")
        if not q.execute("SELECT 1 FROM place_name WHERE place_id=? AND name=?", (leaf, raw)).fetchone():
            q.execute(
                "INSERT INTO place_name (id,place_id,name,is_primary) VALUES (?,?,?,?)", (ulid(), leaf, raw, False)
            )
        q.execute(
            "UPDATE place_string SET place_id=?, status='accepted', resolver=?, resolved_at=?, variant_kind=?, notes=? WHERE id=?",
            (
                leaf,
                by,
                ts,
                kind,
                dumps(
                    {"how": "chosen from the proposal's candidates", "match": cand, "proposal": p["id"], "note": note}
                ),
                psid
            )
        )
    else:
        q.execute(
            "UPDATE place_string SET place_id=NULL, status='rejected', resolver=?, resolved_at=?, notes=? WHERE id=?",
            (by, ts, dumps({"reason": note or "not a place", "proposal": p["id"]}), psid)
        )
    q.execute(
        "UPDATE proposal SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE id=?",
        (status, by, ts, note, p["id"])
    )
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "accept" if status == "accepted" else "reject",
            "place_string",
            psid,
            dumps(
                {
                    "raw": raw,
                    "from": {"status": ps["status"], "place_id": ps["place_id"]},
                    "to": {"status": status, "place_id": leaf, "variant_kind": kind if status == "accepted" else None},
                    "place": place,
                    "proposal": p["id"],
                    "events": len(events),
                    "note": note
                }
            )
        )
    )
    placed = 0
    if status == "accepted":
        apply_to_events(cx, tree_id, by, ts)
        placed = sum(
            1 for e in events if q.execute("SELECT place_id FROM event WHERE id=?", (e,)).fetchone()["place_id"]
        )
    n = f"{len(events)} fact{'s' if len(events) != 1 else ''} carr{'y' if len(events) != 1 else 'ies'} these words"
    summary = (
        (
            f"\u201c{raw}\u201d means {place}: {n}, {placed} now placed"
            + ("" if placed == len(events) else f", {len(events) - placed} waiting on another string of theirs")
        )
        if status == "accepted"
        else f"\u201c{raw}\u201d is not a place: {n}, none takes it"
    )
    return {
        "ok": True,
        "kind": "place_resolution",
        "status": status,
        "raw": raw,
        "place": place,
        "place_id": leaf,
        "events": len(events),
        "event_ids": events,
        "placed": placed,
        "summary": summary
    }

def decide(cx, tree_id, prop_id, status, by, note=None, choice=None, kind=None, alone=False):
    """A decision on a proposal: is this record's persona this person (persona_match), or a person the tree does not have
    (new_person); or, on a place_resolution proposal, the owner's answer on a place card (decide_place, choice naming the
    candidate, kind how the string differs from the place's name, alone for this card's string only). Accepted: the link accepted, every fact the record states accepted onto the person (assert_facts), the
    family links it states with persons already matched on it accepted (link_family), the plans of the person and of the
    person the record was fetched for regenerated and the questions that closes marked answered (the regeneration logs a
    household record, a census page whichever way it arrived, found on the person's own step for its census year,
    plan_person through log_search.hold_household, so their row reads held and no runner searches that census again for a
    household the tree has read, the way the runner logs the household's other steps for a connector's answer); on a page
    anyone can edit the
    decision is an identity: the link accepted, the memberships it states created where the tree lacks them with an Undecided
    assertion, and the facts written undecided. Rejected: the link rejected;
    for a new person nothing but the proposal. A proposal the rule accepted can be rejected by a person afterwards: the link,
    every assertion and the name alias the rule wrote turn rejected, and so does every family link the decision was one of
    the two acceptances for, written by the other's decision (links_resting_on, what a withdrawal takes back: the persona is
    not this person, so the record states no link of theirs), and a step held by the record for this person is planned
    again; rejecting a card whose decision the rule took back turns rejected what that decision wrote and the links its
    withdrawal took back the same way, and either rejection is the person's own decision on each of those statements
    (person_decided), so no later acceptance of the other card writes the link again. One the rule took back (withdraw) is
    accepted with everything it had written standing again, its name alias included, save a statement a person has decided
    on its own since, which keeps the person's status. Either way, once the plans are regenerated, the rule goes over the conflicts of the people whose plans the
    decision changed (rule_conflicts): its own resolutions there examined again, every open conflict on an event's date or
    place decided where the classes favour one side without doubt; and then the undecided cards putting a persona to one of
    those people are matched again on their evidence as it now stands (rematch): one the matcher no longer puts to that
    person closes as superseded and its record is matched again, one it still does takes its words as they now read. The
    decision's audit row is written as it takes effect, before the conflicts it changes and the cards of the same record
    the rule takes next, so audit ids run in the order decisions were taken (reconsider examines the rule's decisions in
    that order). Returns what was written, rematched the rows of the cards matched again, or an error."""
    q = _q(cx)
    p = q.execute("SELECT * FROM proposal WHERE id=? AND tree_id=?", (prop_id, tree_id)).fetchone()
    if p and p["kind"] == "place_resolution" and status in ("accepted", "rejected"):
        return decide_place(cx, tree_id, p, status, by, note, choice, kind, alone)
    if not p or p["kind"] not in ("persona_match", "new_person") or status not in ("accepted", "rejected"):
        return {"error": "not a persona match, new person or place resolution, or bad status"}
    pay = json.loads(p["payload_json"])
    persona_id, person_id = pay["persona_id"], pay.get("person_id")
    ts = now()
    n = 0
    members = []
    alias_id = None
    identity = editable(cx, pay["artifact_sha256"])  # a page anyone can edit: the identity and its links, never a fact
    if (
        p["status"] != "undecided"
        and not (p["status"] == "accepted" and status == "rejected" and (p["decided_by"] or "").startswith("rule:"))
    ):
        return {"error": "already decided"}
    # a person's own decision on every statement the card's decision wrote, standing or taken back by the rule, and on every
    # family link it was one of the two acceptances for: the persona is not this person, so the record states none of them
    links = links_resting_on(cx, tree_id, prop_id, taken_back=True) if status == "rejected" else []
    if status == "rejected":
        n = q.execute(
            "UPDATE assertion SET status='rejected', asserted_by=?, asserted_at=?, person_decided=TRUE WHERE tree_id=? AND json_valid(notes) AND json_extract(notes,'$.proposal')=?",
            (by, ts, tree_id, prop_id)
        ).rowcount
        if links:
            n += q.execute(
                f"UPDATE assertion SET status='rejected', asserted_by=?, asserted_at=?, person_decided=TRUE WHERE id IN ({','.join('?' * len(links))})",
                (by, ts, *links)
            ).rowcount
        # the name as the record writes it goes with the record
        q.execute(
            "UPDATE alias SET status='rejected' WHERE tree_id=? AND json_valid(notes) AND json_extract(notes,'$.proposal')=?",
            (tree_id, prop_id)
        )
    q.execute(
        "UPDATE proposal SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE id=?",
        (status, by, ts, note, prop_id)
    )
    # created once; a decision the rule took back and that is taken again links the same person
    if p["kind"] == "new_person" and status == "accepted" and not person_id:
        person_id = create_person(cx, tree_id, persona_id, ts)
        q.execute(
            "UPDATE proposal SET payload_json=json_set(payload_json,'$.person_id',?) WHERE id=?", (person_id, prop_id)
        )
    if person_id:
        # the decision is about this entry of the record: every reading's persona of it takes it
        for pe_id in same_personas(cx, persona_id):
            q.execute(
                "INSERT OR REPLACE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)",
                (person_id, pe_id, status, prop_id, by, ts)
            )
    answered = []
    if status == "accepted":
        # what the rule wrote and took back stands again; what it wrote undecided, and what a person set undecided on its own, stays so
        n = q.execute(f"""UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=? WHERE tree_id=? AND status='undecided' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?
                          AND {ACCEPTED_WITH_RECORD} AND NOT person_decided""", (by, ts, tree_id, prop_id)).rowcount
        # the name alias a withdrawn decision on this record left undecided stands again with this one
        q.execute("""UPDATE alias SET status='accepted', notes=json_set(notes,'$.proposal',?) WHERE tree_id=? AND entity_kind='person' AND entity_id=? AND source_artifact_sha256=?
                     AND status='undecided' AND json_valid(notes) AND json_extract(notes,'$.proposal') IS NOT NULL""", (prop_id, tree_id, person_id, pay["artifact_sha256"]))
        m, sha = assert_facts(cx, tree_id, person_id, persona_id, prop_id, by, ts)
        n += m
        alias_id = write_name_alias(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts)
        held_back = []
        members = link_family(cx, tree_id, person_id, persona_id, sha, prop_id, by, ts, held_back=held_back)
        if held_back:  # what the record states and the decision did not write, said in the decision itself
            note = "; ".join([note] + held_back) if note else "; ".join(held_back)
            q.execute("UPDATE proposal SET decision_note=? WHERE id=?", (note, prop_id))
    # the decision is the record's: every other copy's persona of this entry takes it
    if person_id:
        carry(cx, by, pay["artifact_sha256"], trees=[tree_id], settle=False)
    # a spouse joined on the record: the marriage it dates is now on their family too; a link taken back with a rejection,
    # each person it joined
    linked = [
        json.loads(r["subject_id"])[1]
        for r in q.execute(
            f"SELECT subject_id FROM assertion WHERE subject_kind='family_member' AND id IN ({','.join('?' * len(links))})",
            links
        )
    ] if links else []
    people = [
        pid
        for pid in dict.fromkeys(
            [person_id, pay.get("subject_person_id")] + [m["of"] for m in members if m["role"] == "partner"] + linked
        )
        if pid
    ]
    for pid in people:
        answered += answer_questions(cx, tree_id, pid, prop_id, by)
    # a step the record held for this person is planned again
    released = (
        release_household(cx, tree_id, person_id, pay["artifact_sha256"], by)
        if status == "rejected" and person_id and not identity
        else []
    )
    # the plan sees the row open again
    if released:
        answered += answer_questions(cx, tree_id, person_id, prop_id, by)
    # written as the decision takes effect, ahead of what it brings on: the audit ids run in the order decisions were taken
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "accept" if status == "accepted" else "reject",
            "proposal",
            prop_id,
            dumps(
                {
                    "kind": p["kind"],
                    "persona": persona_id,
                    "person": person_id,
                    "identity": identity,
                    "assertions": n,
                    "alias": alias_id,
                    "memberships": members,
                    "links": links,
                    "answered": answered,
                    "released_steps": released,
                    "note": note
                }
            )
        )
    )
    # the conflicts the decision opened or changed, and the rule's own resolutions that rest on what it changed
    conflicts = rule_conflicts(cx, tree_id, by, people=people)
    # the cards these people's evidence has passed by: matched again
    rematched = rematch_people(cx, tree_id, by, people)
    # the record's other personas come up next, against this person's relatives, on the current reading of the record
    if status == "accepted":
        eid = q.execute("SELECT extraction_id FROM persona WHERE id=?", (persona_id,)).fetchone()["extraction_id"]
        while (
            later := q.execute("SELECT superseded_by FROM extraction WHERE id=?", (eid,)).fetchone()["superseded_by"]
        ):
            eid = later
        match_record(cx, eid, by.split(" for ", 1)[-1] if by.startswith("rule:") else by)
    return {
        "ok": True,
        "status": status,
        "kind": p["kind"],
        "person": person_id,
        "persona": persona_id,
        "identity": identity,
        "assertions": n,
        "alias": alias_id,
        "memberships": members,
        "links": links,
        "answered": answered,
        "released_steps": released,
        "note": note,
        "conflicts": conflicts,
        "rematched": rematched
    }

def _stands_for(cat, persona, cand, chosen):
    """Whether a persona on a page anyone can edit stands for a person of the tree as the relative the identity rule may count:
    it fits the person, or the given name and the surname agree and nothing compared disagrees (a memorial lists a relative by
    name and years alone)."""
    fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen)
    if fits:
        return True
    given = any(a.field == "given name" for a in agree)
    surname = any(a.field == "surname" for a in agree) or any(a.married for a in absent)
    return given and surname and not disagree

FIELD_EVENT = {
    "birth date": ("Birth", "date", "birth"),
    "death date": ("Death", "date", "death"),
    "birth place": ("Birth", "place", "birth place"),
    "burial place": ("Burial", "place", "burial place"),
    "death place": ("Death", "place", "death place")
}

def against(cx, tree_id, eid, axis, value, without=(), primary=False, record_state=None):
    """The accepted statements on this event whose date or place disagrees with value, a record's (a date, {start, end, text,
    qualifier}; a place, its words): what the standing rule refuses a record on (docs/RESEARCH-WORKFLOW.md §5–7, what of an
    event's value is accepted), whatever the event itself shows, so a claim the event shows never vetoes, and a record that
    agrees with that claim is still refused where an accepted statement gives another value. A statement counts when it is
    accepted, of the event's own type, carries no mark (MARKS) and is not one a standing resolution set aside
    (catalog.set_aside); the owner's own word with no record fact of its own (a vouch: facts.vouch) stands for the event's
    own date as it stands, and gives no place. A place is compared as the place the statement's words are resolved to when
    they are, and disagrees when neither agrees with the other (catalog.place_verdict, a bare county on the record read
    with record_state, the state of its own collection), unless both name parts of the event's own place, neither inside it,
    as Catalog.disagreements reads two such statements (a death index's state and an obituary's town written without it are
    parts of one place). primary: only a statement holding primary information
    (catalog.evidence_classes), the owner's word not among them. without: proposal ids whose statements do not count, and
    statements that do not (reconsider, unless). Returns [(assertion id, the value it gives in words, its record in words)]."""
    from catalog import set_aside
    q = _q(cx)
    cat = Catalog(cx, tree_id)
    skip, skipped = unless(without)
    ev = q.execute(
        "SELECT event_type, date_text, date_start, date_end, date_qualifier, place_id FROM event WHERE id=?", (eid,)
    ).fetchone()
    rows = q.execute(f"""SELECT a.id, a.artifact_sha256, a.persona_fact_id, pf.fact_type, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw,
                                CASE WHEN ps.status='accepted' THEN ps.place_id END AS place_id
                         FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                         WHERE a.subject_kind='event' AND a.subject_id=? AND a.status='accepted' AND NOT {marked()} {skip}
                         ORDER BY a.asserted_at, a.id""", (eid, *skipped)).fetchall()
    shown = (cat.place(eid, ev["place_id"]) or {}).get("text") if axis == "place" else None
    def part(p, state=None):
        """Whether a place names a part of the event's own place, not a place inside it."""
        f = (
            place_verdict(p, shown, record_state=state, dated_names=cat.dated_names(ev["place_id"]))
            if shown
            else Finding("absent")
        )
        return f.verdict == "agrees" and not f.finer
    out, aside = [], None
    for r in rows:
        own = r["persona_fact_id"] is None
        if not own and r["fact_type"] != ev["event_type"]:
            continue
        if axis == "date":
            src = ev if own else r
            d = {
                "start": src["date_start"] or src["date_end"],
                "end": src["date_end"],
                "text": src["date_text"],
                "qualifier": src["date_qualifier"]
            }
            if not d["start"] or date_verdict(value, d).verdict != "disagrees":
                continue
            given = d["text"] or d["start"]
        else:
            if own or not r["raw"]:
                continue
            given = cat._place_chain(r["place_id"])["text"] if r["place_id"] else r["raw"]
            names = cat.dated_names(r["place_id"])
            if place_verdict(value, given, record_state=record_state, dated_names=names).verdict == "agrees":
                continue
            if place_verdict(given, value, dated_names=names).verdict == "agrees":
                continue
            if part(value, record_state) and part(given):
                continue
        if primary and (own or (evidence_classes(cx, r["id"]) or {}).get("information") != "primary"):
            continue
        if aside is None:
            aside = set_aside(cx, eid, axis)
        if r["id"] in aside:
            continue
        out.append((r["id"], given, cat.record_label(r["artifact_sha256"])))
    return out

def held_against(cx, tree_id, cand_id, other_id, kind, without=()):
    """Whether the tree holds, on an accepted statement resting on a trusted record or the owner's word (trusted_evidence),
    the state a stated relationship of the candidate to other contradicts: for a child, the candidate's own parents; for a
    parent, the other's parents; for a spouse, a spouse of the candidate's; for a sibling, both the candidate's parents and
    the other's. A link the file only claims, or no link at all, holds nothing against the record."""
    q = _q(cx)
    rows = lambda pid, role: [
        dumps([f, pid, role])
        for f, in q.execute("SELECT family_id FROM family_member WHERE person_id=? AND role=?", (pid, role))
    ]
    held = lambda pid, role: trusted_evidence(cx, tree_id, "family_member", rows(pid, role), without=without)
    if kind == "child":
        return held(cand_id, "child")
    if kind == "parent":
        return held(other_id, "child")
    if kind == "spouse":
        return held(cand_id, "partner")
    if kind == "sibling":
        return held(cand_id, "child") and held(other_id, "child")
    return True

def split_disagree(cx, tree_id, cand, persona, disagree, chosen, without=(), editable_page=False):
    """Partition the record's disagreements into those against an accepted value (a veto), those against a bare claim (named
    in the decision note instead, never a veto) and a birth place that differs from an accepted one. A birth or death date, a
    birth, death or burial place is read against the accepted statements on the event (against), never against the value
    the event shows, which may itself be a claim (docs/RESEARCH-WORKFLOW.md §5–7, what of an event's value is accepted):
    compare()'s difference with the shown value is a veto only where an accepted statement disagrees too, and a value
    compare() finds no difference in is still met with the accepted statements, a disagreement with one written as its own
    line. A stated relationship is read against what the tree holds of it on accepted evidence (held_against), so a family
    the file only claims is a claim here too. A birth place, secondary on nearly every record and never a point, never
    vetoes, and when it differs from an accepted value the difference is a conflict question once the record is taken; every
    other kind of disagreement (a name, a middle name, sex) vetoes. On a page anyone can edit (editable_page), a date or a
    place that disagrees with an accepted statement holding primary information is no veto either: the primary record
    stands, and the page's value, written undecided, is a contradiction of it, a conflict question once the page's identity
    is taken (the owner, 3 Oct 2026: a page anyone can edit is not trusted; use the primary document and tag the page as a
    contradiction). without: proposal ids whose statements do not count (reconsider). Returns (vetoes, claims, conflicts),
    each a list of findings (catalog.Finding, in words by match.said), a contradiction among the conflicts."""
    state = persona.get("record_state")
    def accepted_against(field, primary=False):
        et, axis, at = FIELD_EVENT[field]
        eid = cand["events"].get(et)
        return against(cx, tree_id, eid, axis, persona[at], without, primary=primary, record_state=state) if eid else []
    vetoes, claims, conflicts, met = [], [], [], set()
    for d in disagree:
        field = d.field if d.field in FIELD_EVENT else None
        if field:
            met.add(field)
        if field and cand["events"].get(FIELD_EVENT[field][0]) and not accepted_against(field):
            claims.append(d)
        elif field == "birth place":
            conflicts.append(d)
        elif (
            field
            and cand["events"].get(FIELD_EVENT[field][0])
            and editable_page
            and accepted_against(field, primary=True)
        ):
            conflicts.append(d)
        elif d.field == "relationship":
            # the relative the finding names, by its persona on the record
            oc = chosen.get(d.other)
            vetoed = oc is None or held_against(cx, tree_id, cand["id"], oc["id"], d.kind, without)
            (vetoes if vetoed else claims).append(d)
        else:
            vetoes.append(d)
    # a value that agrees with what the event shows, or that the event does not show, met with the accepted statements
    for field, (et, axis, at) in FIELD_EVENT.items():
        value = persona[at]
        if field in met or not (value.get("start") or value.get("end") if axis == "date" else value):
            continue
        hit = accepted_against(field)
        if not hit:
            continue
        line = Finding(
            "disagrees",
            field=field,
            record=value["text"] or value["start"] or value["end"] if axis == "date" else value,
            tree=cand[at]["text"] if axis == "date" else cand[at],
            accepted=(hit[0][1], hit[0][2])
        )
        if field == "birth place":
            conflicts.append(line)
        elif editable_page and accepted_against(field, primary=True):
            conflicts.append(line)
        else:
            vetoes.append(line)
    return vetoes, claims, conflicts

# a relation group: the person's own role in the family joining the two, then the relative's
MEMBERSHIPS = {
    "parents": ("child", "partner"),
    "children": ("partner", "child"),
    "spouses": ("partner", "partner"),
    "siblings": ("child", "child")
}

def claimed_or_accepted(cx, tree_id, pid, other, group, rec, keys, without=(), claim_only=False):
    """Whether the tree links a person to another by a relation group (parents, children, spouses, siblings), claimed or
    accepted (docs/RESEARCH-WORKFLOW.md §5–7): in a family joining the two, the membership of each carries an accepted
    statement or the file's claim of it, the import's own statement (on a file this tree imported, tree_import), not
    rejected; with claim_only, the file's claim alone. Nothing else is the file's word: an undecided statement from a page
    anyone can edit or a link a withdrawn decision left claims nothing, and an indexer's grouping or a sibling placement
    (MARKS) nothing whatever its status. A statement from the record under decision on any of its copies (rec: record_self),
    a claim whose own citation is that record (keys: record_keys), one a decision in without wrote and one in without itself
    (reconsider, unless) never count (not_the_files_word)."""
    q = _q(cx)
    mine, theirs = MEMBERSHIPS[group]
    def stands(fid, who, role):
        return any(not_the_files_word(r, rec, keys, without, claim_only) is None for r in q.execute(f"""SELECT a.id, a.status, a.artifact_sha256, a.notes, a.artifact_sha256 IN (SELECT artifact_sha256 FROM tree_import WHERE tree_id=?) AS imported
                                          FROM assertion a WHERE a.tree_id=? AND a.subject_kind='family_member' AND a.subject_id=? AND a.status<>'rejected'""", (tree_id, tree_id, dumps([fid, who, role]))).fetchall())
    return any(stands(fid, pid, mine) and stands(fid, other, theirs) for fid, in q.execute("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role=?
                                        WHERE fm.person_id=? AND fm.role=?""", (other, theirs, pid, mine)).fetchall())

# what a page's identity left out, in words (event_claimed_or_accepted)
LEFT_OUT = {
    "self": "the page itself",
    "cites": "a claim citing this very page",
    "placed": "a sibling placement",
    "alternate": "a value a page keeps beneath the one it shows",
    "computed": "a link a record's indexer computed",
    "without": "a later decision of the rule",
    "undecided": "a statement left undecided",
    "editable": "an undecided fact another page anyone can edit types",
    "aside": "a statement the event's value was decided against"
}

def event_claimed_or_accepted(cx, tree_id, eid, axis, value, rec, keys, without=(), day=False):
    """Whether the tree holds the date or the place of an event that a page anyone can edit agrees with, claimed or accepted
    (docs/RESEARCH-WORKFLOW.md §5–7, the identity), as claimed_or_accepted reads a link: a statement on the event that
    stands (not_the_files_word) and gives value (gives; to the day, with day), whatever the event itself shows, never one a
    standing resolution set aside (catalog.set_aside). Returns (True, []), or (False, what the statements not rejected that
    give value but do not stand are, in words: LEFT_OUT)."""
    from catalog import set_aside
    q = _q(cx)
    left = []
    aside = None
    ev = q.execute("SELECT date_text, date_start, date_end, date_qualifier FROM event WHERE id=?", (eid,)).fetchone()
    for r in q.execute(f"""SELECT {STATEMENT_COLUMNS}, a.artifact_sha256 IN (SELECT artifact_sha256 FROM tree_import WHERE tree_id=?) AS imported
                           FROM assertion a {STATEMENT_JOINS} WHERE a.tree_id=? AND a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected'
                           ORDER BY a.asserted_at, a.id""", (tree_id, tree_id, eid)).fetchall():
        if not gives(ev, r, axis, value, day):
            continue
        if aside is None:
            aside = set_aside(cx, eid, axis)
        if r["id"] in aside:
            left.append("aside")
            continue
        why = not_the_files_word(r, rec, keys, without)
        if why is None:
            return True, []
        left.append("editable" if why == "undecided" and editable(cx, r["artifact_sha256"]) else why)
    return False, [LEFT_OUT[w] for w in dict.fromkeys(left)]

def claimed_relation_match(relations, accepted_on_record, linked):
    """Whether the persona's stated relationship names a persona already accepted on this very record as a person the tree
    links to the candidate by that relation, claimed or accepted (docs/RESEARCH-WORKFLOW.md §5-7): (group, other candidate,
    other name) when so, else None. relations: (kind, other persona, computed, other name), a relationship the record's
    indexer computed being no statement of the record's. accepted_on_record: persona id -> candidate, from person_persona
    rows already decided accepted on this extraction — not the fitting check's own guesses. linked(group, other person id):
    whether the tree links the two so (claimed_or_accepted)."""
    for kind, other_pid, computed, other_name in relations:
        other_cand = accepted_on_record.get(other_pid)
        if computed or not other_cand:
            continue
        group = {"child": "parents", "parent": "children", "spouse": "spouses", "sibling": "siblings"}.get(kind)
        if group and linked(group, other_cand["id"]):
            return group, other_cand, other_name
    return None

def dated_with_parents(cx, extraction_id):
    """Whether a reading of a register entry dates it and names a person's parents: a persona's fact carries a date, and a
    child-parent relationship between two of its personas is one the record states (catalog.relation_classes)."""
    q = _q(cx)
    if not q.execute("""SELECT 1 FROM persona_fact pf JOIN persona pe ON pe.id=pf.persona_id WHERE pe.extraction_id=? AND pf.fact_type NOT IN ('Name','Sex')
                        AND (pf.date_start IS NOT NULL OR pf.date_end IS NOT NULL)""", (extraction_id,)).fetchone():
        return False
    return any(
        relation_classes(
            cx, r["persona_id"], r["related_persona_id"], r["kind"], r["value_text"]
        )["relationship"] != "computed"
        for r in q.execute(
            """SELECT r.persona_id, r.related_persona_id, r.kind, r.value_text FROM persona_relation r JOIN persona pe ON pe.id=r.persona_id
                                     WHERE pe.extraction_id=? AND r.kind IN ('child','parent')""", (extraction_id,)
        ).fetchall()
    )

def _on(statements):
    """What the statements a point stands on are, in words: primary information, secondary information, your own word."""
    return " and ".join(
        dict.fromkeys(
            s["information"] if s["information"] == "your own word" else f"{s['information']} information"
            for s in statements
        )
    )

def copy_cards(cx, tree_id, prop):
    """A proposal as each copy of its record holds it (docs/DATA-ARCHITECTURE.md §7 decision 15): itself, then, for every
    other copy (same_record), the same proposal with the persona of the same entry on that copy's current reading in its place
    (catalog.entry_on), each with the file it stands on."""
    from catalog import copy_entry, current_reading, entry_on, record_copies
    pay = json.loads(prop["payload_json"])
    out = [(prop, pay["artifact_sha256"])]
    cur = current_entry(cx, pay["persona_id"]) or pay["persona_id"]
    for c in record_copies(cx, tree_id, *copy_entry(cx, cur))[1:]:
        r = current_reading(cx, c[0])
        other = entry_on(cx, cur, r) if r else None
        if other and (not c[1] or copy_entry(cx, other) == tuple(c)):
            out.append(
                (
                    {
                        **dict(prop),
                        "payload_json": dumps({**pay, "persona_id": other, "artifact_sha256": c[0], "extraction_id": r})
                    },
                    c[0]
                )
            )
    return out

def copy_named(cx, text):
    """A copy of a record as the owner names it: an archived file by its sha256 (or the first twelve or more of its characters)
    or its file name, and a listing's one row by the number after @ (ky-death-index-1946-davidson.txt@14205). (sha256,
    entry), or an error in words."""
    from catalog import NUMBERS, copy_entry, current_reading
    name, _, number = text.partition("@")
    hits = [
        r[0]
        for r in cx.execute(
            "SELECT sha256 FROM artifact WHERE sha256 LIKE ? OR original_filename=?",
            (name.lower() + "%" if re.fullmatch(r"[0-9a-fA-F]{12,64}", name) else "-", name)
        )
    ]
    if len(hits) != 1:
        return f"{name}: {'no archived file' if not hits else str(len(hits)) + ' archived files'} by that name"
    if not number:
        return (hits[0], "")
    e = current_reading(cx, hits[0])
    rows = (
        [
            p
            for p, r, role, seq, region in cx.execute(
                "SELECT id, name_text, role_in_record, sequence, region_json FROM persona WHERE extraction_id=?", (e,)
            )
            if persona_key(role, seq, r, region)[0] in NUMBERS and number in persona_key(role, seq, r, region)[1]
        ]
        if e
        else []
    )
    return (
        copy_entry(cx, rows[0])
        if len(rows) == 1
        else f"{text}: {'no row' if not rows else str(len(rows)) + ' rows'} of that number on the file's reading"
    )

def copies_on_word(cx, tree_id, a, b, same, by, note):
    """The owner's word on two archived copies, in this tree only (same_record, basis owner), standing above anything code
    found for the pair: one record (same), and every decision on either carried to the other (carry); or not one record, and
    what a decision on one had carried to the other given back: the link on the copy and its statements under that decision
    undecided again (one whose status a person decided on its own, person_decided, keeping it), the people's plans,
    conflicts and cards gone over again, and the copy matched again, its entry a card
    for the owner or the rule's. a, b: (sha256, entry). Returns the rows carried, or the links given back."""
    from catalog import current_reading, record_copies
    q = _q(cx)
    ts = now()
    q.execute(
        """INSERT INTO same_record (id,tree_id,a_sha256,a_entry,b_sha256,b_entry,same,basis,shared,decided_by,decided_at,notes) VALUES (?,?,?,?,?,?,?,'owner',NULL,?,?,?)""",
        (ulid(), tree_id, *a, *b, 1 if same else 0, by, ts, note)
    )
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "insert",
            "same_record",
            a[0],
            dumps({"copy": a, "of": b, "same": same, "note": note})
        )
    )
    if same:
        return carry(cx, by, a[0], trees=[tree_id])
    back, people = [], {}
    for x in (a, b):
        mine = {c[0] for c in record_copies(cx, tree_id, *x)}
        for pp in q.execute(
            """SELECT pp.person_id, pp.persona_id, pp.proposal_id, json_extract(p.payload_json,'$.artifact_sha256') AS on_sha FROM person_persona pp
                               JOIN persona pe ON pe.id=pp.persona_id JOIN proposal p ON p.id=pp.proposal_id
                               WHERE pe.artifact_sha256=? AND p.tree_id=? AND pp.status<>'undecided'""", (x[0], tree_id)
        ).fetchall():
            # a decision on this record's own copies stays
            if pp["on_sha"] in mine:
                continue
            q.execute(
                "UPDATE person_persona SET status='undecided', decided_by=NULL, decided_at=NULL WHERE person_id=? AND persona_id=?",
                (pp["person_id"], pp["persona_id"])
            )
            q.execute(
                """UPDATE assertion SET status='undecided', asserted_by=?, asserted_at=? WHERE tree_id=? AND artifact_sha256=? AND status<>'undecided' AND NOT person_decided
                         AND json_valid(notes) AND json_extract(notes,'$.proposal')=?""",
                (by, ts, tree_id, x[0], pp["proposal_id"])
            )
            back.append(
                {"person": pp["person_id"], "persona": pp["persona_id"], "proposal": pp["proposal_id"], "copy": x[0]}
            )
            people.setdefault(pp["person_id"], pp["proposal_id"])
    for pid, prop in people.items():
        answer_questions(cx, tree_id, pid, prop, by)
    if people:
        rule_conflicts(cx, tree_id, by, people=list(people))
        rematch_people(cx, tree_id, by, list(people))
    # the copy given back is matched again for the people it was given back from: its entry a card for the owner, or the rule's
    for sha in dict.fromkeys(b_["copy"] for b_ in back):
        match_record(
            cx,
            current_reading(cx, sha),
            by,
            about=list(dict.fromkeys(b_["person"] for b_ in back if b_["copy"] == sha))
        )
    return back

def rule_accepts(cx, tree_id, prop, without=()):
    """Whether the standing rule takes a proposal, and why, in words: (True, reason) or (False, why not), as
    docs/RESEARCH-WORKFLOW.md §5–7 states the rule ("The standing rule", and "What the rule counts" in the proof standard):
    the record taken on its points (rule_points), and then identity tested, not assumed (identity_refused): nobody else of
    the tree fits the persona as well, the person holds no other persona on this reading of the record, and nothing the
    record would add falls outside the person's life as accepted. A test that fails is a refusal with its reason, and the
    card stays the owner's. The record is every copy of it (copy_cards): it is taken on the points of the copy that earns
    them, and refused when any copy's persona of the entry disagrees against an accepted value or fails the identity
    tests, the reason naming that copy. A card putting an entry to the person a creation made from that very entry, which
    no route above takes and nothing vetoes, is judged as that creation (made_here): on the creation's own terms and its
    identity test, the person it made not counted."""
    cards = copy_cards(cx, tree_id, prop)
    seen = [rule_points(cx, tree_id, p, without) for p, _ in cards]
    on = (
        lambda i: ""
        if not i
        else " (on " + (
            cx.execute(
                "SELECT coalesce(original_filename, substr(sha256,1,12)) FROM artifact WHERE sha256=?", (cards[i][1],)
            ).fetchone()[0]
        ) + ", a copy of this record)"
    )
    taken = next((i for i, (ok, _, _) in enumerate(seen) if ok), None)
    veto = next((i for i, (_, _, vetoes) in enumerate(seen) if vetoes), None)
    if taken is None:
        made = made_here(cx, tree_id, prop) if veto is None else None
        if not made:
            return seen[0][:2]
        ok, why = rule_accepts(cx, tree_id, made, without)
        return (
            True,
            f"the person the rule created from this entry of the record, judged on this reading as that creation: {why}"
        ) if ok else (
            False,
            f"{seen[0][1]}; nor does this reading meet the terms of the creation that made them from this entry: {why}"
        )
    if veto is not None:
        return False, seen[veto][1] + on(veto)
    for i, (p, _) in enumerate(cards):
        refused = identity_refused(cx, tree_id, p, without)
        if refused:
            return False, refused + on(i)
    return True, seen[taken][1] + on(taken)

def made_here(cx, tree_id, prop):
    """The creation a card stands for (docs/RESEARCH-WORKFLOW.md §5–7, the creation route): when a persona_match card puts an
    entry of a record to the person a creation made from that very entry (a new_person proposal of that person on any
    reading's persona of the entry, on any copy of the record, that no person rejected: standing, taken back, or closed with
    its reading as superseded), the card as that creation, a new_person proposal of the person on the card's own persona and
    reading, the creation's id as payload made; else None."""
    if prop["kind"] != "persona_match":
        return None
    pay = json.loads(prop["payload_json"])
    entry = set().union(
        *(same_personas(cx, json.loads(p["payload_json"])["persona_id"]) for p, _ in copy_cards(cx, tree_id, prop))
    )
    for c in _q(cx).execute("""SELECT id, payload_json FROM proposal WHERE tree_id=? AND kind='new_person' AND json_extract(payload_json,'$.person_id')=?
                               AND (status<>'rejected' OR decision_note='superseded') ORDER BY created_at, id""", (tree_id, pay.get("person_id"))).fetchall():
        if json.loads(c["payload_json"])["persona_id"] in entry:
            return {**dict(prop), "kind": "new_person", "payload_json": dumps({**pay, "made": c["id"]})}
    return None

def rule_points(cx, tree_id, prop, without=()):
    """Whether the record of a proposal is one the standing rule takes on its points, and why, in words, with the
    disagreements against an accepted value that refuse it (split_disagree's vetoes, as findings): (True, reason, []) or
    (False, why not, vetoes, empty unless they are why), before identity is tested (rule_accepts).
    The record's kinds and their standing come from data/evidence-classes.csv (catalog.record_kinds, record_standing), on its
    current reading, the same for a page a parser read and an image read by hand or by the model; the persona is judged on that
    reading too, the persona of the same entry there (catalog.current_entry) with its facts and the relationships and personas
    beside it, so a decision written on an earlier reading is examined on what the record now reads as. A trusted record (T1–T3) of
    an automated kind is taken on the accepted name and two points, nothing disagreeing against an accepted value
    (split_disagree); each point stands on the tree's own statements as ground() finds them, whatever value the event shows
    beside them (docs/RESEARCH-WORKFLOW.md §5–7, what of an event's value is accepted), and a date to the day or a
    relationship counts double where the tree holds it on such ground, whatever its information class (the classes decide
    conflicts, not whether two records that agree are about one person); a link no such statement grounds counts once where
    the file itself claims it, and nothing else stands in for the file (claimed_or_accepted). A persona whose
    name the tree does not hold on such ground is taken only through a relationship the record states to a persona already
    accepted on it whom the tree links to the candidate so, claimed or accepted (claimed_or_accepted). A page anyone can edit
    (T4) of an identity kind gives the identity alone, on the name and three of birth day, death day, burial place and one
    stated parent or spouse whom the tree links so, each claimed or accepted (event_claimed_or_accepted, claimed_or_accepted),
    a claim citing the page not among them, however many relatives it lists, the reason naming what it left out; a child or
    a sibling is none of the four. without: proposal ids whose
    assertions and persona links are not ground (reconsider); a name accepted on nothing outside them is judged by the
    relationship route, as it was taken."""
    q = _q(cx)
    pay = json.loads(prop["payload_json"])
    pid, sha = pay.get("person_id"), pay["artifact_sha256"]
    if prop["kind"] not in ("persona_match", "new_person") or (prop["kind"] == "persona_match" and not pid):
        return False, "not a card the rule decides", []
    x = q.execute(f"""SELECT x.name, CASE WHEN json_valid(e.structured_json) THEN json_extract(e.structured_json,'$.collection') END AS read_collection, c.name AS collection, {tier_sql()} AS trust_tier, s.name AS source
                     FROM extraction e JOIN extractor x ON x.id=e.extractor_id JOIN artifact ar ON ar.sha256=e.artifact_sha256
                     LEFT JOIN collection c ON c.id=ar.collection_id LEFT JOIN source s ON s.id=ar.source_id WHERE e.id=?""", (pay["extraction_id"],)).fetchone()
    if not x:
        return False, "the record's extraction is gone", []
    eid = pay["extraction_id"]
    while (later := q.execute("SELECT superseded_by FROM extraction WHERE id=?", (eid,)).fetchone()["superseded_by"]):
        eid = later
    kinds, year = record_kinds(cx, sha, eid)
    standing, by_kind = record_standing(kinds)
    coll = x["read_collection"] or x["collection"] or x["name"]
    # a page anyone can edit: the identity may be taken, its facts never
    identity = str(x["trust_tier"] or "")[:2] not in TRUSTED
    survivors_kind = NAMED_SURVIVORS in kinds                            # identifying only through who it names
    if identity:
        if standing != "identity":
            return False, f"a row on a {x['source'] or 'T4'} page anyone can edit is a hint until its own record is read: the owner decides it", []
    else:
        if standing != "automated":
            return False, f"a {coll} record is a hint until a person reads it (" + (
                f"data/evidence-classes.csv reads it as {by_kind}, {standing}"
                if by_kind
                else "data/evidence-classes.csv holds no kind it reads as"
            ) + ")", []
        yr = year or (re.search(r"\b(1[5-9]\d\d)\b", coll) or [None, None])[1]
        if HEAD_ONLY[0] in kinds and yr and int(yr) < HEAD_ONLY[1]:
            return False, f"a census before {HEAD_ONLY[1]} names only the head", []
        if by_kind == DATED_WITH_PARENTS and not dated_with_parents(cx, eid):
            return (
                False,
                "a church register entry is a hint until a person reads it, unless it is dated and names the parents",
                []
            )
    cat = Catalog(cx, tree_id)
    # the record as its current reading gives it: the persona of the same entry there, else the proposal's own reading
    cur = current_entry(cx, pay["persona_id"])
    reading, persona_id = (eid, cur) if cur else (pay["extraction_id"], pay["persona_id"])
    persona = next((p for p in personas_of(cx, reading) if p["id"] == persona_id), None)
    if not persona:
        return False, "persona not found", []
    # a link a decision under reconsideration wrote is not ground either
    skip = f"AND coalesce(pp.proposal_id,'') NOT IN ({','.join('?' * len(without))})" if without else ""
    chosen = {r["persona_id"]: candidate(cat, r["person_id"]) for r in q.execute(f"""SELECT pp.persona_id, pp.person_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                    JOIN person o ON o.id=pp.person_id WHERE pe.extraction_id=? AND pp.status='accepted' AND o.tree_id=? {skip}""", (reading, tree_id, *without))}
    # persona id -> candidate, genuinely decided on this record; the fitting loop below only guesses at a fit
    accepted_on_record = dict(chosen)
    if prop["kind"] == "new_person":
        return (*rule_creates(cx, prop, persona, x, identity, survivors_kind, accepted_on_record), [])
    fam = cat.family(pid)
    cand = candidate(cat, pid)
    relatives = [candidate(cat, rid) for g in ("parents", "spouses", "children") for rid, _ in fam[g]]
    INV = {"child": "parent", "parent": "child", "spouse": "spouse", "sibling": "sibling"}
    inverse = lambda p: q.execute("""SELECT r.kind, r.persona_id, r.value_text, o.name_text FROM persona_relation r JOIN persona o ON o.id=r.persona_id
                                     WHERE r.related_persona_id=? AND r.kind IN ('child','parent','spouse','sibling')""", (p["id"],)).fetchall()
    def both_ways(p):
        """A persona's stated relationships read from either side of the persona_relation row, in compare()'s shape: its own
        (the persona is the <kind> of the other) and the inverse of every row naming it (the other is the <kind> of the
        persona)."""
        return [(k, o, None, n) for k, o, _, n in p["relations"]] + [
            (INV[r["kind"]], r["persona_id"], None, r["name_text"]) for r in inverse(p)
        ]
    def stated(p):
        """both_ways with each relationship's computed class in place of the words: (kind, other persona, computed, other name),
        computed when the record's indexer, not the record, states it (catalog.relation_classes); the stated first."""
        computed = lambda a, b, k, v: relation_classes(cx, a, b, k, v)["relationship"] == "computed"
        rows = [(k, o, computed(p["id"], o, k, v), n) for k, o, v, n in p["relations"]] + [
            (
                INV[r["kind"]],
                r["persona_id"],
                computed(r["persona_id"], p["id"], r["kind"], r["value_text"]),
                r["name_text"]
            )
            for r in inverse(p)
        ]
        return sorted(rows, key=lambda r: r[2])
    # other persona id -> (agree, disagree) against the relative it stands for, for the relationship point below
    fitted = {}
    others = {p["id"]: p for p in personas_of(cx, reading)}
    # a persona the record relates to this one fits a relative the tree already links: it stands for that relative here
    for other in others.values():
        if other["id"] == persona["id"] or other["id"] in chosen:
            continue
        # its relation to the persona under decision, stated from either side, is one of the things it fits on (docs/RESEARCH-WORKFLOW.md §5-7)
        as_related = {**other, "relations": both_ways(other)}
        for c in relatives:
            # a birth place, never a veto, never unfits a relative either: the rule's decisions do not turn on a finer place another decision brought
            fits, agree, disagree, absent, near = compare(cat, as_related, c, {persona["id"]: cand}, birth_place=False)
            if fits or (identity and _stands_for(cat, as_related, c, {persona["id"]: cand})):
                chosen[other["id"]] = c
                fitted[other["id"]] = (agree, disagree)
                break
    # the record under decision, every copy of it one source with it
    rec = record_self(cx, tree_id, sha, persona["id"], pid)
    keys = record_keys(cx, sha, rec["copies"])
    def grounded(other_pid):
        """Whether the persona a stated relationship names earns the relationship its point: accepted on this record already,
        or standing for the tree's relative on something besides that relationship, a date or a place (an age is a birth
        year) that rests on more than a claim citing this very record (docs/RESEARCH-WORKFLOW.md, the proof standard). A
        persona that fits only through its relation to the one under decision, a name and the relationship, earns nothing:
        the relationship would be its own proof."""
        if other_pid in accepted_on_record:
            return True
        if other_pid not in fitted:
            return False
        c, other = chosen[other_pid], others[other_pid]
        for a in fitted[other_pid][0]:
            field = a.field if a.field in FIELD_EVENT else None
            if field:
                et, axis, at = FIELD_EVENT[field]
                if (
                    c["events"].get(et)
                    and rests_elsewhere(cx, c["events"][et], sha, axis, other[at], keys=keys, copies=rec["copies"])
                ):
                    return True
            elif a.field == "residence place":
                if any(
                    e["place"]
                        and place_verdict(other["residence place"], e["place"]["text"]).verdict == "agrees"
                        and rests_elsewhere(
                            cx, e["id"], sha, "place", other["residence place"], keys=keys, copies=rec["copies"]
                        )
                    for e in cat.events(c["id"])
                ):
                    return True
            elif a.field == "memorial":
                return True
        return False
    fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen)
    vetoes, claims, conflicts = split_disagree(
        cx, tree_id, cand, persona, disagree, chosen, without, editable_page=identity
    )
    if vetoes:
        return False, "disagrees: " + "; ".join(map(said, vetoes)), vetoes
    claim_note = (
        (" (disagrees with the tree's own claim, not yet accepted: " + "; ".join(map(said, claims)) + ")")
        if claims
        else ""
    )
    contradicts = [said(c) for c in conflicts if c.field != "birth place"]
    born = [said(c) for c in conflicts if c.field == "birth place"]
    claim_note += (
        " (the birth place differs from an accepted one, never a veto: a conflict question once the record is taken: "
        + "; ".join(born)
        + ")"
    ) if born else ""
    claim_note += (
        (
            " (contradicts a primary record the tree holds, which stands: the page's value is kept as a contradiction, a conflict question once its identity is taken: "
            + "; ".join(contradicts)
            + ")"
        )
        if contradicts
        else ""
    )
    # a wife under her married name: not a disagreement, and not the surname's absence either
    married = any(a.married for a in absent)
    if not any(a.field == "given name" for a in agree) or not (any(a.field == "surname" for a in agree) or married):
        return False, "the name does not agree in full", []
    if any(a.field == "surname" and a.spelling == "one letter apart" for a in agree):
        return False, "the surname agrees one letter apart: an indexer's slip a person reads, not the rule's ground", []
    relations = stated(persona)
    def joined(kind, other_pid):
        """The relative a stated relation names, when the tree links the two so on a membership not rejected (Catalog.family):
        (group, candidate) or None."""
        oc = chosen.get(other_pid)
        group = {"child": "parents", "parent": "children", "spouse": "spouses", "sibling": "siblings"}.get(kind)
        return (group, oc) if oc and group and any(rid == oc["id"] for rid, _ in fam[group]) else None
    if identity:
        # both sides a full date, the same day
        day = lambda t: any(a.field == f"{t} date" and not a.only for a in agree)
        # own: what agrees with the tree on nothing claimed or accepted, never a point -> what the tree has it from, in words
        points, own = [], {}
        def held(w, eid, axis, value, full=False, shown=False):
            """A point when a statement claimed or accepted gives the page's value (event_claimed_or_accepted), a date whatever
            the event shows; otherwise what was left out, said when something gave the value or the event shows it (shown)."""
            ok, left = (
                event_claimed_or_accepted(cx, tree_id, eid, axis, value, rec, keys, without, day=full)
                if eid
                else (False, [])
            )
            if ok:
                points.append(w)
            elif left or shown:
                own[w] = " and ".join(left)
        for t, w, et in (("birth", "birth date to the day", "Birth"), ("death", "death date to the day", "Death")):
            if len(persona[t]["start"] or "") == 10:
                held(w, cand["events"].get(et), "date", persona[t], full=True, shown=day(t))
        if any(a.field == "burial place" for a in agree):
            held("burial place", cand["events"].get("Burial"), "place", persona["burial place"], shown=True)
        anywhere = (set(), set(), set())  # no record's keys: the file's claim read whatever it cites
        # however many relatives the page lists, a stated parent or spouse is one of the four; a child or a sibling never
        for kind, other_pid, computed, other_name in relations:
            group, oc = {"child": "parents", "spouse": "spouses"}.get(kind), chosen.get(other_pid)
            if computed or not group or not oc or not grounded(other_pid):
                continue
            if claimed_or_accepted(cx, tree_id, pid, oc["id"], group, rec, keys, without):
                points.append(f"{REL_OF[group]} {other_name}")
                break
            if claimed_or_accepted(cx, tree_id, pid, oc["id"], group, rec, anywhere, without):
                own[f"{REL_OF[group]} {other_name}"] = LEFT_OUT["cites"]
        by_source = {}
        for w, src in own.items():
            by_source.setdefault(src, []).append(w)
        own_note = (
            (
                "; not counted: "
                + "; ".join(
                    ", ".join(ws) + (
                        f", which the tree has only from {src}" if src else ", which nothing claimed or accepted gives"
                    )
                    for src, ws in by_source.items()
                )
            )
            if own
            else ""
        )
        if len(points) < 3:
            return False, (
                "a page anyone can edit identifies a person only when the name and three of birth date to the day, death date to the day, burial place "
                "and a stated parent or spouse agree: here " + (
                    ", ".join(points) + (" agree" if len(points) > 1 else " agrees")
                    if points
                    else "the name alone agrees"
                ) + own_note
            ), []
        return True, "identity on a page anyone can edit: the name, " + ", ".join(
            points
        ) + " agree with the tree; the page's facts are written undecided, never accepted" + own_note + claim_note, []
    # the name is a claim, or accepted on nothing the rule may count here: the route through a stated relationship
    if cat.basis("person", pid) != "accepted" or not trusted_evidence(cx, tree_id, "person", [pid], without=without):
        rel = claimed_relation_match(
            relations,
            accepted_on_record,
            lambda group, other: claimed_or_accepted(cx, tree_id, pid, other, group, rec, keys, without)
        )
        # a stated sibling of someone accepted here, and the tree holds no parents to contradict it
        unplaced = (
            None
            if rel or fam["parents"]
            else next(
                (
                    (accepted_on_record[o], n)
                    for k, o, c, n in relations
                    if k == "sibling" and not c and o in accepted_on_record
                ),
                None
            )
        )
        if not rel and not unplaced:
            # a link the tree shows, on nothing that claims it
            loose = [
                f"{REL_OF[j[0]]} {n}"
                for k, o, c, n in relations
                if not c and o in accepted_on_record and (j := joined(k, o))
            ]
            loose = (
                f"; your tree holds the {', '.join(dict.fromkeys(loose))} only on statements neither accepted nor the file's own claim (a sibling placement, a page anyone can edit, an indexer's grouping, this record's own)"
                if loose
                else ""
            )
            if any(c and o in accepted_on_record for k, o, c, n in relations):
                return False, "the name is not accepted yet, and the record's relationship to the person accepted on it is its indexer's, not the record's own statement" + loose, []
            return False, (
                "the name is not accepted yet"
                if cat.basis("person", pid) != "accepted"
                else "the accepted name rests on no trusted source and not on your own word"
            ) + loose, []
        if any(d.field == "birth date" for d in disagree):
            return (
                False,
                "the name is not accepted yet, and the birth year disagrees with the claimed relative's record",
                []
            )
        if unplaced:
            return True, f"a stated sibling: sibling {unplaced[1]}, already accepted on this record, and your tree holds no parents for {cand['name']}, so nothing contradicts it; the name and birth year agree, so the record's own name fact documents it, and they are placed beside {unplaced[1]} as a child of the same parents, undecided, where the tree holds those" + claim_note, []
        group, other_cand, other_name = rel
        return True, f"a claimed relationship: {REL_OF[group]} {other_name}, already accepted on this record, and your tree already links them so, claimed or accepted; the name and birth year agree, so the record's own name fact documents it" + claim_note, []
    # points: (words, how many it counts); left: what agrees and earns nothing, said in the reason
    points, rel_points, left = [], [], []
    # one record is one source wherever it is held, and the same person's record of one event counts once
    one_source = lambda what, shared: left.append(
        f"{what}, which the tree holds only from {' and '.join(dict.fromkeys(shared))}"
    )
    # a date stands on an accepted statement that gives it, whatever the event shows beside it
    for t, et in (("birth", "Birth"), ("death", "Death")):
        if not (persona[t]["start"] or persona[t]["end"]) or not cand["events"].get(et):
            continue
        gs, shared = ground(
            cx, tree_id, "event", [cand["events"][et]], sha, rec, axis="date", value=persona[t], without=without
        )
        if not gs:
            if shared:
                one_source(f"the {t} date", shared)
            continue
        day = [g for g in gs if g["day"]]
        points.append((f"{t} date to the day ({_on(day)})", 2) if day else (f"{t} date", 1))
    # a place stands on an accepted statement giving the place the event shows, whole
    for label, et in (("death place", "Death"), ("burial place", "Burial")):
        found = next((a for a in agree if a.field == label), None)
        if not found or not cand["events"].get(et):
            continue
        if found.coarser is not None:
            left.append(
                f"the {label}, which the record gives only as {found.coarser}, coarser than the tree's {cand[label]}"
            )
            continue
        gs, shared = ground(
            cx,
            tree_id,
            "event",
            [cand["events"][et]],
            sha,
            rec,
            axis="place",
            value=persona[label],
            tree=cand[label],
            without=without
        )
        if gs:
            points.append((label, 1))
        elif shared:
            one_source(f"the {label}", shared)
    # a relative counts once, however many rows of the record relate the two: the stated row before one the indexer computed
    named, bare = set(), []
    for kind, other_pid, computed, other_name in relations:
        j = joined(kind, other_pid)
        if not j or j[1]["id"] in named:
            continue
        # the relative's own persona stands for them on nothing but this relationship: no point
        if not grounded(other_pid):
            bare.append(other_name)
            continue
        group, oc = j
        named.add(oc["id"])
        role = "child" if group in ("parents", "siblings") else "partner"
        other_role = "child" if group in ("children", "siblings") else "partner"
        # the membership that joins these two, read from either side: the child's under the parent, a partner's beside the other, a sibling's child row beside the other's
        rows = [
            dumps([fid, who, r])
            for fid, in q.execute(
                """SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role=?
                                                                WHERE fm.person_id=? AND fm.role=?""",
                (oc["id"], other_role, pid, role)
            )
            for who, r in ((pid, role), (oc["id"], other_role))
        ]
        gs, shared = ground(cx, tree_id, "family_member", rows, sha, rec, without=without)
        pt = f"{REL_OF[group]} {other_name}"
        # the file's own claim of the link, read where nothing grounds it
        claimed = lambda: claimed_or_accepted(cx, tree_id, pid, oc["id"], group, rec, keys, without, claim_only=True)
        if computed and (gs or claimed()):
            points.append(
                (
                    f"{pt}, once (the record's indexer, not the record, states it" + (
                        "" if gs else "; a link the file claims"
                    ) + ")",
                    1
                )
            )
        elif gs and not computed:
            rel_points.append(pt)  # a survivor the tree holds on trusted evidence: an obituary's ground
            points.append((f"{pt} ({_on(gs)})", 2))
        elif shared:
            one_source(f"the {pt}", shared)
        # grounded above: a link the file claims counts once, never double, and is no obituary's ground
        elif not computed and claimed():
            points.append(
                (f"{pt} (a link the file claims, the relative's own persona here fitting on more than a name)", 1)
            )
        else:
            left.append(f"the {pt}, a link the tree holds neither on trusted ground nor as the file's own claim")
    bare_note = (
        (
            "; the relationship the record gives to "
            + ", ".join(dict.fromkeys(bare))
            + " is no point: the record gives nothing of them but the name and the relationship itself, and they are not accepted on it"
        )
        if bare
        else ""
    )
    left_note = ("; no point for " + "; ".join(left)) if left else ""
    if sum(n for _, n in points) < 2:
        return False, "agrees with the accepted name" + (
            f" and {points[0][0]}" if points else ""
        ) + " only, counting facts from trusted sources; two are needed" + bare_note + left_note, []
    if survivors_kind and not rel_points:
        return False, "an obituary or newspaper text is ground only through who it names: " + (
            ", ".join(w for w, _ in points) or "the name"
        ) + " agree, but none of the accepted relatives is among the survivors it names" + bare_note + left_note, []
    return True, "agrees with your accepted name, " + " and ".join(
        w for w, _ in points
    ) + " from trusted sources; nothing disagrees against an accepted value" + claim_note + left_note, []

def rule_creates(cx, prop, persona, x, identity, survivors_kind, accepted_on_record):
    """Whether the rule creates the person a new_person card proposes, and why, in words (docs/RESEARCH-WORKFLOW.md §5–7): a
    trusted record (T1–T2, or an obituary once read) names them, with a name, in a stated family relationship (child, parent,
    spouse, sibling, half sibling, grandchild, in-law; never "other relative" or a blank; one the record's indexer computed is
    no statement of the record's, catalog.relation_classes) to a person accepted on the same record, and nobody in the tree
    fits after the fitting check — the matcher's own word, so a card an older matcher wrote is left for reconsider to propose
    again (rematch), and the check run once more across the whole tree as it stands when the rule decides (identity_refused). A page
    anyone can edit names a person but never creates one: the owner does. A creation is judged on the persona its record's
    current reading gives the entry (rule_points), and a card the creation stands for (made_here) on the same terms: the
    matcher has put that persona to the person, so its word is not asked again, and the creation stands on the entry."""
    q = _q(cx)
    made = json.loads(prop["payload_json"]).get("made")
    if identity:
        return False, "a page anyone can edit names a person but never creates one: the owner decides"
    tier = str(x["trust_tier"] or "")[:2]
    if tier not in ("T1", "T2") and not (survivors_kind and tier == "T3"):
        return False, f"a {tier or 'untiered'} record creates nobody: only a T1 or T2 record, or an obituary once read, and the owner otherwise"
    given, rest = split_persona_name(persona["name"])
    if not given or not rest or persona["name"] == "(unnamed)":
        return False, "the record gives no full name to create a person under"
    if prop["status"] == "undecided" and not made:
        v = q.execute("SELECT version FROM extractor WHERE id=?", (prop["generated_by"],)).fetchone()
        if not v or v["version"] != MATCHER[2]:
            return False, f"the matcher at {v['version'] if v else '?'} found nobody fitting; the matcher now at {MATCHER[2]} has not looked: reconsider proposes it again"
    # own: the persona is the <kind> of the other; else the other is the persona's
    stated = [
        (
            r["kind"],
            r["value_text"],
            r["persona_id"] if r["persona_id"] != persona["id"] else r["related_persona_id"],
            relation_classes(
                cx, r["persona_id"], r["related_persona_id"], r["kind"], r["value_text"]
            )["relationship"] == "computed",
            r["persona_id"] == persona["id"]
        )
        for r in q.execute(
            "SELECT kind, value_text, persona_id, related_persona_id FROM persona_relation WHERE persona_id=? OR related_persona_id=?",
            (persona["id"], persona["id"])
        )
    ]
    def resolves(word, other):
        in_law = IN_LAW.get((word or "").strip().lower())
        # a half sibling, a grandchild: not an in-law, no link to resolve first
        if not in_law:
            return True
        x_surname = (split_persona_name(persona["name"])[1] or [""])[-1]
        return bool(resolve_in_law(cx, prop["tree_id"], accepted_on_record[other]["id"], in_law, x_surname))
    family = [
        (kind, word, other, computed, own)
        for kind, word, other, computed, own in stated
        if other in accepted_on_record
            and (
                kind in ("child", "parent", "spouse", "sibling")
                or (kind == "other" and FAMILY_WORD.search(word or "") and resolves(word, other))
            )
    ]
    named = [(kind, word, other, own) for kind, word, other, computed, own in family if not computed]
    if not named:
        others = [word or kind for kind, word, other, _, _ in stated if other in accepted_on_record]
        return (
            False,
            (
                "the record's indexer, not the record, relates them to a person accepted on it ("
                + ", ".join(word or kind for kind, word, _, _, _ in family)
                + "): the owner decides"
            )
                if family
                else (
                    "the record relates them to a person accepted on it only as "
                    + ", ".join(others)
                    + ": not a family relationship the rule creates a person on, or an in-law tie that does not resolve to one person"
                )
                if others
                else "the record states no family relationship between them and a person accepted on it"
        )
    kind, word, other, own = named[0]
    tie = (
        f"{word or kind} of {accepted_on_record[other]['name']}, accepted on this record"
        if own
        else f"the record names {accepted_on_record[other]['name']}, accepted on it, as their {(word or kind).lower()}"
    )
    return (
        True,
        f"{tie}, and nobody else in the tree fits them after the fitting check: the creation stands on this entry"
            if made
            else f"{tie}, and nobody in the tree fits them after the fitting check: created as a person with the record's facts"
    )

def accepted_span(cx, tree_id, pid, etype, without=()):
    """What the person's accepted statements of an event type a life holds once say of its date: (earliest, latest, words),
    the earliest day any of them can stand for and the latest (catalog.date_span; None on a side one of them leaves open),
    and the dates as written; None when none is accepted or none gives a date. A statement with no record fact of its own
    (the owner's word) stands for the event's own date. without: proposal ids whose statements do not count, and statements
    that do not (reconsider, unless)."""
    skip, skipped = unless(without)
    spans, words = [], []
    for r in _q(cx).execute(f"""SELECT a.persona_fact_id, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, e.date_text AS ev_text, e.date_start AS ev_start, e.date_end AS ev_end, e.date_qualifier AS ev_q
                                FROM assertion a JOIN event e ON e.id=a.subject_id JOIN event_participant ep ON ep.event_id=e.id LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                WHERE a.tree_id=? AND a.subject_kind='event' AND a.status='accepted' AND ep.person_id=? AND e.event_type=? {skip} ORDER BY a.asserted_at, a.id""", (tree_id, pid, etype, *skipped)):
        own = r["persona_fact_id"] is None
        sp = (
            date_span(r["ev_start"], r["ev_end"], r["ev_q"])
            if own
            else date_span(r["date_start"], r["date_end"], r["date_qualifier"])
        )
        if sp:
            spans.append(sp)
            words.append(r["ev_text" if own else "date_text"] or "")
    if not spans:
        return None
    return (
        None if any(s[0] is None for s in spans) else min(s[0] for s in spans),
        None if any(s[1] is None for s in spans) else max(s[1] for s in spans),
        " and ".join(dict.fromkeys(w for w in words if w))
    )

def record_span(cx, persona_id, etype):
    """What a persona's own record says of an event type's date: (earliest, latest, words), or None."""
    r = _q(cx).execute(
        "SELECT date_text, date_start, date_end, date_qualifier FROM persona_fact WHERE persona_id=? AND fact_type=? AND coalesce(date_start, date_end) IS NOT NULL ORDER BY rowid",
        (persona_id, etype)
    ).fetchone()
    sp = date_span(r["date_start"], r["date_end"], r["date_qualifier"]) if r else None
    return (*sp, r["date_text"] or r["date_start"] or r["date_end"]) if sp else None

def fits_as_well(cat, persona, cand_id, chosen, exclude):
    """The persons of the tree (never one merged into another, none in exclude) other than the candidate who fit the persona
    on as much as the candidate does or more (match.compare: given names and surnames with their spelling variants and short
    forms, dates, places, the relationships the record states to personas already accepted on it), or, with no candidate,
    who fit it at all: [(person id, name, what agrees)]. compare's fit needs the given name to agree, or the same memorial
    accepted as them, so only those persons are compared."""
    from match import by_memorial, name_keys, same_given
    names = [split_persona_name(n) for n in (persona.get("names") or [persona["name"]])]
    givens = [g for g, _ in names if g]
    mine = len(compare(cat, persona, candidate(cat, cand_id), chosen)[1]) if cand_id else 0
    same_memorial = set(by_memorial(cat.cx, cat.tree_id, persona["memorial"])) if persona.get("memorial") else set()
    out = []
    for pid, name in cat.q(
        "SELECT id, display_name FROM person WHERE tree_id=? AND merged_into IS NULL ORDER BY created_at, id",
        cat.tree_id
    ):
        if pid == cand_id or pid in exclude:
            continue
        if pid not in same_memorial and not any(same_given(g, k) for g in givens for k, _ in name_keys(cat, pid)):
            continue
        fits, agree, _, _, _ = compare(cat, persona, candidate(cat, pid), chosen)
        if fits and len(agree) >= mine:
            out.append((pid, name, agree))
    return out

def outside_life(cx, tree_id, persona, pid, accepted_on_record, without=()):
    """Why what the record would add falls outside a life as accepted (data/life-limits.csv), or None: a dated fact of the
    persona's after the person's accepted death (a type a life holds after its end excepted: catalog.life_limits'
    after_death_types) or before the accepted birth (a birth fact excepted), or a parent-child relationship the record states
    to a persona accepted on it that breaks the limits of one life (catalog.parent_limit), each side's dates the person's
    accepted ones, else what the record itself says of them. pid None: a person the record would create, whose life is the
    record's alone."""
    L = life_limits()
    q = _q(cx)
    birth = accepted_span(cx, tree_id, pid, "Birth", without) if pid else None
    death = accepted_span(cx, tree_id, pid, "Death", without) if pid else None
    for f in q.execute(f"""SELECT fact_type, date_text, date_start, date_end, date_qualifier FROM persona_fact WHERE persona_id=? AND coalesce(date_start, date_end) IS NOT NULL
                           AND fact_type NOT IN ('Name','Sex',{','.join('?' * len(RECORD_FACTS))}) ORDER BY rowid""", (persona["id"], *RECORD_FACTS)).fetchall():
        sp = date_span(f["date_start"], f["date_end"], f["date_qualifier"])
        if not sp:
            continue
        said = f"{f['fact_type'].lower()} {f['date_text'] or f['date_start'] or f['date_end']}"
        if death and death[1] and sp[0] and f["fact_type"] not in L["after_death_types"] and sp[0] > death[1]:
            return f"the record dates {said}, after the accepted death ({death[2]}): a statement beyond the limits of one life"
        if birth and birth[0] and sp[1] and f["fact_type"] != "Birth" and sp[1] < birth[0]:
            return f"the record dates {said}, before the accepted birth ({birth[2]}): a statement beyond the limits of one life"
    def life(person_id, persona_id, etype):
        return (
            (accepted_span(cx, tree_id, person_id, etype, without) if person_id else None)
            or record_span(cx, persona_id, etype)
        )
    def sex(person_id, persona_id):
        r = q.execute("SELECT sex FROM person WHERE id=?", (person_id,)).fetchone() if person_id else None
        return (
            (r["sex"] if r and r["sex"] in ("M", "F") else None)
            or (q.execute("SELECT sex FROM persona WHERE id=?", (persona_id,)).fetchone() or {"sex": None})["sex"]
        )
    rels = [
        (r["kind"], r["related_persona_id"])
        for r in q.execute(
            "SELECT kind, related_persona_id FROM persona_relation WHERE persona_id=? AND kind IN ('child','parent')",
            (persona["id"],)
        )
    ] + [
        ({"child": "parent", "parent": "child"}[r["kind"]], r["persona_id"])
        for r in q.execute(
            "SELECT kind, persona_id FROM persona_relation WHERE related_persona_id=? AND kind IN ('child','parent')",
            (persona["id"],)
        )
    ]
    name = (
        lambda person_id, persona_id: (
            q.execute("SELECT display_name FROM person WHERE id=?", (person_id,)).fetchone() or {"display_name": None}
        )["display_name"]
        or q.execute("SELECT name_text FROM persona WHERE id=?", (persona_id,)).fetchone()["name_text"]
    )
    span = lambda person_id, persona_id, etype: (lambda s: s[:2] if s else None)(life(person_id, persona_id, etype))
    for kind, other in rels:
        if other not in accepted_on_record:
            continue
        o = accepted_on_record[other]
        (par, par_pe), (ch, ch_pe) = ((o, other), (pid, persona["id"])) if kind == "child" else (
            (pid, persona["id"]), (o, other)
        )
        hit = parent_limit(
            sex(par, par_pe), span(par, par_pe, "Birth"), span(par, par_pe, "Death"), span(ch, ch_pe, "Birth")
        )
        if hit:
            on, words = hit
            d = life(par, par_pe, "Birth" if on == "birth" else "Death")
            b = life(ch, ch_pe, "Birth")
            return (
                f"the record makes {name(ch, ch_pe)}, born {b[2]}, a child of {name(par, par_pe)}, {'born' if on == 'birth' else 'who died'} {d[2]}: {words}, "
                "beyond the limits of one life"
            )
    return None

def identity_refused(cx, tree_id, prop, without=()):
    """Why the rule may not take a record it would take on its points, or None: identity tested, not assumed
    (docs/DATA-ARCHITECTURE.md §7 decision 12, docs/RESEARCH-WORKFLOW.md §5–7). Three tests, each a refusal naming what it
    found: another person of the tree fits the persona as well as the candidate or better (fits_as_well; for a person the
    rule would create, anyone who fits, or whom the fitting check reaches, match.by_name_and_year); the person already holds
    another persona on this reading of the record (two rows of one page are two people); something the record would add
    falls outside the person's life as accepted (outside_life). The persona tested is the one of the same entry on the
    record's current reading (catalog.current_entry), with the facts and relationships that reading gives, as rule_points
    judges it. A person created by a decision under reconsideration (without) or by this one is no other person, nor is
    one accepted as another persona on this reading. without: proposal ids whose assertions and links do not count
    (reconsider)."""
    from match import by_name_and_year
    q = _q(cx)
    pay = json.loads(prop["payload_json"])
    cat = Catalog(cx, tree_id)
    ext = pay["extraction_id"]
    while (later := q.execute("SELECT superseded_by FROM extraction WHERE id=?", (ext,)).fetchone()["superseded_by"]):
        ext = later
    cur = current_entry(cx, pay["persona_id"])
    reading, persona_id = (ext, cur) if cur else (pay["extraction_id"], pay["persona_id"])
    persona = next((p for p in personas_of(cx, reading) if p["id"] == persona_id), None)
    if not persona:
        return None
    pid = pay.get("person_id") if prop["kind"] == "persona_match" else None
    skip = f"AND coalesce(pp.proposal_id,'') NOT IN ({','.join('?' * len(without))})" if without else ""
    accepted_on_record = {r["persona_id"]: r["person_id"] for r in q.execute(f"""SELECT pp.persona_id, pp.person_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                          JOIN person o ON o.id=pp.person_id WHERE pe.extraction_id=? AND pp.status='accepted' AND o.tree_id=? AND pp.persona_id<>? {skip}""", (reading, tree_id, persona["id"], *without))}
    marks = ",".join("?" * len(without))
    created = (
        {
            r["pid"]
            for r in q.execute(
                f"SELECT json_extract(payload_json,'$.person_id') AS pid FROM proposal WHERE kind='new_person' AND id IN ({marks})",
                without
            )
        }
        if without
        else set()
    )
    if prop["kind"] == "new_person" and pay.get("person_id"):
        created.add(pay["person_id"])
    exclude = (created | set(accepted_on_record.values())) - {pid, None}
    chosen = {o: candidate(cat, p) for o, p in accepted_on_record.items()}
    who = lambda rows: " and ".join(f"{n} [{i[-6:]}]" for i, n, _ in rows)
    on = lambda agree: ", ".join(
        dict.fromkeys("the same memorial" if a.field == "memorial" else a.field for a in agree)
    ) + " agreeing"
    others = fits_as_well(cat, persona, pid, chosen, exclude)
    if others:
        return (
            f"{who(others)} {'fits' if len(others) == 1 else 'fit'} {persona['name']} "
            + ("as well as the candidate or better" if pid else "already")
            + f" ({on(others[0][2])}): which person the record is about is yours to say"
        )
    if not pid:
        reached = [
            (i, n, a)
            for i in by_name_and_year(cat, cx, tree_id, persona)
            if i not in exclude
            for n in [cat.person(i)["name"]]
            for f, a, _, _, near in [compare(cat, persona, candidate(cat, i), chosen)]
            if f or near
        ]
        if reached:
            return f"the fitting check reaches {who(reached)} for {persona['name']} ({on(reached[0][2])}): the person may be in the tree already, which is yours to say"
    if pid:
        mine = set(same_personas(cx, persona["id"]))
        held = [r for r in q.execute(f"""SELECT pe.id, pe.name_text, pe.role_in_record FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                                          WHERE pp.person_id=? AND pp.status='accepted' AND pe.extraction_id=? {skip} ORDER BY pe.sequence""", (pid, ext, *without)) if r["id"] not in mine]
        if held:
            return (
                f"{cat.person(pid)['name']} is already accepted as {held[0]['name_text']} ({held[0]['role_in_record'] or 'no role'}) on this reading of the record: "
                "two rows of one page are two people, and which row is theirs is yours to say"
            )
    return outside_life(cx, tree_id, persona, pid, accepted_on_record, without)

def match_record(cx, eid, by, about=None):
    """The matcher on an extraction, then the standing rule on every proposal it wrote: those it takes are accepted on the
    owner's behalf, recorded as the rule. Returns (proposals written, proposals the rule accepted with the reason)."""
    q = _q(cx)
    written = match(cx, eid, by, about=about)
    taken = []
    for prop_id, kind, name, person_id in written:
        p = q.execute("SELECT * FROM proposal WHERE id=?", (prop_id,)).fetchone()
        # decided or superseded already, by what an earlier decision here brought on
        if p["status"] != "undecided":
            continue
        ok, why = rule_accepts(cx, p["tree_id"], p)
        if ok:
            decide(cx, p["tree_id"], prop_id, "accepted", f"{RULE_ACTOR[p['kind']]} for {by}", note=why)
            taken.append((prop_id, name, why))
    return written, taken

def link_on_word(cx, tree_id, pid, other, kind, sha, by, note, marriage=None):
    """The owner places a person in a family by their own word, on a record that stops short of naming both parties in full
    (an index that gives the spouse's surname by four letters): the membership is created in a family of the right shape and
    carries one Accepted assertion on the artifact, vouched, the owner's own decision on it (person_decided), with the owner's reason; a marriage the record dates becomes the
    family's Marriage event with the same assertion. kind is 'spouse' (other is the spouse) or 'child' (other is one parent
    or a list of both): the child joins the family that pairs the named parents; a parent with several families needs both
    named; a family made here for two parents asserts their partnership on the same word. Returns the family id."""
    q = _q(cx)
    ts = now()
    one = lambda sql, args: next((f for f, in q.execute(sql, args)), None)
    if kind == "spouse":
        fid = one("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                     WHERE fm.person_id=? AND fm.role='partner'""", (other, pid))
        if fid is None:
            fid = new_family(cx, tree_id, other, ts)
        rows = [(fid, pid, "partner"), (fid, other, "partner")]
    else:
        parents = list(other) if isinstance(other, (list, tuple)) else [other]
        fids = [
            f
            for f, in q.execute(
                "SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (parents[0],)
            )
            if all(
                q.execute(
                    "SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role='partner'", (f, x)
                ).fetchone()
                for x in parents[1:]
            )
        ]
        if len(fids) > 1:
            raise ValueError("the parent has more than one family: name both parents")
        fid = fids[0] if fids else new_family(cx, tree_id, parents[0], ts)
        rows = [(fid, pid, "child")] + ([(fid, x, "partner") for x in parents if x != parents[0]] if not fids else [])
    for f, who, role in rows:
        if not q.execute(
            "SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (f, who, role)
        ).fetchone():
            q.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (f, who, role))
        q.execute(
            """INSERT INTO assertion (id,tree_id,subject_kind,subject_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,person_decided,notes)
                     VALUES (?,?,'family_member',?,?,?,'accepted',?,?,TRUE,?)""",
            (
                ulid(),
                tree_id,
                dumps([f, who, role]),
                sha,
                "the owner's word on this record",
                by,
                ts,
                dumps({"vouched": True, "note": note})
            )
        )
    if marriage:
        eid = ulid()
        q.execute(
            "INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at) VALUES (?,?,'Marriage',?,?,?,?,?,?,?)",
            (
                eid,
                tree_id,
                marriage.get("date_text"),
                marriage.get("date_start"),
                marriage.get("date_end"),
                marriage.get("qualifier"),
                "gregorian",
                ts,
                ts
            )
        )
        q.execute(
            "INSERT INTO event_participant (id,event_id,family_id,role) VALUES (?,?,?,'family')", (ulid(), eid, fid)
        )
        q.execute(
            """INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,person_decided,notes)
                     VALUES (?,?,'event',?,?,?,?,'accepted',?,?,TRUE,?)""",
            (
                ulid(),
                tree_id,
                eid,
                marriage.get("persona_fact_id"),
                sha,
                marriage.get("citation") or "the record's marriage entry",
                by,
                ts,
                dumps({"vouched": True, "note": note})
            )
        )
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "accept",
            "family",
            fid,
            dumps(
                {"link": kind, "person": pid, "other": other, "record": sha, "note": note, "marriage": bool(marriage)}
            )
        )
    )
    return fid

def divorce(cx, tree_id, a, b, date_text, evidence, by, note):
    """The couple's family gets a Divorce event, dated as the records allow ("BET 1950 AND 1959"), with one Accepted assertion per
    piece of evidence the owner names: (artifact sha, persona_fact id or None, citation words), each the owner's own decision on
    it (person_decided). A divorced couple stays a family in
    the tree, so the children keep both parents; the event is what the screen shows between the two lines."""
    q = _q(cx)
    ts = now()
    fid = next((f for f, in q.execute("""SELECT fm.family_id FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=? AND x.role='partner'
                                          WHERE fm.person_id=? AND fm.role='partner'""", (b, a))), None)
    if fid is None:
        raise ValueError("no family joins these two")
    from treelib import parse_gedcom_date
    d = parse_gedcom_date(date_text) if date_text else {"date_start": None, "date_end": None, "date_qualifier": None}
    eid = ulid()
    q.execute(
        "INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at) VALUES (?,?,'Divorce',?,?,?,?,?,?,?)",
        (eid, tree_id, date_text, d["date_start"], d["date_end"], d["date_qualifier"], "gregorian", ts, ts)
    )
    q.execute("INSERT INTO event_participant (id,event_id,family_id,role) VALUES (?,?,?,'family')", (ulid(), eid, fid))
    for sha, pf, cite in evidence:
        q.execute(
            """INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,person_decided,notes)
                     VALUES (?,?,'event',?,?,?,?,'accepted',?,?,TRUE,?)""",
            (ulid(), tree_id, eid, pf, sha, cite, by, ts, dumps({"vouched": True, "note": note}))
        )
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (ulid(), tree_id, ts, by, "accept", "event", eid, dumps({"divorce": [a, b], "date": date_text, "note": note}))
    )
    return eid

def _fold_event(q, eid, into, moved):
    """An event's statements and notes moved onto another of the same owner and type, their statuses unchanged; a statement
    of a record fact the other already carries, or a second vouch, stays where it is, so nothing is stated twice on one
    event. The event itself is left as it is. Returns (the statements moved, the statements left)."""
    ev = q.execute("SELECT event_type, date_start FROM event WHERE id=?", (eid,)).fetchone()
    vouch = lambda notes: bool(notes and notes.startswith("{") and json.loads(notes).get("vouched"))
    there = q.execute(
        "SELECT persona_fact_id, notes FROM assertion WHERE subject_kind='event' AND subject_id=?", (into,)
    ).fetchall()
    facts, vouched = {r["persona_fact_id"] for r in there if r["persona_fact_id"]}, any(
        vouch(r["notes"]) for r in there
    )
    go, stay = [], []
    for a in q.execute(
        "SELECT id, persona_fact_id, notes FROM assertion WHERE subject_kind='event' AND subject_id=? ORDER BY asserted_at, id",
        (eid,)
    ).fetchall():
        (
            stay if (a["persona_fact_id"] in facts if a["persona_fact_id"] else vouched and vouch(a["notes"])) else go
        ).append(a["id"])
    for aid in go:
        q.execute("UPDATE assertion SET subject_id=? WHERE id=?", (into, aid))
    q.execute("UPDATE note SET entity_id=? WHERE entity_kind='event' AND entity_id=?", (into, eid))
    moved["events_folded"] += 1
    moved["event_assertions_folded"] += len(go)
    moved["folded_events"].append(
        {
            "event_type": ev["event_type"],
            "date_start": ev["date_start"],
            "into_event_id": into,
            "assertions": len(go),
            **({"left": stay} if stay else {})
        }
    )
    return go, stay

def owner_on_event(cx, tree_id, eid, axis):
    """How the owner has spoken on this event's own date or place, by the event itself: 'resolved' (a conflict on it the
    owner resolved), 'reopened' (a resolution of the rule's on it the owner took back), else None."""
    q = _q(cx)
    for r in q.execute("""SELECT json_extract(detail_json,'$.resolution.by') AS by FROM research_question WHERE tree_id=? AND kind='conflict' AND closed_reason='resolved'
                          AND json_valid(detail_json) AND json_extract(detail_json,'$.resolution.event')=? AND json_extract(detail_json,'$.resolution.axis')=?""", (tree_id, eid, axis)):
        if not str(r["by"] or "").startswith("rule:"):
            return "resolved"
    if q.execute("""SELECT 1 FROM audit_log WHERE tree_id=? AND entity_kind='research_question' AND actor NOT LIKE 'rule:%' AND json_valid(diff_json)
                    AND json_extract(diff_json,'$.reopened') IS NOT NULL AND json_extract(diff_json,'$.event')=? AND json_extract(diff_json,'$.axis')=?""", (tree_id, eid, axis)).fetchone():
        return "reopened"
    return None

def fold_plan(cx, tree_id, owner):
    """The folds a person's events, or a family's, call for (fold); owner is ("person", id) or ("family", id). Events of one
    type are one event when catalog.same_event says so (places agreeing or one absent, and the type held once in a life or
    the dates one), an event joining a group when it is one with every event already in it, taken in the order the kept
    event is chosen: the event whose date or place the owner has spoken on (owner_on_event), then one a standing resolution
    of the rule's names, then the most accepted statements, the most statements, the earliest. One entry per group of two
    or more: {"type", "kept": event, "folded": [events], "refused": words when more than one event of the group carries the
    owner's word, so that a fold would set one value the owner resolved aside, else None}; each event is
    Catalog.owner_events' with its place_id, its statements counted, and the axes the owner ("owner") and the rule ("rule")
    have decided on it."""
    q = _q(cx)
    cat = Catalog(cx, tree_id)
    col = "person_id" if owner[0] == "person" else "family_id"
    kinds = {}
    for etype, kind in q.execute(f"""SELECT e.event_type, et.kind FROM event e JOIN event_participant ep ON ep.event_id=e.id JOIN event_type et ON et.name=e.event_type
                                     WHERE ep.{col}=? GROUP BY e.event_type HAVING count(DISTINCT e.id)>1 ORDER BY e.event_type""", (owner[1],)).fetchall():
        kinds[etype] = kind
    out = []
    for etype, kind in kinds.items():
        evs = cat.owner_events(etype, **{owner[0]: owner[1]})
        for e in evs:
            r = q.execute("""SELECT e.place_id, (SELECT count(*) FROM assertion a WHERE a.subject_kind='event' AND a.subject_id=e.id) AS n,
                                    (SELECT count(*) FROM assertion a WHERE a.subject_kind='event' AND a.subject_id=e.id AND a.status='accepted') AS accepted FROM event e WHERE e.id=?""", (e["id"],)).fetchone()
            e.update(
                place_id=r["place_id"],
                statements=r["n"],
                accepted=r["accepted"],
                owner={ax for ax in ("date", "place") if owner_on_event(cx, tree_id, e["id"], ax)},
                rule={a for a, in q.execute("""SELECT json_extract(detail_json,'$.resolution.axis') FROM research_question WHERE tree_id=? AND kind='conflict' AND closed_reason='resolved'
                                                     AND json_valid(detail_json) AND json_extract(detail_json,'$.resolution.event')=? AND json_extract(detail_json,'$.resolution.by') LIKE 'rule:%'""", (tree_id, e["id"]))}
            )
        groups = []
        for e in sorted(evs, key=lambda e: (not e["owner"], not e["rule"], -e["accepted"], -e["statements"], e["id"])):
            g = next((g for g in groups if all(same_event(etype, kind, m, e) for m in g)), None)
            if g is None:
                groups.append([e])
            else:
                g.append(e)
        for g in groups:
            if len(g) < 2:
                continue
            spoke = [m["id"] for m in g if m["owner"]]
            out.append(
                {
                    "type": etype,
                    "kept": g[0],
                    "folded": g[1:],
                    "refused": f"the {etype.lower()} events {', '.join(spoke)} of {owner[0]} {owner[1]} each carry a date or place the owner resolved or reopened: folding them would set one of those values aside"
                        if len(spoke) > 1
                        else None
                }
            )
    return out

def accepted_dates(q, eid):
    """The dates the accepted statements on an event give, each {"start", "qualifier"}: a record fact's own date, and for the
    owner's word with no fact of its own (a vouch) the event's own date, which is what the vouch accepted."""
    ev = q.execute("SELECT date_start, date_end, date_qualifier FROM event WHERE id=?", (eid,)).fetchone()
    out = []
    for r in q.execute("""SELECT a.persona_fact_id, pf.date_start, pf.date_end, pf.date_qualifier FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id
                          WHERE a.subject_kind='event' AND a.subject_id=? AND a.status='accepted'""", (eid,)):
        src = ev if r["persona_fact_id"] is None else r
        if src["date_start"] or src["date_end"]:
            out.append(
                {
                    "start": src["date_start"] or src["date_end"],
                    "end": src["date_end"],
                    "qualifier": src["date_qualifier"]
                }
            )
    return out

def _take_lacking(q, kept, other, ts, held=()):
    """What the kept event of a fold takes from an event folded into it: a date where it has none, or one that agrees with its
    own and says more (catalog.fuller_date: 26 Jun 1901 over 1901, 24 April 1876 over CAL 1875), and a place where it has
    none, never on an axis the owner or the rule has decided on it, and never a date that a date in held disagrees with (the
    accepted statements on both events before the fold, accepted_dates: a fold never sets an accepted record's date aside
    for a claim); a date that disagrees stays the kept event's own. Returns what changed, each with its value before; kept is
    brought up to date."""
    k = q.execute(
        "SELECT date_text, date_start, date_end, date_qualifier, calendar, place_id FROM event WHERE id=?",
        (kept["id"],)
    ).fetchone()
    o = q.execute(
        "SELECT date_text, date_start, date_end, date_qualifier, calendar, place_id FROM event WHERE id=?",
        (other["id"],)
    ).fetchone()
    decided, sets = kept["owner"] | kept["rule"], {}
    taken = {"start": o["date_start"] or o["date_end"], "end": o["date_end"], "qualifier": o["date_qualifier"]}
    if "date" not in decided and not any(date_verdict(h, taken).verdict == "disagrees" for h in held) \
       and fuller_date({"start": k["date_start"], "end": k["date_end"], "qualifier": k["date_qualifier"]},
                       {"start": o["date_start"], "end": o["date_end"], "qualifier": o["date_qualifier"]}):
        sets.update({c: o[c] for c in ("date_text", "date_start", "date_end", "date_qualifier", "calendar")})
        kept.update(text=o["date_text"], start=o["date_start"], end=o["date_end"], qualifier=o["date_qualifier"])
    if "place" not in decided and not k["place_id"] and o["place_id"]:
        sets["place_id"] = o["place_id"]
        kept["place_id"] = o["place_id"]
    if not sets:
        return {}
    q.execute(
        f"UPDATE event SET {', '.join(f'{c}=?' for c in sets)}, updated_at=? WHERE id=?",
        (*sets.values(), ts, kept["id"])
    )
    return {c: {"was": k[c], "now": v} for c, v in sets.items()}

def fold(cx, tree_id, owner, actor=None, retire=None, moved=None):
    """A person's events, or a family's, of one type that are one event folded into one (docs/RESEARCH-WORKFLOW.md §5–7, one
    statement, one event; the groups and the kept event as fold_plan gives them), the same fold a merge makes of a
    duplicate's events: each folded event's statements and notes move onto the kept event as they are (_fold_event), the
    kept event takes what it lacks from it (_take_lacking), and the folded event leaves the owner's events (retire(event id),
    by default its participant row removed: the event row and anything left on it stay for the audit trail). A date the
    events give apart, on a type a life holds once, stays the kept event's own and the folded one's statements give the
    other, so the difference is the conflict question Catalog.disagreements raises. A group fold_plan refuses is left as it
    is and named in moved's folds_refused. actor: one audit row per event folded, naming what moved, under that actor.
    Returns one entry per event folded: the owner, the type, the kept and folded events' ids and values, the statements
    moved and left, and what the kept event took."""
    q = _q(cx)
    ts = now()
    moved = moved if moved is not None else {"events_folded": 0, "event_assertions_folded": 0, "folded_events": []}
    col = "person_id" if owner[0] == "person" else "family_id"
    done = []
    for g in fold_plan(cx, tree_id, owner):
        if g["refused"]:
            moved.setdefault("folds_refused", []).append(g["refused"])
            continue
        kept = g["kept"]
        for m in g["folded"]:
            was = {"date": kept["text"], "place_id": kept["place_id"]}
            held = accepted_dates(q, kept["id"]) + accepted_dates(q, m["id"])
            go, stay = _fold_event(q, m["id"], kept["id"], moved)
            took = _take_lacking(q, kept, m, ts, held)
            if retire:
                retire(m["id"])
            else:
                q.execute(f"DELETE FROM event_participant WHERE event_id=? AND {col}=?", (m["id"], owner[1]))
            row = {
                owner[0]: owner[1],
                "type": g["type"],
                "kept": {"event": kept["id"], "date": was["date"], "place_id": was["place_id"]},
                "folded": {"event": m["id"], "date": m["text"], "place_id": m["place_id"]},
                "moved": go,
                "left": stay,
                "took": took
            }
            if actor:
                q.execute(
                    "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                    (ulid(), tree_id, ts, actor, "update", "event", m["id"], dumps({"folded_into": kept["id"], **row}))
                )
            done.append(row)
    return done

def _fold_family(q, fid, other, moved):
    """A family whose partners are exactly another's, folded into that one: each child's membership moves there, or, the
    child already being the other family's, joins it, the statements moving with it either way; the family's own events
    move; the partner memberships' statements fold onto the other family's own and the partner rows go, so the family row
    is left emptied for the audit trail."""
    for cid, in q.execute("SELECT person_id FROM family_member WHERE family_id=? AND role='child'", (fid,)).fetchall():
        if q.execute(
            "SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role='child'", (other, cid)
        ).fetchone():
            q.execute("DELETE FROM family_member WHERE family_id=? AND person_id=? AND role='child'", (fid, cid))
        else:
            q.execute(
                "UPDATE family_member SET family_id=? WHERE family_id=? AND person_id=? AND role='child'",
                (other, fid, cid)
            )
        q.execute(
            "UPDATE assertion SET subject_id=? WHERE subject_kind='family_member' AND subject_id=?",
            (dumps([other, cid, "child"]), dumps([fid, cid, "child"]))
        )
        moved["family_children_moved"] += 1
    moved["family_events_moved"] += q.execute(
        "UPDATE event_participant SET family_id=? WHERE family_id=?", (other, fid)
    ).rowcount
    for pid_, in q.execute(
        "SELECT person_id FROM family_member WHERE family_id=? AND role='partner'", (fid,)
    ).fetchall():
        q.execute(
            "UPDATE assertion SET subject_id=? WHERE subject_kind='family_member' AND subject_id=?",
            (dumps([other, pid_, "partner"]), dumps([fid, pid_, "partner"]))
        )
    q.execute("DELETE FROM family_member WHERE family_id=? AND role='partner'", (fid,))
    moved["families_folded"] += 1
    moved["folded_families"].append({"family_id": fid, "into_family_id": other})

def _partner_families(q, pid):
    """The families a person is a partner in, each with its set of partners."""
    return [
        (
            fid,
            {
                r[0]
                for r in q.execute(
                    "SELECT person_id FROM family_member WHERE family_id=? AND role='partner'", (fid,)
                ).fetchall()
            }
        )
        for fid, in q.execute(
            "SELECT DISTINCT family_id FROM family_member WHERE person_id=? AND role='partner' ORDER BY family_id",
            (pid,)
        ).fetchall()
    ]

def _back_to(q, dup_id, kept_id):
    """A merge's retire for fold: the folded event's participant returned to the duplicate's row, out of the kept person's
    events, as a merge leaves the duplicate's own."""
    return lambda eid: q.execute(
        "UPDATE event_participant SET person_id=? WHERE event_id=? AND person_id=?", (dup_id, eid, kept_id)
    )

def complete_merge(cx, tree_id, dup_id, kept_id, by, note):
    """A merge made before a merge folded events and same-partner families, completed: the kept person's events folded as a
    merge folds them (fold), each folded event's participant returned to the duplicate's row (_back_to); the kept person's
    partner families with the same partners folded into the earliest (_fold_family), and that family's events folded the
    same way. Nothing else moves, and a merge already complete folds nothing. One audit row. Returns what folded."""
    q = _q(cx)
    ts = now()
    moved = {
        "events_folded": 0,
        "event_assertions_folded": 0,
        "families_folded": 0,
        "family_children_moved": 0,
        "family_events_moved": 0,
        "folded_events": [],
        "folded_families": []
    }
    fold(cx, tree_id, ("person", kept_id), retire=_back_to(q, dup_id, kept_id), moved=moved)
    fams = _partner_families(q, kept_id)
    for i, (fid, partners) in enumerate(fams):
        into = next(
            (
                f
                for f, ps in fams[:i]
                if ps == partners
                    and q.execute("SELECT 1 FROM family_member WHERE family_id=? AND role='partner'", (f,)).fetchone()
            ),
            None
        )
        if into:
            _fold_family(q, fid, into, moved)
            fold(cx, tree_id, ("family", into), moved=moved)
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "update",
            "person",
            dup_id,
            dumps({"merge_completed": kept_id, "note": note, **moved})
        )
    )
    return {"duplicate": dup_id, "kept": kept_id, "completed": True, **moved}

def merge(cx, tree_id, dup_id, kept_id, by, note):
    """Close a duplicate_person question (RESEARCH-WORKFLOW §2; the worked example's "merging the two Thomas entries closes
    the question"): the duplicate's persona links, assertions, event and family memberships, plan steps, search log rows and
    open questions move onto the person it duplicates, `person.merged_into` is set so the duplicate's own row stays for the
    audit trail but out of every listing, overview, plan and matcher run, and one `duplicate_person` proposal records the
    decision with the owner's note; the duplicate_person question between the two, on either side, closes answered by it. A
    moved step the kept person's plan already has by step_key keeps whichever of the two carries search_log runs (neither carrying runs keeps the kept person's own); the duplicate's runs, if any, are carried
    onto the survivor rather than lost, each a new row restating it (log_search.restate), the duplicate's step left on its row,
    skipped, holding the runs it superseded. A dropped step or question is named in the audit row by its key, row (a step's) and
    rationale, and why it was dropped, the way plan.py's own audit row names what it drops.

    The duplicate's events join the kept person's, and the kept person's events of one type that are then one event are
    folded (fold, docs/RESEARCH-WORKFLOW.md §5–7: places agreeing or one absent, and the type held once in a life or the
    dates one): the statements move onto the kept event, and each folded event and its participant are left on the
    duplicate's row (_back_to), so the kept person never carries two Birth or two Death events; a date the two give apart is
    the conflict question the catalog raises. A duplicate's own family, once its membership has moved, whose partners are
    then exactly the kept person's own family's partners is folded the same way: its children's memberships and its own
    events move to that family, its partner memberships and their assertions fold onto the kept family's own, the family's
    events that are then one event fold too, and the duplicate's family row is left emptied, with the duplicate, for the
    audit trail (a child of both joins the kept family's own membership). A pair already merged is completed instead
    (complete_merge). Returns what moved."""
    q = _q(cx)
    dup = q.execute("SELECT tree_id, merged_into, display_name FROM person WHERE id=?", (dup_id,)).fetchone()
    kept = q.execute("SELECT tree_id, merged_into, display_name FROM person WHERE id=?", (kept_id,)).fetchone()
    if not dup or not kept:
        raise ValueError("no such person in this tree")
    if dup["tree_id"] != tree_id or kept["tree_id"] != tree_id:
        raise ValueError("both persons must be in this tree")
    if dup_id == kept_id:
        raise ValueError("a person cannot be merged into themself")
    if dup["merged_into"] == kept_id:
        return complete_merge(cx, tree_id, dup_id, kept_id, by, note)
    if dup["merged_into"]:
        raise ValueError(f"{dup['display_name']} is already merged into another person")
    if kept["merged_into"]:
        raise ValueError(f"{kept['display_name']} is itself merged into another person")
    ts = now()
    # each drop or fold named by its key/type/family, the way plan.py's own audit row does: the audit row is the only trace of it afterwards
    moved = {
        "persona_links": 0,
        "assertions": 0,
        "event_participants": 0,
        "events_folded": 0,
        "event_assertions_folded": 0,
        "family_memberships": 0,
        "families_folded": 0,
        "family_children_moved": 0,
        "family_events_moved": 0,
        "plan_steps_moved": 0,
        "plan_steps_dropped": 0,
        "log_rows_carried": 0,
        "questions_moved": 0,
        "questions_dropped": 0,
        "questions_answered": 0,
        "dropped_steps": [],
        "dropped_questions": [],
        "folded_events": [],
        "folded_families": []
    }

    for persona_id, in q.execute("SELECT persona_id FROM person_persona WHERE person_id=?", (dup_id,)).fetchall():
        if q.execute(
            "SELECT 1 FROM person_persona WHERE person_id=? AND persona_id=?", (kept_id, persona_id)
        ).fetchone():
            continue
        q.execute(
            "UPDATE person_persona SET person_id=? WHERE person_id=? AND persona_id=?", (kept_id, dup_id, persona_id)
        )
        moved["persona_links"] += 1

    for ep_id, eid, role, fam in q.execute(
        "SELECT id, event_id, role, family_id FROM event_participant WHERE person_id=?", (dup_id,)
    ).fetchall():
        if q.execute(
            "SELECT 1 FROM event_participant WHERE event_id=? AND role=? AND person_id=? AND family_id IS ?",
            (eid, role, kept_id, fam)
        ).fetchone():
            continue
        q.execute("UPDATE event_participant SET person_id=? WHERE id=?", (kept_id, ep_id))
        moved["event_participants"] += 1
    fold(cx, tree_id, ("person", kept_id), retire=_back_to(q, dup_id, kept_id), moved=moved)

    partner_fams = set()
    for fid, role in q.execute("SELECT family_id, role FROM family_member WHERE person_id=?", (dup_id,)).fetchall():
        if q.execute(
            "SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, kept_id, role)
        ).fetchone():
            continue
        q.execute(
            "UPDATE family_member SET person_id=? WHERE family_id=? AND person_id=? AND role=?",
            (kept_id, fid, dup_id, role)
        )
        q.execute(
            "UPDATE assertion SET subject_id=? WHERE subject_kind='family_member' AND subject_id=?",
            (dumps([fid, kept_id, role]), dumps([fid, dup_id, role]))
        )
        moved["family_memberships"] += 1
        if role == "partner":
            partner_fams.add(fid)

    for fid in partner_fams:
        partners = {
            r[0]
            for r in q.execute(
                "SELECT person_id FROM family_member WHERE family_id=? AND role='partner'", (fid,)
            ).fetchall()
        }
        if kept_id not in partners:
            continue
        other = next((f for f, ps in _partner_families(q, kept_id) if f != fid and ps == partners), None)
        if other:
            _fold_family(q, fid, other, moved)
            fold(cx, tree_id, ("family", other), moved=moved)

    moved["assertions"] = q.execute(
        "UPDATE assertion SET subject_id=? WHERE subject_kind='person' AND subject_id=?", (kept_id, dup_id)
    ).rowcount

    for step in q.execute("SELECT * FROM search_plan WHERE person_id=?", (dup_id,)).fetchall():
        existing = q.execute(
            "SELECT id FROM search_plan WHERE person_id=? AND step_key=?", (kept_id, step["step_key"])
        ).fetchone()
        if not existing:
            q.execute("UPDATE search_plan SET person_id=? WHERE id=?", (kept_id, step["id"]))
            moved["plan_steps_moved"] += 1
            continue
        dup_has_runs = q.execute("SELECT 1 FROM search_log WHERE plan_step_id=?", (step["id"],)).fetchone()
        kept_has_runs = q.execute("SELECT 1 FROM search_log WHERE plan_step_id=?", (existing["id"],)).fetchone()
        if dup_has_runs and not kept_has_runs:
            q.execute("DELETE FROM search_plan WHERE id=?", (existing["id"],))
            q.execute("UPDATE search_plan SET person_id=? WHERE id=?", (kept_id, step["id"]))
            moved["plan_steps_moved"] += 1
        else:
            runs = [
                lid
                for lid, in q.execute(
                    "SELECT id FROM search_log WHERE plan_step_id=? AND superseded_by IS NULL ORDER BY id",
                    (step["id"],)
                ).fetchall()
            ]
            for lid in runs:
                restate(cx, by, lid, step_id=existing["id"])
            moved["log_rows_carried"] += len(runs)
            # its rows stay on it, each superseded by its restatement on the kept step
            if runs:
                q.execute("UPDATE search_plan SET status='skipped' WHERE id=?", (step["id"],))
            else:
                q.execute("DELETE FROM search_plan WHERE id=?", (step["id"],))
            moved["plan_steps_dropped"] += 1
            moved["dropped_steps"].append(
                {
                    "step_key": step["step_key"],
                    "row_key": step["row_key"],
                    "rationale": step["rationale"],
                    "reason": "the kept person's own step of this key carries search_log runs already"
                        if kept_has_runs
                        else "the kept person's own step of this key is kept; neither carries a search_log run"
                }
            )

    prop_id = ulid()
    for qid, in q.execute(
        """SELECT id FROM research_question WHERE status='open' AND kind='duplicate_person'
                             AND ((subject_person_id=? AND q_key=?) OR (subject_person_id=? AND q_key=?))""",
        (dup_id, f"duplicate_person:{kept_id}", kept_id, f"duplicate_person:{dup_id}")
    ).fetchall():
        q.execute(
            "UPDATE research_question SET status='closed', closed_reason='answered', closed_at=?, answered_by_proposal_id=? WHERE id=?",
            (ts, prop_id, qid)
        )
        # the duplicate question between the two, either side's, is the one the merge answers
        moved["questions_answered"] += 1
    for question in q.execute("SELECT * FROM research_question WHERE subject_person_id=?", (dup_id,)).fetchall():
        # answered above, or closed already: never a question of the kept person about themselves
        if question["kind"] == "duplicate_person" and question["q_key"] == f"duplicate_person:{kept_id}":
            continue
        if q.execute(
            "SELECT 1 FROM research_question WHERE subject_person_id=? AND q_key=?", (kept_id, question["q_key"])
        ).fetchone():
            moved["questions_dropped"] += 1
            moved["dropped_questions"].append({"q_key": question["q_key"], "kind": question["kind"],
                                               "reason": "the kept person already has an open question of this key"})
            continue
        q.execute("UPDATE research_question SET subject_person_id=? WHERE id=?", (kept_id, question["id"]))
        moved["questions_moved"] += 1

    q.execute("UPDATE person SET merged_into=?, updated_at=? WHERE id=?", (kept_id, ts, dup_id))
    human = q.execute("SELECT id FROM extractor WHERE kind='human' AND name='manual'").fetchone()[0]
    q.execute(
        """INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status,decided_by,decided_at,decision_note)
                 VALUES (?,?,?,?,?,?,?,'accepted',?,?,?)""",
        (
            prop_id,
            tree_id,
            "duplicate_person",
            dumps({"duplicate_person_id": dup_id, "kept_person_id": kept_id, "moved": moved}),
            note,
            human,
            ts,
            by,
            ts,
            note
        )
    )
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "update",
            "person",
            dup_id,
            dumps({"merged_into": kept_id, "proposal": prop_id, "note": note, **moved})
        )
    )
    return {"proposal": prop_id, "duplicate": dup_id, "kept": kept_id, **moved}

# a conflict line's own opening: the event type, lowercased, and the axis (Catalog.disagreements)
CONFLICT_AXIS = re.compile(r"^(.+?) (date|place): ")

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
    q = _q(cx)
    ts = now()
    cat = Catalog(cx, tree_id)
    if not (note or "").strip():
        return {"error": "a resolution needs your written reason (--note)"}
    rq = q.execute("SELECT * FROM research_question WHERE id=? AND tree_id=?", (qid, tree_id)).fetchone()
    rule_res = rule_resolution(rq)
    if rule_res and not by.startswith("rule:"):                        # the owner's own resolution over the rule's
        cx.execute("SAVEPOINT owner_over_rule")
        take_back(cx, tree_id, qid, by, f"the owner resolves it: {note}", ts)
        primary = rule_res.get("question") or qid
        reopened = q.execute(
            "SELECT id FROM research_question WHERE id IN (?,?) AND status='open' ORDER BY id=? DESC",
            (qid, primary, qid)
        ).fetchone()
        out = (
            resolve(cx, tree_id, reopened["id"], keep, by, note)
            if reopened
            else {
                "error": "the rule's resolution is taken back, but the difference no longer reads as this question: resolve the question the plan now holds"
            }
        )
        if "error" in out:
            cx.execute("ROLLBACK TO owner_over_rule")
        cx.execute("RELEASE owner_over_rule")
        return out
    if not rq or rq["kind"] != "conflict" or rq["status"] != "open":
        return {"error": "not an open conflict question in this tree"}
    detail = (json.loads(rq["detail_json"] or "{}") or {}).get("detail") or ""
    m = CONFLICT_AXIS.match(detail)
    if not m:
        return {
            "error": "this conflict is not about one event's date or place: no statement to keep (dismiss it with tools/log_search.py --dismiss)"
        }
    etype, axis = m.group(1), m.group(2)
    a = q.execute("""SELECT a.id, a.status, a.subject_kind, a.subject_id, a.artifact_sha256, a.citation_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier,
                            pf.calendar, ps.raw, ps.place_id FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                     WHERE a.id=? AND a.tree_id=?""", (keep, tree_id)).fetchone()
    if not a:
        return {"error": "no such statement in this tree"}
    if a["status"] == "rejected":
        return {"error": "the statement to keep is rejected"}
    ev = (
        q.execute("SELECT * FROM event WHERE id=? AND tree_id=?", (a["subject_id"], tree_id)).fetchone()
        if a["subject_kind"] == "event"
        else None
    )
    pid = rq["subject_person_id"]
    if not ev or ev["event_type"].lower() != etype or detail not in cat.disagreements(pid, event=ev["id"]):
        return {"error": "the statement is not on the event the question is about"}
    if axis == "date" and not (a["date_start"] or a["date_end"]):
        return {"error": "the statement gives no date to keep"}
    if axis == "place" and not a["raw"]:
        return {"error": "the statement gives no place to keep"}
    if axis == "place" and not a["place_id"]:
        return {
            "error": f"the place the statement gives, “{a['raw']}”, is not yet resolved to a place: answer its words first, then keep it"
        }
    kept_value = (
        {
            "start": a["date_start"] or a["date_end"],
            "end": a["date_end"],
            "text": a["date_text"],
            "qualifier": a["date_qualifier"]
        }
        if axis == "date"
        else a["raw"]
    )
    differs = lambda v: (
        date_verdict(kept_value, v).verdict if axis == "date" else place_verdict(kept_value, v).verdict
    ) == "disagrees"
    set_aside = []
    for r in q.execute("""SELECT a.id, a.citation_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw FROM assertion a
                          JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected' AND a.id<>? AND pf.fact_type=?""", (ev["id"], keep, ev["event_type"])):
        v = (
            {
                "start": r["date_start"] or r["date_end"],
                "end": r["date_end"],
                "text": r["date_text"],
                "qualifier": r["date_qualifier"]
            }
            if axis == "date"
            else r["raw"]
        )
        if (v["start"] if axis == "date" else v) and differs(v):
            set_aside.append(
                {
                    "assertion": r["id"],
                    "record": r["citation_text"],
                    "value": r["date_text"] if axis == "date" else r["raw"]
                }
            )
    was = (
        {
            "date_text": ev["date_text"],
            "date_start": ev["date_start"],
            "date_end": ev["date_end"],
            "date_qualifier": ev["date_qualifier"]
        }
        if axis == "date"
        else {"place_id": ev["place_id"], "place": (cat.place(ev["id"], ev["place_id"]) or {}).get("text")}
    )
    own = (
        {
            "start": ev["date_start"] or ev["date_end"],
            "end": ev["date_end"],
            "text": ev["date_text"],
            "qualifier": ev["date_qualifier"]
        }
        if axis == "date"
        else was["place"]
    )
    if (own["start"] if axis == "date" else own) and differs(own):  # the event's own value, which the kept one replaces
        set_aside.insert(
            0,
            {
                "assertion": None,
                "record": "the tree's own value",
                "value": ev["date_text"] if axis == "date" else was["place"]
            }
        )
    if axis == "date":
        q.execute(
            "UPDATE event SET date_text=?, date_start=?, date_end=?, date_qualifier=?, calendar=coalesce(?, calendar), updated_at=? WHERE id=?",
            (a["date_text"], a["date_start"], a["date_end"], a["date_qualifier"], a["calendar"], ts, ev["id"])
        )
    else:
        q.execute("UPDATE event SET place_id=?, updated_at=? WHERE id=?", (a["place_id"], ts, ev["id"]))
    resolution = {
        "kept": {
            "assertion": keep, "record": a["citation_text"], "value": a["date_text"] if axis == "date" else a["raw"]
        },
        "set_aside": set_aside,
        "event": ev["id"],
        "axis": axis,
        "was": was,
        "note": note,
        "by": by,
        "at": ts,
        "question": qid
    }
    people = [pid] + [
        r["person_id"] for r in q.execute("""SELECT fm.person_id FROM event_participant ep JOIN family_member fm ON fm.family_id=ep.family_id AND fm.role='partner'
                                                            WHERE ep.event_id=? AND fm.person_id<>?""", (ev["id"], pid))
    ]
    closed = [qid]
    q.execute(
        "UPDATE research_question SET status='closed', closed_reason='resolved', closed_at=?, detail_json=? WHERE id=?",
        (ts, dumps({**json.loads(rq["detail_json"] or "{}"), "resolution": resolution}), qid)
    )
    # the same difference, read now from the kept side, and the partner's own question on a family's event
    for person in dict.fromkeys(people):
        lines = [detail] + [l for l in cat.disagreements(person, event=ev["id"]) if l.startswith(f"{etype} {axis}:")]
        for line in dict.fromkeys(lines):
            qd = {"kind": "conflict", "detail": line}
            key = q_key(qd)
            row = q.execute(
                "SELECT id, status, closed_reason FROM research_question WHERE subject_person_id=? AND q_key=?",
                (person, key)
            ).fetchone()
            body = dumps({**qd, "resolution": resolution})
            if row and row["id"] == qid:
                continue
            if row and (row["status"] == "open" or row["closed_reason"] == "gap_gone"):
                q.execute(
                    "UPDATE research_question SET status='closed', closed_reason='resolved', closed_at=?, detail_json=? WHERE id=?",
                    (ts, body, row["id"])
                )
                closed.append(row["id"])
            elif not row and line != detail:
                nid = ulid()
                closed.append(nid)
                q.execute(
                    "INSERT INTO research_question (id,tree_id,subject_person_id,kind,q_key,detail_json,status,closed_reason,created_at,closed_at) VALUES (?,?,?,?,?,?,'closed','resolved',?,?)",
                    (nid, tree_id, person, "conflict", key, body, ts, ts)
                )
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (ulid(), tree_id, ts, by, "update", "research_question", qid, dumps({**resolution, "questions_closed": closed}))
    )
    for person in dict.fromkeys(people):
        plan_person(cx, tree_id, person, by)
    return {
        "ok": True,
        "question": qid,
        "event": ev["id"],
        "axis": axis,
        "kept": resolution["kept"],
        "set_aside": set_aside,
        "was": was,
        "questions_closed": closed
    }

# the source classes the record of the event itself is read from: its own image, or an index or transcript of it
FIRST_HAND = ("original", "derivative")

def rule_resolution(rq):
    """The resolution the rule wrote on a question row closed 'resolved' (its detail's resolution, by rule:…), else None."""
    if not rq or rq["kind"] != "conflict" or rq["status"] != "closed" or rq["closed_reason"] != "resolved":
        return None
    try:
        res = (json.loads(rq["detail_json"] or "{}") or {}).get("resolution")
    except ValueError:
        return None
    return res if isinstance(res, dict) and str(res.get("by") or "").startswith("rule:") else None

def owner_decided(cx, tree_id, ev, axis):
    """Words when the owner has spoken on this event's date or place: resolved a conflict on it, reopened one the rule had
    resolved (take_back's audit row, reopened), or dismissed one on it (a dismissal's line names the type and the axis, not
    the event, so a dismissal on any of the person's events of the type counts). The rule then leaves every conflict on it
    to the owner. None when the owner has not."""
    q = _q(cx)
    what = f"{ev['event_type'].lower()} {axis}"
    spoke = owner_on_event(cx, tree_id, ev["id"], axis)
    if spoke == "resolved":
        return f"you resolved a difference on this {what} yourself: every later one is yours"
    if spoke == "reopened":
        return f"you reopened the rule's resolution of this {what}: it is yours"
    people = [r["person_id"] for r in q.execute("""SELECT person_id FROM event_participant WHERE event_id=? AND person_id IS NOT NULL
                                                   UNION SELECT fm.person_id FROM event_participant ep JOIN family_member fm ON fm.family_id=ep.family_id AND fm.role='partner' WHERE ep.event_id=?""", (ev["id"], ev["id"]))]
    for r in q.execute(
        f"SELECT detail_json FROM research_question WHERE kind='conflict' AND closed_reason='dismissed' AND subject_person_id IN ({','.join('?' * len(people))})",
        people
    ):
        try:
            d = (json.loads(r["detail_json"] or "{}") or {}).get("detail") or ""
        except ValueError:
            d = ""
        if d.startswith(what + ":"):
            return f"you dismissed a difference on this {what}: it is yours"
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
    q = _q(cx)
    cat = Catalog(cx, tree_id)
    cache = {}
    ev = q.execute("SELECT * FROM event WHERE id=? AND tree_id=?", (eid, tree_id)).fetchone()
    if not ev:
        return None, "no such event in this tree"
    fact = ev["event_type"].lower()
    said = owner_decided(cx, tree_id, ev, axis)
    if said:
        return None, said
    sts, extra = [], {}
    for s in subject_statements(cat, "event", eid, want=ev["event_type"]):
        if s["status"] == "rejected":
            continue
        r = q.execute("""SELECT a.notes, ps.place_id, ps.status, pf.persona_id, NOT EXISTS (SELECT 1 FROM persona_relation pr WHERE pr.persona_id=pf.persona_id) AS own
                         FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE a.id=?""", (s["id"],)).fetchone()
        try:
            notes = json.loads(r["notes"]) if r["notes"] and r["notes"].startswith("{") else {}
        except ValueError:
            notes = {}
        extra[s["id"]] = {
            "notes": notes,
            "place_id": r["place_id"] if r["status"] == "accepted" else None,
            "own": bool(r["persona_id"] and r["own"])
        }
        resolved = extra[s["id"]]["place_id"]
        sts.append(
            dict(s, raw=s["place"], place=cat._place_chain(resolved)["text"] if resolved and s["place"] else s["place"])
        )
    vouched = any(s["kind"] == "vouch" and s["status"] == "accepted" for s in sts)
    valued = [s for s in sts if s["kind"] != "vouch" and axis_value(axis, s)]
    if not valued:
        return None, f"no statement on the {fact} gives a {axis}: nothing to decide"
    tree = (
        {
            "start": ev["date_start"] or ev["date_end"],
            "end": ev["date_end"],
            "text": ev["date_text"],
            "qualifier": ev["date_qualifier"]
        }
        if axis == "date"
        else (cat.place(eid, ev["place_id"]) or {}).get("text")
    )
    if not ((tree or {}).get("start") if axis == "date" else tree):
        tree = None
    shown = lambda s: s["date"]["text"] if axis == "date" else s["raw"]
    trusted = lambda s: str(source_tier(cx, s["sha256"]) or "")[:2] in TRUSTED
    primary = lambda s: s["kind"] == "record" and (s["classes"] or {}).get("information") == "primary"
    owners_word = lambda s: s["kind"] == "file" and s["status"] == "accepted" and extra[s["id"]]["notes"].get("uncited")
    table = evidence_table()
    # the table names this event the record's own, for everyone on it (a census household's residence)
    made_for = lambda s: any(
        r["field"] == ev["event_type"] and r.get("information") == "primary"
        for k in (s["classes"] or {}).get("kinds") or []
        for r in table.get(k, [])
    )
    def name(s):
        c = s["classes"] or {}
        rec = record_info(cx, s["sha256"], cache)["name"]
        return f"the {c['original']} ({rec})" if c.get("original") else rec
    def rests(statements):
        parts = {}
        for s in statements:
            c = s["classes"] or {}
            if s["kind"] == "file":
                parts.setdefault("the file's claim", [])
            elif editable(cx, s["sha256"]):
                parts.setdefault("a page anyone can edit", []).append(name(s))
            elif c.get("source") == "authored":
                parts.setdefault("an authored work", []).append(name(s))
            elif c.get("information") == "secondary":
                parts.setdefault("secondary information", []).append(name(s))
            else:
                parts.setdefault("indeterminable information", []).append(name(s))
        return " and ".join(k + (f" ({'; '.join(dict.fromkeys(v))})" if v else "") for k, v in parts.items())
    def narrative(statements, only="", kept=None):
        """The sides these statements form, each with what it rests on, and the tree's own value when no statement gives it."""
        out = [f"{shown(g['statements'][0])} rests {only}on {rests(g['statements'])}" for g in sides(axis, statements)]
        if (
            tree
            and not any(same_value(axis, tree, axis_value(axis, s)) for s in statements)
            and not (kept and same_value(axis, tree, kept))
        ):
            out.append(f"the tree's own {tree['text'] if axis == 'date' else tree} rests {only}on no statement")
        return "; ".join(out)
    def not_first(s):
        """Why a primary statement does not hold the event first-hand, or None when it does."""
        c = s["classes"] or {}
        if s["status"] != "accepted":
            return "it is not accepted as this person's"
        if not trusted(s):
            return "it is a page anyone can edit"
        if c.get("source") not in FIRST_HAND:
            return f"its source is {c.get('source') or 'unclassed'}"
        if c.get("evidence") != "direct":
            return "it is indirect evidence"
        if not (extra[s["id"]]["own"] or made_for(s)):
            return f"the record was made for another person's event, and the {fact} it gives is a relative's"
        return None
    first = [s for s in valued if primary(s) and not_first(s) is None]
    if not first:
        held = next((s for s in valued if primary(s)), None)
        if held:
            return None, f"{name(held)} gives the {fact} as primary information, {shown(held)}, but {not_first(held)}: the conflict is yours"
        return (
            None, f"no side holds primary information about the {fact}, so the classes favour none: {narrative(valued)}"
        )
    keep = sorted(first, key=lambda s: (-specificity(axis, axis_value(axis, s)), order(s["classes"])))
    k = keep[0]
    vk = axis_value(axis, k)
    beside = [s for s in valued if s is not k and same_value(axis, axis_value(axis, s), vk)]
    apart = [s for s in valued if s is not k and s not in beside]
    clash = next((s for s in apart if primary(s)), None)
    if clash:
        return None, f"primary information about the {fact} on more than one side: {name(k)} gives {shown(k)}, {name(clash)} {shown(clash)}"
    word = next((shown(s) for s in apart if owners_word(s)), None)
    # a vouch stands for the tree's own value
    if word is None and vouched and tree and not same_value(axis, tree, vk):
        word = tree["text"] if axis == "date" else tree
    if word:
        return None, f"your own word stands on {word}, against {name(k)}'s {shown(k)}: the conflict is yours"
    left = next(
        (
            (a, b)
            for i, a in enumerate(beside)
            for b in beside[i + 1:]
            if not same_value(axis, axis_value(axis, a), axis_value(axis, b))
        ),
        None
    )
    if left:
        return None, f"{name(k)} states the {fact} first-hand only as {shown(k)}, which leaves {shown(left[0])} against {shown(left[1])}: the classes decide between none of them, so the conflict is yours"
    if axis == "place":
        # as fine a place as the one kept, never a coarser stand-in for it
        placed = [
            s
            for s in keep
            if extra[s["id"]]["place_id"]
                and same_value(axis, axis_value(axis, s), vk)
                and specificity(axis, axis_value(axis, s)) >= specificity(axis, vk)
        ]
        if not placed:
            return None, f"{name(k)} states the {fact} first-hand, but the place it gives, “{k['raw']}”, is not yet resolved to a place: the rule keeps it once its words are answered"
        k = placed[0]
    rest = narrative(apart, only="only ", kept=vk)
    return k["id"], f"{name(k)} states the {fact} first-hand, {shown(k)} ({words(k['classes'])}); " + (
        rest or "every other statement agrees with it"
    )

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
    if not res:
        raise ValueError("not a conflict the rule resolved")
    primary, axis, was = res.get("question") or qid, res["axis"], res["was"]
    ev = q.execute("SELECT * FROM event WHERE id=?", (res["event"],)).fetchone()
    current = None
    if ev and axis == "date":
        current = {k: ev[k] for k in ("date_text", "date_start", "date_end", "date_qualifier")}
        q.execute(
            "UPDATE event SET date_text=?, date_start=?, date_end=?, date_qualifier=?, updated_at=? WHERE id=?",
            (was["date_text"], was["date_start"], was["date_end"], was["date_qualifier"], ts, ev["id"])
        )
    elif ev:
        current = {"place_id": ev["place_id"]}
        q.execute("UPDATE event SET place_id=?, updated_at=? WHERE id=?", (was["place_id"], ts, ev["id"]))
    rows = q.execute("""SELECT id, subject_person_id FROM research_question WHERE tree_id=? AND closed_reason='resolved' AND json_valid(detail_json)
                        AND json_extract(detail_json,'$.resolution.question')=? AND json_extract(detail_json,'$.resolution.at')=?""", (tree_id, primary, res["at"])).fetchall()
    ids = [r["id"] for r in rows]
    q.execute(f"UPDATE research_question SET closed_reason='gap_gone' WHERE id IN ({','.join('?' * len(ids))})", ids)
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "update",
            "research_question",
            primary,
            dumps(
                {
                    "withdrawn": why,
                    "event": res["event"],
                    "axis": axis,
                    "restored": was,
                    "from": current,
                    "kept": res["kept"],
                    "questions": ids,
                    **({"reopened": why} if reopened else {})
                }
            )
        )
    )
    for person in dict.fromkeys(r["subject_person_id"] for r in rows):
        plan_person(cx, tree_id, person, by)
    return ids

def reopen(cx, tree_id, qid, by, note):
    """The owner reopens a conflict the rule resolved: taken back (take_back, reopened), the event's value back to what it was
    and the question open again, the owner's from now on; the rule never resolves that event's date or place again. Refused
    when the note is empty or the question is not one the rule resolved (the owner's own resolution stands as written).
    Returns what was done, or an error."""
    if not (note or "").strip():
        return {"error": "a reopen needs your written reason (--note)"}
    rq = _q(cx).execute("SELECT * FROM research_question WHERE id=? AND tree_id=?", (qid, tree_id)).fetchone()
    res = rule_resolution(rq)
    if not res:
        return {"error": "not a conflict the rule resolved"}
    ids = take_back(cx, tree_id, qid, by, note, now(), reopened=True)
    st = _q(cx).execute("SELECT status FROM research_question WHERE id=?", (res.get("question") or qid,)).fetchone()
    return {
        "ok": True,
        "question": res.get("question") or qid,
        "event": res["event"],
        "axis": res["axis"],
        "restored": res["was"],
        "questions": ids,
        "open": bool(st and st["status"] == "open")
    }

def rule_conflict_decisions(rows):
    """The rows of rule_conflicts that are decisions the rule made: a conflict it resolved (kind conflict, taken) and a
    resolution of its own it took back (kind resolution, not kept)."""
    return [
        x for x in rows if (x["kind"] == "conflict" and x["taken"]) or (x["kind"] == "resolution" and not x["kept"])
    ]

def rule_conflict_line(row):
    """One decision of the rule on a conflict, in words, as the decision's printout, the person screen and the turn's report
    tell it: the person, the date or place kept, the rule's reason, and how to give it back (reopen takes the question's id)."""
    what = row["detail"].split(":", 1)[0]
    if row["kind"] == "conflict":
        return f"the rule resolved {row['person']}'s {what}" + (
            f", kept {row['value']}" if row.get("value") else ""
        ) + f": {row['why']} (to take it back: tools/conclude.py reopen {row['question']} --note \"…\")"
    return f"the rule took back its resolution of {row['person']}'s {what}" + (
        f" (it had kept {row['value']})" if row.get("value") else ""
    ) + f": {row['why']} (the difference is open for you again)"

def rule_conflict_changes(cx, tree_id, after):
    """The rule's decisions on conflicts written to the audit log after the row `after` (an audit row id, the last one when a
    turn began), whichever tool wrote them: each resolution (kind conflict, taken) and each resolution it took back (kind
    resolution, not kept), in the order they were written, as the rows rule_conflicts returns, the reason in the rule's own words."""
    q = _q(cx)
    out = []
    for r in q.execute("""SELECT a.entity_id, a.diff_json, rq.subject_person_id, rq.detail_json FROM audit_log a JOIN research_question rq ON rq.id=a.entity_id
                          WHERE a.tree_id=? AND a.entity_kind='research_question' AND a.actor LIKE 'rule:%' AND a.id>? AND json_extract(a.diff_json,'$.kept') IS NOT NULL
                          ORDER BY a.id""", (tree_id, after)):
        d = json.loads(r["diff_json"])
        row = {
            "person": q.execute(
                "SELECT display_name FROM person WHERE id=?", (r["subject_person_id"],)
            ).fetchone()["display_name"],
            "question": r["entity_id"],
            "detail": (json.loads(r["detail_json"] or "{}") or {}).get("detail") or "",
            "value": d["kept"]["value"]
        }
        out.append(
            {**row, "kind": "resolution", "kept": False, "why": d["withdrawn"]}
            if d.get("withdrawn")
            else {**row, "kind": "conflict", "taken": True, "why": d["note"]}
        )
    return out

def conflict_lines(cat, pid):
    """The person's conflict lines on an event's date or place as the catalog gives them now (Catalog.disagreements), each
    with its event and axis: [(line, event id, axis)]."""
    out = []
    for eid, in cat.q("""SELECT DISTINCT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                         WHERE ep.person_id=? OR ep.family_id IN (SELECT family_id FROM family_member WHERE person_id=? AND role='partner') ORDER BY e.event_type, e.date_start, e.id""", pid, pid):
        for line in cat.disagreements(pid, event=eid):
            m = CONFLICT_AXIS.match(line)
            if m:
                out.append((line, eid, m.group(2)))
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
    with the person, the question, its line and the date or place kept (value; none for a conflict left, or one a dry run
    would resolve); known, the questions the rule had resolved before a run that decides cards first (reconsider), makes a
    resolution written since, inside one of those decisions, a row of kind conflict taken, as one this pass wrote."""
    from plan import q_key
    q = _q(cx)
    ts = now()
    cat = Catalog(cx, tree_id)
    out = []
    actor = f"{RULE_ACTOR['conflict']} for {by.split(' for ', 1)[-1] if by.startswith('rule:') else by}"
    name = lambda pid: (
        q.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone() or {"display_name": "?"}
    )["display_name"]
    want = None if people is None else set(people)
    done = {}
    for rq in q.execute(
        """SELECT * FROM research_question WHERE tree_id=? AND kind='conflict' AND closed_reason='resolved' AND json_valid(detail_json)
                           AND json_extract(detail_json,'$.resolution.question')=id AND json_extract(detail_json,'$.resolution.by') LIKE 'rule:%'
                           ORDER BY json_extract(detail_json,'$.resolution.at') DESC, id DESC""", (tree_id,)
    ).fetchall():
        if want is not None and rq["subject_person_id"] not in want:
            continue
        res = rule_resolution(rq)
        spot = (res["event"], res["axis"])
        # a newer resolution on the same date or place stands: the older ones under it stand with it
        if done.get(spot):
            continue
        detail = (json.loads(rq["detail_json"]) or {}).get("detail")
        ev = q.execute("SELECT * FROM event WHERE id=?", (res["event"],)).fetchone()
        said = owner_decided(cx, tree_id, ev, res["axis"]) if ev else "the event is gone"
        if said:
            done[spot] = True
            out.append(
                {
                    "kind": "resolution",
                    "person": name(rq["subject_person_id"]),
                    "question": rq["id"],
                    "detail": detail,
                    "kept": True,
                    "value": res["kept"]["value"],
                    "why": said
                }
            )
            continue
        keep, why = classes_decide(cx, tree_id, res["event"], res["axis"])
        holds = keep is not None and (keep == res["kept"]["assertion"] or kept_agrees(cx, keep, res))
        if keep is not None and not holds:
            why = f"it would now keep another value: {why}"
        if not holds and not dry_run:
            take_back(cx, tree_id, rq["id"], actor, why, ts)
        done[spot] = holds
        # written during this run, inside a decision: told as resolved here
        if holds and known is not None and rq["id"] not in known:
            out.append(
                {
                    "kind": "conflict",
                    "person": name(rq["subject_person_id"]),
                    "question": rq["id"],
                    "detail": detail,
                    "taken": True,
                    "value": res["kept"]["value"],
                    "why": res.get("note") or why
                }
            )
            continue
        out.append(
            {
                "kind": "resolution",
                "person": name(rq["subject_person_id"]),
                "question": rq["id"],
                "detail": detail,
                "kept": holds,
                "value": res["kept"]["value"],
                "why": why
            }
        )
    pids = (
        list(dict.fromkeys(people))
        if people is not None
        else [
            r["subject_person_id"]
            for r in q.execute(
                "SELECT DISTINCT subject_person_id FROM research_question WHERE tree_id=? AND kind='conflict' AND status='open' ORDER BY subject_person_id",
                (tree_id,)
            )
        ]
    )
    opened = lambda pid: {
        (json.loads(r["detail_json"] or "{}") or {}).get("detail"): r["id"]
        for r in q.execute(
            "SELECT id, detail_json FROM research_question WHERE subject_person_id=? AND kind='conflict' AND status='open'",
            (pid,)
        )
    }
    for pid in pids:
        lines = conflict_lines(cat, pid)
        now_lines = {l for l, _, _ in lines}
        open_ = opened(pid)
        if not dry_run and any(CONFLICT_AXIS.match(d or "") and d not in now_lines for d in open_):
            # the questions as the catalog gives them now
            plan_person(cx, tree_id, pid, by)
            open_ = opened(pid)
        seen = set()
        for line, eid, axis in lines:
            if (eid, axis) in seen:
                continue
            qid = open_.get(line)
            if qid is None:
                # not an open question: resolved, dismissed or closed with its event and axis
                if not dry_run:
                    continue
                closed = q.execute(
                    "SELECT closed_reason FROM research_question WHERE subject_person_id=? AND q_key=? AND status='closed'",
                    (pid, q_key({"kind": "conflict", "detail": line}))
                ).fetchone()
                if closed and closed["closed_reason"] != "gap_gone":
                    continue
            elif q.execute("SELECT status FROM research_question WHERE id=?", (qid,)).fetchone()["status"] != "open":
                seen.add((eid, axis))
                continue
            seen.add((eid, axis))
            keep, why = classes_decide(cx, tree_id, eid, axis)
            taken = keep is not None
            value = None
            if taken and not dry_run:
                r = resolve(cx, tree_id, qid, keep, actor, why)
                if "error" in r:
                    taken, why = False, r["error"]
                else:
                    value = r["kept"]["value"]
            out.append(
                {
                    "kind": "conflict",
                    "person": name(pid),
                    "question": qid,
                    "detail": line,
                    "taken": taken,
                    "value": value,
                    "why": why
                }
            )
    return out

def kept_agrees(cx, keep, res):
    """Whether the statement the rule would keep now gives the same value its resolution kept (another first-hand record of
    the same date or place, on the same side)."""
    from proof import same_value
    r = _q(cx).execute("""SELECT pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id
                          LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE a.id=?""", (keep,)).fetchone()
    if not r:
        return False
    kept = res["kept"]["value"]
    if res["axis"] == "date":
        k = _q(cx).execute(
            """SELECT pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id WHERE a.id=?""",
            (res["kept"]["assertion"],)
        ).fetchone()
        if not k:
            return False
        return same_value(
            "date",
            {
                "start": r["date_start"] or r["date_end"],
                "end": r["date_end"],
                "text": r["date_text"],
                "qualifier": r["date_qualifier"]
            },
            {
                "start": k["date_start"] or k["date_end"],
                "end": k["date_end"],
                "text": k["date_text"],
                "qualifier": k["date_qualifier"]
            }
        )
    return bool(r["raw"] and kept and same_value("place", r["raw"], kept))

def living(cx, tree_id, pid, word, by, note):
    """The owner's word on whether a person is alive, above the tier rule (docs/DATA-ARCHITECTURE.md §7 decision 3):
    person.living_override set to living or deceased, or cleared by unknown so the rule decides again; one audit row. Returns
    what was and is, with the default's reading afterwards."""
    q = _q(cx)
    ts = now()
    row = q.execute("SELECT living_override FROM person WHERE id=? AND tree_id=?", (pid, tree_id)).fetchone()
    if not row:
        raise ValueError("no such person in this tree")
    value = None if word == "unknown" else word
    q.execute("UPDATE person SET living_override=?, updated_at=? WHERE id=?", (value, ts, pid))
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "update",
            "person",
            pid,
            dumps({"living_override": {"was": row["living_override"], "now": value}, "note": note})
        )
    )
    return {"was": row["living_override"], "now": value, **Catalog(cx, tree_id).living(pid)}

def links_resting_on(cx, tree_id, prop_id, gone=(), taken_back=False):
    """The statements a withdrawal or a person's rejection of this decision takes back besides its own
    (docs/RESEARCH-WORKFLOW.md §5–7): a family link the record states stands on both people it relates being accepted on the
    record, and is written by the second of the two acceptances (link_family), so it is the other decision's statement.
    Taken back: each accepted statement of a membership joining this decision's person to a person accepted on another
    persona of the record, written from a relationship the record states between that persona and this decision's entry (on
    any reading or copy of it), the relationship's own word its citation (an in-law's tie resolved through this decision's
    person included), unless another pair of personas accepted on the record states the same link in the same word; and with
    a spouse link that goes, the facts the same decision wrote on the couple's family from the record
    (assert_family_events). A statement whose status a person decided on its own (person_decided), one written undecided
    (ACCEPTED_WITH_RECORD) and this decision's own are never among them. gone: decisions already withdrawn in this pass
    (reconsider), read as not accepted. taken_back: the undecided statements a withdrawal of this decision left are among
    them too, for a person's rejection of a card whose decision the rule took back. Returns the assertion ids."""
    q = _q(cx)
    statuses = ("accepted", "undecided") if taken_back else ("accepted",)
    held = f"status IN ({','.join('?' * len(statuses))})"
    pay = json.loads(q.execute("SELECT payload_json FROM proposal WHERE id=?", (prop_id,)).fetchone()["payload_json"])
    me = pay.get("person_id")
    if not me:
        return []
    gone = set(gone) | {prop_id}
    mine = set(same_personas(cx, pay["persona_id"]))
    for x, in q.execute(
        "SELECT persona_id FROM person_persona WHERE proposal_id=? AND person_id=?", (prop_id, me)
    ).fetchall():
        mine |= set(same_personas(cx, x))
    def person(z):
        """The person a persona other than this decision's entry is accepted as, by a decision standing in this pass, or None."""
        if z in mine:
            return None
        r = q.execute("""SELECT pp.person_id, pp.proposal_id FROM person_persona pp JOIN person o ON o.id=pp.person_id
                         WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?""", (z, tree_id)).fetchone()
        return r["person_id"] if r and r["proposal_id"] not in gone else None
    members = lambda fid: {
        r["person_id"] for r in q.execute("SELECT person_id FROM family_member WHERE family_id=?", (fid,))
    }
    word = lambda r: r["value_text"] or r["kind"]
    in_law = lambda r: r["kind"] == "other" and bool(IN_LAW.get((r["value_text"] or "").strip().lower()))
    out, couples = [], []
    for sha in sorted(
        {
            r["artifact_sha256"]
            for r in q.execute(
                f"SELECT artifact_sha256 FROM persona WHERE id IN ({','.join('?' * len(mine))})", tuple(mine)
            )
        }
    ):
        rows = q.execute(
            """SELECT r.persona_id, r.related_persona_id, r.kind, r.value_text FROM persona_relation r JOIN persona pe ON pe.id=r.persona_id
                            WHERE pe.artifact_sha256=? AND r.kind IN ('child','parent','spouse','other')""", (sha,)
        ).fetchall()
        rows = [r for r in rows if r["kind"] != "other" or in_law(r)]
        def states(r, fid, who, them):
            """Whether a relationship row on the record, both its personas accepted, states this membership: one of the two its
            person (who), the other in its family; for an in-law's tie, written from the in-law's side, the in-law the one (them)."""
            a, b = person(r["persona_id"]), person(r["related_persona_id"])
            if not (a and b):
                return False
            if in_law(r):
                return a == them
            fam = members(fid)
            return who in (a, b) and a in fam and b in fam
        for r in rows:
            if r["persona_id"] in mine and r["related_persona_id"] not in mine:
                other = r["related_persona_id"]
            elif r["related_persona_id"] in mine and r["persona_id"] not in mine:
                other = r["persona_id"]
            else:
                continue
            # an in-law's tie is written from the in-law's side: this decision's person is the in-law then, and the link is its own
            if in_law(r) and r["persona_id"] != other:
                continue
            them = person(other)
            if not them:
                continue
            for a in q.execute(
                f"""SELECT id, subject_id, notes FROM assertion WHERE tree_id=? AND subject_kind='family_member' AND artifact_sha256=? AND citation_text=?
                                   AND {held} AND NOT person_decided AND {ACCEPTED_WITH_RECORD}""",
                (tree_id, sha, f"{word(r)} on the record", *statuses)
            ).fetchall():
                if a["id"] in out or json.loads(a["notes"] or "{}").get("proposal") == prop_id:
                    continue
                fid, who, role = json.loads(a["subject_id"])
                fam = members(fid)
                if not (
                    (who == them or them in fam) if in_law(r) else (who in (me, them) and me in fam and them in fam)
                ):
                    continue
                if any(word(s) == word(r) and states(s, fid, who, them) for s in rows):
                    continue
                out.append(a["id"])
                if role == "partner":
                    couples.append((fid, json.loads(a["notes"] or "{}").get("proposal"), sha))
    for fid, writer, sha in dict.fromkeys(couples):
        out += [a for a, in q.execute(f"""SELECT a.id FROM assertion a JOIN event_participant ep ON ep.event_id=a.subject_id AND ep.family_id=?
                                          WHERE a.tree_id=? AND a.subject_kind='event' AND a.artifact_sha256=? AND a.{held} AND NOT a.person_decided
                                          AND json_valid(a.notes) AND json_extract(a.notes,'$.proposal')=? AND json_extract(a.notes,'$.computed') IS NULL""", (fid, tree_id, sha, *statuses, writer)).fetchall() if a not in out]
    return out

def withdraw(cx, tree_id, prop_id, by, why, ts):
    """The rule takes back a decision it would no longer make: the proposal and the persona link return to Undecided, every
    assertion the decision wrote returns to Undecided under by, the rule acting for whoever ran it, save one whose status a
    person has decided on its own since (person_decided), which keeps it; and so does the name alias it wrote (an Accept
    later makes them Accepted again), and every family link the decision was one of the two acceptances for, written by the
    other's decision, with the family facts written with a spouse link (links_resting_on: accepting either card again
    writes it again); the questions the decision answered are closed as gap_gone so the plan reopens the ones whose gap is
    back, the plans of everyone whose links changed are regenerated, and the audit row says why. The record is a card for
    the owner again. Returns how many assertions were taken back."""
    q = _q(cx)
    p = q.execute(
        "SELECT * FROM proposal WHERE id=? AND tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%'",
        (prop_id, tree_id)
    ).fetchone()
    if not p:
        raise ValueError("not a decision the rule made")
    pay = json.loads(p["payload_json"])
    links = links_resting_on(cx, tree_id, prop_id)
    linked = (
        [
            json.loads(r["subject_id"])[1]
            for r in q.execute(
                f"SELECT subject_id FROM assertion WHERE subject_kind='family_member' AND id IN ({','.join('?' * len(links))})",
                links
            )
        ]
        if links
        else []
    )
    n = q.execute(
        """UPDATE assertion SET status='undecided', asserted_by=?, asserted_at=? WHERE tree_id=? AND status='accepted' AND NOT person_decided
                     AND json_valid(notes) AND json_extract(notes,'$.proposal')=?""", (by, ts, tree_id, prop_id)
    ).rowcount
    if links:
        n += q.execute(
            f"UPDATE assertion SET status='undecided', asserted_by=?, asserted_at=? WHERE id IN ({','.join('?' * len(links))})",
            (by, ts, *links)
        ).rowcount
    q.execute(
        "UPDATE alias SET status='undecided' WHERE tree_id=? AND status='accepted' AND json_valid(notes) AND json_extract(notes,'$.proposal')=?",
        (tree_id, prop_id)
    )
    q.execute(
        "UPDATE proposal SET status='undecided', decided_by=NULL, decided_at=NULL, decision_note=? WHERE id=?",
        (f"the rule took its decision back: {why}", prop_id)
    )
    # every reading's persona of this entry of the record, the re-reads' included, and every other copy's the decision was carried to
    ids = same_personas(cx, pay["persona_id"])
    q.execute(
        f"UPDATE person_persona SET status='undecided', decided_by=NULL, decided_at=NULL WHERE person_id=? AND (persona_id IN ({','.join('?' * len(ids))}) OR proposal_id=?)",
        (pay["person_id"], *ids, prop_id)
    )
    q.execute(
        "UPDATE research_question SET closed_reason='gap_gone', answered_by_proposal_id=NULL WHERE answered_by_proposal_id=?",
        (prop_id,)
    )
    for pid in dict.fromkeys([pay.get("person_id"), pay.get("subject_person_id")] + linked):
        if pid:
            plan_person(cx, tree_id, pid, by)
    q.execute(
        "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            ulid(),
            tree_id,
            ts,
            by,
            "update",
            "proposal",
            prop_id,
            dumps(
                {
                    "withdrawn": why,
                    "persona": pay["persona_id"],
                    "person": pay["person_id"],
                    "assertions": n,
                    "links": links
                }
            )
        )
    )
    return n

def rematch(cx, tree_id, by, ts, people=None, dry_run=False, withdrawn=()):
    """The undecided cards the evidence has passed by, matched again (docs/RESEARCH-WORKFLOW.md §5–7): a card an older matcher
    wrote (the matcher is versioned, match.MATCHER); a card left on a superseded reading of its record (a decision the rule
    took on that reading and withdrew after the page was read again: a re-read closes only the cards undecided at the
    time); and a card putting a persona to a person that the matcher, on the person's evidence as it now stands, would no
    longer write (match.proposals, the record matched for the person the card was written for, the card taken as
    unwritten): the persona a hint for that person now, waiting on the record's own person, or put to another person. Each
    closes rejected with the note superseded, as a re-read closes the cards of the reading it supersedes, and its record's
    current reading is matched again (match_record): the matcher proposes the persona afresh as it stands, the rule taking
    what it takes, so a creation the rule took back on a reading since superseded comes back as a card for the person it
    created, judged as that creation (made_here), and a persona that is a hint leaves the cards and stays a hint on the page. A card closed on a superseded
    reading, a decision the rule withdrew, leaves what the withdrawal took back undecided, statements and name alias:
    closing a card judges nothing it stated, so a family membership resting on it stays the claim it was, and the card the
    record's current reading gets carries the record's facts again: accepting it makes them stand. A card the matcher still puts to
    the same person keeps its id, its rationale the matcher's words as the evidence now stands; one the rule took and
    withdrew keeps the words written before the record was taken, since its own statements now stand on the person and the
    matcher would read the record against itself. people: only the cards putting a persona to one of them (rematch_people:
    the people whose evidence a decision changed); every undecided card otherwise (reconsider). dry_run writes nothing and matches nothing again; withdrawn, the decisions
    a dry run of reconsider would withdraw, are read as the cards they would be again, so a dry run names the ones it would
    supersede on an older matcher's or a superseded reading. Returns (rows, taken): a row per card closed (kind rematch)
    and per rationale rewritten (kind rationale), each with the proposal, the person, the persona and why; and a row per
    card the rule took on the records matched again (kind card)."""
    from match import proposals
    q = _q(cx)
    out = []
    taken_rows = []
    if people is not None and not people:
        return out, taken_rows
    current = (
        q.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", MATCHER).fetchone() or {"id": None}
    )["id"]
    name = lambda pid: (
        q.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone() or {"display_name": "(a new person)"}
    )["display_name"]
    persona = lambda pid: q.execute("SELECT name_text FROM persona WHERE id=?", (pid,)).fetchone()["name_text"]
    said = lambda text: [s.strip() for s in re.split(r"(?<=\.)\s+(?=[A-Z])", text or "") if s.strip()]
    scope = (
        f"AND json_extract(p.payload_json,'$.person_id') IN ({','.join('?' * len(people))})"
        if people is not None
        else ""
    )
    withdrawn = tuple(withdrawn)
    also = f" OR p.id IN ({','.join('?' * len(withdrawn))})" if withdrawn else ""
    cards = q.execute(
        f"""SELECT p.*, e.superseded_by, x.version FROM proposal p JOIN extraction e ON e.id=json_extract(p.payload_json,'$.extraction_id')
                          JOIN extractor x ON x.id=p.generated_by WHERE p.tree_id=? AND (p.status='undecided'{also}) AND p.kind IN ('persona_match','new_person') {scope}
                          ORDER BY e.ran_at, e.id, p.created_at, p.id""", (tree_id, *withdrawn, *(people or []))
    ).fetchall()
    again = {}  # extraction id -> matched again once every card is examined
    def close(p, pay, why, reading):
        out.append(
            {
                "proposal": p["id"],
                "person": name(pay.get("person_id")),
                "persona": persona(pay["persona_id"]),
                "kind": "rematch",
                "taken": True,
                "why": why
            }
        )
        again[reading] = True
        if dry_run:
            return
        q.execute(
            "UPDATE proposal SET status='rejected', decided_by=?, decided_at=?, decision_note='superseded' WHERE id=?",
            (by, ts, p["id"])
        )
        q.execute(
            "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                ulid(),
                tree_id,
                ts,
                by,
                "reject",
                "proposal",
                p["id"],
                dumps(
                    {
                        "closed": "superseded",
                        "why": why,
                        "matcher": p["version"],
                        "now": MATCHER[2],
                        "extraction": pay["extraction_id"],
                        "matched_again": reading
                    }
                )
            )
        )
    later = []
    for p in cards:  # first what no comparison is needed for: an older matcher's card, a card on a superseded reading
        pay = json.loads(p["payload_json"])
        eid = pay["extraction_id"]
        if p["superseded_by"]:
            cur = eid
            while (
                nxt := q.execute("SELECT superseded_by FROM extraction WHERE id=?", (cur,)).fetchone()["superseded_by"]
            ):
                cur = nxt
            close(
                p,
                pay,
                "written on a reading of the record that a later reading superseded: superseded, the current reading matched again",
                cur
            )
        elif p["generated_by"] != current:
            close(p, pay, f"the matcher at {p['version']} wrote it; superseded, proposed again at {MATCHER[2]}", eid)
        elif p["kind"] == "persona_match" and p["status"] == "undecided":
            later.append((p, pay))
    views = {}  # extraction id -> {persona id: what the matcher proposes for it now}
    # then each card against what the matcher writes now, the statements just turned counted as they stand
    for p, pay in later:
        eid = pay["extraction_id"]
        if eid not in views:  # the record matched for the people its cards were written for, as when they were written
            mine = [(c["id"], cp.get("subject_person_id")) for c, cp in later if cp["extraction_id"] == eid]
            views[eid] = {
                v["persona_id"]: v
                for v in proposals(
                    cx, eid, about=list(dict.fromkeys(s for _, s in mine if s)), ignore=[i for i, _ in mine]
                )
                if v["tree_id"] == tree_id
            }
        v = views[eid].get(pay["persona_id"])
        if v and v["kind"] == "persona_match" and v["person_id"] == pay["person_id"]:
            if v["rationale"] == p["rationale"]:
                continue
            # a decision withdrawn: its own statements stand on the person, the words written before it was taken stay
            if q.execute(
                "SELECT 1 FROM assertion WHERE tree_id=? AND json_valid(notes) AND json_extract(notes,'$.proposal')=? LIMIT 1",
                (tree_id, p["id"])
            ).fetchone():
                continue
            was, now_ = said(p["rationale"]), said(v["rationale"])
            why = "; ".join(
                x
                for x in (
                    "now: " + " ".join(s for s in now_ if s not in was) if any(s not in was for s in now_) else "",
                    "no longer: " + " ".join(s for s in was if s not in now_) if any(s not in now_ for s in was) else ""
                )
                if x
            )
            out.append(
                {
                    "proposal": p["id"],
                    "person": name(pay.get("person_id")),
                    "persona": persona(pay["persona_id"]),
                    "kind": "rationale",
                    "taken": True,
                    "why": why
                }
            )
            if dry_run:
                continue
            q.execute("UPDATE proposal SET rationale=? WHERE id=?", (v["rationale"], p["id"]))
            q.execute(
                "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                (
                    ulid(),
                    tree_id,
                    ts,
                    by,
                    "update",
                    "proposal",
                    p["id"],
                    dumps({"rationale": {"was": p["rationale"], "now": v["rationale"]}})
                )
            )
            continue
        why = (
            f"the matcher now puts {persona(pay['persona_id'])} to {name(v['person_id'])}"
            if v and v["person_id"]
            else f"the matcher now finds nobody in the tree fitting {persona(pay['persona_id'])}"
            if v
            else f"no longer a card for {name(pay.get('person_id'))} as the evidence stands: a hint on the page, or waiting on the record's own person"
        ) + ": superseded, the record matched again"
        close(p, pay, why, eid)
    if dry_run:
        return out, taken_rows
    for eid in again:
        for prop_id, pname, why in match_record(cx, eid, by)[1]:
            pay = json.loads(
                q.execute("SELECT payload_json FROM proposal WHERE id=?", (prop_id,)).fetchone()["payload_json"]
            )
            taken_rows.append(
                {
                    "proposal": prop_id,
                    "person": name(pay.get("person_id")),
                    "persona": pname,
                    "kind": "card",
                    "taken": True,
                    "why": why
                }
            )
    return out, taken_rows

def rematch_people(cx, tree_id, by, people):
    """The undecided cards of these people matched again (rematch) once a decision has changed their evidence, the owner's or
    the rule's (acting for the owner, who is then the one recorded): a card, a key fact, one statement, a place's words, a
    conflict resolved or reopened, a statement placed, a family link or a divorce on the owner's word, a merge. Returns the
    rows of the cards superseded and rewritten."""
    owner = by.split(" for ", 1)[-1] if by.startswith("rule:") else by
    return rematch(cx, tree_id, owner, now(), people=[p for p in dict.fromkeys(people) if p])[0]

def superseded_lines(rows):
    """The cards a decision superseded, one line each, as the command line tells them."""
    return [
        f"card superseded, {x['person']} <- {x['persona']} [{x['proposal'][-6:]}]: {x['why']}"
        for x in rows
        if x["kind"] == "rematch"
    ]

def reconsider(cx, tree_id, by, dry_run=False):
    """Every decision on one copy of a record carried first to every other copy the archive holds of it (carry: one record is
    one source wherever it is held). Then every decision the rule made, in the order it took them, examined again as the rule
    stands now, on the ground that stood before it: the assertions of that decision, of every rule decision after it and of every decision already withdrawn do not
    count, so each rests only on the owner's decisions and on earlier rule decisions that survived. The order is the second the
    decision was taken, then its accept row in the audit log (a ULID, minted in order to the millisecond, written as the decision
    takes effect: decide), the card's own id where no such row exists; within one second a card the rule took after one it
    rests on is examined after it. One the rule would no longer take is withdrawn, and with it the family links it was one
    of the two acceptances for (links_resting_on), which no decision examined after it stands on either. Then every
    undecided card is matched again (rematch): one an older matcher wrote, one left on a superseded reading of its record,
    and one the matcher would no longer put to that person as the evidence now stands close as superseded and their
    records' current readings are matched again, the matcher proposing the personas afresh; one it still puts to the same
    person takes its words as they now read. Then every card still undecided, oldest first, examined as the rule stands
    now: one it would now take is taken, recorded as the rule; a decision can open another card, so the pass repeats until
    nothing new is taken.
    Then the conflicts (rule_conflicts): every conflict the rule resolved examined again, one it would no longer resolve so
    taken back with the event's value restored, and every open conflict on an event's date or place resolved where the
    classes favour one side without doubt (classes_decide), the rest left to the owner with the reason; the cards of the
    people whose date or place that changed are matched again last (rematch_people). Returns one row per decision, per
    card superseded or rewritten, per card and per conflict, and per decision carried to a copy: kind (decision, rematch,
    rationale, card, resolution, conflict or carried), the person, kept or taken, why; a card's rows the proposal and the persona, a conflict's the question and
    its line. A dry run examines the cards a run would leave, a decision it would withdraw among them, on the ground a run
    would leave (without the decisions it would withdraw and the links they take back): not the ones it would supersede."""
    q = _q(cx)
    ts = now()
    out = []
    gone = []
    unlinked = []
    name = lambda pid: (
        q.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone() or {"display_name": "(a new person)"}
    )["display_name"]
    # a decision on one copy of a record is the record's: carried to every copy first
    for sha, in q.execute(
        "SELECT a_sha256 FROM same_record UNION SELECT b_sha256 FROM same_record ORDER BY 1"
    ).fetchall():
        for c in carry(cx, by, sha, trees=[tree_id], dry_run=dry_run):
            if not any(
                o["kind"] == "carried" and o["proposal"] == c["proposal"] and o["persona_id"] == c["persona"]
                for o in out
            ):
                out.append(
                    {
                        "proposal": c["proposal"],
                        "person": name(c["person"]),
                        "persona": q.execute(
                            "SELECT name_text FROM persona WHERE id=?", (c["persona"],)
                        ).fetchone()["name_text"],
                        "persona_id": c["persona"],
                        "kind": "carried",
                        "taken": not c["kept"],
                        "why": (
                            f"decided {c['status']} on another copy of the record; {q.execute('SELECT coalesce(original_filename, substr(sha256,1,12)) FROM artifact WHERE sha256=?', (c['copy'],)).fetchone()[0]} "
                            + (
                                f"holds it {c['kept']} on a decision of its own, which stands"
                                if c["kept"]
                                else "takes it"
                            )
                        )
                    }
                )
    known = {
        r["id"]
        for r in q.execute(
            "SELECT id FROM research_question WHERE tree_id=? AND closed_reason='resolved' AND json_valid(detail_json) AND json_extract(detail_json,'$.resolution.by') LIKE 'rule:%'",
            (tree_id,)
        )
    }
    rows = q.execute("""SELECT p.* FROM proposal p WHERE p.tree_id=? AND p.status='accepted' AND p.decided_by LIKE 'rule:%'
                        ORDER BY p.decided_at, coalesce((SELECT max(a.id) FROM audit_log a WHERE a.entity_kind='proposal' AND a.entity_id=p.id AND a.action='accept'), p.id), p.id""", (tree_id,)).fetchall()
    ids = [r["id"] for r in rows]
    name = lambda pay: (
        q.execute("SELECT display_name FROM person WHERE id=?", (pay.get("person_id"),)).fetchone()
        or {"display_name": "(a new person)"}
    )["display_name"]
    persona = lambda pay: q.execute(
        "SELECT name_text FROM persona WHERE id=?", (pay["persona_id"],)
    ).fetchone()["name_text"]
    def link_words(links):
        """The family links a withdrawal takes back, in words: whose membership, and the record's word for it."""
        rows_ = [
            q.execute("SELECT subject_kind, subject_id, citation_text FROM assertion WHERE id=?", (a,)).fetchone()
            for a in links
        ]
        words = [
            f"{name({'person_id': json.loads(r['subject_id'])[1]})}'s {'parents' if json.loads(r['subject_id'])[2] == 'child' else 'spouse'} link ({r['citation_text']})"
            for r in rows_
            if r["subject_kind"] == "family_member"
        ]
        return (
            ("; with it the family links it was one of the two acceptances for: " + ", ".join(dict.fromkeys(words)))
            if words
            else ""
        )
    for i, p in enumerate(rows):
        pay = json.loads(p["payload_json"])
        ok, why = rule_accepts(cx, tree_id, p, without=tuple(ids[i:] + gone + unlinked))
        if not ok:
            # one an earlier withdrawal in this pass took back is gone already
            links = [a for a in links_resting_on(cx, tree_id, p["id"], gone) if a not in unlinked]
            gone.append(p["id"])
            unlinked += links
            why += link_words(links)
            if not dry_run:
                withdraw(cx, tree_id, p["id"], f"{RULE_ACTOR[p['kind']]} for {by}", why, ts)
        out.append(
            {
                "proposal": p["id"],
                "person": name(pay),
                "persona": persona(pay),
                "kind": "decision",
                "kept": ok,
                "why": why
            }
        )
    rematched, retaken = rematch(cx, tree_id, by, ts, dry_run=dry_run, withdrawn=gone if dry_run else ())
    out += rematched
    superseded = {r["proposal"] for r in rematched if r["kind"] == "rematch"}
    # proposal id -> the row of its latest examination; the re-run's own decisions first
    cards = {r["proposal"]: r for r in retaken}
    taken = True
    while taken:
        taken = False
        # a dry run reads the decisions it would withdraw as the cards they would be
        dry = tuple(gone) if dry_run else ()
        also = f" OR id IN ({','.join('?' * len(dry))})" if dry else ""
        for p in q.execute(
            f"SELECT * FROM proposal WHERE tree_id=? AND (status='undecided'{also}) AND kind IN ('persona_match','new_person') ORDER BY created_at, id",
            (tree_id, *dry)
        ).fetchall():
            if p["id"] in superseded or (p["id"] in cards and cards[p["id"]]["taken"]):
                continue
            # a decision earlier in this pass may have closed it
            p = q.execute("SELECT * FROM proposal WHERE id=?", (p["id"],)).fetchone()
            if p["status"] != "undecided" and p["id"] not in dry:
                continue
            pay = json.loads(p["payload_json"])
            ok, why = rule_accepts(cx, tree_id, p, without=tuple(gone + unlinked) if dry_run else ())
            if ok and not dry_run:
                decide(cx, tree_id, p["id"], "accepted", f"{RULE_ACTOR[p['kind']]} for {by}", note=why)
                taken = True
            cards[p["id"]] = {
                "proposal": p["id"],
                "person": name(pay),
                "persona": persona(pay),
                "kind": "card",
                "taken": ok,
                "why": why
            }
    # a card refused here and closed since by a later decision's rematch is no card left
    still = (
        lambda r: r["taken"]
        or dry_run
        or q.execute("SELECT status FROM proposal WHERE id=?", (r["proposal"],)).fetchone()["status"] == "undecided"
    )
    # its resolutions examined again, then every open conflict on a date or a place
    conflicts = rule_conflicts(cx, tree_id, by, dry_run=dry_run, known=known)
    moved = (
        []
        if dry_run
        else [
            q.execute(
                "SELECT subject_person_id FROM research_question WHERE id=?", (c["question"],)
            ).fetchone()["subject_person_id"]
            for c in conflicts
            if c["question"]
                and ((c["kind"] == "conflict" and c["taken"]) or (c["kind"] == "resolution" and not c["kept"]))
        ]
    )
    # a date or place the pass kept or gave back moves the cards compared with it
    return out + [r for r in cards.values() if still(r)] + conflicts + rematch_people(cx, tree_id, by, moved)

def main():
    ap = argparse.ArgumentParser(
        description="The standing rule's decisions examined again; the owner's word on a family link, a divorce, a duplicate or whether a person is alive."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    dc = sub.add_parser("decide", help="the decision on a card: is this record's persona this person (or a new person)")
    dc.add_argument("proposal")
    dc.add_argument("verdict", choices=["accept", "reject"])
    dc.add_argument("--note")
    dc.add_argument(
        "--choice",
        help="a place card: the number of the candidate the words mean, in the order the card offers them (0 is the first)"
    )
    dc.add_argument(
        "--alone",
        action="store_true",
        help="a place card: answer this card's string only, not every card that offers the same places"
    )
    dc.add_argument(
        "--kind",
        choices=[
            "typo",
            "phonetic",
            "transcription",
            "abbreviation",
            "translation",
            "historical",
            "jurisdiction_change",
            "jurisdiction_error",
            "context_glue",
            "detail",
            "unclassified"
        ],
        help="a place card: how the words differ from the place's own name"
    )
    fc = sub.add_parser(
        "fact",
        help="a key fact of a person decided: accept touches held evidence or is your own word (a vouch); reject and undecided touch every assertion behind it"
    )
    fc.add_argument("person")
    fc.add_argument("field")
    fc.add_argument("verdict", choices=["accept", "reject", "undecided"])
    fc.add_argument("--note")
    ac = sub.add_parser(
        "assertion",
        help="one statement of one record on one subject, decided on its own (a fact decision touches every statement behind the fact)"
    )
    ac.add_argument("assertion")
    ac.add_argument("verdict", choices=["accept", "reject", "undecided"])
    ac.add_argument("--note")
    pc = sub.add_parser(
        "place",
        help="a record's fact onto the event the owner means: one whose event is the owner's choice (Catalog.unplaced), or one asserted on another event of its type, moved; an event left with no statement but rejected ones leaves the person or the family"
    )
    pc.add_argument("persona_fact")
    pc.add_argument("--event", required=True, dest="event")
    pc.add_argument("--note")
    ls = sub.add_parser(
        "facts",
        help="a person's key facts, events and attributes with their ids, and every statement behind each with its id, status and record"
    )
    ls.add_argument("person")
    r = sub.add_parser(
        "reconsider",
        help="the rule re-examines every decision it made, every card still undecided and every conflict: a decision or a resolution it would no longer make is taken back, a card or a conflict it would now decide is decided"
    )
    r.add_argument("--dry-run", action="store_true", help="report only")
    l = sub.add_parser(
        "link", help="place a person in a family on your own word, on a record that stops short of naming both parties"
    )
    l.add_argument("person")
    g = l.add_mutually_exclusive_group(required=True)
    g.add_argument("--spouse")
    g.add_argument("--parent", action="append")
    l.add_argument("--record", required=True, help="sha256 of the archived record")
    l.add_argument("--note", required=True, help="your reason, kept on the assertion")
    l.add_argument("--marriage", help="the marriage date the record gives, GEDCOM form (14 AUG 1959)")
    d = sub.add_parser("divorce", help="a Divorce event between two people, with the evidence you name")
    d.add_argument("a")
    d.add_argument("b")
    d.add_argument("--date", help="GEDCOM form (BET 1950 AND 1959)")
    d.add_argument("--evidence", action="append", required=True, help="sha256[:persona fact id][:citation words]")
    d.add_argument("--note", required=True)
    mg = sub.add_parser(
        "merge",
        help="close a duplicate_person question: move the duplicate's evidence links onto the person it duplicates"
    )
    mg.add_argument("duplicate")
    mg.add_argument("--into", dest="kept", required=True)
    mg.add_argument("--note", required=True, help="why these are the same person, kept on the proposal")
    lv = sub.add_parser(
        "living",
        help="your own word on whether a person is alive, above the tier rule; unknown clears it so the rule decides again"
    )
    lv.add_argument("person")
    lv.add_argument("word", choices=["living", "deceased", "unknown"])
    lv.add_argument("--note", required=True, help="your reason, kept on the audit row")
    rs = sub.add_parser(
        "resolve",
        help="close a conflict question with your reason, the statement whose date or place the event keeps named; the others stay as their records say; over the rule's own resolution, yours stands"
    )
    rs.add_argument("question")
    rs.add_argument(
        "--keep", required=True, help="the assertion id of the statement kept (tools/conclude.py facts lists them)"
    )
    rs.add_argument("--note", required=True, help="your reason, kept on the question and the audit row")
    ro = sub.add_parser(
        "reopen",
        help="a conflict the rule resolved, taken back: the event's value as it was, the question open again and yours from now on"
    )
    ro.add_argument("question")
    ro.add_argument("--note", required=True, help="your reason, kept on the audit row")
    cp = sub.add_parser(
        "copies",
        help="your word that two archived files (or a listing's row, file@number) are copies of one record: one citation, one decision, every decision on either carried to the other"
    )
    cp.add_argument("a")
    cp.add_argument("b")
    cp.add_argument("--note", required=True, help="what the two share of the record, kept on the row")
    sp = sub.add_parser(
        "apart",
        help="your word that two archived files are not copies of one record, above anything code found: what a decision on one carried to the other is given back"
    )
    sp.add_argument("a")
    sp.add_argument("b")
    sp.add_argument("--note", required=True, help="why they are two records, kept on the row")
    for x in (dc, fc, ac, pc, ls, r, l, d, mg, lv, rs, ro, cp, sp):
        x.add_argument("--tree")
        x.add_argument("--db", default=DB)
        x.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree)
    cat = Catalog(cx, tree_id)
    cx.execute("BEGIN")
    try:
        if a.cmd == "decide":
            res = decide(
                cx,
                tree_id,
                a.proposal,
                "accepted" if a.verdict == "accept" else "rejected",
                a.by,
                note=a.note,
                choice=a.choice,
                kind=a.kind,
                alone=a.alone
            )
            if "error" in res:
                raise SystemExit(res["error"])
            if res.get("kind") == "place_resolution":
                print(res["summary"])
                for line in superseded_lines(res["rematched"]):
                    print("   ", line)
                cx.commit()
                return
            who = cx.execute("SELECT display_name FROM person WHERE id=?", (res["person"],)).fetchone()
            print(
                f"{res['status']}: {res['kind'].replace('_', ' ')} {who[0] if who else ''}; {res['assertions']} assertion(s), {len(res['memberships'])} family link(s), {len(res['answered'])} question(s) answered"
            )
            if res["links"]:
                print(
                    f"    {len(res['links'])} statement(s) of the family links this decision was one of the two acceptances for, rejected with it"
                )
            if res["status"] == "accepted" and res["identity"]:
                print(
                    "    an identity on a page anyone can edit: the link accepted; the family links and every fact it states are written undecided, never accepted"
                )
            if res["status"] == "accepted" and res["person"]:
                sha = cx.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (res["persona"],)).fetchone()[0]
                for f in record_says(cx, tree_id, res["person"], sha):
                    print(
                        f"    {f['status']:9} {f['fact']}"
                        + (f"  [conflict: {f['disagrees']}]" if f["disagrees"] else "")
                    )
            nm = lambda i: cx.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()[0]
            for m in res["memberships"]:
                if m.get("placed") == "sibling":
                    print(
                        "   ",
                        f"{nm(m['person'])} placed beside {nm(m['of'])} as a child of the same parents, undecided: the record states a sibling, not the parents"
                    )
                elif m.get("computed"):
                    print(
                        "   ",
                        f"{nm(m['person'])} {'child' if m['role'] == 'child' else 'spouse'} of {nm(m['of'])}: the record's indexer, not the record, states it, undecided"
                            + ("" if m["new"] else "; this record cited as evidence on the link")
                    )
                elif m.get("undecided"):
                    print(
                        "   ",
                        f"{nm(m['person'])} {'child' if m['role'] == 'child' else 'spouse'} of {nm(m['of'])}: a page anyone can edit states it, undecided"
                            + ("" if m["new"] else "; this record cited as evidence on the link")
                    )
                else:
                    print(
                        "   ",
                        f"{nm(m['person'])} {'child' if m['role'] == 'child' else 'spouse'} of {nm(m['of'])}: " + (
                            "a new link, on this record" if m["new"] else "this record accepted as evidence on the link"
                        )
                    )
            left = cx.execute(
                "SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND json_extract(payload_json,'$.artifact_sha256')=(SELECT json_extract(payload_json,'$.artifact_sha256') FROM proposal WHERE id=?)",
                (tree_id, a.proposal)
            ).fetchone()[0]
            print(
                f"    {left} card(s) still waiting on this record" if left else "    nothing else waits on this record"
            )
            for x in rule_conflict_decisions(res["conflicts"]):
                print("   ", rule_conflict_line(x))
            for line in superseded_lines(res["rematched"]):
                print("   ", line)
        elif a.cmd == "fact":
            from facts import decide_fact
            pid = cat.find_person(a.person)
            res = decide_fact(
                cx,
                tree_id,
                pid,
                a.field,
                {"accept": "accepted", "reject": "rejected", "undecided": "undecided"}[a.verdict],
                a.note,
                a.by
            )
            if "error" in res:
                raise SystemExit(res["error"])
            print(
                f"{a.field} {res['status']}: {res['assertions']} assertion(s) touched"
                + (f", {len(res['vouched'])} written on your own word" if res["vouched"] else "")
                + (f", {len(res['answered'])} question(s) answered" if res["answered"] else "")
            )
            from facts import evidence_rows
            for e in evidence_rows(cx, pid, a.field):
                print(
                    f"    {e['id'][-6:]} {e['status']:9} {e['tier'] or '-':5} {e['citation'] or ''}"
                    + (" (your own word)" if e["vouched"] else " (the file's uncited claim)" if e["uncited"] else "")
                )
            for line in superseded_lines(res["rematched"]):
                print("   ", line)
        elif a.cmd == "assertion":
            row = cx.execute(
                "SELECT id, subject_kind, subject_id, status, citation_text FROM assertion WHERE id=? AND tree_id=?",
                (a.assertion, tree_id)
            ).fetchone()
            if not row:
                raise SystemExit("no such assertion in this tree")
            status = {"accept": "accepted", "reject": "rejected", "undecided": "undecided"}[a.verdict]
            ts = now()
            # a person's own decision on this statement
            cx.execute(
                "UPDATE assertion SET status=?, asserted_by=?, asserted_at=?, person_decided=TRUE WHERE id=?",
                (status, a.by, ts, row["id"])
            )
            cx.execute(
                "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                (
                    ulid(),
                    tree_id,
                    ts,
                    a.by,
                    {"accepted": "accept", "rejected": "reject", "undecided": "update"}[status],
                    "assertion",
                    row["id"],
                    dumps(
                        {
                            "was": row["status"],
                            "now": status,
                            "subject": [row["subject_kind"], row["subject_id"]],
                            "note": a.note
                        }
                    )
                )
            )
            people = (
                [
                    r[0]
                    for r in cx.execute(
                        "SELECT person_id FROM event_participant WHERE event_id=? AND person_id IS NOT NULL",
                        (row["subject_id"],)
                    )
                ]
                if row["subject_kind"] == "event"
                else [row["subject_id"]]
                if row["subject_kind"] == "person"
                else [json.loads(row["subject_id"])[1]]
                if row["subject_kind"] == "family_member"
                else []
            )
            for pid in people:
                plan_person(cx, tree_id, pid, a.by)
            print(
                f"assertion {row['id'][-6:]} on {row['subject_kind']} ({row['citation_text'] or ''}): {row['status']} -> {status}; plan regenerated for {len(people)} person(s)"
            )
            for line in superseded_lines(rematch_people(cx, tree_id, a.by, people)):
                print("   ", line)
        elif a.cmd == "place":
            res = place(cx, tree_id, a.persona_fact, a.event, a.by, a.note)
            if "error" in res:
                raise SystemExit(res["error"])
            who = cx.execute("SELECT display_name FROM person WHERE id=?", (res["person"],)).fetchone()[0]
            moved = (
                f" (moved from event {res['moved_from']}" + (
                    "; that event, left with no statement but rejected ones, leaves the person"
                    if res.get("retired")
                    else ""
                ) + ")"
                if res.get("moved_from")
                else ""
            )
            print(
                f"persona fact {a.persona_fact[-6:]} placed on event {res['event']}{moved}: {res['status']}, {who} [{res['person'][-6:]}]; plan regenerated"
            )
            for line in superseded_lines(rematch_people(cx, tree_id, a.by, [res["person"]])):
                print("   ", line)
        elif a.cmd == "facts":
            from facts import KEY_FACTS, claimed_parts, evidence_rows, fact_status
            pid = cat.find_person(a.person)
            print(cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0], f"[{pid[-6:]}]")
            rows = [(f, f, None) for f in KEY_FACTS] + [
                (
                    f"event:{e['id']}",
                    f"{e['event_type'].lower()} {e['date_text'] or ''} {cat.place(e['id'], e['place_id'])['text'] if e['place_id'] else ''} {e['description'] or ''}".strip(),
                    e["id"]
                )
                for e in cx.execute("""SELECT e.id, e.event_type, e.date_text, e.place_id, e.description FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                                               WHERE ep.person_id=? AND e.event_type NOT IN ('Birth','Death') ORDER BY e.date_start, e.event_type""", (pid,))
            ]
            for field, label, eid in rows:
                st = fact_status(cx, pid, field)
                if st is None and eid is None:
                    print(f"  {label:11} no claim")
                    continue
                print(f"  {label[:60]:60} {st or '-':9}" + (f"  event:{eid}" if eid else ""))
                for part in claimed_parts(cat, pid, field):
                    print(f"      {part}")
                for e in evidence_rows(cx, pid, field):
                    print(
                        f"      {e['id']} {e['status']:9} {e['tier'] or '-':5} {(e['citation'] or '')[:60]}"
                        + (
                            " (your own word)"
                            if e["vouched"]
                            else " (the file's uncited claim)"
                            if e["uncited"]
                            else ""
                        )
                        + ("" if e["held"] else "  not held")
                    )
        elif a.cmd in ("copies", "apart"):
            x, y = copy_named(cx, a.a), copy_named(cx, a.b)
            for c in (x, y):
                if isinstance(c, str):
                    raise SystemExit(c)
            if x == y:
                raise SystemExit("one copy named twice")
            rows = copies_on_word(cx, tree_id, x, y, a.cmd == "copies", a.by, a.note)
            print(
                f"{a.a} and {a.b}: " + ("one record on your word" if a.cmd == "copies" else "two records on your word")
            )
            for r_ in rows:
                who = cx.execute("SELECT display_name FROM person WHERE id=?", (r_["person"],)).fetchone()[0]
                print(
                    "   ",
                    (
                        f"carried: {who} on {r_['copy'][:12]}, {r_['status']}"
                        + (f", kept {r_['kept']} as decided there" if r_.get("kept") else "")
                    )
                        if a.cmd == "copies"
                        else f"given back: {who} on {r_['copy'][:12]}, undecided again"
                )
        elif a.cmd == "reconsider":
            rows = reconsider(cx, tree_id, a.by, dry_run=a.dry_run)
            for x in rows:
                if x["kind"] in ("resolution", "conflict"):
                    verdict = (
                        ("kept" if x["kept"] else "would take back" if a.dry_run else "taken back")
                        if x["kind"] == "resolution"
                        else ("would resolve" if a.dry_run else "resolved")
                        if x["taken"]
                        else "left to you"
                    )
                    print(
                        f"{verdict:19} {x['person']} [{x['question'][-6:] if x['question'] else 'no question yet'}] {x['detail']}: {x['why']}"
                    )
                    continue
                verdict = (
                    ("would carry" if a.dry_run else "carried")
                    if x["kind"] == "carried" and x["taken"]
                    else "kept apart"
                    if x["kind"] == "carried"
                    else ("kept" if x["kept"] else "would withdraw" if a.dry_run else "withdrawn")
                    if x["kind"] == "decision"
                    else ("would supersede" if a.dry_run else "superseded")
                    if x["kind"] == "rematch"
                    else ("would rewrite" if a.dry_run else "rewritten")
                    if x["kind"] == "rationale"
                    else ("would take" if x["taken"] and a.dry_run else "taken" if x["taken"] else "refused")
                )
                print(f"{verdict:19} {x['person']} <- {x['persona']} [{x['proposal'][-6:]}]: {x['why']}")
            if not rows:
                print("the rule has made no decision in this tree, and no card or conflict waits")
            else:
                print(
                    f"{sum(1 for x in rows if x['kind'] == 'carried' and x['taken'])} decision(s) {'it would carry' if a.dry_run else 'carried'} to another copy of their record, "
                    f"{sum(1 for x in rows if x['kind'] == 'decision')} decision(s) examined, {sum(1 for x in rows if x['kind'] == 'rematch')} card(s) {'it would supersede' if a.dry_run else 'superseded'} and their records matched again, "
                    f"{sum(1 for x in rows if x['kind'] == 'rationale')} rationale(s) {'it would rewrite' if a.dry_run else 'rewritten'}, "
                    f"{sum(1 for x in rows if x['kind'] == 'card' and x['taken'])} card(s) {'it would take' if a.dry_run else 'taken'}, "
                    f"{sum(1 for x in rows if x['kind'] == 'card' and not x['taken'])} refused, "
                    f"{sum(1 for x in rows if x['kind'] == 'resolution' and not x['kept'])} of {sum(1 for x in rows if x['kind'] == 'resolution')} resolution(s) {'it would take back' if a.dry_run else 'taken back'}, "
                    f"{sum(1 for x in rows if x['kind'] == 'conflict' and x['taken'])} conflict(s) {'it would resolve' if a.dry_run else 'resolved'}, "
                    f"{sum(1 for x in rows if x['kind'] == 'conflict' and not x['taken'])} left to you"
                )
        elif a.cmd == "link":
            pid = cat.find_person(a.person)
            marriage = None
            if a.marriage:
                marriage = {
                    "date_text": a.marriage,
                    **{k: v for k, v in parse_gedcom_date(a.marriage).items() if k != "calendar"}
                }
            if marriage:
                marriage["qualifier"] = marriage.pop("date_qualifier")
            if a.spouse:
                fid = link_on_word(
                    cx, tree_id, pid, cat.find_person(a.spouse), "spouse", a.record, a.by, a.note, marriage=marriage
                )
            else:
                fid = link_on_word(
                    cx, tree_id, pid, [cat.find_person(x) for x in a.parent], "child", a.record, a.by, a.note
                )
            print(f"family {fid}: {a.person} placed on your word; the record {a.record[:12]} carries the assertion")
            for line in superseded_lines(
                rematch_people(
                    cx,
                    tree_id,
                    a.by,
                    [r[0] for r in cx.execute("SELECT person_id FROM family_member WHERE family_id=?", (fid,))]
                )
            ):
                print("   ", line)
        elif a.cmd == "divorce":
            ev = []
            for e in a.evidence:
                parts = e.split(":", 2)
                ev.append(
                    (
                        parts[0],
                        parts[1] or None if len(parts) > 1 else None,
                        parts[2] if len(parts) > 2 else "the record's own words"
                    )
                )
            eid = divorce(cx, tree_id, cat.find_person(a.a), cat.find_person(a.b), a.date, ev, a.by, a.note)
            print(f"divorce event {eid} between {a.a} and {a.b}")
            for line in superseded_lines(
                rematch_people(cx, tree_id, a.by, [cat.find_person(a.a), cat.find_person(a.b)])
            ):
                print("   ", line)
        elif a.cmd == "resolve":
            res = resolve(cx, tree_id, a.question, a.keep, a.by, a.note)
            if "error" in res:
                raise SystemExit(res["error"])
            print(
                f"resolved: the event's {res['axis']} is now {res['kept']['value']} ({res['kept']['record']}); set aside, as their records say: "
                + ("; ".join(f"{s['value']} ({s['record']})" for s in res["set_aside"]) or "nothing")
                + f"; {len(res['questions_closed'])} question(s) closed"
            )
            for line in superseded_lines(
                rematch_people(
                    cx,
                    tree_id,
                    a.by,
                    [
                        cx.execute(
                            "SELECT subject_person_id FROM research_question WHERE id=?", (a.question,)
                        ).fetchone()[0]
                    ]
                )
            ):
                print("   ", line)
        elif a.cmd == "reopen":
            res = reopen(cx, tree_id, a.question, a.by, a.note)
            if "error" in res:
                raise SystemExit(res["error"])
            was = res["restored"].get("date_text") if res["axis"] == "date" else res["restored"].get("place")
            print(
                f"reopened: the rule's resolution taken back, the event's {res['axis']} {was or 'empty'} again; the question is "
                + ("open" if res["open"] else "closed: the difference no longer reads as it did")
                + f"; the rule leaves this {res['axis']} to you from now on"
            )
            for line in superseded_lines(
                rematch_people(
                    cx,
                    tree_id,
                    a.by,
                    [
                        cx.execute(
                            "SELECT subject_person_id FROM research_question WHERE id=?", (a.question,)
                        ).fetchone()[0]
                    ]
                )
            ):
                print("   ", line)
        elif a.cmd == "living":
            pid = cat.find_person(a.person)
            res = living(cx, tree_id, pid, a.word, a.by, a.note)
            print(
                f"{cx.execute('SELECT display_name FROM person WHERE id=?', (pid,)).fetchone()[0]} [{pid[-6:]}]: living_override {res['was'] or 'none'} -> {res['now'] or 'none'}; "
                f"the default now reads {res['status']} ({res['reason']}); the plan next: tools/plan.py"
            )
        else:
            kept_id = cat.find_person(a.kept)
            # a duplicate already merged into this person is named among those merged into them, by name or six characters
            six = re.search(r"\[([A-Z0-9]{6})\]\s*$", a.duplicate)
            already = [
                i
                for i, n in cx.execute(
                    "SELECT id, display_name FROM person WHERE tree_id=? AND merged_into=?", (tree_id, kept_id)
                )
                if n == a.duplicate or (six and i.endswith(six.group(1)))
            ]
            res = merge(
                cx, tree_id, already[0] if len(already) == 1 else cat.find_person(a.duplicate), kept_id, a.by, a.note
            )
            if res.get("completed"):
                print(
                    f"{a.duplicate} already merged into {a.kept}; completed: {res['events_folded']} event(s) folded ({res['event_assertions_folded']} statement(s) moved), "
                    f"{res['families_folded']} family(ies) folded ({res['family_children_moved']} child membership(s), {res['family_events_moved']} family event(s))"
                )
            else:
                print(
                    f"{a.duplicate} merged into {a.kept}: {res['persona_links']} persona link(s), {res['assertions']} assertion(s), "
                    f"{res['event_participants']} event participant(s), {res['family_memberships']} family membership(s), "
                    f"{res['plan_steps_moved']} plan step(s) moved ({res['plan_steps_dropped']} dropped as already on the kept person's plan, "
                    f"{res['log_rows_carried']} run(s) carried onto it), {res['questions_moved']} question(s) moved "
                    f"({res['questions_dropped']} already open on the kept person), {res['questions_answered']} duplicate question(s) answered; proposal {res['proposal']}"
                )
            for line in superseded_lines(rematch_people(cx, tree_id, a.by, [kept_id])):
                print("   ", line)
        cx.commit()
    except Exception:
        cx.rollback()
        raise

if __name__ == "__main__":
    main()
