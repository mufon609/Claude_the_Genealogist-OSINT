"""Attach a record file to the steps it fulfils: the archive once, a found run logged on every step, then the extractor
and the matcher once, after the log rows exist, so the matcher sees every person the record was fetched for.

One code path for tools/attach_inbox.py and the person screen's "Archive + log". The record's identity is read from the
file itself, never from its name: a Find a Grave memorial id from the memorial's own markup (memNumberLabel), a
FamilySearch ark from the record page's print header. The steps a record fulfils are the tree's fetch steps whose citation
carries that identity: for a memorial, the memorial URL in the step's fields; for an ark, the record id the artifact was
archived under (and every id naming the same census page) once it is in the archive, else the census page the record
page itself names (year, enumeration district, sheet, county and state) against each step's citation details. A file
whose identity matches no step is not archived by the inbox tool; the screen still attaches it to the step the person
chose. Archived bytes are linked, not copied, and a step already logged with the same artifact is not logged again.
"""
import json, mimetypes, os, re, shutil, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import archive_object, dumps, imports_dir, inbox_dir, now, ulid
from catalog import dbid_of, same_page
from log_search import log as log_search, rendered_query
from extract import FS_MARK, parse_memorial, parse_record, parse_search, AAD_MARK, parse_aad_search, parse_aad_record
from match import key as name_key
from conclude import match_record

MEMORIAL_URL = re.compile(r"findagrave\.com/memorial/(\d+)(?:/|$)")

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

def steps_for(cx, tree_id, kind, value, parsed=None):
    """The tree's steps this identity fulfils: for a memorial or an ark, the fetch steps whose citation carries it, the citation on
    the person themselves first; for a search results page, the cemetery search steps whose fields are the search's own query."""
    if kind == "search":
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='search' AND sp.sources_json LIKE '%"E01"%'
                             ORDER BY sp.seq""", (tree_id,)).fetchall()
        return [r for r in rows if _same_search(r, (parsed or {}).get("query") or {})]
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
        return out
    if kind == "memorial":
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch'
                             AND json_extract(sp.query_json,'$.url.value') LIKE ? ORDER BY sp.on_json='[]' DESC, sp.seq""", (tree_id, f"%/memorial/{value}/%")).fetchall()
        return [r for r in rows if (MEMORIAL_URL.search(json.loads(r["query_json"]).get("url", {}).get("value") or "") or [None, None])[1] == value]
    if kind == "ark":
        loc = cx.execute("""SELECT a.locator_value FROM artifact_locator l JOIN artifact a ON a.sha256=l.artifact_sha256
                            WHERE l.kind='ark' AND l.value=? AND a.locator_kind='apid'""", (value,)).fetchone()
        if loc:
            ids = sorted(same_page(cx, loc[0]))
            return cx.execute(f"""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.locator_kind='apid'
                                  AND sp.locator_value IN ({','.join('?'*len(ids))}) ORDER BY sp.on_json='[]' DESC, sp.seq""", (tree_id, *ids)).fetchall()
        named = _page_named(parsed or {})
        if named:
            rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.locator_kind='apid'
                                 AND sp.query_type='household' ORDER BY sp.on_json='[]' DESC, sp.seq""", (tree_id,)).fetchall()
            return [r for r in rows if _cites_page(r, named)]
        return _steps_by_kind(cx, tree_id, parsed or {})
    return []

ROW_OF = [(r"obituar", "obituary"), (r"death", "death record"), (r"birth", "birth record"), (r"marriage", "marriage record"), (r"social security|numident", "Social Security (SSDI / SS-5)"),
          (r"draft", "WWII draft card"), (r"naturali", "naturalization"), (r"find a grave|burial|cemetery", "cemetery / family plot")]

def _steps_by_kind(cx, tree_id, parsed):
    """A record that names no census page: the steps of the checklist row its collection is about (an obituary collection to the
    obituary row, a death index to the death record row, the Social Security files to that row), on every person of the tree
    whose name is the record's principal name. The record satisfies the row whatever holder the file had pointed at."""
    coll = (parsed.get("collection") or "").lower(); row = next((r for rx, r in ROW_OF if re.search(rx, coll)), None)
    if not row: return []
    pg, rest = _split_name(parsed.get("name") or "")
    if not pg or not rest: return []
    out = []
    for r in cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.status='planned' AND sp.row_key LIKE ? ORDER BY sp.seq""", (tree_id, row + ":%")):
        keys = {(name_key((g or "").split()[0]) if g else "", name_key(sn)) for g, sn in cx.execute("SELECT given, surname FROM person_name WHERE person_id=?", (r["person_id"],))}
        if any(g == pg and sn in rest for g, sn in keys): out.append(r)
    return out

def _split_name(text):
    parts = [name_key(x) for x in re.sub(r"^(mr|mrs|miss|ms|dr)\.?\s+", "", (text or "").strip(), flags=re.I).split() if name_key(x)]
    return (parts[0], parts[1:]) if parts else ("", [])

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
    lkind, lvalue, cname = (("url", value, "Find a Grave memorial search") if kind == "search" else ("url", value, "WWII Army Enlistment Records (AAD)") if kind == "aad_search"
                            else ("url", (parsed or {}).get("url") or value, "WWII Army Enlistment Records (AAD)") if kind == "aad_record"
                            else (st["locator_kind"] or "file", st["locator_value"] or os.path.basename(src), col[0] if col else None))
    holder = {"ark": "D03", "memorial": "E01", "search": "E01", "aad_search": "F01", "aad_record": "F01"}.get(kind)   # the page's own identity says where it came from, whatever holder the step pointed at
    from_row = _source_row(cx, holder) or from_row
    if kind == "ark" and (parsed or {}).get("collection"):                           # the record's own collection at its holder
        own = re.sub(r"^[^•]*•\s*", "", parsed["collection"]).strip()
        row = cx.execute("SELECT id, name FROM collection WHERE source_id=? AND name=?", (holder, own)).fetchone()
        if not row: cid = ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, holder, own, "other", own)); row = (cid, own)
        st = dict(st); st["collection_id"], cname = row[0], row[1]
    if kind in ("search", "aad_search"):
        query = {k: {"value": v, "basis": "run"} for k, v in parsed["query"].items()}
        note = "; ".join(x for x in (f"{parsed['count'] if parsed['count'] is not None else len(parsed['rows'])} matching records, page {parsed['page']} of {parsed['pages']}, {len(parsed['rows'])} rows on this page", note) if x)
    with open(src, "rb") as fh: data = fh.read()
    sha, new = archive_object(cx, data, mime=mime, source_id=holder or st["locator_source_id"] or (sources[0] if sources else None), collection_id=st["collection_id"], collection_name=cname,
                              locator_kind=lkind, locator_value=lvalue, retrieved_by=by, terms=from_row.get("terms"),
                              cost=_cost(from_row.get("cost")), trust_tier=kind_row.get("trust_tier") or from_row.get("trust_tier"), original_filename=os.path.basename(src), notes=note)
    if kind == "memorial": cx.execute("INSERT OR IGNORE INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (sha, "memorial_id", value))   # the page's own identity, however it was cited
    logs = []
    for s in steps:
        if cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json LIKE ?", (s["id"], f'%"{sha}"%')).fetchone(): continue
        logs.append((s["id"], log_search(cx, tree_id, by, step_id=s["id"], outcome="found", artifacts=[sha], note=note, query=query or rendered_query(s["query_json"], s["revisions_json"]))))
    out = {"sha256": sha, "new": new, "mime": mime, "logs": logs, "extraction": None, "proposals": [], "unparsed": None}
    if new and mime.startswith("text/html"):                     # a page is parsed and matched on arrival; an image waits for a transcription
        from extract import extract as extract_html
        eid, n = extract_html(cx, sha, by); out["extraction"] = eid
        if "failed" in n: out["unparsed"] = n["failed"]
        else: out["proposals"], out["accepted_by_rule"] = match_record(cx, eid, by, about=[about] if about else None)
        if kind in ("search", "aad_search") and not out["proposals"] and logs:   # no candidate fits: the run found nothing for the person; the candidates stay on the artifact
            for _, lid in logs: cx.execute("UPDATE search_log SET outcome='none', notes=? WHERE id=?", (f"no candidate fits; {note}", lid))
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
    with an identity but no step is archived under its holder and put before the matcher for that person, as a search the
    owner ran by hand. Returns one result per file."""
    names = names or sorted(f for f in os.listdir(inbox_dir()) if os.path.isfile(os.path.join(inbox_dir(), f)) and not f.startswith("."))
    results = []
    for name in names:
        path = os.path.join(inbox_dir(), os.path.basename(name)); r = {"file": os.path.basename(name), "identity": None, "steps": [], "left": None}
        if not os.path.isfile(path): r["left"] = "not in the inbox"; results.append(r); continue
        with open(path, "rb") as fh: data = fh.read()
        kind, value, parsed = identity(data.decode("utf-8", errors="replace")) if (mimetypes.guess_type(path)[0] or "").startswith("text/html") else (None, None, None)
        if not kind: r["left"] = "no record identity read from the file (not a Find a Grave memorial or results page, not a FamilySearch record page)"; results.append(r); continue
        r["identity"] = f"{kind} {value}"
        steps = steps_for(cx, tree_id, kind, value, parsed)
        r["steps"] = [(s["id"], cx.execute("SELECT display_name FROM person WHERE id=?", (s["person_id"],)).fetchone()[0], s["row_key"]) for s in steps]
        if not steps and not about: r["left"] = "no cemetery search step in this tree has this search's fields" if kind == "search" else "no fetch step in this tree cites this record"; results.append(r); continue
        r.update(attach(cx, tree_id, slug, name, steps, by, note=f"attached from the inbox by identity: {kind} {value}" + (" on the owner's word about the person" if not steps else ""), kind=kind, value=value, parsed=parsed, about=about))
        results.append(r)
    return results

def line(r):
    """One line per file, as the inbox tool prints it."""
    if r["left"]: return f"{r['file']}: {r['identity'] or 'no identity'}; left in the inbox: {r['left']}"
    who = ", ".join(f"{n} ({rk.split(':')[0]})" for _, n, rk in r["steps"])
    return (f"{r['file']}: {r['identity']}; {len(r['steps'])} step(s) fulfilled: {who}; artifact {r['sha256'][:12]}{'' if r['new'] else ' (already archived)'}; "
            f"{len(r['logs'])} run(s) logged{' as none' if r.get('outcome') == 'none' else ''}; extraction {r['extraction'] or '-'}; {len(r['proposals'])} proposal(s)" + (f"; unparsed: {r['unparsed']}" if r["unparsed"] else ""))
