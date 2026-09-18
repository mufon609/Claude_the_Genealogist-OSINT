"""Attach a record file to the steps it fulfils: the archive once, a found run logged on every step, then the extractor
and the matcher once, after the log rows exist, so the matcher sees every person the record was fetched for.

One code path for tools/attach_inbox.py and the person screen's "Archive + log". The record's identity is read from the
file itself, never from its name: a Find a Grave memorial id from the memorial's own markup (memNumberLabel), a
FamilySearch ark from the record page's print header. An image carries no identity in its bytes, so a gravestone
photograph takes the one the fetch list printed in its name (findagrave-photo-<memorial id>-<photo id>.jpg): the step for
that photograph on that memorial, archived under the gravestone row (E05) with the image's own URL as locator, logged found,
and read afterwards by the transcription path, never parsed. A page from a holder whose pages carry no identity the attach
reads (an SAR patriot page, a Legacy.com obituary) is taken by tools/fetches.py collect under the name the list printed and
attached here as kind "page": archived under the step's holder with the page's own URL as locator, logged found, and parsed
only when a parser claims it. The steps a record fulfils are the tree's fetch steps whose citation
carries that identity: for a memorial, the memorial URL in the step's fields; for an ark, the record ids the artifact holds
(catalog.holds: its own and, on the same sheet, those of the people the page names) once it is in the archive, else the
census page the record page itself names (year, enumeration district, sheet, county and state) against each step's
citation details, for the people the page names by name and birth year. A results page (told from a record page by the
parser that claims it, never by its file name) fulfils the search steps whose fields are the search's own, and the fetch
steps whose citation was searched for by hand at that holder because it carries no record id of the holder's: the
citation's collection has the page's collection as a holder (data/holders.csv) and the name the citation sits on is the
name searched. Such a page is the run's own artifact: a found run when a row fits someone, a none run when none does, the
query as run on the log; the same search saved again with the same rows is left in the inbox as a repeat. A file
whose identity matches no step is not archived by the inbox tool; the screen still attaches it to the step the person
chose. Archived bytes are linked, not copied, and a step already logged with the same artifact is not logged again.
"""
import json, mimetypes, os, re, shutil, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import archive_object, dumps, imports_dir, inbox_dir, now, object_path, ulid
from catalog import dbid_of, holders, holds, name_parts, person_named
from log_search import log as log_search, rendered_query
from extract import FS_MARK, FS_SEARCH_MARK, parse_memorial, parse_record, parse_search, parse_fs_search, AAD_MARK, parse_aad_search, parse_aad_record
from match import key as name_key
from conclude import match_record

MEMORIAL_URL = re.compile(r"findagrave\.com/memorial/(\d+)(?:/|$)")
PHOTO_NAME = re.compile(r"^findagrave-photo-(\d+)-(\d+)\.(?:jpe?g|png|webp|gif)$", re.I)
PHOTOS, PHOTO_COLLECTION = "E05", "Find a Grave memorial photographs"

def identity_of_name(name):
    """("photo", "<memorial id>:<photo id>", None) for an image saved under the name the fetch list printed for a gravestone
    photograph, else (None, None, None): an image carries no identity in its bytes."""
    m = PHOTO_NAME.match(os.path.basename(name or ""))
    return ("photo", f"{m.group(1)}:{m.group(2)}", None) if m else (None, None, None)

def identity(text):
    """(kind, value, parsed) from a page's own markup: ("memorial", id, parsed memorial) for a Find a Grave memorial (body id
    memorial-summary), ("search", search URL, parsed page) for a Find a Grave results page (body id memorial-list; its identity is
    the search's own fields), ("ark", ark, parsed record) for a FamilySearch record page, or (None, None, None)."""
    if re.search(r'<body[^>]*\bid="memorial-summary"', text):
        p = parse_memorial(text); mid = re.sub(r"\D", "", p.get("memorial_id") or "")
        return ("memorial", mid, p) if mid else (None, None, p)
    if re.search(r'<body[^>]*\bid="memorial-list"', text):
        p = parse_search(text)
        return ("search", p["url"], p) if p["query"].get("lastname") else (None, None, p)
    if FS_MARK.search(text):
        p = parse_record(text)
        return ("ark", p["ark"], p) if p.get("ark") else (None, None, p)
    if FS_SEARCH_MARK.search(text):                                  # a FamilySearch results page: its identity is the search's own fields
        p = parse_fs_search(text)
        return ("fs_search", p["url"], p) if p["query"].get("q.surname") and p["url"] else (None, None, p)
    if AAD_MARK.search(text) and re.search(r'<table[^>]*\bid="queryResults"', text):
        p = parse_aad_search(text)
        return ("aad_search", p["url"] or "aad search", p) if p["query"].get("name") else (None, None, p)
    if AAD_MARK.search(text) and re.search(r"Display Full Records", text):
        p = parse_aad_record(text)
        return ("aad_record", p["rid"], p) if p.get("rid") else (None, None, p)
    return None, None, None

def _int(s):
    m = re.search(r"\d+", s or ""); return int(m.group(0)) if m else None

def _page_named(parsed):
    """The census page a FamilySearch record page names: (year, enumeration district, sheet number, sheet letter, place text) or None."""
    f = {k.lower(): v for k, v in parsed.get("fields") or []}
    year = _int(f.get("event date")) or _int(parsed.get("collection"))
    orig = f.get("event place (original)") or f.get("event place") or ""
    ed = _int((re.search(r"\bED\s*([\d-]+)", orig) or [None, f.get("enumeration district")])[1])
    sheet = _int(f.get("sheet number") or f.get("sheet"))
    letter = (f.get("sheet letter") or "").strip().upper() or (re.search(r"^\d+([A-Za-z])$", (f.get("sheet number") or "").strip()) or [None, ""])[1].upper()
    if not (year and sheet): return None
    return year, ed, sheet, letter, orig.lower()

def _cites_page(step, named):
    """Whether a fetch step's citation details name the same census page as a FamilySearch record page."""
    year, ed, sheet, letter, orig = named
    v = lambda k: ((json.loads(step["query_json"] or "{}").get(k) or {}).get("value") or "")
    if _int(v("year")) != year or _int(v("page")) != sheet: return False
    if ed is not None and v("enumeration district") and _int(v("enumeration district")) != ed: return False
    m = re.search(r"^\d+([A-Za-z])$", v("page").strip())
    if letter and m and m.group(1).upper() != letter: return False
    parts = [p.strip().lower() for p in v("census place").split(",") if p.strip()]
    return all(p in orig for p in parts[-2:]) if parts else True

def _same_search(step, qy):
    """A cemetery search step whose foundation fields, after the person's revisions, are the results page's own query: the
    surname, the first given name, and the birth and death years where both sides have them."""
    f = rendered_query(step["query_json"], step["revisions_json"]); v = lambda k: (f.get(k) or {}).get("value")
    first = lambda s: name_key(str(s).split()[0]) if s and str(s).split() else ""
    if name_key(v("surname")) != name_key(qy.get("lastname")) or first(v("given")) != first(qy.get("firstname")): return False
    return all(not (v(fk) and qy.get(qk)) or str(v(fk)) == str(qy[qk]) for fk, qk in (("birth_year", "birthyear"), ("death_year", "deathyear")))

def _same_fs_search(cx, step, qy):
    """A search step with FamilySearch among its sources whose foundation fields, after the person's revisions, are the results
    page's own query: the surname, the first given name, a birth year inside the page's birth range where both have one, and for
    a census household step the collection searched being that year's census (data/holders.csv)."""
    f = rendered_query(step["query_json"], step["revisions_json"]); v = lambda k: (f.get(k) or {}).get("value")
    first = lambda s: name_key(str(s).split()[0]) if s and str(s).split() else ""
    if name_key(v("surname")) != name_key(qy.get("q.surname")) or first(v("given")) != first(qy.get("q.givenName")): return False
    if v("birth_year") and qy.get("q.birthLikeDate.from") and qy.get("q.birthLikeDate.to"):
        if not (int(qy["q.birthLikeDate.from"]) <= int(v("birth_year")) <= int(qy["q.birthLikeDate.to"])): return False
    if v("year") and qy.get("f.collectionId"):
        from catalog import holders
        coll = next((h["HolderCollection"] for rows in holders().values() for h in rows if h.get("HolderKind") == "fs_collection" and h.get("HolderKey") == qy["f.collectionId"]), None)
        if coll and str(v("year")) not in coll: return False
    return True

def _why(rows, reason):
    """The steps as plain dicts, each with the reason it is fulfilled (kept on the run's log note and printed by the inbox tool)."""
    return [{**dict(r), "reason": reason(r) if callable(reason) else reason} for r in rows]

def _fetch_steps_searched(cx, tree_id, holder_id, given, surname, holder_key=None):
    """The fetch steps a results page at a holder was saved for: the citation carries no record id of the holder's to open
    directly, so the holder's own collection search was run by hand on the citation's own details, and the page is that
    search's answer. A step fits when its citation's collection has this holder's collection as a holder (data/holders.csv:
    the citation's dbid, the holder, and the holder's own key where the page names one, a FamilySearch f.collectionId) and
    the name the citation sits on is the name searched (the first given name and the surname). Planned or done: a step
    found at another holder since still ran this search."""
    pg, sn = name_key((given or "").split()[0]) if (given or "").split() else "", name_key(surname)
    if not sn: return []
    dbids = {d for d, rows in holders().items() for h in rows if h["HolderSourceId"] == holder_id and (holder_key is None or h["HolderKey"] == holder_key)}
    if not dbids: return []
    out = []
    for r in cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.locator_kind='apid'
                           AND sp.status IN ('planned','done') ORDER BY sp.seq""", (tree_id,)):
        if dbid_of(r["locator_value"]) not in dbids: continue
        q = json.loads(r["query_json"] or "{}")
        if MEMORIAL_URL.search((q.get("url") or {}).get("value") or ""): continue            # a memorial cited by its own URL is fetched as itself, never searched for
        cg, rest = _split_name((q.get("name") or {}).get("value") or "")     # the first given name's key and every later word's: the surname is the last
        if not rest or (cg and pg and cg != pg) or rest[-1] != sn: continue
        out.append(r)
    return _why(out, "the citation's own search at the holder: its name and collection")

def steps_for(cx, tree_id, kind, value, parsed=None):
    """The tree's steps this identity fulfils: for a memorial or an ark, the fetch steps whose citation carries it, the citation on
    the person themselves first; for a search results page, the search steps whose fields are the search's own query, and the
    fetch steps whose citation was searched for by hand at that holder (_fetch_steps_searched)."""
    if kind == "search":
        qy = (parsed or {}).get("query") or {}
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='search' AND sp.sources_json LIKE '%"E01"%'
                             ORDER BY sp.seq""", (tree_id,)).fetchall()
        return _why([r for r in rows if _same_search(r, qy)], "the step's fields are this search's own") + _fetch_steps_searched(cx, tree_id, "E01", qy.get("firstname"), qy.get("lastname"))
    if kind == "fs_search":                                           # the search steps FamilySearch can answer whose fields are the page's own query
        qy = (parsed or {}).get("query") or {}
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='search' AND sp.sources_json LIKE '%"D03"%'
                             ORDER BY sp.seq""", (tree_id,)).fetchall()
        return _why([r for r in rows if _same_fs_search(cx, r, qy)], "the step's fields are this search's own") + \
               (_fetch_steps_searched(cx, tree_id, "D03", qy.get("q.givenName"), qy.get("q.surname"), qy["f.collectionId"]) if qy.get("f.collectionId") else [])
    if kind in ("aad_search", "aad_record"):                      # the enlistment steps whose person the page's name and birth year fit
        p = parsed or {}
        if kind == "aad_search": name, yb = p.get("query", {}).get("name") or "", p.get("query", {}).get("birth_year")
        else: f = dict(p.get("fields") or []); name, yb = " ".join(x for x in (f.get("NAME") or "").split("#") if x), f.get("YEAR OF BIRTH")
        words = [name_key(x) for x in name.split() if name_key(x)]
        if not words: return []
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='search' AND sp.sources_json LIKE '%"F01"%' ORDER BY sp.seq""", (tree_id,)).fetchall()
        out = []
        for r in rows:
            q = json.loads(r["query_json"] or "{}"); v = lambda k: (q.get(k) or {}).get("value")
            given = name_key((v("given") or "").split()[0]) if v("given") else ""
            if name_key(v("surname") or "") != words[0] or (given and len(words) > 1 and given != words[1]): continue
            if yb and v("birth_year") and int(v("birth_year")) % 100 != int(yb) % 100: continue
            out.append(r)
        return _why(out, "the page's name and year of birth are the step's")
    if kind == "photo":                                               # the step for this photograph on this memorial
        mid, pid = value.split(":", 1)
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.locator_source_id=?
                             AND json_extract(sp.query_json,'$.memorial.value')=? AND json_extract(sp.query_json,'$.photo.value')=? ORDER BY sp.seq""", (tree_id, PHOTOS, mid, pid)).fetchall()
        return _why(rows, "the photograph the step asks for, by the name the fetch list gave it")
    if kind == "memorial":
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch'
                             AND json_extract(sp.query_json,'$.url.value') LIKE ? ORDER BY sp.on_json='[]' DESC, sp.seq""", (tree_id, f"%/memorial/{value}/%")).fetchall()
        return _why([r for r in rows if (MEMORIAL_URL.search(json.loads(r["query_json"]).get("url", {}).get("value") or "") or [None, None])[1] == value], "the citation carries this memorial")
    if kind == "ark":
        loc = cx.execute("""SELECT a.sha256 FROM artifact_locator l JOIN artifact a ON a.sha256=l.artifact_sha256
                            WHERE l.kind='ark' AND l.value=? AND a.locator_kind='apid'""", (value,)).fetchone()
        if loc:                                                        # archived already: the ids the artifact holds (the household it names)
            ids = sorted(holds(cx, loc[0]))
            rows = cx.execute(f"""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.locator_kind='apid'
                                  AND sp.locator_value IN ({','.join('?'*len(ids))}) ORDER BY sp.on_json='[]' DESC, sp.seq""", (tree_id, *ids)).fetchall()
            own = cx.execute("SELECT locator_value FROM artifact WHERE sha256=?", (loc[0],)).fetchone()[0]
            return _why([r for r in rows if _named_on(cx, r["person_id"], parsed)], lambda r: "the citation is this record's own" if r["locator_value"] == own else "the same sheet, and the page names this person")
        named = _page_named(parsed or {})
        if named:                                                      # new to the archive: the steps citing the page it names, for the people it names
            rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.locator_kind='apid'
                                 AND sp.query_type='household' ORDER BY sp.on_json='[]' DESC, sp.seq""", (tree_id,)).fetchall()
            return _why([r for r in rows if _cites_page(r, named) and _named_on(cx, r["person_id"], parsed)], "the citation names this census page, and the page names this person")
        return _steps_by_kind(cx, tree_id, parsed or {})
    return []

ROW_OF = [(r"obituar", "obituary"), (r"death", "death record"), (r"birth", "birth record"), (r"marriage", "marriage record"), (r"social security|numident", "Social Security (SSDI / SS-5)"),
          (r"draft", "WWII draft card"), (r"naturali", "naturalization"), (r"find a grave|burial|cemetery", "cemetery / family plot")]

def _record_collection(parsed):
    """The record page's own collection, its FamilySearch section prefix stripped ("Vital • Kentucky, Vital Record Indexes,
    1911-1999" -> "Kentucky, Vital Record Indexes, 1911-1999"), for matching against data/holders.csv's HolderCollection."""
    return re.sub(r"^[^•]*•\s*", "", parsed.get("collection") or "").strip()

def _matches_collection(r, coll):
    """Whether this fetch step's own citation is of the record page's own collection, at the holder it was fetched from
    (data/holders.csv): a page fetched at a holder belongs to the citation whose holder collection it came from, never to
    another citation of the same row that merely shares the same holder (the Kentucky and Ohio death indexes are both at
    FamilySearch, D03, but are not each other's record). A step with no citation of its own (a search step) or a page with
    no collection field has nothing to check and matches as before."""
    if not r["locator_value"] or not coll: return True
    dbid = dbid_of(r["locator_value"])
    return any(h["HolderSourceId"] == r["locator_source_id"] and h["HolderCollection"] == coll for h in (holders().get(dbid) or []))

def _steps_by_kind(cx, tree_id, parsed):
    """A record that names no census page: the steps of the checklist row its own event type is about (a birth, a death, a
    marriage), or, when the page names none, its collection (an obituary collection to the obituary row, a death index to the
    death record row, the Social Security files to that row), on every person of the tree whose name is the record's principal
    name, the surname as written, a spelling variant or one letter apart, whose row's year is the record's within two, and
    whose own citation is of the collection this page came from (data/holders.csv). The record satisfies the row whatever
    holder the file had pointed at, so long as the holder's collection agrees."""
    from catalog import same_surname
    fields = {k.lower(): v for k, v in parsed.get("fields") or []}
    kind = (fields.get("event type") or "").lower()                        # the record's own event before its heading: FamilySearch mislabels a heading ("Death" over a birth)
    row = next((r for rx, r in ROW_OF if re.search(rx, kind)), None) if kind else None
    if not row:
        coll = (parsed.get("collection") or "").lower(); row = next((r for rx, r in ROW_OF if re.search(rx, coll)), None)
    if not row: return []
    pg, rest = _split_name(parsed.get("name") or "")
    if not pg or not rest: return []
    ym = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", fields.get("event date") or fields.get("event year") or ""); year = int(ym.group(1)) if ym else None
    record_coll = _record_collection(parsed)
    out = []
    for r in cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.status='planned' AND sp.row_key LIKE ? ORDER BY sp.seq""", (tree_id, row + ":%")):
        inst = r["row_key"].split(":", 1)[1] if ":" in r["row_key"] else ""
        if year and inst.isdigit() and abs(int(inst) - year) > 2: continue      # the row's year (birth record:1932) against the record's own: a father's birth is not his son's
        if not _matches_collection(r, record_coll): continue
        keys = {(name_key((g or "").split()[0]) if g else "", name_key(sn)) for g, sn in cx.execute("SELECT given, surname FROM person_name WHERE person_id=?", (r["person_id"],))}
        if any(g == pg and any(same_surname(t, sn) for t in rest) for g, sn in keys): out.append(r)   # as written, a spelling variant or an indexer's slip
    return _why(out, f"a {row} naming {parsed.get('name')}, the row's kind and the person's name" + (f", in {year}" if year else ""))

def _named_on(cx, person_id, parsed):
    """Whether a record page names this person: its subject or a household member, each with the birth year its age and the
    record's year give (catalog.person_named)."""
    p = parsed or {}; f = {k.lower(): v for k, v in p.get("fields") or []}
    yr = _int(f.get("event date")) or _int(p.get("collection"))
    born = lambda age: yr - _int(age) if yr and _int(age) is not None else None
    people = [(p.get("name") or "", born(f.get("age")))] + [(m.get("name") or "", born(m.get("age"))) for m in p.get("members") or []]
    return person_named(cx, person_id, people)

def _split_name(text): return name_parts(text)

def _rows_of(kind, parsed):
    """A results page's rows by the record ids they carry (an ark, a memorial id, an AAD record id), in order."""
    return [r.get("ark") or r.get("memorial_id") or r.get("rid") or r.get("url") for r in (parsed or {}).get("rows") or []]

def _repeat_save(cx, step_id, kind, parsed):
    """Whether this results page is the same search saved again: an artifact already logged on the step carries the same search
    URL as locator and, read again with the same parser, lists the same rows. The page adds nothing to the record of that run;
    a later run of the same search that answers with other rows is a new run."""
    parse = {"search": parse_search, "fs_search": parse_fs_search, "aad_search": parse_aad_search}[kind]
    for arts, in cx.execute("SELECT artifacts_json FROM search_log WHERE plan_step_id=? AND artifacts_json IS NOT NULL", (step_id,)):
        for sha in json.loads(arts or "[]"):
            loc = cx.execute("SELECT locator_value FROM artifact WHERE sha256=?", (sha,)).fetchone()
            if not loc or loc[0] != parsed.get("url"): continue
            try:
                with open(object_path(sha), "rb") as fh: earlier = parse(fh.read().decode("utf-8", errors="replace"))
            except (OSError, ValueError): continue
            if _rows_of(kind, earlier) == _rows_of(kind, parsed) and earlier.get("count") == parsed.get("count"): return True
    return False

def _row_of(parsed):
    """(checklist row, year) a record page is about, from its own event type (the principal's, else the one type its members
    carry), else its collection (ROW_OF); (None, year) when neither names a row."""
    lower = lambda fields: {k.lower(): v for k, v in fields or []}
    each = [lower(parsed.get("fields"))] + [lower(m.get("fields")) for m in parsed.get("members") or []]
    types = [f.get("event type").lower() for f in each if f.get("event type")]
    kind = types[0] if types and len(set(types)) == 1 else ""
    row = next((r for rx, r in ROW_OF if re.search(rx, kind)), None) if kind else None
    if not row: row = next((r for rx, r in ROW_OF if re.search(rx, (parsed.get("collection") or "").lower())), None)
    ym = next((m for m in (re.search(r"\b(1[5-9]\d\d|20\d\d)\b", f.get("event date") or f.get("event year") or "") for f in each) if m), None)
    return row, int(ym.group(1)) if ym else None

def on_word(cx, tree_id, pid, sha, by, note=None, parsed=None):
    """A record the owner says is about a person, with no step citing it: a fetch step on the person's plan, done with a found
    run naming the record, so the record is fetched for them from then on (match.persons_for reads the log) and every re-read
    and matcher run finds them. The step's locator is the record's own identity (its ark, its memorial id, else the artifact's
    locator), its row the checklist row the record's own event or collection is about — the person's own row of that kind
    within two years of the record's year, else the row at the record's year — and its fields the record's collection and
    URL as the record gives them, the name the owner's. A step of the same key already on the plan is logged, not written
    again; a run already naming the record is not logged again. parsed: the page as read on arrival, before its extraction
    exists; else the current extraction's own reading. Returns (step id, log id or None when the run was logged before)."""
    ts = now(); q = cx.cursor(); q.row_factory = sqlite3.Row
    ar = q.execute("SELECT sha256, source_id, collection_id, locator_kind, locator_value, (SELECT name FROM collection WHERE id=collection_id) AS collection FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if not ar: raise ValueError(f"not in the archive: {sha[:12]}")
    ident = q.execute("SELECT kind, value FROM artifact_locator WHERE artifact_sha256=? AND kind IN ('ark','memorial_id') ORDER BY kind", (sha,)).fetchone()
    lkind, lvalue = (ident["kind"], ident["value"]) if ident else (ar["locator_kind"] or "file", ar["locator_value"] or sha)
    key = f"fetch:{'memorial' if lkind == 'memorial_id' else lkind}:{lvalue}"
    if parsed is None:
        ext = q.execute("SELECT structured_json FROM extraction WHERE artifact_sha256=? AND superseded_by IS NULL AND status='complete' ORDER BY ran_at DESC LIMIT 1", (sha,)).fetchone()
        parsed = json.loads(ext["structured_json"] or "{}") if ext else {}
    row, year = _row_of(parsed)
    if row:
        own = [r[0] for r in q.execute("SELECT DISTINCT row_key FROM search_plan WHERE person_id=? AND row_key LIKE ?", (pid, row + ":%"))]
        near = [k for k in own if year and k.split(":", 1)[1].isdigit() and abs(int(k.split(":", 1)[1]) - year) <= 2] or (own if len(own) == 1 and not year else [])
        row_key = near[0] if near else f"{row}:{year or ''}"
    else: row_key = f"{lkind}:"
    who = q.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()["display_name"]
    coll = _record_collection(parsed) or ar["collection"] or ""
    url = {"ark": f"https://www.familysearch.org/{lvalue}", "memorial_id": f"https://www.findagrave.com/memorial/{lvalue}/", "url": lvalue}.get(lkind)
    fields = {"collection": {"value": coll, "basis": "record"}, "name": {"value": who, "basis": "owner"}, **({"url": {"value": url, "basis": "record"}} if url else {})}
    st = q.execute("SELECT id FROM search_plan WHERE person_id=? AND step_key=?", (pid, key)).fetchone()
    if st: sid = st["id"]
    else:
        sid = ulid(); seq = (q.execute("SELECT coalesce(max(seq),0) FROM search_plan WHERE person_id=?", (pid,)).fetchone()[0] or 0) + 1
        q.execute("""INSERT INTO search_plan (id,person_id,row_key,question_id,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,collection_id,on_json,sources_json,mode,expected,status,rationale,created_at)
                     VALUES (?,?,?,NULL,?,?,'fetch','subject_record',?,?,?,?,?,'[]',?,'fetch',?,'planned',?,?)""",
                  (sid, pid, row_key, seq, key, dumps(fields), ar["source_id"], lkind, lvalue, ar["collection_id"], dumps([ar["source_id"]] if ar["source_id"] else []),
                   "the record the owner named as this person's, read for what it says about them", f"attached on the owner's word as {who}'s: no step of the plan cited it", ts))
    if q.execute("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json LIKE ?", (sid, f'%"{sha}"%')).fetchone(): return sid, None
    return sid, log_search(cx, tree_id, by, step_id=sid, outcome="found", artifacts=[sha], note="; ".join(x for x in (f"on the owner's word about {who}", note) if x), query=fields)

def cite_on_word(cx, tree_id, pid, row_key, holder, fields, by, note=None, query_type=None):
    """A record the owner says exists about a person, at a holder, with no citation in the file and nothing archived yet: a
    fetch step on the person's plan carrying the citation's own details as the owner gives them (each field basis 'owner';
    for a census household the surname, the census place, the enumeration district and the sheet as 'page'), the holder as
    its locator source and its one source, so the runner asks the holder's connector for it like any cited fetch, and the
    record it brings back is fetched for this person (match.persons_for reads the log). The step carries no record locator
    until the run archives one. A step of the same key already on the plan is returned, not written again; the planner never
    drops a step the owner's word wrote (plan.plan_person). Returns the step id."""
    ts = now(); q = cx.cursor(); q.row_factory = sqlite3.Row
    who = q.execute("SELECT display_name FROM person WHERE id=? AND tree_id=?", (pid, tree_id)).fetchone()
    if not who: raise ValueError("no such person in this tree")
    src = q.execute("SELECT id, name FROM source WHERE id=?", (holder,)).fetchone()
    if not src: raise ValueError(f"no source {holder} in the registry")
    clean = {k.strip().lower(): str(v).strip() for k, v in (fields or {}).items() if str(v).strip()}
    if not (clean.get("surname") or clean.get("name")): raise ValueError("the citation needs a surname or a name to ask the holder for")
    record = row_key.split(":", 1)[0].strip()
    qt = query_type or ("household" if record.startswith("census household") else "subject_record")
    key = "word:" + row_key + ":" + holder + ":" + "|".join(f"{k}={clean[k]}" for k in sorted(clean))
    st = q.execute("SELECT id FROM search_plan WHERE person_id=? AND step_key=?", (pid, key)).fetchone()
    if st: return st["id"]
    sid = ulid(); seq = (q.execute("SELECT coalesce(max(seq),0) FROM search_plan WHERE person_id=?", (pid,)).fetchone()[0] or 0) + 1
    fields_json = dumps({k: {"value": v, "basis": "owner"} for k, v in clean.items()})
    q.execute("""INSERT INTO search_plan (id,person_id,row_key,question_id,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,collection_id,on_json,sources_json,mode,expected,status,rationale,created_at)
                 VALUES (?,?,?,NULL,?,?,'fetch',?,?,?,NULL,NULL,NULL,'[]',?,'fetch',?,'planned',?,?)""",
              (sid, pid, row_key, seq, key, qt, fields_json, holder, dumps([holder]), f"the record the owner cites about {who['display_name']}, read for what it says about them",
               f"cited on the owner's word about {who['display_name']}: no citation in the file; fetch the record at {src['name']}", ts))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "insert", "search_plan", sid, dumps({"on_word": True, "person": pid, "row_key": row_key, "holder": holder, "fields": clean, "note": note})))
    return sid

def _source_row(cx, sid):
    r = cx.execute("SELECT id, trust_tier, terms, cost FROM source WHERE id=?", (sid,)).fetchone() if sid else None
    return dict(r) if r else {}

def _cost(text):
    t = (text or "").strip().lower(); return next((c for c in ("free", "paid", "member") if t.startswith(c)), "unknown")

def attach(cx, tree_id, slug, name, steps, by, note=None, query=None, kind=None, value=None, parsed=None, about=None):
    """Archive one inbox file for these steps (provenance from the first: the record's kind gives the trust tier, where it was
    retrieved gives terms and cost; the locator is the step's, or the search URL for a results page), log a found run on every
    step not yet logged with it (a results page's log carries the query as run and the number of results), file the original
    under the tree, then parse and match a page new to the archive. A results page on which no candidate fits has its run set
    to none, the candidates kept on the artifact. Returns what happened."""
    src = os.path.join(inbox_dir(), os.path.basename(name))
    if not os.path.isfile(src): raise ValueError("file not in inbox")
    if not steps and not about: raise ValueError("no step to attach to")
    st = steps[0] if steps else {"sources_json": None, "locator_source_id": None, "collection_id": None, "locator_kind": None, "locator_value": None}
    ts = now(); mime = mimetypes.guess_type(src)[0] or "application/octet-stream"
    sources = json.loads(st["sources_json"] or "[]"); kind_row = _source_row(cx, sources[0] if sources else None); from_row = _source_row(cx, st["locator_source_id"]) or kind_row
    col = cx.execute("SELECT name FROM collection WHERE id=?", (st["collection_id"],)).fetchone() if st["collection_id"] else None
    lkind, lvalue, cname = (("url", value, "Find a Grave memorial search") if kind == "search" else ("url", value, "FamilySearch record search") if kind == "fs_search" else ("url", value, "WWII Army Enlistment Records (AAD)") if kind == "aad_search"
                            else ("url", (parsed or {}).get("url") or value, "WWII Army Enlistment Records (AAD)") if kind == "aad_record"
                            else ("url", st["locator_value"], PHOTO_COLLECTION) if kind == "photo"
                            else ("url", value, col[0] if col else None) if kind == "page"
                            else (st["locator_kind"] or "file", st["locator_value"] or os.path.basename(src), col[0] if col else None))
    holder = {"ark": "D03", "memorial": "E01", "search": "E01", "fs_search": "D03", "aad_search": "F01", "aad_record": "F01", "photo": PHOTOS, "page": st["locator_source_id"]}.get(kind)   # the page's own identity says where it came from, whatever holder the step pointed at; a page taken by name comes from the step's holder
    from_row = _source_row(cx, holder) or from_row
    if kind == "photo":                                                              # the stone itself: an image under the gravestone row, tier 1
        kind_row = from_row
        row = cx.execute("SELECT id, name FROM collection WHERE source_id=? AND name=?", (PHOTOS, PHOTO_COLLECTION)).fetchone()
        if not row: cid = ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, PHOTOS, PHOTO_COLLECTION, "other", "findagrave-photo")); row = (cid, PHOTO_COLLECTION)
        st = dict(st); st["collection_id"] = row[0]
    if kind == "ark" and (parsed or {}).get("collection"):                           # the record's own collection at its holder
        own = re.sub(r"^[^•]*•\s*", "", parsed["collection"]).strip()
        row = cx.execute("SELECT id, name FROM collection WHERE source_id=? AND name=?", (holder, own)).fetchone()
        if not row: cid = ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, holder, own, "other", own)); row = (cid, own)
        st = dict(st); st["collection_id"], cname = row[0], row[1]
    if kind in ("search", "aad_search", "fs_search"):
        query = {k: {"value": v, "basis": "run"} for k, v in parsed["query"].items()}
        note = "; ".join(x for x in (f"{parsed['count'] if parsed['count'] is not None else len(parsed['rows'])} matching records, page {parsed['page']} of {parsed['pages']}, {len(parsed['rows'])} rows on this page", note) if x)
    with open(src, "rb") as fh: data = fh.read()
    sha, new = archive_object(cx, data, mime=mime, source_id=holder or st["locator_source_id"] or (sources[0] if sources else None), collection_id=st["collection_id"], collection_name=cname,
                              locator_kind=lkind, locator_value=lvalue, retrieved_by=by, terms=from_row.get("terms"),
                              cost=_cost(from_row.get("cost")), trust_tier=kind_row.get("trust_tier") or from_row.get("trust_tier"), original_filename=os.path.basename(src), notes=note)
    if kind == "memorial": cx.execute("INSERT OR IGNORE INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (sha, "memorial_id", value))   # the page's own identity, however it was cited
    if kind == "ark": cx.execute("INSERT OR IGNORE INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (sha, "ark", value))
    logs = []
    was = {s["id"]: cx.execute("SELECT status FROM search_plan WHERE id=?", (s["id"],)).fetchone()[0] for s in steps}   # each step's status before this page's run marks it done
    if not steps and about: logs.append(on_word(cx, tree_id, about, sha, by, note=note, parsed=parsed or {}))   # the owner's word: a fetch step on their plan, done with the found run, so the record is fetched for them from now on
    for s in steps:
        if cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json LIKE ?", (s["id"], f'%"{sha}"%')).fetchone(): continue
        fields = rendered_query(s["query_json"], s["revisions_json"])   # the step's own fields, and for a results page the fields as searched beside them (basis run)
        logs.append((s["id"], log_search(cx, tree_id, by, step_id=s["id"], outcome="found", artifacts=[sha], note="; ".join(x for x in (note, s.get("reason") if isinstance(s, dict) else None) if x), query={**fields, **(query or {})})))
    out = {"sha256": sha, "new": new, "mime": mime, "logs": logs, "extraction": None, "proposals": [], "unparsed": None}
    if new and mime.startswith("text/html"):                     # a page is parsed and matched on arrival; an image waits for a transcription
        from extract import extract as extract_html, RESULTS_LISTINGS
        eid, n = extract_html(cx, sha, by); out["extraction"] = eid
        if "failed" in n: out["unparsed"] = n["failed"]
        else: out["proposals"], out["accepted_by_rule"] = match_record(cx, eid, by, about=[about] if about else None)
        is_results_page = cx.execute(f"""SELECT 1 FROM extraction e JOIN extractor x ON x.id=e.extractor_id
                                        WHERE e.id=? AND x.name IN ({','.join('?' * len(RESULTS_LISTINGS))})""", (eid, *RESULTS_LISTINGS)).fetchone()
        if is_results_page and not out["proposals"] and logs:   # a results page whose own rows fit nobody: the run found nothing for the person, the candidates stay on the artifact
            for sid, lid in logs:                                # and a none run holds no record: the step stands as it stood before, planned or done by an earlier run
                cx.execute("UPDATE search_log SET outcome='none', notes=? WHERE id=?", (f"no candidate fits; {note}", lid))
                if sid in was: cx.execute("UPDATE search_plan SET status=? WHERE id=?", (was[sid], sid))
            out["outcome"] = "none"
    filed = os.path.join(imports_dir(slug), "records"); os.makedirs(filed, exist_ok=True)   # the original leaves the inbox last, so a failure before this point leaves it there
    shutil.move(src, os.path.join(filed, f"{ts[:10]}_{re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.basename(src))}"))
    return out

def attach_held(cx, tree_id, slug, name, about_id, by, note=None):
    """A family-held file (a photograph of an object, a letter, a Bible page) with no record identity: archived under the
    family-held source (M05) with the owner's note as its description, filed under the tree, and put before the matcher for
    the person the owner says it is about. What it says about anyone is read afterwards, one persona at a time (the screen's
    transcription form or the model), and decided on a card. Returns the artifact hash and whether it was new."""
    src = os.path.join(inbox_dir(), os.path.basename(name))
    if not os.path.isfile(src): raise ValueError("file not in inbox")
    ts = now(); mime = mimetypes.guess_type(src)[0] or ("image/heic" if src.lower().endswith(".heic") else "application/octet-stream")
    row = _source_row(cx, "M05")
    col = cx.execute("SELECT id FROM collection WHERE source_id='M05' AND name='Family-held originals'").fetchone()
    cid = col[0] if col else ulid()
    if not col: cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, "M05", "Family-held originals", "other", "family"))
    with open(src, "rb") as fh: data = fh.read()
    sha, new = archive_object(cx, data, mime=mime, source_id="M05", collection_id=cid, collection_name="Family-held originals", locator_kind="file", locator_value=os.path.basename(src),
                              retrieved_by=by, terms=row.get("terms"), cost="free", trust_tier=row.get("trust_tier"), original_filename=os.path.basename(src), notes=note)
    cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
               (ulid(), tree_id, "artifact", sha, f"about {cx.execute('SELECT display_name FROM person WHERE id=?', (about_id,)).fetchone()[0]}, on the owner's word" + (f": {note}" if note else ""), by, ts))
    filed = os.path.join(imports_dir(slug), "records"); os.makedirs(filed, exist_ok=True)
    shutil.move(src, os.path.join(filed, f"{ts[:10]}_{re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.basename(src))}"))
    return sha, new

def attach_inbox(cx, tree_id, slug, by, names=None, about=None):
    """Every file in the inbox (or the named ones): identity from the file, the steps it fulfils, attach. A file with no
    identity or no step stays in the inbox, unless the owner says whom a record is about (about: person id): then a record
    with an identity but no step is archived under its holder, given a fetch step on that person's plan done with the found
    run (on_word), and put before the matcher for them. Returns one result per file."""
    names = names or sorted(f for f in os.listdir(inbox_dir()) if os.path.isfile(os.path.join(inbox_dir(), f)) and not f.startswith("."))
    results = []
    for name in names:
        path = os.path.join(inbox_dir(), os.path.basename(name)); r = {"file": os.path.basename(name), "identity": None, "steps": [], "left": None}
        if not os.path.isfile(path): r["left"] = "not in the inbox"; results.append(r); continue
        with open(path, "rb") as fh: data = fh.read()
        kind, value, parsed = identity(data.decode("utf-8", errors="replace")) if (mimetypes.guess_type(path)[0] or "").startswith("text/html") else identity_of_name(name)
        if not kind: r["left"] = "no record identity read from the file (not a Find a Grave memorial or results page, not a FamilySearch record page, not a photograph under the name the fetch list printed)"; results.append(r); continue
        r["identity"] = f"{kind} {value}"
        steps = steps_for(cx, tree_id, kind, value, parsed)
        if kind in ("search", "fs_search", "aad_search") and steps:  # the same search saved again adds nothing to a step that already holds its answer
            fresh = [s for s in steps if not _repeat_save(cx, s["id"], kind, parsed)]
            if not fresh: r["left"] = "the same search, with the same rows, is already logged on every step it fits: a repeat save"; results.append(r); continue
            steps = fresh
        r["steps"] = [(s["id"], cx.execute("SELECT display_name FROM person WHERE id=?", (s["person_id"],)).fetchone()[0], s["row_key"], s.get("reason")) for s in steps]
        if not steps and not about: r["left"] = "no search step in this tree has this search's fields, and no fetch step's citation was searched for by this name at this holder" if kind in ("search", "fs_search") else "no step in this tree asks for this photograph" if kind == "photo" else "no fetch step in this tree cites this record"; results.append(r); continue
        r.update(attach(cx, tree_id, slug, name, steps, by, note=f"attached from the inbox by identity: {kind} {value}" + (" on the owner's word about the person" if not steps else ""), kind=kind, value=value, parsed=parsed, about=about))
        results.append(r)
    return results

def line(r):
    """One line per file, as the inbox tool prints it."""
    if r["left"]: return f"{r['file']}: {r['identity'] or 'no identity'}; left in the inbox: {r['left']}"
    who = "; ".join(f"{n} ({rk.split(':')[0]}: {why or 'the step cites it'})" for _, n, rk, why in r["steps"])
    return (f"{r['file']}: {r['identity']}; {len(r['steps'])} step(s) fulfilled: {who}; artifact {r['sha256'][:12]}{'' if r['new'] else ' (already archived)'}; "
            f"{len(r['logs'])} run(s) logged{' as none' if r.get('outcome') == 'none' else ''}; extraction {r['extraction'] or '-'}; {len(r['proposals'])} proposal(s)" + (f"; unparsed: {r['unparsed']}" if r["unparsed"] else ""))
