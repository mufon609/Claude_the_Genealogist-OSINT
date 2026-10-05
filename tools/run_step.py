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
response the connector marks as the record itself is read as one. A place field carrying several names is tried name by
name, stopping at the first that gets a hit whose record arrived (the run's logged place says so), and a request already
made on the run is not made again: a name that makes one is logged as tried, the note saying whose request it repeated. One search_log
row records the exact query, the outcome (found when a hit's record or image arrived, none when the source answered with
nothing, error when it did not answer: a hit none of whose records arrived, its fetches timed out or refused or an item's
metadata leading nowhere, is a request the source did not answer, and a run whose hits are all such is an error run, the
step asked again), how many results the source said it had, and every artifact hash; found marks the step done. An answer no reader of the connector parses (any exception from its total, narrow, hits, next_page or follow: a
challenge or maintenance page a holder serves with status 200 in place of its answer) is archived as it came and counts as
no answer: the note gives the exception's type and message, and a run none of whose requests was answered is logged error,
so the step stays runnable and the turn goes on (docs/RESEARCH-WORKFLOW.md §8). Then the extractor runs on each hit's own transcription or text (the search response is the query's evidence, not
a record) and the matcher on each extraction; a record no extractor claims is reported as unparsed. A run that fails is an
error run, never a stop (docs/RESEARCH-WORKFLOW.md §4): when the reading or the matching of its records raises, what the
reading wrote is rolled back, the run's rows and the responses it archived are kept, and each row is restated as error
with the exception in its note; when the connector raises before the run is logged (it cannot build its requests), what it
wrote is rolled back and an error run is logged in its place. Either way the step stays runnable at that source and --all
goes on to the next step. A run whose records
are results listings (extract.RESULTS_LISTINGS: one persona per row, the gravesite locator's results page, the death
index's rows under a surname) is found only when a row fits a person, as docs/RESEARCH-WORKFLOW.md §4 has it for a
results page saved by hand: when no row of any listing fits anyone, the run is read again as none with the reason in its note
(log_search.restate: a new row superseding the found one, search_log being insert-only), the rows stay on the artifact as
candidates, and the step stands as it stood before the run. A run whose records are all
records no parser reads, whatever their form (log_search.unread_record: a web page or a JSON or text response, every reading
of it failed; an image or an item's metadata is never read as a record), is read again as unread the same way, as the
attach logs a page saved by hand: the records are held on the step's log, the note says so, and no step is closed.
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
import argparse, http.client, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, USER_AGENT, archive_object, connect, dumps, now, resolve_tree, ulid
from catalog import Catalog, collection_tier, first_value
from log_search import hold_unread, log as log_search, latest_answer, ran_unchanged, rendered_query, restate, unread_record
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
    cid = ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key,trust_tier) VALUES (?,?,?,?,?,?)", (cid, conn.SOURCE, conn.COLLECTION, "other", conn.__name__.split(".")[-1], collection_tier(conn.SOURCE, conn.COLLECTION)))
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

def outcome_of(hits, errors, answered, lost=()):
    """found when a hit's record (or its image) arrived (hits: the hits answered, whose record arrived or which are a book the
    Archive lends); error when the run's only hits are hits none of whose records arrived (lost: their fetches timed out or
    were refused, or an item's metadata led nowhere, requests the source did not answer, so the step is asked again), or
    when the source answered no request (a timeout, a refusal, or an answer no reader parses: a challenge or maintenance page
    served in place of the answer); none when it answered with nothing, or when every hit is a book the Archive lends and
    does not serve (the note says so)."""
    if any(not h.get("restricted") for h in hits): return "found"
    if lost: return "error"
    if errors and not answered: return "error"
    return "none"

def unreadable(url, e):
    """An answer no reader of the connector parses, as the run's note and the turn's report show it: the exception's type and
    message first, so a challenge page and a reader's own defect both read plainly, then the URL."""
    return f"an answer no reader parses ({type(e).__name__}: {e}) at {url}"

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
    """The planned steps the runner can take: auto search steps, and every fetch step whose holder (or a row source) has a
    connector, whether or not that connector currently has anything to ask (a book citation that names no title still runs,
    logged `none` there with the field wanted); each while one of its connectors' sources has no run since the plan last wrote
    its fields (waiting_connectors): a step run once on these fields at every source is asked again only when the plan changes
    them, or by its id; a run logged error, the source not answering, does not count, so that source is asked again."""
    rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.status='planned'
                         AND ((sp.kind='search' AND sp.mode='auto') OR (sp.kind='fetch' AND sp.mode='fetch')) ORDER BY p.display_name, sp.seq""", (tree_id,)).fetchall()
    out = []
    for r in rows:
        conns = connectors_for(cat, r)
        if not conns: continue
        q = rendered_query(r["query_json"], r["revisions_json"])
        if not waiting_connectors(cx, r, q, conns): continue
        out.append(r)
    return out

def household_steps(cx, tree_id, step):
    """The other fetch steps at the same holder whose citations name the same census page (year, enumeration district, census
    place and page): every household member cited on it. A page fetched once is held for all of them."""
    q = json.loads(step["query_json"] or "{}"); v = lambda d, k: str(first_value((d.get(k) or {}).get("value")) or "").strip().lower()
    if not v(q, "enumeration district"): return []
    rows = cx.execute("""SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE p.tree_id=? AND sp.kind='fetch' AND sp.id<>?
                         AND sp.locator_source_id=? AND sp.status='planned'""", (tree_id, step["id"], step["locator_source_id"])).fetchall()
    return [r for r in rows if all(v(json.loads(r["query_json"] or "{}"), k) == v(q, k) for k in ("year", "enumeration district", "census place", "page"))]

def run(cx, cat, tree_id, step, by, dry_run=False, again=False):
    """One step through the connectors still to ask on its current fields (waiting_connectors), or through every one when
    again is set (a step run by its id): one run each (connector_run), then extraction and matching over every record any of
    them archived (read_records); a found run whose records fit no one (every record a results listing none of whose rows
    fits) is read again as none, and one whose records are all records no parser reads, a page or a response alike, as unread
    (log_search.restate: a new row superseding the found one, whose id the result then names), each leaving the step as it
    stood before the run. A run that fails is an error run, never an exception: the connector raising before the run is
    logged (connector_run) or the reading or matching of its records raising (read_records) leaves an error run on the step,
    the exception in its note and under `failed` in the result, and the step runnable at that source. Returns one result per
    connector: a connector not asked, its source having answered on these fields, reports that answer (asked False,
    answered {outcome, at}) instead of a run, so --dry-run says which sources a step would ask."""
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
        if dry_run:
            r = run_connector(cx, cat, tree_id, step, conn, by, dry_run=True)
            answered = {"answered": {"outcome": a[0], "at": a[1]}} if a else {}
            out.append({**r, "source": conn.SOURCE, "asked": True, **answered})
            continue
        r = connector_run(cx, cat, tree_id, step, conn, by, q)
        r = {**r, "source": conn.SOURCE, "asked": True}
        out.append(read_records(cx, tree_id, step, r, by))
    return out

def failure(what, e):
    """A failure of the runner's own work on a step, as the run's note and the turn's report show it: what failed, then the
    exception's type and message."""
    return f"{what} failed ({type(e).__name__}: {e})"

def connector_run(cx, cat, tree_id, step, conn, by, query):
    """run_connector in a savepoint of its own: the run, or, when it raises (a connector that cannot build its requests from
    the step's fields), what it wrote rolled back and an error run logged in its place at the connector's source, the
    exception in the note and under `failed`, so the step stays runnable there."""
    cx.execute("SAVEPOINT connector_run")
    try:
        r = run_connector(cx, cat, tree_id, step, conn, by)
    except (Exception, SystemExit) as e:
        cx.execute("ROLLBACK TO connector_run")
        cx.execute("RELEASE connector_run")
        said = failure("the connector's run", e)
        lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome="error", artifacts=None, note=said, query=query)
        return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": [], "outcome": "error", "log": lid, "logs": [lid],
                "artifacts": [], "hits": [], "errors": [said], "household_steps": [], "records": [], "failed": said}
    cx.execute("RELEASE connector_run")
    return r

def read_records(cx, tree_id, step, r, by):
    """A run's records read and matched (read) in a savepoint of its own. When the reading or the matching raises, what it
    wrote is rolled back, the run's rows and the responses it archived are kept, and every row the run logged is restated as
    an error run (log_search.restate), the exception in its note and under `failed`, each step it marked done back to the
    status it had: the step stays runnable. Returns the run with its outcome, its rows and what each record read gave."""
    records = r.pop("records")
    cx.execute("SAVEPOINT reading")
    try:
        extracted, outcome, logs = read(cx, tree_id, step, r, records, by)
    except (Exception, SystemExit) as e:
        cx.execute("ROLLBACK TO reading")
        cx.execute("RELEASE reading")
        said = failure("reading and matching its records", e)
        logs = [restate(cx, by, lid, outcome="error", note=said) for lid in r["logs"]]
        for sid in r["household_steps"]: cx.execute("UPDATE search_plan SET status='planned' WHERE id=?", (sid,))   # household_steps takes only planned steps
        cx.execute("UPDATE search_plan SET status=? WHERE id=?", (step["status"], step["id"]))
        return {**r, "outcome": "error", "log": logs[0], "logs": logs, "errors": r["errors"] + [said], "failed": said, "extracted": []}
    cx.execute("RELEASE reading")
    return {**r, "outcome": outcome, "log": logs[0], "logs": logs, "extracted": extracted}

def read(cx, tree_id, step, r, records, by):
    """Extraction and matching over a run's records, then the run read again when they say so: as none when every record is
    a results listing none of whose rows fits anyone, as unread when every record is one no parser reads. Returns (what each
    record read gave, the run's outcome, its rows)."""
    extracted, readings = [], []                                 # readings: (a results listing, fits someone) per record read
    for sha in records:                                          # a hit's own record; the search response is the query's evidence, not a record
        eid, n = extract(cx, sha, by)
        if "failed" in n: extracted.append({"sha256": sha, "unparsed": n["failed"]}); continue
        props, taken = match_record(cx, eid, by)
        extracted.append({"sha256": sha, "extraction": eid, **{k: v for k, v in n.items() if k != "place_strings"}, "proposals": len(props), "accepted_by_rule": len(taken)})
        readings.append((listing(cx, eid), fits(cx, tree_id, eid, props)))
    outcome, logs = r["outcome"], list(r["logs"])
    if outcome == "found" and readings and all(l for l, _ in readings) and not any(f for _, f in readings):
        logs[0] = restate(cx, by, logs[0], outcome="none", note="no candidate fits")   # a none run holds no record: the step stands as it stood before the run
        cx.execute("UPDATE search_plan SET status=? WHERE id=?", (step["status"], step["id"]))
        outcome = "none"
    elif outcome == "found" and extracted and all(unread_record(cx, e["sha256"]) for e in extracted):   # every record is one no parser reads, page or response: held on the log, read by nobody, closing nothing
        logs = [hold_unread(cx, by, lid) for lid in logs]
        for sid in r["household_steps"]: cx.execute("UPDATE search_plan SET status='planned' WHERE id=?", (sid,))   # household_steps takes only planned steps
        cx.execute("UPDATE search_plan SET status=? WHERE id=?", (step["status"], step["id"]))
        outcome = "unread"
    return extracted, outcome, logs

def request_key(rq):
    """What makes two requests one: the URL and the form data posted to it."""
    return rq["url"], json.dumps(rq.get("data") or {}, sort_keys=True, default=str)

def run_connector(cx, cat, tree_id, step, conn, by, dry_run=False):
    """One step at one connector: requests, responses archived, hits fetched and archived, the log row under the connector's
    source. A place field carrying more than one accurate name (checklist.py's PLACES for a search step's own "place",
    plan.citation_fields for a fetch step's citation label, "census place": the name valid at the record's date first, then
    as-written, then current, then every other dated name) is tried in that order, one substituted for it at a time, and
    stops at the first that gets a hit. A name's requests are built (connector.requests) before any is sent, and one
    already made on this run is never made again: a connector that reads a place only as a state and a county, or not at
    all, builds the same request for two names of one place, which a rate-limited holder cannot answer differently, so
    such a name is not asked and the run's note says which name's request it repeated. Every name tried, asked or not,
    is on the logged run's query, the last of them its value, with `stopped_at_hit` saying whether the run stopped at a
    name that got a hit, whatever the hit came to (a record, a book the Archive lends, a listing no row of which fits), so
    a widening try is read back afterwards, and a run that tried every name or stopped at a hit is read as the step's own
    fields (log_search.same_fields). A name one of whose requests got no answer (a timeout, a refusal, or a hit none of whose
    records arrived), its own or the earlier name's it repeated, is listed `unanswered` beside them, and such a run is not
    the step's own fields: the next run asks it again. A hit none of whose records arrived is no hit to stop at: the next
    name is tried. Returns the run with the records archived, to be read afterwards."""
    query = rendered_query(step["query_json"], step["revisions_json"])
    from connectors.ia import name_parts
    surname = name_parts(query)[1]
    variants = variants_of(cx, step["person_id"], surname) if surname else []
    if variants: query = {**query, "surname_variants": {"value": variants, "basis": "record"}}   # the spellings records gave the person, for a search that takes one word
    pk = next((k for k in query if (k == "place" or k.endswith("place")) and isinstance((query.get(k) or {}).get("value"), list)), None)   # a search step's own "place", or a fetch step's citation label ("census place")
    place_field = query.get(pk) if pk else None
    names = place_field["value"] if isinstance(place_field, dict) and isinstance(place_field.get("value"), list) and place_field["value"] else [None]
    query_for = lambda name: query if name is None else {**query, pk: {**place_field, "value": name}}
    reqs = conn.requests(query_for(names[0])); gate = outside(cat, conn, step["query_type"], query)
    wants = (conn.wants(query_for(names[0])) if hasattr(conn, "wants") else None) or "a surname, or for a cited book its title" if not reqs else None
    if dry_run: return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": reqs, **({"outside": gate} if gate else {}), **({"wants": wants} if wants else {}),
                        **({"place_names": names} if names != [None] else {})}
    if not reqs: gate = f"the fields give the connector nothing to ask; it wants {wants}: not asked"   # no request: a none run with the reason, the step asked again once the plan writes the field
    if gate:                                                     # the source's years miss the step's, or its connector has nothing to ask: a none run with the reason, no request
        lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome="none", artifacts=None, note=gate, query=query)
        return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": [], "outcome": "none", "log": lid, "logs": [lid], "artifacts": [], "hits": [], "errors": [], "household_steps": [], "records": [], **({"wants": wants} if wants else {"outside": gate})}
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
    def hits_of_page(h, in_hand):
        """A hit's fetches archived, and whether its record arrived: a fetch read as a record or an image archived, or, for a hit
        that fetches nothing, the response in hand that is itself the record (in_hand). An item's metadata alone is no record."""
        got, todo, arrived = [], list(h["fetch"]), in_hand and not h["fetch"]
        while todo:                                              # a fetched response may name more to fetch (connector.follow)
            f = todo.pop(0)
            if "bytes" in f:                                     # computed locally from a response already in hand, not a request of its own
                d2, h2 = f["bytes"], {"status": None, "etag": None, "last_modified": None, "final_url": f.get("url"), "content_type": None}
            else:
                try: d2, h2 = fetch(f["url"], f["kind"], conn)
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, http.client.HTTPException) as e: errors.append(f"{f['url']}: {e}"); continue
            if hasattr(conn, "follow"):                          # first, so what the response taught (the pages chosen) is in this artifact's notes
                try: todo += conn.follow(f, d2, h)
                except Exception as e: errors.append(unreadable(f["url"], e))
            got.append(keep(d2, h2, f["kind"], f["url"], {**h["notes"], "hit": h["label"], "locator": h["locator"], "step_type": step["query_type"], "connector": conn.__name__.split(".")[-1],
                                                          **({"page_number": f["page"]} if f.get("page") else {}), **({"spelling": f["spelling"]} if f.get("spelling") else {})},
                            derived_from=f.get("derived_from")))   # the step's kind and the connector on the response itself, so it reads the same on its own
            if f["kind"] != "image" and f.get("record", True): records.append(got[-1])
            arrived = arrived or f["kind"] == "image" or f.get("record", True)
        hits.append({"label": h["label"], "locator": h["locator"], "artifacts": got, "restricted": bool(h["notes"].get("restricted")), "arrived": arrived})
    asked = []                                                   # what a source with too many results needs on the step (connector.narrow)
    made, repeated = {}, []                                      # made: a request's identity -> the name that made it; repeated: the notes of the names that made no new request
    answered, unanswered = {}, []                                # answered: a request's identity -> whether every page of it was answered and every hit it named arrived; unanswered: the names one of whose requests was not
    stopped = False                                              # the run stopped at a name that got a hit, the rest never tried
    for name in names:
        q = query_for(name); creqs = reqs if name == names[0] else conn.requests(q)
        if name is not None: tried.append(name)
        new = [rq for rq in creqs if request_key(rq) not in made]
        if creqs and not new:                                    # every request this name makes was made under another name already
            earlier = dict.fromkeys(made[request_key(rq)] for rq in creqs)
            repeated.append(f"{name} made the same request as {' and '.join(earlier)}: not asked again")
            if name is not None and not all(answered[request_key(rq)] for rq in creqs): unanswered.append(name)
            continue
        made.update({request_key(rq): name for rq in new})
        before = len(hits)
        for rq in new:
            all_reqs.append(rq["url"])
            url = rq["url"]; pages = 1; answered[request_key(rq)] = True
            while url:                                               # a search pages on while the connector says the total stays small (connector.next_page)
                first = url == rq["url"]                             # the request as the connector gave it; a later page is a GET of the URL the connector named
                try: data, meta = fetch(url, rq["kind"], conn, rq.get("data") if first else None)
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, http.client.HTTPException) as e: errors.append(f"{url}: {e}"); answered[request_key(rq)] = False; break
                sha = keep(data, meta, rq["kind"], url, {"request": rq["kind"], "query": q}, locator=(rq.get("locator") if first else f"{rq['locator']}&page={pages}") if rq.get("locator") else None)
                rq["archived_sha"] = sha                              # this request's own bytes, for hits() to derive from (connectors/__init__.py)
                try:                                                 # an answer no reader parses (a challenge page served with status 200) is no answer: the request is unanswered
                    total = conn.total(data) if first else None
                    narrow = conn.narrow(url, data) if first and hasattr(conn, "narrow") else None
                    page_hits = conn.hits(url, data, rq) if conn.hits.__code__.co_argcount > 2 else conn.hits(url, data)
                    nxt = conn.next_page(url, data) if hasattr(conn, "next_page") and rq["kind"] == "search" else None
                except Exception as e: errors.append(unreadable(url, e)); answered[request_key(rq)] = False; break
                if first: totals.append(total); asked.append(narrow)
                if rq.get("record") and page_hits: records.append(sha)   # the response is the record itself (a results page listing what was found); an empty answer is not a record
                pages += 1; url = nxt
                for h in page_hits:
                    hits_of_page(h, bool(rq.get("record")))
                    if not (hits[-1]["arrived"] or hits[-1]["restricted"]): answered[request_key(rq)] = False   # a hit none of whose records arrived: its fetches went unanswered
        if name is not None and not all(answered[request_key(rq)] for rq in creqs): unanswered.append(name)
        if any(h["arrived"] or h["restricted"] for h in hits[before:]): stopped = True; break   # a hit under this name, whatever it turns out to hold: never try the rest
    came = lambda h: h["arrived"] or h["restricted"]
    outcome = outcome_of([h for h in hits if came(h)], errors, any(answered.values()), [h for h in hits if not came(h)])
    answered = "; ".join(f"the source answered with {t} result(s)" for t in totals if t is not None)
    note = "; ".join(x for x in [answered] + [a for a in asked if a] + repeated + [h["label"] + (": the Archive lends this copy and serves no text; read it at another holder" if h.get("restricted") else "") for h in hits] + errors if x)[:1000] or None
    if tried: query = {**query, pk: {**place_field, "value": tried[-1], "tried": tried, "stopped_at_hit": stopped, **({"unanswered": unanswered} if unanswered else {})}}   # every name tried, asked or not, the one the run stopped on, whether it stopped at a hit, and the names the source did not answer

    own = step["kind"] != "fetch" or conn.SOURCE == step["locator_source_id"]   # a fetch step is done by its holder's answer alone: a row-source connector's hit is another paper's page, logged and held, the cited record still to fetch
    lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome=outcome, artifacts=shas or None, note=note, query=query, done=own)
    household, logs = [], [lid]
    if step["kind"] == "fetch" and outcome == "found" and own:      # the page is held for every household member cited on it
        for other in household_steps(cx, tree_id, step):
            logs.append(log_search(cx, tree_id, by, step_id=other["id"], outcome="found", artifacts=shas, note=f"the same page, fetched for {cx.execute('SELECT display_name FROM person WHERE id=?', (step['person_id'],)).fetchone()[0]}",
                                   query=rendered_query(other["query_json"], other["revisions_json"]))); household.append(other["id"])
    return {"connector": conn.__name__.split(".")[-1], "query": query, "requests": all_reqs, "outcome": outcome, "log": lid, "logs": logs, "artifacts": shas, "hits": hits,
            "errors": errors, "household_steps": household, "records": records}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("step", nargs="?"); ap.add_argument("--all", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=DB); ap.add_argument("--tree"); ap.add_argument("--by", default="agent:run_step")
    a = ap.parse_args()
    cx = connect(a.db, rows=True)
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
