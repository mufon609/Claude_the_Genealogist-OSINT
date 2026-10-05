#!/usr/bin/env python3
"""Households read off a census form (docs/DATA-ARCHITECTURE.md §7 decision 21; the rules in words: docs/RESEARCH-WORKFLOW.md
§5–7, "Households").

usage: tools/households.py show [--json] [--db catalog/tree.db]           the households as the script groups them now
       tools/households.py write [--by user:<you>] [--db catalog/tree.db]  grouped again, and stored where they changed

The entries are the personas of every current reading that a census form places (region_json {"form", "locators"},
data/record-forms.csv). They are grouped by the form's own rule, never by a tree's decision:

- One member is one entry, however many copies carry it: the same record id (catalog.persona_key: a FamilySearch entry's
  ark) wherever it is read, one line of one image however many readings read it, and an entry of one copy that is an
  entry of another copy of the same record (code's same_record joins, catalog.entry_on).
- A FamilySearch census record page is one household: its persons are one record of the index, one household under one
  household identifier, the page's own person and every member it lists.
- On one page the form bounds a household by a run of lines, opened by the head's line, or on a form that numbers its
  families by the line that carries a family number, and running to the next. The line read is the one the form's `lines`
  column names: a reading's own line down its image (`image_line`), and the copy's Line Number only where the column names
  `line` (the 1925 New York index), and then only the page's own person's, since a member's line on a FamilySearch record
  page repeats the page's own person's. A page is the image a reading is of, or the form's page locators all held alike (a
  county the copy's locators lack read off the entry's census residence). Two entries of one page with no held opener
  between them are one run when every line between them is held, or when they share a surname as written: a line not held
  may open another household, and the surname is the one tie the two entries themselves state. A run with no head held is
  a household under a head not held.
- A form that names the head alone (1790 to 1840) is one line to a household, its entry the head; a reading of a form of one
  schedule to a family (1890) is one household to an image.
- An entry that no copy groups and no line places (the 1950 census site's machine reading: no relationship, and a row the
  form's rule does not read) is in no household, and is reported so.

Each member's persona keeps the relationship to the head as its copy states it, as written: the Relationship to Head of
Household field, a stated relation (persona_relation not marked computed) toward another person of its reading (a census
states the relationship to the head alone), or a reading's own role word; no other tie among the members is stated here.
A household is complete when nothing the form's rule shows is missing: its head held, and, where every member's line is
read, no line between the first and the last. What is missing is named, the head first ("the head", "line 24"), never
filled in by guess.

Stored insert-only (household, household_member; schema/catalog.sql) with the script's version (GROUPED_BY): a household
grouped again differently (a page newly held, a reading read again, the script at another version) is a new row, and each
row it replaces names it in superseded_by, written once; a household whose entries no current reading holds any longer is
replaced by a row of no members. Households are evidence shared by every tree (CLAUDE.md hard rule 4): nothing a tree
decided is read in grouping them.

    group(cx)                        the households as the script groups them now, and the entries in none
    regroup(cx, by, ts=None)         group, store what changed, supersede what it replaces: what it wrote
    stored(cx)                       the current stored households, with their members
"""
import argparse, collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, ulid
from catalog import US_NAMES, entry_on, is_identity, key, persona_key, record_copies, split_name, us_state
from forms import forms

VERSION = "0.1.0"
GROUPED_BY = f"rule:households@{VERSION}"
FAMILYSEARCH = "familysearch-record"          # the reader of a FamilySearch record page: one record of the index, one household
READINGS = ("human", "llm")                   # a reading of an image, by a person or a model (the screen's transcription path)
GONE = "its entries are on no current reading"

class Union:
    """Sets joined two at a time, each named by its least member."""
    def __init__(self): self.up = {}
    def find(self, a):
        self.up.setdefault(a, a)
        while self.up[a] != a: self.up[a] = self.up[self.up[a]]; a = self.up[a]
        return a
    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.up[max(ra, rb)] = min(ra, rb)

def _chunks(ids, n=500):
    ids = list(ids)
    for i in range(0, len(ids), n): yield ids[i:i + n]

def census_forms():
    """The census forms of data/record-forms.csv by id."""
    return {f["id"]: f for f in forms() if f["kind"] == "census household"}

def place_parts(raw):
    """(minor division, county, state) of a census place as written ("Hempstead, Nassau, New York, United States": Hempstead,
    Nassau, New York), each None where the string does not give it: the state is the last part when a state's name or
    abbreviation is, the county the part before it, the minor division the first part before the county."""
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    while parts and parts[-1].lower() in US_NAMES: parts.pop()
    state = us_state(parts[-1]) if parts else None
    if not state: return (parts[0] if parts else None), None, None
    rest = parts[:-1]
    return (rest[0] if len(rest) >= 2 else None), (rest[-1] if rest else None), state

def _entries(cx):
    """Every persona of a current reading a census form places: a dict of its id, the file and reading, the copy it is
    (familysearch, reading or listing), whether it is the page's own person on a FamilySearch record page, its name, role,
    sequence, region, form and locators."""
    byid = census_forms(); out = []
    for pid, sha, eid, name, role, seq, region, xkind, xname in cx.execute(
            """SELECT p.id, p.artifact_sha256, p.extraction_id, p.name_text, p.role_in_record, p.sequence, p.region_json, x.kind, x.name
               FROM persona p JOIN extraction e ON e.id=p.extraction_id JOIN extractor x ON x.id=e.extractor_id
               WHERE e.superseded_by IS NULL AND e.status<>'failed'
               AND (CASE WHEN json_valid(p.region_json) THEN json_extract(p.region_json,'$.form') END) IS NOT NULL
               ORDER BY p.artifact_sha256, p.extraction_id, p.sequence, p.id"""):
        r = json.loads(region); form = byid.get(r.get("form"))
        if not form: continue
        out.append({"id": pid, "sha": sha, "extraction": eid, "name": name or "", "role": role or "", "seq": seq or 0, "region": r, "form": form,
                    "loc": {k: str(v) for k, v in (r.get("locators") or {}).items() if v not in (None, "")},
                    "copy": "familysearch" if xname == FAMILYSEARCH else "reading" if xkind in READINGS else "listing",
                    "own": r.get("label") == "record"})
    return out

def _facts(cx, ids):
    """{persona id: [(fact type, value as written, date as written, place as written, alternate)]}: the Relationship and
    Residence facts of the personas, in the order written."""
    out = collections.defaultdict(list)
    for part in _chunks(ids):
        for pid, ftype, value, date, raw, region in cx.execute(
                f"""SELECT pf.persona_id, pf.fact_type, pf.value_text, pf.date_text, ps.raw, pf.region_json FROM persona_fact pf
                    LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pf.persona_id IN ({','.join('?' * len(part))})
                    AND pf.fact_type IN ('Relationship','Residence') ORDER BY pf.rowid""", part):
            out[pid].append((ftype, value, date, raw, bool((json.loads(region) if region else {}).get("alternate"))))
    return out

def _stated(cx, ids):
    """{persona id: [(the persona it is toward, value as written)]}: the relations a reading wrote as the record's own
    statement (persona_relation whose region does not mark it computed, the site's inference)."""
    out = collections.defaultdict(list)
    for part in _chunks(ids):
        for pid, to, value, region in cx.execute(f"SELECT persona_id, related_persona_id, value_text, region_json FROM persona_relation WHERE persona_id IN ({','.join('?' * len(part))}) ORDER BY rowid", part):
            if value and not (json.loads(region) if region else {}).get("computed"): out[pid].append((to, value))
    return out

def relationship(e, facts, stated, reading):
    """The persona's relationship to the head as its copy states it, as written, or None: its Relationship to Head of
    Household field, else a stated relation toward another persona of its reading, else a reading's own role word, the
    relationship column as the reader read it."""
    for ftype, value, _, _, alt in facts.get(e["id"], []):
        if ftype == "Relationship" and value and not alt: return value
    for to, value in stated.get(e["id"], []):
        if to in reading: return value
    return (e["role"] or None) if e["copy"] == "reading" else None

def _line(e):
    """The entry's line on the form as the form's `lines` column reads it, or None; a member's line on a FamilySearch record
    page is never read, since it repeats the page's own person's."""
    if e["copy"] == "familysearch" and not e["own"]: return None
    for k in e["form"]["lines"]:
        v = e["loc"].get(k)
        if v and v.isdigit(): return int(v)
    return None

def _residence(pid, facts):
    """The persona's census residence as written, the one its copy shows (not a value kept beneath it), or None."""
    return next((raw for ftype, _, _, raw, alt in facts.get(pid, []) if ftype == "Residence" and raw and not alt), None)

def _page_locators(e, own, facts):
    """The form's page locators the entry is placed by: its own, or a FamilySearch member's with none of its own the page's own
    person's, and a state or county the locators lack read off the census residence."""
    src = own if own and not e["loc"] else e
    page = {k: src["loc"][k] for k in e["form"]["page"] if k in src["loc"]}
    _, county, state = place_parts(_residence(src["id"], facts) or (_residence(own["id"], facts) if own else None))
    if "county" in e["form"]["page"] and "county" not in page and county: page["county"] = county
    if "state" in e["form"]["page"] and "state" not in page and state: page["state"] = state
    return {k: page[k] for k in e["form"]["page"] if k in page}

def span(lines):
    """Lines not held, in words, in order: "line 24", "lines 5 to 6"."""
    out, run = [], []
    for n in sorted(lines):
        if run and n == run[-1] + 1: run.append(n); continue
        if run: out.append(run)
        run = [n]
    if run: out.append(run)
    return [f"line {r[0]}" if len(r) == 1 else f"lines {r[0]} to {r[-1]}" for r in out]

def group(cx):
    """The households as the script groups them now: ([household], [entry in no household]). A household is a dict of its
    form id, page (the form's page locators its entries hold), complete, missing (in words, the head first), ground (what groups
    its entries, in words) and members, one dict per persona in line order: persona id, name as written, the member's entry
    (the same for every copy of it), relationship as stated, head, line read, the file it is on."""
    es = _entries(cx)
    if not es: return [], []
    ids = {e["id"] for e in es}; by_id = {e["id"]: e for e in es}
    facts, stated = _facts(cx, ids), _stated(cx, ids)
    own_of = {e["extraction"]: e for e in es if e["copy"] == "familysearch" and e["own"]}   # a FamilySearch record page's own person, by its reading
    reading = collections.defaultdict(list)
    for e in es: reading[e["extraction"]].append(e)
    for e in es:
        e["relationship"] = relationship(e, facts, stated, {x["id"] for x in reading[e["extraction"]]})
        e["head"] = e["form"]["names"] == "head" or (e["relationship"] or "").strip().lower() == "head"
        e["line"] = _line(e)
        e["page"] = _page_locators(e, own_of.get(e["extraction"]), facts)
        e["surname"] = key(split_name(e["name"])[1]) or None
        k = persona_key(e["role"], e["seq"], e["name"], e["region"])
        e["key"] = json.dumps(list(k)) if is_identity(k) else None              # a record id the copy gives the entry
        e["at"] = json.dumps(["line", e["sha"], e["loc"].get("sheet"), e["loc"].get("sheet_letter"), e["line"]]) if e["copy"] == "reading" and e["line"] is not None else None
    # members: one entry, however many copies carry it
    member = Union(); first = {}
    for e in es:
        member.find(e["id"])
        for k in (e["key"], e["at"]):
            if k and k in first: member.join(first[k], e["id"])
            elif k: first[k] = e["id"]
    files = collections.defaultdict(set)
    for e in es: files[e["sha"]].add(e["extraction"])
    for sha in sorted(files):                                                  # an entry of one copy that is an entry of another copy of the same record
        others = [o for o, entry in record_copies(cx, None, sha)[1:] if entry == "" and o in files]
        for e in (x for x in es if x["sha"] == sha and x["key"] is None):
            for o in others:
                for eid in sorted(files[o]):
                    q = entry_on(cx, e["id"], eid)
                    if q in ids: member.join(e["id"], q)
    m_of = {e["id"]: member.find(e["id"]) for e in es}
    # households: the copy's own record, the runs of lines on one page
    house = Union(); placed = set(); across = collections.defaultdict(list)
    for m in set(m_of.values()): house.find(m)
    for eid, page in reading.items():                                          # a FamilySearch record page is one household
        if page[0]["copy"] != "familysearch": continue
        for e in page: house.join(m_of[page[0]["id"]], m_of[e["id"]]); placed.add(e["id"])
    pages = collections.defaultdict(list)
    for e in es:
        rule = e["form"]["household"]; e["where"] = None
        if "one line" in rule: placed.add(e["id"]); continue
        if "one schedule" in rule:
            if e["copy"] == "reading": pages[("schedule", e["sha"])].append(e)
            continue
        if e["line"] is None: continue
        if e["copy"] == "reading": e["where"] = ("image", e["sha"], e["loc"].get("sheet"), e["loc"].get("sheet_letter"))
        elif all(k in e["page"] for k in e["form"]["page"]): e["where"] = ("page", e["form"]["id"]) + tuple(e["page"][k] for k in e["form"]["page"])
        if e["where"]: pages[e["where"]].append(e)
    for where, page in pages.items():
        placed.update(e["id"] for e in page)
        if where[0] == "schedule":
            for e in page: house.join(m_of[page[0]["id"]], m_of[e["id"]])
            continue
        numbered = "family number" in page[0]["form"]["household"]
        opens = lambda e: e["head"] or (numbered and bool(e["loc"].get("family")))
        held = {e["line"] for e in page}
        page.sort(key=lambda e: (e["line"], e["seq"]))
        for i, a in enumerate(page):
            for b in page[i + 1:]:
                if b["line"] != a["line"] and opens(b): break                  # b opens a run of its own: nothing from it on is a's
                gap = set(range(a["line"] + 1, b["line"])) - held
                if not gap: house.join(m_of[a["id"]], m_of[b["id"]])
                elif a["surname"] and a["surname"] == b["surname"]:
                    house.join(m_of[a["id"]], m_of[b["id"]]); across[m_of[a["id"]]].append((gap, split_name(b["name"])[1]))
    in_one = {m_of[p] for p in placed}                                          # a member any copy of which a rule places: every copy of it is in the household
    comps = collections.defaultdict(list)
    for e in es:
        if m_of[e["id"]] in in_one: comps[house.find(m_of[e["id"]])].append(e)
    out = []
    for mem in comps.values():
        mem.sort(key=lambda e: (e["line"] is None, e["line"] or 0, e["seq"], e["sha"], e["id"]))
        roots = list(dict.fromkeys(m_of[e["id"]] for e in mem))
        entry = {}
        for r in roots:
            its = [e for e in mem if m_of[e["id"]] == r]
            ks = sorted(e["key"] for e in its if e["key"]) or sorted(e["at"] for e in its if e["at"])
            entry[r] = ks[0] if ks else json.dumps([its[0]["sha"]] + list(persona_key(its[0]["role"], its[0]["seq"], its[0]["name"], its[0]["region"])))
        form = mem[0]["form"]; page = {}
        for e in mem:
            for k, v in e["page"].items(): page.setdefault(k, v)
        missing = [] if any(e["head"] for e in mem) else ["the head"]
        line_of = {}
        for e in mem:
            if e.get("where"): line_of.setdefault(m_of[e["id"]], (e["where"], e["line"]))
        if len(line_of) == len(roots) and len({w for w, _ in line_of.values()}) == 1:   # every member's line read, on one page: a line between the first and the last not held is missing
            have = {n for _, n in line_of.values()}; missing += span(set(range(min(have), max(have) + 1)) - have)
        out.append({"form": form["id"], "page": page, "complete": not missing, "missing": missing, "ground": _ground(mem, roots, m_of, reading, across, form),
                    "members": [{"persona": e["id"], "name": e["name"], "entry": entry[m_of[e["id"]]], "relationship": e["relationship"], "head": e["head"],
                                 "line": e["line"], "sha": e["sha"]} for e in mem]})
    out.sort(key=lambda h: (h["form"], dumps(h["page"]), h["members"][0]["entry"]))
    return out, [e for e in es if m_of[e["id"]] not in in_one]

def _ground(mem, roots, m_of, reading, across, form):
    """What groups a household's entries, in words: FamilySearch's record where it lists more than one, the lines of one page
    or image and a gap crossed by one surname, an entry on several copies; a form of one line to a household, its head's line."""
    out = []
    for eid in dict.fromkeys(e["extraction"] for e in mem):
        page = reading[eid]
        if page[0]["copy"] == "familysearch" and len(page) > 1:
            own = next((e for e in page if e["own"]), page[0])
            out.append(f"FamilySearch's record of {own['name']} ({own['region'].get('ark') or own['sha'][:10]})")
    lines = sorted({e["line"] for e in mem if e["line"] is not None})
    if len(lines) > 1:
        out.append(f"lines {', '.join(map(str, lines[:-1]))} and {lines[-1]} of one " + ("image" if any(e["copy"] == "reading" for e in mem) else "page"))
    for r in roots:
        for gap, surname in across.get(r, []): out.append(f"across {', '.join(span(gap))} not held, by one surname ({surname})")
    for r in roots:
        files = {e["sha"] for e in mem if m_of[e["id"]] == r}
        if len(files) > 1: out.append(f"{next(e['name'] for e in mem if m_of[e['id']] == r)} one entry on {len(files)} copies")
    if not out: out.append("one line, the head's" if "one line" in form["household"] else "one schedule" if "one schedule" in form["household"] else "one entry")
    return "; ".join(dict.fromkeys(out))

def stored(cx):
    """The current stored households (superseded_by empty), each with its members in line order, its id and when and by what it
    was grouped; a row of no members, the one that replaced a household whose entries are read no longer, left out."""
    out = {}; fs = census_forms()
    for hid, form, page, complete, missing, ground, by, at in cx.execute(
            "SELECT id, form, page_json, complete, missing_json, ground, grouped_by, grouped_at FROM household WHERE superseded_by IS NULL ORDER BY id"):
        page = json.loads(page); order = (fs.get(form) or {}).get("page") or []
        out[hid] = {"id": hid, "form": form, "page": {**{k: page[k] for k in order if k in page}, **{k: v for k, v in page.items() if k not in order}},
                    "complete": bool(complete), "missing": json.loads(missing), "ground": ground, "grouped_by": by, "grouped_at": at, "members": []}
    for hid, pid, entry, rel, head, line, name, sha in cx.execute(
            """SELECT m.household_id, m.persona_id, m.entry, m.relationship, m.head, m.line, p.name_text, p.artifact_sha256 FROM household_member m
               JOIN household h ON h.id=m.household_id JOIN persona p ON p.id=m.persona_id WHERE h.superseded_by IS NULL
               ORDER BY m.line IS NULL, m.line, p.sequence, p.artifact_sha256, m.persona_id"""):
        out[hid]["members"].append({"persona": pid, "name": name or "", "entry": entry, "relationship": rel, "head": bool(head), "line": line, "sha": sha})
    return sorted((h for h in out.values() if h["members"]), key=lambda h: (h["form"], dumps(h["page"]), h["members"][0]["entry"]))

def _sig(h, by=GROUPED_BY):
    """What a household is, to tell one grouped now from one stored: the script's version, its form, page, what it lacks, its
    ground and each member's persona, entry, relationship, head and line."""
    return (by, h["form"], dumps(h["page"]), bool(h["complete"]), dumps(h["missing"]), h["ground"],
            tuple(sorted((m["persona"], m["entry"], m["relationship"] or "", bool(m["head"]), -1 if m["line"] is None else m["line"]) for m in h["members"])))

def _insert(cx, h, ts, by, supersedes=()):
    """One household row, its member rows and the audit row naming the rows it replaces: its id."""
    hid = ulid()
    cx.execute("INSERT INTO household (id,form,page_json,complete,missing_json,ground,grouped_by,grouped_at) VALUES (?,?,?,?,?,?,?,?)",
               (hid, h["form"], dumps(h["page"]), bool(h["complete"]), dumps(h["missing"]), h["ground"], GROUPED_BY, ts))
    for m in h["members"]:
        cx.execute("INSERT INTO household_member (household_id,persona_id,entry,relationship,head,line) VALUES (?,?,?,?,?,?)",
                   (hid, m["persona"], m["entry"], m["relationship"], bool(m["head"]), m["line"]))
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, by, "insert", "household", hid, dumps({"form": h["form"], "members": len(h["members"]), "missing": h["missing"], "grouped_by": GROUPED_BY,
                                                                   **({"supersedes": list(supersedes)} if supersedes else {})})))
    return hid

def regroup(cx, by, ts=None):
    """The households grouped again (group) and stored where they changed: one the store holds as it is grouped now is kept,
    any other is a new row; each current row not kept is superseded by a new household holding one of its entries, or, none
    holding any, by a row of no members saying its entries are on no current reading. Returns {kept, written, superseded,
    ungrouped}, the last the entries in no household."""
    ts = ts or now(); new, loose = group(cx); cur = {h["id"]: h for h in stored(cx)}
    have = {_sig(h, h["grouped_by"]): hid for hid, h in cur.items()}
    for n in new: n["id"] = have.get(_sig(n))
    kept = {n["id"] for n in new if n["id"]}
    entries = lambda h: {m["entry"] for m in h["members"]}
    fresh = [n for n in new if not n["id"]]
    gone = {hid: next((n for n in fresh if entries(n) & entries(h)), None) for hid, h in cur.items() if hid not in kept}
    for n in fresh: n["id"] = _insert(cx, n, ts, by, supersedes=[hid for hid, succ in gone.items() if succ is n])
    for hid, succ in gone.items():
        sid = succ["id"] if succ else _insert(cx, {"form": cur[hid]["form"], "page": {}, "complete": False, "missing": [], "ground": GONE, "members": []}, ts, by, supersedes=[hid])
        cx.execute("UPDATE household SET superseded_by=? WHERE id=?", (sid, hid))
    return {"kept": len(kept), "written": len(fresh), "superseded": len(gone), "ungrouped": len(loose)}

def said(m):
    """A member in words: their name, with the relationship and the line the form gives them."""
    parts = [x for x in (m["relationship"], f"line {m['line']}" if m["line"] is not None else None) if x]
    return f"{m['name']} ({', '.join(parts)})" if parts else m["name"]

def page_words(page):
    """A household's page in words: "page 19, assembly district 01, election district 06, county Nassau"."""
    return ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in page.items())

def describe(h):
    """A household in one line: its form and page, its members, what is missing, its ground."""
    return (f"{h['form']} {page_words(h['page']) or '(no page locator held)'}: {'; '.join(said(m) for m in h['members'])}. "
            + ("Complete" if h["complete"] else "Missing " + ", ".join(h["missing"])) + f". Grouped by {h['ground']}.")

def main():
    ap = argparse.ArgumentParser(description="Households read off a census form: show what the script groups now, or write them, grouped again, where they changed.")
    ap.add_argument("cmd", choices=["show", "write"]); ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=DB); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db)
    if a.cmd == "write":
        cx.execute("BEGIN"); st = regroup(cx, a.by); cx.commit()
        hs, loose = stored(cx), group(cx)[1]
    else: hs, loose = group(cx)
    if a.json: print(dumps({"households": hs, "ungrouped": [{"persona": e["id"], "name": e["name"], "form": e["form"]["id"], "sha": e["sha"]} for e in loose]})); return
    for h in hs: print(describe(h))
    for (form, sha), n in sorted(collections.Counter((e["form"]["id"], e["sha"][:10]) for e in loose).items()):
        print(f"in no household: {n} entr{'y' if n == 1 else 'ies'} of {form} on {sha}: no copy groups them and no line the form's rule reads places them")
    print(f"{len(hs)} household(s), {sum(not h['complete'] for h in hs)} not wholly held" + (f"; {st['written']} written, {st['kept']} kept, {st['superseded']} superseded" if a.cmd == "write" else ""))

if __name__ == "__main__": main()
