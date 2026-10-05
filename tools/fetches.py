#!/usr/bin/env python3
"""The pages waiting to be fetched by hand at every holder, and the pages that came back.

usage: tools/fetches.py next [K] [--tree slug] [--db catalog/tree.db]
       tools/fetches.py list [--all] [--json] [--tree slug] [--db catalog/tree.db]
       tools/fetches.py collect [--folder DIR] [--by user:<you>] [--tree slug] [--db catalog/tree.db]

Find a Grave forbids automation and FamilySearch answers a browser only, so a cited record at such a holder is saved one page
at a time in the owner's own browser by the page-saves-itself method (docs/RESEARCH-WORKFLOW.md §4, tools/save_page.js),
one tab per page; a gravestone photograph the same way in the image's own tab (tools/save_image.js), under the name the list
prints. `list` prints the planned fetch steps whose holder has no connector at all (a holder whose connector merely has
nothing to ask yet, a book cited with no title, runs through tools/run_step.py instead: a `none` run naming the field
wanted, off this list, left for a hand on the person's screen), once per page, with the holder, the
link to open (the memorial page itself; the holder's own search prefilled from the citation's details, a collection's own
search when no record id of the holder's is known yet; a row of a saved results page that fits the person is a lead of its
own, the row's record page, listed under the record-page name with the row's ark filled in), the people whose steps it
fulfils, and the file name to save under
(a FamilySearch record page's name takes the record's own ark id from its page; a FamilySearch or other holder's search
carries the search's own given name and surname, so the several people's steps one search serves share one name; a page
from any other holder carries no identity the attach reads, so it is listed once per citation and person waiting on it,
under a name that carries the citation's own record locator and ends in that person's six characters; two different links
that would take one name each carry six characters of their own link's digest, so no page is saved as another): the leads from
held records first (a persona accepted as a person, whose memorial the record links), then the file's citations, the pages
that settle most steps first. Saved pages go to the data root's own `downloads/` folder (the repository's `downloads/` for
the live tree; a scratch run's under its DATA_ROOT): the owner points the browser's download location there once, a separate
browser profile for tree work if they prefer, and no tool reads the owner's own download folder. `collect` moves every saved
page from that folder (or --folder) into `inbox/` (beside a file of the same name already there, under a free name, never
over it: treelib.move_free) and attaches each: a photograph by its own name (it carries no identity in its bytes), any other .html page whose
saved-from line (the browser's own comment, tools/save_page.js) is a FamilySearch record or search URL, a Find a Grave
memorial or search, or an AAD record or search, by that identity (tools/attach.py identity) whatever the name says —
archived once, logged found on every step that cites it, extracted, matched, the rule run; a page that carries a key (the
second comment tools/save_page.js writes when the browser ran it with the `call` the list printed: the plan steps the page was
saved for) reaches those steps first (tools/attach.py named_steps), each checked against the page's own identity, and the steps
its identity reaches beside them; a page from a holder whose
pages carry no identity the attach reads, by the name the list printed, to the steps of the one citation and person the
name carries, archived under that holder with the page's own URL (the saved-from line the browser wrote) as locator,
logged unread (held on the step's log, the step planned), and reported unparsed until a parser claims it. A file with neither a recognised saved-from line nor a
listed name is left in the folder. Each file is attached in a transaction of its own: one that fails is rolled back alone,
named with the exception, and left where it was (a page taken by name in the folder, a page taken by identity in the inbox),
the others attached.

`next [K]` is the browser session's own list: the next K pages (five by default) a turn can send someone to (`openable`: a
link to open, a step with no run since the plan last wrote its fields), one line each with the link, the file name to save
under, the people waiting in short and the `call` for the save script (the file name, whether to save a page of no known kind
anyway, and the key: the steps the page serves); `list` prints the same
`call` for every page. `list` hides the pages whose steps
have all been run on unchanged fields (a page saved, or answered, and the plan has not changed the step since) unless --all
brings them back. A step at a holder whose link takes nothing from the citation is planned assisted, a search a person runs
by hand (tools/plan.py), never a page on this list.
"""
import argparse, collections, hashlib, json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, downloads_dir, dumps, inbox_dir, move_free, resolve_tree
from attach import ark_id, attach, attach_each, failed, line
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

def distinct_names(entries):
    """The entries with no two different links told one name: where entries of different links would save under one name (a
    person's two searches of one census collection, one of them narrowed to a residence the other leaves open), each of them
    carries the first six characters of its own link's sha1 before the extension, so neither page is saved as the other; a name
    only one link has is left as save_as built it. Returns the entries."""
    links = collections.defaultdict(set)
    for e in entries: links[e["save_as"]].add(e["url"])
    for e in entries:
        if len(links[e["save_as"]]) < 2: continue
        stem, ext = os.path.splitext(e["save_as"])
        e["save_as"] = f"{stem}-{hashlib.sha1((e['url'] or '').encode()).hexdigest()[:6]}{ext}"
    return entries

def waiting(cx, tree_id):
    """Every planned fetch step whose holder has no connector, once per page: holder, url, the people and the number of
    steps waiting on it, whether it is a lead from a held record (locator memorial_id) or the file's citation (locator
    apid), the file name to save under (save_as, two different links never one name: distinct_names), and `serves`, the steps the saved page serves: those of every entry with this entry's link and file name
    (the page the browser saves is one, whatever census page or citation each entry stands for), the key page_call gives the save
    script. A step whose holder has a connector never appears here, whether or not that
    connector currently has anything to ask: it runs through tools/run_step.py, which logs a `none` run naming the field
    wanted when it has nothing to ask, so the step is answered on its fields and left for a hand on the person's screen, not
    the browser. Steps citing one census page (the household's record ids) are one page. A page at a holder whose pages carry
    no identity the attach reads (no memorial id, no ark) is one entry per citation and person waiting on it, named for both,
    so the saved file reaches that person's steps on that citation alone. A step whose locator is a record's own ark (a row of a
    results page that fits the person, tools/plan.py's result_row_leads, or a record the owner named) is that record's page,
    named with the ark filled in: the listing pointed at the record and is not one, so the record's page is the next to save.
    A step at a browse-only holder (catalog.browse_only:
    a FamilySearch images-only collection) never appears either: nobody can save such a page the page-saves-itself way,
    so it stays on the plan with its reason and off this list, never a name with an unfilled placeholder."""
    cat = Catalog(cx, tree_id); groups = cat.page_groups(); out = {}
    def add(s, key, link, holder, name):
        e = out.setdefault(key, {"holder_id": s["locator_source_id"], "holder": holder, "url": link, "lead": False, "people": [], "steps": 0, "step_ids": [], "rows": [],
                                 "save_as": name, "how": "image" if s["locator_source_id"] == "E05" else "page"})
        e["steps"] += 1; e["step_ids"].append(s["id"]); e["lead"] = e["lead"] or s["locator_kind"] in ("memorial_id", "url", "ark")
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
            page = piece = min(groups.get(s["locator_value"]) or {s["locator_value"]})
            key = (hid, page) if hid == "D03" else (hid, page, s["person_id"])      # a FamilySearch page carries its ark; any other page is named for its citation and person
            t = fetch_target(s["locator_value"], url, fields); link = t["url"]; holder = f"{s['holder_name']}: {t['holder']}" if t["holder"] else s["holder_name"]
        else:
            key = (hid, s["locator_value"]); link = url or None; holder = s["holder_name"]
        name = save_as(hid, fields, s["row_key"], mid, s["person_id"][-6:], piece, link)
        add(s, key, link, holder, name.replace("<ark id>", ark_id(s["locator_value"])).replace("-<year>", "") if s["locator_kind"] == "ark" else name)
    entries = distinct_names(list(out.values()))
    for e in entries: e["serves"] = [sid for o in entries if (o["url"], o["save_as"]) == (e["url"], e["save_as"]) for sid in o["step_ids"]]
    return sorted(entries, key=lambda e: (not e["lead"], e["holder"], -e["steps"], e["url"] or ""))

def annotated(cx, tree_id):
    """Every waiting page (`waiting`) with open_step_ids: the steps among its step_ids with no run at the step's own source
    (log_search.step_source: the holder, or the row's first source, what a page saved by hand is logged under) since the plan
    last wrote their fields (log_search.ran_unchanged, the reading the runner's own runnable steps use per source); a run of a
    row source's connector on the same step (an obituary step answered at the Archive's newspapers) does not stand for the
    holder's page. A page with no link has none open."""
    out = []
    for e in waiting(cx, tree_id):
        if not e["url"]: out.append({**e, "open_step_ids": []}); continue
        steps = [cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,)).fetchone() for sid in e["step_ids"]]
        out.append({**e, "open_step_ids": [st["id"] for st in steps if st and not ran_unchanged(cx, st, rendered_query(st["query_json"], st["revisions_json"]), step_source(st))]})
    return out

def openable(cx, tree_id):
    """The waiting pages a turn can send someone to: the entries with a link to open and a step still open (annotated). A page
    saved once and logged (found, none, blocked) on a step's unchanged fields is listed by `list --all` as still waiting, but
    that step does not send anyone to it again until the plan changes it; a page seven people's steps share is open for the
    people whose own step is still unrun."""
    return [e for e in annotated(cx, tree_id) if e["url"] and e["open_step_ids"]]

PHOTO_NAME = re.compile(r"findagrave-photo-\d+-\d+(?: \(\d+\))?\.(jpe?g|png|webp|gif)$", re.I)   # a second download of one name, Chrome's " (1)", is the same photograph
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
    """Every page in the data root's downloads folder (or the folder given) saved under a name the list printed: a gravestone
    photograph by its own name (it carries no identity in its bytes), and any .html file whose saved-from line (the browser's
    own comment, tools/save_page.js) is a FamilySearch record or search URL, a Find a Grave memorial or search, or an AAD
    record or search, moved to inbox/ under its own name and attached by that identity (tools/attach.py identity), whatever
    the name says, to the steps its key names first when it carries one (attach.named_steps). A file of the same name already
    in the inbox is never written over: the page takes a free name beside it (treelib.move_free), its result naming that
    name as `inbox_as` and keeping the name it was saved under as `file`. A page from a holder whose pages
    carry no identity the attach reads is taken by the by-name path
    instead, under the list's own name, and attached to the steps of the one citation and person the name carries, archived
    under that holder with its own URL as locator. A name is not an identity: at a holder whose pages carry their own
    (IDENTITY_HOLDERS) a file under the list's name with no saved-from line is not the page, whoever or whatever saved it,
    and is left where it is, as a file with neither is. The pages taken by name go first,
    then those taken by identity, each file in a transaction of its own (attach.attach_each): a file whose transaction fails
    is rolled back alone and named with the failure, a page taken by name put back in the folder it was saved in (only collect
    takes a page by its name), a page taken by identity left in the inbox (attach_inbox.py, and the next turn, take it again).
    Returns (the names the pages taken have in the inbox, the attach results)."""
    folder = folder or downloads_dir(); by_identity, results = [], []
    entries = waiting(cx, tree_id)
    for f in sorted(os.listdir(folder)):
        path = os.path.join(folder, f)
        if not os.path.isfile(path): continue
        if PHOTO_NAME.fullmatch(f) or (f.lower().endswith(".html") and SAVED_FROM_IDENTITY.search(saved_from(path) or "")): by_identity.append(f); continue
        e = named_for(f, entries)
        if not e or not f.lower().endswith(".html"): continue
        if e["holder_id"] in IDENTITY_HOLDERS: continue          # this holder's pages carry their own identity: a file under the list's name without it is not the page
        dst = move_free(path, inbox_dir()); taken = os.path.basename(dst)   # beside a file of the same name already in the inbox, never over it
        cx.execute("BEGIN")
        try:
            url = saved_from(dst) or e["url"]
            steps = [{**dict(r), "reason": "saved under the name the fetch list printed for this page"} for sid in e["step_ids"] for r in cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,))]
            r = {"file": f, "identity": f"page {url}", "steps": [(s["id"], cx.execute("SELECT display_name FROM person WHERE id=?", (s["person_id"],)).fetchone()[0], s["row_key"], s["reason"]) for s in steps], "left": None}
            r.update(attach(cx, tree_id, slug, taken, steps, by, note=f"saved in the browser under the fetch list's name at {e['holder']}", kind="page", value=url)); cx.commit()
            if taken != f: r["inbox_as"] = taken
        except Exception as ex:
            cx.rollback()
            back = move_free(dst, folder, f) if os.path.exists(dst) else path   # the attach files the original last, so a failure before that leaves it in the inbox to put back
            r = failed(os.path.basename(back), ex, folder)
        results.append(r)
    inbox = {}                                                   # the name each page taken by identity has in the inbox -> the name it was saved under
    for f in by_identity: inbox[os.path.basename(move_free(os.path.join(folder, f), inbox_dir()))] = f
    attached = attach_each(cx, tree_id, slug, by, list(inbox))
    for r in attached:
        if inbox.get(r["file"], r["file"]) != r["file"]: r["inbox_as"], r["file"] = r["file"], inbox[r["file"]]
    return list(inbox) + [r.get("inbox_as") or r["file"] for r in results], attached + results

def people_short(names, n=2): return ", ".join(names[:n]) + (f" +{len(names) - n}" if len(names) > n else "")

IDENTITY_HOLDERS = ("D03", "E01", "F01")   # FamilySearch, Find a Grave, AAD: pages save_page.js knows by their own markup; any other holder's page is saved with true

def page_call(e):
    """The call the browser runs tools/save_page.js with for a page, in place of the ("FILENAME.html") that ends the script: the file name
    to save under; true at a holder whose pages the script knows by no markup of its own, so it saves the page anyway; and the key, the
    plan steps the page serves (the entry's own and those of every entry with the same link and name), which the script writes under the
    saved-from line so that collect reaches those steps first (attach.named_steps)."""
    return f'("{e["save_as"]}", {"false" if e["holder_id"] in IDENTITY_HOLDERS else "true"}, "{",".join(e["serves"])}")'

def page_line(e):
    """A page to save as one compact line: the link, the file name to save under, the people waiting in short, an image marked,
    and the call the save script runs with (page_call; an image carries none: its name is its identity)."""
    return f"{e['url']}  {e['save_as']}  {people_short(e['people'])}" + ("  [image: tools/save_image.js]" if e["how"] == "image" else "") \
        + ("  [any page: save_page.js with true]" if e["how"] != "image" and e["holder_id"] not in IDENTITY_HOLDERS else "") + (f"  call {page_call(e)}" if e["how"] != "image" else "")

def next_lines(cx, tree_id, k):
    """The next k openable pages, a line each (page_line), and the count."""
    rows = openable(cx, tree_id)
    return [page_line(e) for e in rows[:k]] + [f"{min(k, len(rows))} of {len(rows)} openable page(s); one tab each, then tools/fetches.py collect"] if rows else ["no page waiting that a turn can open"]

def main():
    ap = argparse.ArgumentParser(description="The pages waiting to be saved by hand, and collect: the pages saved in the data root's downloads/ folder (the browser's "
                                             "download location, set once), or --folder, taken into inbox/ and attached; the owner's own download folder is never read.")
    ap.add_argument("cmd", choices=["next", "list", "collect"]); ap.add_argument("count", nargs="?", type=int, default=5, help="next: how many pages")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--all", action="store_true", help="list: the pages already run on unchanged fields too"); ap.add_argument("--tree")
    ap.add_argument("--db", default=DB); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument("--folder", help="collect: the folder to take saved pages from, instead of the data root's downloads/ folder (the browser's download location, set once)")
    a = ap.parse_args()
    cx = connect(a.db, rows=True)
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.cmd == "next": print("\n".join(next_lines(cx, tree_id, a.count)))
    elif a.cmd == "list":
        every = annotated(cx, tree_id); rows = every if a.all else [e for e in every if e["open_step_ids"] or not e["url"]]
        if a.json: print(dumps(rows)); return
        last = None
        for e in rows:
            if e["holder"] != last: print(f"-- {e['holder']}"); last = e["holder"]
            print(f"{'lead ' if e['lead'] else 'cited'} {e['url']}  {', '.join(e['people'])}  ({e['steps']} step{'s' if e['steps'] > 1 else ''}: {', '.join(e['rows'])})  save as {e['save_as']}" + ("  (an image: tools/save_image.js in its own tab)" if e["how"] == "image" else "")
                  + ("  [already run on unchanged fields]" if a.all and e["url"] and not e["open_step_ids"] else "")
                  + (f"  call {page_call(e)}" if e["url"] and e["how"] != "image" else ""))
        print(f"{len(rows)} page(s) to fetch, one tab per page; then tools/fetches.py collect" + (f" ({len(every) - len(rows)} already run on unchanged fields, hidden: --all)" if len(every) > len(rows) else ""))
    else:
        names, results = collect(cx, tree_id, slug, a.by, folder=a.folder)
        for r in results: print(line(r))
        if not names: print(f"nothing saved in {a.folder or downloads_dir()}")

if __name__ == "__main__": main()
