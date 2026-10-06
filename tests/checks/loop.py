"""The loop's tools on the harness tree: the queue, a turn, the runner, the attach and the place resolver, with no network.

The scenarios under tests/fixtures/scenarios/loop/ are walked by tests/checks/scenario.py with the actions and
expectations here added: a turn or a run whose network is a fake standing in for the connectors' answers, the answers
themselves in the scenario's data (a body, an outcome per request, the field a connector wants), never in this file. The
fakes stay code because they exercise the connectors' contract (requests, hits, fetch); nothing here names a person, a
place or a page.
"""
import contextlib, importlib.util, io, json, os, re, shutil, sys, types
from common import BY, FIXTURES, TOOLS, run, tool
import scenario
from scenario import ACTIONS, EXPECTS, SCENARIOS, has, plant_geocoder, plant_wikidata

def queue_module():
    """tools/queue.py loaded by path: importing it by name would shadow the standard library's queue."""
    spec = importlib.util.spec_from_file_location("tree_queue", tool("queue.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def fake_answers(fake):
    """A run_step.run stand-in whose outcomes come from the data: the first run's outcome, then the rest's, one log row per
    connector of the step under that connector's own source, as run_step.run logs them, the errors as the data words them;
    `raise` for a run that raises the data's error instead, the harness's stand-in for a turn that fails outside its runs'
    own reading and requests."""
    seen = []
    def fake_run(cx, cat, tree_id, step, by, dry_run=False, again=False):
        import run_step
        from log_search import log as log_search
        seen.append(step["id"])
        outcome = fake["first"] if len(seen) == 1 else fake.get("then", "none")
        if outcome == "raise": raise RuntimeError(fake["error"])
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
def geocoder_silent():
    """The harness's stand-in for a geocoder that does not answer, for a step whose data says `geocoder_silent`: the geocoder answers from
    the resolver's cache only, and a query the cache lacks, at the limit it is asked at, fails as an endpoint that does not answer, as a
    refusal or a timeout would, with no request made: the request itself (resolve_places.nominatim_request) is what is replaced. Without it a
    query the cache lacks is a request, which fails the scenario (tests/checks/offline.py)."""
    import resolve_places
    def silent(q, limit): raise OSError("the harness has no network")
    with patched(resolve_places, "nominatim_request", silent): yield

def silence(x):
    """geocoder_silent when the step's data asks for it, nothing otherwise."""
    return geocoder_silent() if x.get("geocoder_silent") else contextlib.nullcontext()

def raiser(said):
    def fail(*a, **k): raise RuntimeError(said)
    return fail

@contextlib.contextmanager
def failing(x):
    """The harness's stand-ins for the runner's or the turn's own work failing, as the step's data says under `fails`: a
    code path that raises, never a page or a record. `reading`: every record's reading raises (run_step's extract);
    `requests`: the connector named cannot build its requests from the step's fields; `reconsider`: the tail's reconsider
    raises."""
    import run_step, turn
    from connectors import load
    f = x.get("fails") or {}
    stand_ins = {"reading": (run_step, "extract", "a reader that fails"),
                 "requests": (load(f["requests"]) if f.get("requests") else None, "requests", "a connector that cannot build its requests"),
                 "reconsider": (turn, "reconsider", "a reconsider that fails")}
    with contextlib.ExitStack() as stack:
        for key, (module, name, what) in stand_ins.items():
            if f.get(key): stack.enter_context(patched(module, name, raiser(f"the harness's stand-in for {what}")))
        yield

def state_of(w):
    """This tree's entries of the people who wait, as the file beside the database holds them (<db>.turn-state.json: a
    `waiting` list, or one entry in the one-turn shape), read from the file itself."""
    try:
        with open(w.db + ".turn-state.json", encoding="utf-8") as fh: st = json.load(fh)
    except FileNotFoundError:
        return []
    return [e for e in (st["waiting"] if "waiting" in st else [st]) if e["tree_id"] == w.tid]

# ---------------------------------------------------------------- actions

def reopens(text):
    """The question ids a report names for tools/conclude.py reopen, in the order it names them."""
    return re.findall(r"tools/conclude\.py reopen (\S+) ", text)

def unanswered(fetch):
    """answered_by over the data, and the requests no answer of the data covered: a run that swallows the refusal still fails
    the step (checked)."""
    missed = []
    return answered_by(fetch, missed), missed

def checked(missed):
    """A request the data does not answer fails the step, whatever the code under check made of the refusal."""
    if missed: raise AssertionError(missed[0])

def a_turn(w, x):
    """tools/turn.py start on a person, run_step.run standing in for the network as the data says, or with `fetch` the real
    runner and connectors with only the network call replaced (answered_by), the geocoder's answers the
    fixtures under `geocoder` plant (a query they lack is a request, which fails the scenario unless the step says `geocoder_silent`) and Wikidata's items those under `wikidata`,
    and the stand-ins for the runner's or the turn's own work failing under `fails` (failing); the steps it ran, what it
    printed, and the entries of the people who wait kept beside the database."""
    import run_step, turn
    fake_run, seen = fake_answers(x.get("fake_run") or {"first": "none"})
    fetch, missed = unanswered(x.get("fetch"))
    plant_geocoder(x.get("geocoder") or []); plant_wikidata(x.get("wikidata")); w.cx.commit()
    buf = io.StringIO()
    network = patched(run_step, "fetch", fetch) if x.get("fetch") else patched(run_step, "run", fake_run)
    with network, silence(x), failing(x), contextlib.redirect_stdout(buf): turn.start(w.cx, w.tid, w.slug, w.person(x["person"]), BY, w.db)
    checked(missed)
    out = buf.getvalue()
    return {"seen": seen, "seen_len": len(seen), "distinct": len(set(seen)), "state": state_of(w), "printed": out,
            "left": out.split("left:", 1)[1] if "left:" in out else "", "reopens": reopens(out)}

def a_turn_by_hand(w, x):
    """tools/turn.py as the owner runs it on a person, `turn.py "<name>"` (turn.main): run_step.run standing in for the network
    as the data says, the stand-ins under `fails` as a turn's; what it printed and the status it exited with (None when it
    ran to its end)."""
    import run_step, turn
    fake_run, seen = fake_answers(x.get("fake_run") or {"first": "none"})
    plant_geocoder(x.get("geocoder") or []); plant_wikidata(x.get("wikidata")); w.cx.commit()
    argv = ["turn.py", w.name_of(w.person(x["person"])), "--db", w.db, "--tree", w.slug, "--by", BY]
    buf = io.StringIO(); status = None
    with patched(run_step, "run", fake_run), patched(sys, "argv", argv), silence(x), failing(x), contextlib.redirect_stdout(buf):
        try: turn.main()
        except SystemExit as e: status = e.code
    return {"printed": buf.getvalue(), "exit": status, "seen": seen, "state": state_of(w)}

def a_resume(w, x):
    """The pages dropped into the inbox as a save would leave them, the geocoder's answers and Wikidata's items planted as a turn's
    are, then tools/turn.py --resume; its report, and the entries of the people who wait as it left them."""
    import turn
    for f in x.get("inbox", []): shutil.copy(os.path.join(FIXTURES, f), os.path.join(w.treelib.inbox_dir(), f))
    plant_geocoder(x.get("geocoder") or []); plant_wikidata(x.get("wikidata")); w.cx.commit()
    buf = io.StringIO()
    with silence(x), failing(x), contextlib.redirect_stdout(buf): tail = turn.resume(w.cx, w.tid, w.slug, BY, w.db)
    out = buf.getvalue()
    return {"report": out, "left": out.split("left:", 1)[1] if "left:" in out else "", "state": state_of(w), "reopens": reopens(out),
            "finished": list(tail["credited"])}

def a_turns(w, x):
    """tools/turns.py: what was saved taken in, then turn after turn from the queue, run_step.run standing in for the network as
    the data says (fake_run, as a turn's), the geocoder's answers and Wikidata's items planted as a turn's are, the stand-ins
    under `fails` as a turn's, --turns as `turns` says, the pages `inbox` names dropped into the inbox first, and the page
    `arrives` gives (as `save` takes it) saved into a download folder once the run's opening resume is over, as the owner's
    browser saves a page while the runner goes on; what it printed, the summary, the run's count as it ended, the entries of
    the people who wait, and a refusal's text when it exited."""
    import run_step, turn, turns
    fake_run, seen = fake_answers(x.get("fake_run") or {"first": "none"})
    for f in x.get("inbox", []): shutil.copy(os.path.join(FIXTURES, f), os.path.join(w.treelib.inbox_dir(), f))
    plant_geocoder(x.get("geocoder") or []); plant_wikidata(x.get("wikidata")); w.cx.commit()
    buf = io.StringIO(); refused = None; st = None
    real_resume = turn.resume
    def resume_then_save(*a, **k):
        tail = real_resume(*a, **k)
        if x.get("arrives"): scenario.a_save(w, x["arrives"])
        return tail
    with patched(run_step, "run", fake_run), patched(turn, "resume", resume_then_save), silence(x), failing(x), contextlib.redirect_stdout(buf):
        try: st = turns.run(w.cx, w.tid, w.slug, BY, w.db, turns=x.get("turns"))
        except SystemExit as e: refused = str(e)
    out = buf.getvalue()
    return {"printed": out, "summary": out.split("\nloop:", 1)[1] if "\nloop:" in out else "", "state": st, "turn_state": state_of(w),
            "seen": seen, "refused": refused, "turn_people": [t["person"] for t in (st or {}).get("turns", [])], "passed_people": [p["person"] for p in (st or {}).get("passed", [])]}

def a_next_person(w, x):
    """tools/turns.py's next_person on a run's count the data gives (`turns`: each turn's `person` and its held count before and
    after, as the runner keeps them in the run): the person it names next and the people it passes over, by name, with the
    reasons."""
    import turns
    st = {"turns": [{"person_id": w.person(t["person"]), "person": w.name_of(w.person(t["person"])), "held_before": t["held_before"], "held_after": t["held_after"]} for t in x.get("turns", [])],
          "passed": [], "finished": []}
    e = turns.next_person(w.cx, w.tid, st, w.db)
    return {"named": e["name"] if e else None, "passed": [p["person"] for p in st["passed"]], "reasons": [p["reason"] for p in st["passed"]]}

def a_clear_state(w, x):
    import turn; turn.write_state(w.db, []); return {}

def a_old_turn_state(w, x):
    """A state kept beside the database in the one-turn shape, a turn on `person` paused on its pages, its keys as the
    owner's own state file holds them: the tree, the person, the moment it paused (`at`), who existed then, and the held,
    decided and unanswered lines of the turn so far, empty. No page or record of anyone: who the turn was on, by the
    harness's own people."""
    import turn
    pid = w.person(x["person"])
    before = dict(w.cx.execute("SELECT id, display_name FROM person WHERE tree_id=?", (w.tid,)).fetchall())
    st = {"tree_id": w.tid, "tree": w.slug, "person_id": pid, "person": w.name_of(pid), "started_at": x["at"],
          "before_ids": before, "held": [], "decided": [], "unanswered": []}
    with open(turn.state_path(w.db), "w", encoding="utf-8") as fh: json.dump(st, fh)
    return {"person_id": pid}

def asked_at(fixture):
    """Where a saved real response was asked: the locator its manifest gives (<stem>.manifest.json), or the archive locator its
    sidecar gives (<stem>.expect.json); None for a fixture with neither."""
    stem = os.path.join(FIXTURES, fixture.rsplit(".", 1)[0])
    for path, key in ((stem + ".manifest.json", None), (stem + ".expect.json", "archive")):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh: d = json.load(fh)
            loc = ((d.get(key) if key else d) or {}).get("locator") or {}
            if loc.get("kind") == "url": return loc["value"]
    return None

def served(fixture):
    """The headers a saved real response came with, as its manifest records them (<stem>.manifest.json's http: status, etag,
    last_modified); {} for a fixture whose manifest records none or that has a sidecar instead."""
    path = os.path.join(FIXTURES, fixture.rsplit(".", 1)[0] + ".manifest.json")
    if not os.path.exists(path): return {}
    with open(path, encoding="utf-8") as fh: return json.load(fh).get("http") or {}

def answers_request(loc, url, data):
    """Whether a response asked at `loc` is the answer to this request: a GET at the locator's own URL (a fragment marks an
    excerpt of that answer: #excerpt, #bytes=), or a form posted to the locator's host whose fields carry the values the
    locator's fragment records (the gravesite locator's #lastName=...&firstName=...)."""
    import urllib.parse
    base, _, frag = loc.partition("#")
    if data: return urllib.parse.urlsplit(url).netloc == urllib.parse.urlsplit(base).netloc and all(str(data.get(k, "")) == v for k, v in urllib.parse.parse_qsl(frag) if k in data)
    return url == base

CHALLENGE = b"<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>the harness's stand-in for a holder's challenge page</body></html>"

def answered_by(fetch, missed=None):
    """The network call a run is played back with, from the data: `answers`, one for each request, in the order the requests
    come. An answer is for the first request carrying its `url_has` that no earlier request has taken (with `every`, for every
    such request): a saved real response (`fixture` under tests/fixtures/, its `content_type`), which answers only the request
    it was asked at (asked_at), with the status, ETag and Last-Modified its manifest records (served; status 200 and neither
    header where it records none); an `error` the source's connection raises, the harness's stand-in for a holder that did not
    answer (a timeout, a refusal); or `challenge`, the harness's stand-in for a challenge or maintenance page a holder serves
    with status 200 in place of its answer (CHALLENGE, text/html), which carries no record of anyone (docs/DATA-ARCHITECTURE.md
    §7 decision 8). A request the data does not answer, or answers with another request's response, fails the run, and is
    written to `missed` so that the step fails even when the runner makes an error run of it (checked); no `fetch` means no
    network at all."""
    import urllib.error
    used = set(); missed = [] if missed is None else missed
    def meta(url, content_type, fixture=None):
        h = served(fixture) if fixture else {}
        return {"status": h.get("status", 200), "etag": h.get("etag"), "last_modified": h.get("last_modified"), "final_url": url, "content_type": content_type}
    def refused(said):
        missed.append(said)
        return AssertionError(said)
    def fake_fetch(url, kind, c, data=None):
        for i, ans in enumerate((fetch or {}).get("answers", [])):
            if i in used or ans["url_has"] not in url: continue
            if not ans.get("every"): used.add(i)
            if ans.get("error"): raise urllib.error.URLError(ans["error"])
            if ans.get("challenge"): return CHALLENGE, meta(url, "text/html; charset=utf-8")
            loc = asked_at(ans["fixture"])
            if loc and not answers_request(loc, url, data): raise refused(f"{ans['fixture']} is the answer to {loc}, not to {url}{' ' + json.dumps(data) if data else ''}")
            with open(os.path.join(FIXTURES, ans["fixture"]), "rb") as fh: return fh.read(), meta(url, ans.get("content_type", "application/json"), ans["fixture"])
        raise refused(f"a request went out that the data does not answer: {url}")
    return fake_fetch

def a_run(w, x):
    """tools/run_step.py run on one step through its real connectors, only the network call replaced (answered_by); `dry` for
    --dry-run, no request allowed, `again` for a run by the step's id, every connector asked; the stand-ins under `fails`
    (failing). The result carries each connector's run (`failed`, the failure a run that failed names) and, under `records`,
    the sha256 of every record the runner archived and read, and under `archived` of every response it archived."""
    import run_step
    st = w.step(x["step"]); cat = w.catalog()
    fetch, missed = unanswered(None if x.get("dry") else x.get("fetch"))
    with patched(run_step, "fetch", fetch), failing(x):
        w.cx.execute("BEGIN"); res = run_step.run(w.cx, cat, w.tid, st, BY, dry_run=bool(x.get("dry")), again=bool(x.get("again"))); w.cx.commit()
    checked(missed)
    return {"step": st["id"], "results": [{"connector": r.get("connector"), "source": r.get("source"), "asked": r.get("asked"), "answered": r.get("answered"), "outcome": r.get("outcome"),
                                          "requests": r.get("requests"), "wants": r.get("wants"), "error": r.get("error"), "errors": r.get("errors"), "failed": r.get("failed"),
                                          "proposals": (r.get("extracted") or [{}])[0].get("proposals"), "extraction": (r.get("extracted") or [{}])[0].get("extraction")} for r in res],
            "records": [e["sha256"] for r in res for e in r.get("extracted") or [] if "extraction" in e],
            "archived": [a for r in res for a in r.get("artifacts") or []],
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
    builds and the runner sends, the run's outcome and the query and note the run logged. `dry`: run_step.run in dry-run mode
    instead, saying whether the runner would ask the connector again on the step's current fields."""
    import run_step
    from connectors import load
    st = w.step(x["step"]); conn = load(x["connector"])
    if x.get("dry"):
        res = run_step.run(w.cx, w.catalog(), w.tid, st, BY, dry_run=True)
        return {"results": [{"connector": r.get("connector"), "asked": r.get("asked"), "answered": r.get("answered")} for r in res]}
    fetch, missed = unanswered(x.get("fetch"))
    with patched(run_step, "fetch", fetch): r = run_step.run_connector(w.cx, w.catalog(), w.tid, st, conn, BY)
    checked(missed)
    logged = w.cx.execute("SELECT query_json, notes FROM search_log WHERE plan_step_id=? AND superseded_by IS NULL ORDER BY executed_at DESC, id DESC", (st["id"],)).fetchone()
    return {"outcome": r.get("outcome"), "requests": r.get("requests"), "logged_query": json.loads(logged[0]) if logged else {}, "logged_note": logged[1] if logged else None}

def a_resolve(w, x):
    """tools/resolve_places.py on the strings named (--only, one run each) with the geocoder's answers planted in its cache,
    Wikidata's items in its own, and the gazetteers' answers (GOV's and Wikidata's searches, each fixture a list of the
    resolver's own cache records) under the paths the resolver reads them from, so no request goes out; the strings must
    already be the tree's. With `geocoder_silent` the tool runs in this process (resolve_places.main) under the harness's
    stand-in for a geocoder that does not answer (geocoder_silent), so a query the cache lacks at the limit it is asked at
    is no request but an endpoint that does not answer."""
    import resolve_places
    plant_geocoder(x.get("geocoder", [])); plant_wikidata(x.get("wikidata"))
    for fixture in x.get("gazetteer", []):
        with open(os.path.join(FIXTURES, fixture), encoding="utf-8") as fh: records = json.load(fh)
        for rec in records:
            path = resolve_places.gazetteer_cache_path(rec["service"], rec["args"]); os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh: json.dump(rec, fh, ensure_ascii=False)
    w.cx.commit()
    argv = lambda raw: ["--db", w.db, "--tree", w.slug, "--by", BY, "--only", raw]   # one string at a time: the tree's other strings never reach the network
    if not x.get("geocoder_silent"): return {"printed": "".join(run(tool("resolve_places.py"), *argv(raw)) for raw in x["only"])}
    buf = io.StringIO()
    for raw in x["only"]:
        with patched(sys, "argv", ["resolve_places.py", *argv(raw)]), silence(x), contextlib.redirect_stdout(buf): resolve_places.main()
    return {"printed": buf.getvalue()}

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

def a_browser_script(w, x):
    """One of the scripts the owner's browser runs (tools/<file>) read as the browser tool runs it: `awaited` whether its code,
    past the comment lines that head it, is one awaited call of an async function (the tool returns an awaited value and gives
    {} for a promise still pending), and `call`, what it ends with, the placeholder call the fetch list's line replaces."""
    with open(os.path.join(TOOLS, x["file"]), encoding="utf-8") as fh: code = "\n".join(l for l in fh.read().splitlines() if not l.startswith("//")).strip()
    return {"awaited": code.startswith("await (async function"), "call": code[code.rindex("})(") + 2:] if "})(" in code else None}

def a_save_names(w, x):
    """fetches.distinct_names on the entries the data gives, each a link (`url`) and the name save_as built for it (`save_as`),
    as the fetch list holds them: the names the list then prints, in order."""
    from fetches import distinct_names
    return {"names": [e["save_as"] for e in distinct_names([{"url": e["url"], "save_as": e["save_as"]} for e in x["entries"]])]}

def a_task(w, x):
    """run_task.run_fetch on the fetch list's entry serving a step, the launcher's process replaced (run_task.spawn) as the data
    says and nothing else: `silent` a launcher that does not answer (`timeout`: it outlives the timeout; `exit`: it exits with
    that status and prints nothing), or `captured` a fixture holding a launcher's own output, printed as it was captured. `saves`
    is a real page that comes into the data root's downloads/ while the launcher runs, as the owner's browser leaves it, or a
    list of them: a `fixture` under the entry's own file name (or `name`), with the entry's key written under its saved-from
    line when `key` is true. The run's row as run_fetch returns it, and the command the launcher was started with.

    With `session` the task goes through the session's launcher instead, no process started: run_task.hand_out on the entry, the
    page under `saves` coming in while the task is out, then run_task.report_done with what a session reported of its subagent:
    `{"captured": fixture}`, a file `tools/run_task.py done --out` wrote (the answer as it came, the tokens, the tool uses, the
    time), or `"silent"`, a subagent that ended with no message and no measures. The result adds `handout`, the words the session
    was handed, `state` the task as written beside the database, `out_twice` the refusal of a second task while one is out, and
    `done_twice` the refusal of a second report."""
    import subprocess, run_task
    from fetches import openable
    sid = w.step(x["step"])["id"]
    e = next(e for e in openable(w.cx, w.tid) if sid in e["step_ids"])
    seen = {}
    def comes_in():
        for page in (x["saves"] if isinstance(x.get("saves"), list) else [x["saves"]] if x.get("saves") else []):
            data = w.fixture_bytes(page)
            if page.get("key"):
                top, nl, rest = data.partition(b"\n")
                if not top.startswith(b"<!-- saved from "): raise KeyError("a key goes under the page's saved-from line, and this page has none")
                data = top + nl + f"<!-- for steps {','.join(e['serves'])} -->\n".encode() + rest
            with open(os.path.join(w.treelib.downloads_dir(), page.get("name") or e["save_as"]), "wb") as fh:
                fh.write(data)
    def refusal(call):
        try:
            call()
        except SystemExit as ex:
            return str(ex)
        return None
    if "session" in x:
        w.cx.commit()
        state = run_task.hand_out(w.tid, w.db, e, x["model"])
        out_twice = refusal(lambda: run_task.hand_out(w.tid, w.db, e, x["model"]))
        comes_in()
        given = {}
        if x["session"] != "silent":
            with open(os.path.join(FIXTURES, x["session"]["captured"]), encoding="utf-8") as fh:
                given = json.load(fh)
        r = run_task.report_done(w.cx, w.tid, w.slug, w.db, BY, given.get("answer"), given.get("tokens"), given.get("tool_uses"), given.get("duration_ms"))
        done_twice = refusal(lambda: run_task.report_done(w.cx, w.tid, w.slug, w.db, BY, None, None, None, None))
        return {**r, "printed": run_task.run_line(r), "entry": e, "handout": run_task.handout(state), "state": state, "out_twice": out_twice, "done_twice": done_twice}
    def stand_in(cmd, timeout, cwd):
        seen["cmd"] = cmd
        comes_in()
        if x.get("silent") == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        if "silent" in x:
            return int(x["exit"]), ""
        with open(os.path.join(FIXTURES, x["captured"]), encoding="utf-8") as fh:
            return 0, fh.read()
    w.cx.commit()
    with patched(run_task, "spawn", stand_in):
        r = run_task.run_fetch(w.cx, w.tid, w.slug, e, BY, x["model"], x["effort"], x.get("budget", 0.05), x.get("timeout", 5))
    cmd = seen.get("cmd") or []
    after = lambda flag: cmd[cmd.index(flag) + 1] if flag in cmd else None
    return {**r, "printed": run_task.run_line(r), "entry": e,
            "command": {"flags": [c for c in cmd if c.startswith("-")], "mcp_config": after("--mcp-config"), "model": after("--model"), "effort": after("--effort"), "tools": after("--tools"), "budget": after("--max-budget-usd"),
                        "prompt": after("-p"), "system_prompt_is_the_text": after("--system-prompt") == run_task.task_text("fetch")[0], "schema": json.loads(after("--json-schema") or "null")}}

ACTIONS.update({"task": a_task, "save_names": a_save_names, "browser_script": a_browser_script, "decide_place": a_decide_place, "step_query": a_step_query, "turn": a_turn, "turn_by_hand": a_turn_by_hand, "turns": a_turns, "resume": a_resume, "next_person": a_next_person, "clear_state": a_clear_state, "old_turn_state": a_old_turn_state,
                "run": a_run, "run_all": a_run_all, "run_connector": a_run_connector,
                "resolve": a_resolve, "place_string": a_place_string, "apply_places": a_apply_places, "fetch_list": a_fetch_list})

# ---------------------------------------------------------------- expectations

def e_queue(w, x, want):
    """tools/queue.py's edge, the people who wait read from beside the database as the tool reads them: who is named next and
    who is passed over, each with the reason."""
    import turn
    out, passed = queue_module().edge(w.cx, w.tid, turn.waits(w.cx, w.db, w.tid))
    got = {"named": [{"name": e["name"], "reason": e["reason"]} for e in out], "passed": [{"name": e["name"], "reason": e["reason"]} for e in passed]}
    ok = True
    for ref in x.get("named", []): ok &= any(e["id"] == w.person(ref) for e in out)
    for ref in x.get("not_named", []): ok &= not any(e["id"] == w.person(ref) for e in out)
    for ref in x.get("passed", []): ok &= any(e["id"] == w.person(ref) for e in passed)
    for ref in x.get("not_passed", []): ok &= not any(e["id"] == w.person(ref) for e in passed)
    if "first" in x: ok &= bool(out) and out[0]["id"] in [w.person(r) for r in (x["first"] if isinstance(x["first"], list) else [x["first"]])]
    if "first_reason" in x: ok &= bool(out) and has(out[0]["reason"], x["first_reason"])
    reasons = x.get("reasons") or {}
    for ref, pat in (reasons.items() if isinstance(reasons, dict) else reasons): ok &= any(e["id"] == w.person(ref) and has(e["reason"], pat) for e in out + passed)   # a list of [person, pattern] pairs names a person no key can, one the rule created
    if "passed_count" in x: ok &= has(len(passed), x["passed_count"])
    return ok, got

def e_runnable(w, x, want):
    import run_step
    ids = {r["id"] for r in run_step.runnable(w.cx, w.catalog(), w.tid)}
    st = w.step(x["step"]); v = st is not None and st["id"] in ids
    return v == x.get("is", True), v

def e_turn_state(w, x, want):
    """The people who wait, as kept beside the database (this tree's entries): with `person`, that person's entry, matching
    `is` when given, or with `is` null no entry for them; without, `is` null for nobody waiting, or a pattern over the
    entries."""
    entries = state_of(w)
    if "person" not in x: return (not entries if x.get("is") is None else has(entries, x["is"])), entries
    mine = next((e for e in entries if e["person_id"] == w.person(x["person"])), None)
    if "is" in x and x["is"] is None: return mine is None, mine
    return mine is not None and has(mine, x.get("is", {})), mine

def e_kept_places(w, x, want):
    """The place strings the geocoder left unanswered, as kept beside the database for this tree (<db>.turn-state.json's
    `places`, read from the file itself): their words, matching `is`."""
    try:
        with open(w.db + ".turn-state.json", encoding="utf-8") as fh: st = json.load(fh)
    except FileNotFoundError:
        st = {}
    raws = sorted(p["raw"] for p in (st.get("places") or []) if p["tree_id"] == w.tid)
    return has(raws, x["is"]), raws

def e_turns_run(w, x, want):
    """The runner's count as the last turns action left it: the turns in order (each a person, whether it held nothing new,
    whether it failed, and whether the person waits on pages to save now), the people passed over this run and the people
    who waited whose turns it finished."""
    st = (w.env.get("last") or {}).get("state") or {}
    waiting_now = {e["person_id"] for e in state_of(w)}
    turns = []
    for t in st.get("turns", []):
        nothing_new = t.get("held_after") is not None and t["held_after"] <= t["held_before"]
        turns.append({"person": t["person_id"], "nothing_new": nothing_new, "failed": bool(t.get("failed")), "waits": t["person_id"] in waiting_now})
    got = {"turns": turns, "passed": [p["person_id"] for p in st.get("passed", [])], "finished": [p["person_id"] for p in st.get("finished", [])]}
    ok = True
    if "turns" in x:
        ok &= len(got["turns"]) == len(x["turns"])
        for g, wnt in zip(got["turns"], x["turns"]):
            ok &= g["person"] == w.person(wnt["person"]) and all(g[k] == wnt[k] for k in ("nothing_new", "failed", "waits") if k in wnt)
    for ref in x.get("passed", []): ok &= w.person(ref) in got["passed"]
    for ref in x.get("not_passed", []): ok &= w.person(ref) not in got["passed"]
    if "finished" in x: ok &= got["finished"] == [w.person(r) for r in x["finished"]]
    named = {"turns": [{**t, "name": w.name_of(t["person"])} for t in got["turns"]]}
    named.update({k: [w.name_of(p) for p in got[k]] for k in ("passed", "finished")})
    return ok, named

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

def e_task_run(w, x, want):
    """The task_run rows, in the order written, each with its JSON columns read (`steps`, `task`, `usage`, `answer`), `differs` as
    a boolean, `text_is_current` saying whether its hash is tools/tasks/<kind>.md's now, and `log` the search_log row it names
    (its step's key and its outcome), or none."""
    import run_task
    rows = [dict(r) for r in w.cx.execute("SELECT * FROM task_run WHERE tree_id=? ORDER BY id", (w.tid,))]
    for r in rows:
        r["steps"] = json.loads(r.pop("plan_step_ids_json"))
        r["task"] = json.loads(r.pop("task_json"))
        r["usage"] = json.loads(r.pop("usage_json") or "null")
        r["answer"] = json.loads(r.pop("answer_json") or "null")
        r["differs"] = bool(r["differs"])
        r["text_is_current"] = r["task_text_sha256"] == run_task.task_text(r["task_kind"])[1]
        log = w.cx.execute("SELECT l.outcome, sp.step_key FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE l.id=?", (r["search_log_id"],)).fetchone()
        r["log"] = dict(log) if log else None
    return has(rows, w.value(x["is"])), [{k: r[k] for k in ("launcher", "task_kind", "holder_id", "model", "effort", "ended", "total_tokens", "tool_uses", "outcome", "differs", "cost_usd", "turns", "input_tokens", "output_tokens", "answer", "note", "log")} for r in rows]

EXPECTS.update({"task_run": e_task_run, "kept_places": e_kept_places, "queue": e_queue, "runnable": e_runnable, "turn_state": e_turn_state, "turns_run": e_turns_run, "locator_known": e_locator_known, "steps_by_collection": e_steps_by_collection, "fetched_rows": e_fetched_rows, "fetch_call": e_fetch_call,
                "place": e_place, "place_card": e_place_card, "place_group": e_place_group, "same_place": e_same_place, "event_place": e_event_place, "file_exists": e_file_exists})

def check(keep, show, only=None):
    return scenario.check(os.path.join(SCENARIOS, "loop"), keep, show, only)
