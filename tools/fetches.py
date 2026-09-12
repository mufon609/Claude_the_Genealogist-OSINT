#!/usr/bin/env python3
"""The pages waiting to be fetched by hand at every holder, and the pages that came back.

usage: tools/fetches.py list [--json] [--tree slug] [--db catalog/tree.db]
       tools/fetches.py collect [--by user:<you>] [--tree slug] [--db catalog/tree.db]

Find a Grave forbids automation and FamilySearch answers a browser only, so a cited record at such a holder is saved one page
at a time in the owner's own browser by the page-saves-itself method (docs/RESEARCH-WORKFLOW.md §4, tools/save_page.js),
one tab per page; a gravestone photograph the same way in the image's own tab (tools/save_image.js), under the name the list
prints. `list` prints every planned fetch step whose holder has no connector, or whose holder's connector has
nothing to ask from the citation (a book cited with no title), once per page, with the holder, the
link to open (the memorial page itself; the holder's own search prefilled from the citation's details), the people whose
steps it fulfils, and the file name to save under (a FamilySearch page's name takes the record's own ark id from its page;
`collect` recognises the memorial, FamilySearch, AAD and photograph names, and a page from any other holder is attached from
the person screen on its step): the leads from held records first (a persona accepted as a person, whose memorial
the record links), then the file's citations, the pages that settle most steps first. `collect` moves every saved page
from the browser's download folder into inbox/ and attaches each by its own identity (tools/attach.py): archived once,
logged found on every step that cites it, extracted, matched, the rule run.
"""
import argparse, json, os, re, shutil, sqlite3, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, inbox_dir, resolve_tree
from attach import attach_inbox, line
from catalog import Catalog, fetch_target
from log_search import rendered_query
import connectors

MEMORIAL = re.compile(r"/memorial/(\d+)(?:/|$)")

def _slug(text): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").lower())).strip("-")

def save_as(holder_id, fields, row_key, mid=None):
    """The file name a saved page takes, in the shape tools/fetches.py collect recognises: findagrave-memorial-<id>.html for a
    memorial; familysearch-<collection words>-<year>-<ark id>.html for a FamilySearch record page, the year from the citation
    or the row, the ark id read off the record page (the part after ark:/61903/1:1:)."""
    if holder_id == "E01" and mid: return f"findagrave-memorial-{mid}.html"
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if holder_id == "E05": return f"findagrave-photo-{v('memorial')}-{v('photo')}" + (os.path.splitext((v("url") or "").split("?")[0])[1].lower() or ".jpg")
    coll = v("collection") or ""
    words = "census" if re.search(r"census", coll, re.I) else _slug(re.sub(r"[\d\u2013-]+|U\.S\.", " ", coll))[:40] or "record"
    inst = row_key.split(":", 1)[1] if ":" in row_key else ""
    year = v("year") or (inst if inst.isdigit() else None) or "<year>"
    return f"familysearch-{words}-{year}-<ark id>.html" if holder_id == "D03" else f"{_slug(holder_id)}-{words}-{year}-<record id>.html"

def waiting(cx, tree_id):
    """Every planned fetch step whose holder has no connector, or whose connector has nothing to ask from the citation, once per
    page: holder, url, the people and the number of steps waiting on it, whether it is a lead from a held record (locator
    memorial_id) or the file's citation (locator apid), and the file name to save under. Steps citing one census page (the
    household's record ids) are one page."""
    cat = Catalog(cx, tree_id); groups = cat.page_groups(); out = {}
    for s in cx.execute("""SELECT sp.id, sp.locator_source_id, sp.locator_kind, sp.locator_value, sp.query_json, sp.revisions_json, sp.row_key, p.display_name,
                           src.name AS holder_name, src.connector FROM search_plan sp JOIN person p ON p.id=sp.person_id LEFT JOIN source src ON src.id=sp.locator_source_id
                           WHERE p.tree_id=? AND sp.kind='fetch' AND sp.mode='fetch' AND sp.status='planned' ORDER BY sp.seq""", (tree_id,)):
        if s["connector"] and connectors.load(s["connector"]).requests(rendered_query(s["query_json"], s["revisions_json"])): continue   # the runner takes it
        fields = json.loads(s["query_json"] or "{}"); url = (fields.get("url") or {}).get("value") or ""
        hid = s["locator_source_id"]; m = MEMORIAL.search(url)
        mid = s["locator_value"] if s["locator_kind"] == "memorial_id" else (m.group(1) if m else None)
        if hid == "E01":
            if not mid: continue
            key = (hid, mid); link = f"https://www.findagrave.com/memorial/{mid}/"; holder = "Find a Grave"
        elif s["locator_kind"] == "apid":
            key = (hid, min(groups.get(s["locator_value"]) or {s["locator_value"]}))
            t = fetch_target(s["locator_value"], url, fields); link = t["url"]; holder = f"{s['holder_name']}: {t['holder']}" if t["holder"] else s["holder_name"]
        else:
            key = (hid, s["locator_value"]); link = url or None; holder = s["holder_name"]
        e = out.setdefault(key, {"holder_id": hid, "holder": holder, "url": link, "lead": False, "people": [], "steps": 0, "rows": [],
                                 "save_as": save_as(hid, fields, s["row_key"], mid), "how": "image" if hid == "E05" else "page"})
        e["steps"] += 1; e["lead"] = e["lead"] or s["locator_kind"] in ("memorial_id", "url")
        if s["display_name"] not in e["people"]: e["people"].append(s["display_name"])
        rk = s["row_key"].split(":")[0]
        if rk not in e["rows"]: e["rows"].append(rk)
    return sorted(out.values(), key=lambda e: (not e["lead"], e["holder"], -e["steps"], e["url"] or ""))

def downloads_dir():
    try: return subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=5).stdout.strip() or os.path.expanduser("~/Downloads")
    except Exception: return os.path.expanduser("~/Downloads")

def collect(cx, tree_id, slug, by):
    """Every page in the download folder saved under a name the list printed for a memorial, a FamilySearch record, an AAD
    record or a gravestone photograph: moved to inbox/, then attached by its own identity (a photograph's is in its name). A page from a holder whose pages carry no identity the attach
    reads stays where it is and is attached from the person screen on its step. Returns the attach results."""
    names = []
    for f in sorted(os.listdir(downloads_dir())):
        if re.fullmatch(r"(findagrave-memorial-\d+|familysearch-[a-z0-9-]+-\d+-[A-Za-z0-9_:-]+|aad-enlistment-[A-Za-z0-9_-]+)\.html|findagrave-photo-\d+-\d+\.(jpe?g|png|webp|gif)", f, re.I):
            shutil.move(os.path.join(downloads_dir(), f), os.path.join(inbox_dir(), f)); names.append(f)
    return names, (attach_inbox(cx, tree_id, slug, by, names) if names else [])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["list", "collect"]); ap.add_argument("--json", action="store_true"); ap.add_argument("--tree")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.cmd == "list":
        rows = waiting(cx, tree_id)
        if a.json: print(dumps(rows)); return
        last = None
        for e in rows:
            if e["holder"] != last: print(f"-- {e['holder']}"); last = e["holder"]
            print(f"{'lead ' if e['lead'] else 'cited'} {e['url']}  {', '.join(e['people'])}  ({e['steps']} step{'s' if e['steps'] > 1 else ''}: {', '.join(e['rows'])})  save as {e['save_as']}" + ("  (an image: tools/save_image.js in its own tab)" if e["how"] == "image" else ""))
        print(f"{len(rows)} page(s) to fetch, one tab per page; then tools/fetches.py collect")
    else:
        cx.execute("BEGIN")
        try: names, results = collect(cx, tree_id, slug, a.by); cx.commit()
        except Exception: cx.rollback(); raise
        for r in results: print(line(r))
        if not names: print(f"nothing saved in {downloads_dir()}")

if __name__ == "__main__": main()
