#!/usr/bin/env python3
"""Green in one command: every parser read against a saved real page.

usage: tools/check.py [--show] [--keep]

A scratch catalog under a temporary data root, never the owner's. Every page under tests/fixtures/ is archived there and
read by tools/extract.py as the attach would read it, and the personas, facts and relations it writes are compared with
the expectations in the sidecar beside the page (<stem>.expect.json, the vocabulary in tests/fixtures/README.md) by
tests/checks/parsers.py; the connectors' requests and their reading of saved responses are checked with no network. One
line per fixture, ok or FAIL with every reason; exit status 1 on any failure. --show prints what each extraction wrote,
for writing a sidecar; --keep leaves the scratch directories in place and prints their paths.
"""
import argparse, json, os, sqlite3, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
BY = "agent:check"
sys.path.insert(0, os.path.join(ROOT, "tests", "checks")); sys.path.insert(0, os.path.join(ROOT, "tools"))
import parsers, scenario                                     # every parser on its fixture, and the scenarios on the harness tree: the expectations in the data beside them

def scratch(keep):
    d = tempfile.mkdtemp(prefix="tree-check-")
    os.environ["DATA_ROOT"] = d                                  # before treelib is imported: every data path resolves under it
    db = os.path.join(d, "catalog", "tree.db"); os.makedirs(os.path.dirname(db)); os.makedirs(os.path.join(d, "inbox"))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "initdb.py"), "--db", db], capture_output=True, text=True)
    if r.returncode: sys.exit(f"initdb failed:\n{r.stdout}{r.stderr}")
    return d, db

def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=os.environ)
    if r.returncode: raise RuntimeError(f"{os.path.basename(args[0])} failed:\n{r.stdout}{r.stderr}")
    return r.stdout

def places(keep):
    """resolve_places.py's own accept/undecided line: a unique full match auto-accepts; same-name candidates whose
    boundingboxes coincide (one territory under two names, Philadelphia city/county) auto-accept as the locality,
    "coterminous: one territory"; same-name candidates genuinely nested at different scales (Hempstead village inside
    its much larger town) stay Undecided with both offered (CLAUDE.md; the wider nested/coterminous shortcut that used
    name and containment alone, with no size test, is withdrawn)."""
    import hashlib
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from resolve_places import cache_dir, wikidata_cache_dir
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "resolvertest", "--name", "Resolver Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON")
    unique_raw, cotermin_raw, nested_raw = "Emmaus, Lehigh, Pennsylvania", "Philadelphia, Pennsylvania", "Hempstead, Nassau, New York"
    morioka_raw, tonan_raw = "Morioka, Japan", "Ogau Tonan, Iwate Shiwa, Japan"
    for raw in (unique_raw, cotermin_raw, nested_raw, morioka_raw, tonan_raw): cx.execute("INSERT INTO place_string (id, raw) VALUES (?, ?)", (treelib.ulid(), raw))
    cx.commit()
    emmaus = {"osm_type": "node", "osm_id": 1, "lat": "40.53", "lon": "-75.49", "name": "Emmaus",
              "display_name": "Emmaus, Lehigh County, Pennsylvania, United States", "category": "boundary", "type": "administrative",
              "addresstype": "town", "address": {"town": "Emmaus", "county": "Lehigh County", "state": "Pennsylvania", "country": "United States", "country_code": "us"}, "extratags": {}}
    phila_city = {"osm_type": "relation", "osm_id": 2, "lat": "40.0", "lon": "-75.13", "name": "Philadelphia",
                  "display_name": "Philadelphia, Philadelphia County, Pennsylvania, United States", "category": "boundary", "type": "administrative",
                  "addresstype": "city", "boundingbox": ["39.8670050", "40.1379593", "-75.2802660", "-74.9558314"],
                  "address": {"city": "Philadelphia", "county": "Philadelphia County", "state": "Pennsylvania", "country": "United States", "country_code": "us"}, "extratags": {}}
    phila_county = {"osm_type": "relation", "osm_id": 3, "lat": "40.0", "lon": "-75.13", "name": "Philadelphia County",
                    "display_name": "Philadelphia County, Pennsylvania, United States", "category": "boundary", "type": "administrative",
                    "addresstype": "county", "boundingbox": ["39.8670050", "40.1379593", "-75.2802660", "-74.9558314"],
                    "address": {"county": "Philadelphia County", "state": "Pennsylvania", "country": "United States", "country_code": "us"}, "extratags": {}}
    hemp_town = {"osm_type": "relation", "osm_id": 4, "lat": "40.64", "lon": "-73.6", "name": "Town of Hempstead",
                 "display_name": "Town of Hempstead, Nassau County, New York, United States", "category": "boundary", "type": "administrative",
                 "addresstype": "municipality", "boundingbox": ["40.5253180", "40.7567050", "-73.7672900", "-73.4647620"],
                 "address": {"municipality": "Town of Hempstead", "county": "Nassau County", "state": "New York", "country": "United States", "country_code": "us"}, "extratags": {}}
    hemp_village = {"osm_type": "relation", "osm_id": 5, "lat": "40.70", "lon": "-73.62", "name": "Village of Hempstead",
                    "display_name": "Village of Hempstead, Town of Hempstead, Nassau County, New York, United States", "category": "boundary", "type": "administrative",
                    "addresstype": "town", "boundingbox": ["40.6841120", "40.7213530", "-73.6433830", "-73.5984910"],
                    "address": {"town": "Village of Hempstead", "municipality": "Town of Hempstead", "county": "Nassau County", "state": "New York", "country": "United States", "country_code": "us"}, "extratags": {}}
    os.makedirs(cache_dir(), exist_ok=True)
    def plant(query, cands):
        with open(os.path.join(cache_dir(), hashlib.sha1(query.lower().encode()).hexdigest() + ".json"), "w", encoding="utf-8") as fh:
            json.dump({"query": query, "fetched_at": treelib.now(), "results": cands}, fh)
    morioka = {"osm_type": "relation", "osm_id": 10, "lat": "39.7", "lon": "141.15", "name": "Morioka",
               "display_name": "Morioka, Iwate, Japan", "category": "boundary", "type": "administrative", "addresstype": "city",
               "address": {"city": "Morioka", "state": "Iwate", "country": "Japan", "country_code": "jp"}, "extratags": {"wikidata": "Q200077"}}
    plant("Emmaus, Lehigh, Pennsylvania, United States", [emmaus])
    plant("Philadelphia, Pennsylvania, United States", [phila_city, phila_county])
    plant("Hempstead, Nassau, New York, United States", [hemp_town, hemp_village])
    plant("Morioka, Japan", [morioka])
    plant("Ogau Tonan, Iwate Shiwa, Japan", [])                       # no geocoder candidates: falls to the dated-name check
    plant("Ogau Tonan, Japan", [])
    os.makedirs(wikidata_cache_dir(), exist_ok=True)                  # the Wikidata answers, so the run never hits the network
    for qid in ("Q200077", "Q11643491"):
        shutil.copy(os.path.join(ROOT, "tests", "fixtures", f"wikidata-{qid}-{'morioka' if qid == 'Q200077' else 'tonan'}.json"), os.path.join(wikidata_cache_dir(), qid + ".json"))
    run(os.path.join(ROOT, "tools", "resolve_places.py"), "--db", db, "--tree", "resolvertest", "--by", BY)
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    row = cx.execute("SELECT status, place_id FROM place_string WHERE raw=?", (unique_raw,)).fetchone()
    fail(row and row[0] == "accepted" and row[1], f"a unique full match still auto-accepts: {tuple(row) if row else row}")
    row2 = cx.execute("SELECT status, place_id, notes FROM place_string WHERE raw=?", (cotermin_raw,)).fetchone()
    fail(row2 and row2[0] == "accepted" and row2[1] and json.loads(row2[2])["how"] == "coterminous: one territory",
         f"a city and the county coterminous with it accept as one territory: {tuple(row2) if row2 else row2}")
    row3 = cx.execute("SELECT status, place_id FROM place_string WHERE raw=?", (nested_raw,)).fetchone()
    fail(row3 and row3[0] == "undecided" and row3[1] is None, f"a village genuinely nested in its much larger town stays undecided: {tuple(row3) if row3 else row3}")
    prop = cx.execute("SELECT payload_json FROM proposal WHERE kind='place_resolution' AND payload_json LIKE ?", (f'%{nested_raw}%',)).fetchone()
    names = {c.get("display_name") for c in json.loads(prop[0])["candidates"]} if prop else set()
    fail(prop and hemp_town["display_name"] in names and hemp_village["display_name"] in names,
         f"the proposal offers both the village and the town as candidates: {names}")
    morioka_row = cx.execute("SELECT id, wikidata_id FROM place WHERE name='Morioka'").fetchone()
    fail(morioka_row and morioka_row[1] == "Q200077", f"Morioka resolves with its wikidata_id carried onto the place: {morioka_row}")
    dated_row = cx.execute("SELECT valid_from, valid_to FROM place_name WHERE place_id=? AND name='Tonan'", (morioka_row[0] if morioka_row else None,)).fetchone()
    fail(dated_row == ("1955-04-01", "1992-04-01"), f"Tonan is written as a dated former name of Morioka, from Wikidata's own P571/P576: {dated_row}")
    tonan_row = cx.execute("SELECT status, place_id FROM place_string WHERE raw=?", (tonan_raw,)).fetchone()
    fail(tonan_row and tonan_row[0] == "undecided" and tonan_row[1] is None, f"a dated former name is offered, never auto-resolved: {tonan_row}")
    tonan_prop = cx.execute("SELECT payload_json FROM proposal WHERE kind='place_resolution' AND payload_json LIKE ?", (f'%{tonan_raw}%',)).fetchone()
    tonan_cands = json.loads(tonan_prop[0])["candidates"] if tonan_prop else []
    fail(len(tonan_cands) == 1 and tonan_cands[0]["kind"] == "jurisdiction_change" and tonan_cands[0]["name"] == "Tonan" and tonan_cands[0]["place_id"] == morioka_row[0]
         and tonan_cands[0]["valid_from"] == "1955-04-01" and tonan_cands[0]["valid_to"] == "1992-04-01" and tonan_cands[0]["leading"] == "Ogau",
         f"the string's own card offers Tonan as a dated candidate of Morioka, the leading word left as the finer, unverified part: {tonan_cands}")
    cx.close()
    if not keep: shutil.rmtree(d, ignore_errors=True)
    return fails

def place_name_retry(keep):
    """run_step.run_connector, given a search step whose place field carries more than one accurate name
    (checklist.py's PLACES), tries each in order and stops at the first hit, with no real network: a fake connector
    and a monkeypatched fetch answer 'none' for the first name and 'found' for the second."""
    import treelib; d, db = scratch(keep); treelib.DATA_ROOT = d
    import run_step
    from treelib import dumps, ulid, now
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "retrytest", "--name", "Retry Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='retrytest'").fetchone()[0]
    ts = now(); pid = ulid()
    cx.execute("INSERT INTO person (id,tree_id,display_name,created_at,updated_at) VALUES (?,?,?,?,?)", (pid, tid, "Retry Person", ts, ts))
    query = {"surname": {"value": "Davidson", "basis": "accepted"}, "place": {"value": ["Tonan", "Morioka"], "basis": "accepted"}}
    spid = ulid()
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (spid, pid, "test row", 1, "search:test", "search", "household", dumps(query), dumps(["D05"]), "auto", "planned", ts))
    cx.commit()
    step = cx.execute("SELECT * FROM search_plan WHERE id=?", (spid,)).fetchone()
    from connectors import value
    import types
    seen_urls = []
    def fake_requests(fields):
        place = value(fields, "place")
        return [{"url": f"http://test.invalid/search?place={place}", "kind": "search"}] if place else []
    def fake_hits(url, data):
        return [] if data == b"none" else [{"label": "hit", "locator": "loc1", "fetch": [], "notes": {}}]
    conn = types.SimpleNamespace(__name__="fake.connector", SOURCE="D05", COLLECTION="Test Collection", RATE={"search": 6000}, requests=fake_requests, hits=fake_hits, total=lambda data: None)
    def fake_fetch(url, kind, c, data=None):
        return (b"none" if "place=Tonan" in url else b"found"), {"status": 200, "etag": None, "last_modified": None, "final_url": url, "content_type": "application/json"}
    orig_fetch = run_step.fetch; run_step.fetch = fake_fetch
    try:
        from catalog import Catalog
        cat = Catalog(cx, tid)
        r = run_step.run_connector(cx, cat, tid, step, conn, BY)
    finally:
        run_step.fetch = orig_fetch
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    fail(r.get("outcome") == "found", f"the second name gets a hit and the run reads found: {r}")
    fail(r.get("requests") == ["http://test.invalid/search?place=Tonan", "http://test.invalid/search?place=Morioka"], f"both names are tried, in order, before the run stops: {r.get('requests')}")
    logged = cx.execute("SELECT query_json FROM search_log WHERE plan_step_id=?", (spid,)).fetchone()
    tried = json.loads(logged[0])["place"] if logged else {}
    fail(tried.get("tried") == ["Tonan", "Morioka"] and tried.get("value") == "Morioka", f"the logged run's query names every try, the one that hit last: {tried}")
    cx.close()
    if not keep: shutil.rmtree(d, ignore_errors=True)
    return fails

def _chain_fixture(cx, tid, ts):
    """A tree scratch fixture with places on one chain (United States > Pennsylvania > Philadelphia County >
    Philadelphia) and a second city (Pittsburgh, under Allegheny County, the same state) on a different chain, and two
    events: one with accepted facts on the Philadelphia chain (the state and the city), one split across Philadelphia
    and Pittsburgh. Returns (ev_chain, ev_split, phila)."""
    import treelib
    def mkplace(name, ptype, parent=None):
        pid = treelib.ulid()
        cx.execute("INSERT INTO place (id,name,place_type,parent_id,updated_at) VALUES (?,?,?,?,?)", (pid, name, ptype, parent, ts))
        return pid
    usa = mkplace("United States", "country")
    pa = mkplace("Pennsylvania", "state", usa)
    phila_co = mkplace("Philadelphia County", "county", pa)
    phila = mkplace("Philadelphia", "city", phila_co)
    allegheny_co = mkplace("Allegheny County", "county", pa)
    pittsburgh = mkplace("Pittsburgh", "city", allegheny_co)
    def mk_string(raw, place_id):
        psid = treelib.ulid()
        cx.execute("INSERT INTO place_string (id,raw,place_id,status,resolver,resolved_at) VALUES (?,?,?,?,?,?)",
                   (psid, raw, place_id, "accepted", "ai:nominatim-resolver@0.1.0", ts))
        return psid
    ps_pa, ps_phila, ps_pitt = mk_string("Pennsylvania", pa), mk_string("Philadelphia, Pennsylvania", phila), mk_string("Pittsburgh, Pennsylvania", pittsburgh)
    ext_id = treelib.ulid()
    cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (ext_id, "human", "harness", "0.1.0", ts))
    src = cx.execute("SELECT id, trust_tier, terms FROM source LIMIT 1").fetchone()
    def mk_event(tag, *psids):
        pid = treelib.ulid()
        cx.execute("INSERT INTO person (id,tree_id,display_name,created_at,updated_at) VALUES (?,?,?,?,?)", (pid, tid, f"Chain {tag}", ts, ts))
        eid = treelib.ulid()
        cx.execute("INSERT INTO event (id,tree_id,event_type,created_at,updated_at) VALUES (?,?,?,?,?)", (eid, tid, "Residence", ts, ts))
        cx.execute("INSERT INTO event_participant (id,event_id,person_id,role) VALUES (?,?,?,?)", (treelib.ulid(), eid, pid, "primary"))
        sha, _ = treelib.archive_object(cx, f"chain-{tag}".encode(), mime="text/html", source_id=src[0], collection_id=None,
                                        locator_kind="url", locator_value=f"http://example.test/{tag}", retrieved_by=BY, terms=src[2], cost="free", trust_tier=src[1])
        xid = treelib.ulid()
        cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,status,ran_at) VALUES (?,?,?,?,?)", (xid, sha, ext_id, "complete", ts))
        persid = treelib.ulid()
        cx.execute("INSERT INTO persona (id,extraction_id,artifact_sha256,sequence,name_text) VALUES (?,?,?,?,?)", (persid, xid, sha, 1, f"Chain {tag}"))
        for psid in psids:
            pfid = treelib.ulid()
            cx.execute("INSERT INTO persona_fact (id,persona_id,fact_type,place_string_id) VALUES (?,?,?,?)", (pfid, persid, "Residence", psid))
            cx.execute("INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,status,asserted_by,asserted_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (treelib.ulid(), tid, "event", eid, pfid, sha, "accepted", BY, ts))
        return eid
    ev_chain = mk_event("chain", ps_pa, ps_phila)
    ev_split = mk_event("split", ps_phila, ps_pitt)
    cx.commit()
    return ev_chain, ev_split, phila

def place_fallback_depth(keep):
    """Catalog.place's fallback, among the place strings on accepted assertions, prefers the one resolved to the
    deepest place over the alphabet — before any filler has run, an event with an accepted state and an accepted city
    in that state already shows the city, Philadelphia, not "Pennsylvania" sorting first."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from catalog import Catalog
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "chaintest", "--name", "Chain Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='chaintest'").fetchone()[0]
    ev_chain, ev_split, phila = _chain_fixture(cx, tid, treelib.now())
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    cat = Catalog(cx, tid)
    shown = cat.place(ev_chain, None)
    fail(shown and shown["text"].split(" < ")[0] == "Philadelphia",
         f"a state and the city in it on one event show the deepest, Philadelphia, never the alphabet: {shown}")
    cx.close()
    if not keep: shutil.rmtree(d, ignore_errors=True)
    return fails

def chain_fill(keep):
    """apply_to_events fills an event from facts on one chain (a state, the county in it, the city in that county) at
    its most specific point, and leaves facts on different chains (two cities in the same state) unfilled."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from resolve_places import apply_to_events
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "chaintest", "--name", "Chain Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='chaintest'").fetchone()[0]
    ev_chain, ev_split, phila = _chain_fixture(cx, tid, treelib.now())
    apply_to_events(cx, tid, BY, treelib.now()); cx.commit()
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    fail(cx.execute("SELECT place_id FROM event WHERE id=?", (ev_chain,)).fetchone()[0] == phila,
         f"a state and the city in it agree; the event takes the most specific, Philadelphia: {cx.execute('SELECT place_id FROM event WHERE id=?', (ev_chain,)).fetchone()}")
    fail(cx.execute("SELECT place_id FROM event WHERE id=?", (ev_split,)).fetchone()[0] is None,
         f"Philadelphia and Pittsburgh are different chains under the same state; the event stays unplaced: {cx.execute('SELECT place_id FROM event WHERE id=?', (ev_split,)).fetchone()}")
    cx.close()
    if not keep: shutil.rmtree(d, ignore_errors=True)
    return fails

def turn_check(keep):
    """tools/queue.py and tools/turn.py on tests/fixtures/harness.ged. The queue names James Joseph Ahearn first: the home
    person's own parent, the file's claim, not yet accepted. Charlotte D Lukens's six vouchable key facts (name, sex,
    birth, death, spouses, children; she has no parents claimed) are accepted so her plan opens searches, then a turn on
    her: plan, every step a connector can run (the network faked: the first step's source does not answer and logs
    'error', the rest answer nothing and log 'none'; the turn keeps going, never stopping on a source that did not
    answer), the assisted fetch list she still has, the turn's own state kept beside the database (nothing written to
    the catalog by pausing) naming the source that did not answer, no state once nothing is left to fetch. The step
    logged error is still runnable (an error is no run on its fields; queue_pass_over_check has the queue's side of it,
    on a person at the edge), the steps logged none are not, and a none run after the error closes it.
    Then a page dropped into the inbox as a save would leave it, and --resume: fetches.py collect, attach_inbox.py,
    reconsider, the plan regenerated, the state file cleared, and the file's identity read even though it answers no
    step of hers (an unrelated fixture), reported as left in the inbox."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    import importlib.util
    spec = importlib.util.spec_from_file_location("tree_queue", os.path.join(ROOT, "tools", "queue.py"))
    tree_queue = importlib.util.module_from_spec(spec); spec.loader.exec_module(tree_queue)   # not "import queue": that shadows the stdlib module
    import turn, run_step, fetches as fetches_mod
    from facts import decide_fact
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "harness", "--name", "Harness")
    run(os.path.join(ROOT, "tools", "ingest_gedcom.py"), os.path.join(FIXTURES, "harness.ged"), "--keep", "--db", db, "--tree", "harness", "--by", BY)
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "home", "Frederick Michael Ahearn", "--tree", "harness")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='harness'").fetchone()[0]
    slug = "harness"
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    say = (lambda *a: print("    ", *a)) if keep else (lambda *a: None)

    q, passed_over = tree_queue.edge(cx, tid)
    fail(bool(q) and q[0]["name"] == "James Joseph Ahearn" and "parent" in q[0]["reason"] and "not yet accepted" in q[0]["reason"],
         f"the queue names the home person's own unconfirmed parent first: {q[:1]}")
    fail(passed_over == [], f"nobody has been planned yet, so nobody is passed over as settled but for the owner alone: {passed_over}")

    pid = cx.execute("SELECT id FROM person WHERE tree_id=? AND display_name='Charlotte D Lukens'", (tid,)).fetchone()[0]
    for field in ("name", "sex", "birth", "death", "spouses", "children"):
        res = decide_fact(cx, tid, pid, field, "accepted", "harness: vouch, to open her searches", BY); cx.commit()
        fail(res.get("ok"), f"{field} accepted on Charlotte D Lukens's own word: {res}")

    before_people = turn.person_ids(cx, tid)
    # a fake in place of run_step.run itself, on the pattern of check.py's own fake connectors elsewhere: turn.py's own
    # orchestration (iterate the person's runnable steps, run each, commit) is what this check is about, not run_step.py's
    # network layer, which tools/check.py already checks on its own (rules(), connectors_offline(), decisions()).
    real_run = run_step.run; seen_steps = []
    def fake_run(cx_, cat_, tree_id_, step_, by_, dry_run=False):
        seen_steps.append(step_["id"])
        from log_search import log as log_search
        outcome = "error" if len(seen_steps) == 1 else "none"; errors = ["https://faked.example/search: timed out"] if outcome == "error" else []
        lid = log_search(cx_, tree_id_, by_, step_id=step_["id"], source_id=None, outcome=outcome, artifacts=None, note="harness: faked, no network", query=json.loads(step_["query_json"] or "{}"))
        return [{"connector": "fake", "query": {}, "outcome": outcome, "log": lid, "artifacts": [], "hits": [], "errors": errors, "household_steps": [], "extracted": []}]
    run_step.run = fake_run
    try:
        turn.start(cx, tid, slug, pid, BY, db)
    finally:
        run_step.run = real_run
    steps = cx.execute("SELECT id FROM search_plan WHERE person_id=? AND kind='search' AND mode='auto'", (pid,)).fetchall()
    fail(len(steps) >= 1, "the plan opens at least one auto search step once her baseline is reviewed")
    fail(len(seen_steps) >= 2 and len(seen_steps) == len(set(seen_steps)), f"turn.py ran every one of her runnable steps once each, one commit apiece: {seen_steps}")
    logged = cx.execute("""SELECT GROUP_CONCAT(l.outcome) FROM search_log l WHERE l.plan_step_id IN ({}) ORDER BY l.id""".format(",".join("?" * len(seen_steps))), seen_steps).fetchone()[0] if seen_steps else ""
    fail(sorted((logged or "").split(",")) == sorted(["error"] + ["none"] * (len(seen_steps) - 1)), f"each run it took is logged, exactly as run_step.run reports it: {logged}")
    st = turn.load_state(db)
    fail(st is not None and st["person_id"] == pid, f"the turn paused on her assisted fetch list with its own state kept beside the database: {st}")
    # ---- an error run is a source that did not answer, not a run on the step's fields: the step stays runnable, the queue names her on it, the state names the source
    from catalog import Catalog as _Catalog
    cat_h = _Catalog(cx, tid)
    errored = cx.execute("SELECT * FROM search_plan WHERE id=?", (seen_steps[0],)).fetchone() if seen_steps else None
    src_name = cx.execute("SELECT s.name FROM search_log l JOIN source s ON s.id=l.source_id WHERE l.plan_step_id=? AND l.outcome='error'", (seen_steps[0],)).fetchone() if seen_steps else None
    fail(errored is not None and errored["id"] in {r["id"] for r in run_step.runnable(cx, cat_h, tid)}, "the step whose latest run is an error is still runnable: the source did not answer")
    fail(seen_steps[1:] and not ({sid for sid in seen_steps[1:]} & {r["id"] for r in run_step.runnable(cx, cat_h, tid)}), "the steps logged none on these fields are not runnable")
    fail(st is not None and len(st.get("unanswered") or []) == 1 and src_name and src_name[0] in st["unanswered"][0] and "did not answer" in st["unanswered"][0] and "timed out" in st["unanswered"][0],
         f"the paused turn's state names the source that did not answer, by the registry's name, with what it said: {st and st.get('unanswered')}")
    from log_search import log as log_none
    log_none(cx, tid, BY, step_id=seen_steps[0], outcome="none", note="harness: the source answered on the second ask", query=json.loads(errored["query_json"] or "{}")); cx.commit()
    fail(errored["id"] not in {r["id"] for r in run_step.runnable(cx, cat_h, tid)}, "a none run on the same fields after the error closes the step")
    fail(not cx.execute("SELECT 1 FROM search_plan WHERE person_id=? AND kind='fetch' AND mode='fetch' AND status='planned'", (pid,)).fetchall() == [], "she still has an assisted fetch step waiting, or there was nothing to pause on")

    import shutil as _sh
    os.makedirs(treelib.inbox_dir(), exist_ok=True)
    _sh.copy(os.path.join(FIXTURES, "familysearch-census-1940-KQX1-VT9.html"), os.path.join(treelib.inbox_dir(), "familysearch-census-1940-KQX1-VT9.html"))
    import contextlib, io as _io
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf): turn.resume(cx, tid, slug, BY, db)
    resumed = buf.getvalue()
    fail(turn.load_state(db) is None, "the state file is cleared once a turn is resumed")
    fail("left:" in resumed and src_name and f"{src_name[0]}" in resumed.split("left:", 1)[1] and "the next turn asks it again" in resumed.split("left:", 1)[1],
         f"the resumed turn's report still names the source that did not answer, under left, so the next turn asks it again:\n{resumed}")
    left_row = cx.execute("SELECT 1 FROM artifact_locator WHERE kind='ark' AND value='ark:/61903/1:1:KQX1-VT9'").fetchone()
    fail(left_row is None, "an unrelated fixture, saved by hand into the inbox, is read for its identity and left there: it fulfils none of her steps")
    fail(os.path.isfile(os.path.join(treelib.inbox_dir(), "familysearch-census-1940-KQX1-VT9.html")), "the unmatched file stays in the inbox, not filed under the tree")

    after_people = turn.person_ids(cx, tid)
    fail(after_people.keys() >= before_people.keys(), "a turn creates people through the existing tools only; none vanish")
    st2 = {k: v for k, v in [(p, __import__("plan").plan_person(cx, tid, p, BY)) for p in (pid,)]}; cx.commit()
    fail(all(v["steps_new"] == 0 and v["steps_dropped"] == 0 for v in st2.values()), f"the plan turn.py itself regenerated is already settled, idempotent: {st2}")
    ok = cx.execute("PRAGMA integrity_check").fetchone()[0]; fk = cx.execute("PRAGMA foreign_key_check").fetchall()
    fail(ok == "ok" and not fk, f"scratch catalog: integrity {ok}, foreign keys {len(fk)}")
    cx.close()
    if keep: print("turn scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def attach_collection_check(keep):
    """The attach fallback that matches a page to a step by the row's kind and the person's name (tools/attach.py
    _steps_by_kind) must also require the page's own collection to be the citation's own holder collection
    (data/holders.csv): two citations of one row at the same holder (the Kentucky and Ohio death indexes, both
    FamilySearch, D03) are not each other's record, and a page of neither citation's collection matches nothing."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from treelib import now as tnow, ulid as tulid, dumps as tdumps
    from attach import _steps_by_kind
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "colltest", "--name", "Collision Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='colltest'").fetchone()[0]
    ts = tnow(); pid = tulid()
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tid, "M", "John Test", ts, ts))
    cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (tulid(), pid, "John", "Test", "test, john"))
    def step(apid, source_id):
        sid = tulid()
        cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,sources_json,mode,status,created_at)
                      VALUES (?,?,?,1,?,'fetch','subject_record',?,?,'apid',?,?,'fetch','planned',?)""",
                   (sid, pid, "death record:1946", f"fetch:{apid}", tdumps({}), source_id, apid, tdumps([source_id]), ts))
        return sid
    ky_step = step("1,3077::111", "D03")            # Kentucky, U.S., Death Index, 1911-2000
    oh_step = step("1,5763::222", "D03")             # Ohio, U.S., Death Records, 1908-1932, 1938-2022; same holder, a different collection
    cx.commit()
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    ky_parsed = {"fields": [("Event Type", "Death"), ("Event Date", "1946")], "collection": "Vital • Kentucky, Vital Record Indexes, 1911-1999", "name": "John Test"}
    got = [g["id"] for g in _steps_by_kind(cx, tid, ky_parsed)]
    fail(got == [ky_step], f"a Kentucky death index page matches only the Kentucky citation's step, never the Ohio one at the same holder: {got}")
    oh_parsed = {**ky_parsed, "collection": "Vital • Ohio, Deaths, 1908-1953"}
    got = [g["id"] for g in _steps_by_kind(cx, tid, oh_parsed)]
    fail(got == [oh_step], f"an Ohio death index page matches only the Ohio citation's step: {got}")
    other_parsed = {**ky_parsed, "collection": "Vital • Some Other State, Deaths"}
    got = [g["id"] for g in _steps_by_kind(cx, tid, other_parsed)]
    fail(got == [], f"a page of a collection neither citation names matches nothing: {got}")
    cx.close()
    if keep: print("attach collection scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def attach_none_check(keep):
    """docs/RESEARCH-WORKFLOW.md §4: 'No fit at all sets the run to none.' A results page saved for a fetch step's own search
    (its citation has no record id at the holder, so tools/fetches.py collect attaches the page by the name the list printed,
    kind="page", not by the page's own search identity) must set the run to none the same way a page attached by that
    identity already does, whichever step the page's rows fit nobody on."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from treelib import now as tnow, ulid as tulid, dumps as tdumps, inbox_dir
    from attach import attach
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "nonetest", "--name", "None Run Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='nonetest'").fetchone()[0]
    ts = tnow(); pid = tulid()
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tid, "F", "Jane Test", ts, ts))
    cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (tulid(), pid, "Jane", "Test", "test, jane"))
    sid = tulid()                                     # a marriage record fetch step: the citation carries no ark to open directly, so it is searched at the holder by hand
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,sources_json,mode,status,created_at)
                  VALUES (?,?,'marriage record:1950',1,'fetch:1,999::123','fetch','subject_record',?,'D03','apid','1,999::123','["D03"]','fetch','planned',?)""",
               (sid, pid, tdumps({}), ts))
    cx.commit()
    fname = "familysearch-marriage-index-results-nonetest.html"
    with open(os.path.join(inbox_dir(), fname), "w", encoding="utf-8") as fh:
        fh.write('<!-- saved from https://www.familysearch.org/en/search/record/results?q.givenName=Zelda&q.surname=Quorum&f.collectionId=9999999 -->\n'
                  '<html><body><table><tr data-testid="/ark:/61903/1:1:ZZZZ-9999"><td>1</td>'
                  '<td><a href="/ark:/61903/1:1:ZZZZ-9999?lang=en">Zelda Quorum</a></td><td></td></tr></table></body></html>')
    step = cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,)).fetchone()
    cx.execute("BEGIN")
    res = attach(cx, tid, "nonetest", fname, [step], BY, note="saved in the browser under the fetch list's name at FamilySearch record collections",
                 kind="page", value="https://www.familysearch.org/en/search/record/results?q.givenName=Zelda&q.surname=Quorum")
    cx.commit()
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    fail(res["proposals"] == [], f"the page's one row (Zelda Quorum) fits nobody in this tree: {res['proposals']}")
    fail(res.get("outcome") == "none", f"no candidate fits, so the run the page was saved for is none, not found: {res}")
    log = cx.execute("SELECT outcome, notes FROM search_log WHERE plan_step_id=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    fail(log and log["outcome"] == "none" and "no candidate fits" in (log["notes"] or ""), f"the step's own log row reads none, the reason in its note: {log and tuple(log)}")
    cx.close()
    if keep: print("attach none scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def run_none_check(keep):
    """docs/RESEARCH-WORKFLOW.md §4: 'No fit at all sets the run to none.' A connector's run whose records are results
    listings (extract.RESULTS_LISTINGS) is found only when a row fits a person: the New Jersey death index connector, its
    download faked, answers a death record search on a surname whose rows fit nobody in the tree with a none run, the reason
    in the note, the rows kept on the artifact and the step planned as before; the same connector on a person born 1901,
    whose row carries that year, with a card, a found run and the step done."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    import run_step
    from treelib import now as tnow, ulid as tulid, dumps as tdumps
    from catalog import Catalog
    from connectors import nj_death_index
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "runnone", "--name", "Run None Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='runnone'").fetchone()[0]
    ts = tnow(); steps = {}
    for given, surname, birth in (("Jane", "Quorum", None), ("Zelda", "Fitwell", 1901)):
        pid = tulid()
        cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tid, "F", f"{given} {surname}", ts, ts))
        cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (tulid(), pid, given, surname, f"{surname.lower()}, {given.lower()}"))
        query = {"given": {"value": given, "basis": "accepted"}, "surname": {"value": surname, "basis": "accepted"}}
        if birth:
            eid = tulid(); cx.execute("INSERT INTO event (id,tree_id,event_type,date_text,date_start,created_at,updated_at) VALUES (?,?,'Birth',?,?,?,?)", (eid, tid, str(birth), str(birth), ts, ts))
            cx.execute("INSERT INTO event_participant (id,event_id,person_id,role) VALUES (?,?,?,'primary')", (tulid(), eid, pid))
            query["birth_year"] = {"value": str(birth), "basis": "claim"}
        sid = tulid()
        cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                      VALUES (?,?,'death record:',1,'search:death record','search','subject_record',?,'["C09"]','auto','planned',?)""", (sid, pid, tdumps(query), ts))
        steps[surname] = (pid, sid)
    cx.commit()
    body = ",".join(nj_death_index.FIELDS).encode() + b"\nZelda,Quorum,,1,1930,1,2,Newark,NJ,USA,2010,3,4,NJ\nZelda,Fitwell,,2,1901,5,6,Newark,NJ,USA,1990,7,8,NJ\n"
    def fake_fetch(url, kind, c, data=None):
        return body, {"status": 200, "etag": None, "last_modified": None, "final_url": url, "content_type": "text/csv"}
    orig_fetch = run_step.fetch; run_step.fetch = fake_fetch
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    try:
        cat = Catalog(cx, tid)
        for surname in ("Quorum", "Fitwell"):
            step = cx.execute("SELECT * FROM search_plan WHERE id=?", (steps[surname][1],)).fetchone()
            fail(step["status"] == "planned" and [c.__name__.split(".")[-1] for c in run_step.connectors_for(cat, step)] == ["nj_death_index"], f"the death record search step on {surname} runs at the death index")
            cx.execute("BEGIN"); res = run_step.run(cx, cat, tid, step, BY); cx.commit()
            r = res[0] if res else {}
            log = cx.execute("SELECT outcome, notes, artifacts_json FROM search_log WHERE plan_step_id=? ORDER BY id DESC LIMIT 1", (step["id"],)).fetchone()
            status = cx.execute("SELECT status FROM search_plan WHERE id=?", (step["id"],)).fetchone()[0]
            personas = cx.execute("SELECT COUNT(*) FROM persona pe JOIN extraction e ON e.id=pe.extraction_id WHERE e.id=?", ((r.get("extracted") or [{}])[0].get("extraction"),)).fetchone()[0]
            if surname == "Quorum":
                fail(r.get("outcome") == "none" and log and log["outcome"] == "none" and (log["notes"] or "").startswith("no candidate fits; 1 row(s) under Quorum"),
                     f"the one Quorum row (born 1930) fits nobody: the run is none, the reason first in its note: {r.get('outcome')}, {log and tuple(log)}")
                fail(status == "planned", f"a none run leaves the step planned: {status}")
                fail(personas == 1 and (r.get("extracted") or [{}])[0].get("proposals") == 0, f"the row stays on the artifact as a candidate, no card: {personas} persona(s), {r.get('extracted')}")
                fail(bool(log and log["artifacts_json"] and len(json.loads(log["artifacts_json"])) == 2), f"the run keeps the whole file and the surname's derivative as its artifacts: {log and log['artifacts_json']}")
            else:
                fail(r.get("outcome") == "found" and log and log["outcome"] == "found" and (log["notes"] or "").startswith("1 row(s) under Fitwell"),
                     f"the Fitwell row, born 1901 like the tree's Zelda Fitwell, fits: a found run: {r.get('outcome')}, {log and tuple(log)}")
                fail(status == "done", f"a found run marks the step done: {status}")
                fail((r.get("extracted") or [{}])[0].get("proposals") == 1, f"one card, the persona match for her: {r.get('extracted')}")
    finally:
        run_step.fetch = orig_fetch
    cx.close()
    if keep: print("run none scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def run_wants_check(keep):
    """A search step its connectors cannot ask: a person with a name and nothing else, on a compiled-genealogy step at the
    Archive's books (L02) and WikiTree (B04), run once with no network. Each connector logs a none run with no request, the
    note naming the field it wanted (a state; a birth or death year); the step is not runnable after, and the queue passes
    the person over. Once the plan writes the field wanted, the step is runnable again."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    import run_step
    from treelib import now as tnow, ulid as tulid, dumps as tdumps
    from catalog import Catalog
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "wantstest", "--name", "Wants Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='wantstest'").fetchone()[0]
    ts = tnow(); home_id, parent_id = tulid(), tulid()
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (home_id, tid, "F", "Home Person", ts, ts))
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (parent_id, tid, "M", "Nameonly Parent", ts, ts))
    cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (tulid(), parent_id, "Nameonly", "Parent", "parent, nameonly"))
    cx.execute("UPDATE tree SET home_person_id=? WHERE id=?", (home_id, tid))
    fid = tulid(); cx.execute("INSERT INTO family (id,tree_id,rel_type,created_at,updated_at) VALUES (?,?,'unknown',?,?)", (fid, tid, ts, ts))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid, parent_id))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'child')", (fid, home_id))
    sid = tulid()
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                  VALUES (?,?,'compiled genealogy / family history:',1,'search:compiled','search','name',?,'["L02","B04"]','auto','planned',?)""",
               (sid, parent_id, tdumps({"given": {"value": "Nameonly", "basis": "accepted"}, "surname": {"value": "Parent", "basis": "accepted"}}), ts))
    cx.commit()
    def no_fetch(url, kind, c, data=None): raise AssertionError(f"a request went out: {url}")
    orig_fetch = run_step.fetch; run_step.fetch = no_fetch
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    import importlib.util
    spec = importlib.util.spec_from_file_location("tree_queue3", os.path.join(ROOT, "tools", "queue.py"))
    tree_queue = importlib.util.module_from_spec(spec); spec.loader.exec_module(tree_queue)
    try:
        cat = Catalog(cx, tid)
        step = cx.execute("SELECT * FROM search_plan WHERE id=?", (sid,)).fetchone()
        fail([c.__name__.split(".")[-1] for c in run_step.connectors_for(cat, step)] == ["ia_books", "wikitree"], "the step runs at the Archive's books and WikiTree")
        fail(sid in {r["id"] for r in run_step.runnable(cx, cat, tid)}, "with no run, the step is runnable")
        out, passed = tree_queue.edge(cx, tid)
        fail(any(e["id"] == parent_id for e in out), f"the parent is named on it: {out}")
        cx.execute("BEGIN"); res = run_step.run(cx, cat, tid, step, BY); cx.commit()
        fail([(r.get("connector"), r.get("outcome"), r.get("requests"), r.get("wants")) for r in res] == [("ia_books", "none", [], "a state"), ("wikitree", "none", [], "a birth or death year")],
             f"each connector is a none run with no request, naming the field it wanted: {[(r.get('connector'), r.get('outcome'), r.get('requests'), r.get('wants'), r.get('error')) for r in res]}")
        rows = cx.execute("SELECT source_id, outcome, notes, artifacts_json FROM search_log WHERE plan_step_id=? ORDER BY id", (sid,)).fetchall()
        fail([(r["source_id"], r["outcome"], r["artifacts_json"]) for r in rows] == [("L02", "none", None), ("B04", "none", None)], f"one log row per connector under its own source, none, no artifact: {[tuple(r) for r in rows]}")
        fail(rows and "it wants a state" in (rows[0]["notes"] or "") and "it wants a birth or death year" in (rows[1]["notes"] or ""), f"the notes name the field: {[r['notes'] for r in rows]}")
        fail(cx.execute("SELECT status FROM search_plan WHERE id=?", (sid,)).fetchone()[0] == "planned", "the step stays planned")
        fail(sid not in {r["id"] for r in run_step.runnable(cx, cat, tid)}, "run once on these fields, the step is not runnable again")
        out, passed = tree_queue.edge(cx, tid)
        fail(any(e["id"] == parent_id for e in passed) and not any(e["id"] == parent_id for e in out), f"the parent is passed over: {passed}")
        cx.execute("UPDATE search_plan SET query_json=? WHERE id=?", (tdumps({"given": {"value": "Nameonly", "basis": "accepted"}, "surname": {"value": "Parent", "basis": "accepted"}, "birth_year": {"value": "1880", "basis": "accepted"}}), sid)); cx.commit()
        fail(sid in {r["id"] for r in run_step.runnable(cx, cat, tid)}, "once the plan writes a birth year, the step is runnable again")
        fail(any(e["id"] == parent_id for e in tree_queue.edge(cx, tid)[0]), "and the parent is named again")
    finally:
        run_step.fetch = orig_fetch
    cx.close()
    if keep: print("run wants scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def results_for_fetch_check(keep):
    """A results page saved for a fetch step's own search at the holder (the citation carries no record id of the holder's
    to open): tools/attach.py tells it from a record page by the parser that claims it, never the file name, and attaches
    it to the fetch steps whose citation's collection has the page's collection as a holder (data/holders.csv) and whose
    name is the name searched, as the run's own artifact with the query as run: none when no row fits the person, found
    when one does. The Kentucky death-records search for Lena Howard Bell names her once, as a mother with no dates, so
    nothing fits, the run is none and the twenty rows stay on the artifact; the same page saved again is a repeat and stays
    in the inbox. On a second scratch where the tree's Lena Bell was born 1884, the row Lena W. Bell, born 1884 and died
    1941, fits on the surname and birth year: a card, a found run, the step done."""
    from treelib import now as tnow, ulid as tulid, dumps as tdumps
    fname = "familysearch-kentucky-death-records-1918-results-P1P2YM.html"
    url = "https://www.familysearch.org/en/search/record/results?f.collectionId=1417491&q.givenName=Lena%20Howard&q.surname=Bell"
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    def build(birth_year):
        d, db = scratch(keep)
        import treelib; treelib.DATA_ROOT = d
        from attach import attach_inbox
        run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "resultstest", "--name", "Results Test")
        cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
        tid = cx.execute("SELECT id FROM tree WHERE slug='resultstest'").fetchone()[0]
        ts = tnow(); pid = tulid()
        cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tid, "F", "Lena Howard Bell", ts, ts))
        cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (tulid(), pid, "Lena Howard", "Bell", "bell, lena howard"))
        if birth_year:
            eid = tulid(); cx.execute("INSERT INTO event (id,tree_id,event_type,date_text,date_start,created_at,updated_at) VALUES (?,?,'Birth',?,?,?,?)", (eid, tid, str(birth_year), str(birth_year), ts, ts))
            cx.execute("INSERT INTO event_participant (id,event_id,person_id,role) VALUES (?,?,?,'primary')", (tulid(), eid, pid))
        sid = tulid()                                     # the citation at Ancestry's Kentucky death records (dbid 1222), fetched at FamilySearch by its own search
        cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,sources_json,mode,status,created_at)
                      VALUES (?,?,'death record:1918',1,'fetch:1,1222::1373711','fetch','subject_record',?,'D03','apid','1,1222::1373711','["C03"]','fetch','planned',?)""",
                   (sid, pid, tdumps({"name": {"value": "Lena Howard Bell", "basis": "citation"}, "collection": {"value": "Kentucky, U.S., Death Records, 1852-1965", "basis": "citation"}}), ts))
        cx.commit()
        os.makedirs(treelib.inbox_dir(), exist_ok=True)
        shutil.copy(os.path.join(FIXTURES, "familysearch-search-kentucky-deaths-bell-lena-howard.html"), os.path.join(treelib.inbox_dir(), fname))
        cx.execute("BEGIN"); res = attach_inbox(cx, tid, "resultstest", BY); cx.commit()
        return d, db, cx, tid, pid, sid, res, treelib.inbox_dir(), attach_inbox
    d, db, cx, tid, pid, sid, res, inbox, attach_inbox = build(None)
    r = res[0] if res else {}
    fail(len(res) == 1 and (r.get("identity") or "").startswith("fs_search ") and not r.get("left"), f"the page is read as a FamilySearch results page by its own markup and attached: {res}")
    fail([x[0] for x in r.get("steps") or []] == [sid] and "citation's own search" in ((r.get("steps") or [[None] * 4])[0][3] or ""), f"it fulfils the fetch step whose citation was searched for by this name in this collection: {r.get('steps')}")
    fail(r.get("proposals") == [] and r.get("outcome") == "none", f"the page names her only as a mother with no dates, so no row fits and the run is none: {r.get('proposals')}, {r.get('outcome')}")
    log = cx.execute("SELECT outcome, notes, query_json, artifacts_json FROM search_log WHERE plan_step_id=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    fail(log and log["outcome"] == "none" and "no candidate fits" in (log["notes"] or "") and "529 matching records" in (log["notes"] or "") and json.loads(log["query_json"]).get("q.surname", {}).get("value") == "Bell" and r.get("sha256") in (log["artifacts_json"] or ""),
         f"the step's log row: none, the reason and the count in its note, the query as run, the page as its artifact: {log and tuple(log)}")
    art = cx.execute("SELECT source_id, locator_kind, locator_value FROM artifact WHERE sha256=?", (r.get("sha256"),)).fetchone()
    fail(art and art["source_id"] == "D03" and art["locator_kind"] == "url" and art["locator_value"] == url, f"archived under FamilySearch with the search URL as locator: {art and tuple(art)}")
    fail(cx.execute("SELECT status FROM search_plan WHERE id=?", (sid,)).fetchone()[0] == "planned", "a none run leaves the step planned")
    fail(cx.execute("SELECT COUNT(*) FROM persona WHERE artifact_sha256=?", (r.get("sha256"),)).fetchone()[0] == 20, "the twenty rows stay on the artifact as candidates")
    fail(not os.path.exists(os.path.join(inbox, fname)), "the page leaves the inbox, filed under the tree")
    again = "familysearch-kentucky-death-records-1918-results-again-P1P2YM.html"                # the same search saved once more: the same rows, other bytes
    with open(os.path.join(FIXTURES, "familysearch-search-kentucky-deaths-bell-lena-howard.html"), "rb") as fh: data = fh.read()
    with open(os.path.join(inbox, again), "wb") as fh: fh.write(data + b"\n")
    cx.execute("BEGIN"); res2 = attach_inbox(cx, tid, "resultstest", BY); cx.commit()
    fail(len(res2) == 1 and "repeat" in (res2[0].get("left") or ""), f"the same search saved again, with the same rows, is a repeat and is left in the inbox: {res2}")
    fail(os.path.exists(os.path.join(inbox, again)) and cx.execute("SELECT COUNT(*) FROM search_log WHERE plan_step_id=?", (sid,)).fetchone()[0] == 1, "the repeat stays in the inbox and logs no second run")
    cx.close()
    if keep: print("results-for-fetch scratch (none) kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    d, db, cx, tid, pid, sid, res, inbox, attach_inbox = build(1884)
    r = res[0] if res else {}
    fail(len(res) == 1 and not r.get("left") and r.get("outcome") != "none" and len(r.get("proposals") or []) >= 1, f"with a birth year of 1884 in the tree, the row Lena W. Bell (born 1884) fits and the run is found: {res}")
    props = [json.loads(pj) for pj, in cx.execute("SELECT payload_json FROM proposal WHERE tree_id=? AND kind='persona_match'", (tid,))]
    fail(any(p.get("person_id") == pid for p in props), f"the card is a persona match for Lena Howard Bell herself: {props}")
    fail(all(cx.execute("SELECT status FROM proposal WHERE tree_id=?", (tid,)).fetchone()[0] == "undecided" for _ in [0]), "the rule takes nothing on a tree with no accepted fact: the card is the owner's")
    log = cx.execute("SELECT outcome FROM search_log WHERE plan_step_id=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    fail(log and log["outcome"] == "found" and cx.execute("SELECT status FROM search_plan WHERE id=?", (sid,)).fetchone()[0] == "done", f"a found run, the step done: {log and tuple(log)}")
    cx.close()
    if keep: print("results-for-fetch scratch (found) kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def run_step_all_check(keep):
    """tools/run_step.py --all reads runnable steps fresh before each run, as tools/turn.py has since re-reading a person's
    own plan before each connector run: a step's own run can regenerate the plan in the same request and drop a later step
    already queued, or open a new one, and a stale id must never be run. A SystemExit escaping a step's own run (the shape
    of log_search.py's own guard when a step id no longer exists) must roll that step's transaction back and re-raise, not
    crash the loop with an open transaction."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from treelib import now as tnow, ulid as tulid
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "allrun", "--name", "All Run Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='allrun'").fetchone()[0]
    ts = tnow(); pid = tulid()
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tid, "M", "Al Test", ts, ts))
    def step(key, seq, row_key=None):
        sid = tulid()
        cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                      VALUES (?,?,?,?,?,'search','name','{}','["H01"]','auto','planned',?)""", (sid, pid, row_key or f"footprint:{key}", seq, key, ts))
        return sid
    keep_step, drop_step = step("keep", 1), step("drop", 2)
    cx.commit()
    import run_step
    orig_run, orig_connectors_for = run_step.run, run_step.connectors_for
    run_step.connectors_for = lambda cat, st: [True]              # every planned search step runnable here, no real connector needed
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    try:
        calls, new_sid = [], []
        def fake_run(cx_, cat_, tree_id_, st_, by_, dry_run=False):
            calls.append(st_["id"])
            if st_["id"] == keep_step:                            # this step's own run regenerates the plan: drops "drop", opens "new"
                cx_.execute("DELETE FROM search_plan WHERE id=?", (drop_step,))
                sid = tulid(); new_sid.append(sid)
                cx_.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                              VALUES (?,?,'footprint:new',3,'new','search','name','{}','["H01"]','auto','planned',?)""", (sid, pid, tnow()))
            return []
        run_step.run = fake_run
        old_argv = sys.argv; sys.argv = ["run_step.py", "--all", "--db", db, "--tree", "allrun", "--by", BY]
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()): run_step.main()
        sys.argv = old_argv
        fail(calls == [keep_step] + new_sid, f"the step read before the regeneration runs, the one it dropped never does, the one it opened still gets its own turn: {calls}, new {new_sid}")
        fail(not cx.execute("SELECT 1 FROM search_plan WHERE id=?", (drop_step,)).fetchone(), "the dropped step is really gone")
        # ---- a step whose own run raises SystemExit (log_search.py's guard on a step id no longer there): the transaction rolls back, the exception still propagates
        cx.execute("DELETE FROM search_plan WHERE person_id=?", (pid,))   # fake_run never marks a step done, so nothing from the first scenario is planned to steal boom_step's own turn
        boom_step = step("boom", 1); cx.commit()
        def boom_run(cx_, cat_, tree_id_, st_, by_, dry_run=False):
            cx_.execute("UPDATE search_plan SET status='done' WHERE id=?", (st_["id"],))   # a write inside the same transaction, that must not survive
            raise SystemExit("no step " + st_["id"])
        run_step.run = boom_run
        sys.argv = ["run_step.py", "--all", "--db", db, "--tree", "allrun", "--by", BY]
        raised = False
        try:
            with contextlib.redirect_stdout(io.StringIO()): run_step.main()
        except SystemExit: raised = True
        finally: sys.argv = old_argv
        fail(raised, "a SystemExit from a step's own run still stops the run: it is not silently swallowed")
        fail(cx.execute("SELECT status FROM search_plan WHERE id=?", (boom_step,)).fetchone()[0] == "planned", "its write does not survive: the transaction rolled back before the exception was re-raised")
    finally:
        run_step.run, run_step.connectors_for = orig_run, orig_connectors_for
    cx.close()
    if keep: print("run_step --all scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def queue_pass_over_check(keep):
    """tools/queue.py's edge() names the next person a turn can act on, passing over one whose only open work is the
    owner's alone: already planned, with no step left a turn can advance. The home person, fully planned with nothing
    left to run, a document still undecided: passed over. Her own unconfirmed parent, with a runnable auto search step
    still planned: still named next, not passed over, though his link is the very same shape of open question (a claim
    not yet accepted). Then the test itself: once that step is logged none on the very fields it carries, the parent is
    passed over (the same query again is not a turn's work); once the plan writes new fields, named again; logged error on
    those fields (the source did not answer), still named; logged none on them after that, passed over. A second
    parent whose only step is an assisted search with no link to open is passed over from the start. A spouse whose
    only step is a memorial page on the fetch list, with a link: named; logged none on unchanged fields: passed over."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from treelib import now as tnow, ulid as tulid, dumps as tdumps
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "queuetest", "--name", "Queue Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='queuetest'").fetchone()[0]
    ts = tnow(); home_id, parent_id = tulid(), tulid()
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (home_id, tid, "F", "Home Person", ts, ts))
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (parent_id, tid, "M", "Unconfirmed Parent", ts, ts))
    cx.execute("UPDATE tree SET home_person_id=? WHERE id=?", (home_id, tid))
    fid = tulid(); cx.execute("INSERT INTO family (id,tree_id,rel_type,created_at,updated_at) VALUES (?,?,'unknown',?,?)", (fid, tid, ts, ts))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid, parent_id))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'child')", (fid, home_id))
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                  VALUES (?,?,'obituary:1950',1,'fetch:done','fetch','subject_record','{}','[]','fetch','done',?)""", (tulid(), home_id, ts))   # the home person's own plan: run out, nothing left planned
    parent_step = tulid()
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                  VALUES (?,?,'footprint:',1,'search:parent','search','name','{}','["H01"]','auto','planned',?)""", (parent_step, parent_id, ts))   # the parent's own plan: an auto step still to run, at a source with a connector
    other_id, spouse_id = tulid(), tulid()
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (other_id, tid, "F", "Assisted Parent", ts, ts))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid, other_id))
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at)
                  VALUES (?,?,'will / probate:',1,'search:probate','search','probate','{}','["J03"]','assisted','planned',?)""", (tulid(), other_id, ts))   # an assisted search with no link the fetch list prints
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (spouse_id, tid, "M", "Spouse By Hand", ts, ts))
    fid2 = tulid(); cx.execute("INSERT INTO family (id,tree_id,rel_type,created_at,updated_at) VALUES (?,?,'unknown',?,?)", (fid2, tid, ts, ts))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid2, home_id))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid2, spouse_id))
    spouse_step = tulid()
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,sources_json,mode,status,created_at)
                  VALUES (?,?,'cemetery / family plot:',1,'fetch:memorial','fetch','subject_record',?,'E01','memorial_id','123','["E01"]','fetch','planned',?)""",
               (spouse_step, spouse_id, tdumps({"url": {"value": "https://www.findagrave.com/memorial/123/spouse-by-hand", "basis": "citation"}}), ts))   # a memorial page on the fetch list, with its link
    ex_id = tulid(); cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (ex_id, "rule", "harness", "0.1.0", ts))
    cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,generated_by,created_at,status) VALUES (?,?,'persona_match',?,?,?,'undecided')",
               (tulid(), tid, tdumps({"person_id": home_id}), ex_id, ts))   # a document still waiting on the home person, her own open question
    cx.commit()
    import importlib.util
    spec = importlib.util.spec_from_file_location("tree_queue2", os.path.join(ROOT, "tools", "queue.py"))
    tree_queue = importlib.util.module_from_spec(spec); spec.loader.exec_module(tree_queue)
    out, passed = tree_queue.edge(cx, tid)
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    fail(any(e["id"] == parent_id for e in out), f"the parent, with a runnable step still planned, is still named next: {out}")
    fail(not any(e["id"] == home_id for e in out), f"the home person is never named next once nothing is left for a turn to run: {out}")
    fail(any(e["id"] == home_id for e in passed), f"the home person is passed over instead, her open document the reason: {passed}")
    fail(any(e["id"] == other_id for e in passed) and not any(e["id"] == other_id for e in out), f"a parent whose only step is an assisted search with no link to open is passed over: {passed}")
    fail(any(e["id"] == spouse_id for e in out), f"a spouse whose memorial page is on the fetch list with a link is named: {out}")
    from log_search import log as log_search
    log_search(cx, tid, BY, step_id=parent_step, source_id="H01", outcome="none", note="harness: run on these very fields"); cx.commit()
    out, passed = tree_queue.edge(cx, tid)
    fail(any(e["id"] == parent_id for e in passed) and not any(e["id"] == parent_id for e in out), f"the parent's step, run none on the fields it still carries, is not a turn's work: passed over: {passed}")
    cx.execute("UPDATE search_plan SET query_json=? WHERE id=?", (tdumps({"surname": {"value": "Parent", "basis": "claim"}}), parent_step)); cx.commit()   # the plan wrote new fields
    out, passed = tree_queue.edge(cx, tid)
    fail(any(e["id"] == parent_id for e in out), f"once the plan changes the step's fields, the parent is named again: {out}")
    log_search(cx, tid, BY, step_id=parent_step, source_id="H01", outcome="error", note="harness: the source did not answer"); cx.commit()
    out, passed = tree_queue.edge(cx, tid)
    fail(any(e["id"] == parent_id for e in out) and not any(e["id"] == parent_id for e in passed), f"a run logged error on these fields is a source that did not answer, not a run: the parent is still named: {passed}")
    log_search(cx, tid, BY, step_id=parent_step, source_id="H01", outcome="none", note="harness: answered on the second ask"); cx.commit()
    out, passed = tree_queue.edge(cx, tid)
    fail(any(e["id"] == parent_id for e in passed) and not any(e["id"] == parent_id for e in out), f"a none run on the same fields after the error closes the step: passed over: {passed}")
    log_search(cx, tid, BY, step_id=spouse_step, source_id="E01", outcome="none", note="harness: the page saved, no fit"); cx.commit()
    out, passed = tree_queue.edge(cx, tid)
    fail(any(e["id"] == spouse_id for e in passed) and not any(e["id"] == spouse_id for e in out), f"the spouse's page, logged on unchanged fields, is not opened again: passed over: {passed}")
    cx.close()
    if keep: print("queue pass-over scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def unnamed_fetch_check(keep):
    """A fetch step whose page the list cannot name is not a turn's work (tools/fetches.py unnamed, tools/queue.py,
    tools/turn.py). Two parents the file claims for the home person, each with one fetch step at a holder with no connector
    whose pages carry no identity the attach reads (the New York State marriage index on the Internet Archive, C08): one
    cited with no year on a row with no instance, so the name the list prints still wants a year ("...-<year>-<six>.html")
    and no save can be made under it; the other on a dated row, named whole. The queue passes the first over, the reason
    naming the file, and names the second. A turn on the first pauses on nothing (no state kept), prints the page as
    passed over with the reason and runs to its report; a turn on the second pauses on its page as before."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from treelib import now as tnow, ulid as tulid, dumps as tdumps
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "unnamedtest", "--name", "Unnamed Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='unnamedtest'").fetchone()[0]
    ts = tnow(); home_id, undated_id, dated_id = tulid(), tulid(), tulid()
    for pid, sex, name in ((home_id, "F", "Home Person"), (undated_id, "M", "Undated Parent"), (dated_id, "F", "Dated Parent")):
        cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tid, sex, name, ts, ts))
    cx.execute("UPDATE tree SET home_person_id=? WHERE id=?", (home_id, tid))
    fid = tulid(); cx.execute("INSERT INTO family (id,tree_id,rel_type,created_at,updated_at) VALUES (?,?,'unknown',?,?)", (fid, tid, ts, ts))
    for pid, role in ((undated_id, "partner"), (dated_id, "partner"), (home_id, "child")):
        cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (fid, pid, role))
    url = "https://archive.org/search?query=%22New+York+State+Marriage+Index%22"
    fields = lambda u: tdumps({"url": {"value": u, "basis": "owner"}, "collection": {"value": "New York State, Marriage Index, 1881-1967", "basis": "owner"},
                               "name": {"value": "Home Person", "basis": "owner"}})   # basis owner: the planner keeps a step the owner's word wrote
    undated_step, dated_step = tulid(), tulid()
    for sid, pid, row_key, u in ((undated_step, undated_id, "footprint:", url), (dated_step, dated_id, "marriage record:1930", url + "+1930")):   # the dated citation opens the year's own item
        cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,sources_json,mode,status,rationale,created_at)
                      VALUES (?,?,?,1,?,'fetch','subject_record',?,'C08','url',?,'["C08"]','fetch','planned','harness: a page at a holder whose pages carry no identity',?)""",
                   (sid, pid, row_key, "word:" + row_key, fields(u), u, ts))
    cx.commit()
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    import fetches as fetches_mod, turn
    entries = {e["people"][0]: e for e in fetches_mod.openable(cx, tid)}
    u, n = entries.get("Undated Parent"), entries.get("Dated Parent")
    fail(u is not None and u["unnamed"] and "<year>" in u["save_as"] and u["save_as"] in u["unnamed"], f"the undated citation's entry is one the list cannot name, the reason naming the file: {u}")
    fail(n is not None and not n["unnamed"] and "-1930-" in n["save_as"], f"the dated row's entry is named whole, its year filled in: {n}")
    import importlib.util
    spec = importlib.util.spec_from_file_location("tree_queue3", os.path.join(ROOT, "tools", "queue.py"))
    tree_queue = importlib.util.module_from_spec(spec); spec.loader.exec_module(tree_queue)
    out, passed = tree_queue.edge(cx, tid)
    fail(any(e["id"] == dated_id for e in out), f"the parent whose page the list names is named next: {out}")
    fail(not any(e["id"] == undated_id for e in out) and any(e["id"] == undated_id and "cannot name" in e["reason"] and "<year>" in e["reason"] for e in passed),
         f"the parent whose page the list cannot name is passed over, the reason naming the file: {passed}")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): turn.start(cx, tid, "unnamedtest", undated_id, BY, db)
    fail(turn.load_state(db) is None, "a turn on the undated parent pauses on nothing: no state kept")
    fail("passed over:" in buf.getvalue() and "cannot name" in buf.getvalue() and "plan:" in buf.getvalue(), f"the turn prints the page as passed over with the reason and runs to its report: {buf.getvalue()[:400]}")
    fail(cx.execute("SELECT status FROM search_plan WHERE id=?", (undated_step,)).fetchone()[0] == "planned", "the step stays planned: passed over, not run, not logged")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): turn.start(cx, tid, "unnamedtest", dated_id, BY, db)
    st = turn.load_state(db)
    fail(st is not None and st["person_id"] == dated_id and not st.get("unnamed"), f"a turn on the dated parent pauses on her page as before, nothing passed over: {st}")
    fail("save as" in buf.getvalue() and "-1930-" in buf.getvalue() and "passed over" not in buf.getvalue(), f"the pause prints her page with its whole name: {buf.getvalue()[:400]}")
    turn.clear_state(db)
    cx.close()
    if keep: print("unnamed fetch scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def fetched_rows_subject_check(keep):
    """Catalog.fetched_rows must hold a one-person row only through a record whose accepted persona for that
    person is the record's own subject (is_subject), the same gate person_citations(subject_only=True) already applies --
    not merely a done step whose citation sits on the person (on_json []) with some artifact found under it, whoever the
    record turns out to be about (Raymond Earl Davidson's own obituary citation, an Ancestry-side mixup, held his wife's
    obituary instead; his own row read held all the same before this fix)."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from treelib import now as tnow, ulid as tulid, dumps as tdumps, archive_object
    from catalog import Catalog
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "fetchtest", "--name", "Fetched Rows Test")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='fetchtest'").fetchone()[0]
    ts = tnow(); ex_id = tulid()
    cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (ex_id, "rule", "harness", "0.1.0", ts))
    def record(pid, name, subject_role, related_persona=None):
        """An archived page with one persona in the given role, an accepted link from pid to it (related_persona: another
        persona on the page this one has an outgoing relation to, as a survivor names the deceased); a done fetch step on
        pid citing it, on_json [] (the citation sits on pid), logged found."""
        cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tid, "F", name, ts, ts))
        sha, _ = archive_object(cx, f"<html>{name}</html>".encode(), mime="text/html", source_id="H05", collection_id=None, locator_kind="url",
                                locator_value=f"https://example/{pid}", retrieved_by=BY, terms=None, cost="free", trust_tier="T2", original_filename=f"{pid}.html")
        eid = tulid(); cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status) VALUES (?,?,?,?,'complete')", (eid, sha, ex_id, ts))
        pe_id = tulid(); cx.execute("INSERT INTO persona (id,extraction_id,artifact_sha256,name_text,role_in_record,sequence) VALUES (?,?,?,?,?,1)", (pe_id, eid, sha, name, subject_role))
        if related_persona: cx.execute("INSERT INTO persona_relation (id,persona_id,related_persona_id,kind) VALUES (?,?,?,?)", (tulid(), pe_id, related_persona, "survivor"))
        cx.execute("INSERT INTO person_persona (person_id,persona_id,status,decided_by,decided_at) VALUES (?,?,'accepted',?,?)", (pid, pe_id, BY, ts))
        sid = tulid()
        cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,on_json,created_at)
                      VALUES (?,?,'obituary:',1,?,'fetch','subject_record','{}','["H05"]','fetch','done','[]',?)""", (sid, pid, f"fetch:{pid}", ts))
        cx.execute("INSERT INTO search_log (id,tree_id,plan_step_id,executed_at,executed_by,query_json,outcome,artifacts_json) VALUES (?,?,?,?,?,?,?,?)",
                   (tulid(), tid, sid, ts, BY, "{}", "found", tdumps([sha])))
        return pe_id
    subject_id = tulid(); record(subject_id, "True Subject", "deceased")   # her own obituary, unrelated to the mixed-up person below
    named_id = tulid(); cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (named_id, tid, "M", "Named Relative", ts, ts))
    cx.commit()
    # a second page: Named Relative's own step holds a record whose accepted persona for them is a survivor of someone else, not their own
    other_subject = tulid(); cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (other_subject, tid, "M", "Someone Else", ts, ts))
    sha2, _ = archive_object(cx, b"<html>mixup</html>", mime="text/html", source_id="H05", collection_id=None, locator_kind="url", locator_value="https://example/mixup",
                             retrieved_by=BY, terms=None, cost="free", trust_tier="T2", original_filename="mixup.html")
    eid2 = tulid(); cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status) VALUES (?,?,?,?,'complete')", (eid2, sha2, ex_id, ts))
    deceased_pe = tulid(); cx.execute("INSERT INTO persona (id,extraction_id,artifact_sha256,name_text,role_in_record,sequence) VALUES (?,?,?,?,?,1)", (deceased_pe, eid2, sha2, "Someone Else", "deceased"))
    survivor_pe = tulid(); cx.execute("INSERT INTO persona (id,extraction_id,artifact_sha256,name_text,role_in_record,sequence) VALUES (?,?,?,?,?,2)", (survivor_pe, eid2, sha2, "Named Relative", "survivor"))
    cx.execute("INSERT INTO persona_relation (id,persona_id,related_persona_id,kind) VALUES (?,?,?,?)", (tulid(), survivor_pe, deceased_pe, "survivor"))
    cx.execute("INSERT INTO person_persona (person_id,persona_id,status,decided_by,decided_at) VALUES (?,?,'accepted',?,?)", (named_id, survivor_pe, BY, ts))
    sid2 = tulid()
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,on_json,created_at)
                  VALUES (?,?,'obituary:',2,?,'fetch','subject_record','{}','["H05"]','fetch','done','[]',?)""", (sid2, named_id, "fetch:mixup", ts))
    cx.execute("INSERT INTO search_log (id,tree_id,plan_step_id,executed_at,executed_by,query_json,outcome,artifacts_json) VALUES (?,?,?,?,?,?,?,?)",
               (tulid(), tid, sid2, ts, BY, "{}", "found", tdumps([sha2])))
    cx.commit()
    cat = Catalog(cx, tid)
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    fail(cat.fetched_rows(subject_id).get("obituary:") is True, f"a person accepted as a record's own subject (no outgoing relation): held: {cat.fetched_rows(subject_id)}")
    fail(cat.fetched_rows(named_id).get("obituary:") is not True, f"a person accepted only as a survivor named on someone else's record (an outgoing relation to the deceased): not held, the mixed-up citation John Y Davidson's own Social Security row would once have read: {cat.fetched_rows(named_id)}")
    cx.close()
    if keep: print("fetched_rows subject scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def rules():
    """The name rules as the docs state them, on their own."""
    from catalog import same_surname
    want = {("ahearn", "ahearn"): "agrees", ("ahern", "ahearn"): "variant", ("brant", "brandt"): "variant", ("ahearu", "ahearn"): "one letter apart",
            ("grant", "brant"): "", ("bran", "brant"): "", ("kriebel", "krebel"): "variant", ("horn", "ahearn"): ""}
    bad = [f"same_surname{k} gave {same_surname(*k)!r}, expected {v!r}" for k, v in want.items() if same_surname(*k) != v]
    from catalog import holder_search
    f = lambda **kw: {k: {"value": v, "basis": "citation"} for k, v in kw.items()}
    cases = [
        ({"HolderKind": "url", "HolderKey": "https://archive.org/search?query=title%3A%28%22{title}%22%29", "HolderCollection": "x"}, f(name="Abram C Brant", citation="The Genealogical Record of the Schwenkfelder Families"),
         "https://archive.org/search?query=title%3A%28%22The%20Genealogical%20Record%20of%20the%20Schwenkfelder%20Families%22%29"),
        ({"HolderKind": "url", "HolderKey": "https://www.legacy.com/obituaries/search?firstName={given}&lastName={surname}", "HolderCollection": "x"}, f(name="Helen Sara Brant"), "https://www.legacy.com/obituaries/search?firstName=Helen%20Sara&lastName=Brant"),
        ({"HolderKind": "url", "HolderKey": "{url}", "HolderCollection": "x"}, f(name="Noi Davidson", url="http://www.legacy.com/obituaries/x?n=noi"), "http://www.legacy.com/obituaries/x?n=noi"),
        ({"HolderKind": "url", "HolderKey": "https://archive.org/search?query=x+{year}", "HolderCollection": "x"}, f(name="Carol Evers"), None),
        ({"HolderKind": "url", "HolderKey": "", "HolderCollection": "x"}, f(name="Catherine Rittenhouse"), None),
        ({"HolderKind": "fs_images", "HolderKey": "1999196", "HolderCollection": "Pennsylvania, Probate Records, 1683-1994"}, f(name="Matthias Wool Rittenhouse"), None),
        ({"HolderKind": "fs_collection", "HolderKey": "1937489", "HolderCollection": "New York, State Census, 1925"}, f(name="Dorothy Peters", city="Hempstead", county="Nassau"),
         "https://www.familysearch.org/en/search/record/results?f.collectionId=1937489&q.givenName=Dorothy&q.residenceDate.from=1925&q.residenceDate.to=1925&q.residencePlace=Hempstead%2C%20Nassau&q.surname=Peters"),
        ({"HolderKind": "url", "HolderKey": "https://www.google.com/search?q=%22{title}%22&tbm=bks&tbs=cdr:1,cd_min:{mdy},cd_max:{mdy}", "HolderCollection": "x"},
         f(name="Helen Sara Brant", citation="Boca Raton News", **{"publication date": "27 Jan 1986"}),
         "https://www.google.com/search?q=%22Boca%20Raton%20News%22&tbm=bks&tbs=cdr:1,cd_min:1%2F27%2F1986,cd_max:1%2F27%2F1986"),
    ]
    for h, fields, want_url in cases:
        got = holder_search(h, fields)
        if got != want_url: bad.append(f"holder_search({h['HolderKind']}, {h['HolderKey'][:40]!r}) gave {got!r}, expected {want_url!r}")
    from conclude import AUTOMATED
    if "nj-death-index" not in AUTOMATED: bad.append("conclude.AUTOMATED does not name nj-death-index: a death index would stay a hint until a person reads it")
    from catalog import collection_state, place_verdict
    township = "Mount Holly Township < Burlington County < New Jersey < United States"
    franklin_ky = "Franklin < Simpson County < Kentucky < United States"
    pv_cases = [
        (("NJ", township), ("agrees", "the record gives only New Jersey")),                    # a state code against a township in the state: agrees, coarser, and says so
        (("NJ", "New Jersey < United States"), ("agrees", None)),                              # a state against itself: agrees outright, nothing coarser to say
        (("Newark", township), ("disagrees", None)),                                            # two different towns: still disagrees
        (("Kent", franklin_ky), ("disagrees", None)),                                           # "Kent" is not Kentucky: no whole part matches
        (("Frank", franklin_ky), ("disagrees", None)),                                          # "Frank" is not Franklin
        (("Franklin, Tennessee", franklin_ky), ("disagrees", None)),                            # the town's name alone does not carry the wrong state
        (("KY", franklin_ky), ("agrees", "the record gives only Kentucky")),                    # a state code, expanded, still agrees, coarser
        (("Simpson County, Kentucky", franklin_ky), ("agrees", "the record gives only Simpson")), # county and state agree, coarser than the town
        (("Simpson", franklin_ky), ("agrees", "the record gives only Simpson")),                # the county alone still agrees
        (("Methacton Mennonite Cemetery, Norristown, Montgomery County, Pennsylvania, USA", "Norristown < Montgomery < Pennsylvania < United States"),
         ("agrees", "the record is finer: Methacton Mennonite Cemetery")),                      # a cemetery named ahead of the town is not compared; the jurisdictions match in full, and the note names what the record adds
        (("Vickers Hospital, Franklin, Simpson, Ky.", "Franklin, Simpson, Kentucky, United States"), ("agrees", "the record is finer: Vickers Hospital")),   # a building ahead of the town on a record that names no country, against a string that does: the country is not a part to count
        (("Franklin, Simpson, Kentucky, United States", "Franklin, Simpson, Ky."), ("agrees", None)),                     # and the other way round
        (("United States", franklin_ky), ("absent", None)),                                     # a record that names only the country says nothing to compare
        (("Simpson County, Kentucky", "Kentucky < United States"), ("agrees", "the record is finer: Simpson County")),   # a finer record against a tree that holds only the state: agrees on the state, the note says the record is finer, in the record's own words
        (("Franklin, Simpson, Ky.", "Simpson County < Kentucky < United States"), ("agrees", "the record is finer: Franklin")),   # the town ahead of the county the tree holds: agrees on the county
        (("Simpson County", "Kentucky < United States"), ("disagrees", None)),                  # a county alone, naming no state, against a tree that holds only the state: no level in common on the strings
        (("Franklin, Simpson, Kentucky", "Simpson County < Tennessee < United States"), ("disagrees", None)),   # finer, but under another state: disagrees
    ]
    for (record, tree), want in pv_cases:
        got = place_verdict(record, tree)
        if got != want: bad.append(f"place_verdict({record!r}, {tree!r}) gave {got!r}, expected {want!r}")
    rs_cases = [                                                                                # a bare county takes the record's own event place's state, supplied by the caller (match.personas_of, from the collection's own name)
        (("Simpson County", "Kentucky < United States", "Kentucky"),
         ("agrees", "the record is finer: Simpson County; supplying Kentucky, the record's own event place, for the bare county")),
        (("Simpson County", "Simpson County < Kentucky < United States", "Kentucky"), ("agrees", None)),   # the tree already holds the county: no need to fall back to the supplied state, so no note about it
        (("Simpson County", "Tennessee < United States", "Kentucky"), ("disagrees", None)),      # a wrong state supplied does not paper over a real disagreement
    ]
    for (record, tree, record_state), want in rs_cases:
        got = place_verdict(record, tree, record_state=record_state)
        if got != want: bad.append(f"place_verdict({record!r}, {tree!r}, record_state={record_state!r}) gave {got!r}, expected {want!r}")
    cs_cases = [("Kentucky, U.S., Death Index, 1911-2000", "Kentucky"), ("United States Census, 1900", None), ("", None)]
    for name, want in cs_cases:
        got = collection_state(name)
        if got != want: bad.append(f"collection_state({name!r}) gave {got!r}, expected {want!r}")
    morioka_names = [("Tonan", "1955-04-01", "1992-04-01")]                                        # a place's own dated names, as tools/resolve_places.py writes them from Wikidata
    dn_cases = [
        (("Tonan, Japan", "Morioka < Iwate < Japan"), ("agrees", "as Tonan, a name it held 1955-04-01–1992-04-01")),
        (("Ogau Tonan, Japan", "Morioka < Iwate < Japan"), ("agrees", "as Tonan, a name it held 1955-04-01–1992-04-01")),   # a leading word (a hamlet) ahead of the dated name is not mistaken for the whole
        (("Tokushima, Japan", "Morioka < Iwate < Japan"), ("disagrees", None)),                     # a real disagreement is not papered over by an unrelated dated name
    ]
    for (record, tree), want in dn_cases:
        got = place_verdict(record, tree, dated_names=morioka_names)
        if got != want: bad.append(f"place_verdict({record!r}, {tree!r}, dated_names=...) gave {got!r}, expected {want!r}")
    return bad

def connectors_offline():
    """The connectors' requests from a step's fields and their reading of saved responses, with no network: the Archive's
    title search for a cited book and the VA gravesite locator's posted search."""
    from connectors import ia, ia_books, va_graves
    from treelib import parse_gedcom_date
    bad = []; f = lambda **kw: {k: {"value": v, "basis": "citation"} for k, v in kw.items()}
    say = lambda ok, why: None if ok else bad.append(why)
    rq = ia_books.requests(f(collection="U.S., Family History Books", name="Abraham B Brant", citation="The Genealogical Record of the Schwenkfelder Families"))
    say(rq and rq[0]["url"].startswith(ia.ADVANCED) and "title%3A%28%22The%20Genealogical%20Record%20of%20the%20Schwenkfelder%20Families%22%29" in rq[0]["url"]
        and rq[0]["surname"] == "Brant" and str(rq[0]["given"]).startswith("Abraham"), f"a Family History Books citation asks the Archive's advanced search for its title with the citation's name: {rq}")
    rq2 = ia_books.requests(f(collection="North America, Family Histories, 1500-2000", name="Sarah Cassel", **{"book title": "A genealogical history of the Cassel family in America : being the descendants of Julius Kassel or"}))
    say(rq2 and rq2[0]["q"] == '"A genealogical history of the Cassel family in America"', f"a book title is asked by its main title, the subtitle and Ancestry's cut tail off: {rq2 and rq2[0]['q']}")
    say(ia_books.requests(f(collection="U.S., Family History Books", name="Robert Powell McCrary")) == [], "a book citation naming no title asks nothing")
    say(ia_books.requests(f(given="Abram C", surname="Brant", state="pennsylvania", birth_year=1880)) and "be-api.us.archive.org" in ia_books.requests(f(given="Abram C", surname="Brant", state="pennsylvania", birth_year=1880))[0]["url"], "a search step still asks the full-text search")
    with open(os.path.join(FIXTURES, "ia-advancedsearch-title-schwenkfelder-families.json"), "rb") as fh: body = fh.read()
    say(ia.total(body) == 3, f"the advanced search's total: {ia.total(body)}")
    hs = ia_books.hits(rq[0]["url"], body, rq[0]) if rq else []
    say([h["notes"]["item"] for h in hs] == ["genealogicalreco0000samu_a7w0", "genealogicalreco0000samu", "genealogicalreco00unse"], f"the three copies of the cited book, in the Archive's order: {[h['notes']['item'] for h in hs]}")
    say(hs and hs[0]["fetch"] == [{"url": "https://archive.org/metadata/genealogicalreco0000samu_a7w0", "kind": "json", "then": "metadata", "record": False}] and hs[0]["locator"]["value"] == "https://archive.org/details/genealogicalreco0000samu_a7w0",
        "a hit's first fetch is the item's metadata, the item's page its locator")
    say(ia_books.hits(rq2[0]["url"], body, rq2[0]) == [] if rq2 else False, "a response for another title gives no hit: every naming word of the cited title must be in the item's")
    rq = va_graves.requests(f(collection="U.S., Veterans' Gravesites, ca. 1775-2019", name="Raymond Earl Davidson"))
    say(rq and rq[0]["url"] == va_graves.URL and rq[0]["data"]["lastName"] == "Davidson" and rq[0]["data"]["firstName"] == "Raymond" and rq[0]["data"]["middleName"] == "E" and rq[0]["data"]["middleNameOpt"] == "2"
        and rq[0]["data"]["p_deathYY"] == "" and rq[0]["record"] is True and rq[0]["locator"] == "https://gravelocator.cem.va.gov/ngl/#lastName=Davidson&firstName=Raymond&middleName=E",
        f"a citation's name posts the locator's form, surname and first given name exact, the middle name's first letter as a beginning, the page the record: {rq}")
    rq = va_graves.requests({"given": {"value": "Chris M", "basis": "accepted"}, "surname": {"value": "Hahnle", "basis": "accepted"}, "death_year": {"value": 1960, "basis": "accepted"}})
    say(rq and rq[0]["data"]["p_deathYY"] == "1960" and rq[0]["data"]["firstName"] == "Chris" and rq[0]["data"]["middleName"] == "M", f"a search step's death year narrows the search: {rq}")
    say(va_graves.requests(f(name="Noi Davidson"))[0]["data"]["middleNameOpt"] == "1", "no middle name, none asked")
    with open(os.path.join(FIXTURES, "va-gravesite-search-davidson-raymond-page1.html"), "rb") as fh: page1 = fh.read()
    say(va_graves.total(page1) == 22 and len(va_graves.results(page1)) == 10 and va_graves.narrow(va_graves.URL, page1) is None
        and va_graves.next_page(va_graves.URL, page1) == "https://gravelocator.cem.va.gov/ngl/result/1lAHS2AnK4QkAoGcnXxp7TkBqZNjNMEghZnIjXo=",
        f"a first page of ten of 22 links its next page, and 22 is within what is read: {va_graves.total(page1)}, {va_graves.next_page(va_graves.URL, page1)}")
    say(va_graves.requests(f(collection="x")) == [], "no surname, nothing asked")
    with open(os.path.join(FIXTURES, "va-gravesite-search-davidson-raymond-2007.html"), "rb") as fh: body = fh.read()
    rows = va_graves.results(body)
    say(va_graves.total(body) == 2 and len(rows) == 2 and va_graves.narrow(va_graves.URL, body) is None and va_graves.next_page(va_graves.URL, body) is None, f"two decedents found, both on the page, no next page: {va_graves.total(body)}, {len(rows)}")
    say(rows and rows[1].get("name") == "DAVIDSON, RAYMOND E" and rows[1].get("birth") == "10/12/1939" and rows[1].get("death") == "01/27/2007" and rows[1].get("buried_at", "").startswith("SECTION O1 SITE 2239")
        and rows[1].get("cemetery") == "BG WILLIAM C DOYLE VET'S MEM CEM" and rows[1].get("city") == "WRIGHTSTOWN" and rows[1].get("state") == "NJ", f"the second decedent as the page writes him: {rows[1:] if rows else rows}")
    say(len(va_graves.hits(va_graves.URL, body, {"locator": "x"})) == 2 and va_graves.hits(va_graves.URL, body, {"locator": "x"})[0]["fetch"] == [], "one hit per decedent, fetching nothing: the page is the record")
    say(parse_gedcom_date("10/12/1939")["date_start"] == "1939-10-12" and parse_gedcom_date("13/12/1939")["date_start"] is None, "a month-first date is read, an impossible one is not")
    body_meta = json.dumps({"server": "ia800300.us.archive.org", "dir": "/1/items/genealogicalreco01krie", "metadata": {"identifier": "genealogicalreco01krie"}, "files": [{"name": "genealogicalreco01krie_jp2.zip"}]}).encode()
    h = ia.hit({"identifier": "genealogicalreco01krie", "doc": "genealogicalreco01krie", "title": "x", "year": 1879, "date": None, "collections": [], "page": None, "text": []}, {"q": '"Frederick Ahearn"~3', "surname": "Ahearn", "given": "Frederick", "variants": ["Ahern", "ahearn"]}, "x")
    inside = ia.follow(h["fetch"][0], body_meta, h)
    say([x.get("spelling") for x in inside] == ["Ahearn", "Ahern"] and all("inside.php" in x["url"] for x in inside) and "q=Ahern" in inside[1]["url"], f"the search inside is asked once per spelling, the surname first, a repeat spelling dropped: {[(x.get('spelling'), x['url'][-40:]) for x in inside]}")
    body_a = json.dumps({"ia": "x", "q": "Ahearn", "matches": [{"text": "Frederick Ahearn", "par": [{"page": 12}]}, {"text": "Ahearn", "par": [{"page": 40}]}]}).encode()
    body_b = json.dumps({"ia": "x", "q": "Ahern", "matches": [{"text": "Ahern", "par": [{"page": 40}]}, {"text": "Ahern", "par": [{"page": 55}]}, {"text": "Ahern", "par": [{"page": 60}]}]}).encode()
    imgs = ia.follow(inside[0], body_a, h) + ia.follow(inside[1], body_b, h)
    say(h["notes"]["pages"] == [12, 40, 55] and [x["page"] for x in imgs] == [12, 40, 55] and h["notes"].get("spellings_found") == ["Ahearn", "Ahern"], f"the pages of every spelling merged, three in all, each image once, the spellings found noted: {h['notes'].get('pages')}, {[x['page'] for x in imgs]}, {h['notes'].get('spellings_found')}")
    lent = ia.hit({"identifier": "lent", "doc": "lent", "title": "x", "year": 1900, "date": None, "collections": [], "page": None, "text": []}, {"surname": "Brant"}, "x")
    say(ia.follow(lent["fetch"][0], json.dumps({"server": "s", "dir": "/d", "metadata": {"access-restricted-item": "true"}, "files": []}).encode(), lent) == [] and lent["notes"].get("restricted") is True, "a book the Archive lends stops at its metadata, marked restricted")
    from run_step import outcome_of
    say(outcome_of([{"restricted": True}], [], ["a"]) == "none" and outcome_of([{"restricted": True}, {"restricted": False}], [], ["a"]) == "found" and outcome_of([], ["x"], []) == "error" and outcome_of([], [], ["a"]) == "none",
        "a run whose every hit is a lent book is none; one read is found; no answer at all is error")
    from connectors import loc_gov, ia_newspapers
    fq = f(collection="U.S., Newspapers.com Obituary Index, 1800s-current", name="Helen Sara Brant", **{"publication date": "27 Jan 1986", "publication place": "Boca Raton, Florida, USA"})
    lg = loc_gov.requests(fq); ian = ia_newspapers.requests(fq)
    say(lg and "q=Brant%20Helen" in lg[0]["url"] and "dates=1986%2F1986" in lg[0]["url"] and "location_state%3Aflorida" in lg[0]["url"], f"a cited obituary's fields ask loc.gov by the citation's name in the paper's year and state: {lg and lg[0]['url']}")
    say(ian and ian[0]["years"] == [1986, 1986] and "Helen%20Brant" in ian[0]["url"] and ian[0]["surname"] == "Brant" and ian[0]["given"] == "Helen Sara", f"and the Archive's newspapers within the paper's year, the citation's name split so the search inside asks the surname alone: {ian and (ian[0]['years'], ian[0]['surname'], ian[0]['url'][-60:])}")
    fts = json.dumps({"hits": {"total": {"value": 2}, "hits": [{"fields": {"identifier": ["st-joseph-herald-press-1967-02-11"], "meta_title": ["St Joseph Herald Press (1967-02-11)"], "meta_collection": ["newspaperarchive"], "filename": ["x_hocr_searchtext.txt.gz"]}, "highlight": {"text": ["Helen Brant"]}},
                                                                {"fields": {"identifier": ["boca-raton-news-1986-01-27"], "meta_title": ["Boca Raton News (1986-01-27)"], "meta_collection": ["newspaperarchive"]}, "highlight": {"text": ["Helen Ahearn"]}}]}}).encode()
    its = ia.items(fts)
    say([(i["year"], i["date"]) for i in its] == [(1967, "1967-02-11"), (1986, "1986-01-27")], f"a newspaper issue's day read from its title when the search gives no year: {[(i['year'], i['date']) for i in its]}")
    say([h["notes"]["item"] for h in ia_newspapers.hits(ian[0]["url"], fts, ian[0])] == ["boca-raton-news-1986-01-27"] if ian else False, "and only the issue of the paper's year is a hit")
    from run_step import spelling_variants
    say(spelling_variants("Ahearn", ["James J. Ahearu", "Frederick Ahern", "Helen Sara Brant Ahearn", "Alicia Ahern", "Mary Horn"]) == ["Ahearu", "Ahern"],
        f"the surname's spellings among the aliases: a slip and a variant once each, never a married name or another surname: {spelling_variants('Ahearn', ['James J. Ahearu', 'Frederick Ahern', 'Helen Sara Brant Ahearn', 'Alicia Ahern', 'Mary Horn'])}")
    from run_step import connectors_for
    class Cat2: sources = {"H05": {"connector": ""}, "H01": {"connector": "loc_gov"}, "H07": {"connector": "ia_newspapers"}, "H03": {}, "L02": {"connector": "ia_books"}}
    st = {"kind": "fetch", "locator_source_id": "H05", "sources_json": '["H01","H07","H03"]'}
    say([c.__name__.split(".")[-1] for c in connectors_for(Cat2, st)] == ["loc_gov", "ia_newspapers"], "a fetch step at a holder without a connector runs at the connectors of its row's sources")
    st2 = {"kind": "fetch", "locator_source_id": "L02", "sources_json": '["H07","L02"]'}
    say([c.__name__.split(".")[-1] for c in connectors_for(Cat2, st2)] == ["ia_books", "ia_newspapers"], "a fetch step's holder comes first, once")
    class Cat3: sources = {"C09": {"connector": "nj_death_index"}, "C08": {"connector": ""}}
    st3 = {"kind": "search", "row_key": "marriage record:Raymond Earl Davidson", "locator_source_id": None, "sources_json": '["C08","C09"]'}
    st4 = {"kind": "search", "row_key": "death record:", "locator_source_id": None, "sources_json": '["C08","C09"]'}
    say(connectors_for(Cat3, st3) == [] and [c.__name__.split(".")[-1] for c in connectors_for(Cat3, st4)] == ["nj_death_index"],
        f"a search step is asked at a connector only on a row it answers: the New Jersey death index reads the death row, never a marriage search: {connectors_for(Cat3, st3)}, {connectors_for(Cat3, st4)}")
    from connectors import answers
    say(answers("nj_death_index", "death record:") and not answers("nj_death_index", "birth record") and answers("loc_gov", "marriage record:"), "connectors.answers: a connector without ROWS answers every row")
    from run_step import coverage_years, step_years
    want = {"US 1756-1963": (1756, 1963), "US 1780s-1990s": (1780, 1999), "US 1950": (1950, 1950), "Global": None, "US veterans": None, "PA 1789-2013, few titles after the 1920s": (1789, 2013)}
    say(all(coverage_years(k) == v for k, v in want.items()), f"the registry's coverage years as read: {[(k, coverage_years(k)) for k in want]}")
    q = lambda **kw: {k: {"value": v, "basis": "accepted"} for k, v in kw.items()}
    say(step_years("obituary", q(death_year=2016, birth_year=1932)) == (2016, 2017) and step_years("household", q(year="1950", birth_year=1932)) == (1950, 1950)
        and step_years("name", q(birth_year=1880, death_year=1961)) == (1880, 1961) and step_years("name", q(birth_year=1880)) == (1880, 1980) and step_years("subject_record", q(surname="Brant")) is None
        and step_years("obituary", f(name="Helen Sara Brant", **{"publication date": "27 Jan 1986"})) == (1986, 1986),
        "a step's years: the death year for an obituary, the paper's year for a cited one, the census year for a household, the lifetime otherwise, none without a year")
    class Src: SOURCE = "H01"
    class Cat: sources = {"H01": {"coverage": "US 1756-1963"}, "L02": {"coverage": "Global"}}
    from run_step import outside
    say(outside(Cat, Src, "obituary", q(death_year=2016)) is not None and outside(Cat, Src, "obituary", q(death_year=1918)) is None and outside(Cat, Src, "name", q(birth_year=1932)) is None,
        "an obituary for a death after the newspapers end is not asked; one within them, or a lifetime overlapping them, is")
    from connectors import nj_death_index as nj
    whole = ("FNAME,LNAME,MIDDLE_NAME,STATE_FILE_NUMBER,BIRTH_YEAR,BIRTH_MONTH,BIRTH_DAY,BIRTH_CITY,BIRTH_STATE,BIRTH_COUNTRY,DEATH_YEAR,DEATH_MONTH,DEATH_DAY,DEATH_STATE\r\n"
             "fred,ahearn,,20160057427,1907,5,22,,Massachusetts,United States,2016,3,4,NJ\r\n"
             "noi,davidson,,20150044120,1949,1,12,Morioka,,Japan,2015,6,9,NJ\r\n"
             "alice,ahearn,m,20160012345,1935,,,,,United States,2016,8,1,NJ\r\n"
             "john,smith,,20140099999,1930,7,4,,New Jersey,United States,2014,2,14,NJ\r\n").encode()
    rq = nj.requests(f(name="Frederick Micheal Ahearn Jr"))
    say(rq and rq[0]["url"] == nj.CSV_URL and rq[0]["kind"] == "text" and rq[0]["surname"] == "Ahearn" and rq[0]["record"] is False, f"the whole file is asked once, the step's own surname split from its citation's name, not itself the record: {rq}")
    say(nj.requests(f(collection="x")) == [], "no name on the step, nothing asked")
    rq0 = rq[0]; rq0["archived_sha"] = "parentsha000000000000000000000000000000000000000000000000000"
    hs = nj.hits(nj.CSV_URL, whole, rq0)
    say(len(hs) == 1 and hs[0]["notes"]["rows"] == 2 and hs[0]["locator"]["value"] == f"{nj.CSV_URL}#surname=Ahearn", f"one hit, the two Ahearn rows out of the four, the file's own URL with the surname as its own locator: {hs}")
    fetch0 = hs[0]["fetch"][0]
    say(fetch0["derived_from"] == rq0["archived_sha"] and fetch0["record"] is True and "bytes" in fetch0, f"the derivative carries its parent's sha and is itself the record, computed, not fetched: {fetch0}")
    deriv_text = fetch0["bytes"].decode()
    say(deriv_text.splitlines()[0] == whole.decode().splitlines()[0] and len(deriv_text.splitlines()) == 3 and "davidson" not in deriv_text.lower(), f"the derivative carries the header and only the Ahearn rows, nobody else's: {deriv_text}")
    say(nj.hits(nj.CSV_URL, whole, {"surname": "Nobody", "archived_sha": rq0["archived_sha"]}) == [], "a surname the file carries no row under gives no hit")
    d, db = scratch(False)
    import treelib; treelib.DATA_ROOT = d
    from treelib import archive_object as ao, ulid as tulid, now as tnow
    from extract import extract as ext_fn
    cx2 = sqlite3.connect(db); cx2.execute("PRAGMA foreign_keys=ON"); cx2.row_factory = sqlite3.Row
    parent_sha, _ = ao(cx2, whole, mime="text/csv", source_id="C09", collection_id=None, locator_kind="url", locator_value=nj.CSV_URL, retrieved_by=BY, terms="public-domain", cost="free", trust_tier="T2", original_filename="nj-death-index-whole.csv")
    _, n_whole = ext_fn(cx2, parent_sha, BY)
    say(n_whole.get("failed") and "whole file" in n_whole["failed"], f"the whole file, read on its own, is refused: more than one surname: {n_whole}")
    d_sha, is_new = ao(cx2, fetch0["bytes"], mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=hs[0]["locator"]["value"], retrieved_by=BY, terms="public-domain", cost="free",
                       trust_tier="T2", original_filename=None, notes=json.dumps({**hs[0]["notes"], "hit": hs[0]["label"], "locator": hs[0]["locator"]}), derived_from=parent_sha)
    say(is_new and cx2.execute("SELECT derived_from FROM artifact WHERE sha256=?", (d_sha,)).fetchone()[0] == parent_sha, "the derivative's own row names its parent")
    eid, n = ext_fn(cx2, d_sha, BY)
    say(n.get("personas") == 2 and not n.get("failed"), f"one persona per Ahearn row: {n}")
    ps = [dict(r) for r in cx2.execute("SELECT id, name_text, sequence FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,))]
    fred = next((p for p in ps if p["name_text"] == "fred ahearn"), None)
    say(fred is not None, f"the first row's name as written: {[p['name_text'] for p in ps]}")
    if fred:
        facts = {(t, v, dt, pl) for t, v, dt, pl in cx2.execute("SELECT fact_type, value_text, date_text, ps.raw FROM persona_fact pf LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE persona_id=?", (fred["id"],))}
        say(("Birth", None, "1907-05-22", "Massachusetts, United States") in facts, f"birth date and place as the row's own columns give them: {facts}")
        say(("Death", None, "2016-03-04", "NJ") in facts, f"death date and state as written: {facts}")
        say(any(t == "Unknown" and v == "State File Number: 20160057427" for t, v, _, _ in facts), f"the state file number under its own label: {facts}")
    alice = next((p for p in ps if p["name_text"] == "alice ahearn"), None)
    if alice:
        afacts = {(t, dt) for t, v, dt, pl in cx2.execute("SELECT fact_type, value_text, date_text, place_string_id FROM persona_fact WHERE persona_id=?", (alice["id"],))}
        say(("Birth", "1935") in afacts, f"a birth with no month or day carries the year alone: {afacts}")
    same_sha, same_new = ao(cx2, fetch0["bytes"], mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=hs[0]["locator"]["value"], retrieved_by=BY, terms="public-domain", cost="free",
                            trust_tier="T2", derived_from=parent_sha)
    say(same_sha == d_sha and not same_new, "re-deriving the same surname's rows from the same parent lands on the same artifact, archived once")
    other = ("FNAME,LNAME,MIDDLE_NAME,STATE_FILE_NUMBER,BIRTH_YEAR,BIRTH_MONTH,BIRTH_DAY,BIRTH_CITY,BIRTH_STATE,BIRTH_COUNTRY,DEATH_YEAR,DEATH_MONTH,DEATH_DAY,DEATH_STATE\r\n"
             "john,smith,,20140099999,1930,7,4,,New Jersey,United States,2014,2,14,NJ\r\n").encode()
    other_sha, _ = ao(cx2, other, mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=f"{nj.CSV_URL}#surname=Smith", retrieved_by=BY, terms="public-domain", cost="free", trust_tier="T2", derived_from=parent_sha)
    eid2, n2 = ext_fn(cx2, other_sha, BY)
    say(n2.get("personas") == 1 and eid2 != eid, f"a different surname's derivative, a different artifact, its own extraction: {n2}")
    say(cx2.execute("SELECT superseded_by FROM extraction WHERE id=?", (eid,)).fetchone()[0] is None, "extracting another surname's derivative never supersedes this one's own extraction")
    ok2 = cx2.execute("PRAGMA integrity_check").fetchone()[0]; fk2 = cx2.execute("PRAGMA foreign_key_check").fetchall()
    say(ok2 == "ok" and not fk2, f"scratch catalog: integrity {ok2}, foreign keys {len(fk2)}")
    cx2.close(); shutil.rmtree(d, ignore_errors=True)
    return bad

def compiles():
    """Every tool, the screen's server and the check modules compile; the first thing green means."""
    import py_compile
    bad = []
    for f in sorted(os.listdir(os.path.join(ROOT, "tools"))) + ["connectors/" + f for f in sorted(os.listdir(os.path.join(ROOT, "tools", "connectors")))] + ["../app/person/server.py"] + ["../tests/checks/" + f for f in sorted(os.listdir(os.path.join(ROOT, "tests", "checks")))]:
        if not f.endswith(".py"): continue
        try: py_compile.compile(os.path.join(ROOT, "tools", f), doraise=True)
        except py_compile.PyCompileError as e: bad.append(f"{f}: {e.msg.splitlines()[0]}")
    return bad

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--show", action="store_true"); ap.add_argument("--keep", action="store_true"); a = ap.parse_args()
    bad_files = compiles()
    print("ok   every tool compiles" if not bad_files else "FAIL compile: " + "; ".join(bad_files))
    bad_rules = rules(); bad_files += bad_rules
    print("ok   the surname rule, the holder search, the rule's automated kinds and place_verdict's coarser and finer agreement: as written, a variant, one letter apart, not Grant for Brant; a template filled from the citation or the holder's page; nj-death-index is automated; a state code or an ancestor place agrees on the level it states, a finer place on the level the tree states and says so" if not bad_rules else "FAIL rules: " + "; ".join(bad_rules))
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    bad_conn = connectors_offline(); bad_files += bad_conn
    print("ok   connectors offline: a cited book asked by its title and its copies read from the Archive's answer, the search inside once per spelling, a lent book a none run; a cited obituary asked at the row's connectors in the paper's year; the gravesite locator's posted search and its results page read" if not bad_conn else "FAIL connectors: " + "; ".join(bad_conn))
    bad = len(bad_files) + parsers.check(a.keep, a.show)
    bad += scenario.check(os.path.join(scenario.SCENARIOS, "decisions"), a.keep, a.show)
    try: fails = turn_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL turn.py / queue.py on harness.ged: " + "; ".join(fails))
    else: print("ok   turn.py / queue.py on harness.ged: the queue names the edge, a turn runs its connector steps, pauses on its assisted list, resumes, reconsiders and reports; a step whose latest run is an error stays runnable and the report names the source that did not answer")
    try: fails = attach_collection_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL attach _steps_by_kind collision: " + "; ".join(fails))
    else: print("ok   attach _steps_by_kind: a page matches only the citation of its own holder collection, never another citation of the same row at the same holder")
    try: fails = attach_none_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL attach none run: " + "; ".join(fails))
    else: print("ok   attach none run: a results page saved under the fetch list's own name, its rows fitting nobody, sets the run to none like any other results page")
    try: fails = run_none_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL run_step none run: " + "; ".join(fails))
    else: print("ok   run_step none run: a connector's results listing whose rows fit nobody is a none run with the reason, the rows kept as candidates and the step planned; a row that fits is a card and a found run")
    try: fails = run_wants_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL run_step none run for want of a field: " + "; ".join(fails))
    else: print("ok   run_step none run for want of a field: a connector with nothing to ask on the step's fields logs a none run with no request, the note naming the field it wanted; the step is not runnable until the plan writes it, and the queue passes the person over")
    try: fails = results_for_fetch_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL attach results page for a fetch step: " + "; ".join(fails))
    else: print("ok   attach results page for a fetch step: a results page told by its parser goes to the fetch steps whose citation was searched for by that name in that collection, a none run when no row fits and found when one does, a repeat save left in the inbox")
    try: fails = run_step_all_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL run_step.py --all: " + "; ".join(fails))
    else: print("ok   run_step.py --all: runnable steps read fresh before each run, so a step a run's own regeneration drops is never run and one it opens still gets its turn; a SystemExit from a step's own run rolls that step's transaction back and still propagates")
    try: fails = queue_pass_over_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL queue.py pass-over: " + "; ".join(fails))
    else: print("ok   queue.py pass-over: a person already planned with nothing left for a turn to run, whose open question is the owner's alone, is passed over and never named next; an error run is no run on the fields, a none run after it is")
    try: fails = unnamed_fetch_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL fetch step the list cannot name: " + "; ".join(fails))
    else: print("ok   fetch step the list cannot name: a save name still wanting a year the citation does not carry is passed over with the reason by the queue and by turn.py, never paused on")
    try: fails = fetched_rows_subject_check(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL Catalog.fetched_rows subject gate: " + "; ".join(fails))
    else: print("ok   Catalog.fetched_rows subject gate: a one-person row is held only through a record whose accepted persona for that person is the record's own subject, not merely named on it")
    try: fails = places(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL resolve_places.py: " + "; ".join(fails))
    else: print("ok   resolve_places.py: a unique full match auto-accepts; a city coterminous with its county accepts as one territory; a village nested in its much larger town stays Undecided with both offered; a resolved place's wikidata_id brings its dated former names, offered as a candidate to a string naming one, never auto-resolved")
    try: fails = place_name_retry(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL run_step.py place retry: " + "; ".join(fails))
    else: print("ok   run_step.py: a search step's place field carrying more than one accurate name is tried in order and stops at the first hit, every try named on the logged run's query")
    try: fails = place_fallback_depth(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL Catalog.place fallback: " + "; ".join(fails))
    else: print("ok   Catalog.place fallback: an accepted state and an accepted city in it show the deepest, Philadelphia, never the alphabet")
    try: fails = chain_fill(a.keep)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL chain fill: " + "; ".join(fails))
    else: print("ok   chain fill: a state and the city in it fill the event at the city; Philadelphia and Pittsburgh, different chains, leave it unplaced")
    print("green" if not bad else f"{bad} failure(s)")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
