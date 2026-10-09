#!/usr/bin/env python3
"""The rule's decisions examined again, as the rule stands now (docs/RULE.md, reconsider): every decision it made, in the order
it took them, on the ground that stood before each, and one it would no longer take withdrawn, the record a card for the
owner again, with the family links it was one of the two acceptances for (rule.links_resting_on), which no later decision
stands on; one it keeps brought to what a decision writes now (written_otherwise, bring_to_now: its name alias at the standing
of its record, a link the record's indexer computed undecided); then every undecided card the evidence has passed by matched
again (decisions.rematch), every card still undecided examined the same way and one the rule would now take taken
(decisions.decide), and the rule over everyone's conflicts (conflicts.rule_conflicts). Before all of it, every decision on one
copy of a record is carried to every other copy the archive holds (decisions.carry). A statement a person decided on its own
keeps its state throughout, and the same under a person's own decisions are listed as theirs to answer; --dry-run reports
what it would do. The command is tools/conclude.py (reconsider).

- withdraw: a decision taken back by the rule: the proposal and the persona link return to Undecided, every assertion the
  decision wrote returns to Undecided under the rule acting for whoever ran it, the links resting on it with them, the plans
  of everyone they reach regenerated.
- written_otherwise, bring_to_now: what a kept decision wrote that a decision would write otherwise now, and each set to
  what a decision writes, one audit row each.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import dumps, now, ulid
from catalog import current_entry, marked, relation_classes, source_tier
from plan import plan_person
from rule import RULE_ACTOR, TRUSTED, _q, links_resting_on, rule_accepts, same_personas
from conflicts import rule_conflicts
from decisions import carry, decide, decision_memberships, link_people, memberships_of, rematch, rematch_people

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
