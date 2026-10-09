#!/usr/bin/env python3
"""The owner's commands on the tree: the decision on a card, a key fact, one statement, a record's fact placed on its event,
the rule's re-examination of its own decisions, the owner's word on a family link, a divorce, a duplicate, whether a person is
alive, a conflict's resolution or its reopening, and two archived copies joined or kept apart. The decision code is by job:
the standing rule's tests are tools/rule.py, the rule's decisions on conflicts tools/conflicts.py, the decisions and what
follows every one tools/decisions.py (decide, match_record, the writers, the owner's word, settle_people), a person's key facts
tools/facts.py, the joins of a record's copies and the owner's word on them tools/copies.py, a duplicate merged and the
folds tools/merges.py, the rule's re-examination of its own decisions tools/reconsider.py. Every command runs in one
transaction, committed whole or rolled back; what followed a decision is printed one line each (settled_lines).

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

"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, parse_gedcom_date, resolve_tree
from catalog import Catalog
from facts import KEY_FACTS, claimed_parts, decide_fact, evidence_rows, fact_status
from conflicts import rule_conflict_decisions, rule_conflict_line
from decisions import decide, decide_assertion, divorce, link_on_word, living, place, record_says, reopen, resolve
from copies import copies_on_word, copy_named
from merges import merge
from reconsider import reconsider

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
