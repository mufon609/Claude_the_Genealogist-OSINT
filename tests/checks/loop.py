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
from scenario import ACTIONS, EXPECTS, SCENARIOS, has, plant_geocoder

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

@contextlib.contextmanager
def geocoder_offline():
    """The geocoder answering from the resolver's cache only, for a turn the harness runs in this process: a query the cache lacks
    fails as an endpoint that does not answer, so no request leaves the harness."""
    import hashlib, resolve_places
    def cached(q):
        path = os.path.join(resolve_places.cache_dir(), hashlib.sha1(q.lower().encode()).hexdigest() + ".json")
        if not os.path.exists(path): raise OSError("the harness has no network")
        with open(path, encoding="utf-8") as fh: return json.load(fh)["results"]
    with patched(resolve_places, "nominatim", cached): yield

# ---------------------------------------------------------------- actions

def a_turn(w, x):
    """tools/turn.py start on a person, run_step.run standing in for the network as the data says, the geocoder's answers the
    fixtures under `geocoder` plant (and no other); the steps it ran and the state it kept beside the database."""
    import run_step, turn
    fake_run, seen = fake_answers(x.get("fake_run") or {"first": "none"})
    plant_geocoder(x.get("geocoder") or []); w.cx.commit()
    buf = io.StringIO()
    with patched(run_step, "run", fake_run), geocoder_offline(), contextlib.redirect_stdout(buf): turn.start(w.cx, w.tid, w.slug, w.person(x["person"]), BY, w.db)
    st = turn.load_state(w.db)
    return {"seen": seen, "seen_len": len(seen), "distinct": len(set(seen)), "state": st, "printed": buf.getvalue()}

def a_resume(w, x):
    """The pages dropped into the inbox as a save would leave them, then tools/turn.py --resume; its report."""
    import turn
    os.makedirs(w.treelib.inbox_dir(), exist_ok=True)
    for f in x.get("inbox", []): shutil.copy(os.path.join(FIXTURES, f), os.path.join(w.treelib.inbox_dir(), f))
    plant_geocoder(x.get("geocoder") or []); w.cx.commit()
    buf = io.StringIO()
    with geocoder_offline(), contextlib.redirect_stdout(buf): turn.resume(w.cx, w.tid, w.slug, BY, w.db)
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
    plant_geocoder(x.get("geocoder") or []); w.cx.commit()
    buf = io.StringIO(); refused = None; st = None
    with patched(run_step, "run", fake_run), geocoder_offline(), contextlib.redirect_stdout(buf):
        try: st = turns.run(w.cx, w.tid, w.slug, BY, w.db, turns=x.get("turns"), resume=bool(x.get("resume")))
        except SystemExit as e: refused = str(e)
    out = buf.getvalue()
    return {"printed": out, "summary": out.split("\nloop:", 1)[1] if "\nloop:" in out else "", "state": st, "saved": turns.load_state(w.db), "turn_state": turn.load_state(w.db),
            "seen": seen, "refused": refused, "turn_people": [t["person"] for t in (st or {}).get("turns", [])], "passed_people": [p["person"] for p in (st or {}).get("passed", [])]}

def a_clear_state(w, x):
    import turn; turn.clear_state(w.db); return {}

def answered_by(fetch):
    """The network call a run is played back with, from the data: `answers`, one for each request, in the order the requests
    come. An answer is for the first request carrying its `url_has` that no earlier request has taken: a saved real response
    (`fixture` under tests/fixtures/, its `content_type`) or an `error` the source's connection raises, the harness's
    stand-in for a holder that did not answer (a timeout, a refusal, a challenge). A request the data does not answer fails
    the run; no `fetch` means no network at all."""
    import urllib.error
    used = set()
    def meta(url, content_type): return {"status": 200, "etag": None, "last_modified": None, "final_url": url, "content_type": content_type}
    def fake_fetch(url, kind, c, data=None):
        for i, ans in enumerate((fetch or {}).get("answers", [])):
            if i in used or ans["url_has"] not in url: continue
            used.add(i)
            if ans.get("error"): raise urllib.error.URLError(ans["error"])
            with open(os.path.join(FIXTURES, ans["fixture"]), "rb") as fh: return fh.read(), meta(url, ans.get("content_type", "application/json"))
        raise AssertionError(f"a request went out that the data does not answer: {url}")
    return fake_fetch

def a_run(w, x):
    """tools/run_step.py run on one step through its real connectors, only the network call replaced (answered_by); `dry` for
    --dry-run, no request allowed, `again` for a run by the step's id, every connector asked. The result carries each
    connector's run and, under `records`, the sha256 of every record the runner archived and read."""
    import run_step
    st = w.step(x["step"]); cat = w.catalog()
    with patched(run_step, "fetch", answered_by(None if x.get("dry") else x.get("fetch"))):
        w.cx.execute("BEGIN"); res = run_step.run(w.cx, cat, w.tid, st, BY, dry_run=bool(x.get("dry")), again=bool(x.get("again"))); w.cx.commit()
    return {"step": st["id"], "results": [{"connector": r.get("connector"), "source": r.get("source"), "asked": r.get("asked"), "answered": r.get("answered"), "outcome": r.get("outcome"),
                                          "requests": r.get("requests"), "wants": r.get("wants"), "error": r.get("error"), "errors": r.get("errors"),
                                          "proposals": (r.get("extracted") or [{}])[0].get("proposals"), "extraction": (r.get("extracted") or [{}])[0].get("extraction")} for r in res],
            "records": [e["sha256"] for r in res for e in r.get("extracted") or [] if "extraction" in e],
            "connectors": [c.__name__.split(".")[-1] for c in run_step.connectors_for(cat, st)]}

def a_run_all(w, x):
    """tools/run_step.py --all with run_step.run standing in: a run that regenerates the plan as the data says (dropping one
    step, opening another), or one that raises SystemExit; which steps are runnable is the real connectors' say."""
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
    with patched(run_step, "run", fake_run):
        sys.argv = ["run_step.py", "--all", "--db", w.db, "--tree", w.slug, "--by", BY]
        try:
            with contextlib.redirect_stdout(io.StringIO()): run_step.main()
        except SystemExit: raised = True
        finally: sys.argv = old_argv
    return {"calls": calls, "opened": opened, "raised": raised}

def a_run_connector(w, x):
    """run_step.run_connector on a step with the real connector named (`connector`, its module under tools/connectors/), only
    the network call replaced (answered_by): the place names the step carries tried one at a time, the requests the connector
    builds, the run's outcome and the query the run logged. `dry`: run_step.run in dry-run mode instead, saying whether the
    runner would ask the connector again on the step's current fields."""
    import run_step
    from connectors import load
    st = w.step(x["step"]); conn = load(x["connector"])
    if x.get("dry"):
        res = run_step.run(w.cx, w.catalog(), w.tid, st, BY, dry_run=True)
        return {"results": [{"connector": r.get("connector"), "asked": r.get("asked"), "answered": r.get("answered")} for r in res]}
    with patched(run_step, "fetch", answered_by(x.get("fetch"))): r = run_step.run_connector(w.cx, w.catalog(), w.tid, st, conn, BY)
    logged = w.cx.execute("SELECT query_json FROM search_log WHERE plan_step_id=?", (st["id"],)).fetchone()
    return {"outcome": r.get("outcome"), "requests": r.get("requests"), "logged_query": json.loads(logged[0]) if logged else {}}

def a_resolve(w, x):
    """tools/resolve_places.py on the strings named (--only, one run each) with the geocoder's answers planted in its cache,
    Wikidata's items in its own, and the gazetteers' answers (GOV's and Wikidata's searches, each fixture a list of the
    resolver's own cache records) under the paths the resolver reads them from, so no request goes out; the strings must
    already be the tree's."""
    from resolve_places import gazetteer_cache_path, wikidata_cache_dir
    os.makedirs(wikidata_cache_dir(), exist_ok=True)
    plant_geocoder(x.get("geocoder", []))
    for qid, fixture in x.get("wikidata", {}).items(): shutil.copy(os.path.join(FIXTURES, fixture), os.path.join(wikidata_cache_dir(), qid + ".json"))
    for fixture in x.get("gazetteer", []):
        with open(os.path.join(FIXTURES, fixture), encoding="utf-8") as fh: records = json.load(fh)
        for rec in records:
            path = gazetteer_cache_path(rec["service"], rec["args"]); os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh: json.dump(rec, fh, ensure_ascii=False)
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

def a_decide_place(w, x):
    """The owner's answer on a place card found by its string (`raw`), through conclude.decide: the candidate whose gazetteer id is
    `gazetteer` (a gazetteer's own candidate, or the one attached to a geocoder candidate) or whose OpenStreetMap id is `osm`,
    or `status` rejected, a string that is not a place; `alone` answers that card's string only."""
    from conclude import decide
    row = w.cx.execute("SELECT id, payload_json FROM proposal WHERE tree_id=? AND kind='place_resolution' AND status='undecided' AND json_extract(payload_json,'$.raw')=?", (w.tid, x["raw"])).fetchone()
    if not row: raise KeyError(f"no open place card for {x['raw']!r}")
    status = x.get("status", "accepted")
    def picks(c):
        if "osm" in x: return c.get("osm") == x["osm"]
        return (c.get("kind") == "gazetteer" and c.get("id") == x["gazetteer"]) or (c.get("gazetteer") or {}).get("id") == x["gazetteer"]
    i = None if status == "rejected" else next(i for i, c in enumerate(json.loads(row[1])["candidates"]) if picks(c))
    return decide(w.cx, w.tid, row[0], status, BY, note=x.get("note", "harness: the owner chooses"), choice=i, alone=bool(x.get("alone")))

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

ACTIONS.update({"decide_place": a_decide_place, "step_query": a_step_query, "turn": a_turn, "turns": a_turns, "resume": a_resume, "clear_state": a_clear_state, "run": a_run, "run_all": a_run_all, "run_connector": a_run_connector,
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
    row = w.cx.execute("SELECT id, name, place_type, wikidata_id, gov_id FROM place WHERE name=?", (x["name"],)).fetchone()
    got = dict(row) if row else None
    if got and "dated_name" in x:
        d = w.cx.execute("SELECT valid_from, valid_to FROM place_name WHERE place_id=? AND name=?", (row["id"], x["dated_name"])).fetchone()
        got["dated"] = list(d) if d else None
    if got: got["chain"] = chain_names(w.cx, row["id"])
    return row is not None and has(got, {k: v for k, v in x.items() if k in ("place_type", "wikidata_id", "gov_id", "dated", "chain")}), got

def chain_names(cx, pid):
    """A place and every place enclosing it, by name, the place first."""
    out = []
    while pid:
        r = cx.execute("SELECT name, parent_id FROM place WHERE id=?", (pid,)).fetchone()
        if not r: break
        out.append(r[0]); pid = r[1]
    return out

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

def e_place_group(w, x, want):
    """The words of every string whose open card asks the same as the card of the string `raw`, in order, as the screen shows them
    on one card (resolve_places.place_groups)."""
    from resolve_places import place_groups
    row = w.cx.execute("SELECT id FROM proposal WHERE tree_id=? AND kind='place_resolution' AND status='undecided' AND json_extract(payload_json,'$.raw')=?", (w.tid, x["raw"])).fetchone()
    covers = [m["raw"] for m in place_groups(w.cx, w.tid).get(row[0], [])] if row else []
    return has(covers, x["covers"]), covers

def e_same_place(w, x, want):
    """Whether the strings `raws` are all accepted to one place."""
    ids = [(w.cx.execute("SELECT place_id FROM place_string WHERE raw=? AND status='accepted'", (r,)).fetchone() or [None])[0] for r in x["raws"]]
    return (len(set(ids)) == 1 and ids[0] is not None) == x.get("is", True), ids

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

def e_fetch_call(w, x, want):
    """The call the fetch list gives the save script for the page that serves a step (fetches.page_call): its text, and `serves`, the
    steps its key names, checked as the steps given (plan step references), in order."""
    from fetches import page_call, waiting
    sid = w.step(x["step"])["id"]
    e = next((e for e in waiting(w.cx, w.tid) if sid in e["step_ids"]), None)
    if not e: return x.get("exists") is False, None
    got = {"call": page_call(e), "serves": e["serves"]}
    ok = has(got["call"], x["call"]) if "call" in x else True
    if "serves" in x: ok &= got["serves"] == [w.step(r)["id"] for r in x["serves"]]
    return ok, got

EXPECTS.update({"queue": e_queue, "runnable": e_runnable, "turn_state": e_turn_state, "turns_run": e_turns_run, "locator_known": e_locator_known, "steps_by_collection": e_steps_by_collection, "fetched_rows": e_fetched_rows, "fetch_call": e_fetch_call,
                "place": e_place, "place_card": e_place_card, "place_group": e_place_group, "same_place": e_same_place, "event_place": e_event_place, "file_exists": e_file_exists})

def check(keep, show, only=None):
    return scenario.check(os.path.join(SCENARIOS, "loop"), keep, show, only)
