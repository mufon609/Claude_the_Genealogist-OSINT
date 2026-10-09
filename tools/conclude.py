#!/usr/bin/env python3
"""The owner's commands on the tree: the decision on a card, a key fact, one statement, a record's fact placed on its event,
the rule's re-examination of its own decisions, the owner's word on a family link, a divorce, a duplicate, whether a person is
alive, a conflict's resolution or its reopening, and two archived copies joined or kept apart. The decision code is by job:
the standing rule's tests are tools/rule.py, the rule's decisions on conflicts tools/conflicts.py, the decisions and what
follows every one tools/decisions.py (decide, match_record, the writers, the owner's word, settle_people), a person's key facts
tools/facts.py, the joins of a record's copies and the owner's word on them tools/copies.py; the merges (merge, fold) and
the rule's re-examination (reconsider, withdraw) are here still. Every command runs in one transaction, committed whole or
rolled back.

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

- fold, fold_plan: a person's or a family's events of one type that are one event folded into one, as a merge and
  tools/initdb.py's migration of an older catalog fold them.
- merge: a duplicate_person question closed, everything about the duplicate moved onto the person it duplicates.
- reconsider, withdraw: the rule's decisions examined again, in the order it took them, on the ground that stood before
  each; one it would no longer take, taken back with the family links it was one of the two acceptances for
  (rule.links_resting_on); one it keeps brought to what a decision writes now (written_otherwise, bring_to_now); then every
  undecided card the evidence has passed by matched again (decisions.rematch), and every card still undecided examined, one the
  rule would now take, taken; then the rule over everyone's conflicts (conflicts.rule_conflicts).
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, parse_gedcom_date, resolve_tree, ulid
from catalog import Catalog, current_entry, date_verdict, fuller_date, marked, relation_classes, same_event, source_tier
from plan import plan_person
from log_search import restate
from facts import KEY_FACTS, claimed_parts, decide_fact, evidence_rows, fact_status
from rule import RULE_ACTOR, TRUSTED, _q, links_resting_on, rule_accepts, same_personas
from conflicts import owner_on_event, rule_conflict_decisions, rule_conflict_line, rule_conflicts
from decisions import (
    carry,
    decide,
    decide_assertion,
    decision_memberships,
    divorce,
    link_on_word,
    link_people,
    living,
    memberships_of,
    place,
    record_says,
    rematch,
    rematch_people,
    reopen,
    resolve,
    settle_people
)
from copies import copies_on_word, copy_named

def _fold_event(q, eid, into, moved):
    """An event's statements and notes moved onto another of the same owner and type, their statuses unchanged; a statement
    of a record fact the other already carries, or a second vouch, stays where it is, so nothing is stated twice on one
    event. The event itself is left as it is. Returns (the statements moved, the statements left).
    Implements [rule.fold.3]."""
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

def fold_plan(cx, tree_id, owner):
    """The folds a person's events, or a family's, call for (fold); owner is ("person", id) or ("family", id). Events of one
    type are one event when catalog.same_event says so (places agreeing or one absent, and the type held once in a life or
    the dates one), an event joining a group when it is one with every event already in it, taken in the order the kept
    event is chosen: the event whose date or place the owner has spoken on (owner_on_event), then one a standing resolution
    of the rule's names, then the most accepted statements, the most statements, the earliest. One entry per group of two
    or more: {"type", "kept": event, "folded": [events], "refused": words when more than one event of the group carries the
    owner's word, so that a fold would set one value the owner resolved aside, else None}; each event is
    Catalog.owner_events' with its place_id, its statements counted, and the axes the owner ("owner") and the rule ("rule")
    have decided on it.
    Implements [rule.fold.1], [rule.fold.2], [rule.fold.5]."""
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
    owner's word with no fact of its own (a vouch) the event's own date, which is what the vouch accepted.
    Implements [rule.fold.3]."""
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
    brought up to date.
    Implements [rule.fold.3]."""
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
    """A person's events, or a family's, of one type that are one event folded into one (docs/RULE.md, one
    statement, one event; the groups and the kept event as fold_plan gives them), the same fold a merge makes of a
    duplicate's events: each folded event's statements and notes move onto the kept event as they are (_fold_event), the
    kept event takes what it lacks from it (_take_lacking), and the folded event leaves the owner's events (retire(event id),
    by default its participant row removed: the event row and anything left on it stay for the audit trail). A date the
    events give apart, on a type a life holds once, stays the kept event's own and the folded one's statements give the
    other, so the difference is the conflict question Catalog.disagreements raises. A group fold_plan refuses is left as it
    is and named in moved's folds_refused. actor: one audit row per event folded, naming what moved, under that actor.
    Returns one entry per event folded: the owner, the type, the kept and folded events' ids and values, the statements
    moved and left, and what the kept event took.
    Implements [rule.fold.1], [rule.fold.3], [rule.fold.4]."""
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
    is left emptied for the audit trail.
    Implements [rule.fold.1], [rule.merge.2]."""
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

def _move_memberships(q, dup_id, kept_id, moved):
    """A merge's family memberships: each of the duplicate's rows moves to the kept person with its statements; a row the kept
    person already holds in the same family and role (one child entered twice under the same parents) is folded as
    _fold_family folds a child of both, its statements onto the kept person's row and the duplicate's row gone, each named
    in folded_memberships with the statements it moved. Returns the families whose partner row moved.
    Implements [rule.merge.2]."""
    partner_fams = set()
    for fid, role in q.execute("SELECT family_id, role FROM family_member WHERE person_id=?", (dup_id,)).fetchall():
        was, into = dumps([fid, dup_id, role]), dumps([fid, kept_id, role])
        held = q.execute(
            "SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, kept_id, role)
        ).fetchone()
        statements = [
            a
            for a, in q.execute(
                "SELECT id FROM assertion WHERE subject_kind='family_member' AND subject_id=? ORDER BY id", (was,)
            ).fetchall()
        ]
        if held:
            q.execute("DELETE FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, dup_id, role))
        else:
            q.execute(
                "UPDATE family_member SET person_id=? WHERE family_id=? AND person_id=? AND role=?",
                (kept_id, fid, dup_id, role)
            )
        q.execute("UPDATE assertion SET subject_id=? WHERE subject_kind='family_member' AND subject_id=?", (into, was))
        if held:
            moved["folded_memberships"].append({"family_id": fid, "role": role, "statements": statements})
            continue
        moved["family_memberships"] += 1
        if role == "partner":
            partner_fams.add(fid)
    return partner_fams

def _repoint_proposals(q, tree_id, dup_id, kept_id, moved):
    """A merge's proposals: every proposal of the tree whose payload names the duplicate (a card's person_id, the
    subject_person_id the record was fetched for, whatever key holds the id) names the kept person instead, each listed in
    proposals_repointed with the keys it rewrote (rewritten), so a decision, a withdrawal, reconsider and the matcher read
    the kept person wherever the duplicate stood. A duplicate_person proposal is a merge's own record of who was merged into
    whom and keeps its words.
    Implements [rule.merge.1]."""
    keys = {}
    for r in q.execute(
        """SELECT p.id, j.key FROM proposal p, json_each(p.payload_json) j
           WHERE p.tree_id=? AND p.kind<>'duplicate_person' AND j.type='text' AND j.value=? ORDER BY p.id, j.key""",
        (tree_id, dup_id)
    ).fetchall():
        keys.setdefault(r["id"], []).append(r["key"])
    for prop_id, ks in keys.items():
        for k in ks:
            q.execute(
                "UPDATE proposal SET payload_json=json_set(payload_json, ?, ?) WHERE id=?", (f"$.{k}", kept_id, prop_id)
            )
        moved["proposals_repointed"].append({"proposal": prop_id, "rewritten": ks})

def _move_links(q, dup_id, kept_id, moved):
    """A merge's persona links: each of the duplicate's person_persona rows moves to the kept person; a row whose persona the
    kept person already links is folded onto theirs, as a membership the kept person holds is folded: the kept person's row
    stands, taking the duplicate's decision (its status, proposal, decider and moment) only where its own is undecided,
    which is no decision, and the duplicate's row goes, so no decision on that persona stays with the merged person. Each
    fold is named in folded_links with both rows as they were and whether the decision moved.
    Implements [rule.merge.2]."""
    cols = "status, proposal_id, decided_by, decided_at"
    for r in q.execute(f"SELECT persona_id, {cols} FROM person_persona WHERE person_id=? ORDER BY persona_id", (dup_id,)).fetchall():
        held = q.execute(f"SELECT {cols} FROM person_persona WHERE person_id=? AND persona_id=?", (kept_id, r["persona_id"])).fetchone()
        if not held:
            q.execute(
                "UPDATE person_persona SET person_id=? WHERE person_id=? AND persona_id=?", (kept_id, dup_id, r["persona_id"])
            )
            moved["persona_links"] += 1
            continue
        took = held["status"] == "undecided" and r["status"] != "undecided"
        if took:
            q.execute(
                "UPDATE person_persona SET status=?, proposal_id=?, decided_by=?, decided_at=? WHERE person_id=? AND persona_id=?",
                (r["status"], r["proposal_id"], r["decided_by"], r["decided_at"], kept_id, r["persona_id"])
            )
        q.execute("DELETE FROM person_persona WHERE person_id=? AND persona_id=?", (dup_id, r["persona_id"]))
        moved["folded_links"].append(
            {
                "persona": r["persona_id"],
                **{k: r[k] for k in ("status", "proposal_id", "decided_by", "decided_at")},
                "kept": {k: held[k] for k in ("status", "proposal_id", "decided_by", "decided_at")},
                "decision_moved": took
            }
        )

def _move_aliases(q, dup_id, kept_id, moved):
    """A merge's name aliases: each of the duplicate's moves to the kept person, named in aliases_moved; one whose words the
    kept person already holds as an alias is folded onto theirs, the kept person's row standing as it is (a person holds a
    name as written once, and write_name_alias never writes words the person already holds) and the duplicate's row gone,
    named whole in folded_aliases, the only trace of it afterwards.
    Implements [rule.merge.2]."""
    for a in q.execute("SELECT * FROM alias WHERE entity_kind='person' AND entity_id=? ORDER BY value, id", (dup_id,)).fetchall():
        if q.execute(
            "SELECT 1 FROM alias WHERE entity_kind='person' AND entity_id=? AND value=?", (kept_id, a["value"])
        ).fetchone():
            q.execute("DELETE FROM alias WHERE id=?", (a["id"],))
            moved["folded_aliases"].append(dict(a))
            continue
        q.execute("UPDATE alias SET entity_id=? WHERE id=?", (kept_id, a["id"]))
        moved["aliases_moved"].append({"alias": a["id"], "value": a["value"]})

def _move_questions(q, dup_id, kept_id, prop_id, ts, moved):
    """A merge's research questions: each of the duplicate's moves to the kept person, save the duplicate_person question
    between the two (the merge's own to answer) and one whose key the kept person already holds, in any status: the kept
    person's question asked twice, which an open one on the duplicate closes as answered by the merge (answered_by_proposal_id
    the merge's duplicate_person proposal), each named in closed_questions by its id, key and kind.
    Implements [rule.merge.2]."""
    for question in q.execute("SELECT * FROM research_question WHERE subject_person_id=? ORDER BY id", (dup_id,)).fetchall():
        if question["kind"] == "duplicate_person" and question["q_key"] == f"duplicate_person:{kept_id}":
            continue
        if q.execute(
            "SELECT 1 FROM research_question WHERE subject_person_id=? AND q_key=?", (kept_id, question["q_key"])
        ).fetchone():
            if question["status"] == "open":
                q.execute(
                    "UPDATE research_question SET status='closed', closed_reason='answered', closed_at=?, answered_by_proposal_id=? WHERE id=?",
                    (ts, prop_id, question["id"])
                )
                moved["closed_questions"].append(
                    {
                        "question": question["id"],
                        "q_key": question["q_key"],
                        "kind": question["kind"],
                        "reason": "the kept person holds a question of this key: closed as answered by the merge"
                    }
                )
            continue
        q.execute("UPDATE research_question SET subject_person_id=? WHERE id=?", (kept_id, question["id"]))
        moved["questions_moved"] += 1

def merge_people(cx, kept_id, dup_fams, moved):
    """Everyone whose family a merge changed, the kept person first: everyone in each family the duplicate's memberships moved
    into (dup_fams, read before they moved) and in each family a fold emptied another into (folded_families), the family's
    shape changed for each of them (link_people's joined: the kept person's spouses, children, parents and siblings there).
    Implements [rule.plans.1]."""
    joined = dict.fromkeys(list(dup_fams) + [f["into_family_id"] for f in moved["folded_families"]])
    return list(dict.fromkeys([kept_id] + link_people(cx, [], joined=joined)))

def complete_merge(cx, tree_id, dup_id, kept_id, by, note):
    """A merge made before a merge did all it does now, completed: a persona link the duplicate still holds moved or folded
    onto the kept person's (_move_links), a family membership moved or folded the same way (_move_memberships), its name
    aliases moved or folded (_move_aliases), a question still on it closed as answered by the merge where the kept person
    holds its key, else moved (_move_questions, answered by the pair's own duplicate_person proposal), every proposal still
    naming the duplicate re-pointed to the kept person (_repoint_proposals), the kept person's events folded as a merge
    folds them (fold), each folded event's participant returned to the duplicate's row (_back_to); the kept person's partner
    families with the same partners folded into the earliest (_fold_family), and that family's events folded the same way.
    Nothing else moves, and a merge already complete changes nothing. One audit row; then the plans of everyone whose family
    it changed are regenerated (merge_people: the kept person and everyone in a family a membership moved into or a fold
    emptied another into), the rule goes over their conflicts and their cards are matched again (settle_people). Returns
    what moved and folded, the rule's rows on the conflicts and the cards matched again.
    Implements [rule.merge.3]."""
    q = _q(cx)
    ts = now()
    moved = {
        "persona_links": 0,
        "family_memberships": 0,
        "events_folded": 0,
        "event_assertions_folded": 0,
        "families_folded": 0,
        "family_children_moved": 0,
        "family_events_moved": 0,
        "questions_moved": 0,
        "folded_links": [],
        "folded_memberships": [],
        "aliases_moved": [],
        "folded_aliases": [],
        "closed_questions": [],
        "proposals_repointed": [],
        "folded_events": [],
        "folded_families": []
    }
    merged_by = q.execute(
        """SELECT id FROM proposal WHERE tree_id=? AND kind='duplicate_person' AND json_extract(payload_json,'$.duplicate_person_id')=?
           AND json_extract(payload_json,'$.kept_person_id')=? ORDER BY created_at DESC, id DESC""",
        (tree_id, dup_id, kept_id)
    ).fetchone()
    dup_fams = [f for f, in q.execute("SELECT DISTINCT family_id FROM family_member WHERE person_id=?", (dup_id,)).fetchall()]
    _move_links(q, dup_id, kept_id, moved)
    _move_memberships(q, dup_id, kept_id, moved)
    _move_aliases(q, dup_id, kept_id, moved)
    _move_questions(q, dup_id, kept_id, merged_by["id"] if merged_by else None, ts, moved)
    _repoint_proposals(q, tree_id, dup_id, kept_id, moved)
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
    people = merge_people(cx, kept_id, dup_fams, moved)
    for pid in people:
        plan_person(cx, tree_id, pid, by)
    conflicts, rematched = settle_people(cx, tree_id, by, people)
    return {
        "duplicate": dup_id,
        "kept": kept_id,
        "completed": True,
        **moved,
        "conflicts": conflicts,
        "rematched": rematched
    }

def merge(cx, tree_id, dup_id, kept_id, by, note):
    """Close a duplicate_person question (docs/TERMS.md §2; docs/LOOP.md's worked example, "merging the two Thomas entries closes
    the question"): the duplicate's persona links, assertions, event and family memberships, name aliases, plan steps, search
    log rows and questions move onto the person it duplicates; a persona link whose persona the kept person already links is
    folded onto theirs, the kept person's row taking the duplicate's decision only where its own is undecided (_move_links),
    a membership the kept person already holds in the same family and role folded onto theirs with its statements
    (_move_memberships), an alias of words the kept person already holds folded onto theirs (_move_aliases), and a question
    whose key the kept person already holds, in any status, left on the duplicate and closed, where open, as answered by the
    merge (_move_questions), so nothing open and no decision stays with the merged person; every proposal naming the
    duplicate re-pointed to the kept person (_repoint_proposals), `person.merged_into` is set so the duplicate's own row stays
    for the audit trail but out of every listing, overview, plan and matcher run, and one `duplicate_person` proposal records
    the decision with the owner's note; the duplicate_person question between the two, on either side, closes answered by
    it. A moved step the kept person's plan already has by step_key keeps whichever of the two carries search_log runs
    (neither carrying runs keeps the kept person's own); the duplicate's runs, if any, are carried onto the survivor rather
    than lost, each a new row restating it (log_search.restate), the duplicate's step left on its row, skipped, holding the
    runs it superseded. A dropped step, a closed question and a folded link or alias are named in the audit row (a step by
    its key, row and rationale, and why it was dropped, the way plan.py's own audit row names what it drops).

    The duplicate's events join the kept person's, and the kept person's events of one type that are then one event are
    folded (fold, docs/RULE.md: places agreeing or one absent, and the type held once in a life or the
    dates one): the statements move onto the kept event, and each folded event and its participant are left on the
    duplicate's row (_back_to), so the kept person never carries two Birth or two Death events; a date the two give apart is
    the conflict question the catalog raises. A duplicate's own family, once its membership has moved, whose partners are
    then exactly the kept person's own family's partners is folded the same way: its children's memberships and its own
    events move to that family, its partner memberships and their assertions fold onto the kept family's own, the family's
    events that are then one event fold too, and the duplicate's family row is left emptied, with the duplicate, for the
    audit trail (a child of both joins the kept family's own membership). Then the plans of everyone whose family the merge
    changed are regenerated (merge_people: the kept person and everyone in a family a membership moved into or a fold
    emptied another into, so the duplicate's spouse, children and parents see the kept person in its place), the rule goes
    over their conflicts and their cards are matched again (settle_people). A pair already merged is completed instead
    (complete_merge). Returns what moved, the rule's rows on the conflicts and the cards matched again.
    Implements [rule.merge.1], [rule.merge.2], [rule.fold.1]."""
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
        "questions_answered": 0,
        "dropped_steps": [],
        "closed_questions": [],
        "folded_links": [],
        "folded_memberships": [],
        "aliases_moved": [],
        "folded_aliases": [],
        "proposals_repointed": [],
        "folded_events": [],
        "folded_families": []
    }

    dup_fams = [f for f, in q.execute("SELECT DISTINCT family_id FROM family_member WHERE person_id=?", (dup_id,)).fetchall()]
    _move_links(q, dup_id, kept_id, moved)

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

    partner_fams = _move_memberships(q, dup_id, kept_id, moved)
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
    _move_aliases(q, dup_id, kept_id, moved)

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
    _move_questions(q, dup_id, kept_id, prop_id, ts, moved)

    _repoint_proposals(q, tree_id, dup_id, kept_id, moved)
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
    people = merge_people(cx, kept_id, dup_fams, moved)
    for pid in people:
        plan_person(cx, tree_id, pid, by)
    conflicts, rematched = settle_people(cx, tree_id, by, people)
    return {"proposal": prop_id, "duplicate": dup_id, "kept": kept_id, **moved, "conflicts": conflicts, "rematched": rematched}

def withdraw(cx, tree_id, prop_id, by, why, ts):
    """The rule takes back a decision it would no longer make: the proposal and the persona link return to Undecided, every
    assertion the decision wrote returns to Undecided under by, the rule acting for whoever ran it, save one whose status a
    person has decided on its own since (person_decided), which keeps it; and so does the name alias it wrote (an Accept
    later makes them Accepted again), and every family link the decision was one of the two acceptances for, written by the
    other's decision, with the family facts written with a spouse link (links_resting_on: accepting either card again
    writes it again); the questions the decision answered are closed as gap_gone so the plan reopens the ones whose gap is
    back, the plans of the person, of the person the record was fetched for and of everyone whose family the links taken
    back reach (link_people) are regenerated, and the audit row says why. The record is a card for
    the owner again. Returns how many assertions were taken back.
    Implements [rule.reconsider.5], [rule.reconsider.7], [rule.name.4], [rule.own.3]."""
    q = _q(cx)
    p = q.execute(
        "SELECT * FROM proposal WHERE id=? AND tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%'",
        (prop_id, tree_id)
    ).fetchone()
    if not p:
        raise ValueError("not a decision the rule made")
    pay = json.loads(p["payload_json"])
    links = links_resting_on(cx, tree_id, prop_id)
    # everyone whose family the links taken back reach: the decision's own and those it was one of the two acceptances for
    linked = link_people(cx, decision_memberships(cx, tree_id, prop_id) + memberships_of(cx, links))
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

def written_otherwise(cx, tree_id, prop):
    """What a decision wrote that decide would write otherwise now (docs/RULE.md, reconsider): each name
    alias it wrote whose status is not the standing its record gives now (write_name_alias: accepted from a record nobody
    can edit at will, T1–T3, undecided from a page anyone can edit or a record of no known tier), and each family-link
    statement it wrote accepted whose relationship the record's current reading gives as its indexer's (link_family's
    reading, catalog.relation_classes: the relationship in the statement's own words between the decision's entry on that
    reading and the person the other entry is accepted as, an in-law's tie to the relative it resolves to, computed and
    never stated), which decide writes undecided as the indexer's. A statement a person decided on its own
    (person_decided) is theirs and never among them. Returns one row each: kind (alias or link), the row's id, the person
    it is about, the record, what it is in words, the status it holds and the one it would hold, why, and the note its audit
    row carries (a link's the note decide writes for an indexer's grouping).
    Implements [rule.reconsider.6]."""
    q = _q(cx)
    pay = json.loads(prop["payload_json"])
    me = pay.get("person_id")
    name = lambda pid: (q.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone() or {"display_name": "?"})["display_name"]
    out = []
    for a in q.execute("""SELECT id, entity_id, value, status, source_artifact_sha256 FROM alias WHERE tree_id=? AND entity_kind='person'
                          AND status IN ('accepted','undecided') AND json_valid(notes) AND json_extract(notes,'$.proposal')=? ORDER BY id""", (tree_id, prop["id"])).fetchall():
        trusted = str(source_tier(cx, a["source_artifact_sha256"]) or "")[:2] in TRUSTED
        if a["status"] != ("accepted" if trusted else "undecided"):
            out.append(
                {
                    "kind": "alias",
                    "id": a["id"],
                    "person": a["entity_id"],
                    "record": a["source_artifact_sha256"],
                    "what": f"the name as the record writes it, {a['value']}",
                    "was": a["status"],
                    "now": "accepted" if trusted else "undecided",
                    "why": "an alias takes the standing of its record, "
                    + ("one nobody can edit at will" if trusted else "a page anyone can edit")
                }
            )
    if not me:
        return out
    accepted_as = lambda z: next((r[0] for r in q.execute("""SELECT pp.person_id FROM person_persona pp JOIN person o ON o.id=pp.person_id
                                                              WHERE pp.persona_id=? AND pp.status='accepted' AND o.tree_id=?""", (z, tree_id))), None)
    for s in q.execute(f"""SELECT a.id, a.subject_id, a.persona_id, a.artifact_sha256, a.citation_text FROM assertion a WHERE a.tree_id=? AND a.subject_kind='family_member'
                           AND a.status='accepted' AND NOT a.person_decided AND NOT {marked('a')} AND json_valid(a.notes) AND json_extract(a.notes,'$.proposal')=? ORDER BY a.id""", (tree_id, prop["id"])).fetchall():
        cur = current_entry(cx, s["persona_id"]) if s["persona_id"] else None
        if not cur:
            continue
        word = re.sub(r"\s+on the record$", "", s["citation_text"] or "")
        fid, who, role = json.loads(s["subject_id"])
        fam = {r[0] for r in q.execute("SELECT person_id FROM family_member WHERE family_id=?", (fid,))}
        rows = []
        for r in q.execute("""SELECT persona_id, related_persona_id, kind, value_text FROM persona_relation
                              WHERE (persona_id=? OR related_persona_id=?) AND coalesce(nullif(value_text,''), kind)=?""", (cur, cur, word)).fetchall():
            them = accepted_as(r["related_persona_id"] if r["persona_id"] == cur else r["persona_id"])
            # an in-law's tie is the decision's person's link to the relative it resolves to (resolve_in_law)
            if them and (me in fam and who in fam if r["kind"] == "other" else who in (me, them) and me in fam and them in fam):
                rows.append((r, them))
        if rows and all(
            relation_classes(cx, r["persona_id"], r["related_persona_id"], r["kind"], r["value_text"])["relationship"] == "computed"
            for r, _ in rows
        ):
            out.append(
                {
                    "kind": "link",
                    "id": s["id"],
                    "person": who,
                    "record": s["artifact_sha256"],
                    "what": f"{name(who)}'s {'parents' if role == 'child' else 'spouse'} link ({s['citation_text']})",
                    "was": "accepted",
                    "now": "undecided",
                    "why": "the record's indexer, not the record, states it",
                    "note": f"the link to {name(rows[0][1])} ({word}) written undecided: the record's indexer, not the record, states it"
                }
            )
    return out

def bring_to_now(cx, tree_id, prop_id, rows, by, ts):
    """What a kept decision wrote brought to what decide writes now (written_otherwise's rows): each alias to the standing of
    its record, each family link the record's indexer computed undecided and marked so (link_family's mark, so a later
    acceptance of the card writes it undecided as well), under by, the rule acting for whoever ran it; one audit row each,
    and the plans of everyone whose family a link reaches regenerated (link_people).
    Implements [rule.reconsider.6]."""
    q = _q(cx)
    for r in rows:
        if r["kind"] == "alias":
            q.execute("UPDATE alias SET status=? WHERE id=?", (r["now"], r["id"]))
        else:
            q.execute(
                "UPDATE assertion SET status='undecided', asserted_by=?, asserted_at=?, notes=json_set(notes,'$.computed',json('true')) WHERE id=?",
                (by, ts, r["id"])
            )
        q.execute(
            "INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                ulid(),
                tree_id,
                ts,
                by,
                "update",
                "alias" if r["kind"] == "alias" else "assertion",
                r["id"],
                dumps({"was": r["was"], "now": r["now"], "proposal": prop_id, "note": r.get("note") or f"{r['what']} written {r['now']}: {r['why']}"})
            )
        )
    for pid in link_people(cx, memberships_of(cx, [r["id"] for r in rows if r["kind"] == "link"])):
        plan_person(cx, tree_id, pid, by)

def settled_lines(res):
    """What followed a decision, one line each, as the command line tells it: each decision of the rule on a conflict
    (rule_conflict_line), then each card it superseded (superseded_lines).
    Implements [rule.conflict.8]."""
    return [rule_conflict_line(x) for x in rule_conflict_decisions(res.get("conflicts") or [])] + superseded_lines(
        res.get("rematched") or []
    )

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
    of the two acceptances for (links_resting_on), which no decision examined after it stands on either. One it keeps is
    brought to what decide writes now (written_otherwise, bring_to_now): the name alias it wrote to the standing of its
    record, and a family link it wrote accepted that the record's current reading gives as its indexer's grouping
    undecided, each with an audit row as the rule acting for by; the same under a person's own decision are never changed,
    returned last as theirs to answer. Then every
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
    card superseded or rewritten, per card and per conflict, per decision carried to a copy, and per alias or link brought
    to what decide writes now or left to the person: kind (decision, rematch, rationale, card, resolution, conflict,
    carried, standing or theirs), the person, kept or taken, why; a card's rows the proposal and the persona, a conflict's
    the question and its line, a standing or theirs row the decision's person and persona, the record, what it is, the
    status it holds and the one a decision writes now. A dry run examines the cards a run would leave, a decision it would withdraw among them, on the ground a run
    would leave (without the decisions it would withdraw and the links they take back): not the ones it would supersede.
    Implements [rule.reconsider.5], [rule.reconsider.6], [rule.reconsider.7], [rule.reconsider.8], [rule.copies.5], [rule.conflict.2]."""
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
    def otherwise_row(p, w, kind):
        """A row of written_otherwise as reconsider returns it: under a decision of the rule's it keeps (standing), or under a
        person's own (theirs)."""
        return {
            "proposal": p["id"],
            "person": name(json.loads(p["payload_json"])),
            "persona": persona(json.loads(p["payload_json"])),
            "kind": kind,
            "taken": kind == "standing",
            "record": q.execute(
                "SELECT coalesce(original_filename, substr(sha256,1,12)) FROM artifact WHERE sha256=?", (w["record"],)
            ).fetchone()[0],
            **{k: w[k] for k in ("what", "was", "now", "why")}
        }
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
        if ok:
            # what the kept decision wrote, brought to what decide writes now; a link a withdrawal in this pass took back is gone
            otherwise = [w for w in written_otherwise(cx, tree_id, p) if w["id"] not in unlinked]
            if otherwise and not dry_run:
                bring_to_now(cx, tree_id, p["id"], otherwise, f"{RULE_ACTOR[p['kind']]} for {by}", ts)
            out += [otherwise_row(p, w, "standing") for w in otherwise]
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
    out += [r for r in cards.values() if still(r)] + conflicts + rematch_people(cx, tree_id, by, moved)
    # the same under a person's own decisions: theirs to answer, never the rule's to change
    for p in q.execute("""SELECT * FROM proposal WHERE tree_id=? AND status='accepted' AND kind IN ('persona_match','new_person')
                          AND coalesce(decided_by,'') NOT LIKE 'rule:%' ORDER BY decided_at, id""", (tree_id,)).fetchall():
        out += [otherwise_row(p, w, "theirs") for w in written_otherwise(cx, tree_id, p)]
    return out

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
            for line in settled_lines(res):
                print("   ", line)
        elif a.cmd == "fact":
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
            for e in evidence_rows(cx, pid, a.field):
                print(
                    f"    {e['id'][-6:]} {e['status']:9} {e['tier'] or '-':5} {e['citation'] or ''}"
                    + (" (your own word)" if e["vouched"] else " (the file's uncited claim)" if e["uncited"] else "")
                )
            for line in settled_lines(res):
                print("   ", line)
        elif a.cmd == "assertion":
            res = decide_assertion(
                cx,
                tree_id,
                a.assertion,
                {"accept": "accepted", "reject": "rejected", "undecided": "undecided"}[a.verdict],
                a.by,
                a.note
            )
            if "error" in res:
                raise SystemExit(res["error"])
            print(
                f"assertion {res['assertion'][-6:]} on {res['subject_kind']} ({res['citation'] or ''}): {res['was']} -> {res['status']}; plan regenerated for {len(res['people'])} person(s)"
            )
            for line in settled_lines(res):
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
            for line in settled_lines(res):
                print("   ", line)
        elif a.cmd == "facts":
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
                if x["kind"] in ("standing", "theirs"):
                    print(
                        f"{('would set' if a.dry_run else 'set') if x['kind'] == 'standing' else 'yours to answer':19} {x['person']} <- {x['persona']} [{x['proposal'][-6:]}]: "
                        f"{x['what']}, on {x['record']}, {x['was']}"
                        + (f", now {x['now']}" if x["kind"] == "standing" and not a.dry_run else f"; decided now it is {x['now']}")
                        + f": {x['why']}"
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
                    f"{sum(1 for x in rows if x['kind'] == 'conflict' and not x['taken'])} left to you, "
                    f"{sum(1 for x in rows if x['kind'] == 'standing')} alias(es) and link(s) of kept decisions {'it would set' if a.dry_run else 'set'} as a decision writes them now, "
                    f"{sum(1 for x in rows if x['kind'] == 'theirs')} under your own decisions yours to answer"
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
                res = link_on_word(
                    cx, tree_id, pid, cat.find_person(a.spouse), "spouse", a.record, a.by, a.note, marriage=marriage
                )
            else:
                res = link_on_word(
                    cx, tree_id, pid, [cat.find_person(x) for x in a.parent], "child", a.record, a.by, a.note
                )
            print(
                f"family {res['family']}: {a.person} placed on your word; the record {a.record[:12]} carries the assertion"
            )
            for line in settled_lines(res):
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
            res = divorce(cx, tree_id, cat.find_person(a.a), cat.find_person(a.b), a.date, ev, a.by, a.note)
            print(f"divorce event {res['event']} between {a.a} and {a.b}")
            for line in settled_lines(res):
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
            for line in settled_lines(res):
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
            for line in settled_lines(res):
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
                    f"{a.duplicate} already merged into {a.kept}; completed: {res['persona_links']} persona link(s) moved "
                    f"({len(res['folded_links'])} folded onto the kept person's own), {res['family_memberships']} family membership(s) moved, "
                    f"{len(res['folded_memberships'])} folded onto the kept person's own, {len(res['aliases_moved'])} alias(es) moved "
                    f"({len(res['folded_aliases'])} folded), {res['questions_moved']} question(s) moved, {len(res['closed_questions'])} the kept "
                    f"person holds closed as answered by the merge, {len(res['proposals_repointed'])} proposal(s) re-pointed, "
                    f"{res['events_folded']} event(s) folded ({res['event_assertions_folded']} statement(s) moved), "
                    f"{res['families_folded']} family(ies) folded ({res['family_children_moved']} child membership(s), {res['family_events_moved']} family event(s))"
                )
            else:
                print(
                    f"{a.duplicate} merged into {a.kept}: {res['persona_links']} persona link(s) ({len(res['folded_links'])} more folded onto "
                    f"the kept person's own), {res['assertions']} assertion(s), "
                    f"{res['event_participants']} event participant(s), {res['family_memberships']} family membership(s) "
                    f"({len(res['folded_memberships'])} more folded onto the kept person's own), {len(res['aliases_moved'])} alias(es) "
                    f"({len(res['folded_aliases'])} more folded), {len(res['proposals_repointed'])} proposal(s) re-pointed, "
                    f"{res['plan_steps_moved']} plan step(s) moved ({res['plan_steps_dropped']} dropped as already on the kept person's plan, "
                    f"{res['log_rows_carried']} run(s) carried onto it), {res['questions_moved']} question(s) moved "
                    f"({len(res['closed_questions'])} the kept person holds closed as answered by the merge), "
                    f"{res['questions_answered']} duplicate question(s) answered; proposal {res['proposal']}"
                )
            for line in settled_lines(res):
                print("   ", line)
        cx.commit()
    except Exception:
        cx.rollback()
        raise

if __name__ == "__main__":
    main()
