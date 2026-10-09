#!/usr/bin/env python3
"""Conflicts on an event's date or place: the rule's test on one, what a resolution writes and what taking one back restores,
the rule over a set of people's conflicts, and the comparison of a conflict's sides that the test and the proof
(tools/proof.py) share. The owner's own resolve and reopen are commands of tools/decisions.py, which settle what follows;
tools/conclude.py is the command line.

The rule decides a conflict on an event's date or place when the classes favour one side without doubt (classes_decide,
docs/RULE.md, the proof standard): one side holds the event first-hand, primary information from the record of the event
itself, and every other rests only on secondary or indeterminable information, a page anyone can edit or the file's claim. It
resolves such a conflict through the owner's own resolve, its reason in words as the note, after every decision that changes
a person's evidence and in reconsider, which also examines its earlier resolutions again and takes back one it would no
longer make, the event's value restored. Every other conflict is the owner's, and the owner's own resolve, or a reopen,
stands above the rule's (owner_decided, owner_on_event).

- write_resolution: a conflict question closed with a written reason naming the value kept, by the owner or by the rule
  acting for them; the kept statement's date or place becomes the event's, the others set aside as their records say.
- take_back: a resolution of the rule's taken back, by the rule (rule_conflicts) or the owner (reopen), the event's value
  restored; rule_resolution, the resolution the rule wrote on a question.
- rule_conflicts: the rule over these people's conflicts, acting for the owner (RULE_ACTOR conflict): its earlier
  resolutions examined again (kept_agrees), then each open conflict decided where classes_decide finds a side; its rows are
  what a decision reports, as words through rule_conflict_line, rule_conflict_decisions and rule_conflict_changes (the audit
  log after a row); conflict_lines, the catalog's conflict lines on a person's events now.
- The sides of a conflict: subject_statements, the statements on one subject with their class words (decider, who made each
  decision); sides, the values the statements give grouped where they agree (same_value, axis_value, specificity), each
  side's best statement in the classes' own order (order); words, a statement's classes as a line prints them; record_info,
  what a line says about an archived record. A sort key of words, never a score.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import dumps, now, ulid
from catalog import BOUNDS, Catalog, date_verdict, evidence_classes, not_withdrawn, place_verdict, source_tier
from plan import plan_person
from rule import RULE_ACTOR, TRUSTED, _q, editable

def owner_on_event(cx, tree_id, eid, axis):
    """How the owner has spoken on this event's own date or place, by the event itself: 'resolved' (a conflict on it the
    owner resolved), 'reopened' (a resolution of the rule's on it the owner took back), else None.
    Implements [rule.fold.2]."""
    q = _q(cx)
    for r in q.execute("""SELECT json_extract(detail_json,'$.resolution.by') AS by FROM research_question WHERE tree_id=? AND kind='conflict' AND closed_reason='resolved'
                          AND json_valid(detail_json) AND json_extract(detail_json,'$.resolution.event')=? AND json_extract(detail_json,'$.resolution.axis')=?""", (tree_id, eid, axis)):
        if not str(r["by"] or "").startswith("rule:"):
            return "resolved"
    if q.execute("""SELECT 1 FROM audit_log WHERE tree_id=? AND entity_kind='research_question' AND actor NOT LIKE 'rule:%' AND json_valid(diff_json)
                    AND json_extract(diff_json,'$.reopened') IS NOT NULL AND json_extract(diff_json,'$.event')=? AND json_extract(diff_json,'$.axis')=?""", (tree_id, eid, axis)).fetchone():
        return "reopened"
    return None

# a conflict line's own opening: the event type, lowercased, and the axis (Catalog.disagreements)
CONFLICT_AXIS = re.compile(r"^(.+?) (date|place): ")

def write_resolution(cx, tree_id, qid, keep, by, note):
    """A conflict question closed with a written reason naming the value kept (docs/RULE.md, the proof
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
    gives no value on that axis, or the place it gives is not yet resolved to a place. Returns what was done, the people it
    was about among it, or an error.
    Implements [rule.conflict.4], [rule.conflict.7], [rule.conflict.9]."""
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
            write_resolution(cx, tree_id, reopened["id"], keep, by, note)
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
        "questions_closed": closed,
        "people": list(dict.fromkeys(people))
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
    to the owner. None when the owner has not.
    Implements [rule.conflict.6]."""
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
    """The rule's test on a conflict about one event's date or place (docs/RULE.md, the proof standard:
    conflicts kept, cited, pointed out, then decided): (the assertion id of the statement it keeps, or None; why, a sentence
    in words from the classes). The statements on the event of its own type, rejected ones, the owner's own word and those
    resting on a withdrawn file (evidence for nothing) aside, are read by their classes (data/evidence-classes.csv,
    catalog.evidence_classes), a place compared as the place its words are resolved to, as Catalog.disagreements compares it. A statement holds the event first-hand when it is primary
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
    (sides). No first-hand statement, primary information against it, the owner's word against it, a difference left
    beside it, or an owner who has spoken on this event's date or place before (owner_decided): no decision, the conflict is
    the owner's, and the reason says which. A place is kept only once its words are resolved to a place, as resolve needs,
    the rule otherwise waiting on the owner's answer to the words.
    Implements [rule.conflict.5], [rule.conflict.6], [rule.conflict.9], [rule.editable.11], [rule.points.9]."""
    from catalog import evidence_table
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
        if s["status"] == "rejected" or s["withdrawn"]:
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
        """Why a primary statement does not hold the event first-hand, or None when it does.
        Implements [rule.conflict.5]."""
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
    Returns the question ids set back.
    Implements [rule.conflict.2], [rule.conflict.7]."""
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

def rule_conflict_decisions(rows):
    """The rows of rule_conflicts that are decisions the rule made: a conflict it resolved (kind conflict, taken) and a
    resolution of its own it took back (kind resolution, not kept)."""
    return [
        x for x in rows if (x["kind"] == "conflict" and x["taken"]) or (x["kind"] == "resolution" and not x["kept"])
    ]

def rule_conflict_line(row):
    """One decision of the rule on a conflict, in words, as the decision's printout, the person screen and the turn's report
    tell it: the person, the date or place kept, the rule's reason, and how to give it back (reopen takes the question's id).
    Implements [rule.conflict.8]."""
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
    resolution, not kept), in the order they were written, as the rows rule_conflicts returns, the reason in the rule's own words.
    Implements [rule.conflict.8]."""
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
    open conflict on an event's date or place: where classes_decide keeps a statement it is resolved through
    write_resolution, the owner's own path, the rule's reason as the note; every other stays the owner's with the reason the
    rule left it. A person whose open conflict questions no longer read as the catalog does is planned again first, so the
    question resolved is the one the catalog gives; dry_run writes nothing and reads the catalog's own lines instead.
    Returns one row per
    resolution examined (kind resolution: kept, why) and per conflict decided or left (kind conflict: taken, why), each
    with the person, the question, its line and the date or place kept (value; none for a conflict left, or one a dry run
    would resolve); known, the questions the rule had resolved before a run that decides cards first (reconsider), makes a
    resolution written since, inside one of those decisions, a row of kind conflict taken, as one this pass wrote.
    Implements [rule.conflict.2], [rule.conflict.5], [rule.conflict.6]."""
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
                r = write_resolution(cx, tree_id, qid, keep, actor, why)
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
    the same date or place, on the same side).
    Implements [rule.conflict.2]."""
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

INFORMATION = ("primary", "secondary", "indeterminable", None)    # the order the classes favour a side in, best first

SOURCE = ("original", "derivative", "authored", None)

EVIDENCE = ("direct", "indirect", None)

def order(c):
    """The classes' own order for favouring a side: the record of the event itself (primary information) first, then the
    source (original over derivative over authored), then the evidence (direct over indirect). A sort key of words, never
    shown and never a score.
    Implements [rule.proof.1]."""
    c = c or {}
    return (INFORMATION.index(c.get("information")) if c.get("information") in INFORMATION else 3,
            SOURCE.index(c.get("source")) if c.get("source") in SOURCE else 3,
            EVIDENCE.index(c.get("evidence")) if c.get("evidence") in EVIDENCE else 2)

def words(c):
    """A statement's classes as the words a line prints: source, information, evidence, and a family link's relationship.
    Implements [rule.proof.1]."""
    if not c: return ""
    if c.get("vouched"): return "your own word"
    return ", ".join(x for x in (c.get("source"), c.get("information"), c.get("evidence"), c.get("relationship")) if x)

def decider(by, notes, person_decided):
    """Who made a decision, in words, from the assertion's own record of it: the owner, a session acting for them or their own
    word (a vouch) where a person's own decision on this statement set its status (assertion.person_decided); otherwise what
    set it, which is no person's decision on the statement: the rule, the acceptance of its record (the notes name the proposal
    that wrote it), or a re-read or a carry.
    Implements [rule.proof.3], [rule.own.2]."""
    by = by or ""
    if (notes or {}).get("vouched"): return "your own word"
    if person_decided:
        if by.startswith("user:"): return "the owner"
        if by.startswith("agent:") and " for user:" in by: return "a session for the owner"
        return by or "unknown"
    if by.startswith("rule:"): return "the rule"
    return "the record's acceptance" if (notes or {}).get("proposal") else "a re-read or a carry"

# ---------------------------------------------------------------- the records
def record_info(cx, sha, cache, entry=None):
    """What a line says about an archived record: its short name, its locator as a reader opens it, the locator as the
    catalog holds it (locator_value, the record's identity in a conflict line) and its citation (Evidence Explained style),
    the citation naming entry, the person as the record writes them, where the record's own citation does not.
    Implements [rule.proof.3]."""
    if (sha, entry) in cache: return cache[(sha, entry)]
    q = _q(cx)
    a = q.execute("""SELECT ar.sha256, ar.mime, ar.locator_kind, ar.locator_value, ar.retrieved_at, ar.original_filename, c.name AS collection, s.name AS source, s.id AS source_id
                     FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?""", (sha,)).fetchone()
    e = q.execute("""SELECT e.structured_json, x.name, x.kind FROM extraction e JOIN extractor x ON x.id=e.extractor_id
                     WHERE e.artifact_sha256=? AND e.superseded_by IS NULL AND e.status<>'failed' ORDER BY e.ran_at DESC LIMIT 1""", (sha,)).fetchone()
    try: parsed = json.loads(e["structured_json"]) if e and e["structured_json"] else {}
    except ValueError: parsed = {}
    parsed = parsed if isinstance(parsed, dict) else {}
    locs = {r["kind"]: r["value"] for r in q.execute("SELECT kind, value FROM artifact_locator WHERE artifact_sha256=?", (sha,))}
    own = re.sub(r"^[^•]*•\s*", "", parsed.get("collection") or "").strip() if e and e["name"] == "familysearch-record" else ""
    name = own or (a["collection"] if a else None) or (a["source"] if a else None) or sha[:12]
    if "memorial_id" in locs: name = f"Find a Grave memorial {locs['memorial_id']}"
    url = (f"https://www.familysearch.org/{locs['ark']}" if "ark" in locs else f"https://www.findagrave.com/memorial/{locs['memorial_id']}/" if "memorial_id" in locs
           else a["locator_value"] if a and a["locator_kind"] == "url" else f"Ancestry record {a['locator_value']}" if a and a["locator_kind"] == "apid" else (a["original_filename"] if a else None))
    retrieved = (a["retrieved_at"] or "")[:10] if a else ""
    if e and e["name"] == "familysearch-record" and parsed.get("citation"):
        doc = {str(k).lower(): v for k, v in parsed.get("document") or []}
        film = ", ".join(f"{label} {doc[k]}" for k, label in (("microfilm number", "microfilm"), ("digital folder number", "digital folder"), ("image number", "image")) if doc.get(k))
        cite = parsed["citation"].strip() + (f" Citing {film}." if film else "")
    else:
        reader = f"; read by {e['name']}" if e and e["kind"] in ("llm", "human") else ""
        cite = f"\"{name}\", {a['source'] if a else 'unknown holder'} ({url or 'no locator'}" + (f" : accessed {retrieved}" if retrieved else "") + ")" + \
               (f", entry for {entry}" if entry else "") + reader + "."
    cache[(sha, entry)] = {"sha256": sha, "name": name, "locator": url, "locator_value": a["locator_value"] if a else None, "citation": cite}
    return cache[(sha, entry)]

def subject_statements(cat, kind, sid, want=None, relative=None):
    """The assertions on one subject (a person, an event, a family link), each as statements() describes it; a statement of
    another fact type than want is left out, the owner's own word (no record fact of its own) never.
    Implements [rule.proof.3]."""
    cx, q = cat.cx, _q(cat.cx)
    out = []
    for r in q.execute(f"""SELECT a.id, a.status, a.asserted_by, a.person_decided, a.notes, a.artifact_sha256, a.citation_text, pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end,
                                 pf.date_qualifier, ps.raw AS place, ar.mime, pe.name_text AS persona, pe.id AS persona_id, NOT {not_withdrawn('a.artifact_sha256')} AS withdrawn
                          FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          LEFT JOIN persona pe ON pe.id=coalesce(pf.persona_id, a.persona_id)
                          LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 WHERE a.subject_kind=? AND a.subject_id=? ORDER BY a.asserted_at, a.id""", (kind, sid)):
        if want and r["fact_type"] and r["fact_type"] != want: continue
        try: notes = json.loads(r["notes"]) if r["notes"] and r["notes"].startswith("{") else {}
        except ValueError: notes = {}
        st = {"id": r["id"], "status": r["status"], "by": decider(r["asserted_by"], notes, r["person_decided"]), "sha256": r["artifact_sha256"], "subject": [kind, sid], "relative": relative, "persona": r["persona"], "persona_id": r["persona_id"],
              "said": re.sub(r"\s+on the record$", "", r["citation_text"] or "") if kind == "family_member" else None,
              "value": r["value_text"], "date": {"start": r["date_start"], "end": r["date_end"], "text": r["date_text"], "qualifier": r["date_qualifier"]} if r["date_start"] or r["date_end"] or r["date_text"] else None,
              "place": r["place"], "apid": notes.get("apid"), "withdrawn": bool(r["withdrawn"])}
        if notes.get("vouched"): st.update({"kind": "vouch", "classes": {"vouched": True}})
        elif r["mime"] == "text/x-gedcom": st.update({"kind": "file", "classes": evidence_classes(cx, r["id"])})
        else: st.update({"kind": "record", "classes": evidence_classes(cx, r["id"])})
        out.append(st)
    return out

def axis_value(axis, st):
    """What a statement gives on one axis of a conflict: its date ({start, text, qualifier}) or its place as written."""
    return st["date"] if axis == "date" else st["place"]

def specificity(axis, v):
    """How specific a value is, for the order sides are formed in: a date's length, a bounded date (before, after, between)
    least of all, a place's named parts."""
    if axis == "date": return 0 if v.get("qualifier") in BOUNDS else len(v.get("start") or "")
    return len([p for p in re.split(r"<|,", v) if p.strip()])

def same_value(axis, a, b):
    """Whether two values stand on one side: dates that agree by catalog.date_verdict, or one within the other's bound (a
    bound differs from no date inside it), places by catalog.place_verdict read either way (a coarser place agrees with a
    finer one inside it).
    Implements [rule.conflict.5]."""
    return date_verdict(a, b).verdict in ("agrees", "within") if axis == "date" else (place_verdict(a, b).verdict == "agrees" or place_verdict(b, a).verdict == "agrees")

def sides(axis, sts):
    """The sides of a date or place conflict: the values the statements give (rejected ones and the owner's own word
    aside), the most specific first and a bounded date last, grouped where they agree (same_value); a value that agrees with
    more than one side (a year against two days of it, a state against two towns in it, a bound holding two dates) takes no
    side. Each side is {value, statements, best}, best
    its best statement in the classes' own order, and the sides come in that order.
    Implements [rule.conflict.5]."""
    out = []
    for st in sorted((s for s in sts if s["status"] != "rejected" and s["kind"] != "vouch" and axis_value(axis, s)), key=lambda s: -specificity(axis, axis_value(axis, s))):
        fits = [s for s in out if same_value(axis, axis_value(axis, st), s["value"])]
        if len(fits) > 1: continue
        if not fits: fits = [{"value": axis_value(axis, st), "statements": []}]; out.append(fits[0])
        fits[0]["statements"].append(st)
    for s in out: s["best"] = min(s["statements"], key=lambda x: order(x["classes"]))
    out.sort(key=lambda s: order(s["best"]["classes"]))
    return out
