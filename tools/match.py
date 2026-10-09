#!/usr/bin/env python3
"""Match the personas of an extraction against the tree and write proposals.

usage: tools/match.py <extraction id> [--about "<person>"] [--db catalog/tree.db] [--by user:<you>]

The record was fetched for one or more persons: those whose step logged the
artifact, those whose fetch step points at a record id the artifact holds
(catalog.holds: the household a record page names, the whole sheet for an
image), and those already matched on it by an accepted persona link. The candidates
are those persons and their relatives as the catalog knows them (parents,
spouses, children, siblings); a person the record was fetched for keeps their
own step and question on the proposal, a relative takes the context they were
first met in. Every persona on the extraction is compared with
each candidate on name, sex, birth and death dates, burial and death place, and
stated relationships. Dates are compared as dates when both sides carry a full
date (a different day in the same year disagrees), and to the month when both
give one (a different month in the same year disagrees; a month against a full
date of it agrees to the month and says so); a bare year against a fuller date
agrees on the year only and says so; a date marked about, estimated or
calculated on either side agrees within two years (catalog.date_verdict). A place agrees the same way on the part it states: a record place that names
the tree's own place, or an ancestor of it in the resolved hierarchy (the county, or the state alone, spelled out or
as its two-letter US code), agrees on the level it names and says so; a record place inside the tree's own (the town
ahead of the state the tree holds) agrees on the level the tree states and says the record is finer; a place neither
the tree's own, nor an ancestor of it, nor inside it disagrees — unless the record names a county alone, which then
takes the state of the record's own collection (catalog.collection_state) for the comparison, the note saying so; or
unless the record names a dated former name of the tree's own place (catalog.dated_names, from tools/resolve_places.py's
own Wikidata reading), which then agrees on that name, the note naming the period it held it; the
place string itself is never touched. A prefix (Dr, Maj), a nickname in quotes
and an extra middle name are not disagreements, but a middle name or initial
both names carry that differs is (middle_differs: John A. against John D; an
initial, a short form or a spelling variant of the tree's agrees, and so does
an initial standing for another surname the person holds, Helen B. for a woman
born Brant); such a persona never fits, at most a card; a name written surname first
(Doe, John A.) is read as such and an initial is never a surname; the
surname agrees when any token of the record's name after the given name is a
surname the tree has for the candidate (a memorial writes a married woman's
birth surname inside her name). A persona fits a candidate when the given name agrees, nothing compared
disagrees, and either the surname and at least one of the dates or places
agree, or a stated relationship agrees; a persona whose own memorial link is a
memorial already accepted as a person fits that person outright, and that
person joins the candidates whether or not they are a relative in the tree.
Nobody fitting outright, the fitting check (docs/RULE.md)
still proposes an existing person before a new one, looking across the whole
tree (by_name_and_year): a candidate whose surname or birth surname agrees, as
written or as a spelling variant, and whose birth year agrees within the window
where both have one, or who already stands in the same stated relationship to
the same candidate the record's other persona was accepted as, is proposed with
the disagreement in the rationale; for a person with no family link yet a given
name that disagrees is not what refuses this, only the surname or the
relationship (a stated sibling is neither held nor contradicted by a candidate
with no parents in the tree), while a person already placed in a family is
reached this way only when the given name agrees too; and a candidate of the
same name comes before one the fitting check reaches on the surname or the
relationship alone, so a brother named Joe is put to the tree's Joe, not to the
first sibling met. One proposal per persona: kind
persona_match with the candidate that fits (the one with more agreements when
two fit, the other named in the rationale), or new_person when nobody fits,
outright or by the fitting check, and the persona has a full name and a word of kinship (KIN_WORD, or a child, parent,
spouse or sibling heading) to a persona accepted on the record. Two kinds of persona are held back as hints, each with
the reason in words (proposals' held, which cards.hints_on shows): a namesake, a persona of a record a name search alone
reached (found_by_name: a search step's own result, or the record behind a results page's row) that agrees with the
candidate on no more than the name, the sex and a year of birth the record gives bare, disagrees on something, and
states no relationship to a persona accepted on the record, fitting a person or carrying a card; and nobody to create,
a persona with no full name, or one related to those accepted only by a word that is no kinship (an informant, "other
relative"), by "other" with no word, or by nothing. The
proposal carries the question of the step the candidate came from, when it has
one. A row of a results page that points at records (extract.POINTING_LISTINGS: a
FamilySearch, Find a Grave or AAD search) is never proposed, fitting or not: its own
record is the document, so it stays a hint on the page, and fitting_rows names the
rows that fit a person the page was fetched for, by this module's own definition of
fits, for tools/plan.py to write a fetch step for each row's record (a lead). A row
of a listing that is the record (the gravesite locator's, the death indexes') is
proposed like any persona; one that fits nobody stays a hint on the page, and the
candidate card says why it does not fit. The rationale says in plain words which fields agree, which disagree, which
are absent. Nothing numeric is stored. A persona that already has a proposal is
skipped, so re-running adds nothing; a proposal closed as superseded (a re-read's,
or one tools/conclude.py rematch closes: an older matcher's, one left on a superseded
reading, one the person's evidence has passed by) is not one, so that persona is
proposed again. What the matcher proposes is proposals(), which writes nothing:
match writes it, and rematch compares a card that stands with it, the card taken as
unwritten. A persona already decided, its link accepted or rejected, is
skipped too; an undecided link is no decision (a decision the rule took back), so
it keeps no persona from its card. A relative a memorial merely lists (every persona on a
findagrave-memorial extraction but its own subject) gets no proposal at all,
fit or not: the owner's word is that a memorial's family connections are leads
to look over, not facts (docs/TERMS.md §0), so tools/plan.py writes
a fetch step for the relative's own memorial instead, and the persona stays a
hint on the page. The matcher is versioned like an extractor (MATCHER); every
proposal carries the version that wrote it in generated_by.
"""
import argparse, dataclasses, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, ulid
from catalog import (
    COUNTRY,
    Catalog,
    Finding,
    cited_persons,
    collection_state,
    date_verdict,
    edits,
    first_given,
    holds,
    key,
    name_words,
    note,
    place_verdict,
    same_surname,
    short_form,
    soundex,
    split_persona_name,
    year
)
from log_search import REOPENED

# raised with any change to what fits: reconsider then proposes every older version's undecided cards again
MATCHER = ("rule", "matcher", "0.10.0")
# the matcher's own window on a birth year, in years: the fitting check's reach, and beyond it no likely identity
WINDOW = 3
# extractor name -> the page's own subject role; every other persona on such an extraction is a relative the page merely lists, a lead (tools/plan.py), never a card
LISTED_RELATIVE_SUBJECT = {"findagrave-memorial": "memorial"}
# the husband of a daughter or a sister on the same record: the surname she may be shown married under
MARRIED_IN_LAW = re.compile(r"son-in-law|brother-in-law", re.I)
REL_OF = {"parents": "parent", "children": "child", "spouses": "spouse", "siblings": "sibling"}
# a word of kinship a record files under another heading (a grandson, a daughter-in-law, a maternal grandmother): never "other relative", an informant's signature or a blank
KIN_WORD = re.compile(
    r"\b(?:great-?)*(?:grand)?(?:father|mother|son|daughter|child|children|parent)s?\b|\b(?:brother|sister|sibling|husband|wife|spouse|groom|bride|widow|widower|aunt|uncle|niece|nephew|cousin)s?\b|in-law|\bhalf\b|\bstep",
    re.I
)
NAME_ONLY = ("given name", "surname", "sex")  # what a namesake agrees on, besides a year of birth the record gives bare
# a disagreement on one of these keeps a persona from fitting, the birth place unless compare is told otherwise
UNFITTING = ("sex", "middle name", "birth date", "death date", "burial place", "death place")
# an agreement on one of these is more than a name and a year
STRONG = ("death date", "birth place", "burial place", "death place", "residence place")

def same_given(a, b):
    """Two given-name keys are the same name: equal, one an initial of the other, a short form of the other (catalog.short_form),
    or one letter apart when both are five letters or longer (a transcriber's slip)."""
    if not a or not b:
        return False
    if a == b or (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return True
    if short_form(a, b):
        return True
    if min(len(a), len(b)) >= 5 and abs(len(a) - len(b)) <= 1:
        if len(a) == len(b):
            return sum(x != y for x, y in zip(a, b)) == 1
        s, l = (a, b) if len(a) < len(b) else (b, a)
        return any(l[:i] + l[i + 1:] == s for i in range(len(l)))
    return False

def name_keys(cat, pid, accepted=False):
    """(first given, surname) keys for a person: every name row and every alias not rejected, the matcher's reading for finding
    and proposing; accepted: the name rows and the accepted aliases alone, the names the standing rule stands on
    (docs/RULE.md, which variants the rule counts as the name)."""
    keys = set()
    p = cat.person(pid)
    for given, surname, *_ in p["names"]:
        keys.add((first_given(given), key(surname)))
    for alias in p["accepted_aliases" if accepted else "aliases"]:
        parts = alias.split()
        if len(parts) >= 2:
            keys.add((first_given(parts[0]), key(parts[-1])))
    return keys

def same_middle(a, b):
    """Two middle-name keys are one name: one an initial of the other, the same name or a short form (same_given), or a
    spelling variant, the same Soundex code within two edits (Sara and Sarah, Micheal and Michael)."""
    return same_given(a, b) or (len(a) > 1 and len(b) > 1 and soundex(a) == soundex(b) and edits(a, b) <= 2)

def middle_differs(written, names, surnames):
    """(the record's middle name, the tree's) when a name as written and the person's own names in the tree (names: (given,
    surname) rows) both carry a middle name or initial and none of the record's agrees with any of the tree's (same_middle:
    John Georgi Young agrees with John Y), else None. A word that is a surname the person holds (a married woman's birth
    surname written inside her name, Lena Bell Davidson) is no middle name, and an initial standing for one agrees (Helen
    B. Ahearn for a Brant born); a name with no middle on either side disagrees with nothing."""
    keys = [key(s) for s in surnames if key(s)]
    own = lambda w: len(w) > 1 and any(same_surname(w, s) for s in keys)
    words = name_words(written)
    mine = [w for w in words[1:-1] if not own(w)]
    if not mine:
        return None
    theirs = [[w for w in name_words(g)[1:] if not own(w)] for g, s in names]
    theirs = [m for m in theirs if m]
    if not theirs:
        return None
    # the initial of another surname the person holds than the one the record writes
    if any(len(m) == 1 and s.startswith(m) and not same_surname(s, words[-1]) for m in mine for s in keys):
        return None
    # one of the record's middle names is one of the tree's: John Georgi Young for John Y
    if any(same_middle(m, x) for m in mine for t in theirs for x in t):
        return None
    return mine[0], theirs[0][0]

def compare(cat, persona, cand, chosen, birth_place=True, accepted_names=False):
    """Agreements, disagreements and absences between a persona and a candidate person, as findings (catalog.Finding, in
    words by said). birth_place False: a birth place that differs keeps the persona from fitting no more than it vetoes
    the standing rule (docs/RULE.md), as the rule reads a relative's persona on a record; the matcher's
    own proposals read it as written. accepted_names: the person's names read as the rule stands on them, the name rows
    and the accepted aliases alone (name_keys); the matcher reads every alias not rejected."""
    agree, disagree, absent = [], [], []
    keys = name_keys(cat, cand["id"], accepted=accepted_names)
    # every name the record gives: at birth, current, as written elsewhere on it
    names = [split_persona_name(n) for n in (persona.get("names") or [persona["name"]])]
    pg, rest = next(
        (
            (g, r)
            for g, r in names
            if any(same_given(g, k) for k, _ in keys) and any(same_surname(t, s) for t in r for _, s in keys)
        ),
        names[0]
    )
    ps = rest[-1] if rest else ""
    given_ok = any(same_given(g, k) for g, _ in names for k, _ in keys)
    how = (
        next((same_surname(t, s) for _, r in names for t in r for _, s in keys if same_surname(t, s) == "agrees"), None)
        or next((same_surname(t, s) for _, r in names for t in r for _, s in keys if same_surname(t, s)), None)
    )
    surname_ok = bool(how)
    # a wife under her husband's surname (the record's spouse or the tree's), or any woman shown married: a daughter or sister
    # beside a son- or brother-in-law of that surname, or written "Mrs."; never one the record or the tree says is a man
    married = (
        bool(ps)
        and not surname_ok
        and "M" not in (persona["sex"], cand["sex"])
        and (
            persona.get("spouse_surname") == ps
            or any(same_surname(ps, s) for s in cand.get("spouse_surnames") or [])
            or any(same_surname(ps, s) for s in persona.get("in_law_surnames") or [])
            or persona.get("shown_mrs")
        )
    )
    (agree if given_ok else disagree).append(
        Finding("agrees" if given_ok else "disagrees", field="given name", record=persona["name"], tree=cand["name"])
    )
    if ps and married:
        absent.append(Finding("absent", field="surname", record=persona["name"], married=True))
    elif ps:
        (agree if surname_ok else disagree).append(
            Finding(
                "agrees" if surname_ok else "disagrees",
                field="surname",
                record=persona["name"],
                tree=cand["name"],
                spelling=how if how in ("variant", "one letter apart") else None
            )
        )
    else:
        absent.append(Finding("absent", field="surname"))
    rows = [(g or "", s or "") for g, s, *_ in cat.person(cand["id"])["names"]]
    # both carry a middle name or initial and they differ: another person, or a slip the owner reads
    if given_ok and middle_differs(persona["name"], rows, [s for _, s in rows]):
        disagree.append(Finding("disagrees", field="middle name", record=persona["name"], tree=cand["name"]))
    if persona["sex"] and cand["sex"] in ("M", "F"):
        (agree if persona["sex"] == cand["sex"] else disagree).append(
            Finding(
                "agrees" if persona["sex"] == cand["sex"] else "disagrees",
                field="sex",
                record=persona["sex"],
                tree=cand["sex"]
            )
        )
    else:
        absent.append(Finding("absent", field="sex"))
    dated = False
    for label in ("birth", "death"):
        f = date_verdict(persona[label], cand[label])
        if f.verdict == "absent":
            absent.append(Finding("absent", field=f"{label} date"))
            continue
        f = dataclasses.replace(
            f, field=f"{label} date", record=persona[label]["text"], tree=cand[label]["text"]
        )
        # a bound neither agrees nor disagrees (catalog.date_verdict)
        if f.verdict == "within":
            absent.append(f)
            continue
        (agree if f.verdict == "agrees" else disagree).append(f)
        dated = dated or f.verdict == "agrees"
    for label in ("birth place", "burial place", "death place"):
        f = place_verdict(
            persona[label],
            cand[label],
            record_state=persona.get("record_state"),
            dated_names=cat.dated_names(cand.get(f"{label}_id"))
        )
        if f.verdict == "absent":
            absent.append(Finding("absent", field=label))
            continue
        (agree if f.verdict == "agrees" else disagree).append(
            dataclasses.replace(f, field=label, record=persona[label], tree=cand[label])
        )
        dated = dated or f.verdict == "agrees"
    if persona.get("residence place"):  # where the record puts the person, against every place the tree knows them at
        known = [p for p in cand.get("places") or [] if p]
        hit = next(
            (
                (p, f)
                for p in known
                for f in [place_verdict(persona["residence place"], p)]
                if f.verdict == "agrees"
            ),
            None
        )
        if hit:
            agree.append(
                dataclasses.replace(hit[1], field="residence place", record=persona["residence place"], tree=hit[0])
            )
            dated = dated or True
        else:
            absent.append(Finding("absent", field="residence place", record=persona["residence place"]))
    same = bool(persona.get("memorial")) and persona["memorial"] in (cand.get("memorials") or set())
    if same:
        agree.append(Finding("agrees", field="memorial", record=persona["memorial"], tree=cand["name"]))
    rel_ok = False
    for kind, other_pid, as_written, other_name in persona["relations"]:
        stated = dict(field="relationship", kind=kind, word=as_written, other=other_pid, other_name=other_name)
        other_cand = chosen.get(other_pid)
        if not other_cand:
            absent.append(Finding("absent", why="unmatched", **stated))
            continue
        fam = cat.family(cand["id"])
        group = {"child": "parents", "parent": "children", "spouse": "spouses", "sibling": "siblings"}.get(kind)
        if group is None:
            absent.append(Finding("absent", why="unmapped", **stated))
            continue
        holds = any(rid == other_cand["id"] for rid, _ in fam[group])
        # a sibling is held through the parents: a candidate with none in the tree neither holds nor contradicts it
        if not holds and kind == "sibling" and not fam["parents"]:
            absent.append(Finding("absent", why="no parents", tree=cand["name"], **stated))
            continue
        (agree if holds else disagree).append(
            Finding(
                "agrees" if holds else "disagrees",
                tree=cand["name"],
                related=other_cand["name"],
                role=REL_OF[group],
                **stated
            )
        )
        rel_ok = rel_ok or holds
    clean = not any(d.field in UNFITTING + (("birth place",) if birth_place else ()) for d in disagree)
    # more than a name and a year: a place, a death, or the day
    strong = (
        any(a.field in STRONG for a in agree)
        or any(
            a.field == "birth date" and not a.only and len((persona["birth"] or {}).get("start") or "") == 10
            for a in agree
        )
    )
    fits = clean and (same or (given_ok and (((surname_ok or married) and dated and strong) or rel_ok)))
    # disagreeing on both is not a likely identity either
    both_dates = (
        any(d.field == "birth date" for d in disagree)
        and any(d.field == "death date" for d in disagree)
    )
    ry, cy = year((persona["birth"] or {}).get("start")), year((cand["birth"] or {}).get("start"))
    # born outside the matcher's own window: another generation, never a likely identity
    far = ry is not None and cy is not None and abs(ry - cy) > WINDOW
    # the persona relates to a persona already resolved on this record
    has_relation = any(chosen.get(o) for _, o, _, _ in persona["relations"])
    # a person of the tree with no family link yet
    unlinked = not any(cat.family(cand["id"])[g] for g in ("parents", "spouses", "children", "siblings"))
    # the fitting check (docs/RULE.md): the same stated relationship to the same accepted person, or the surname on a person with no family link yet; a given name disagreeing does not refuse it
    fitting = clean and (surname_ok or married) and has_relation and (rel_ok or unlinked)
    # the same name, something else disagrees, or the fitting check's relationship route: a card, never a rule decision
    near = (
        not fits
        and not far
        and not any(d.field == "sex" for d in disagree)
        and not both_dates
        and ((given_ok and (surname_ok or married or same)) or fitting)
    )
    return fits, agree, disagree, absent, near

def said(f):
    """A finding of compare's, or a disagreement conclude.split_disagree finds with an accepted statement, in words: the
    sentence a rationale, a card and the rule's reasons carry. Nothing reads these words back."""
    if f.accepted:
        return (
            f"{f.field} disagrees with an accepted statement "
            f"(record {f.record}, accepted {f.accepted[0]} on {f.accepted[1]}; the tree shows {f.tree or 'none'})"
        )
    if f.field == "relationship" and f.why:
        to = f"relationship to {f.other_name} ({f.word})"
        if f.why == "unmatched":
            return f"{to}: {f.other_name} not yet matched"
        if f.why == "unmapped":
            return f"{to}: the record's heading is not one the matcher maps to a family link"
        return f"{to}: {f.tree} has no parents in the tree to hold or contradict a sibling"
    if f.field == "relationship":
        holds = f.verdict == "agrees"
        return (
            f"relationship {f.verdict}: {f.word or f.kind} of {f.other_name}, "
            f"{'and' if holds else 'but'} {f.related} is {'' if holds else 'not '}a {f.role} of {f.tree} in the tree"
        )
    if f.field == "memorial":
        return f"the same memorial {f.record} is already accepted as {f.tree}"
    if f.married:
        return f"surname: {f.record} carries her husband's surname on the record"
    if f.field == "residence place" and f.verdict == "absent":
        return f"residence: {f.record} is not a place the tree knows them at"
    if f.verdict == "absent":
        return f.field
    if f.field == "sex":
        return f"sex {f.verdict} ({f.record} in the record, {f.tree} in the tree)"
    if f.field == "surname":
        return (
            f"surname {f.verdict}"
            + {"variant": " as a spelling variant", "one letter apart": ", one letter apart"}.get(f.spelling, "")
            + f" (record {f.record}, tree {f.tree})"
        )
    # where the record puts the person: the place the tree knows them at, no more
    if f.field == "residence place":
        return f"residence place agrees (record {f.record}, tree {f.tree})"
    n = note(f)
    return f"{f.field} {f.verdict} (record {f.record}, tree {f.tree}" + (f": {n}" if n else "") + ")"

def _date(row):
    return (
        {"text": row[0], "start": row[1] or row[2], "end": row[2], "qualifier": row[3]}
        if row and (row[1] or row[2])
        else {"text": None, "start": None, "end": None, "qualifier": None}
    )

def personas_of(cx, eid):
    """The personas of an extraction as the matcher compares them, in the record's order: each one's name, every other name
    the record gives them, sex, role, birth and death, the birth, burial, death and residence places, the relations it
    states and the memorial it links. A value the page keeps beneath the one it shows (a fact whose region marks it
    alternate, FamilySearch's edit history) is no value the record states (docs/RULE.md, the proof standard):
    no name, date or place of a persona is read from one."""
    out = []
    coll = cx.execute(
        "SELECT c.name FROM extraction e JOIN artifact ar ON ar.sha256=e.artifact_sha256 LEFT JOIN collection c ON c.id=ar.collection_id WHERE e.id=?",
        (eid,)
    ).fetchone()
    # the record's own event place for a bare county (catalog.place_verdict), from the collection's own name
    record_state = collection_state(coll[0] if coll else None)
    # persona id -> its facts, and its relations, in the order they were written: a results page holds a hundred personas, read in three queries
    facts, rels = {}, {}
    for r in cx.execute("""SELECT pf.persona_id, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw FROM persona_fact pf JOIN persona pe ON pe.id=pf.persona_id
                           LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pe.extraction_id=?
                           AND NOT (json_valid(pf.region_json) AND json_extract(pf.region_json,'$.alternate') IS NOT NULL) ORDER BY pf.rowid""", (eid,)):
        facts.setdefault(r[0], []).append(tuple(r[1:]))
    for r in cx.execute("""SELECT r.persona_id, r.kind, r.related_persona_id, r.value_text, o.name_text FROM persona_relation r JOIN persona o ON o.id=r.related_persona_id
                           JOIN persona pe ON pe.id=r.persona_id WHERE pe.extraction_id=? ORDER BY r.rowid""", (eid,)):
        rels.setdefault(r[0], []).append(tuple(r[1:]))
    for pid, name, sex, role, region_json in cx.execute(
        "SELECT id, name_text, sex, role_in_record, region_json FROM persona WHERE extraction_id=? ORDER BY sequence",
        (eid,)
    ):
        # (fact type, value, date text, date start, date end, date qualifier, place as written)
        mine = facts.get(pid, [])
        fact = lambda t: next(
            ((x[2], x[3], x[4], x[5]) for x in mine if x[0] == t and (x[3] is not None or x[4] is not None)), None
        )
        names = [name] + [x[1] for x in mine if x[0] == "Name" and x[1] is not None and x[1] != name]
        place = lambda t: next((x[6] for x in mine if x[0] == t and x[6] is not None), None)
        region = json.loads(region_json or "{}")
        m = re.search(r"/memorial/(\d+)(?:/|$)", region.get("url") or "")
        out.append(
            {
                "id": pid,
                "name": name,
                "names": names,
                "sex": sex,
                "role": role,
                "birth": _date(fact("Birth")),
                "death": _date(fact("Death")),
                "birth place": place("Birth"),
                "burial place": place("Burial"),
                "death place": place("Death"),
                "residence place": place("Residence"),
                "relations": rels.get(pid, []),
                "memorial": str(region.get("memorial_id") or (m.group(1) if m else "")) or None,
                "record_state": record_state
            }
        )
    names = {p["id"]: p["name"] for p in out}
    in_law_surnames = [
        rest[-1]
        for p in out
        if MARRIED_IN_LAW.search(p["role"] or "")
        for rest in [split_persona_name(p["name"])[1]]
        if rest
    ]
    for p in out:  # a spouse relation on the record: the other's surname, for a wife written under it
        sp = next((names[r[1]] for r in p["relations"] if r[0] == "spouse" and r[1] in names), None)
        p["spouse_surname"] = split_persona_name(sp)[1][-1] if sp and split_persona_name(sp)[1] else None
        # a daughter or sister under her own husband's surname, a son-in-law or brother-in-law of it named beside her
        p["in_law_surnames"] = in_law_surnames
        p["shown_mrs"] = bool(re.match(r"^\s*mrs\.?\b", p["name"] or "", re.I))
    return out

def memorials_of(cx, pid):
    """The Find a Grave memorial ids already accepted as this person: the id of a memorial page accepted as theirs, and the id a
    held record links beside a persona accepted as them. A record's link to the same memorial is the same identity. Only the
    personas of current extractions count: a superseded reading's links are history."""
    ids = set()
    for region, sha, role in cx.execute("""SELECT pe.region_json, pe.artifact_sha256, pe.role_in_record FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                                            JOIN extraction e ON e.id=pe.extraction_id WHERE pp.person_id=? AND pp.status='accepted' AND e.superseded_by IS NULL""", (pid,)):
        r = json.loads(region or "{}")
        m = re.search(r"/memorial/(\d+)(?:/|$)", r.get("url") or "")
        if r.get("memorial_id"):
            ids.add(str(r["memorial_id"]))
        if m:
            ids.add(m.group(1))
        if role == "memorial":
            for v, in cx.execute(
                "SELECT value FROM artifact_locator WHERE artifact_sha256=? AND kind='memorial_id'", (sha,)
            ):
                ids.add(v)
    return ids

def by_name_and_year(cat, cx, tree_id, persona):
    """Persons of the whole tree (never one merged into another) whose surname or birth surname agrees with the persona's, as
    written or as a spelling variant (catalog.same_surname), and whose birth year lies within the matcher's window of the
    persona's where both give one (the fitting check, docs/RULE.md): a household or obituary record names
    people the tree may already hold, a sibling added from a memorial with no family link yet, or a grandson the obituary
    writes Ahern whom the tree holds as Ahearn in another branch of the family. A person with no family link yet is reached
    on the surname and the year alone, the record's other signals carrying the actual decision; a person already placed in
    a family only when a given name of the persona's agrees with one of theirs too (same_given), so the household's
    unknown members are not put to every relative of the surname the tree holds. Without a birth year on either side the
    names are the whole of it."""
    names = [split_persona_name(n) for n in (persona.get("names") or [persona["name"]])]
    givens, rest = [g for g, _ in names if g], [t for _, r in names for t in r]
    if not rest:
        return []
    by = (persona["birth"] or {}).get("start")
    y = int(by[:4]) if by and by[:4].isdigit() else None
    out = []
    for pid, linked in cx.execute(
        """SELECT id, EXISTS (SELECT 1 FROM family_member fm WHERE fm.person_id=person.id) FROM person
                                     WHERE tree_id=? AND merged_into IS NULL ORDER BY created_at, id""", (tree_id,)
    ).fetchall():
        keys = name_keys(cat, pid)
        if not any(same_surname(t, s) for t in rest for _, s in keys if s):
            continue
        if linked and not any(same_given(g, k) for g in givens for k, _ in keys):
            continue
        if y is not None:
            years = [
                int(ds[:4])
                for ds, in cx.execute("""SELECT e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id
                     WHERE ep.person_id=? AND e.event_type='Birth' AND e.date_start IS NOT NULL""", (pid,))
                if ds[:4].isdigit()
            ]
            if years and not any(abs(cy - y) <= WINDOW for cy in years):
                continue
        out.append(pid)
    return out

def fits_by_name_and_year(cat, cx, tree_id, persona):
    """Persons of the tree whose given name and surname (or birth surname) agree with this persona's, and whose birth year
    agrees within the matcher's window where both give one, with no middle name or initial both carry differing: the given
    name as same_given reads it, any later word of the persona's name as one of the surnames the tree holds for the person
    (every name and alias) written the same or a spelling variant of it (same_surname: Detwiler for Detweiler), as the
    matcher's comparison agrees a surname everywhere (docs/RULE.md), never one letter apart, an indexer's
    slip a person reads, since nobody reads this fit before it is used. A plain name-and-year fit on a specific candidate,
    unlike by_name_and_year's coarser surname-only filter (deliberately wide, for compare() to judge further; wrong here,
    since a shared surname alone would fit a memorial's subject to their own listed spouse). docs/TERMS.md §0's relative that fits exactly
    one person by name and birth year is this, the caller asking for exactly one: tools/plan.py's listed-relative leads seat
    a relative the matcher never proposes on the one person of the tree they plainly are, and conclude.link_family places
    the membership a page anyone can edit states for such a relative, undecided, without deciding an identity."""
    given, rest = split_persona_name(persona["name"])
    if not given or not rest:
        return []
    by = (persona["birth"] or {}).get("start")
    y = int(by[:4]) if by and by[:4].isdigit() else None
    out = []
    for pid, in cx.execute("SELECT id FROM person WHERE tree_id=? AND merged_into IS NULL", (tree_id,)):
        keys = name_keys(cat, pid)
        if not any(same_given(given, k) for k, _ in keys):
            continue
        if not any(same_surname(t, s) in ("agrees", "variant") for t in rest for _, s in keys if s):
            continue
        rows = [(g or "", s or "") for g, s, *_ in cat.person(pid)["names"]]
        # a middle name or initial both carry, differing: not plainly this person
        if middle_differs(persona["name"], rows, [s for _, s in rows]):
            continue
        if y is not None:
            years = [
                int(ds[:4])
                for ds, in cx.execute("""SELECT e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id
                     WHERE ep.person_id=? AND e.event_type='Birth' AND e.date_start IS NOT NULL""", (pid,))
                if ds[:4].isdigit()
            ]
            if years and not any(abs(cy - y) <= WINDOW for cy in years):
                continue
        out.append(pid)
    return out

def by_memorial(cx, tree_id, mid):
    """Persons of the tree already accepted under this memorial id, by memorials_of, on current extractions only."""
    return [pid for pid, in cx.execute("""SELECT DISTINCT pp.person_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN person p ON p.id=pp.person_id
                                          JOIN extraction e ON e.id=pe.extraction_id
                                          WHERE p.tree_id=? AND pp.status='accepted' AND e.superseded_by IS NULL AND (json_extract(pe.region_json,'$.memorial_id')=? OR json_extract(pe.region_json,'$.url') LIKE ?
                                             OR (pe.role_in_record='memorial' AND EXISTS (SELECT 1 FROM artifact_locator l WHERE l.artifact_sha256=pe.artifact_sha256 AND l.kind='memorial_id' AND l.value=?)))""", (tree_id, mid, f"%/memorial/{mid}/%", mid))]

def candidate(cat, pid):
    """A person as the matcher compares them: their names, sex, and the birth, death and burial the tree shows (Catalog.
    canonical_event: the event of the type with the strongest ground, never one whose every statement is rejected), each
    event's date and place and its id for the rule's ground, every place the tree knows them at, their spouses' surnames
    and the memorials accepted as them."""
    p = cat.person(pid)
    ev = cat.events(pid)
    def shown(t):
        e = cat.canonical_event(ev, t)
        if not e:
            return {
                "text": None,
                "start": None,
                "end": None,
                "qualifier": None,
                "place": None,
                "place_id": None,
                "event": None
            }
        r = cat.cx.execute(
            "SELECT date_text, date_start, date_end, date_qualifier FROM event WHERE id=?", (e["id"],)
        ).fetchone()
        return {
            **_date(r),
            "place": e["place"]["text"] if e["place"] else None,
            "place_id": (e["place"] or {}).get("place_id"),
            "event": e["id"]
        }
    b, d, bu = shown("Birth"), shown("Death"), shown("Burial")
    # the events compared, for the rule's ground
    return {
        "id": pid,
        "name": p["name"],
        "sex": p["sex"],
        "birth": b,
        "death": d,
        "birth place": b["place"],
        "burial place": bu["place"],
        "death place": d["place"],
        "birth place_id": b["place_id"],
        "burial place_id": bu["place_id"],
        "death place_id": d["place_id"],
        "memorials": memorials_of(cat.cx, pid),
        "places": [e["place"]["text"] for e in ev if e.get("place") and e["place"]["text"]],
        "spouse_surnames": [key(n.split()[-1]) for _, n in cat.family(pid)["spouses"] if n and n.split()],
        "events": {"Birth": b["event"], "Death": d["event"], "Burial": bu["event"]}
    }

def persons_for(cx, sha):
    """(person_id, question_id, step_id) for every person the artifact was fetched for: a step logged on it, the persons the
    logged fetch step's citation sits on (a record fetched on a relative's footprint step is that relative's own record, and
    the file's claim that it is theirs is the question put to them), a fetch step pointing at its locator, or an accepted
    persona link on it (question and step None; a superseded reading's links are history, so only a persona of a current
    extraction counts). A step's log row no longer counts once a later run reopened the step
    (log_search.reopen): the row stays as what happened, and the step's most recent word on the record governs."""
    rows = cx.execute("""SELECT DISTINCT sp.person_id, sp.question_id, sp.id, sp.on_json='[]' AS own, l.executed_at, sp.seq, sp.locator_kind, sp.locator_value
                          FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE l.artifacts_json LIKE ? AND l.superseded_by IS NULL
                          AND NOT EXISTS (SELECT 1 FROM search_log r WHERE r.plan_step_id=l.plan_step_id AND r.notes LIKE ? AND r.id > l.id AND r.superseded_by IS NULL)
                          ORDER BY own DESC, l.executed_at, sp.seq""", (f'%"{sha}"%', REOPENED + "%")).fetchall()
    # the citation's own people, under the step that fetched it
    cited = [(who, r[1], r[2]) for r in rows if r[6] == "apid" and r[7] for who in cited_persons(cx, r[7])]
    # the step whose citation sits on the person themselves first, then in the order logged, then the cited
    rows = [r[:3] for r in rows] + cited
    loc = cx.execute("SELECT locator_kind, locator_value FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if loc and loc[0] and loc[1]:
        # the ids the artifact holds: the household it names, or the whole sheet for an image
        values = sorted(holds(cx, sha)) if loc[0] == "apid" else [loc[1]]
        rows += cx.execute(
            f"SELECT DISTINCT person_id, question_id, id FROM search_plan WHERE kind='fetch' AND locator_kind=? AND locator_value IN ({','.join('?'*len(values))}) ORDER BY seq",
            (loc[0], *values)
        ).fetchall()
    rows += cx.execute(
        """SELECT DISTINCT pp.person_id, NULL, NULL FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN extraction e ON e.id=pe.extraction_id
                          WHERE pe.artifact_sha256=? AND pp.status='accepted' AND e.superseded_by IS NULL""", (sha,)
    ).fetchall()
    seen, out = set(), []
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0])
            out.append(r)
    return out

def linked(cat, a, b):
    """Whether two persons stand in one family on a record: both memberships carry an accepted assertion resting on an archived
    record, not on the tree file's claim and not on the owner's word alone. A vouch is a claim the owner stands behind, not a
    document, so a vouched relative waits like any other until the record's own person is decided."""
    on_record = lambda fid, who, role: bool(cat.q("""SELECT 1 FROM assertion a WHERE a.subject_kind='family_member' AND a.subject_id=? AND a.status='accepted'
                                                      AND a.artifact_sha256 IS NOT NULL AND a.artifact_sha256 NOT IN (SELECT artifact_sha256 FROM tree_import)
                                                      AND NOT (json_valid(a.notes) AND (coalesce(json_extract(a.notes,'$.vouched'),0)=1 OR coalesce(json_extract(a.notes,'$.uncited'),0)=1))""", dumps([fid, who, role])))
    for fid, ra, rb in cat.q("""SELECT fm.family_id, fm.role, x.role FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.person_id=?
                                 WHERE fm.person_id=?""", b, a):
        if on_record(fid, a, ra) and on_record(fid, b, rb):
            return True
    return False

def fitting_rows(cx, eid, person_id=None, known=None):
    """The rows of a results page that points at records (extract.POINTING_LISTINGS), as the current reading holds them, that fit
    a person the page was fetched for (persons_for, or person_id alone), by compare's own definition of fits: more than a name
    and a year, a place, a death, the day, a stated relationship, and nothing compared disagreeing. [(person id, the row's
    persona as personas_of reads it, what agrees as findings)], one entry for each person a row fits, in the page's order. Nothing is
    written: the matcher proposes no row of such a page (match), so this is the one answer to which rows are worth their own
    record, read by tools/plan.py for the leads and by tools/attach.py for whether the run found anyone. Empty for any other
    extraction. known: {person id: (Catalog, candidate)} a caller asking about several pages keeps, so each person is read once."""
    from extract import POINTING_LISTINGS
    ext = cx.execute("""SELECT e.artifact_sha256 FROM extraction e JOIN extractor x ON x.id=e.extractor_id
                         WHERE e.id=? AND e.superseded_by IS NULL AND e.status='complete' AND x.name IN (%s)""" % ",".join("?" * len(POINTING_LISTINGS)), (eid, *POINTING_LISTINGS)).fetchone()
    if not ext:
        return []
    rows = personas_of(cx, eid)
    out = []
    known = {} if known is None else known
    for pid, _, _ in persons_for(cx, ext[0]):
        if person_id not in (None, pid):
            continue
        if pid not in known:
            cat = Catalog(cx, cx.execute("SELECT tree_id FROM person WHERE id=?", (pid,)).fetchone()[0])
            known[pid] = (cat, candidate(cat, pid))
        cat, cand = known[pid]
        for pr in rows:
            fits, agree, _, _, _ = compare(cat, pr, cand, {})
            if fits:
                out.append((pid, pr, agree))
    return out

def found_by_name(cx, sha):
    """Whether a record was reached by a name search alone (docs/RULE.md, a namesake): every plan step that
    logged it or points at it is a search step, the record its own result, or the fetch of the record behind a row of a
    results page (step key fetch:row:), and the file cites it for nobody. A record the file cites, one a held record links (a
    memorial a page names, an ark) and one attached on the owner's word are each reached by more than a name."""
    loc = cx.execute("SELECT locator_kind, locator_value FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if loc and loc[0] == "apid" and loc[1] and cited_persons(cx, loc[1]):
        return False
    steps = cx.execute("""SELECT DISTINCT sp.kind, sp.step_key FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id
                          WHERE l.artifacts_json LIKE ? AND l.superseded_by IS NULL""", (f'%"{sha}"%',)).fetchall()
    if loc and loc[0] and loc[1]:
        values = sorted(holds(cx, sha)) if loc[0] == "apid" else [loc[1]]
        if values:
            steps += cx.execute(
                f"SELECT DISTINCT kind, step_key FROM search_plan WHERE kind='fetch' AND locator_kind=? AND locator_value IN ({','.join('?' * len(values))})",
                (loc[0], *values)
            ).fetchall()
    return bool(steps) and all(kind == "search" or step_key.startswith("fetch:row:") for kind, step_key in steps)

def namesake(agree, disagree):
    """Whether a comparison (compare) agrees on the name, the sex and at most a year of birth the record gives bare, and on
    nothing else, and disagrees on something: a persona a name search alone reached that does so, tied to the person by
    nothing more, is a namesake, a hint and never a card (docs/RULE.md)."""
    return (
        bool(disagree)
        and all(a.field in NAME_ONLY or (a.field == "birth date" and a.only == "record" and not a.month) for a in agree)
    )

def matchable(cx, eid):
    """The sha256 of the record an extraction is, when the matcher proposes from it; None for a superseded reading, whose
    personas are history (only the current reading is proposed), and for a results page that points at records, whose rows
    are never cards whatever they agree on: its own record is the document (docs/TERMS.md §0); fitting_rows
    names the rows that fit, tools/plan.py writes a fetch step for each."""
    from extract import POINTING_LISTINGS
    ext = cx.execute(
        "SELECT e.artifact_sha256, e.superseded_by, x.name FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?",
        (eid,)
    ).fetchone()
    if not ext:
        raise SystemExit(f"no extraction {eid}")
    return None if ext[1] or ext[2] in POINTING_LISTINGS else ext[0]

def match(cx, eid, by, about=None):
    """One person at a time: a record proposes first the persona that may be the person it was fetched for (or a person already
    attached to them by a record accepted earlier, or already accepted under the same memorial); the record's other personas wait. Once a
    person is accepted on the record, its other personas are proposed against that person's relatives as the catalog knows
    them, claims included, and against every person of the tree the fitting check reaches (by_name_and_year): the same
    surname or birth surname, as written or as a spelling variant, and a birth year within three years where both give one
    (and, for a person already placed in a family, the same given name), or the same stated relationship to the same
    accepted person; a persona the record relates to an accepted person and that fits nobody, by the fitting check either,
    is proposed as a new person. about: person ids the owner says the record concerns, when no step or link names them (a
    family-held file). What it proposes is proposals' answer, written: [(proposal id, kind, persona name, person id)]."""
    sha = matchable(cx, eid)
    if not sha:
        return []
    ts = now()
    row = cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", MATCHER).fetchone()
    mid = row[0] if row else ulid()
    if not row:
        cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (mid, *MATCHER, ts))
    written = []
    for p in proposals(cx, eid, about=about):
        prop = ulid()
        cx.execute(
            """INSERT INTO proposal (id,tree_id,kind,question_id,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,?,'undecided')""",
            (
                prop,
                p["tree_id"],
                p["kind"],
                p["question_id"],
                dumps(
                    {
                        "persona_id": p["persona_id"],
                        "person_id": p["person_id"],
                        "subject_person_id": p["subject_person_id"],
                        "extraction_id": eid,
                        "artifact_sha256": sha,
                        "step_id": p["step_id"]
                    }
                ),
                p["rationale"],
                mid,
                ts
            )
        )
        written.append((prop, p["kind"], p["name"], p["person_id"]))
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, by, "insert", "proposal", eid, dumps({"proposals": len(written)})))
    return written

def on_another_copy(cx, tree_id, persona_id, ignore=()):
    """Whether a persona's entry of its record is proposed or decided on another copy of the record (same_record,
    catalog.entry_on): one record is one source wherever it is held (docs/DATA-ARCHITECTURE.md §7 decision 15), so its entry
    is put to the owner once, and a decision on it reaches every copy (conclude.carry). ignore: proposal ids taken as not
    written."""
    from catalog import copy_entry, current_reading, entry_on, record_copies
    copies = record_copies(cx, tree_id, *copy_entry(cx, persona_id))
    unless = f" AND p.id NOT IN ({','.join('?' * len(ignore))})" if ignore else ""
    for sha, _ in copies[1:]:
        r = current_reading(cx, sha)
        other = entry_on(cx, persona_id, r) if r else None
        if (
            other
            and (
                cx.execute(
                    "SELECT 1 FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND o.tree_id=? AND pp.status<>'undecided'",
                    (other, tree_id)
                ).fetchone()
                or cx.execute(
                    "SELECT 1 FROM proposal p WHERE p.tree_id=? AND json_extract(p.payload_json,'$.persona_id')=? AND NOT (p.status='rejected' AND p.decision_note='superseded')" + unless,
                    (tree_id, other, *ignore)
                ).fetchone()
            )
        ):
            return True
    return False

def proposals(cx, eid, about=None, ignore=(), held=None):
    """What the matcher proposes on an extraction as the catalog stands, written by match and by nothing else: one dict per
    persona it proposes, in the page's order, {tree_id, persona_id, name, kind, person_id (None for a new person),
    subject_person_id, question_id, step_id, rationale}. The record is matched for the people persons_for finds and the
    ones about names besides them. A persona already proposed or already decided gets none; ignore: proposal ids taken as
    not written, so a card that stands is matched again as the matcher would write it now (tools/conclude.py rematch).
    held: a dict filled with {persona id: why, in words} for each persona it would otherwise propose and holds back as a
    hint (docs/RULE.md): a namesake a name search alone reached (found_by_name, namesake), tied to the
    candidate by no relationship to a persona accepted on the record, fitting a person or carrying a card; and nobody to
    create, a persona with no full name, or one the record relates to the persons accepted on it by no word of kinship
    (KIN_WORD), only "other" with no word, or nothing (cards.hints_on shows the words)."""
    sha = matchable(cx, eid)
    if not sha:
        return []
    extractor_name = cx.execute(
        "SELECT x.name FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (eid,)
    ).fetchone()[0]
    # set on a page anyone can edit that lists a subject's family: every other role on it is a relative merely listed
    subject_role = LISTED_RELATIVE_SUBJECT.get(extractor_name)
    ignore = tuple(ignore)
    unless = f" AND id NOT IN ({','.join('?' * len(ignore))})" if ignore else ""
    personas = personas_of(cx, eid)
    out = []
    held = {} if held is None else held
    # reached by a name search alone: a persona agreeing on no more than the name and disagreeing is a namesake
    by_name = found_by_name(cx, sha)
    # persona id -> (kind, word, other persona id, other's name) for each relationship the record states, either way
    stated = {p["id"]: [] for p in personas}
    for p in personas:
        for kind, other, word, other_name in p["relations"]:
            stated[p["id"]].append((kind, word, other, other_name))
            if other in stated:
                stated[other].append((kind, word, p["id"], p["name"]))
    by_tree = {}                                                # tree id -> [(person id, question id, step id)]
    found = persons_for(cx, sha)
    for pid, qid, step_id in found + [
        (a, None, None) for a in dict.fromkeys(about or []) if a not in {f[0] for f in found}
    ]:
        by_tree.setdefault(cx.execute("SELECT tree_id FROM person WHERE id=?", (pid,)).fetchone()[0], []).append(
            (pid, qid, step_id)
        )
    for tree_id, contexts in by_tree.items():
        # candidate persons in order met; candidate id -> the context it came from
        cat = Catalog(cx, tree_id)
        cands, ctx_of = [], {}
        accepted_here = {r[0] for r in cx.execute("""SELECT pp.person_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN person p ON p.id=pp.person_id
                                                      WHERE pe.extraction_id=? AND pp.status='accepted' AND p.tree_id=?""", (eid, tree_id))}
        # persons a proposal may name now: the record's own people, and what accepted links or decisions attach to them
        open_now = set()
        for pid, qid, step_id in contexts:  # a person the record was fetched for keeps their own step and question
            if pid not in ctx_of:
                ctx_of[pid] = (pid, qid, step_id)
                cands.append(candidate(cat, pid))
                open_now.add(pid)
        for pid, qid, step_id in contexts:
            fam = cat.family(pid)
            for rid in [r for g in ("parents", "spouses", "children", "siblings") for r, _ in fam[g]]:
                if rid not in ctx_of:
                    ctx_of[rid] = (pid, qid, step_id)
                    cands.append(candidate(cat, rid))
                # a relative attached by an accepted record, or reached through a person accepted on this one
                if pid in accepted_here or linked(cat, pid, rid):
                    open_now.add(rid)
        for pr in personas:  # a persona whose memorial link is already accepted as someone: that person is a candidate
            if pr.get("memorial"):
                for rid in by_memorial(cx, tree_id, pr["memorial"]):
                    if rid not in ctx_of:
                        ctx_of[rid] = contexts[0]
                        cands.append(candidate(cat, rid))
                    open_now.add(rid)
            if accepted_here:
                # a person of the tree the fitting check reaches: the persona's surname, a spelling variant of it, and its birth year
                for rid in by_name_and_year(cat, cx, tree_id, pr):
                    if rid not in ctx_of:
                        ctx_of[rid] = contexts[0]
                        cands.append(candidate(cat, rid))
                    open_now.add(rid)
        accepted_personas = {r[0] for r in cx.execute("""SELECT pp.persona_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN person p ON p.id=pp.person_id
                                                          WHERE pe.extraction_id=? AND pp.status='accepted' AND p.tree_id=?""", (eid, tree_id))}
        related_to_accepted = (
            lambda pr: any(o in accepted_personas for _, o, _, _ in pr["relations"])
            or bool(
                cx.execute(
                    f"""SELECT 1 FROM persona_relation r WHERE r.related_persona_id=? AND r.persona_id IN ({','.join('?' * len(accepted_personas)) or "''"})""",
                    (pr["id"], *accepted_personas)
                ).fetchone()
            )
        )
        chosen = {}  # persona id -> candidate, settled in passes so relationships can be checked
        nearly = {}  # persona id -> candidate of the same name with a disagreement: proposed, never taken
        # among near candidates the same name comes before the fitting check's surname or relationship alone, then more agreements
        rank = lambda agree: (any(a.field == "given name" for a in agree), len(agree))
        for _ in range(2):
            for pr in personas:
                best = None
                close = None
                for c in cands:
                    fits, agree, disagree, absent, near = compare(cat, pr, c, chosen)
                    if fits and (best is None or len(agree) > len(best[1])):
                        best = (c, agree, disagree, absent)
                    if near and (close is None or rank(agree) > rank(close[1])):
                        close = (c, agree, disagree, absent)
                if best:
                    chosen[pr["id"]] = best[0]
                    nearly.pop(pr["id"], None)
                elif close:
                    chosen[pr["id"]] = close[0]
                    nearly[pr["id"]] = close[0]
        names = ", ".join(cat.person(pid)["name"] for pid, _, _ in contexts)
        carded = {
            r[0]
            for r in cx.execute(
                "SELECT json_extract(payload_json,'$.persona_id') FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.extraction_id')=? AND status='undecided'" + unless,
                (tree_id, eid, *ignore)
            )
        }
        # a relationship to one of these ties a persona to the record by more than its name
        ties = accepted_personas | carded | {o for o in chosen if o not in nearly}
        for pr in personas:
            # proposed already, unless that proposal was superseded
            if cx.execute(
                "SELECT 1 FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.persona_id')=? AND NOT (status='rejected' AND decision_note='superseded')" + unless,
                (tree_id, pr["id"], *ignore)
            ).fetchone():
                continue
            # decided already, accepted or rejected (a link carried across a re-extraction); an undecided link is no decision: one the rule took back, whose older card a newer matcher superseded, is proposed again
            if cx.execute(
                "SELECT 1 FROM person_persona pp JOIN person p ON p.id=pp.person_id WHERE pp.persona_id=? AND p.tree_id=? AND pp.status<>'undecided'",
                (pr["id"], tree_id)
            ).fetchone():
                continue
            # its entry on another copy of the record is proposed or decided there: one record, one decision
            if on_another_copy(cx, tree_id, pr["id"], ignore):
                continue
            # a relative such a page merely lists is a lead, never a card (docs/TERMS.md §0): tools/plan.py writes the fetch step instead
            if subject_role and pr["role"] != subject_role:
                continue
            if (
                pr["id"] in nearly
                and pr["role"] in ("result", "listed", "named in the text")
                and not any(
                    a.field not in ("given name", "surname") for a in compare(cat, pr, chosen[pr["id"]], chosen)[1]
                )
            ):
                # a row on a results page that is itself the record, a schedule row or a name in running text that agrees on the name alone is a hint on the page, not a card
                continue
            if (
                pr["id"] in nearly
                and (
                    any(o != pr["id"] and o not in nearly and chosen[o]["id"] == chosen[pr["id"]]["id"] for o in chosen)
                    or cx.execute(
                        """SELECT 1 FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id WHERE pe.extraction_id=? AND pp.status='accepted' AND pp.person_id=?""",
                        (eid, chosen[pr["id"]]["id"])
                    ).fetchone()
                )
            ):
                # another persona on this page fits, or is accepted as, that person: one decision put once; the near one stays a hint on the page
                continue
            # fits a person nothing yet attaches to this record: waits for the decision on the record's own person
            if pr["id"] in chosen and chosen[pr["id"]]["id"] not in open_now:
                continue
            if pr["id"] in nearly and by_name and not any(o in ties for _, _, o, _ in stated[pr["id"]]):
                c = chosen[pr["id"]]
                _, agree, disagree, _, _ = compare(cat, pr, c, chosen)
                # a namesake: the name, the sex and a bare year, something disagreeing, nothing more: a hint on the page
                if namesake(agree, disagree):
                    fields = {a.field for a in agree}
                    on = ["the name"] + ["the sex"] * ("sex" in fields) + ["a year of birth"] * ("birth date" in fields)
                    held[pr["id"]] = (
                        f"{pr['name']} ({pr['role']}) is a namesake of {c['name']}, not a card: the record was reached by a name search, agrees with "
                        f"{c['name']} on no more than {', '.join(on[:-1]) + ' and ' + on[-1] if len(on) > 1 else on[0]}, and disagrees: "
                            + "; ".join(said(d) for d in disagree)
                    )
                    continue
            # a new person is proposed only from a record already accepted as somebody's, for those it relates to them
            if pr["id"] not in chosen and not related_to_accepted(pr):
                continue
            if pr["id"] in chosen:
                c = chosen[pr["id"]]
                fits, agree, disagree, absent, near = compare(cat, pr, c, chosen)
                others = [o["name"] for o in cands if o["id"] != c["id"] and compare(cat, pr, o, chosen)[0]]
                text = f"{pr['name']} ({pr['role']}) may be {c['name']}" + (
                    (", though something disagrees. " if disagree else ", on the name alone. ")
                    if pr["id"] in nearly
                    else ". "
                ) + " ".join(s[0].upper() + s[1:] + "." for s in map(said, agree + disagree))
                if absent:
                    text += " Absent: " + ", ".join(map(said, absent)) + "."
                if others:
                    text += " Also fits: " + ", ".join(others) + "."
                kind, person_id, (pid, qid, step_id) = "persona_match", c["id"], ctx_of[c["id"]]
            # a row of a listing that is the record, a schedule row or a name in running text that fits nobody stays on the page as a hint, not a new person
            elif pr["role"] in ("result", "listed", "named in the text"):
                continue
            else:
                given, rest = split_persona_name(pr["name"])
                kin = [(kind, word, name) for kind, word, o, name in stated[pr["id"]] if o in accepted_personas]
                # a surname alone, a given name alone, a given name and an initial
                if not given or not rest or pr["name"] == "(unnamed)":
                    held[
                        pr["id"]
                    ] = f"{pr['name']} ({pr['role']}) is nobody to create, not a card: the record gives no full name to create a person under"
                    continue
                if not any(
                    kind in ("child", "parent", "spouse", "sibling") or KIN_WORD.search(word or "")
                    for kind, word, _ in kin
                ):
                    held[pr["id"]] = (
                        f"{pr['name']} ({pr['role']}) is nobody to create, not a card: the record relates them to "
                        + ", ".join(
                            f"{name} only as \"{word}\"" if word else f"{name} only under \"{kind}\" with no word"
                            for kind, word, name in kin
                        )
                        + ": no word of kinship to create a person on"
                    )
                    continue
                tried = [compare(cat, pr, c, chosen) for c in cands]
                why = "; ".join(
                    f"{c['name']}: " + (", ".join(map(said, d)) if d else "nothing agrees")
                    for c, (_, a, d, _, _) in zip(cands, tried)
                    if not a or d
                )[:600]
                text = f"{pr['name']} ({pr['role']}) fits nobody in the family of {names}. " + why
                kind, person_id, (pid, qid, step_id) = "new_person", None, contexts[0]
            out.append(
                {
                    "tree_id": tree_id,
                    "persona_id": pr["id"],
                    "name": pr["name"],
                    "kind": kind,
                    "person_id": person_id,
                    "subject_person_id": pid,
                    "question_id": qid,
                    "step_id": step_id,
                    "rationale": text
                }
            )
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extraction")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument(
        "--about",
        help="the person the record is about on the owner's word, when no step or link names them: a fetch step on their plan, done with a found run naming the record"
    )
    a = ap.parse_args()
    cx = connect(a.db)
    about = None
    cx.execute("BEGIN")
    # the owner's word: a fetch step on their plan, done with a found run naming the record, so every later reading finds them
    if a.about:
        from attach import on_word
        from treelib import resolve_tree
        tree_id, _ = resolve_tree(cx, None)
        about = [Catalog(cx, tree_id).find_person(a.about)]
        on_word(
            cx,
            tree_id,
            about[0],
            cx.execute("SELECT artifact_sha256 FROM extraction WHERE id=?", (a.extraction,)).fetchone()[0],
            a.by
        )
    written = match(cx, a.extraction, a.by, about=about)
    cx.commit()
    for prop, kind, name, person_id in written:
        print(f"{prop}  {kind:14} {name}")
        print("   ", cx.execute("SELECT rationale FROM proposal WHERE id=?", (prop,)).fetchone()[0])
    if not written:
        print("no new proposals")

if __name__ == "__main__":
    main()
