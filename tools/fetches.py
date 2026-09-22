#!/usr/bin/env python3
"""The pages waiting to be fetched by hand at every holder, and the pages that came back.

usage: tools/fetches.py list [--json] [--tree slug] [--db catalog/tree.db]
       tools/fetches.py collect [--folder DIR] [--by user:<you>] [--tree slug] [--db catalog/tree.db]

Find a Grave forbids automation and FamilySearch answers a browser only, so a cited record at such a holder is saved one page
at a time in the owner's own browser by the page-saves-itself method (docs/RESEARCH-WORKFLOW.md §4, tools/save_page.js),
one tab per page; a gravestone photograph the same way in the image's own tab (tools/save_image.js), under the name the list
prints. `list` prints every planned fetch step whose holder has no connector at all (a holder whose connector merely has
nothing to ask yet, a book cited with no title, runs through tools/run_step.py instead: a `none` run naming the field
wanted, off this list, left for a hand on the person's screen), once per page, with the holder, the
link to open (the memorial page itself; the holder's own search prefilled from the citation's details, a collection's own
search when no record id of the holder's is known yet; once that search's saved page has a row proposed or accepted as the
step's person, the row's own record page instead, under the record-page name with the row's ark filled in, open until a page
carrying that ark is archived), the people whose steps it fulfils, and the file name to save under
(a FamilySearch record page's name takes the record's own ark id from its page; a FamilySearch or other holder's search
carries the search's own given name and surname, so the several people's steps one search serves share one name; a page
from any other holder carries no identity the attach reads, so it is listed once per citation and person waiting on it,
under a name that carries the citation's own record locator and ends in that person's six characters): the leads from
held records first (a persona accepted as a person, whose memorial the record links), then the file's citations, the pages
that settle most steps first. `collect` moves every saved page from the browser's download folder (or --folder) into
`inbox/` and attaches each: a photograph by its own name (it carries no identity in its bytes), any other .html page whose
saved-from line (the browser's own comment, tools/save_page.js) is a FamilySearch record or search URL, a Find a Grave
memorial or search, or an AAD record or search, by that identity (tools/attach.py identity) whatever the name says —
archived once, logged found on every step that cites it, extracted, matched, the rule run; a page from a holder whose
pages carry no identity the attach reads, by the name the list printed, to the steps of the one citation and person the
name carries, archived under that holder with the page's own URL (the saved-from line the browser wrote) as locator,
logged found, and reported unparsed until a parser claims it. A file with neither a recognised saved-from line nor a
listed name is left in the folder.
"""
import argparse, json, os, re, shutil, sqlite3, subprocess, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, inbox_dir, resolve_tree
from attach import ark_id, attach, attach_inbox, line, pointed_at
from catalog import Catalog, fetch_target, browse_only, dbid_of
from log_search import ran_unchanged, rendered_query, step_source
import connectors

MEMORIAL = re.compile(r"/memorial/(\d+)(?:/|$)")

def _slug(text): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").lower())).strip("-")

def save_as(holder_id, fields, row_key, mid=None, six=None, piece=None, url=None):
    """The file name a saved page takes: findagrave-memorial-<id>.html for a memorial; for a FamilySearch link (D03),
    familysearch-<collection words>-search-<given>-<surname>.html when the link is the collection's own search (no ark in
    the citation: url carries no /ark:/, given and surname read off the search's own q.givenName/q.surname), so the several
    people's steps one search serves share one name, as the list already groups them by URL; a census collection's search
    carries the row's own year too (familysearch-census-<year>-search-<given>-<surname>.html), the row_key's year, since
    "census" alone would collapse a person's two census searches (the 1925 New York state census and the 1930 federal
    census) into one name; a link with no surname to search by (a catalog browsed, not searched) falls to the record-page
    shape below; familysearch-<collection words>-<year>-<ark id>.html for a link that is a record page (a lead with an
    ark), the year from the citation or the row, the ark id read off the record page (the part after ark:/61903/1:1:);
    <holder>-<collection words>-<piece>-<six>.html for a page at any other holder, piece being the citation's own record
    locator (the step's key when it has none) and six the six characters of the person the page is saved for (the
    listing's own way of naming one person), since such a page carries no identity the attach reads and the citation no
    record id of the holder's: the piece keeps one person's pages of one collection apart, the six characters two people's
    pages of one, and no part of the name waits on a year the citation may not carry."""
    if holder_id == "E01" and mid: return f"findagrave-memorial-{mid}.html"
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if holder_id == "E05": return f"findagrave-photo-{v('memorial')}-{v('photo')}" + (os.path.splitext((v("url") or "").split("?")[0])[1].lower() or ".jpg")
    coll = v("collection") or ""
    census = bool(re.search(r"census", coll, re.I))
    words = "census" if census else _slug(re.sub(r"[\d\u2013-]+|U\.S\.", " ", coll))[:40] or "record"
    if holder_id == "D03":
        row_year = row_key.split(":", 1)[1] if ":" in row_key else ""
        if url and "/ark:/" not in url:
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            given = _slug((q.get("q.givenName") or [""])[0]); surname = _slug((q.get("q.surname") or [""])[0])
            if surname: return f"familysearch-{words}{'-' + row_year if census and row_year.isdigit() else ''}-search-{given}-{surname}.html"
        return f"familysearch-{words}-{v('year') or (row_year if row_year.isdigit() else None) or '<year>'}-<ark id>.html"
    return f"{_slug(holder_id)}-{words}-{_slug(piece)}-{six}.html"

def waiting(cx, tree_id):
    """Every planned fetch step whose holder has no connector, once per page: holder, url, the people and the number of
    steps waiting on it, whether it is a lead from a held record (locator memorial_id) or the file's citation (locator
    apid), and the file name to save under. A step whose holder has a connector never appears here, whether or not that
    connector currently has anything to ask: it runs through tools/run_step.py, which logs a `none` run naming the field
    wanted when it has nothing to ask, so the step is answered on its fields and left for a hand on the person's screen, not
    the browser. Steps citing one census page (the household's record ids) are one page. A page at a holder whose pages carry
    no identity the attach reads (no memorial id, no ark) is one entry per citation and person waiting on it, named for both,
    so the saved file reaches that person's steps on that citation alone. A FamilySearch step whose latest holder run was found
    on a results listing with a row proposed or accepted as the step's person (attach.pointed_at) is listed as that row's own
    record page, one entry per ark however many steps it serves, under the record-page name with the ark filled and the year
    from the citation, the row or the listing's row: the listing pointed at the record and is not one, so its page is the next
    to save. A step at a browse-only holder (catalog.browse_only:
    a FamilySearch images-only collection) never appears either: nobody can save such a page the page-saves-itself way,
    so it stays on the plan with its reason and off this list, never a name with an unfilled placeholder."""
    cat = Catalog(cx, tree_id); groups = cat.page_groups(); out = {}
    def add(s, key, link, holder, name, ark=None):
        e = out.setdefault(key, {"holder_id": s["locator_source_id"], "holder": holder, "url": link, "lead": False, "people": [], "steps": 0, "step_ids": [], "rows": [],
                                 "save_as": name, "how": "image" if s["locator_source_id"] == "E05" else "page", "ark": ark})
        e["steps"] += 1; e["step_ids"].append(s["id"]); e["lead"] = e["lead"] or s["locator_kind"] in ("memorial_id", "url")
        if s["display_name"] not in e["people"]: e["people"].append(s["display_name"])
        rk = s["row_key"].split(":")[0]
        if rk not in e["rows"]: e["rows"].append(rk)
    for s in cx.execute("""SELECT sp.id, sp.person_id, sp.step_key, sp.locator_source_id, sp.locator_kind, sp.locator_value, sp.query_json, sp.revisions_json, sp.row_key, p.display_name,
                           src.name AS holder_name, src.connector FROM search_plan sp JOIN person p ON p.id=sp.person_id LEFT JOIN source src ON src.id=sp.locator_source_id
                           WHERE p.tree_id=? AND sp.kind='fetch' AND sp.mode='fetch' AND sp.status='planned' ORDER BY sp.seq""", (tree_id,)):
        if s["connector"]: continue   # the runner takes it, or logs a none run naming the field it wants when it has nothing to ask (tools/run_step.py runnable)
        fields = json.loads(s["query_json"] or "{}"); url = (fields.get("url") or {}).get("value") or ""
        hid = s["locator_source_id"]; m = MEMORIAL.search(url); piece = s["step_key"]
        mid = s["locator_value"] if s["locator_kind"] == "memorial_id" else (m.group(1) if m else None)
        if hid == "E01":
            if not mid: continue
            key = (hid, mid); link = f"https://www.findagrave.com/memorial/{mid}/"; holder = "Find a Grave"
        elif s["locator_kind"] == "apid":
            if browse_only((cat.holders.get(dbid_of(s["locator_value"])) or [None])[0]): continue   # browsed by hand, film by film: no page the browser can save, so it stays off the list
            pointed = pointed_at(cx, s) if hid == "D03" else []
            if pointed:                                                          # the listing's fitting row: its own record page is the next page, one entry per ark
                for ark, link, year in pointed:
                    row_year = s["row_key"].split(":", 1)[-1] if ":" in s["row_key"] else ""
                    yr = (fields.get("year") or {}).get("value") or (row_year if row_year.isdigit() else None) or year     # the citation's year, the row's, else the listing row's own
                    name = save_as(hid, {**fields, **({"year": {"value": yr}} if yr else {})}, s["row_key"], None, None, None, link).replace("<ark id>", ark_id(ark)).replace("-<year>", "")
                    add(s, (hid, "ark", ark), link, f"{s['holder_name']}: the record a row of the search points at", name, ark)
                continue
            page = piece = min(groups.get(s["locator_value"]) or {s["locator_value"]})
            key = (hid, page) if hid == "D03" else (hid, page, s["person_id"])      # a FamilySearch page carries its ark; any other page is named for its citation and person
            t = fetch_target(s["locator_value"], url, fields); link = t["url"]; holder = f"{s['holder_name']}: {t['holder']}" if t["holder"] else s["holder_name"]
        else:
            key = (hid, s["locator_value"]); link = url or None; holder = s["holder_name"]
        add(s, key, link, holder, save_as(hid, fields, s["row_key"], mid, s["person_id"][-6:], piece, link))
    return sorted(out.values(), key=lambda e: (not e["lead"], e["holder"], -e["steps"], e["url"] or ""))

def openable(cx, tree_id):
    """The waiting pages a turn can send someone to: entries with a link to open, each with open_step_ids, the steps among its
    step_ids with no run at the step's own source (log_search.step_source: the holder, or the row's first source, what a page
    saved by hand is logged under) since the plan last wrote their fields (log_search.ran_unchanged, the reading the runner's
    own runnable steps use per source); a run of a row source's connector on the same step (an obituary step answered at the
    Archive's newspapers) does not stand for the holder's page. An entry with none is left out. A
    page saved once and logged (found, none, blocked) on a step's unchanged fields is listed by `list` as still waiting, but
    that step does not send anyone to it again until the plan changes it; a page seven people's steps share is open for the
    people whose own step is still unrun. The record page a listing's row points at (an entry with an ark) is open for every
    step it serves until an artifact carries that ark as a locator: the listing's own run answered the search, not the record."""
    out = []
    for e in waiting(cx, tree_id):
        if not e["url"]: continue
        if e.get("ark"):
            if not cx.execute("SELECT 1 FROM artifact_locator WHERE kind='ark' AND value=?", (e["ark"],)).fetchone(): out.append({**e, "open_step_ids": list(e["step_ids"])})
            continue
        steps = [cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,)).fetchone() for sid in e["step_ids"]]
        open_ids = [st["id"] for st in steps if st and not ran_unchanged(cx, st, rendered_query(st["query_json"], st["revisions_json"]), step_source(st))]
        if open_ids: out.append({**e, "open_step_ids": open_ids})
    return out

def downloads_dir():
    try: return subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=5).stdout.strip() or os.path.expanduser("~/Downloads")
    except Exception: return os.path.expanduser("~/Downloads")

PHOTO_NAME = re.compile(r"findagrave-photo-\d+-\d+\.(jpe?g|png|webp|gif)$", re.I)
SAVED_FROM_IDENTITY = re.compile(r"familysearch\.org/(?:[a-z]{2}/)?(?:ark:/\d+/[\w:.$-]+|search/record/results)"
                                  r"|findagrave\.com/memorial/(?:\d+(?:/|$)|search)"
                                  r"|aad\.archives\.gov/aad/(?:record-detail|display-partial-records)\.jsp", re.I)

def named_for(name, entries):
    """The waiting page a saved file's name was printed for: the name as the list printed it, whole (a page at a holder whose
    pages carry no identity is named for its citation and person, with nothing left to fill in)."""
    return next((e for e in entries if "<" not in e["save_as"] and e["save_as"].lower() == name.lower()), None)

def saved_from(path):
    """The page's own URL, from the line the browser wrote when the page saved itself (tools/save_page.js); None without one."""
    with open(path, "rb") as fh: head = fh.read(4000).decode("utf-8", errors="replace")
    m = re.search(r"<!-- saved from (\S+) -->", head)
    return m.group(1) if m else None

def collect(cx, tree_id, slug, by, folder=None):
    """Every page in the download folder (or the folder given) saved under a name the list printed: a gravestone photograph
    by its own name (it carries no identity in its bytes), and any .html file whose saved-from line (the browser's own
    comment, tools/save_page.js) is a FamilySearch record or search URL, a Find a Grave memorial or search, or an AAD
    record or search, moved to inbox/ under its own name and attached by that identity (tools/attach.py identity), whatever
    the name says. A page from a holder whose pages carry no identity the attach reads is taken by the by-name path
    instead, under the list's own name, and attached to the steps of the one citation and person the name carries, archived
    under that holder with its own URL as locator. A file with neither is left where it is.
    Returns (the names taken, the attach results)."""
    folder = folder or downloads_dir(); names, results = [], []
    entries = waiting(cx, tree_id)
    for f in sorted(os.listdir(folder)):
        path = os.path.join(folder, f)
        if PHOTO_NAME.fullmatch(f) or (f.lower().endswith(".html") and SAVED_FROM_IDENTITY.search(saved_from(path) or "")):
            shutil.move(path, os.path.join(inbox_dir(), f)); names.append(f); continue
        e = named_for(f, entries)
        if not e or not f.lower().endswith(".html"): continue
        shutil.move(os.path.join(folder, f), os.path.join(inbox_dir(), f))
        url = saved_from(os.path.join(inbox_dir(), f)) or e["url"]
        steps = [{**dict(r), "reason": "saved under the name the fetch list printed for this page"} for sid in e["step_ids"] for r in cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,))]
        r = {"file": f, "identity": f"page {url}", "steps": [(s["id"], cx.execute("SELECT display_name FROM person WHERE id=?", (s["person_id"],)).fetchone()[0], s["row_key"], s["reason"]) for s in steps], "left": None}
        r.update(attach(cx, tree_id, slug, f, steps, by, note=f"saved in the browser under the fetch list's name at {e['holder']}", kind="page", value=url)); results.append(r)
    return names + [r["file"] for r in results], (attach_inbox(cx, tree_id, slug, by, names) if names else []) + results

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["list", "collect"]); ap.add_argument("--json", action="store_true"); ap.add_argument("--tree")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument("--folder", help="collect: the folder to take saved pages from, instead of the browser's own download folder")
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
        try: names, results = collect(cx, tree_id, slug, a.by, folder=a.folder); cx.commit()
        except Exception: cx.rollback(); raise
        for r in results: print(line(r))
        if not names: print(f"nothing saved in {a.folder or downloads_dir()}")

if __name__ == "__main__": main()
