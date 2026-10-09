#!/usr/bin/env python3
"""One record is one source wherever it is held (docs/DATA-ARCHITECTURE.md §7 decision 15): code's joins of one archived
file to the other copies of its record (join_copies, same_record), the owner's word joining two copies or keeping two apart
(copies_on_word), a copy as the owner names it (copy_named), and a page read for every tree with the decisions carried to
its reading (read_page: the extraction, the decided links of the readings it supersedes moved to it, carry_links, its joins
written and the decisions on its other copies carried to it, then settled once), which every caller that reads a page runs. A
decision on one copy's entry is carried to every other copy's persona of that entry by decisions.carry, which a decision runs
itself and read_page and copies_on_word run for the page and the pair; the record under decision as the rule counts it, once,
and as every copy holds it, is tools/rule.py (record_self, copy_cards); tools/conclude.py is the command line (copies, apart).

- join_copies: each join written once and shared by every tree: one record id (an Ancestry apid or a FamilySearch ark), one
  FamilySearch entry id on both readings, or one certificate number of one year on two numbered entries agreeing by name
  (_number); code never joins a page anyone can edit to a record nobody can, nor a row of a search's results.
- copies_on_word: the owner's word on two archived copies, in this tree only, standing above anything code found for the
  pair: one record, and every decision on either carried to the other; or not one record, and what one carried to the other
  given back, the statements it wrote undecided again and the cards of those people matched again.
- copy_named: an archived file by its sha256 (or the first twelve or more of its characters) or its file name, and a
  listing's one row by the number after @.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import dumps, now, ulid
from catalog import is_identity, page_entries, persona_key, record_kinds
from readers import extract
from rule import _q, editable
from decisions import answer_questions, assert_facts, carry, link_family, link_people, match_record, memberships_of, settle_carried, settle_people

# ---------------------------------------------------------------- one record, wherever it is held
def _number(cx, persona_id, region_key, reading):
    """(the number's digits, its year) a numbered entry gives its record (catalog.NUMBERS): the year the index files it under
    ("14205 /1946"), else the year of the entry's own dated event, else the reading's record year.
    Implements [rule.extract.4]."""
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
    row of a search's results, whose own record is the document (docs/TERMS.md §0). Returns the rows written:
    (other sha256, basis, shared).
    Implements [rule.copies.3], [rule.copies.5], [rule.extract.4]."""
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

def carry_links(cx, old, eid, sha, by, ts):
    """A decided person-persona link on a superseded extraction moves to the new reading's persona of the same entry of the
    page (catalog.persona_key: its record id, else its role, row and name). An old persona whose entry no new persona carries
    (an older parser that wrote no identity, or wrote it otherwise) moves to the one new persona of its name and role only
    when it is also the one persona of that name and role on its own reading, and never from one record id to another;
    otherwise the link stays behind and the matcher proposes the persona again: a card coming back is safe, a link on another
    row is not. An accepted link asserts the new facts and links onto the person as the decision did, a statement whose status
    a person decided on its own (assertion.person_decided) keeping it. An undecided link is not a decision, so it does not
    carry. Returns how many links were carried, and the people whose evidence the accepted ones changed, {(tree id, person
    id): the decision's proposal}: each person an accepted link carried to, and everyone whose family a family link it wrote
    reaches, as a decision's (decisions.link_people: the member and the family's partners, and everyone in a family it put
    someone into anew), which decisions.settle_carried goes over."""
    n, carried, touched = 0, [], {}
    new = page_entries(cx, sha, eid)
    one_of = lambda entries, name, role: [e for e in entries if e[2] == name and e[3] == role]
    for o in old:
        was = page_entries(cx, sha, o)
        key_of = {pid: key for pid, _, _, _, key in was}
        for pp in cx.execute("""SELECT pp.person_id, pp.status, pp.proposal_id, pp.decided_by, pp.decided_at, pe.name_text, pe.role_in_record, p.tree_id, pe.id
                                FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN person p ON p.id=pp.person_id
                                WHERE pe.extraction_id=? AND pp.status IN ('accepted','rejected')""", (o,)).fetchall():
            k = key_of[pp[8]]
            to = [pid for pid, _, _, _, key in new if key == k]
            if not to:
                before, after = one_of(was, pp[5], pp[6]), one_of(new, pp[5], pp[6])
                if len(before) == 1 and len(after) == 1 and not (is_identity(k) and is_identity(after[0][4])): to = [after[0][0]]
            for pid in to:
                cx.execute("INSERT OR IGNORE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (pp[0], pid, pp[1], pp[2], pp[3], pp[4])); n += 1
                if pp[1] == "accepted": carried.append((pp[7], pp[0], pid, pp[2]))
    for tree_id, person_id, pid, prop_id in carried:            # links first, so the family relations see every accepted persona
        assert_facts(cx, tree_id, person_id, pid, prop_id, by, ts)
        touched[(tree_id, person_id)] = prop_id                  # a person's own decision over another's that linked them
        members = link_family(cx, tree_id, person_id, pid, sha, prop_id, by, ts)
        for who in link_people(cx, [(m["family"], m["person"], m["role"]) for m in members], joined=[m["family"] for m in members if m["new"]]):
            touched.setdefault((tree_id, who), prop_id)
    return n, touched

def read_page(cx, sha, by):
    """One archived page read for every tree, and the decisions carried to the reading: the extraction (readers.extract, which
    supersedes the page's earlier readings), the decided links of the superseded readings moved to the new reading's personas
    (carry_links), the page's joins to the other copies of its record written (join_copies) and the decisions on those copies
    carried to it (decisions.carry), then, once for the reading, the plans of the people whose evidence changed regenerated,
    the rule over their conflicts and their cards matched again (decisions.settle_carried); one audit row for the reading with
    its counts. Every caller that reads a page for a tree (the runner, the attach, the person screen, the harness, the
    extract command) reads it here. Returns (extraction id, counts), the counts naming failed for a page no parser claims.
    Implements [rule.copies.2], [rule.copies.3]."""
    eid, n, old, extractor, ts = extract(cx, sha, by)
    if "failed" in n: return eid, n
    n["links_carried"], touched = carry_links(cx, old, eid, sha, by, ts)
    n["copies_joined"] = len(join_copies(cx, sha, by, ts))      # the other copies of this record the archive holds (same_record), and the decisions on them
    copies = carry(cx, by, sha, settle=False)
    n["decisions_carried"] = len(copies)
    for c in copies:
        if c["kept"] is None: touched.setdefault((c["tree"], c["person"]), c["proposal"])
    settle_carried(cx, by, touched)                              # once for the reading: plans, the rule over conflicts, cards matched again
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, by, "insert", "extraction", eid, dumps({"extractor": ":".join(extractor[:2]) + "@" + extractor[2], **n})))
    return eid, n

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
    what a decision on one had carried to the other given back: the link on the copy, its statements under that decision and
    the name alias the carry wrote from its words undecided again (a statement whose status a person decided on its own,
    person_decided, keeping it), the plans, conflicts and cards gone over again of each person given back and of everyone
    whose family a family link given back with them reaches (link_people), and the copy matched again, its entry a card
    for the owner or the rule's. a, b: (sha256, entry). Returns the rows carried, or the links given back.
    Implements [rule.copies.3], [rule.plans.1]."""
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
            given = [
                aid
                for aid, in q.execute(
                    """SELECT id FROM assertion WHERE tree_id=? AND artifact_sha256=? AND status<>'undecided' AND NOT person_decided
                       AND json_valid(notes) AND json_extract(notes,'$.proposal')=?""",
                    (tree_id, x[0], pp["proposal_id"])
                ).fetchall()
            ]
            if given:
                q.execute(
                    f"UPDATE assertion SET status='undecided', asserted_by=?, asserted_at=? WHERE id IN ({','.join('?' * len(given))})",
                    (by, ts, *given)
                )
            # the copy's own words for the person, which the carry made an alias under that decision, go back with it
            q.execute(
                """UPDATE alias SET status='undecided' WHERE tree_id=? AND entity_kind='person' AND entity_id=? AND source_artifact_sha256=? AND status='accepted'
                         AND json_valid(notes) AND json_extract(notes,'$.proposal')=?""",
                (tree_id, pp["person_id"], x[0], pp["proposal_id"])
            )
            back.append(
                {"person": pp["person_id"], "persona": pp["persona_id"], "proposal": pp["proposal_id"], "copy": x[0]}
            )
            # the person given back, and everyone whose family a link given back with them reaches
            for who in [pp["person_id"]] + link_people(cx, memberships_of(cx, given)):
                people.setdefault(who, pp["proposal_id"])
    for pid, prop in people.items():
        answer_questions(cx, tree_id, pid, prop, by)
    settle_people(cx, tree_id, by, list(people))
    # the copy given back is matched again for the people it was given back from: its entry a card for the owner, or the rule's
    for sha in dict.fromkeys(b_["copy"] for b_ in back):
        match_record(
            cx,
            current_reading(cx, sha),
            by,
            about=list(dict.fromkeys(b_["person"] for b_ in back if b_["copy"] == sha))
        )
    return back
