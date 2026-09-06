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
from treelib import archive_object, dumps, imports_dir, inbox_dir, now
from catalog import dbid_of, same_page
from log_search import log as log_search, rendered_query
from extract import FS_MARK, parse_memorial, parse_record
from match import match as match_personas

MEMORIAL_URL = re.compile(r"findagrave\.com/memorial/(\d+)(?:/|$)")

def identity(text):
    """(kind, value, parsed) from a record page's own markup: ("memorial", id, parsed memorial), ("ark", ark, parsed record), or (None, None, None)."""
    if re.search(r'<body[^>]*\bid="memorial-summary"', text):
        p = parse_memorial(text); mid = re.sub(r"\D", "", p.get("memorial_id") or "")
        return ("memorial", mid, p) if mid else (None, None, p)
    if FS_MARK.search(text):
        p = parse_record(text)
        return ("ark", p["ark"], p) if p.get("ark") else (None, None, p)
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

def steps_for(cx, tree_id, kind, value, parsed=None):
    """The tree's fetch steps whose citation carries this identity, the citation on the person themselves first."""
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
        if not named: return []
        rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.locator_kind='apid'
                             AND sp.query_type='household' ORDER BY sp.on_json='[]' DESC, sp.seq""", (tree_id,)).fetchall()
        return [r for r in rows if _cites_page(r, named)]
    return []

def _source_row(cx, sid):
    r = cx.execute("SELECT id, trust_tier, terms, cost FROM source WHERE id=?", (sid,)).fetchone() if sid else None
    return dict(r) if r else {}

def _cost(text):
    t = (text or "").strip().lower(); return next((c for c in ("free", "paid", "member") if t.startswith(c)), "unknown")

def attach(cx, tree_id, slug, name, steps, by, note=None, query=None):
    """Archive one inbox file for these steps (provenance from the first: the record's kind gives the trust tier, where it was
    retrieved gives terms and cost, its locator is the artifact's), log a found run on every step not yet logged with it, file
    the original under the tree, then parse and match a record page new to the archive. Returns what happened."""
    src = os.path.join(inbox_dir(), os.path.basename(name))
    if not os.path.isfile(src): raise ValueError("file not in inbox")
    if not steps: raise ValueError("no step to attach to")
    st = steps[0]; ts = now(); mime = mimetypes.guess_type(src)[0] or "application/octet-stream"
    sources = json.loads(st["sources_json"] or "[]"); kind_row = _source_row(cx, sources[0] if sources else None); from_row = _source_row(cx, st["locator_source_id"]) or kind_row
    col = cx.execute("SELECT name FROM collection WHERE id=?", (st["collection_id"],)).fetchone() if st["collection_id"] else None
    with open(src, "rb") as fh: data = fh.read()
    sha, new = archive_object(cx, data, mime=mime, source_id=st["locator_source_id"] or (sources[0] if sources else None), collection_id=st["collection_id"], collection_name=col[0] if col else None,
                              locator_kind=st["locator_kind"] or "file", locator_value=st["locator_value"] or os.path.basename(src), retrieved_by=by, terms=from_row.get("terms"),
                              cost=_cost(from_row.get("cost")), trust_tier=kind_row.get("trust_tier") or from_row.get("trust_tier"), original_filename=os.path.basename(src), notes=note)
    logs = []
    for s in steps:
        if cx.execute("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json LIKE ?", (s["id"], f'%"{sha}"%')).fetchone(): continue
        logs.append((s["id"], log_search(cx, tree_id, by, step_id=s["id"], outcome="found", artifacts=[sha], note=note, query=query or rendered_query(s["query_json"], s["revisions_json"]))))
    filed = os.path.join(imports_dir(slug), "records"); os.makedirs(filed, exist_ok=True)
    shutil.move(src, os.path.join(filed, f"{ts[:10]}_{re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.basename(src))}"))
    out = {"sha256": sha, "new": new, "mime": mime, "logs": logs, "extraction": None, "proposals": [], "unparsed": None}
    if new and mime.startswith("text/html"):                     # a record page is parsed and matched on arrival; an image waits for a transcription
        from extract import extract as extract_html
        eid, n = extract_html(cx, sha, by); out["extraction"] = eid
        if "failed" in n: out["unparsed"] = n["failed"]
        else: out["proposals"] = match_personas(cx, eid, by)
    return out

def attach_inbox(cx, tree_id, slug, by, names=None):
    """Every file in the inbox (or the named ones): identity from the file, the steps it fulfils, attach. A file with no
    identity or no step stays in the inbox. Returns one result per file."""
    names = names or sorted(f for f in os.listdir(inbox_dir()) if os.path.isfile(os.path.join(inbox_dir(), f)) and not f.startswith("."))
    results = []
    for name in names:
        path = os.path.join(inbox_dir(), os.path.basename(name)); r = {"file": os.path.basename(name), "identity": None, "steps": [], "left": None}
        if not os.path.isfile(path): r["left"] = "not in the inbox"; results.append(r); continue
        with open(path, "rb") as fh: data = fh.read()
        kind, value, parsed = identity(data.decode("utf-8", errors="replace")) if (mimetypes.guess_type(path)[0] or "").startswith("text/html") else (None, None, None)
        if not kind: r["left"] = "no record identity read from the file (not a Find a Grave memorial or a FamilySearch record page)"; results.append(r); continue
        r["identity"] = f"{kind} {value}"
        steps = steps_for(cx, tree_id, kind, value, parsed)
        r["steps"] = [(s["id"], cx.execute("SELECT display_name FROM person WHERE id=?", (s["person_id"],)).fetchone()[0], s["row_key"]) for s in steps]
        if not steps: r["left"] = "no fetch step in this tree cites this record"; results.append(r); continue
        r.update(attach(cx, tree_id, slug, name, steps, by, note=f"attached from the inbox by identity: {kind} {value}"))
        results.append(r)
    return results

def line(r):
    """One line per file, as the inbox tool prints it."""
    if r["left"]: return f"{r['file']}: {r['identity'] or 'no identity'}; left in the inbox: {r['left']}"
    who = ", ".join(f"{n} ({rk.split(':')[0]})" for _, n, rk in r["steps"])
    return (f"{r['file']}: {r['identity']}; {len(r['steps'])} step(s) fulfilled: {who}; artifact {r['sha256'][:12]}{'' if r['new'] else ' (already archived)'}; "
            f"{len(r['logs'])} run(s) logged; extraction {r['extraction'] or '-'}; {len(r['proposals'])} proposal(s)" + (f"; unparsed: {r['unparsed']}" if r["unparsed"] else ""))
