#!/usr/bin/env python3
"""The standing rule's tests: whether a record is a person's on its points, whether its identity holds, and what the tree's
statements it may stand on are. Read-only: nothing here writes the catalog. The decisions (tools/decisions.py) take what the
rule accepts; tools/conclude.py is the command line.

The standing rule (docs/TERMS.md §0 and docs/RULE.md, rule_accepts): a record of a kind data/evidence-classes.csv gives
the automated standing, from a source nobody can edit at will (T1–T3), is accepted as the person's when the name agrees with
the accepted name, the facts that agree make two points on the tree's own statements (ground: a date to the day or a
relationship counting double whatever its information class, a statement of any copy of the record, or of the same person's
record of the same event from the same original, no ground) and nothing compared disagrees against an accepted value
(against, split_disagree). A page anyone can edit (T4: a Find a Grave memorial, a WikiTree profile) identifies a person but
never builds their facts: the rule takes such an identity on the name and three of birth day, death day, burial place, a
stated parent or spouse, the relatives the page lists one of the four at most and only one the tree links so, claimed or
accepted (claimed_or_accepted, event_claimed_or_accepted). A new person is created by the rule when a trusted record (T1–T2,
or an obituary once read) names them with a name in a family relationship it states to a person accepted on that record and
nobody in the tree fits after the fitting check (rule_creates); a creation is judged on its record's current reading by those
same terms, and a card putting the entry it made a person from to that person is judged as that creation (made_here).
Whatever the route, identity is tested before the rule takes a record or creates a person from it (identity_refused,
docs/DATA-ARCHITECTURE.md §7 decision 12): nobody else of the tree fits the persona as well (fits_as_well), the person holds no
other persona on that reading of the record, and nothing the record would add falls outside the person's accepted life
(outside_life, data/life-limits.csv); a test that fails is a refusal with its reason. Anything less certain is a card for the
owner.

- rule_accepts: whether the rule takes a proposal, and why or why not, in words: on its points (rule_points), then identity
  tested (identity_refused: fits_as_well, a second persona on the reading, outside_life); ground: the tree's statements a
  point stands on; trusted_evidence, whether an accepted statement rests on a trusted source or the owner's own word.
- record_self and copy_cards: the record under decision as the rule counts it, once (one record is one source wherever it is
  held, docs/DATA-ARCHITECTURE.md §7 decision 15), and as every copy holds it; record_keys, cites_record, rests_elsewhere and
  not_the_files_word, the one-source test's parts.
- same_personas: a decision, a withdrawal or a rejection applies to every reading's persona of that entry of the record (its
  record id, else its role, row and name), never to another row of the same name.
- links_resting_on: the statements a withdrawal or a person's rejection of a decision takes back besides its own, the family
  links the decision was one of the two acceptances for.
- resolve_in_law: the real family link an in-law's stated tie resolves to, read by the decisions' link_family and by
  rule_creates alike; IN_LAW, the kinds.
- editable: whether an artifact is a page anyone can edit; TRUSTED, the tiers the rule may act on; RULE_ACTOR, the rule as
  the decider, by what it did; the SQL fragments a decision and a withdrawal share (TRUSTED_ARTIFACT, ACCEPTED_WITH_RECORD).
"""
import json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import dumps
from catalog import (
    Catalog,
    Finding,
    MARKS,
    MEMBERSHIPS,
    RECORD_FACTS,
    current_entry,
    date_span,
    date_verdict,
    evidence_classes,
    files_word,
    holds,
    key as surname_key,
    latest_reading,
    life_limits,
    marked,
    not_withdrawn,
    notes_of,
    page_entries,
    parent_limit,
    place_verdict,
    record_kinds,
    record_original,
    record_standing,
    relation_classes,
    source_tier,
    split_persona_name,
    tier_sql,
    withdrawals
)
from match import MATCHER, REL_OF, candidate, compare, personas_of, said
from forms import census_form

# the kind (data/evidence-classes.csv) that identifies a person only through who it names (docs/TERMS.md §0: "then the named survivors decide"): the rule's ground there is a stated relative, never a date or a place alone
NAMED_SURVIVORS = "obituary"

# a census before this year names the head and counts the rest: a hint (docs/TERMS.md §0)
CENSUS = "census household"   # a census is ground only on a form data/record-forms.csv says names every member (forms.census_form)

# a register entry identifies a person only when it is dated and names their parents (docs/TERMS.md §0)
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
# a card or a decision whose entry the record's current reading has no persona of (a corrected reader no longer reads that row)
NO_LONGER_READ = "the current reading no longer has this entry (the page read again gives no persona of it)"

RULE_ACTOR = {
    "persona_match": "rule:agrees-with-accepted",
    "new_person": "rule:creates-named-relative",
    "conflict": "rule:classes-favour-one-side"
}
# An artifact's source is read from its own identity first (an ark is FamilySearch, a memorial id is Find a Grave), then from the row it was archived under (catalog.tier_sql).

def unless(without):
    """The SQL leaving out of a reading of assertion a the statements reconsider does not count, and its arguments: every
    statement a decision in without wrote, and every statement whose own id is in without (a family link a withdrawal earlier
    in the same pass takes back: links_resting_on).
    Implements [rule.reconsider.5]."""
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
    placement, a value the page keeps beneath, a link the indexer computed) never counts, whatever its status, nor does one
    resting on a withdrawn file (catalog.not_withdrawn: evidence for nothing). without: proposal ids whose assertions do not
    count (a rule decision under reconsideration and every rule decision after it), and statements that do not (unless).
    Implements [rule.standing.3], [rule.points.4], [rule.points.8], [rule.points.9]."""
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
                         WHERE a.tree_id=? AND a.subject_kind=? AND a.subject_id=? AND a.status='accepted' AND NOT {marked()} AND {not_withdrawn('a.artifact_sha256')} {skip} {full}
                         AND (substr({tier_sql()},1,2) IN ('T1','T2','T3') OR (json_valid(a.notes) AND (json_extract(a.notes,'$.vouched')=1 OR json_extract(a.notes,'$.uncited')=1)))""", (tree_id, kind, sid, *skipped)).fetchone():
            return True
    return False

def record_keys(cx, sha, copies=()):
    """What identifies a record for a citation to name it: the record ids it holds (catalog.holds, its own apid first), its
    memorial ids and its URL, and the same of every other copy of the record given (same_record).
    Implements [rule.points.14]."""
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
    own persons, on any copy.
    Implements [rule.points.12], [rule.points.14]."""
    from catalog import copy_entry, record_copies, record_owners
    shas = {c[0] for c in record_copies(cx, tree_id, *copy_entry(cx, persona_id))} | {sha}
    own = not cx.execute("SELECT 1 FROM persona_relation WHERE persona_id=?", (persona_id,)).fetchone()
    owners = {pid} if own and pid else set().union(*(record_owners(cx, tree_id, s) for s in shas))
    return {"copies": shas, "original": record_original(cx, sha), "year": record_kinds(cx, sha)[1], "owners": owners}

def cites_record(notes, keys):
    """Whether a statement's own citation (an imported claim's notes: its record id and URL) is the record these keys name.
    Implements [rule.points.14]."""
    apids, memorials, urls = keys
    url = notes.get("url") or ""
    m = re.search(r"/memorial/(\d+)(?:/|$)", url)
    return bool(
        (notes.get("apid") and notes["apid"] in apids) or (m and m.group(1) in memorials) or (url and url in urls)
    )

def rests_elsewhere(cx, eid, sha, axis, value, keys=None, copies=()):
    """Whether the event's value that a related persona's value agrees with stands on some statement other than the record
    under decision, so that the persona stands for the tree's relative on more than the relationship the record states
    (rule_points, grounded): a statement on the event that is not rejected, not the record's own (on any of its copies), not
    a claim whose own citation is that record (docs/RULE.md, the proof standard: such a claim never counts) and
    resting on no withdrawn file, giving a date or a place that agrees with value (gives).
    Implements [rule.points.13], [rule.points.14]."""
    q = _q(cx)
    keys = keys or record_keys(cx, sha)
    ev = q.execute("SELECT date_text, date_start, date_end, date_qualifier FROM event WHERE id=?", (eid,)).fetchone()
    for r in q.execute(f"""SELECT {STATEMENT_COLUMNS} FROM assertion a {STATEMENT_JOINS}
                           WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected'""", (eid,)):
        if r["artifact_sha256"] == sha or r["artifact_sha256"] in copies or r["withdrawn"]:
            continue
        if cites_record(_notes(r), keys):
            continue
        if gives(ev, r, axis, value):
            return True
    return False

# a statement on an event as gives() reads it, and whether it rests on a withdrawn file (catalog.not_withdrawn)
STATEMENT_COLUMNS = ("a.id, a.status, a.artifact_sha256, a.notes, a.persona_fact_id, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw, "
                     f"NOT {not_withdrawn('a.artifact_sha256')} AS withdrawn")

STATEMENT_JOINS = (
    "LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id"
)

def _notes(r):
    """An assertion row's notes as a dict (catalog.notes_of)."""
    return notes_of(r["notes"])

def gives(ev, r, axis, value, day=False):
    """Whether a statement on an event (r: STATEMENT_COLUMNS; ev: the event's own date fields) gives a date that agrees with
    value (to the day, with day) or a place that does. A statement with no record fact of its own (the owner's word) stands
    for the event's own date and gives no place.
    Implements [rule.value.6]."""
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
    claimed or accepted for the record under decision, or None when it stands: catalog.files_word (the file's claim, the
    import's own statement not rejected; with claim_only that alone, otherwise an accepted statement too; never one carrying
    one of the MARKS, nor one resting on a withdrawn file, "withdrawn"), and never one from the record under decision on any
    of its copies (rec: record_self, "self"), one a
    decision in without wrote or one in without itself (reconsider, unless: "without"), or a claim whose own citation is
    that record (keys: record_keys, "cites").
    Implements [rule.terms.2], [rule.relation.2], [rule.points.14]."""
    notes = _notes(r)
    if r["artifact_sha256"] in rec["copies"]:
        return "self"
    word = files_word(r["status"], notes, r["imported"], claim_only, withdrawn=r["withdrawn"])
    if word in MARKS:
        return word
    if r["id"] in without or notes.get("proposal") in without:
        return "without"
    if r["imported"] and cites_record(notes, keys):
        return "cites"
    return word

def ground(cx, tree_id, kind, ids, sha, rec, axis=None, value=None, tree=None, without=()):
    """The tree's statements the standing rule may stand on for one point about the record under decision (sha; rec, what it
    is: record_self): accepted assertions on these subjects (the event compared, or the memberships joining two people)
    resting on a trusted source (T1–T3) or on the owner's own word (a vouch, or the file's uncited claim the owner accepted),
    never a statement carrying one of the MARKS (a sibling placement, a value the page keeps beneath, a link the indexer
    computed) or resting on a withdrawn file (catalog.not_withdrawn), the record itself on any of its copies (same_record:
    one record is one source wherever it is held), a claim whose own citation is it, or a statement from the same original about the same person's same event: a record whose classes
    name the same original (catalog.evidence_classes, record_original), the record of the same person (record_owners) and,
    where both give one, of the same year, which the code cannot show to be another copy of it and still counts once with it
    (two indexes of one certificate, two papers' obituaries of one death), never by the kind alone, which two people's
    records share. With axis, the statement must give a date or a place that agrees with value, a date whatever the event
    itself shows (docs/RULE.md, what of an event's value is accepted), a place at the level of the tree's
    own (tree), so the place the event shows is given whole by the statement; never one a standing resolution set aside
    (catalog.set_aside); a vouch standing for the event's own date and place. without: proposal ids whose assertions do
    not count, and statements that do not (reconsider, unless). Returns (statements, shared): each statement {day: it gives
    value's very day, information: its information class in words, or the owner's own word}, and in words what was left out
    as one source with the record.
    Implements [rule.standing.3], [rule.value.3], [rule.value.6], [rule.points.4], [rule.points.8], [rule.points.9], [rule.points.12], [rule.points.14]."""
    from catalog import record_owners, set_aside
    q = _q(cx)
    keys = record_keys(cx, sha, rec["copies"])
    cat = Catalog(cx, tree_id)
    out, shared = [], []
    seen, aside = {}, {}
    def same_original(s, c):
        """Whether a statement's record (s), whose classes are c, is the same person's record of the same event as the one under decision.
        Implements [rule.points.12]."""
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
                               WHERE a.tree_id=? AND a.subject_kind=? AND a.subject_id=? AND a.status='accepted' AND NOT {marked()} AND {not_withdrawn('a.artifact_sha256')} {skip}
                               ORDER BY a.asserted_at, a.id""", (tree_id, kind, sid, *skipped)).fetchall():
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
    persona link and the family links it states; its facts are written Undecided, never accepted by the decision.
    Implements [rule.editable.1], [rule.editable.7]."""
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
    readers of accepted links join on current extractions only.
    Implements [rule.copies.1]."""
    sha = cx.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()[0]
    entries = page_entries(cx, sha)
    k = next(key for pid, _, _, _, key in entries if pid == persona_id)
    return [pid for pid, _, _, _, key in entries if key == k]

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

def _stands_for(cat, persona, cand, chosen):
    """Whether a persona on a page anyone can edit stands for a person of the tree as the relative the identity rule may count:
    it fits the person, or the given name and the surname agree and nothing compared disagrees (a memorial lists a relative by
    name and years alone), its name read as the rule stands on one (the name rows and the accepted aliases).
    Implements [rule.editable.10]."""
    fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen, accepted_names=True)
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
    qualifier}; a place, its words): what the standing rule refuses a record on (docs/RULE.md, what of an
    event's value is accepted), whatever the event itself shows, so a claim the event shows never vetoes, and a record that
    agrees with that claim is still refused where an accepted statement gives another value. A statement counts when it is
    accepted, of the event's own type, carries no mark (MARKS), rests on no withdrawn file (catalog.not_withdrawn) and is not
    one a standing resolution set aside (catalog.set_aside); the owner's own word with no record fact of its own (a vouch:
    facts.vouch) stands for the event's own date as it stands, and gives no place. A place is compared as the place the statement's words are resolved to when
    they are, and disagrees when neither agrees with the other (catalog.place_verdict, a bare county on the record read
    with record_state, the state of its own collection), unless both name parts of the event's own place, neither inside it,
    as Catalog.disagreements reads two such statements (a death index's state and an obituary's town written without it are
    parts of one place). primary: only a statement holding primary information
    (catalog.evidence_classes), the owner's word not among them. without: proposal ids whose statements do not count, and
    statements that do not (reconsider, unless). Returns [(assertion id, the value it gives in words, its record in words)].
    Implements [rule.value.3], [rule.value.7], [rule.value.8], [rule.points.8], [rule.points.9]."""
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
                         WHERE a.subject_kind='event' AND a.subject_id=? AND a.status='accepted' AND NOT {marked()} AND {not_withdrawn('a.artifact_sha256')} {skip}
                         ORDER BY a.asserted_at, a.id""", (eid, *skipped)).fetchall()
    shown = (cat.place(eid, ev["place_id"]) or {}).get("text") if axis == "place" else None
    def part(p, state=None):
        """Whether a place names a part of the event's own place, not a place inside it.
        Implements [rule.value.8]."""
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
    the other's. A link the file only claims, or no link at all, holds nothing against the record.
    Implements [rule.points.2]."""
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
    the event shows, which may itself be a claim (docs/RULE.md, what of an event's value is accepted):
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
    each a list of findings (catalog.Finding, in words by match.said), a contradiction among the conflicts.
    Implements [rule.points.2], [rule.value.7], [rule.value.9], [rule.editable.11]."""
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

def claimed_or_accepted(cx, tree_id, pid, other, group, rec, keys, without=(), claim_only=False):
    """Whether the tree links a person to another by a relation group (parents, children, spouses, siblings), claimed or
    accepted (docs/RULE.md), as Catalog.linked_on_word reads a link, for the record under decision: in a
    family joining the two, the membership of each carries an accepted statement or the file's claim of it, the import's own
    statement (on a file this tree imported, tree_import), not rejected; with claim_only, the file's claim alone. Nothing
    else is the file's word: an undecided statement from a page anyone can edit or a link a withdrawn decision left claims
    nothing, and an indexer's grouping, a sibling placement (MARKS) or a statement resting on a withdrawn file nothing
    whatever its status. A statement from the
    record under decision on any of its copies (rec: record_self), a claim whose own citation is that record (keys:
    record_keys), one a decision in without wrote and one in without itself (reconsider, unless) never count
    (not_the_files_word).
    Implements [rule.terms.2], [rule.relation.2]."""
    q = _q(cx)
    mine, theirs = MEMBERSHIPS[group]
    def stands(fid, who, role):
        return any(not_the_files_word(r, rec, keys, without, claim_only) is None for r in q.execute(f"""SELECT a.id, a.status, a.artifact_sha256, a.notes, a.artifact_sha256 IN (SELECT artifact_sha256 FROM tree_import WHERE tree_id=?) AS imported,
                                          NOT {not_withdrawn('a.artifact_sha256')} AS withdrawn
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
    "withdrawn": "a statement on a withdrawn record",
    "editable": "an undecided fact another page anyone can edit types",
    "aside": "a statement the event's value was decided against"
}

def event_claimed_or_accepted(cx, tree_id, eid, axis, value, rec, keys, without=(), day=False):
    """Whether the tree holds the date or the place of an event that a page anyone can edit agrees with, claimed or accepted
    (docs/RULE.md, the identity), as claimed_or_accepted reads a link: a statement on the event that
    stands (not_the_files_word) and gives value (gives; to the day, with day), whatever the event itself shows, never one a
    standing resolution set aside (catalog.set_aside). Returns (True, []), or (False, what the statements not rejected that
    give value but do not stand are, in words: LEFT_OUT).
    Implements [rule.editable.9]."""
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
    links to the candidate by that relation, claimed or accepted (docs/RULE.md): (group, other candidate,
    other name) when so, else None. relations: (kind, other persona, computed, other name), a relationship the record's
    indexer computed being no statement of the record's. accepted_on_record: persona id -> candidate, from person_persona
    rows already decided accepted on this extraction — not the fitting check's own guesses. linked(group, other person id):
    whether the tree links the two so (claimed_or_accepted).
    Implements [rule.relation.1]."""
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
    child-parent relationship between two of its personas is one the record states (catalog.relation_classes).
    Implements [rule.standing.6]."""
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
    (catalog.entry_on), each with the file it stands on.
    Implements [rule.copies.4]."""
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

def rule_accepts(cx, tree_id, prop, without=()):
    """Whether the standing rule takes a proposal, and why, in words: (True, reason) or (False, why not), as
    docs/RULE.md states the rule ("The standing rule", and "What the rule counts" in the proof standard):
    the record taken on its points (rule_points), and then identity tested, not assumed (identity_refused): nobody else of
    the tree fits the persona as well, the person holds no other persona on this reading of the record, and nothing the
    record would add falls outside the person's life as accepted. A test that fails is a refusal with its reason, and the
    card stays the owner's. The record is every copy of it (copy_cards): it is taken on the points of the copy that earns
    them, and refused when any copy's persona of the entry disagrees against an accepted value or fails the identity
    tests, the reason naming that copy. A card putting an entry to the person a creation made from that very entry, which
    no route above takes and nothing vetoes, is judged as that creation (made_here): on the creation's own terms and its
    identity test, the person it made not counted.
    Implements [rule.standing.2], [rule.identity.1], [rule.copies.4], [rule.relation.5]."""
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
    """The creation a card stands for (docs/RULE.md, the creation route): when a persona_match card puts an
    entry of a record to the person a creation made from that very entry (a new_person proposal of that person on any
    reading's persona of the entry, on any copy of the record, that no person rejected: standing, taken back, or closed with
    its reading as superseded), the card as that creation, a new_person proposal of the person on the card's own persona and
    reading, the creation's id as payload made; else None.
    Implements [rule.relation.5]."""
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
    beside it, so a decision written on an earlier reading is examined on what the record now reads as, and one whose entry
    that reading no longer has is refused as no longer read (NO_LONGER_READ), never judged on the superseded persona. A trusted record (T1–T3) of
    an automated kind is taken on the accepted name (the name rows and the accepted aliases, never an undecided one: compare's
    accepted_names, here and for the relatives the record names) and two points, nothing disagreeing against an accepted value
    (split_disagree); each point stands on the tree's own statements as ground() finds them, whatever value the event shows
    beside them (docs/RULE.md, what of an event's value is accepted), and a date to the day or a
    relationship counts double where the tree holds it on such ground, whatever its information class (the classes decide
    conflicts, not whether two records that agree are about one person); a link no such statement grounds counts once where
    the file itself claims it, and nothing else stands in for the file (claimed_or_accepted). A persona whose
    name the tree does not hold on such ground is taken only through a relationship the record states to a persona already
    accepted on it whom the tree links to the candidate so, claimed or accepted (claimed_or_accepted). A page anyone can edit
    (T4) of an identity kind gives the identity alone, on the name and three of birth day, death day, burial place and one
    stated parent or spouse whom the tree links so, each claimed or accepted (event_claimed_or_accepted, claimed_or_accepted),
    a claim citing the page not among them, however many relatives it lists, the reason naming what it left out; a child or
    a sibling is none of the four. A record withdrawn from the evidence (tools/tombstone.py) is refused whatever it states:
    its statements are evidence for nothing, so the owner decides it. without: proposal ids whose
    assertions and persona links are not ground (reconsider); a name accepted on nothing outside them is judged by the
    relationship route, as it was taken.
    Implements [rule.standing.3], [rule.standing.4], [rule.standing.5], [rule.standing.6], [rule.standing.7], [rule.standing.8], [rule.points.1], [rule.points.2], [rule.points.3], [rule.points.4], [rule.points.5], [rule.points.7], [rule.points.9], [rule.points.11], [rule.points.13], [rule.name.1], [rule.value.6], [rule.relation.1], [rule.relation.3], [rule.editable.2], [rule.editable.8], [rule.editable.10]."""
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
    gone = withdrawals(cx, [sha]).get(sha)
    if gone:
        return False, f"the record was withdrawn from the evidence on {gone['at'][:10]} ({gone['reason']}): its statements are evidence for nothing, the owner decides it", []
    eid = latest_reading(cx, pay["extraction_id"])
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
        form = census_form(coll, int(yr)) if CENSUS in kinds and yr else None
        if CENSUS in kinds and yr and form is None:
            return False, f"data/record-forms.csv holds no form of the {yr} census, so whether it names every member is unread: a person reads it", []
        if form and form["names"] == "head":
            return False, f"the {yr} census names only the head (data/record-forms.csv, {form['id']})", []
        if by_kind == DATED_WITH_PARENTS and not dated_with_parents(cx, eid):
            return (
                False,
                "a church register entry is a hint until a person reads it, unless it is dated and names the parents",
                []
            )
    cat = Catalog(cx, tree_id)
    # the record as its current reading gives it: the persona of the same entry there
    cur = current_entry(cx, pay["persona_id"])
    if not cur:
        return False, f"{NO_LONGER_READ}: the owner decides it", []
    reading, persona_id = eid, cur
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
        # its relation to the persona under decision, stated from either side, is one of the things it fits on (docs/RULE.md)
        as_related = {**other, "relations": both_ways(other)}
        for c in relatives:
            # a birth place, never a veto, never unfits a relative either: the rule's decisions do not turn on a finer place another decision brought
            fits, agree, disagree, absent, near = compare(cat, as_related, c, {persona["id"]: cand}, birth_place=False, accepted_names=True)
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
        year) that rests on more than a claim citing this very record (docs/RULE.md, the proof standard). A
        persona that fits only through its relation to the one under decision, a name and the relationship, earns nothing:
        the relationship would be its own proof.
        Implements [rule.points.13]."""
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
    fits, agree, disagree, absent, near = compare(cat, persona, cand, chosen, accepted_names=True)
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
            the event shows; otherwise what was left out, said when something gave the value or the event shows it (shown).
            Implements [rule.editable.9]."""
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
    """Whether the rule creates the person a new_person card proposes, and why, in words (docs/RULE.md): a
    trusted record (T1–T2, or an obituary once read) names them, with a name, in a stated family relationship (child, parent,
    spouse, sibling, half sibling, grandchild, in-law; never "other relative" or a blank; one the record's indexer computed is
    no statement of the record's, catalog.relation_classes) to a person accepted on the same record, and nobody in the tree
    fits after the fitting check — the matcher's own word, so a card an older matcher wrote is left for reconsider to propose
    again (rematch), and the check run once more across the whole tree as it stands when the rule decides (identity_refused). A page
    anyone can edit names a person but never creates one: the owner does. A creation is judged on the persona its record's
    current reading gives the entry (rule_points), and a card the creation stands for (made_here) on the same terms: the
    matcher has put that persona to the person, so its word is not asked again, and the creation stands on the entry.
    Implements [rule.relation.4], [rule.relation.5]."""
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
    (the owner's word) stands for the event's own date; one resting on a withdrawn file (catalog.not_withdrawn) says nothing.
    without: proposal ids whose statements do not count, and statements that do not (reconsider, unless).
    Implements [rule.identity.3], [rule.points.9]."""
    skip, skipped = unless(without)
    spans, words = [], []
    for r in _q(cx).execute(f"""SELECT a.persona_fact_id, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, e.date_text AS ev_text, e.date_start AS ev_start, e.date_end AS ev_end, e.date_qualifier AS ev_q
                                FROM assertion a JOIN event e ON e.id=a.subject_id JOIN event_participant ep ON ep.event_id=e.id LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                WHERE a.tree_id=? AND a.subject_kind='event' AND a.status='accepted' AND {not_withdrawn('a.artifact_sha256')} AND ep.person_id=? AND e.event_type=? {skip}
                                ORDER BY a.asserted_at, a.id""", (tree_id, pid, etype, *skipped)):
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
    """What a persona's own record says of an event type's date: (earliest, latest, words), or None.
    Implements [rule.identity.3]."""
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
    accepted as them, so only those persons are compared. Names are read as the matcher reads them, every alias not rejected:
    a wider name here only refuses more.
    Implements [rule.identity.1], [rule.name.3]."""
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
    record's alone.
    Implements [rule.identity.3]."""
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
    (docs/DATA-ARCHITECTURE.md §7 decision 12, docs/RULE.md). Three tests, each a refusal naming what it
    found: another person of the tree fits the persona as well as the candidate or better (fits_as_well; for a person the
    rule would create, anyone who fits, or whom the fitting check reaches, match.by_name_and_year); the person already holds
    another persona on this reading of the record (two rows of one page are two people); something the record would add
    falls outside the person's life as accepted (outside_life). The persona tested is the one of the same entry on the
    record's current reading (catalog.current_entry), with the facts and relationships that reading gives, as rule_points
    judges it; an entry that reading no longer has is refused as no longer read (NO_LONGER_READ). A person created by a decision under reconsideration (without) or by this one is no other person, nor is
    one accepted as another persona on this reading. without: proposal ids whose assertions and links do not count
    (reconsider).
    Implements [rule.identity.1], [rule.identity.2], [rule.identity.3], [rule.relation.6]."""
    from match import by_name_and_year
    q = _q(cx)
    pay = json.loads(prop["payload_json"])
    cat = Catalog(cx, tree_id)
    ext = latest_reading(cx, pay["extraction_id"])
    cur = current_entry(cx, pay["persona_id"])
    if not cur:
        return NO_LONGER_READ
    reading, persona_id = ext, cur
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

def links_resting_on(cx, tree_id, prop_id, gone=(), taken_back=False):
    """The statements a withdrawal or a person's rejection of this decision takes back besides its own
    (docs/RULE.md): a family link the record states stands on both people it relates being accepted on the
    record, and is written by the second of the two acceptances (link_family), so it is the other decision's statement.
    Taken back: each accepted statement of a membership joining this decision's person to a person accepted on another
    persona of the record, written from a relationship the record states between that persona and this decision's entry (on
    any reading or copy of it), the relationship's own word its citation (an in-law's tie resolved through this decision's
    person included), unless another pair of personas accepted on the record states the same link in the same word; and with
    a spouse link that goes, the facts the same decision wrote on the couple's family from the record
    (assert_family_events). A statement whose status a person decided on its own (person_decided), one written undecided
    (ACCEPTED_WITH_RECORD) and this decision's own are never among them. gone: decisions already withdrawn in this pass
    (reconsider), read as not accepted. taken_back: the undecided statements a withdrawal of this decision left are among
    them too, for a person's rejection of a card whose decision the rule took back. Returns the assertion ids.
    Implements [rule.reject.1], [rule.reconsider.7]."""
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
