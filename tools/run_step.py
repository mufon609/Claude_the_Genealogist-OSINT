#!/usr/bin/env python3
"""Run a step through a connector: a search step whose mode is auto, or a fetch step whose holder has a connector.

usage: tools/run_step.py <step id> [--dry-run] [--db catalog/tree.db] [--tree slug] [--by agent:run_step]
       tools/run_step.py --all [--dry-run] ...

A search step's fields, after the person's include and revise, become the connector's requests (tools/connectors/); a fetch
step's are the citation's own details (the name the citation sits on, the census place, the enumeration district), and a
page found is logged found on every household member's step that cites the same page. Every
request goes out with treelib.USER_AGENT at the source's documented rate; every response is archived as it came, a JSON
artifact whose locator is the request URL and whose source is the registry row; each hit's own transcription, text or
image is fetched and archived the same way with what the response said about it in the manifest notes. One search_log
row records the exact query, the outcome (found when a hit was archived, none when the source answered with nothing,
error when it did not answer), how many results the source said it had, and every artifact hash; found marks the step
done. Then the extractor runs on each hit's own transcription or text (the search response is the query's evidence, not
a record) and the matcher on each extraction; a record no extractor claims is reported as unparsed.
A step whose sources have several connectors runs at each, one log row per source. A fetched response may name more to
fetch (an item's metadata, then the search inside it, then its pages: connector.follow).
--all runs every planned step a connector can take, in plan order, keeping each connector's pace across steps.
--dry-run prints the requests and sends nothing.
"""
import argparse, json, os, sqlite3, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, USER_AGENT, archive_object, dumps, now, resolve_tree, ulid
from catalog import Catalog
from log_search import log as log_search, rendered_query
from extract import extract
from conclude import match_record
import connectors

LAST = {}                                                        # (connector, kind) -> time of the last request, for pacing

def fetch(url, kind, conn):
    """GET with the tool's user agent, no sooner than the connector's rate for this kind of request allows."""
    wait = 60.0 / max(conn.RATE.get(kind, 60), 1); k = (conn.__name__, kind)
    if k in LAST and time.monotonic() - LAST[k] < wait: time.sleep(wait - (time.monotonic() - LAST[k]))
    LAST[k] = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, image/jpeg, text/plain;q=0.9, */*;q=0.5"})
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
    """The planned steps the runner can take: auto search steps, and fetch steps whose holder has a connector."""
    with_conn = [sid for sid, s in cat.sources.items() if s.get("connector")]
    return cx.execute(f"""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.status='planned'
                          AND ((sp.kind='search' AND sp.mode='auto') OR (sp.kind='fetch' AND sp.mode='fetch' AND sp.locator_source_id IN ({','.join('?'*len(with_conn)) or "''"})))
                          ORDER BY p.display_name, sp.seq""", (tree_id, *with_conn)).fetchall()

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
    reqs = conn.requests(query)
    if dry_run: return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": reqs}
    if not reqs: return {"connector": conn.__name__.split(".")[-1], "error": "the fields give the connector nothing to ask; a surname is needed"}
    src = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id=?", (conn.SOURCE,)).fetchone()
    tier, terms, cost = (src or (None, None, None))
    cost = next((c for c in ("free", "paid", "member") if (cost or "").strip().lower().startswith(c)), "unknown")
    cid = collection_for(cx, conn); shas, records, hits, errors, totals = [], [], [], [], []
    def keep(data, http, kind, url, notes, label=None):
        mime = (http.get("content_type") or "").split(";")[0].strip() or {"json": "application/json", "text": "text/plain", "image": "image/jpeg"}[kind]
        if kind in ("json", "search", "text") and mime.startswith("text/html"): mime = "application/json" if data[:1] in (b"{", b"[") else mime
        sha, _ = archive_object(cx, data, mime=mime, source_id=conn.SOURCE, collection_id=cid, collection_name=conn.COLLECTION, locator_kind="url", locator_value=url,
                                retrieved_by=by, terms=terms, cost=cost, trust_tier=tier, notes=dumps(notes) if notes else (label or ""), http=http)
        if sha not in shas: shas.append(sha)
        return sha
    def hits_of_page(h):
        got, todo = [], list(h["fetch"])
        while todo:                                              # a fetched response may name more to fetch (connector.follow)
            f = todo.pop(0)
            try: d2, h2 = fetch(f["url"], f["kind"], conn)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e: errors.append(f"{f['url']}: {e}"); continue
            if hasattr(conn, "follow"):                          # first, so what the response taught (the pages chosen) is in this artifact's notes
                try: todo += conn.follow(f, d2, h)
                except ValueError as e: errors.append(f"{f['url']}: {e}")
            got.append(keep(d2, h2, f["kind"], f["url"], {**h["notes"], "hit": h["label"], "locator": h["locator"], **({"page_number": f["page"]} if f.get("page") else {})}))
            if f["kind"] != "image" and f.get("record", True): records.append(got[-1])
        hits.append({"label": h["label"], "locator": h["locator"], "artifacts": got})
    asked = []                                                   # what a source with too many results needs on the step (connector.narrow)
    for rq in reqs:
        url = rq["url"]
        while url:                                               # a search pages on while the connector says the total stays small (connector.next_page)
            try: data, http = fetch(url, rq["kind"], conn)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e: errors.append(f"{url}: {e}"); break
            keep(data, http, rq["kind"], url, {"request": rq["kind"], "query": query})
            if url == rq["url"]:
                try: totals.append(conn.total(data))
                except ValueError: totals.append(None)
                try: asked.append(conn.narrow(url, data) if hasattr(conn, "narrow") else None)
                except ValueError: pass
            page_hits = conn.hits(url, data, rq) if conn.hits.__code__.co_argcount > 2 else conn.hits(url, data)
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
