#!/usr/bin/env python3
"""A duplicate merged into the person it duplicates, and the folds a merge and tools/initdb.py's migration make of a person's
or a family's events of one type that are one event. The merge closes a duplicate_person question (docs/TERMS.md §2;
docs/LOOP.md's worked example): the duplicate's persona links, assertions, event and family memberships, name aliases, plan
steps, runs, questions and proposals move onto the kept person, each folded onto what the kept person already holds where
they are the same (the movers below), the duplicate's row kept out of every listing (person.merged_into), and what follows
every decision follows it (decisions.settle_people, for everyone a family the merge changed reaches, merge_people). A merge
an older version of the tool left unfinished is completed by the command run again on the pair (complete_merge). The owner's
commands are tools/conclude.py (merge).

- fold, fold_plan: events of one type are one event when catalog.same_event says so, the owner's own word on an event's
  date or place (conflicts.owner_on_event) keeping two apart; the kept event takes a fuller date or a place it lacks
  (_take_lacking), its statements and notes move with their statuses (_fold_event, accepted_dates).
- _fold_family: a family whose partners are exactly another's, folded into that one; _partner_families, _back_to, the
  merge's reading of a person's families and its retire of a folded event.
- _move_memberships, _move_links, _move_aliases, _move_questions, _repoint_proposals: the duplicate's rows onto the kept
  person, folded where the kept person already holds the same.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import dumps, now, ulid
from catalog import Catalog, date_verdict, fuller_date, same_event
from plan import plan_person
from log_search import restate
from rule import _q
from conflicts import owner_on_event
from decisions import link_people, settle_people

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
