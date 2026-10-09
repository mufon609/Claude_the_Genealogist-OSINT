#!/usr/bin/env python3
"""Households read off a census form (docs/DATA-ARCHITECTURE.md §7 decision 21; the rules in words: docs/HOUSEHOLDS.md).

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
decided is read in grouping them. tools/plan.py groups them again before it reads them, so a page read since is in them.

A household not wholly held leads to its missing entries (docs/HOUSEHOLDS.md, the order in words):
its own search, FamilySearch's collection searched by the surname, the place and the year and never a given name
(search_link), is held page by page, the first page of its answer not held being the next to save (answer); and every row of
a results page the archive holds of that collection for that surname at that place (the household's own search's, and an
earlier search's with a given name) is a candidate for the missing entries when it carries the surname and the place and its
own record page is not held (candidates). A row the form's household rule and data/life-limits.csv rule out for the head
is left out where the head alone is missing, and a candidate for a line not held where a line is missing too. The head's
candidates come first, each kind in the order the household itself makes likelier: a record id that differs from a member's
in its last character alone (the ids FamilySearch gives the entries of one household), a name that fits a relative the tree
names for a member in the head's place (it orders, never decides, and is never a field of the search), a birth year nearer
the head's spouse's on the page, a birth year given, then the answer's own order. OPEN_AT_ONCE of them are leads at a time;
a candidate whose record page is held has been tried, whatever it showed, and the next takes its place.

    group(cx)                        the households as the script groups them now, and the entries in none
    regroup(cx, by, ts=None)         group, store what changed, supersede what it replaces: what it wrote
    stored(cx)                       the current stored households, with their members
    waiting_for(cx, tree_id, pid)    the current households not wholly held a member of which the tree ties to the person
    search_link(h, page, per)        the household's own search, a page of its answer
    answer(cx, h)                    what of the household's own search the archive holds, and the page to save next
    candidates(cx, tree_id, h)       the rows that could be its missing entries, in order, those left out and those tried
"""
import argparse, collections, csv, json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, ROOT, connect, dumps, now, parse_gedcom_date, ulid
from catalog import US_NAMES, date_span, entry_on, first_given, holder_search, holders, is_identity, key, parent_limit, persona_key, record_copies, split_name, us_state
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

HOLDERS = None

def fs_collection(name):
    """FamilySearch's own key of a collection, by its name there or the name of the Ancestry collection it holds (data/holders.csv,
    kind fs_collection), or None."""
    global HOLDERS
    if HOLDERS is None:
        with open(os.path.join(ROOT, "data", "holders.csv"), newline="", encoding="utf-8") as fh:
            HOLDERS = [r for r in csv.DictReader(fh) if r["HolderSourceId"] == "D03" and r["HolderKind"] == "fs_collection"]
    return next((r["HolderKey"] for r in HOLDERS if name and name in (r["HolderCollection"], r["AncestryCollection"])), None)

def waiting_for(cx, tree_id, pid):
    """The current households not wholly held a member of which the tree ties to this person: a link or a card on one of the
    member's personas, accepted or undecided, and no link of the person to one of them rejected. Each as stored (stored), with
    what a lead for it needs: `key` (its form and page), `collection` and `collection_id` (the collection its copies are in, at
    FamilySearch where one is), `fs_collection` (FamilySearch's own key for it, data/holders.csv), `year`, `jurisdiction`,
    `surname` (the one most of its members are written under) and `place` (the minor division and county its census residence
    gives, each also as `minor` and `county`)."""
    hids = [r[0] for r in cx.execute(
        """SELECT DISTINCT h.id FROM household h JOIN household_member m ON m.household_id=h.id WHERE h.superseded_by IS NULL AND NOT h.complete
           AND (EXISTS (SELECT 1 FROM person_persona pp WHERE pp.person_id=? AND pp.persona_id=m.persona_id AND pp.status IN ('accepted','undecided'))
                OR EXISTS (SELECT 1 FROM proposal pr WHERE pr.tree_id=? AND pr.kind='persona_match' AND pr.status='undecided'
                           AND json_extract(pr.payload_json,'$.person_id')=? AND json_extract(pr.payload_json,'$.persona_id')=m.persona_id))
           AND NOT EXISTS (SELECT 1 FROM household_member o JOIN person_persona pp ON pp.persona_id=o.persona_id
                           WHERE o.household_id=h.id AND o.entry=m.entry AND pp.person_id=? AND pp.status='rejected')
           ORDER BY h.id""", (pid, tree_id, pid, pid))]
    if not hids: return []
    byid = {h["id"]: h for h in stored(cx)}; fs = census_forms(); out = []
    for hid in hids:
        h = byid.get(hid)
        if not h: continue
        pids = [m["persona"] for m in h["members"]]; facts = _facts(cx, pids)
        colls = cx.execute(f"""SELECT c.id, c.name FROM persona p JOIN artifact a ON a.sha256=p.artifact_sha256 JOIN collection c ON c.id=a.collection_id
                               WHERE p.id IN ({','.join('?' * len(pids))}) ORDER BY p.rowid""", pids).fetchall()
        at_fs = next(((cid, name, fs_collection(name)) for cid, name in colls if fs_collection(name)), None)
        names = [split_name(m["name"])[1] for m in h["members"] if split_name(m["name"])[1]]
        res = next((r for p in pids for r in [_residence(p, facts)] if r), None)
        minor, county, _ = place_parts(res)
        form = fs.get(h["form"]) or {"years": [], "jurisdiction": "united states"}
        dated = [int(m.group(0)) for p in pids for f in facts.get(p, []) if f[0] == "Residence" for m in [re.search(r"\b1[789]\d\d\b", f[2] or "")] if m]
        out.append({**h, "key": h["form"] + "|" + "|".join(f"{k}={v}" for k, v in sorted(h["page"].items())),
                    "collection": at_fs[1] if at_fs else (colls[0][1] if colls else None), "collection_id": at_fs[0] if at_fs else (colls[0][0] if colls else None),
                    "fs_collection": at_fs[2] if at_fs else None, "year": form["years"][0] if len(form["years"]) == 1 else (dated[0] if dated else None),
                    "jurisdiction": form["jurisdiction"], "surname": collections.Counter(names).most_common(1)[0][0] if names else None,
                    "place": ", ".join(x for x in (minor, county) if x) or res, "minor": minor, "county": county})
    return out

PAGING = ("offset", "count")                  # the parameters of a search's link that say which page of its answer, not what was searched
OPEN_AT_ONCE = 1                              # a household's candidates that are leads at a time (docs/HOUSEHOLDS.md: why one)
HEAD = "the head"

def fs_holder(fs_key):
    """data/holders.csv's row for FamilySearch's own collection of that key (HolderKind fs_collection), or None."""
    return next((h for rows in holders().values() for h in rows if h["HolderSourceId"] == "D03" and h["HolderKind"] == "fs_collection" and h["HolderKey"] == fs_key), None)

def search_link(h, page=1, per=None):
    """The household's own search as FamilySearch's link takes it (catalog.holder_search on the surname, the place and the year,
    never a given name), or None: the first page of its answer as the link itself, a later page with the site's own count of rows
    to a page and the offset of its first row, the parameters extract.parse_fs_search reads a saved page's place in the answer by."""
    holder = fs_holder(h.get("fs_collection"))
    if not holder: return None
    f = lambda v: {"value": v, "basis": "record"}
    url = holder_search(holder, {"surname": f(h["surname"]), "residence place": f(h["place"]), "year": f(str(h["year"]))})
    if not url or page <= 1 or not per: return url
    return url + "&" + urllib.parse.urlencode([("count", per), ("offset", (page - 1) * per)])

def _params(url):
    """A search link's own fields, the page of its answer set aside: {parameter: value}."""
    return {k: v for k, v in urllib.parse.parse_qsl(urllib.parse.urlsplit(url or "").query) if k not in PAGING}

def _place_words(raw):
    """A place as written, its words compared as a search writes them: each part in lower case, the country and a last part
    that is a state left out ("Hempstead, Nassau, New York" and "Hempstead, Nassau" are both hempstead, nassau)."""
    parts = [p.strip().lower() for p in (raw or "").split(",") if p.strip()]
    while parts and parts[-1] in US_NAMES: parts.pop()
    if len(parts) > 1 and us_state(parts[-1]): parts.pop()
    return parts

def _pages(cx, h):
    """The FamilySearch results pages the archive holds of a search of the household's collection for its surname at its place
    in its year, in the order they were read: each {"sha", "query", "url", "count", "rows", "own"}, `own` when the page is of
    the household's own search (search_link, its page aside); an earlier search with a given name is not its own and counts too."""
    if not (h.get("fs_collection") and h.get("surname") and h.get("place")): return []
    own, out = _params(search_link(h)), []
    for sha, sj in cx.execute("""SELECT e.artifact_sha256, e.structured_json FROM extraction e JOIN extractor x ON x.id=e.extractor_id JOIN artifact a ON a.sha256=e.artifact_sha256
                                 WHERE x.name='familysearch-search' AND e.superseded_by IS NULL AND e.status='complete' AND a.locator_value LIKE ? ORDER BY e.ran_at, e.id""",
                              (f"%collectionId={h['fs_collection']}%",)):
        p = json.loads(sj or "{}"); q = p.get("query") or {}
        if q.get("f.collectionId") != h["fs_collection"] or key(q.get("q.surname")) != key(h["surname"]) or _place_words(q.get("q.residencePlace")) != _place_words(h["place"]): continue
        span = [int(q[k]) for k in ("q.residenceDate.from", "q.residenceDate.to") if (q.get(k) or "").isdigit()]
        if h.get("year") and len(span) == 2 and not span[0] <= int(h["year"]) <= span[1]: continue
        out.append({"sha": sha, "query": q, "url": p.get("url"), "count": p.get("count"), "rows": p.get("rows") or [], "own": {k: v for k, v in q.items() if k not in PAGING} == own})
    return out

def answer(cx, h, pages=None):
    """What of the household's own search the archive holds: {"url" (its first page), "held" (the pages held, by number), "count"
    (the records the answer states), "per" (rows to a page), "total" (its pages), "next" (the first page not held, None when every
    page is), "next_url"}. A page's number is the offset of its first row over the rows a page holds; with nothing held the next
    page is the first."""
    pages = _pages(cx, h) if pages is None else pages
    mine = [p for p in pages if p["own"]]
    per = max((len(p["rows"]) for p in mine), default=0) or None
    count = next((p["count"] for p in reversed(mine) if p["count"] is not None), None)
    held = sorted({int(p["query"].get("offset") or 0) // per + 1 if per else 1 for p in mine})
    total = max(1, -(-count // per)) if count and per else (1 if mine else None)
    nxt = next((n for n in range(1, (total or 1) + 1) if n not in held), None)
    return {"url": search_link(h), "held": held, "count": count, "per": per, "total": total, "next": nxt, "next_url": search_link(h, nxt, per) if nxt else None}

def ark_id(ark):
    """The id of a FamilySearch record ark ("ark:/61903/1:1:KS4R-RTM" -> "KS4R-RTM"), the part a record page's file name carries."""
    return (ark or "").rsplit(":", 1)[-1]

def _span(text):
    """The days a date as written can stand for (catalog.date_span), or None."""
    d = parse_gedcom_date(text or "")
    return date_span(d["date_start"], d["date_end"], d["date_qualifier"]) if d["date_start"] or d["date_end"] else None

def _year(text):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", text or ""); return int(m.group(1)) if m else None

def _members(cx, h):
    """The household's members as the candidates read them: each {"name", "persona", "id" (the record id the entry is under),
    "kind" (the kind of its relationship to the head, extract.household_kind), "relationship", "sex", "born" (the birth as written)}."""
    from extract import household_kind
    out = []
    for m in h["members"]:
        facts = {t: v for t, v in cx.execute("""SELECT fact_type, coalesce(date_text, value_text) FROM persona_fact WHERE persona_id=? AND fact_type IN ('Birth','Sex')
                                                 AND (CASE WHEN json_valid(region_json) THEN json_extract(region_json,'$.alternate') END) IS NULL ORDER BY rowid DESC""", (m["persona"],))}
        entry = json.loads(m["entry"]) if (m["entry"] or "").startswith("[") else []
        out.append({"name": m["name"], "persona": m["persona"], "id": ark_id(entry[1]) if entry[:1] == ["ark"] else None, "relationship": m["relationship"],
                    "kind": household_kind(m["relationship"]) if m["relationship"] else None, "sex": (facts.get("Sex") or "")[:1].upper() or None, "born": facts.get("Birth")})
    return out

def _relatives_in_head_place(cx, tree_id, members):
    """The people the tree names for the household's members in the head's place: a member stated the head's wife or husband
    gives the people the tree names as their spouse, a son or daughter their parents, a father or mother their children (as
    Catalog.family reads the tree, a claim or an acceptance alike); the people every member that gives any names, less the
    people tied to a member. [(person id, given, surname, birth year)]."""
    from catalog import Catalog
    cat = Catalog(cx, tree_id); role = {"spouse": "spouses", "child": "parents", "parent": "children"}; sets, tied = [], set()
    for m in members:
        people = {r[0] for r in cx.execute("""SELECT pp.person_id FROM person_persona pp JOIN person p ON p.id=pp.person_id WHERE pp.persona_id=? AND pp.status IN ('accepted','undecided') AND p.tree_id=?
                                              UNION SELECT json_extract(payload_json,'$.person_id') FROM proposal WHERE tree_id=? AND kind='persona_match' AND status='undecided'
                                              AND json_extract(payload_json,'$.persona_id')=?""", (m["persona"], tree_id, tree_id, m["persona"]))}
        tied |= people
        if m["kind"] not in role: continue
        named = {rid for pid in people for rid, _ in cat.family(pid)[role[m["kind"]]]}
        if named: sets.append(named)
    out = []
    for rid in sorted(set.intersection(*sets) - tied) if sets else []:
        names = cat.person(rid)["names"]; birth = next((e for e in cat.events(rid) if e["type"] == "Birth" and e["year"]), None)
        out += [(rid, g, s, birth["year"] if birth else None) for g, s, *_ in names[:1]]
    return out

def _fits(row, rel):
    """Whether a row's name fits a relative's by the matcher's own agreement of given names (match.same_given) and the surname
    as written, with no birth year of the two more than a calculated year's span apart."""
    from match import same_given
    _, given, surname, born = rel
    if not same_given(first_given(row["given"]), first_given(given)) or key(row["surname"]) != key(surname): return False
    return not (row["year"] and born and abs(row["year"] - born) > 2)

def _row_name(name):
    """(given names, surname) of a search row's name: a lone word the surname, as a surname search lists an entry whose given
    name the index lacks."""
    given, surname, _ = split_name(name or "")
    return (None, given) if surname is None else (given, surname)

def _where(cx, ark):
    """Where a tried candidate's own record page places it, in words: its page locators, line and relationship as its current
    reading keeps them."""
    r = cx.execute("""SELECT pe.region_json, (SELECT pf.value_text FROM persona_fact pf WHERE pf.persona_id=pe.id AND pf.fact_type='Relationship' ORDER BY pf.rowid LIMIT 1)
                      FROM persona pe JOIN extraction e ON e.id=pe.extraction_id JOIN extractor x ON x.id=e.extractor_id WHERE e.superseded_by IS NULL AND x.name=?
                      AND json_extract(pe.region_json,'$.ark')=? ORDER BY e.ran_at DESC""", (FAMILYSEARCH, ark)).fetchone()
    if not r: return "its page read nowhere"
    loc = (json.loads(r[0] or "{}").get("locators") or {})
    return ", ".join([page_words({k: v for k, v in loc.items() if k not in ("line", "image", "household_id", "digital_folder", "image_number", "film", "publication", "roll")})] +
                     ([f"line {loc['line']}"] if loc.get("line") else []) + ([r[1]] if r[1] else [])) or "no place on a page read"

def candidates(cx, tree_id, h):
    """The rows that could be the household's missing entries (docs/HOUSEHOLDS.md): {"answer"
    (answer), "order" (the candidates in order, each {"ark", "name", "born", "year", "place", "url", "found_on", "row", "for" (the
    missing entries it could be), "why" (what orders it, in words)}), "open" (the first OPEN_AT_ONCE), "left_out" ({"ark", "name",
    "why"}), "tried" ({"ark", "name", "where"}: a candidate whose record page is held and is no member, where that page places
    it)}. A row is one when it carries the household's surname as written and its place, and its own record page is not held."""
    pages = _pages(cx, h); ans = answer(cx, h, pages)
    members = _members(cx, h); entries = {m["id"] for m in members if m["id"]}
    blocks = {m["id"][:-1]: m for m in members if m["id"]}
    head_missing = bool(h["missing"]) and h["missing"][0] == HEAD; lines = [x for x in h["missing"] if x != HEAD]
    spouses = [(m, _year(m["born"])) for m in members if m["kind"] == "spouse" and _year(m["born"])]
    relatives = _relatives_in_head_place(cx, tree_id, members) if head_missing else []
    seen, rows = set(), []
    for p in sorted(pages, key=lambda p: (not p["own"], int(p["query"].get("offset") or 0))):
        for r in p["rows"]:
            if not r.get("ark") or r["ark"] in seen: continue
            seen.add(r["ark"])
            given, surname = _row_name(r.get("name"))
            res = next((e["place"] for e in r.get("events") or [] if e["type"] == "Residence" and e.get("place")), None)
            born = next((e["date"] for e in r.get("events") or [] if e["type"] == "Birth" and e.get("date")), None)
            minor, county, _ = place_parts(res)
            if key(surname) != key(h["surname"]) or (key(minor), key(county)) != (key(h["minor"]), key(h["county"])): continue
            rows.append({"ark": r["ark"], "name": r.get("name") or "", "given": given, "surname": surname, "born": born, "year": _year(born), "place": res, "url": r.get("url"),
                         "found_on": p["url"], "row": r.get("n"), "base": len(rows)})
    order, left_out, tried = [], [], []
    for r in rows:
        if ark_id(r["ark"]) in entries: continue                                   # a member already: held
        if cx.execute("SELECT 1 FROM artifact_locator WHERE kind='ark' AND value=?", (r["ark"],)).fetchone():
            tried.append({"ark": r["ark"], "name": r["name"], "where": _where(cx, r["ark"])}); continue
        why, unlike = [], None
        if head_missing:
            span = _span(r["born"])
            for m in members:
                limit = (parent_limit(None, span, None, _span(m["born"])) if m["kind"] == "child" else parent_limit(m["sex"], _span(m["born"]), None, span) if m["kind"] == "parent" else None) if span else None
                if limit:
                    unlike = f"the head is the {'parent' if m['kind'] == 'child' else 'child'} of {m['name']} ({m['relationship']}, born {m['born']}): {limit[1]} (data/life-limits.csv)"; break
        r["for"] = ([HEAD] if head_missing and not unlike else []) + lines
        if not r["for"]: left_out.append({"ark": r["ark"], "name": r["name"], "why": f"born {r['born']}, so not the head: {unlike}"}); continue
        block = blocks.get(ark_id(r["ark"])[:-1])
        if block: why.append(f"its record id differs from {block['name']}'s ({block['id']}) in its last character alone, as the ids FamilySearch gives the entries of one household do")
        fit = next((rel for rel in relatives if _fits(r, rel)), None) if HEAD in r["for"] else None
        if fit: why.append(f"its name fits {fit[1]} {fit[2]}, whom the tree names in the head's place (a relative it orders by, never decides on)")
        near = min(((abs(r["year"] - y), n) for n, (m, y) in enumerate(spouses)), default=None) if HEAD in r["for"] and r["year"] else None
        if near: m = spouses[near[1]][0]; why.append(f"born {r['born']}, {near[0]} year{'' if near[0] == 1 else 's'} from {m['name']}, the head's {m['relationship'].lower()} (born {m['born']})")
        if HEAD in r["for"] and not r["year"]: why.append("no birth year on the row: nothing rules it out, and nothing orders it before a row that gives one")
        if unlike: why.append(f"not the head ({unlike}), so a candidate for {', '.join(lines)} alone")
        r["why"] = why
        r["sort"] = (HEAD not in r["for"], not block, not fit, HEAD in r["for"] and r["year"] is None, near[0] if near else 0, r["base"])
        order.append(r)
    order.sort(key=lambda r: r["sort"])
    clean = lambda r: {k: r[k] for k in ("ark", "name", "born", "year", "place", "url", "found_on", "row", "for", "why")}
    order = [clean(r) for r in order]
    return {"answer": ans, "order": order, "open": order[:OPEN_AT_ONCE], "left_out": left_out, "tried": tried}

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
