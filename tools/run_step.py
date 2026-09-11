#!/usr/bin/env python3
"""Run a step through a connector: a search step whose mode is auto, or a fetch step whose holder has a connector.

usage: tools/run_step.py <step id> [--dry-run] [--db catalog/tree.db] [--tree slug] [--by agent:run_step]
       tools/run_step.py --all [--dry-run] ...

A search step's fields, after the person's include and revise, become the connector's requests (tools/connectors/); a fetch
step's are the citation's own details (the name the citation sits on, the census place, the enumeration district, a book's
title), and a page found is logged found on every household member's step that cites the same page. Every
request goes out with treelib.USER_AGENT at the source's documented rate, posted as a form when the connector gives it form
data; every response is archived as it came, an artifact whose locator is the request URL (or the identity the connector
names for a posted search) and whose source is the registry row; each hit's own transcription, text or
image is fetched and archived the same way with what the response said about it in the manifest notes, and a search
response the connector marks as the record itself is read as one. One search_log
row records the exact query, the outcome (found when a hit was archived, none when the source answered with nothing,
error when it did not answer), how many results the source said it had, and every artifact hash; found marks the step
done. Then the extractor runs on each hit's own transcription or text (the search response is the query's evidence, not
a record) and the matcher on each extraction; a record no extractor claims is reported as unparsed.
A step whose sources have several connectors runs at each, one log row per source. A fetched response may name more to
fetch (an item's metadata, then the search inside it, then its pages: connector.follow). A source's years, from the
registry's coverage column (1756-1963, 1780s-1990s, 1950), gate its steps: a step whose years fall wholly outside them (an
obituary for a death after the newspapers end) is logged none without a request, the note saying so.
--all runs every planned step a connector can take, in plan order, keeping each connector's pace across steps.
--dry-run prints the requests and sends nothing.
"""
import argparse, http.client, json, os, re, sqlite3, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, USER_AGENT, archive_object, dumps, now, resolve_tree, ulid
from catalog import Catalog
from log_search import log as log_search, rendered_query
from extract import extract
from conclude import match_record
import connectors

LAST = {}                                                        # (connector, kind) -> time of the last request, for pacing
YEARS = re.compile(r"\b(1[5-9]\d\d|20\d\d)(s)?\b")

def coverage_years(text):
    """(first year, last year) the registry's coverage text names, or None when it names no year: "US 1756-1963" is 1756 to 1963,
    "US 1780s-1990s" 1780 to 1999 (a decade runs to its last year), "US 1950" 1950 alone, "Global" nothing."""
    ys = [(int(y), bool(s)) for y, s in YEARS.findall(text or "")]
    if not ys: return None
    lo = min(y for y, _ in ys); hi, dec = max(ys, key=lambda t: t[0])
    return lo, hi + 9 if dec else hi

def step_years(query_type, fields):
    """The years a step asks about, from its rendered fields: an obituary or probate step the death year and the year after; a
    household step its census year; any other step the person's lifetime from the birth year (to the death year, or a hundred
    years). None when the fields name no year, so the source's years do not gate it."""
    v = lambda k: connectors.value(fields, k)
    death, birth, year = v("death_year"), v("birth_year"), v("year")
    if query_type in ("obituary", "probate") and death: return int(death), int(death) + 1
    if query_type == "household" and str(year or "").isdigit(): return int(year), int(year)
    if birth: return int(birth), int(death) if death else int(birth) + 100
    return None

def outside(cat, conn, query_type, fields):
    """Why the step is not asked at this source, or None: the source's years and the step's do not overlap."""
    src = coverage_years((cat.sources.get(conn.SOURCE) or {}).get("coverage")); st = step_years(query_type, fields)
    if not src or not st or (st[0] <= src[1] and st[1] >= src[0]): return None
    return f"the source covers {src[0]}-{src[1]} and the step asks about {st[0]}" + (f"-{st[1]}" if st[1] != st[0] else "") + ": not asked"

def fetch(url, kind, conn, data=None):
    """GET, or POST when form data is given, with the tool's user agent, no sooner than the connector's rate for this kind of
    request allows."""
    wait = 60.0 / max(conn.RATE.get(kind, 60), 1); k = (conn.__name__, kind)
    if k in LAST and time.monotonic() - LAST[k] < wait: time.sleep(wait - (time.monotonic() - LAST[k]))
    LAST[k] = time.monotonic()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, image/jpeg, text/plain;q=0.9, */*;q=0.5"}
    if data: headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), {"status": r.status, "etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified"), "final_url": r.url,
                          "content_type": r.headers.get("Content-Type")}

def collection_for(cx, conn):
    row = cx.execute("SELECT id FROM collection WHERE source_id=? AND name=?", (conn.SOURCE, conn.COLLECTION)).fetchone()
    if row: return row[0]
    cid = ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, conn.SOURCE, conn.COLLECTION, "other", conn.__name__.split(".")[-1]))
    return cid

def connectors_for(cat, step):
    """A search step's connectors are those of its sources that have one, in the row's order; a fetch step's is its holder's
    (the locator source). Each is a query at a different holder and gets its own log row."""
    sids = [step["locator_source_id"]] if step["kind"] == "fetch" else json.loads(step["sources_json"] or "[]")
    out = []
    for sid in sids:
        name = (cat.sources.get(sid) or {}).get("connector")
        if name: out.append(connectors.load(name))
    return out

def connector_for(cat, step):
    conns = connectors_for(cat, step); return conns[0] if conns else None

def runnable(cx, cat, tree_id):
    """The planned steps the runner can take: auto search steps, and fetch steps whose holder has a connector that can ask
    for the record from the citation's details (a book citation that names no title gives the books connector nothing to ask;
    that step stays a link for a hand)."""
    with_conn = [sid for sid, s in cat.sources.items() if s.get("connector")]
    rows = cx.execute(f"""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.status='planned'
                          AND ((sp.kind='search' AND sp.mode='auto') OR (sp.kind='fetch' AND sp.mode='fetch' AND sp.locator_source_id IN ({','.join('?'*len(with_conn)) or "''"})))
                          ORDER BY p.display_name, sp.seq""", (tree_id, *with_conn)).fetchall()
    return [r for r in rows if r["kind"] == "search" or any(c.requests(rendered_query(r["query_json"], r["revisions_json"])) for c in connectors_for(cat, r))]

def household_steps(cx, tree_id, step):
    """The other fetch steps at the same holder whose citations name the same census page (year, enumeration district, census
    place and page): every household member cited on it. A page fetched once is held for all of them."""
    q = json.loads(step["query_json"] or "{}"); v = lambda d, k: ((d.get(k) or {}).get("value") or "").strip().lower()
    if not v(q, "enumeration district"): return []
    rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.id<>?
                         AND sp.locator_source_id=? AND sp.status='planned'""", (tree_id, step["id"], step["locator_source_id"])).fetchall()
    return [r for r in rows if all(v(json.loads(r["query_json"] or "{}"), k) == v(q, k) for k in ("year", "enumeration district", "census place", "page"))]

def run(cx, cat, tree_id, step, by, dry_run=False):
    """One step through every connector its sources have: one run each (run_connector), then extraction and matching over
    every record any of them archived. Returns one result per connector."""
    conns = connectors_for(cat, step)
    if not conns: return [{"error": "no source of this step has a connector"}]
    out = []
    for conn in conns:
        r = run_connector(cx, cat, tree_id, step, conn, by, dry_run)
        if dry_run or "error" in r: out.append(r); continue
        extracted = []
        for sha in r.pop("records"):                             # a hit's own record; the search response is the query's evidence, not a record
            eid, n = extract(cx, sha, by)
            if "failed" in n: extracted.append({"sha256": sha, "unparsed": n["failed"]}); continue
            props, taken = match_record(cx, eid, by)
            extracted.append({"sha256": sha, "extraction": eid, **{k: v for k, v in n.items() if k != "place_strings"}, "proposals": len(props), "accepted_by_rule": len(taken)})
        out.append({**r, "extracted": extracted})
    return out

def run_connector(cx, cat, tree_id, step, conn, by, dry_run=False):
    """One step at one connector: requests, responses archived, hits fetched and archived, the log row under the connector's
    source. Returns the run with the records archived, to be read afterwards."""
    query = rendered_query(step["query_json"], step["revisions_json"])
    reqs = conn.requests(query); gate = outside(cat, conn, step["query_type"], query)
    if dry_run: return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": reqs, **({"outside": gate} if gate else {})}
    if not reqs: return {"connector": conn.__name__.split(".")[-1], "error": "the fields give the connector nothing to ask: a surname, or for a cited book its title"}
    if gate:                                                     # the source's years miss the step's: a none run with the reason, no request
        lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome="none", artifacts=None, note=gate, query=query)
        return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": [], "outcome": "none", "log": lid, "artifacts": [], "hits": [], "errors": [], "household_steps": [], "records": [], "outside": gate}
    src = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id=?", (conn.SOURCE,)).fetchone()
    tier, terms, cost = (src or (None, None, None))
    cost = next((c for c in ("free", "paid", "member") if (cost or "").strip().lower().startswith(c)), "unknown")
    cid = collection_for(cx, conn); shas, records, hits, errors, totals = [], [], [], [], []
    def keep(data, http, kind, url, notes, label=None, locator=None):
        mime = (http.get("content_type") or "").split(";")[0].strip() or {"json": "application/json", "text": "text/plain", "image": "image/jpeg"}[kind]
        if kind in ("json", "search", "text") and mime.startswith("text/html"): mime = "application/json" if data[:1] in (b"{", b"[") else mime
        sha, _ = archive_object(cx, data, mime=mime, source_id=conn.SOURCE, collection_id=cid, collection_name=conn.COLLECTION, locator_kind="url", locator_value=locator or url,
                                retrieved_by=by, terms=terms, cost=cost, trust_tier=tier, notes=dumps(notes) if notes else (label or ""), http=http)
        if sha not in shas: shas.append(sha)
        return sha
    def hits_of_page(h):
        got, todo = [], list(h["fetch"])
        while todo:                                              # a fetched response may name more to fetch (connector.follow)
            f = todo.pop(0)
            try: d2, h2 = fetch(f["url"], f["kind"], conn)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, http.client.HTTPException) as e: errors.append(f"{f['url']}: {e}"); continue
            if hasattr(conn, "follow"):                          # first, so what the response taught (the pages chosen) is in this artifact's notes
                try: todo += conn.follow(f, d2, h)
                except ValueError as e: errors.append(f"{f['url']}: {e}")
            got.append(keep(d2, h2, f["kind"], f["url"], {**h["notes"], "hit": h["label"], "locator": h["locator"], "step_type": step["query_type"], "connector": conn.__name__.split(".")[-1], **({"page_number": f["page"]} if f.get("page") else {})}))   # the step's kind and the connector on the response itself, so it reads the same on its own
            if f["kind"] != "image" and f.get("record", True): records.append(got[-1])
        hits.append({"label": h["label"], "locator": h["locator"], "artifacts": got})
    asked = []                                                   # what a source with too many results needs on the step (connector.narrow)
    for rq in reqs:
        url = rq["url"]; pages = 1
        while url:                                               # a search pages on while the connector says the total stays small (connector.next_page)
            first = url == rq["url"]                             # the request as the connector gave it; a later page is a GET of the URL the connector named
            try: data, http = fetch(url, rq["kind"], conn, rq.get("data") if first else None)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, http.client.HTTPException) as e: errors.append(f"{url}: {e}"); break
            sha = keep(data, http, rq["kind"], url, {"request": rq["kind"], "query": query}, locator=(rq.get("locator") if first else f"{rq['locator']}&page={pages}") if rq.get("locator") else None)
            if url == rq["url"]:
                try: totals.append(conn.total(data))
                except ValueError: totals.append(None)
                try: asked.append(conn.narrow(url, data) if hasattr(conn, "narrow") else None)
                except ValueError: pass
            page_hits = conn.hits(url, data, rq) if conn.hits.__code__.co_argcount > 2 else conn.hits(url, data)
            if rq.get("record") and page_hits: records.append(sha)   # the response is the record itself (a results page listing what was found); an empty answer is not a record
            pages += 1
            try: url = conn.next_page(url, data) if hasattr(conn, "next_page") and rq["kind"] == "search" else None
            except ValueError: url = None
            for h in page_hits:
                hits_of_page(h)
    outcome = "found" if hits else ("error" if errors and not shas else "none")
    answered = "; ".join(f"the source answered with {t} result(s)" for t in totals if t is not None)
    note = "; ".join(x for x in [answered] + [a for a in asked if a] + [h["label"] for h in hits] + errors if x)[:1000] or None

    lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome=outcome, artifacts=shas or None, note=note, query=query)
    household = []
    if step["kind"] == "fetch" and outcome == "found":              # the page is held for every household member cited on it
        for other in household_steps(cx, tree_id, step):
            log_search(cx, tree_id, by, step_id=other["id"], outcome="found", artifacts=shas, note=f"the same page, fetched for {cx.execute('SELECT display_name FROM person WHERE id=?', (step['person_id'],)).fetchone()[0]}",
                       query=rendered_query(other["query_json"], other["revisions_json"])); household.append(other["id"])
    return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": [r["url"] for r in reqs], "outcome": outcome, "log": lid, "artifacts": shas, "hits": hits,
            "errors": errors, "household_steps": household, "records": records}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("step", nargs="?"); ap.add_argument("--all", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--tree"); ap.add_argument("--by", default="agent:run_step")
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    if a.all: steps = runnable(cx, cat, tree_id)
    else:
        if not a.step: sys.exit("give a step id or --all")
        st = cx.execute("SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (a.step, tree_id)).fetchone()
        if not st: sys.exit(f"no step {a.step} in tree {slug}")
        if connector_for(cat, st) is None or st["status"] != "planned": sys.exit(f"step {a.step} is {st['kind']}/{st['mode']}/{st['status']}: no connector runs it")
        steps = [st]
    for st in steps:
        who = cx.execute("SELECT display_name FROM person WHERE id=?", (st["person_id"],)).fetchone()[0]
        if a.dry_run: print(who, st["id"], st["row_key"], dumps(run(cx, cat, tree_id, st, a.by, dry_run=True))); continue
        cx.execute("BEGIN")
        try: res = run(cx, cat, tree_id, st, a.by); cx.commit()
        except Exception: cx.rollback(); raise
        print(who, st["id"], st["row_key"])
        for r in res: print("  ", dumps(r))

if __name__ == "__main__": main()
