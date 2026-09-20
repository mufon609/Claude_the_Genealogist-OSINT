"""The loop's tools on the harness tree: the queue, a turn, the runner, the attach and the place resolver, with no network.

The scenarios under tests/fixtures/scenarios/loop/ are walked by tests/checks/scenario.py with the actions and
expectations here added: a turn or a run whose network is a fake standing in for the connectors' answers, the answers
themselves in the scenario's data (a body, an outcome per request, the field a connector wants), never in this file. The
fakes stay code because they exercise the connectors' contract (requests, hits, fetch); nothing here names a person, a
place or a page.
"""
import contextlib, importlib.util, io, json, os, shutil, sys, types
from common import BY, FIXTURES, TOOLS, run, tool
import scenario
from scenario import ACTIONS, EXPECTS, SCENARIOS, has

def queue_module():
    """tools/queue.py loaded by path: importing it by name would shadow the standard library's queue."""
    spec = importlib.util.spec_from_file_location("tree_queue", tool("queue.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def fake_answers(fake):
    """A run_step.run stand-in whose outcomes come from the data: the first run's outcome, then the rest's, one log row per
    connector of the step under that connector's own source, as run_step.run logs them, the errors as the data words them."""
    seen = []
    def fake_run(cx, cat, tree_id, step, by, dry_run=False, again=False):
        import run_step
        from log_search import log as log_search
        seen.append(step["id"])
        outcome = fake["first"] if len(seen) == 1 else fake.get("then", "none")
        errors = [fake["error"]] if outcome == "error" and fake.get("error") else []
        out = []
        for conn in run_step.connectors_for(cat, step) or [types.SimpleNamespace(__name__="fake", SOURCE=None)]:
            lid = log_search(cx, tree_id, by, step_id=step["id"], source_id=conn.SOURCE, outcome=outcome, artifacts=None, note="harness: faked, no network", query=json.loads(step["query_json"] or "{}"))
            out.append({"connector": conn.__name__.split(".")[-1], "source": conn.SOURCE, "asked": True, "query": {}, "outcome": outcome, "log": lid, "artifacts": [], "hits": [], "errors": errors, "household_steps": [], "extracted": []})
        return out
    return fake_run, seen

@contextlib.contextmanager
def patched(module, name, value):
    orig = getattr(module, name); setattr(module, name, value)
    try: yield
    finally: setattr(module, name, orig)

# ---------------------------------------------------------------- actions

def a_turn(w, x):
    """tools/turn.py start on a person, run_step.run standing in for the network as the data says; the steps it ran and the
    state it kept beside the database."""
    import run_step, turn
    fake_run, seen = fake_answers(x.get("fake_run") or {"first": "none"})
    buf = io.StringIO()
    with patched(run_step, "run", fake_run), contextlib.redirect_stdout(buf): turn.start(w.cx, w.tid, w.slug, w.person(x["person"]), BY, w.db)
    st = turn.load_state(w.db)
    return {"seen": seen, "seen_len": len(seen), "distinct": len(set(seen)), "state": st, "printed": buf.getvalue()}

def a_resume(w, x):
    """The pages dropped into the inbox as a save would leave them, then tools/turn.py --resume; its report."""
    import turn
    os.makedirs(w.treelib.inbox_dir(), exist_ok=True)
    for f in x.get("inbox", []): shutil.copy(os.path.join(FIXTURES, f), os.path.join(w.treelib.inbox_dir(), f))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): turn.resume(w.cx, w.tid, w.slug, BY, w.db)
    out = buf.getvalue()
    return {"report": out, "left": out.split("left:", 1)[1] if "left:" in out else "", "state": turn.load_state(w.db)}

def a_turns(w, x):
    """tools/turns.py: turn after turn from the queue, run_step.run standing in for the network as the data says (fake_run, as
    a turn's), --turns as `turns` says, or --resume with the pages `inbox` names dropped into the inbox first; what it
    printed, the summary, the run's state as it ended, what is saved beside the database, the turn's state, and a refusal's
    text when it exited."""
    import run_step, turn, turns
    fake_run, seen = fake_answers(x.get("fake_run") or {"first": "none"})
    if x.get("resume"):
        os.makedirs(w.treelib.inbox_dir(), exist_ok=True)
        for f in x.get("inbox", []): shutil.copy(os.path.join(FIXTURES, f), os.path.join(w.treelib.inbox_dir(), f))
    buf = io.StringIO(); refused = None; st = None
    with patched(run_step, "run", fake_run), contextlib.redirect_stdout(buf):
        try: st = turns.run(w.cx, w.tid, w.slug, BY, w.db, turns=x.get("turns"), resume=bool(x.get("resume")))
        except SystemExit as e: refused = str(e)
    out = buf.getvalue()
    return {"printed": out, "summary": out.split("\nloop:", 1)[1] if "\nloop:" in out else "", "state": st, "saved": turns.load_state(w.db), "turn_state": turn.load_state(w.db),
            "seen": seen, "refused": refused, "turn_people": [t["person"] for t in (st or {}).get("turns", [])], "passed_people": [p["person"] for p in (st or {}).get("passed", [])]}

def a_clear_state(w, x):
    import turn; turn.clear_state(w.db); return {}

def a_run(w, x):
    """tools/run_step.py run on one step, the download faked: a body the data gives (a text, or CSV rows under a header), one
    answer per request under `answers` (each for the URLs carrying `url_has`: a `body`, or an `error` the source's connection
    raises, standing for a timeout or a challenge), or no network at all, when a request must not go out; `dry` for --dry-run,
    `again` for a run by the step's id, every connector asked."""
    import run_step, urllib.error
    st = w.step(x["step"]); cat = w.catalog()
    fetch = x.get("fetch")
    def meta(url, content_type): return {"status": 200, "etag": None, "last_modified": None, "final_url": url, "content_type": content_type}
    def body_of(f): return (f["header"] + "\r\n" + "\r\n".join(f["rows"]) + "\r\n").encode() if "rows" in f else f["body"].encode()
    if fetch is None or x.get("dry"):
        def fake_fetch(url, kind, c, data=None): raise AssertionError(f"a request went out: {url}")
    elif "answers" in fetch:
        def fake_fetch(url, kind, c, data=None):
            for ans in fetch["answers"]:
                if ans["url_has"] not in url: continue
                if ans.get("error"): raise urllib.error.URLError(ans["error"])
                return body_of(ans), meta(url, ans.get("content_type", "application/json"))
            raise AssertionError(f"a request went out that the data does not answer: {url}")
    else:
        body = body_of(fetch)
        def fake_fetch(url, kind, c, data=None): return body, meta(url, fetch.get("content_type", "text/plain"))
    with patched(run_step, "fetch", fake_fetch):
        w.cx.execute("BEGIN"); res = run_step.run(w.cx, cat, w.tid, st, BY, dry_run=bool(x.get("dry")), again=bool(x.get("again"))); w.cx.commit()
    return {"step": st["id"], "results": [{"connector": r.get("connector"), "source": r.get("source"), "asked": r.get("asked"), "answered": r.get("answered"), "outcome": r.get("outcome"),
                                          "requests": r.get("requests"), "wants": r.get("wants"), "error": r.get("error"),
                                          "proposals": (r.get("extracted") or [{}])[0].get("proposals"), "extraction": (r.get("extracted") or [{}])[0].get("extraction")} for r in res],
            "connectors": [c.__name__.split(".")[-1] for c in run_step.connectors_for(cat, st)]}

def a_run_all(w, x):
    """tools/run_step.py --all with run_step.run standing in: a run that regenerates the plan as the data says (dropping one
    step, opening another), or one that raises SystemExit; every planned search step runnable, no real connector."""
    import run_step
    calls, opened = [], []
    fake = x["fake"]
    def fake_run(cx, cat, tree_id, st, by, dry_run=False, again=False):
        calls.append(st["id"])
        if fake.get("regenerates_at") and st["id"] == w.value(fake["regenerates_at"]):
            cx.execute("DELETE FROM search_plan WHERE id=?", (w.value(fake["drops"]),))
            o = fake["opens"]; sid = w.treelib.ulid(); opened.append(sid)
            cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,status,created_at) VALUES (?,?,?,?,?,'search','name','{}',?,'auto','planned',?)""",
                       (sid, w.person(o["person"]), o["row_key"], o.get("seq", 3), o["step_key"], json.dumps(o.get("sources", [])), w.treelib.now()))
        if fake.get("boom"):
            cx.execute("UPDATE search_plan SET status='done' WHERE id=?", (st["id"],))
            raise SystemExit("no step " + st["id"])
        return []
    raised = False; old_argv = sys.argv
    stand_in = types.SimpleNamespace(__name__="fake.connector", SOURCE=None, requests=lambda fields: [{"url": "fake", "kind": "search"}])   # a connector every planned step has, its runs read whatever their source
    with patched(run_step, "run", fake_run), patched(run_step, "connectors_for", lambda cat, st: [stand_in]):
        sys.argv = ["run_step.py", "--all", "--db", w.db, "--tree", w.slug, "--by", BY]
        try:
            with contextlib.redirect_stdout(io.StringIO()): run_step.main()
        except SystemExit: raised = True
        finally: sys.argv = old_argv
    return {"calls": calls, "opened": opened, "raised": raised}

def a_run_connector(w, x):
    """run_step.run_connector on a step with a connector standing in: its requests from the step's place field, its hits
    from the fetch's answer, the answer per request from the data (none for a URL carrying one text, found otherwise)."""
    import run_step
    from connectors import value
    c = x["connector"]; st = w.step(x["step"])
    def requests(fields):
        place = value(fields, "place")
        return [{"url": f"{c['url']}?place={place}", "kind": "search"}] if place else []
    def hits(url, data): return [] if data == b"none" else [{"label": "hit", "locator": "loc1", "fetch": [], "notes": {}}]
    conn = types.SimpleNamespace(__name__="fake.connector", SOURCE=c["source"], COLLECTION=c["collection"], RATE={"search": 6000}, requests=requests, hits=hits, total=lambda data: None)
    def fake_fetch(url, kind, cc, data=None):
        return (b"none" if c["none_when"] in url else b"found"), {"status": 200, "etag": None, "last_modified": None, "final_url": url, "content_type": "application/json"}
    with patched(run_step, "fetch", fake_fetch): r = run_step.run_connector(w.cx, w.catalog(), w.tid, st, conn, BY)
    logged = w.cx.execute("SELECT query_json FROM search_log WHERE plan_step_id=?", (st["id"],)).fetchone()
    return {"outcome": r.get("outcome"), "requests": r.get("requests"), "logged_query": json.loads(logged[0]) if logged else {}}

def a_resolve(w, x):
    """tools/resolve_places.py on the strings named (--only, one run each) with the geocoder's answers planted in its cache
    and Wikidata's in its own, so no request goes out; the strings must already be the tree's."""
    import hashlib
    from resolve_places import cache_dir, wikidata_cache_dir
    os.makedirs(cache_dir(), exist_ok=True); os.makedirs(wikidata_cache_dir(), exist_ok=True)
    for query, cands in x.get("cache", {}).items():
        with open(os.path.join(cache_dir(), hashlib.sha1(query.lower().encode()).hexdigest() + ".json"), "w", encoding="utf-8") as fh: json.dump({"query": query, "fetched_at": w.treelib.now(), "results": cands}, fh)
    for qid, fixture in x.get("wikidata", {}).items(): shutil.copy(os.path.join(FIXTURES, fixture), os.path.join(wikidata_cache_dir(), qid + ".json"))
    w.cx.commit()
    out = "".join(run(tool("resolve_places.py"), "--db", w.db, "--tree", w.slug, "--by", BY, "--only", raw) for raw in x["only"])   # one string at a time: the tree's other strings never reach the network
    return {"printed": out}

def a_place_string(w, x):
    """A place string of the owner's records written to the tree on its own, for a resolution the tree's own events do not
    yet carry the words of."""
    w.cx.execute("INSERT INTO place_string (id, raw) VALUES (?, ?)", (w.treelib.ulid(), x["raw"])); return {"raw": x["raw"]}

def a_apply_places(w, x):
    from resolve_places import apply_to_events
    return {"applied": apply_to_events(w.cx, w.tid, BY, w.treelib.now())}

def a_step_query(w, x):
    """A step's fields rewritten, as the plan writes new fields on it."""
    st = w.step(x["step"]); w.cx.execute("UPDATE search_plan SET query_json=? WHERE id=?", (json.dumps(x["query"]), st["id"])); return {"step": st["id"]}

def a_fetch_list(w, x):
    """tools/fetches.py list's own entries, read-only: every save-as name it prints (or, with `search_links`, only the
    FamilySearch fielded searches: a D03 entry whose link is the collection's own record search, not a catalog browse),
    for a check that a search link's name is built whole from the search's own fields, no placeholder left in it."""
    from fetches import waiting
    rows = waiting(w.cx, w.tid)
    if x.get("search_links"): rows = [e for e in rows if e["holder_id"] == "D03" and "/search/record/results" in (e.get("url") or "")]
    return {"names": [e["save_as"] for e in rows]}

ACTIONS.update({"step_query": a_step_query, "turn": a_turn, "turns": a_turns, "resume": a_resume, "clear_state": a_clear_state, "run": a_run, "run_all": a_run_all, "run_connector": a_run_connector,
                "resolve": a_resolve, "place_string": a_place_string, "apply_places": a_apply_places, "fetch_list": a_fetch_list})

# ---------------------------------------------------------------- expectations

def e_queue(w, x, want):
    """tools/queue.py's edge: who is named next and who is passed over, each with the reason."""
    out, passed = queue_module().edge(w.cx, w.tid)
    got = {"named": [{"name": e["name"], "reason": e["reason"]} for e in out], "passed": [{"name": e["name"], "reason": e["reason"]} for e in passed]}
    ok = True
    for ref in x.get("named", []): ok &= any(e["id"] == w.person(ref) for e in out)
    for ref in x.get("not_named", []): ok &= not any(e["id"] == w.person(ref) for e in out)
    for ref in x.get("passed", []): ok &= any(e["id"] == w.person(ref) for e in passed)
    for ref in x.get("not_passed", []): ok &= not any(e["id"] == w.person(ref) for e in passed)
    if "first" in x: ok &= bool(out) and out[0]["id"] in [w.person(r) for r in (x["first"] if isinstance(x["first"], list) else [x["first"]])]
    if "first_reason" in x: ok &= bool(out) and has(out[0]["reason"], x["first_reason"])
    for ref, pat in (x.get("reasons") or {}).items(): ok &= any(e["id"] == w.person(ref) and has(e["reason"], pat) for e in out + passed)
    if "passed_count" in x: ok &= has(len(passed), x["passed_count"])
    return ok, got

def e_runnable(w, x, want):
    import run_step
    ids = {r["id"] for r in run_step.runnable(w.cx, w.catalog(), w.tid)}
    st = w.step(x["step"]); v = st is not None and st["id"] in ids
    return v == x.get("is", True), v

def e_turn_state(w, x, want):
    import turn
    st = turn.load_state(w.db)
    if x.get("is") is None and "person" not in x: return st is None, st
    ok = st is not None and (("person" not in x) or st.get("person_id") == w.person(x["person"])) and has(st, x.get("is", {}))
    return ok, st

def e_turns_run(w, x, want):
    """The runner's state as the last turns action left it: the turns in order (each a person, whether it paused, whether it
    held nothing new) and the people passed over this run."""
    st = (w.env.get("last") or {}).get("state") or {}
    got = {"turns": [{"person": t["person_id"], "paused": t.get("held_after") is None, "nothing_new": t.get("held_after") == t["held_before"]} for t in st.get("turns", [])],
           "passed": [p["person_id"] for p in st.get("passed", [])]}
    ok = True
    if "turns" in x:
        ok &= len(got["turns"]) == len(x["turns"])
        for g, wnt in zip(got["turns"], x["turns"]):
            ok &= g["person"] == w.person(wnt["person"]) and all(g[k] == wnt[k] for k in ("paused", "nothing_new") if k in wnt)
    for ref in x.get("passed", []): ok &= w.person(ref) in got["passed"]
    for ref in x.get("not_passed", []): ok &= w.person(ref) not in got["passed"]
    return ok, {"turns": [{**t, "name": w.name_of(t["person"])} for t in got["turns"]], "passed": [w.name_of(p) for p in got["passed"]]}

def e_locator_known(w, x, want):
    v = w.cx.execute("SELECT 1 FROM artifact_locator WHERE kind=? AND value=?", (x["kind"], x["value"])).fetchone() is not None
    return v == x.get("exists", True), v

def e_steps_by_collection(w, x, want):
    from attach import _steps_by_collection
    got = [g["id"] for g in _steps_by_collection(w.cx, w.tid, x["parsed"])]
    want_ids = [w.step(s)["id"] for s in x["is"]]
    return got == want_ids, [w.cx.execute("SELECT step_key FROM search_plan WHERE id=?", (g,)).fetchone()[0] for g in got]

def e_fetched_rows(w, x, want):
    """Catalog.fetched_rows on a person's row: `held` reads the value (a one-person row, held by the record's own subject),
    `present` the key (a household row, held by any member's done step)."""
    rows = w.catalog().fetched_rows(w.person(x["person"])); v = rows.get(x["row"])
    if "present" in x: return (x["row"] in rows) == bool(x["present"]), {"present": x["row"] in rows, "value": v}
    return (v is True) if x.get("held") else (v is not True), v

def e_place(w, x, want):
    row = w.cx.execute("SELECT id, name, place_type, wikidata_id FROM place WHERE name=?", (x["name"],)).fetchone()
    got = dict(row) if row else None
    if got and "dated_name" in x:
        d = w.cx.execute("SELECT valid_from, valid_to FROM place_name WHERE place_id=? AND name=?", (row["id"], x["dated_name"])).fetchone()
        got["dated"] = list(d) if d else None
    return row is not None and has(got, {k: v for k, v in x.items() if k in ("place_type", "wikidata_id", "dated")}), got

def e_place_card(w, x, want):
    """The resolver's own card for a string: its candidates as offered."""
    prop = w.cx.execute("SELECT payload_json, status FROM proposal WHERE kind='place_resolution' AND tree_id=? AND json_extract(payload_json,'$.raw')=?", (w.tid, x["raw"])).fetchone()
    if not prop: return x.get("exists") is False, None
    cands = json.loads(prop["payload_json"])["candidates"]
    got = {"candidates": cands, "names": sorted(c.get("display_name") or c.get("name") or "" for c in cands), "status": prop["status"]}
    if "place_of" in x:
        for c in got["candidates"]:
            if c.get("place_id"): c["place_name"] = (w.cx.execute("SELECT name FROM place WHERE id=?", (c["place_id"],)).fetchone() or [None])[0]
    return has(got, w.value({k: v for k, v in x.items() if k in ("candidates", "names", "status")})), {"names": got["names"], "candidates": [{k: c.get(k) for k in ("kind", "name", "valid_from", "valid_to", "leading", "place_name")} for c in cands]}

def e_event_place(w, x, want):
    """A person's event of a type: the place the event itself carries (after the filler), and the place shown."""
    pid = w.person(x["person"]); cat = w.catalog()
    rows = w.cx.execute("SELECT e.id, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type=?", (pid, x["type"])).fetchall()
    if not rows: return False, None
    eid, place_id = rows[0]
    name = (w.cx.execute("SELECT name FROM place WHERE id=?", (place_id,)).fetchone() or [None])[0] if place_id else None
    got = {"place": name, "shown": cat.place(eid, None)["text"], "shown_first": cat.place(eid, None)["text"].split(" < ")[0]}
    return has(got, {k: v for k, v in x.items() if k in got}), got

def e_file_exists(w, x, want):
    """Whether a named file still sits in a folder, for a page collect had nothing to take (no saved-from identity the
    attach reads, no name the fetch list printed): it is left exactly where it was saved."""
    v = os.path.isfile(os.path.join(w.value(x["folder"]), x["name"]))
    return v == x.get("is", True), v

EXPECTS.update({"queue": e_queue, "runnable": e_runnable, "turn_state": e_turn_state, "turns_run": e_turns_run, "locator_known": e_locator_known, "steps_by_collection": e_steps_by_collection, "fetched_rows": e_fetched_rows,
                "place": e_place, "place_card": e_place_card, "event_place": e_event_place, "file_exists": e_file_exists})

def check(keep, show, only=None):
    return scenario.check(os.path.join(SCENARIOS, "loop"), keep, show, only)
