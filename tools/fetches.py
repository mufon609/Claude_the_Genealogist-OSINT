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
a page from any other holder carries no identity the attach reads and the citation no record id of the holder's, so it is
listed once per person waiting on it, under a name that ends in that person's six characters, with the year filled in):
the leads from held records first (a persona accepted as a person, whose memorial the record links), then the file's
citations, the pages that settle most steps first. `collect` moves every saved page from the browser's download folder
into `inbox/` and attaches each: a memorial, a FamilySearch record, an AAD record or a photograph by its own identity
(tools/attach.py), archived once, logged found on every step that cites it, extracted, matched, the rule run; a page
from any other holder by the name the list printed, to the steps of the one person the name ends in, archived under that
holder with the page's own URL (the saved-from line the browser wrote) as locator, logged found, and reported unparsed
until a parser claims it.
"""
import argparse, json, os, re, shutil, sqlite3, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, inbox_dir, resolve_tree
from attach import attach, attach_inbox, line
from catalog import Catalog, fetch_target
from log_search import ran_unchanged, rendered_query
import connectors

MEMORIAL = re.compile(r"/memorial/(\d+)(?:/|$)")

def _slug(text): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").lower())).strip("-")

def save_as(holder_id, fields, row_key, mid=None, six=None):
    """The file name a saved page takes, in the shape tools/fetches.py collect recognises: findagrave-memorial-<id>.html for a
    memorial; familysearch-<collection words>-<year>-<ark id>.html for a FamilySearch record page, the year from the citation
    or the row, the ark id read off the record page (the part after ark:/61903/1:1:); <holder>-<collection words>-<year>-<six>.html
    for a page at any other holder, six being the six characters of the person the page is saved for (the listing's own way of
    naming one person), since such a page carries no identity the attach reads and the citation no record id of the holder's:
    the six characters are what keeps two people's pages of one collection apart."""
    if holder_id == "E01" and mid: return f"findagrave-memorial-{mid}.html"
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if holder_id == "E05": return f"findagrave-photo-{v('memorial')}-{v('photo')}" + (os.path.splitext((v("url") or "").split("?")[0])[1].lower() or ".jpg")
    coll = v("collection") or ""
    words = "census" if re.search(r"census", coll, re.I) else _slug(re.sub(r"[\d\u2013-]+|U\.S\.", " ", coll))[:40] or "record"
    inst = row_key.split(":", 1)[1] if ":" in row_key else ""
    year = v("year") or (inst if inst.isdigit() else None) or "<year>"
    return f"familysearch-{words}-{year}-<ark id>.html" if holder_id == "D03" else f"{_slug(holder_id)}-{words}-{year}-{six}.html"

def waiting(cx, tree_id):
    """Every planned fetch step whose holder has no connector, or whose connector has nothing to ask from the citation, once per
    page: holder, url, the people and the number of steps waiting on it, whether it is a lead from a held record (locator
    memorial_id) or the file's citation (locator apid), and the file name to save under. Steps citing one census page (the
    household's record ids) are one page. A page at a holder whose pages carry no identity the attach reads (no memorial id,
    no ark) is one entry per person waiting on it, named for that person, so the saved file reaches that person's steps alone."""
    cat = Catalog(cx, tree_id); groups = cat.page_groups(); out = {}
    for s in cx.execute("""SELECT sp.id, sp.person_id, sp.locator_source_id, sp.locator_kind, sp.locator_value, sp.query_json, sp.revisions_json, sp.row_key, p.display_name,
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
            page = min(groups.get(s["locator_value"]) or {s["locator_value"]})
            key = (hid, page) if hid == "D03" else (hid, page, s["person_id"])      # a FamilySearch page carries its ark; any other page is named for its person
            t = fetch_target(s["locator_value"], url, fields); link = t["url"]; holder = f"{s['holder_name']}: {t['holder']}" if t["holder"] else s["holder_name"]
        else:
            key = (hid, s["locator_value"]); link = url or None; holder = s["holder_name"]
        e = out.setdefault(key, {"holder_id": hid, "holder": holder, "url": link, "lead": False, "people": [], "steps": 0, "step_ids": [], "rows": [],
                                 "save_as": save_as(hid, fields, s["row_key"], mid, s["person_id"][-6:]), "how": "image" if hid == "E05" else "page"})
        e["steps"] += 1; e["step_ids"].append(s["id"]); e["lead"] = e["lead"] or s["locator_kind"] in ("memorial_id", "url")
        if s["display_name"] not in e["people"]: e["people"].append(s["display_name"])
        rk = s["row_key"].split(":")[0]
        if rk not in e["rows"]: e["rows"].append(rk)
    return sorted(out.values(), key=lambda e: (not e["lead"], e["holder"], -e["steps"], e["url"] or ""))

def openable(cx, tree_id):
    """The waiting pages a turn can send someone to: entries with a link to open, each with open_step_ids, the steps among its
    step_ids with no run since the plan last wrote their fields (log_search.ran_unchanged); an entry with none is left out. A
    page saved once and logged (found, none, blocked) on a step's unchanged fields is listed by `list` as still waiting, but
    that step does not send anyone to it again until the plan changes it; a page seven people's steps share is open for the
    people whose own step is still unrun."""
    out = []
    for e in waiting(cx, tree_id):
        if not e["url"]: continue
        steps = [cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,)).fetchone() for sid in e["step_ids"]]
        open_ids = [st["id"] for st in steps if st and not ran_unchanged(cx, st, rendered_query(st["query_json"], st["revisions_json"]))]
        if open_ids: out.append({**e, "open_step_ids": open_ids})
    return out

def downloads_dir():
    try: return subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=5).stdout.strip() or os.path.expanduser("~/Downloads")
    except Exception: return os.path.expanduser("~/Downloads")

IDENTIFIED = re.compile(r"(findagrave-memorial-\d+|familysearch-[a-z0-9-]+-\d+-[A-Za-z0-9_:-]+|aad-enlistment-[A-Za-z0-9_-]+)\.html|findagrave-photo-\d+-\d+\.(jpe?g|png|webp|gif)", re.I)

def named_for(name, entries):
    """The waiting page a saved file's name was printed for: the list's name with its year filled in (and, for a FamilySearch
    page, its ark id); the six characters that end any other holder's name are the person's and are matched as printed."""
    fill = {"<year>": r"[^-]+", "<ark id>": r"[A-Za-z0-9_:-]+"}
    for e in entries:
        rx = "".join(fill.get(part, re.escape(part)) for part in re.split(r"(<year>|<ark id>)", e["save_as"]))
        if re.fullmatch(rx, name, re.I): return e
    return None

def saved_from(path):
    """The page's own URL, from the line the browser wrote when the page saved itself (tools/save_page.js); None without one."""
    with open(path, "rb") as fh: head = fh.read(4000).decode("utf-8", errors="replace")
    m = re.search(r"<!-- saved from (\S+) -->", head)
    return m.group(1) if m else None

def collect(cx, tree_id, slug, by, folder=None):
    """Every page in the download folder (or the folder given) saved under a name the list printed: a memorial, a FamilySearch
    record, an AAD record or a gravestone photograph moved to inbox/ and attached by its own identity (a photograph's is in
    its name); a page from any other holder, saved under the list's name with its year filled in, moved to inbox/ and
    attached to the steps of the one person whose six characters end the name, archived under that holder with its own URL
    as locator.
    Returns (the names taken, the attach results)."""
    folder = folder or downloads_dir(); names, results = [], []
    entries = waiting(cx, tree_id)
    for f in sorted(os.listdir(folder)):
        if IDENTIFIED.fullmatch(f):
            shutil.move(os.path.join(folder, f), os.path.join(inbox_dir(), f)); names.append(f); continue
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
