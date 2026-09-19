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
a record) and the matcher on each extraction; a record no extractor claims is reported as unparsed. A run whose records
are results listings (extract.RESULTS_LISTINGS: one persona per row, the gravesite locator's results page, the death
index's rows under a surname) is found only when a row fits a person, as docs/RESEARCH-WORKFLOW.md §4 has it for a
results page saved by hand: when no row of any listing fits anyone, the run is set to none with the reason in its note,
the rows stay on the artifact as candidates, and the step stands as it stood before the run.
A step whose sources have several connectors runs at each, one log row per source: a search step at the connectors of its
row's sources, a fetch step at its holder's and at those of its row's sources too (an obituary cited at a closed source runs
at the Archive's newspapers with the citation's paper and date), the page saved by hand and a connector's answer being runs
of the same step. Each source's runs are read on their own (search_log.source_id): a step is asked at the connectors whose
source has no found or none run on its current fields, so one connector's none does not close the step at another, and a
source that did not answer (a run logged error) is asked again while the rest are not. A fetched response may name more to fetch (an item's metadata, then the search inside it, then its pages:
connector.follow); the search inside a book is asked once per spelling of the surname the alias table holds for the step's
person (surname_variants on the rendered fields, basis record), and a book the Archive only lends is a none run with the
reason. A source's years, from the registry's coverage column (1756-1963, 1780s-1990s, 1950), gate its steps: a step whose
years fall wholly outside them (an obituary for a death after the newspapers end, a cited obituary whose paper's date is)
is logged none without a request, the note saying so. A connector with nothing to ask on the step's fields (WikiTree
without a birth or death year, the Archive's books without a state, a cited book without a title: connector.wants) is
logged none the same way, the note naming the field it wanted, so the step is asked again once the plan writes it.
--all runs every planned step one of whose connectors' sources has no run since the plan last wrote its fields, in plan
order, keeping each connector's pace across steps, asking only those connectors; a step already run on the same fields at
every source is run again at every one by its id, or once the plan changes them. A run logged error is a source that did
not answer, not a run on the fields: the step stays runnable at that source and the next --all or turn asks it again.
--dry-run prints the requests and sends nothing, saying per connector whether it would be asked and what its source last
answered on these fields.
"""
import argparse, http.client, json, os, re, sqlite3, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, USER_AGENT, archive_object, dumps, now, resolve_tree, ulid
from catalog import Catalog
from log_search import log as log_search, latest_answer, ran_unchanged, rendered_query
from extract import extract, RESULTS_LISTINGS
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
    """The years a step asks about, from its rendered fields: an obituary or probate step the death year and the year after, or
    the year of the citation's publication date on a fetch step; a household step its census year; any other step the person's
    lifetime from the birth year (to the death year, or a hundred years). None when the fields name no year, so the source's
    years do not gate it."""
    v = lambda k: connectors.value(fields, k)
    death, birth, year = v("death_year"), v("birth_year"), v("year")
    pub = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", str(v("publication date") or v("date") or "")) if query_type in ("obituary", "probate") else None
    if query_type in ("obituary", "probate") and death: return int(death), int(death) + 1
    if pub: return int(pub.group(1)), int(pub.group(1))
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
    """A step's connectors: those of its row's sources that have one, in the row's order, and for a fetch step its holder's
    (the locator source) first. Each is a query at a different holder and gets its own log row. A search step carries no
    citation collection, so a connector that reads one kind of its source's row (connectors.answers) is asked only on that row."""
    sids = ([step["locator_source_id"]] if step["kind"] == "fetch" and step["locator_source_id"] else []) + json.loads(step["sources_json"] or "[]")
    out, seen = [], set()
    for sid in sids:
        name = (cat.sources.get(sid) or {}).get("connector")
        if not name or name in seen: continue
        if step["kind"] == "search" and not connectors.answers(name, step["row_key"]): continue
        seen.add(name); out.append(connectors.load(name))
    return out

def spelling_variants(surname, aliases):
    """The spellings of a surname among a person's aliases: an alias's last word when it is the surname as the matcher counts
    a spelling variant (the same Soundex within two edits, or one letter apart: Ahern for Ahearn), never a married name or
    another surname, as written, once each."""
    from catalog import key, same_surname
    out = []
    for v in aliases:
        last = (v or "").split()[-1] if (v or "").split() else ""
        if key(last) and key(last) != key(surname) and same_surname(key(last), key(surname)) in ("variant", "one letter apart") and key(last) not in [key(x) for x in out]: out.append(last)
    return out

def variants_of(cx, person_id, surname):
    """The spelling variants of the surname the alias table holds for the person (spelling_variants over the aliases not rejected)."""
    return spelling_variants(surname, [v for v, in cx.execute("SELECT value FROM alias WHERE entity_kind='person' AND entity_id=? AND status<>'rejected'", (person_id,))])

def outcome_of(hits, errors, shas):
    """found when a hit gave a record; error when the source did not answer; none when it answered with nothing, or when
    every hit is a book the Archive lends and does not serve (the note says so)."""
    if any(not h.get("restricted") for h in hits): return "found"
    if errors and not shas: return "error"
    return "none"

def listing(cx, eid):
    """Whether an extraction read a results listing (extract.RESULTS_LISTINGS), one persona per row."""
    return bool(cx.execute(f"SELECT 1 FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=? AND x.name IN ({','.join('?' * len(RESULTS_LISTINGS))})", (eid, *RESULTS_LISTINGS)).fetchone())

def fits(cx, tree_id, eid, written):
    """Whether a record read fits anyone in the tree: the matcher proposed a persona of it now, or a persona of it already
    carries a card or a link in this tree (a link carried across a re-reading of the same record proposes nothing new and
    fits still)."""
    if written: return True
    return bool(cx.execute("""SELECT 1 FROM persona pe WHERE pe.extraction_id=? AND (
                                EXISTS (SELECT 1 FROM proposal pr WHERE pr.tree_id=? AND json_extract(pr.payload_json,'$.persona_id')=pe.id AND NOT (pr.status='rejected' AND pr.decision_note='superseded'))
                                OR EXISTS (SELECT 1 FROM person_persona pp JOIN person p ON p.id=pp.person_id WHERE pp.persona_id=pe.id AND p.tree_id=?))""", (eid, tree_id, tree_id)).fetchone())

def connector_for(cat, step):
    conns = connectors_for(cat, step); return conns[0] if conns else None

def waiting_connectors(cx, step, rendered, conns):
    """The step's connectors still to ask on its current fields: those whose source has no found or none run on them
    (log_search.ran_unchanged, read per source). A step with two connectors is closed at one by its own none run and stays
    open at the other until that one answers; a source whose run was an error is asked again."""
    return [c for c in conns if not ran_unchanged(cx, step, rendered, c.SOURCE)]

def runnable(cx, cat, tree_id):
    """The planned steps the runner can take: auto search steps, and fetch steps whose holder has a connector that can ask
    for the record from the citation's details (a book citation that names no title gives the books connector nothing to ask;
    that step stays a link for a hand); each while one of its connectors' sources has no run since the plan last wrote its
    fields (waiting_connectors): a step run once on these fields at every source is asked again only when the plan changes
    them, or by its id; a run logged error, the source not answering, does not count, so that source is asked again."""
    rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.status='planned'
                         AND ((sp.kind='search' AND sp.mode='auto') OR (sp.kind='fetch' AND sp.mode='fetch')) ORDER BY p.display_name, sp.seq""", (tree_id,)).fetchall()
    out = []
    for r in rows:
        conns = connectors_for(cat, r)
        if not conns: continue
        q = rendered_query(r["query_json"], r["revisions_json"])
        if r["kind"] == "fetch" and not any(c.requests(q) for c in conns): continue
        if not waiting_connectors(cx, r, q, conns): continue
        out.append(r)
    return out

def household_steps(cx, tree_id, step):
    """The other fetch steps at the same holder whose citations name the same census page (year, enumeration district, census
    place and page): every household member cited on it. A page fetched once is held for all of them."""
    q = json.loads(step["query_json"] or "{}"); v = lambda d, k: ((d.get(k) or {}).get("value") or "").strip().lower()
    if not v(q, "enumeration district"): return []
    rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.id<>?
                         AND sp.locator_source_id=? AND sp.status='planned'""", (tree_id, step["id"], step["locator_source_id"])).fetchall()
    return [r for r in rows if all(v(json.loads(r["query_json"] or "{}"), k) == v(q, k) for k in ("year", "enumeration district", "census place", "page"))]

def run(cx, cat, tree_id, step, by, dry_run=False, again=False):
    """One step through the connectors still to ask on its current fields (waiting_connectors), or through every one when
    again is set (a step run by its id): one run each (run_connector), then extraction and matching over every record any of
    them archived. Returns one result per connector: a connector not asked, its source having answered on these fields,
    reports that answer (asked False, answered {outcome, at}) instead of a run, so --dry-run says which sources a step would
    ask."""
    conns = connectors_for(cat, step)
    if not conns: return [{"error": "no source of this step has a connector"}]
    q = rendered_query(step["query_json"], step["revisions_json"])
    todo = conns if again else waiting_connectors(cx, step, q, conns)
    out = []
    for conn in conns:
        name = conn.__name__.split(".")[-1]
        a = latest_answer(cx, step, conn.SOURCE)
        if conn not in todo:
            out.append({"connector": name, "source": conn.SOURCE, "asked": False, "answered": {"outcome": a[0], "at": a[1]}}); continue
        r = run_connector(cx, cat, tree_id, step, conn, by, dry_run)
        if dry_run: out.append({**r, "source": conn.SOURCE, "asked": True, **({"answered": {"outcome": a[0], "at": a[1]}} if a else {})}); continue
        r = {**r, "source": conn.SOURCE, "asked": True}
        if "error" in r: out.append(r); continue
        extracted, read = [], []                                 # read: (a results listing, fits someone) per record read
        for sha in r.pop("records"):                             # a hit's own record; the search response is the query's evidence, not a record
            eid, n = extract(cx, sha, by)
            if "failed" in n: extracted.append({"sha256": sha, "unparsed": n["failed"]}); continue
            props, taken = match_record(cx, eid, by)
            extracted.append({"sha256": sha, "extraction": eid, **{k: v for k, v in n.items() if k != "place_strings"}, "proposals": len(props), "accepted_by_rule": len(taken)})
            read.append((listing(cx, eid), fits(cx, tree_id, eid, props)))
        if r["outcome"] == "found" and read and all(l for l, _ in read) and not any(f for _, f in read):
            note = "no candidate fits; " + (cx.execute("SELECT notes FROM search_log WHERE id=?", (r["log"],)).fetchone()[0] or "")
            cx.execute("UPDATE search_log SET outcome='none', notes=? WHERE id=?", (note.rstrip("; "), r["log"]))   # a none run holds no record: the step stands as it stood before the run
            cx.execute("UPDATE search_plan SET status=? WHERE id=?", (step["status"], step["id"])); r["outcome"] = "none"
        out.append({**r, "extracted": extracted})
    return out

def run_connector(cx, cat, tree_id, step, conn, by, dry_run=False):
    """One step at one connector: requests, responses archived, hits fetched and archived, the log row under the connector's
    source. A place field carrying more than one accurate name (checklist.py's PLACES, docs/RESEARCH-WORKFLOW.md §3: the
    name valid at the record's date first, then as-written, then current, then every other dated name) is tried in that
    order, one substituted for it at a time, and stops at the first that gets a hit; every name actually tried is on the
    logged run's query, the one that hit last, so the same search is never repeated blindly and a widening try is read
    back afterwards. Returns the run with the records archived, to be read afterwards."""
    query = rendered_query(step["query_json"], step["revisions_json"])
    from connectors.ia import name_parts
    surname = name_parts(query)[1]
    variants = variants_of(cx, step["person_id"], surname) if surname else []
    if variants: query = {**query, "surname_variants": {"value": variants, "basis": "record"}}   # the spellings records gave the person, for a search that takes one word
    place_field = query.get("place")
    names = place_field["value"] if isinstance(place_field, dict) and isinstance(place_field.get("value"), list) and place_field["value"] else [None]
    query_for = lambda name: query if name is None else {**query, "place": {**place_field, "value": name}}
    reqs = conn.requests(query_for(names[0])); gate = outside(cat, conn, step["query_type"], query)
    wants = (conn.wants(query_for(names[0])) if hasattr(conn, "wants") else None) or "a surname, or for a cited book its title" if not reqs else None
    if dry_run: return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": reqs, **({"outside": gate} if gate else {}), **({"wants": wants} if wants else {}),
                        **({"place_names": names} if names != [None] else {})}
    if not reqs: gate = f"the fields give the connector nothing to ask; it wants {wants}: not asked"   # no request: a none run with the reason, the step asked again once the plan writes the field
    if gate:                                                     # the source's years miss the step's, or its connector has nothing to ask: a none run with the reason, no request
        lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome="none", artifacts=None, note=gate, query=query)
        return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": [], "outcome": "none", "log": lid, "artifacts": [], "hits": [], "errors": [], "household_steps": [], "records": [], **({"wants": wants} if wants else {"outside": gate})}
    src = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id=?", (conn.SOURCE,)).fetchone()
    tier, terms, cost = (src or (None, None, None))
    cost = next((c for c in ("free", "paid", "member") if (cost or "").strip().lower().startswith(c)), "unknown")
    cid = collection_for(cx, conn); shas, records, hits, errors, totals, tried, all_reqs = [], [], [], [], [], [], []
    def keep(data, http, kind, url, notes, label=None, locator=None, derived_from=None):
        mime = (http.get("content_type") or "").split(";")[0].strip() or {"json": "application/json", "text": "text/plain", "image": "image/jpeg"}[kind]
        if kind in ("json", "search", "text") and mime.startswith("text/html"): mime = "application/json" if data[:1] in (b"{", b"[") else mime
        sha, _ = archive_object(cx, data, mime=mime, source_id=conn.SOURCE, collection_id=cid, collection_name=conn.COLLECTION, locator_kind="url", locator_value=locator or url,
                                retrieved_by=by, terms=terms, cost=cost, trust_tier=tier, notes=dumps(notes) if notes else (label or ""), http=http, derived_from=derived_from)
        if sha not in shas: shas.append(sha)
        return sha
    def hits_of_page(h):
        got, todo = [], list(h["fetch"])
        while todo:                                              # a fetched response may name more to fetch (connector.follow)
            f = todo.pop(0)
            if "bytes" in f:                                     # computed locally from a response already in hand, not a request of its own
                d2, h2 = f["bytes"], {"status": None, "etag": None, "last_modified": None, "final_url": f.get("url"), "content_type": None}
            else:
                try: d2, h2 = fetch(f["url"], f["kind"], conn)
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, http.client.HTTPException) as e: errors.append(f"{f['url']}: {e}"); continue
            if hasattr(conn, "follow"):                          # first, so what the response taught (the pages chosen) is in this artifact's notes
                try: todo += conn.follow(f, d2, h)
                except ValueError as e: errors.append(f"{f['url']}: {e}")
            got.append(keep(d2, h2, f["kind"], f["url"], {**h["notes"], "hit": h["label"], "locator": h["locator"], "step_type": step["query_type"], "connector": conn.__name__.split(".")[-1],
                                                          **({"page_number": f["page"]} if f.get("page") else {}), **({"spelling": f["spelling"]} if f.get("spelling") else {})},
                            derived_from=f.get("derived_from")))   # the step's kind and the connector on the response itself, so it reads the same on its own
            if f["kind"] != "image" and f.get("record", True): records.append(got[-1])
        hits.append({"label": h["label"], "locator": h["locator"], "artifacts": got, "restricted": bool(h["notes"].get("restricted"))})
    asked = []                                                   # what a source with too many results needs on the step (connector.narrow)
    for name in names:
        q = query_for(name); creqs = reqs if name == names[0] else conn.requests(q)
        if name is not None: tried.append(name)
        before = len(hits)
        for rq in creqs:
            all_reqs.append(rq["url"])
            url = rq["url"]; pages = 1
            while url:                                               # a search pages on while the connector says the total stays small (connector.next_page)
                first = url == rq["url"]                             # the request as the connector gave it; a later page is a GET of the URL the connector named
                try: data, meta = fetch(url, rq["kind"], conn, rq.get("data") if first else None)
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, http.client.HTTPException) as e: errors.append(f"{url}: {e}"); break
                sha = keep(data, meta, rq["kind"], url, {"request": rq["kind"], "query": q}, locator=(rq.get("locator") if first else f"{rq['locator']}&page={pages}") if rq.get("locator") else None)
                rq["archived_sha"] = sha                              # this request's own bytes, for hits() to derive from (connectors/__init__.py)
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
        if len(hits) > before: break                              # a hit under this name: never try the rest
    outcome = outcome_of(hits, errors, shas)
    answered = "; ".join(f"the source answered with {t} result(s)" for t in totals if t is not None)
    note = "; ".join(x for x in [answered] + [a for a in asked if a] + [h["label"] + (": the Archive lends this copy and serves no text; read it at another holder" if h.get("restricted") else "") for h in hits] + errors if x)[:1000] or None
    if tried: query = {**query, "place": {**place_field, "value": tried[-1], "tried": tried}}   # every name actually tried, the one the run stopped on

    own = step["kind"] != "fetch" or conn.SOURCE == step["locator_source_id"]   # a fetch step is done by its holder's answer alone: a row-source connector's hit is another paper's page, logged and held, the cited record still to fetch
    lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome=outcome, artifacts=shas or None, note=note, query=query, done=own)
    household = []
    if step["kind"] == "fetch" and outcome == "found" and own:      # the page is held for every household member cited on it
        for other in household_steps(cx, tree_id, step):
            log_search(cx, tree_id, by, step_id=other["id"], outcome="found", artifacts=shas, note=f"the same page, fetched for {cx.execute('SELECT display_name FROM person WHERE id=?', (step['person_id'],)).fetchone()[0]}",
                       query=rendered_query(other["query_json"], other["revisions_json"])); household.append(other["id"])
    return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": all_reqs, "outcome": outcome, "log": lid, "artifacts": shas, "hits": hits,
            "errors": errors, "household_steps": household, "records": records}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("step", nargs="?"); ap.add_argument("--all", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--tree"); ap.add_argument("--by", default="agent:run_step")
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    if a.all:
        ran = set()                                          # a rule accept during one step regenerates the plan (docs/RESEARCH-WORKFLOW.md §5-7)
        while True:                                           # and can drop a step still to run, or open a new one; read fresh before each run, as tools/turn.py does
            todo = [st for st in runnable(cx, cat, tree_id) if st["id"] not in ran]
            if not todo: break
            st = todo[0]; ran.add(st["id"])
            who = cx.execute("SELECT display_name FROM person WHERE id=?", (st["person_id"],)).fetchone()[0]
            if a.dry_run: print(who, st["id"], st["row_key"], dumps(run(cx, cat, tree_id, st, a.by, dry_run=True))); continue
            cx.execute("BEGIN")
            try: res = run(cx, cat, tree_id, st, a.by); cx.commit()
            except (Exception, SystemExit): cx.rollback(); raise
            print(who, st["id"], st["row_key"])
            for r in res: print("  ", dumps(r))
        return
    if not a.step: sys.exit("give a step id or --all")
    st = cx.execute("SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (a.step, tree_id)).fetchone()
    if not st: sys.exit(f"no step {a.step} in tree {slug}")
    if connector_for(cat, st) is None or st["status"] != "planned": sys.exit(f"step {a.step} is {st['kind']}/{st['mode']}/{st['status']}: no connector runs it")
    who = cx.execute("SELECT display_name FROM person WHERE id=?", (st["person_id"],)).fetchone()[0]
    if a.dry_run: print(who, st["id"], st["row_key"], dumps(run(cx, cat, tree_id, st, a.by, dry_run=True, again=True))); return
    cx.execute("BEGIN")
    try: res = run(cx, cat, tree_id, st, a.by, again=True); cx.commit()
    except (Exception, SystemExit): cx.rollback(); raise
    print(who, st["id"], st["row_key"])
    for r in res: print("  ", dumps(r))

if __name__ == "__main__": main()
