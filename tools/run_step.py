#!/usr/bin/env python3
"""Run a search step whose mode is auto against its source's connector.

usage: tools/run_step.py <step id> [--dry-run] [--db catalog/tree.db] [--tree slug] [--by agent:run_step]
       tools/run_step.py --all [--dry-run] ...

The step's fields, after the person's include and revise, become the connector's requests (tools/connectors/). Every
request goes out with treelib.USER_AGENT at the source's documented rate; every response is archived as it came, a JSON
artifact whose locator is the request URL and whose source is the registry row; each hit's own transcription, text or
image is fetched and archived the same way with what the response said about it in the manifest notes. One search_log
row records the exact query, the outcome (found when a hit was archived, none when the source answered with nothing,
error when it did not answer), how many results the source said it had, and every artifact hash; found marks the step
done. Then the extractor runs on each hit's own transcription or text (the search response is the query's evidence, not
a record) and the matcher on each extraction; a record no extractor claims is reported as unparsed.
--all runs every planned auto step of the active tree in plan order, keeping each connector's pace across steps.
--dry-run prints the requests and sends nothing.
"""
import argparse, json, os, sqlite3, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, USER_AGENT, archive_object, dumps, now, resolve_tree, ulid
from catalog import Catalog
from log_search import log as log_search, rendered_query
from extract import extract
from match import match
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

def connector_for(cat, step):
    for sid in json.loads(step["sources_json"] or "[]"):
        name = (cat.sources.get(sid) or {}).get("connector")
        if name: return connectors.load(name)
    return None

def run(cx, cat, tree_id, step, by, dry_run=False):
    """One step: requests, responses archived, hits fetched and archived, the log row, extraction and matching."""
    conn = connector_for(cat, step)
    if conn is None: return {"error": "no source of this step has a connector"}
    query = rendered_query(step["query_json"], step["revisions_json"])
    reqs = conn.requests(query)
    if dry_run: return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": reqs}
    if not reqs: return {"error": "the fields give the connector nothing to ask; a surname is needed"}
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
    for rq in reqs:
        try: data, http = fetch(rq["url"], rq["kind"], conn)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e: errors.append(f"{rq['url']}: {e}"); continue
        keep(data, http, rq["kind"], rq["url"], {"request": rq["kind"], "query": query})
        try: totals.append(conn.total(data))
        except ValueError: totals.append(None)
        for h in conn.hits(rq["url"], data):
            got = []
            for f in h["fetch"]:
                try: d2, h2 = fetch(f["url"], f["kind"], conn)
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e: errors.append(f"{f['url']}: {e}"); continue
                got.append(keep(d2, h2, f["kind"], f["url"], {**h["notes"], "hit": h["label"], "locator": h["locator"]}))
                if f["kind"] != "image": records.append(got[-1])
            hits.append({"label": h["label"], "locator": h["locator"], "artifacts": got})
    outcome = "found" if hits else ("error" if errors and not shas else "none")
    answered = "; ".join(f"the source answered with {t} result(s)" for t in totals if t is not None)
    note = "; ".join(x for x in [answered] + [h["label"] for h in hits] + errors if x)[:1000] or None
    lid = log_search(cx, tree_id, by, step_id=step["id"], outcome=outcome, artifacts=shas or None, note=note, query=query)
    extracted = []
    for sha in records:                                          # a hit's own record; the search response is the query's evidence, not a record
        eid, n = extract(cx, sha, by)
        if "failed" in n: extracted.append({"sha256": sha, "unparsed": n["failed"]}); continue
        props = match(cx, eid, by)
        extracted.append({"sha256": sha, "extraction": eid, **{k: v for k, v in n.items() if k != "place_strings"}, "proposals": len(props)})
    return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": [r["url"] for r in reqs], "outcome": outcome, "log": lid, "artifacts": shas, "hits": hits,
            "errors": errors, "extracted": extracted}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("step", nargs="?"); ap.add_argument("--all", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--tree"); ap.add_argument("--by", default="agent:run_step")
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    if a.all:
        steps = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='search' AND sp.mode='auto' AND sp.status='planned'
                              ORDER BY p.display_name, sp.seq""", (tree_id,)).fetchall()
    else:
        if not a.step: sys.exit("give a step id or --all")
        st = cx.execute("SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (a.step, tree_id)).fetchone()
        if not st: sys.exit(f"no step {a.step} in tree {slug}")
        if st["kind"] != "search" or st["mode"] != "auto": sys.exit(f"step {a.step} is {st['kind']}/{st['mode']}, not an auto search")
        steps = [st]
    for st in steps:
        who = cx.execute("SELECT display_name FROM person WHERE id=?", (st["person_id"],)).fetchone()[0]
        if a.dry_run: print(who, st["id"], st["row_key"], dumps(run(cx, cat, tree_id, st, a.by, dry_run=True))); continue
        cx.execute("BEGIN")
        try: res = run(cx, cat, tree_id, st, a.by); cx.commit()
        except Exception: cx.rollback(); raise
        print(who, st["id"], st["row_key"]); print("  ", dumps(res))

if __name__ == "__main__": main()
