#!/usr/bin/env python3
"""The written conclusion of the Genealogical Proof Standard for a person's key facts (docs/RULE.md,
"The proof standard"), written by code from the catalog: read-only, no model.

usage: tools/proof.py "<person>" [--fact name|sex|birth|death|parents|spouses|children] [--json] [--tree slug] [--db catalog/tree.db]

For each key fact:
  value       the value the tree holds, its basis (accepted, accepted in part, undecided, rejected) and who decided it: the owner, a
              session acting for the owner, or the owner's own word (a vouch) where a person's own decision on that statement
              set its status, and otherwise what set it (the record's acceptance, a re-read or a carry, the rule), never the
              owner; the tree file's own claim and how
              many of its citations are held; for a birth or a death accepted only in part, each part that is a claim beyond
              what the accepted statements give, what it rests on and what they give instead (Catalog.value_basis,
              docs/RULE.md, what of an event's value is accepted)
  evidence    the records behind it, each record once with its copies beneath it (same_record: one record is one source
              wherever it is held), named by the original its classes give (data/evidence-classes.csv), each with its class
              words (source: original, derivative or authored; information: primary, secondary or indeterminable; evidence:
              direct or indirect; a family link's relationship: stated or computed), its status and whether it agrees with
              the tree's value (a name is read as the standing rule's name test reads one: the person's name rows and the
              aliases accepted for them, never an undecided one, compared as tools/match.py compares, so a nickname, an
              initial, a spelling variant of the surname or a name the person is known by on an accepted alias agrees, and
              the line says which); a record withdrawn
              from the evidence (tools/tombstone.py) is listed as withdrawn, its statements as written and evidence for nothing
  conflicts   each conflict question on the fact, with its question id (tools/conclude.py resolve and reopen take it): open, with
              the rule's own reading of it (tools/conflicts.py classes_decide, over every statement on that event's date or
              place): the side it would keep, the record of the event itself against sides resting only on secondary or
              indeterminable information, or why it would not decide; or closed with its reason, the owner's or the rule's
  research    the fact's checklist rows: held, searched with nothing found, cited and not fetched, blocked, or not yet
              searched
  conclusion  meets the standard (an accepted statement both direct and primary, no open conflict, every row held or
              searched); an argument is still owed, with the reasons (only indirect evidence, only secondary information,
              no statement both, a part of the value resting on a claim, an open conflict); research still open; or no
              record accepted, a record withdrawn from the evidence counting for none.
The default prints a few lines per fact, the best records first; --fact prints one fact with every record and its
citation (Evidence Explained style: a FamilySearch page's own "Cite This Record" with its film and image, else the
collection, holder, locator and date retrieved); --json the whole. A record's locator is printed once per proof, at its
first mention, as "#3 <locator>", and every later mention of that record is "#3". No class is ever a number: records
are ordered by their class words, never scored.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, resolve_tree
from catalog import Catalog, date_verdict, first_given, key, name_words, note, place_verdict, record_of, same_given, same_surname, split_name, split_persona_name
from facts import KEY_FACTS, fact_subjects
from match import name_keys
from conflicts import CONFLICT_AXIS, classes_decide, conflict_lines, order, record_info, subject_statements, words


STATUS = ("accepted", "undecided", "rejected")

SHOWN = 3                                                          # records a fact's default lines name before "and more"

ROW_STATES = ("held", "searched, nothing found", "cited, not fetched", "blocked", "not yet searched")

FACT_ROWS = {                                                      # the checklist rows whose records state each key fact (docs/RESEARCH-CHECKLIST.md)
    "name": ("birth record", "death record"),
    "sex": ("birth record",),
    "birth": ("birth record", "church register (baptisms, marriages, burials)", "census household", "Social Security (SSDI / SS-5)", "WWI draft card", "WWII draft card", "naturalization"),
    "death": ("death record", "obituary", "cemetery / family plot", "Social Security (SSDI / SS-5)"),
    "parents": ("birth record", "church register (baptisms, marriages, burials)", "census household", "death record", "Social Security (SSDI / SS-5)"),
    "spouses": ("marriage record", "census household", "obituary"),
    "children": ("census household", "obituary", "will / probate"),
}

def _q(cx):
    q = cx.cursor(); q.row_factory = sqlite3.Row; return q

def statements(cat, pid, field):
    """Every assertion behind one key fact: what it says (a date and a place, a name, a sex, the link's own words and the
    relative it names), its status, who decided it, its classes (catalog.evidence_classes) and whether its record is
    withdrawn from the evidence (catalog.not_withdrawn: the statement stays as written, evidence for nothing). The tree
    file's own claims and their citations are kept apart as kind file; the owner's own word as kind vouch.
    Implements [rule.proof.1], [rule.proof.3]."""
    cx, q = cat.cx, _q(cat.cx)
    want = {"name": "Name", "sex": "Sex"}.get(field)
    out = []
    for kind, sid in fact_subjects(cx, pid, field):
        relative = None
        if kind == "family_member":
            fid, who, role = json.loads(sid)
            if field == "parents": relative = " & ".join(n for n, in q.execute("SELECT p.display_name FROM family_member fm JOIN person p ON p.id=fm.person_id WHERE fm.family_id=? AND fm.role='partner' ORDER BY p.display_name", (fid,)))
            elif field == "spouses": relative = next((n for n, in q.execute("SELECT p.display_name FROM family_member fm JOIN person p ON p.id=fm.person_id WHERE fm.family_id=? AND fm.role='partner' AND fm.person_id<>?", (fid, pid))), None)
            else: relative = next((n for n, in q.execute("SELECT display_name FROM person WHERE id=?", (who,))), None)
        out += subject_statements(cat, kind, sid, want, relative)
    return out

# ---------------------------------------------------------------- the tree's value and agreement
def tree_value(cat, pid, field, ev, fam):
    """(the value the tree holds in words, what statements are compared against).
    Implements [rule.proof.3]."""
    if field == "name":
        p = cat.person(pid); rows = {(first_given(g), key(s)) for g, s, *_ in p["names"]}
        return p["name"], {"name": p["name"], "rows": rows, "keys": name_keys(cat, pid, accepted=True)}
    if field == "sex": s = cat.person(pid)["sex"]; return s, s
    if field in ("birth", "death"):
        e = cat.canonical_event(ev, field.title())
        if not e: return None, None
        place = e["place"]["text"] if e["place"] else None
        start, end, qual = cat.q("SELECT date_start, date_end, date_qualifier FROM event WHERE id=?", e["id"])[0]
        return ", ".join(x for x in (e["date_text"], place) if x) or None, {"date": {"start": start, "end": end, "text": e["date_text"], "qualifier": qual}, "place": place}
    names = [n for _, n in fam[field]]
    return (" & ".join(names) if field == "parents" else ", ".join(names)) or None, names

def written_name(keys, given, later):
    """How a name as written (split_persona_name: its first given name's key and the keys of the words after it) stands to
    (first given, surname) keys, as match.compare reads it for the matcher and the rule alike: whether the first given name
    is one of theirs (catalog.same_given: a nickname, an initial, a slip) and how a word after it is one of their surnames
    (catalog.same_surname: "agrees", else "variant" or "one letter apart", else "" for none).
    Implements [rule.name.1]."""
    hows = [same_surname(t, s) for t in later for _, s in keys]
    return any(same_given(given, k) for k, _ in keys), "agrees" if "agrees" in hows else next((h for h in hows if h), "")

def agreement(field, st, tree):
    """Whether a statement agrees with the tree's value, in words: agrees (with a note: the month only, the year only, the
    months not compared beside a date marked about, estimated or calculated, a coarser place, a spelling variant), the date within a bound (catalog.date_verdict: neither agrees nor disagrees), or what it says instead.
    None where there is nothing to compare. A name is read as the standing rule's name test reads one (tree: the person's
    name, the keys of their name rows and name_keys with accepted, which adds the accepted aliases and never an undecided
    one, docs/RULE.md, which variants the rule counts as the name): it agrees when its first given name
    and a surname after it are the person's by written_name, and says so in a note when only an accepted alias holds them.
    Implements [rule.name.1], [rule.points.6]."""
    if tree is None: return None
    if field == "name" and st["value"]:
        given, later = split_persona_name(st["value"])
        known, sur = written_name(tree["keys"], given, later)
        if not (known and sur): return f"says {st['value']}"
        own = written_name(tree["rows"], given, later)
        if not all(own): return "agrees: a name the person is known by"
        rg = split_name(st["value"])[0]
        rgiven, tgiven = name_words(st["value"])[:-1], name_words(tree["name"])[:-1]
        notes = [] if own[1] == "agrees" else [f"the surname {own[1]}" if own[1] != "variant" else "the surname a spelling variant"]
        if rgiven != tgiven:
            fits = all(any(t == r or (len(r) == 1 and t.startswith(r)) for t in tgiven) for r in rgiven)
            fuller = all(any(t == r or (len(t) == 1 and r.startswith(t)) for t in tgiven) for r in rgiven)
            alike = all(any(same_given(r, t) for t in tgiven) for r in rgiven)
            notes.append("fewer given names" if fits and len(rgiven) < len(tgiven) else "a given name as its initial" if fits
                         else "a given name in full where the tree has its initial" if fuller
                         else "a given name a nickname or spelling variant" if alike else f"given names {rg}")
        return "agrees" + (f": {', '.join(notes)}" if notes else "")
    if field == "sex" and st["value"]:
        v = {"male": "M", "female": "F"}.get(st["value"].strip().lower(), st["value"].strip()[:1].upper())
        return "agrees" if v == tree else f"says {st['value']}"
    if field in ("birth", "death"):
        notes, says, bound = [], [], None
        if st["date"]:
            f = date_verdict(st["date"], tree["date"])
            if f.verdict == "disagrees": says.append(st["date"]["text"])
            elif f.verdict == "agrees" and f.near: notes.append("the months not compared" + (f", within {f.years} years" if f.years else ""))   # both give a month and one is about, estimated or calculated
            elif f.verdict == "agrees" and f.years: notes.append(f"within {f.years} years")   # another year, inside the two an about or calculated date allows, is not the year
            elif f.verdict == "agrees" and f.only: notes.append("month only" if f.month else "year only")   # a month both give, one with no day, agrees to the month
            elif f.verdict == "within": bound = f"the date within: {note(f)}"          # a bound neither agrees nor disagrees (catalog.date_verdict)
        placed = False
        if st["place"]:
            f = place_verdict(st["place"], tree["place"])
            if f.verdict == "disagrees": says.append(st["place"])
            elif f.verdict == "agrees": placed = True; notes += [note(f)] if note(f) else []
        if not (st["date"] or st["place"]): return None
        if says: return f"says {', '.join(says)}"
        if bound and not placed: return bound
        return "agrees" + (f": {'; '.join(notes + ([bound] if bound else []))}" if notes or bound else "")
    return None

# ---------------------------------------------------------------- the groups by original
def groups(cx, tree_id, field, sts, tree, cache):
    """The record statements grouped by the record they are statements of (catalog.record_of: one record is one source
    wherever it is held, so a record is cited once with its copies beneath it, and two records of one kind, two people's
    death certificates, are two), named by the original its classes give, best first: accepted before undecided before
    rejected, then by the classes' own order. Each group carries its copies, its best statement's classes, its status, what
    it says against the tree, who decided, and whether its every statement rests on a withdrawn file (withdrawn: the record
    is evidence for nothing, its statements kept as written).
    Implements [rule.proof.3], [rule.points.9], [rule.points.12]."""
    by = {}
    for st in sts:
        if st["kind"] != "record": continue
        c = st["classes"] or {}
        g = by.setdefault(record_of(cx, tree_id, st["sha256"], st["persona_id"]), {"original": c.get("original"), "records": [], "statements": []})
        g["original"] = g["original"] or c.get("original")
        if st["sha256"] not in g["records"]: g["records"].append(st["sha256"])
        st["agrees"] = agreement(field, st, tree)
        g["statements"].append(st)
    out = []
    for g in by.values():
        live = [s for s in g["statements"] if s["status"] != "rejected"] or g["statements"]
        best = min(live, key=lambda s: (STATUS.index(s["status"]), order(s["classes"])))
        names = list(dict.fromkeys(record_info(cx, sha, cache)["name"] for sha in g["records"]))
        says = list(dict.fromkeys(s["agrees"] for s in live if s["agrees"]))
        records = {}
        for s in g["statements"]:
            rec = record_info(cx, s["sha256"], cache, s["persona"])
            records.setdefault(rec["citation"], rec)
        out.append({"original": g["original"], "label": (f"{g['original']} ({'; '.join(names)})" if g["original"] else "; ".join(names)),
                    "records": list(records.values()), "status": best["status"], "classes": best["classes"],
                    "says": says, "said": list(dict.fromkeys(re.sub(r" of .*$", "", s["said"]) for s in live if s["said"])), "relatives": list(dict.fromkeys(s["relative"] for s in live if s["relative"])),
                    "decided_by": list(dict.fromkeys(s["by"] for s in g["statements"] if s["status"] == "accepted")), "withdrawn": all(s["withdrawn"] for s in g["statements"]),
                    "statements": [{k: s[k] for k in ("id", "status", "by", "said", "relative", "value", "date", "place", "agrees", "classes")} for s in g["statements"]]})
    out.sort(key=lambda g: (STATUS.index(g["status"]), order(g["classes"])))
    return out

# ---------------------------------------------------------------- conflicts
def fact_of(detail):
    """The key fact a conflict question is about, from its own words."""
    d = (detail or "").lower()
    if d.startswith("birth") or "birth event" in d: return "birth"
    if d.startswith("death") or "death event" in d: return "death"
    if "marriage" in d: return "spouses"
    return None

def resolution(cat, qid, detail_json):
    """The written reason on a closed conflict, the owner's or the rule's: kept on the question itself, in a note on it, or on
    the audit row that closed it (tools/log_search.py --dismiss --note, tools/conclude.py resolve); None when no reason was
    written.
    Implements [rule.conflict.9]."""
    try: d = json.loads(detail_json or "{}")
    except ValueError: d = {}
    for k in ("resolution", "reason", "note", "kept"):
        if isinstance(d.get(k), str) and d[k].strip(): return d[k].strip()
    n = cat.q("SELECT body FROM note WHERE entity_kind='research_question' AND entity_id=? ORDER BY created_at DESC LIMIT 1", qid)
    if n: return n[0][0]
    for diff, in cat.q("SELECT diff_json FROM audit_log WHERE entity_kind='research_question' AND entity_id=? ORDER BY at DESC", qid):
        try: d = json.loads(diff or "{}")
        except ValueError: continue
        for k in ("note", "reason", "resolution"):
            if isinstance(d.get(k), str) and d[k].strip(): return d[k].strip()
    return None

def rule_reading(cat, detail, spots):
    """The rule's own reading of one open conflict (tools/conflicts.py classes_decide, which writes nothing): {about: the
    event type and axis, event, axis, keep: the assertion id of the statement the rule would keep or None, why: its
    sentence}. The test is per event and axis, over every statement on it, so two conflicts on one event's date or place
    share one reading. None for a conflict that is not about an event's date or place (a duplicate event, a name); a
    difference the catalog no longer finds on any event says so (spots: the catalog's lines now, each with its event and
    axis, conflicts.conflict_lines).
    Implements [rule.proof.4]."""
    m = CONFLICT_AXIS.match(detail)
    if not m: return None
    about = f"{m.group(1)} {m.group(2)}"
    if detail not in spots: return {"about": about, "event": None, "axis": m.group(2), "keep": None, "why": "the catalog no longer finds this difference: the plan closes the question when it next runs"}
    eid, axis = spots[detail]
    keep, why = classes_decide(cat.cx, cat.tree_id, eid, axis)
    return {"about": about, "event": eid, "axis": axis, "keep": keep, "why": why}

def locators(cx, text):
    """The locators of archived records that a line names in parentheses, as Catalog.disagreements writes a record
    (its collection names and its locator), the catalog's own locator_value of each.
    Implements [rule.proof.5]."""
    return [loc for loc, in cx.execute("SELECT DISTINCT locator_value FROM artifact WHERE locator_value IS NOT NULL AND instr(?, '(' || locator_value || ')') > 0", (text,))]

def conflicts(cat, pid, field, spots):
    """The conflict questions on this fact: every research_question of kind conflict on the person that names it, open or
    closed with a reason (resolved by the owner or the rule, or dismissed), and any difference the catalog finds now that no question
    carries yet (Catalog.disagreements, Catalog.unplaced). Each is {question: its id, None where no question carries it yet,
    detail, status, reason, locators: the records its detail names, verdict: an open conflict's (rule_reading)}.
    Implements [rule.proof.3], [rule.proof.4]."""
    out, seen = [], set()
    for qid, status, reason, detail_json in cat.q("SELECT id, status, closed_reason, detail_json FROM research_question WHERE subject_person_id=? AND kind='conflict'", pid):
        try: detail = json.loads(detail_json or "{}").get("detail") or ""
        except ValueError: detail = ""
        seen.add(detail)
        if fact_of(detail) != field: continue
        if status == "closed" and reason not in ("resolved", "dismissed"): continue      # gone with its gap, or answered: no longer a conflict
        out.append({"question": qid, "detail": detail, "status": "open" if status == "open" else reason, "reason": resolution(cat, qid, detail_json) if status == "closed" else None})
    for detail in cat.disagreements(pid) + cat.unplaced(pid):
        if detail not in seen and fact_of(detail) == field: out.append({"question": None, "detail": detail, "status": "open", "reason": None})
    for c in out:
        c["locators"] = locators(cat.cx, c["detail"])
        if c["status"] == "open": c["verdict"] = rule_reading(cat, c["detail"], spots)
    return out

# ---------------------------------------------------------------- research
def research(cat, pid, field, rows):
    """The fact's checklist rows (FACT_ROWS), each with its state: held; searched, nothing found (every step on the row has
    a none run at each of its sources); blocked (a step blocked, or a run that was); cited, not fetched; not yet searched.
    A row the era rules out (n/a) is left out.
    Implements [rule.proof.2]."""
    out = []
    for r in rows:
        if r["record"] not in FACT_ROWS[field] or r["status"] == "n/a": continue
        name = {"row": r["record"], "instance": r.get("instance")}
        if r["status"] == "held": out.append({**name, "state": "held"}); continue
        steps = cat.q("SELECT id, kind, mode, sources_json, locator_source_id FROM search_plan WHERE person_id=? AND row_key=? AND status<>'skipped'", pid, f"{r['record']}:{r.get('instance') or ''}")
        searched, blocked = bool(steps), False
        for sid, kind, mode, sources, holder in steps:
            runs = cat.q("SELECT source_id, outcome FROM search_log WHERE plan_step_id=? AND superseded_by IS NULL", sid)
            if mode == "blocked" or any(o == "blocked" for _, o in runs): blocked = True
            want = {holder} if kind == "fetch" and holder else set(json.loads(sources or "[]"))
            if not (want and want <= {s for s, o in runs if o == "none"}): searched = False
        state = "searched, nothing found" if searched else "blocked" if blocked else "cited, not fetched" if r["status"] == "cited" else "not yet searched"
        out.append({**name, "state": state})
    return out

def rows_text(rows):
    """Checklist rows in words, one record's instances together: "census household 1920, 1940"."""
    by = {}
    for r in rows: by.setdefault(r["row"], []).append(r.get("instance"))
    return ", ".join(rec + (" " + ", ".join(str(i) for i in insts if i) if any(insts) else "") for rec, insts in by.items())

# ---------------------------------------------------------------- the conclusion
def conclusion(basis, accepted, vouched, open_conflicts, rows, claimed=(), *, files, withdrawn=False):
    """(verdict, reasons): the written conclusion's own words. accepted: the accepted record statements that are evidence (none
    resting on a withdrawn file). claimed: the parts of the value that rest on a claim (Catalog.claim_reasons), each owing an
    argument. files: whether the file's own claim of the fact is among its statements not rejected; a fact no record, no word
    of the owner's and no claim of the file's stands behind rests on records nobody has accepted. withdrawn: an accepted
    statement of the fact rests on a withdrawn file, which counts for nothing and is said so.
    Implements [rule.proof.3], [rule.points.9]."""
    if basis is None: return "no claim", []
    if basis == "rejected": return "rejected", []
    if not accepted:
        rests = ["it rests on your own word"] if vouched else ["it rests on the file's claim"] if files else [] if withdrawn else ["it rests only on records nobody has accepted"]
        return "no record accepted", rests + (["a record accepted for it is withdrawn from the evidence"] if withdrawn else [])
    owed = []
    cls = [s["classes"] or {} for s in accepted]
    if not any(c.get("evidence") == "direct" for c in cls): owed.append("it rests only on indirect evidence")
    if not any(c.get("information") == "primary" for c in cls):
        owed.append("it rests only on secondary information" if all(c.get("information") == "secondary" for c in cls) else "it rests only on secondary or indeterminable information")
    if not owed and not any(c.get("evidence") == "direct" and c.get("information") == "primary" for c in cls): owed.append("no statement is both direct and primary")
    owed += list(claimed)
    if open_conflicts: owed.append(f"{'a conflict is' if open_conflicts == 1 else f'{open_conflicts} conflicts are'} open")
    if owed: return "an argument is still owed", owed
    left = {}
    for r in rows:
        if r["state"] not in ("held", "searched, nothing found"): left.setdefault(r["state"], []).append(r)
    if left: return "research still open", [f"{state}: {rows_text(rs)}" for state, rs in left.items()]
    return "meets the standard", []

def build(cat, pid, only=None):
    """The proof summary of a person's key facts (one when only names it), as a dict: the person, then per fact its value,
    basis, deciders, the file's claim, the evidence groups, the conflicts, the research and the conclusion. A birth or death
    whose key fact is accepted carries what of its event's value is accepted (Catalog.value_basis, as reading) and the parts
    that are a claim in words (claimed); with any, its basis reads "accepted in part" and each part owes an argument.
    Implements [rule.proof.3], [rule.value.4]."""
    from checklist import build as checklist
    ev, fam = cat.events(pid), cat.family(pid)
    spots = {line: (eid, axis) for line, eid, axis in conflict_lines(cat, pid)}
    basis = cat.key_fact_basis(pid, ev)
    rows = checklist(cat, pid)["checklist"]
    rows = rows["A"] + rows["B"]
    cache, facts = {}, []
    for field in KEY_FACTS:
        if only and field != only: continue
        value, tree = tree_value(cat, pid, field, ev, fam)
        sts = statements(cat, pid, field)
        gs = groups(cat.cx, cat.tree_id, field, sts, tree, cache)
        files = [s for s in sts if s["kind"] == "file" and s["status"] != "rejected"]
        apids = list(dict.fromkeys(s["apid"] for s in files if s["apid"]))
        held = [a for a in apids if cat.held_for(a, pid)]
        vouched = [s for s in sts if s["kind"] == "vouch" and s["status"] == "accepted"]
        accepted = [s for s in sts if s["kind"] == "record" and s["status"] == "accepted" and not s["withdrawn"]]
        gone = any(s["kind"] == "record" and s["status"] == "accepted" and s["withdrawn"] for s in sts)
        cf = conflicts(cat, pid, field, spots)
        rs = research(cat, pid, field, rows)
        event = cat.canonical_event(ev, field.title()) if field in ("birth", "death") and basis[field] == "accepted" else None
        reading = cat.value_basis(event["id"]) if event else None
        claimed = cat.claim_words(reading)
        fact_basis = "accepted in part" if claimed else basis[field]
        verdict, why = conclusion(fact_basis, accepted, vouched, sum(1 for c in cf if c["status"] == "open"), rs, claimed=cat.claim_reasons(reading), files=bool(files), withdrawn=gone)
        facts.append({"fact": field, "value": value, "basis": fact_basis, "reading": reading, "claimed": claimed,
                      "decided_by": list(dict.fromkeys(s["by"] for s in sts if s["status"] == "accepted")),
                      "file": {"claims": bool(files), "citations": len(apids), "held": len(held)} if files else None,
                      "vouched": bool(vouched), "evidence": gs, "conflicts": cf, "research": rs, "verdict": verdict, "why": why})
    p = cat.person(pid)
    return {"person": {"id": pid, "name": p["name"]}, "facts": facts}

# ---------------------------------------------------------------- the written form
class Marks:
    """The records a proof has named by locator: each gets a number at its first mention, where its locator is printed in
    full ("#3 <locator>"), and is "#3" at every mention after."""
    def __init__(self): self.numbers = {}
    def first(self, locator):
        """The number of a locator, and whether this is its first mention.
        Implements [rule.proof.5]."""
        new = locator not in self.numbers
        if new: self.numbers[locator] = len(self.numbers) + 1
        return self.numbers[locator], new
    def line(self, text, locators):
        """A line with each of its records' locators (written in parentheses, as Catalog.disagreements writes them) marked.
        Implements [rule.proof.5]."""
        for loc in sorted(locators, key=lambda loc: text.find(f"({loc})")):
            n, new = self.first(loc)
            if new: text = text.replace(f"({loc})", f"(#{n} {loc})", 1)
            text = text.replace(f"({loc})", f"(#{n})")
        return text
    def citation(self, rec):
        """A record's citation, led by its number when the catalog holds a locator for it."""
        loc = rec.get("locator_value")
        return f"#{self.first(loc)[0]} {rec['citation']}" if loc else rec["citation"]

def reading_line(v, read):
    """An open conflict's rule_reading as one line: the rule would keep a statement (its assertion id, which tools/conclude.py
    resolve takes), or would not decide, with the reason in the rule's words; a reading already printed for the same event
    and axis (read) is pointed to. A difference the catalog no longer finds is told as it is.
    Implements [rule.proof.4]."""
    if v["event"] is None: return v["why"]
    spot = (v["event"], v["axis"])
    if spot in read: return f"the rule's reading of this {v['about']} is the one above"
    read.add(spot)
    return f"the rule would keep assertion {v['keep']}: {v['why']}" if v["keep"] else f"the rule would not decide it: {v['why']}"

def render(r, full=False):
    """The summary as text: a few lines per fact by default, every record with its citation when full.
    Implements [rule.proof.3], [rule.proof.5]."""
    out, marks, read = [f"{r['person']['name']} [{r['person']['id'][-6:]}]"], Marks(), set()
    for f in r["facts"]:
        head = f"{f['fact']}: {f['value'] or '(none)'}  {f['basis'] or 'no claim'}"
        if f["decided_by"]: head += f" ({', '.join(f['decided_by'])})"
        if f["file"]: head += "; the file claims it" + (f", citing {f['file']['citations']} record(s), {f['file']['held']} held" if f["file"]["citations"] else ", citing none")
        out.append(head)
        for c in f.get("claimed") or []: out.append(f"  {c}")
        shown = f["evidence"] if full else f["evidence"][:SHOWN]
        for g in shown:
            who = f" [{'; '.join(g['said'])}{': ' + ', '.join(g['relatives']) if g['relatives'] and f['fact'] in ('spouses', 'children') else ''}]" if g["said"] else ""
            says = f"; {'; '.join(g['says'])}" if g["says"] else ""
            out.append(f"  {g['label']}: {words(g['classes'])}; {g['status']}{', withdrawn from the evidence' if g['withdrawn'] else ''}{says}{who}")
            if full:
                for rec in g["records"]: out.append(f"      {marks.citation(rec)}")
                for s in g["statements"]:
                    if s["status"] == "rejected": out.append(f"      a statement rejected [{s['id'][-6:]}]")
        rest = f["evidence"][len(shown):]
        if rest:
            n = {st: sum(1 for g in rest if g["status"] == st) for st in STATUS}
            out.append("  and " + ", ".join(f"{v} more {k}" for k, v in n.items() if v))
        for c in f["conflicts"]:
            line = f"  conflict {c['status']}{' [' + c['question'] + ']' if c.get('question') else ''}: {marks.line(c['detail'], c.get('locators') or [])}"
            if c.get("reason"): line += f"; reason: {c['reason']}"
            out.append(line)
            if c.get("verdict"): out.append(f"    {reading_line(c['verdict'], read)}")
        if f["research"]:
            by = {s: [] for s in ROW_STATES}
            for x in f["research"]: by[x["state"]].append(x)
            by = {s: rs for s, rs in by.items() if rs}
            out.append("  research: " + "; ".join(f"{state}: {rows_text(rs)}" for state, rs in by.items()))
        out.append(f"  conclusion: {f['verdict']}" + (f": {'; '.join(f['why'])}" if f["why"] else ""))
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(description="The proof standard's written conclusion for a person's key facts: read-only, written by code.")
    ap.add_argument("person"); ap.add_argument("--fact", choices=KEY_FACTS); ap.add_argument("--json", action="store_true"); ap.add_argument("--tree")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args()
    cx = connect(a.db); tree_id, _ = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    r = build(cat, cat.find_person(a.person), only=a.fact)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else render(r, full=bool(a.fact)))

if __name__ == "__main__":
    main()
