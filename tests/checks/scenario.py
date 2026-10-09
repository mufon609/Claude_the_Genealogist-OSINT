"""One walker for the scenarios under tests/fixtures/scenarios/: the matcher, the standing rule, the decision writers
and the loop's tools run on the harness tree as the data says, and what they write or refuse checked as the data says.

A scenario file names the tree to ingest (tests/fixtures/harness.ged, the owner's own export cut down) and a list of
steps. A step does one thing (an action) and then checks any number of expectations; the vocabulary of both is in
tests/fixtures/README.md. An entry of `expect` is one expectation and its `why`: a step or an entry carrying any other key fails.
A scenario fails too when a process it starts asks for a connection to any host but this machine (tests/checks/offline.py).
People are named by the harness file's own entry ids, records by the label a step bound them under, and nothing in this
module names a person, a place or a page: another family's export, fixtures and scenarios run through it unchanged.
"""
import contextlib, json, os, shutil, sqlite3, subprocess, sys
import offline
from common import BY, FIXTURES, ROOT, TOOLS, Fails, connect, done, run, scratch, tool, whole

SCENARIOS = os.path.join(FIXTURES, "scenarios")
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"   # the smallest of JPEG files: the stand-in for a family-held photograph, which only the owner may put in tests/

def has(value, wanted):
    """The pattern language every expectation shares: a dict matches the keys given (a value or a pattern each), a list
    matches its length and each element, a string or number equals; {">=": n}, {"<=": n}, {"has": x} (a substring, or
    an element), {"lacks": x}, {"starts": s}, {"ends": s}, {"len": n}, {"some": p} (an element matching p),
    {"none": p}, {"every": p}, {"not": p}, {"in": [..]}, {"is": null}, {"any": true} (anything but nothing)."""
    if isinstance(wanted, dict):
        ops = {">=", "<=", "has", "lacks", "starts", "ends", "first", "len", "some", "none", "every", "not", "in", "is", "any", "keys"}
        if set(wanted) <= ops and wanted:
            for op, w in wanted.items():
                if op == ">=" and not (isinstance(value, (int, float)) and value >= w): return False
                if op == "<=" and not (isinstance(value, (int, float)) and value <= w): return False
                if op == "has" and not (value is not None and all(holds(value, x) for x in (w if isinstance(w, list) else [w]))): return False
                if op == "lacks" and not (value is None or (all(x not in value for x in w) if isinstance(w, list) else w not in value)): return False
                if op == "starts" and not (isinstance(value, str) and value.startswith(w)): return False
                if op == "ends" and not (isinstance(value, str) and value.endswith(w)): return False
                if op == "first" and not (isinstance(value, (list, tuple)) and value and has(value[0], w)): return False
                if op == "len" and not (value is not None and has(len(value), w)): return False
                if op == "some" and not (isinstance(value, (list, dict)) and any(has(v, w) for v in (value.values() if isinstance(value, dict) else value))): return False
                if op == "none" and not (value is None or not any(has(v, w) for v in (value.values() if isinstance(value, dict) else value))): return False
                if op == "every" and not (isinstance(value, (list, dict)) and all(has(v, w) for v in (value.values() if isinstance(value, dict) else value))): return False
                if op == "not" and has(value, w): return False
                if op == "in" and value not in w: return False
                if op == "is" and value is not w: return False
                if op == "any" and not value: return False
                if op == "keys" and not (isinstance(value, dict) and set(w) <= set(value)): return False
            return True
        return isinstance(value, dict) and all(has(value.get(k), w) for k, w in wanted.items())
    if isinstance(wanted, list): return isinstance(value, (list, tuple)) and len(value) == len(wanted) and all(has(v, w) for v, w in zip(value, wanted))
    return value == wanted

def holds(value, x):
    """One thing a value has: a substring of a text, an element of a list (equal, or matching a pattern), a key of a dict."""
    if isinstance(value, str): return isinstance(x, str) and x in value
    if isinstance(value, dict): return x in value
    if isinstance(value, (list, tuple)): return any(v == x or (isinstance(x, (dict, list)) and has(v, x)) for v in value)
    return False

def short(x, n=400):
    try: s = json.dumps(x, default=str, ensure_ascii=False)
    except Exception: s = repr(x)
    return s if len(s) <= n else s[:n] + "…"

STEP_KEYS = ("say", "expect", "at", "as")           # what a step may carry besides its one action

class Walker:
    """The scenario's state: the scratch, the tree, the labels steps bound, and the last action's result."""
    def __init__(self, spec, keep, show):
        self.spec, self.keep, self.show = spec, keep, show
        self.title = spec.get("title", "scenario")
        self.env = {}; self.fails = Fails(); self.step_no = 0
        self.undo = []                                  # the stand-ins a step put in place for the rest of the scenario, lifted when it ends

    # ---------------------------------------------------------------- the tree
    def open(self):
        self.root, self.db = scratch(self.keep)
        import treelib; self.treelib = treelib
        tree = self.spec.get("tree") or {}
        self.slug = tree.get("slug", "harness")
        run(tool("tree.py"), "--db", self.db, "--by", BY, "create", self.slug, "--name", tree.get("name", "Harness"))
        if tree.get("file"): run(tool("ingest_gedcom.py"), os.path.join(FIXTURES, tree["file"]), "--keep", "--db", self.db, "--tree", self.slug, "--by", BY)
        self.cx = connect(self.db)
        self.tid = self.cx.execute("SELECT id FROM tree WHERE slug=?", (self.slug,)).fetchone()[0]
        imp = self.cx.execute("SELECT artifact_sha256 FROM tree_import WHERE tree_id=?", (self.tid,)).fetchone()
        self.env["import"] = {"sha": imp[0] if imp else None}                    # the file itself, for a vouch that rests on it
        if tree.get("home"): self.cx.execute("UPDATE tree SET home_person_id=? WHERE id=?", (self.person(tree["home"]), self.tid)); self.cx.commit()
        if tree.get("plan"):
            from plan import plan_person
            for pid, in self.cx.execute("SELECT id FROM person WHERE tree_id=?", (self.tid,)): plan_person(self.cx, self.tid, pid, BY)
            self.cx.commit()

    @contextlib.contextmanager
    def clock(self, at):
        """With `at`, the clock every tool reads (treelib.now, which each tool imported by name) stands at that second while the step's action runs,
        so decisions taken a second apart by the wall clock carry one second, as the rule's decisions within a run may."""
        if not at: yield; return
        real = self.treelib.now; fake = lambda: at
        modules = lambda: [m for m in list(sys.modules.values()) if m is not None and getattr(m, "now", None) in (real, fake)]
        for m in modules():
            if m.now is real: m.now = fake
        try: yield
        finally:
            for m in modules():
                if m.now is fake: m.now = real

    def close(self):
        for lift in reversed(self.undo): lift()
        w = whole(self.cx)
        if w: self.fails.append(w)
        self.fails.extend(offline.words(offline.sent(self.title)))
        self.cx.close(); done(self.root, self.keep, self.title)

    # ---------------------------------------------------------------- references
    def value(self, x):
        """A value in the data: "$label" or "$label.key.key" reads what a step bound; anything else is itself."""
        if isinstance(x, str) and x.startswith("$"):
            parts = x[1:].split("."); v = self.env.get(parts[0])
            for p in parts[1:]:
                if isinstance(v, dict): v = v.get(p)
                elif isinstance(v, (list, tuple)) and p.isdigit(): v = v[int(p)]
                else: v = getattr(v, p, None)
            return v
        if isinstance(x, list): return [self.value(v) for v in x]
        if isinstance(x, dict): return {k: self.value(v) for k, v in x.items()}
        return x

    def person(self, ref):
        """A person: the harness file's entry id, {"name": display name}, {"created": display name} for one the rule
        made, or "$label" bound to a person id."""
        if ref is None: return None
        if isinstance(ref, dict):
            if "name" in ref or "created" in ref:
                rows = self.cx.execute("SELECT id FROM person WHERE tree_id=? AND display_name=? AND merged_into IS NULL ORDER BY created_at", (self.tid, ref.get("name") or ref.get("created"))).fetchall()
                if not rows: raise KeyError(f"no person named {ref}")
                return rows[-1][0] if "created" in ref else rows[0][0]
            if "person" in ref: return self.person(ref["person"])
        if isinstance(ref, str) and ref.startswith("$"): return self.value(ref)
        row = self.cx.execute("SELECT entity_id FROM external_id WHERE tree_id=? AND entity_kind='person' AND system='ancestry_gedcom_xref' AND value=?", (self.tid, ref)).fetchone()
        if not row: raise KeyError(f"no person with entry id {ref}")
        return row[0]

    def people(self, refs): return [self.person(r) for r in (refs if isinstance(refs, list) else [refs])]

    def name_of(self, pid):
        r = self.cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone(); return r[0] if r else None

    def sha(self, label):
        v = self.value(label if str(label).startswith("$") else "$" + str(label))
        return v["sha"] if isinstance(v, dict) else v

    def card(self, ref):
        """A proposal row: {"record": label, "person": ref} the card putting the record's persona to that person,
        {"record": label, "persona": name[, "role": role]} the card of that persona, or "$label" a bound proposal id."""
        if isinstance(ref, str): return self.cx.execute("SELECT * FROM proposal WHERE id=?", (self.value(ref),)).fetchone()
        sha = self.sha(ref["record"]); kinds = ref.get("kinds", ["persona_match", "new_person"])
        rows = self.cx.execute(f"""SELECT p.*, pe.name_text AS persona_name, pe.role_in_record AS persona_role FROM proposal p JOIN persona pe ON pe.id=json_extract(p.payload_json,'$.persona_id')
                                   WHERE p.tree_id=? AND json_extract(p.payload_json,'$.artifact_sha256')=? AND p.kind IN ({','.join('?' * len(kinds))}) ORDER BY p.created_at, p.id""", (self.tid, sha, *kinds)).fetchall()
        if "person" in ref: pid = self.person(ref["person"]); rows = [r for r in rows if json.loads(r["payload_json"]).get("person_id") == pid]
        if "persona" in ref: rows = [r for r in rows if r["persona_name"] == ref["persona"]]
        if "role" in ref: rows = [r for r in rows if (r["persona_role"] or "") == ref["role"]]
        if isinstance(ref.get("status"), str): rows = [r for r in rows if r["status"] == ref["status"]]
        if "extraction" in ref: xid = self.value(ref["extraction"]); rows = [r for r in rows if json.loads(r["payload_json"]).get("extraction_id") == xid]
        return rows[-1] if rows and ref.get("latest") else (rows[0] if rows else None)

    def cards_on(self, label, status=None, kinds=("persona_match", "new_person")):
        sha = self.sha(label)
        rows = self.cx.execute(f"SELECT * FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.artifact_sha256')=? AND kind IN ({','.join('?' * len(kinds))}) ORDER BY created_at, id", (self.tid, sha, *kinds)).fetchall()
        return [r for r in rows if status is None or r["status"] == status]

    def step(self, ref):
        """A plan step: {"person": ref, "step_key": key} or "step_key_like", or "locator": {"kind","value"}, or "$label"."""
        if isinstance(ref, str): return self.cx.execute("SELECT * FROM search_plan WHERE id=?", (self.value(ref),)).fetchone()
        q = "SELECT * FROM search_plan WHERE person_id=?"; args = [self.person(ref["person"])]
        if "step_key" in ref: q += " AND step_key=?"; args.append(ref["step_key"])
        if "step_key_like" in ref: q += " AND step_key LIKE ?"; args.append(ref["step_key_like"])
        if "row_key" in ref: q += " AND row_key=?"; args.append(ref["row_key"])
        if "row_key_like" in ref: q += " AND row_key LIKE ?"; args.append(ref["row_key_like"])
        if "holder" in ref: q += " AND locator_source_id=?"; args.append(ref["holder"])
        if "locator" in ref: q += " AND locator_kind=? AND locator_value=?"; args += [ref["locator"]["kind"], ref["locator"]["value"]]
        if "kind" in ref: q += " AND kind=?"; args.append(ref["kind"])
        if "status" in ref: q += " AND status=?"; args.append(ref["status"])
        if "mode" in ref: q += " AND mode=?"; args.append(ref["mode"])
        rows = self.cx.execute(q + " ORDER BY seq, created_at", args).fetchall()
        return rows[0] if rows else None

    def steps(self, ref):
        s = self.step(ref); return [s] if s else []

    def catalog(self):
        from catalog import Catalog
        return Catalog(self.cx, self.tid)

    def source(self, sid): return self.cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id=?", (sid,)).fetchone()

    def collection(self, source, name):
        row = self.cx.execute("SELECT id FROM collection WHERE source_id=? AND name=?", (source, name)).fetchone()
        if row: return row[0]
        cid = self.treelib.ulid()
        self.cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid, source, name, "other", "harness:" + cid))
        return cid

    def fixture_bytes(self, a):
        """The bytes an archive step archives: a fixture as it is, or the stand-in for a family-held photograph (`stand_in:
        "image"`). The harness writes no page of its own: the same page saved twice is two real saves under tests/fixtures/."""
        if a.get("fixture"):
            with open(os.path.join(FIXTURES, a["fixture"]), "rb") as fh: return fh.read()
        if a.get("stand_in") == "image": return JPEG
        raise KeyError("no fixture: every page the harness archives or saves is a real one under tests/fixtures/")

    # ---------------------------------------------------------------- the walk
    def walk(self):
        self.open()
        try:
            for step in self.spec["steps"]:
                self.step_no += 1
                self.env["last"] = None
                if self.show: print("    -", step.get("say") or short({k: v for k, v in step.items() if k not in ("expect", "say")}, 160))
                acts, odd = [k for k in step if k in ACTIONS], [k for k in step if k not in ACTIONS and k not in STEP_KEYS]
                if len(acts) > 1 or odd:                    # a step does one thing: a second action or a word the walker does not know would be skipped unseen
                    self.fails.append(f"step {self.step_no}: " + "; ".join(([f"one action per step, not {acts}"] if len(acts) > 1 else []) + ([f"no such action {odd}"] if odd else []))); continue
                action = acts[0] if acts else None
                if action:
                    try:
                        with self.clock(step.get("at")): self.env["last"] = ACTIONS[action](self, self.value(step[action]) if action not in ("transcribe", "place_card", "step", "fake_run", "fake_fetch", "run", "run_all", "run_connector") else step[action])
                    except Exception as e:
                        self.fails.append(f"step {self.step_no} ({step.get('say') or action}) raised {type(e).__name__}: {e}"); self.cx.rollback()
                        if self.show: import traceback; traceback.print_exc()
                        continue
                    self.cx.commit()
                    if "as" in step: self.env[step["as"]] = self.env["last"]
                for want in step.get("expect", []):
                    kinds, odd = [k for k in want if k in EXPECTS], [k for k in want if k not in EXPECTS and k != "why"]
                    if len(kinds) != 1 or odd:                  # an entry is one expectation and its why: a key beside it is a claim in the wrong place, which nothing would ever check
                        self.fails.append(f"step {self.step_no}: " + (f"one expectation per entry, not {kinds}" if len(kinds) > 1 else f"no such expectation {list(want)}" if not kinds else f"{odd} sit beside {kinds[0]}, not inside it"))
                        continue
                    kind = kinds[0]
                    try: ok, got = EXPECTS[kind](self, want[kind], want)
                    except Exception as e:
                        ok, got = False, f"raised {type(e).__name__}: {e}"
                        if self.show: import traceback; traceback.print_exc()
                    if not ok: self.fails.append(f"step {self.step_no} ({step.get('say') or action}) {kind}: {want.get('why') or short(want[kind], 160)}; got {short(got)}")
        finally: self.close()
        return self.fails

# ---------------------------------------------------------------- actions: what a step does; each returns what it wrote, bound under "as"

def a_plan(w, x):
    from plan import plan_person
    pids = [p for p, in w.cx.execute("SELECT id FROM person WHERE tree_id=? AND merged_into IS NULL", (w.tid,))] if x == "all" else w.people(x)
    return {w.name_of(p): plan_person(w.cx, w.tid, p, BY) for p in pids}

def a_migrate(w, x):
    """tools/initdb.py --migrate on the scratch catalog itself: its printed line, for a data correction a migration
    version carries to be checked against a row put in the shape it corrects. A scratch catalog is born current, every
    MIGRATIONS version already recorded applied, never behind; {"reset_to": version} first forgets every later version's
    row, so --migrate meets the correction the way an older catalog actually upgraded through it would. {"refused": true}: a
    correction that refuses is the outcome expected, and what it printed comes back as refused."""
    if isinstance(x, dict) and x.get("reset_to"): w.cx.execute("DELETE FROM schema_migration WHERE version > ?", (x["reset_to"],))
    w.cx.commit()
    try: return {"printed": run(tool("initdb.py"), "--db", w.db, "--migrate").strip()}
    except RuntimeError as e:
        if isinstance(x, dict) and x.get("refused"): return {"refused": str(e)}
        raise

def a_sync_sources(w, x):
    """tools/initdb.py --sync-sources on the scratch catalog itself: the registry's rows and every collection's tier from
    data/data-sources.csv, its printed line."""
    w.cx.commit()
    return {"printed": run(tool("initdb.py"), "--db", w.db, "--sync-sources").strip()}

def a_backfill(w, x):
    """tools/backfill_aliases.py on the scenario's tree, run as the harness session (BY): its printed lines."""
    w.cx.commit()
    return {"printed": run(tool("backfill_aliases.py"), "--db", w.db, "--tree", w.slug, "--by", BY)}

def a_proof(w, x):
    """tools/proof.py's written conclusion for a person (proof.build, one fact when `fact` names it): its whole, each fact
    also under `fact.<name>`, and the text it prints."""
    from catalog import Catalog
    from proof import build, render
    r = build(Catalog(w.cx, w.tid), w.person(x["person"]), only=x.get("fact"))
    return {**r, "fact": {f["fact"]: f for f in r["facts"]}, "text": render(r, full=bool(x.get("fact")))}

def a_dismiss(w, x):
    """A question closed by the owner (tools/log_search.py --dismiss): the person's one open question of the `kind` (conflict
    when none is given) whose detail carries `detail_has`, closed with the owner's `note`; a refusal comes back as {"error": ...}."""
    from log_search import dismiss
    rows = open_questions(w, {"kind": "conflict", **x})
    try: dismiss(w.cx, w.tid, BY, rows[0][0], x.get("note"))
    except SystemExit as e: return {"error": str(e), "question": rows[0][0]}
    return {"question": rows[0][0]}

def open_questions(w, x):
    """The person's open questions of a `kind` (any when none is given) whose detail carries `detail_has`: exactly one."""
    q = "SELECT id, detail_json FROM research_question WHERE subject_person_id=? AND status='open'"; args = [w.person(x["person"])]
    if x.get("kind"): q += " AND kind=?"; args.append(x["kind"])
    rows = [r for r in w.cx.execute(q, args) if x.get("detail_has", "") in (r[1] or "")]
    if len(rows) != 1: raise KeyError(f"{len(rows)} open questions match {short(x)}, expected exactly one")
    return rows

def a_post(w, x):
    """A request to the person screen's server, handed to the handler's own do_POST with no socket (app/person/server.py H), or
    to its do_GET when `method` is GET: `path` is the route's parts joined, a part a string or {"question": ref} / {"step": ref}
    for the id of that row; `body` a POST's JSON; `headers` the ones that differ from what the page itself sends (Host the
    server's own address and, on a POST, Origin that address and Content-Type application/json), a header given as null left
    out. Returns the response's `code`, its JSON `body` and the `ids` the path's row parts named."""
    import email.message, io, types
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server
    server.CFG["db"], server.CFG["by"] = w.db, BY
    ids = []
    def part(p):
        if isinstance(p, dict) and "question" in p: ids.append(open_questions(w, p["question"])[0][0]); return ids[-1]
        if isinstance(p, dict) and "step" in p: ids.append(w.step(p["step"])["id"]); return ids[-1]
        return p
    body = json.dumps(x.get("body") or {}).encode()
    own = "127.0.0.1:8765"
    method = x.get("method", "POST")
    sent = {"Host": own} if method == "GET" else {"Host": own, "Origin": f"http://{own}", "Content-Type": "application/json", "Content-Length": str(len(body))}
    headers = {**sent, **(x.get("headers") or {})}
    h = server.H.__new__(server.H)
    h.server = types.SimpleNamespace(server_address=("127.0.0.1", 8765))
    h.path = "".join(part(p) for p in x["path"]) + f"?tree={w.slug}"
    h.command, h.request_version, h.requestline = method, "HTTP/1.0", f"{method} {h.path} HTTP/1.0"
    h.headers = email.message.Message()
    for k, v in headers.items():
        if v is not None: h.headers[k] = v
    h.rfile, h.wfile = io.BytesIO(body), io.BytesIO()
    getattr(h, "do_" + method)()
    head, _, payload = h.wfile.getvalue().partition(b"\r\n\r\n")
    return {"code": int(head.split(b" ")[1]), "body": json.loads(payload), "ids": ids}

def a_attach(w, x):
    """A fixture dropped into the inbox as a save would leave it and attached: the record's sha, the attach's report and its
    line as the tool prints it."""
    from attach import attach_inbox, line
    name = x.get("as_file") or x["fixture"]
    with open(os.path.join(w.treelib.inbox_dir(), name), "wb") as fh: fh.write(w.fixture_bytes(x))
    kw = {"about": w.person(x["about"])} if x.get("about") else {}
    res = attach_inbox(w.cx, w.tid, w.slug, BY, [name], **kw)
    r = res[0] if res else {}
    return {"sha": r.get("sha256"), "file": name, "filed": r.get("filed"), "line": line(r) if r else None, "steps": r.get("steps"), "left": r.get("left"), "repeat": r.get("repeat"), "proposals": r.get("proposals"), "accepted_by_rule": r.get("accepted_by_rule"),
            "outcome": r.get("outcome"), "identity": r.get("identity"), "extraction": r.get("extraction"), "unparsed": r.get("unparsed"), "results": res,
            "taken": [(n, why) for _, n, why in (r.get("accepted_by_rule") or [])], "step_people": [n for _, n, _, _ in (r.get("steps") or [])]}

def a_attach_inbox(w, x):
    """tools/attach_inbox.py over every file in the inbox, one file per transaction (attach.attach_each, as a turn's tail takes
    what collect left): each file's result and its line as the tool prints it."""
    from attach import attach_each, inbox_files, line
    res = attach_each(w.cx, w.tid, w.slug, BY, inbox_files())
    return {"results": res, "lines": [line(r) for r in res]}

def a_archive(w, x):
    """A page archived as the runner or the owner would archive it, under a source and collection, and read; matched for
    the people named when asked."""
    from treelib import archive_object
    src = w.source(x["source"]) or (None, None, None)
    cid = w.collection(x["source"], x["collection"]) if x.get("collection") else None
    notes = None
    if x.get("manifest"):
        with open(os.path.join(FIXTURES, x["manifest"]), encoding="utf-8") as fh: man = json.load(fh)
        notes = json.dumps({**json.loads(man.get("notes") or "{}"), **(x.get("notes") or {})})
        loc = man["locator"]; mime = man["mime"]; coll = man.get("collection")
    else: loc = x["locator"]; mime = x.get("mime", "text/html"); coll = x.get("collection")
    cost = next((c for c in ("free", "paid", "member") if (src[2] or "").strip().lower().startswith(c)), "unknown")
    sha, new = archive_object(w.cx, w.fixture_bytes(x), mime=mime, source_id=x["source"], collection_id=cid, collection_name=coll, locator_kind=loc["kind"], locator_value=loc["value"],
                              retrieved_by=BY, terms=src[1], cost=cost, trust_tier=src[0], original_filename=x.get("fixture") or x.get("file"), notes=notes)
    out = {"sha": sha, "new": new}
    if x.get("extract"):
        from extract import extract
        eid, n = extract(w.cx, sha, BY); out.update({"extraction": eid, "n": n})
        if "match" in x:
            from conclude import match_record
            from match import match
            about = w.people(x["match"]) if x["match"] else None
            if x.get("rule"): written, taken = match_record(w.cx, eid, BY, about=about); out["taken"] = [(n, why) for _, n, why in taken]
            else: written = match(w.cx, eid, BY, about=about)
            out["written"] = [{"proposal": p, "kind": k, "name": n, "person": pid} for p, k, n, pid in written]
    return out

def a_reread(w, x):
    from extract import extract
    eid, n = extract(w.cx, w.sha(x["record"]), BY); out = {"extraction": eid, "n": n, "sha": w.sha(x["record"])}
    if "match" in x:
        about = w.people(x["match"]) if x["match"] else None
        if x.get("rule"):
            from conclude import match_record
            written, taken = match_record(w.cx, eid, BY, about=about); out["taken"] = [(n, why) for _, n, why in taken]
        else:
            from match import match
            written = match(w.cx, eid, BY, about=about)
        out["written"] = [{"proposal": p, "kind": k, "name": n, "person": pid} for p, k, n, pid in written]
    return out

def a_match(w, x):
    from match import match
    eid = w.value(x["extraction"]) if "extraction" in x else w.cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND superseded_by IS NULL ORDER BY ran_at DESC", (w.sha(x["record"]),)).fetchone()[0]
    written = match(w.cx, eid, BY, about=w.people(x["about"]) if x.get("about") else None)
    return {"written": [{"proposal": p, "kind": k, "name": n, "person": pid} for p, k, n, pid in written]}

def a_decide(w, x):
    """The decision on a card (conclude.decide); with `screen`, through the person screen's own route (server.decide_proposal), whose
    answer in words comes back as `summary`."""
    from conclude import decide
    card = w.card(x["card"])
    if card is None: raise KeyError(f"no card {short(x['card'])}")
    if x.get("screen"):
        sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server; server.CFG["by"] = BY
        r = server.decide_proposal(w.cx, w.tid, card["id"], x.get("status", "accepted"), x.get("note", "harness"), x.get("choice"))
    else: r = decide(w.cx, w.tid, card["id"], x.get("status", "accepted"), x.get("by", BY), note=x.get("note", "harness"), choice=x.get("choice"))
    return {**r, "card": card["id"], "person_id": json.loads(card["payload_json"]).get("person_id")}

def a_withdraw(w, x):
    """The rule's decision on a `card` taken back, or with `record` every decision the rule made on that record, recorded as
    reconsider records it, the rule acting for the harness, unless `by` names who."""
    from conclude import RULE_ACTOR, withdraw
    if "record" in x:
        ids = [r[0] for r in w.cx.execute("""SELECT id FROM proposal WHERE tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%' AND kind IN ('persona_match','new_person')
                                             AND json_extract(payload_json,'$.artifact_sha256')=? ORDER BY decided_at, id""", (w.tid, w.sha(x["record"])))]
    else: ids = [w.card(x["card"])["id"]]
    for i in ids:
        kind = w.cx.execute("SELECT kind FROM proposal WHERE id=?", (i,)).fetchone()[0]
        withdraw(w.cx, w.tid, i, x.get("by", f"{RULE_ACTOR[kind]} for {BY}"), x.get("why", "harness: taken back"), w.treelib.now())
    return {"card": ids[0] if len(ids) == 1 else None, "cards": ids}

def a_copies(w, x):
    """The owner's word on two archived copies through tools/conclude.py's copies_on_word: `a` and `b` bound records (a
    listing's row as {record, number}), `same` true for one record and false for two, `note`; the rows it carried or gave
    back."""
    from conclude import copies_on_word, copy_named
    node = lambda v: copy_named(w.cx, f"{w.sha(v['record'])}@{v['number']}") if isinstance(v, dict) else (w.sha(v), "")
    rows = copies_on_word(w.cx, w.tid, node(x["a"]), node(x["b"]), x.get("same", True), BY, x["note"]); w.cx.commit()
    return {"rows": rows}

def a_reconsider(w, x):
    """reconsider on the tree: its rows, and how many audit rows it wrote (none for a run that changes nothing)."""
    from conclude import reconsider
    before = w.cx.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    rows = reconsider(w.cx, w.tid, BY, dry_run=bool(x.get("dry")))
    return {"rows": rows, "wrote": w.cx.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] - before}

def a_fact(w, x):
    from facts import decide_fact
    pid = w.person(x["person"]); out = {}
    for f in (x.get("fields") or [x["field"]]): out[f] = decide_fact(w.cx, w.tid, pid, f, x.get("status", "accepted"), x.get("note"), BY)
    return out

def a_assertion(w, x):
    """One statement of one record decided on its own, through tools/conclude.py assertion: the assertion found by the
    record, the person and the event type (or the subject kind); a membership's first statement, the record's own when a
    record is given."""
    pid = w.person(x["person"]); sha = w.sha(x["record"]) if x.get("record") else None
    if x.get("membership"):                          # a family link: the family found through one of its partners
        m = x["membership"]; fid = w.cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (w.person(m["family_of"]),)).fetchone()[0]
        row = w.cx.execute("SELECT id FROM assertion WHERE tree_id=? AND subject_kind='family_member' AND subject_id=?" + (" AND artifact_sha256=?" if sha else "") + " ORDER BY asserted_at",
                           (w.tid, w.treelib.dumps([fid, pid, m["role"]]), *([sha] if sha else []))).fetchone()
    elif x.get("event_type"):
        row = w.cx.execute("""SELECT a.id FROM assertion a JOIN event e ON e.id=a.subject_id JOIN event_participant ep ON ep.event_id=e.id
                              WHERE a.tree_id=? AND a.subject_kind='event' AND a.artifact_sha256=? AND e.event_type=? AND ep.person_id=? AND a.status=? ORDER BY a.asserted_at""", (w.tid, sha, x["event_type"], pid, x.get("was", "accepted"))).fetchone()
    else: row = w.cx.execute("SELECT id FROM assertion WHERE tree_id=? AND subject_kind=? AND subject_id=? AND artifact_sha256=? ORDER BY asserted_at", (w.tid, x.get("kind", "person"), pid, sha)).fetchone()
    if not row: raise KeyError("no such assertion")
    w.cx.commit()
    out = run(tool("conclude.py"), "assertion", row[0], x.get("verdict", "reject"), "--note", x.get("note", "harness"), "--db", w.db, "--tree", w.slug, "--by", BY)
    return {"assertion": row[0], "printed": out.strip()}

def a_place(w, x):
    """A record's undated fact, accepted onto a person with several events of its type, placed on the one the owner means
    (tools/conclude.py place): the persona fact found by the record, the person and the fact type, with `alternate` the one
    whose region marks it a value the page keeps beneath the one it shows (or, false, one that is not); the event a literal or
    bound id, or {"person": ref, "type": event_type, "index": n} the person's nth event of that type in the person
    screen's own order (Catalog.events: by date)."""
    from conclude import place
    sha = w.sha(x["record"]); pid = w.person(x["person"])
    alt = "" if "alternate" not in x else " AND (json_extract(coalesce(pf.region_json,'{}'),'$.alternate') IS NOT NULL) = " + ("1" if x["alternate"] else "0")
    pf = w.cx.execute("""SELECT pf.id FROM persona_fact pf JOIN persona pe ON pe.id=pf.persona_id JOIN person_persona pp ON pp.persona_id=pe.id
                         WHERE pe.artifact_sha256=? AND pp.person_id=? AND pp.status='accepted' AND pf.fact_type=?""" + alt, (sha, pid, x["fact_type"])).fetchone()
    if not pf: raise KeyError("no such persona fact")
    ref = x["event"]
    if isinstance(ref, dict):
        rows = w.cx.execute("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type=? ORDER BY e.date_start",
                            (w.person(ref["person"]), ref["type"])).fetchall()
        eid = rows[ref.get("index", 0)][0]
    else: eid = w.value(ref)
    return place(w.cx, w.tid, pf[0], eid, x.get("by", BY), x.get("note", "harness"))

def a_link_on_word(w, x):
    from conclude import link_on_word
    res = link_on_word(w.cx, w.tid, w.person(x["person"]), w.people(x["others"]), x.get("kind", "child"), w.sha(x["record"]), BY, x.get("note", "harness: the owner's word"))
    return {**res, "person": w.person(x["person"])}

def a_living(w, x):
    from conclude import living
    return living(w.cx, w.tid, w.person(x["person"]), x["word"], BY, x.get("note", "harness"))

def a_living_route(w, x):
    """The person screen's own living control (app/person/server.py living_route), through the same function
    app/person/server.py's POST route calls: word and an optional note."""
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server; server.CFG["by"] = BY
    return server.living_route(w.cx, w.tid, w.person(x["person"]), {"word": x["word"], "note": x.get("note")})

def a_transcribe(w, x):
    """A reading typed into the person screen's form, as the model or a person reads a record: the fields as given,
    relations to personas earlier readings bound."""
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server; server.CFG["by"] = BY
    form = dict(w.value(x["form"]))
    if x.get("relations"): form["relations"] = [{"persona_id": w.value(r["persona"]), "kind": r["kind"], "text": r["text"]} for r in x["relations"]]
    about = w.people(x["about"]) if x.get("about") else None
    r = server.transcribe(w.cx, w.sha(x["record"]), form, by=x.get("by", "human:harness"), about=about)
    card = w.cx.execute("SELECT * FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.persona_id')=?", (w.tid, r.get("persona"))).fetchone() if r.get("ok") else None
    return {**r, "card": card["id"] if card else None, "card_status": card["status"] if card else None, "card_kind": card["kind"] if card else None, "sha": w.sha(x["record"])}

def a_view(w, x):
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server
    return server.artifact_view(w.cx, w.tid, w.sha(x["record"]), w.person(x["person"]))

def a_person_view(w, x):
    """The person screen's own view (app/person/server.py person_view): the foundation with its living line, the
    checklist and the plan, as the screen renders them."""
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server
    return server.person_view(w.cx, w.tid, w.person(x["person"]))

def a_save(w, x):
    """A page or an image saved in the browser, a `fixture`: into the inbox, or into a download folder for collect. The
    entry it is saved for is the person's at the `holder` whose link has `url_has`, when the person has several there.
    Under the name the fetch list prints for it, unless `name` gives the file's own name instead (the sanitized shape a
    browser actually produced, to prove collect takes a page by its saved-from identity whatever it is named). `key` writes the
    key into the page the way tools/save_page.js does when the fetch list's call gave it one: a second comment under the page's own
    saved-from line, naming the entry's own steps (true) or the steps given (plan step references, or an id that names no step)."""
    from fetches import waiting
    pid = w.person(x["person"]) if x.get("person") else None
    entries = [e for e in waiting(w.cx, w.tid) if (not x.get("holder") or e["holder_id"] == x["holder"]) and (not x.get("url_has") or x["url_has"] in (e.get("url") or ""))
               and (pid is None or any(s in e["step_ids"] for s in [s[0] for s in w.cx.execute("SELECT id FROM search_plan WHERE person_id=?", (pid,))]))]
    e = entries[0] if entries else None
    if "name" in x: name = x["name"]
    else:
        if not e: raise KeyError("no fetch entry waiting for that person at that holder")
        name = e["save_as"].replace("<year>", str(x.get("year", "")))
        for k, v in (x.get("fill") or {}).items(): name = name.replace(k, v)
    folder = os.path.join(w.root, x["folder"]) if x.get("folder") else w.treelib.inbox_dir()
    os.makedirs(folder, exist_ok=True)                           # a download folder of the scenario's own; the inbox the tools make
    data = w.fixture_bytes(x); key = None
    if x.get("key"):
        key = e["serves"] if x["key"] is True else [(w.step(r) or {"id": r})["id"] if isinstance(r, str) else w.step(r)["id"] for r in x["key"]]   # an id that is no step of the plan is written as it is
        top, nl, rest = data.partition(b"\n")
        if not top.startswith(b"<!-- saved from "): raise KeyError("a key goes under the page's saved-from line, and this page has none")
        data = top + nl + f"<!-- for steps {','.join(key)} -->\n".encode() + rest
    with open(os.path.join(folder, name), "wb") as fh: fh.write(data)
    return {"entry": e, "file": name, "folder": folder, "url": e.get("url") if e else None, "save_as": e["save_as"] if e else None, "how": e.get("how") if e else None, "steps": e.get("step_ids") if e else None, "key": key}

def a_collect(w, x):
    from attach import line
    from fetches import collect
    names, res = collect(w.cx, w.tid, w.slug, BY, folder=w.value(x["folder"]))
    return {"names": names, "results": res, "files": {r["file"]: r for r in res}, "lines": [line(r) for r in res],   # each result as the tool prints it
            "sha": res[0].get("sha256") if len(res) == 1 else None}                                        # the record, when one page came in

def a_block_filing(w, x):
    """The harness's stand-in for a file whose attach fails after it has written its rows: the move that files the original of
    the file named under the tree (tools/attach.py's last write, treelib.move_free into trees/<slug>/imports/records) refused,
    as a full disk or a refused write refuses it, until a step with `clear` lifts it, and lifted when the scenario ends. A
    filing refused, not a holder's answer: no page or record is invented."""
    import attach
    blocked = w.env.setdefault("filing_blocked", set())
    if not w.env.get("filing_stand_in"):
        real = attach.move_free
        def refusing(src, folder, name=None):
            if os.path.basename(src) in blocked and os.path.basename(folder) == "records": raise OSError(f"the harness's stand-in for a filing refused: {os.path.basename(src)} is not filed")
            return real(src, folder, name)
        attach.move_free = refusing
        w.undo.append(lambda: setattr(attach, "move_free", real))
        w.env["filing_stand_in"] = True
    (blocked.discard if x.get("clear") else blocked.add)(x["file"])
    return {"file": x["file"], "blocked": not x.get("clear")}

def a_log(w, x):
    """A run written by hand, as a connector or a saved page would leave it: query true takes the step's own current
    fields; a query dict is a literal override, for a run on fields the step no longer carries (the plan has since
    rewritten them), to stand in for what a real change of fields would leave behind."""
    from log_search import log
    st = w.step(x["step"])
    q = x.get("query")
    query = q if isinstance(q, dict) else json.loads(st["query_json"] or "{}") if q else None
    lid = log(w.cx, w.tid, BY, step_id=st["id"], source_id=x.get("source"), outcome=x["outcome"], artifacts=[w.sha(a) for a in x.get("artifacts", [])] or None, note=x.get("note", "harness"), done=x.get("done", False),
              query=query)
    return {"log": lid, "step": st["id"]}

def a_reopen(w, x):
    from log_search import reopen
    out = []
    for st in (w.steps(x["step"]) if not x.get("all") else [w.cx.execute("SELECT * FROM search_plan WHERE id=?", (s,)).fetchone() for s in w.value(x["all"])]):
        reopen(w.cx, w.tid, BY, st["id"], x.get("note", "harness: wrongly matched")); out.append(st["id"])
    return {"steps": out}

def a_step(w, x):
    """A plan step written by the harness itself, as a step nothing generates or a plan the loop's tools are run on; with
    `revisions`, the person's include and revise as an earlier screen stored them on it."""
    x = w.value(x); sid = w.treelib.ulid(); loc = x.get("locator") or {}
    w.cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,revisions_json,locator_source_id,locator_kind,locator_value,sources_json,mode,expected,status,rationale,on_json,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (sid, w.person(x["person"]), x["row_key"], x.get("seq", 1), x["step_key"], x.get("kind", "search"), x.get("query_type", "name"), json.dumps(x.get("query", {})),
                  json.dumps(x["revisions"]) if x.get("revisions") else None,
                  loc.get("source"), loc.get("kind"), loc.get("value"), json.dumps(x.get("sources", [])), x.get("mode", "auto"), x.get("expected"), x.get("status", "planned"), x.get("rationale"), x.get("on"), w.treelib.now()))
    return {"step": sid}

def a_event(w, x):
    """A second event of a type a person already carries, written by the harness itself for a path only a planted event
    exercises (docs/RESEARCH-WORKFLOW.md's harness-is-data rule keeps the file itself free of invented people and records;
    a bare event with no record behind it is not one of those)."""
    eid = w.treelib.ulid()
    w.cx.execute("""INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,description,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (eid, w.tid, x["type"], x.get("date"), x.get("date_start"), x.get("date_end"), x.get("qualifier"), x.get("calendar", "gregorian"), x.get("description"), w.treelib.now(), w.treelib.now()))
    w.cx.execute("INSERT INTO event_participant (id,event_id,person_id,role) VALUES (?,?,?,'primary')", (w.treelib.ulid(), eid, w.person(x["person"])))
    return {"event": eid}

def a_file_family(w, x):
    """A family of the owner's own file that the harness cut leaves out (the cut keeps the families most scenarios need,
    and one family of a person can change what another scenario reads), written as the import writes it: the family row,
    its file id, and each membership with the file's own uncited claim, undecided. partners and children are people; xref
    is the family's own id in the export."""
    from ingest_gedcom import EXTRACTOR_TAG
    fid = w.treelib.ulid(); ts = w.treelib.now()
    w.cx.execute("INSERT INTO family (id,tree_id,rel_type,created_at,updated_at) VALUES (?,?,?,?,?)", (fid, w.tid, "unknown", ts, ts))
    w.cx.execute("INSERT INTO external_id (id,tree_id,entity_kind,entity_id,system,value,created_at) VALUES (?,?,?,?,?,?,?)",
                 (w.treelib.ulid(), w.tid, "family", fid, "ancestry_gedcom_xref", x["xref"], ts))
    for i, (pid, role) in enumerate([(w.person(p), "partner") for p in x.get("partners", [])] + [(w.person(c), "child") for c in x.get("children", [])]):
        w.cx.execute("INSERT INTO family_member (family_id,person_id,role,child_rel,seq) VALUES (?,?,?,?,?)", (fid, pid, role, "birth" if role == "child" else None, i + 1 if role == "child" else None))
        w.cx.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                        VALUES (?,?,'family_member',?,?,?,'undecided',?,?,?)""", (w.treelib.ulid(), w.tid, w.treelib.dumps([fid, pid, role]), w.env["import"]["sha"], "Ancestry member tree (no citation)", EXTRACTOR_TAG, ts, w.treelib.dumps({"uncited": True})))
    return {"family": fid}

def a_divorce(w, x):
    """The owner's word ending a marriage (tools/conclude.py divorce): a Divorce event between `a` and `b` dated `date`, each
    piece of `evidence` a record's fact named by `record`, the persona's name as written (`persona`) and the `fact_type`,
    with its `citation` words."""
    from conclude import divorce
    ev = []
    for e in x["evidence"]:
        pf = w.cx.execute("""SELECT pf.id FROM persona_fact pf JOIN persona pe ON pe.id=pf.persona_id WHERE pe.artifact_sha256=? AND pe.name_text=? AND pf.fact_type=?""",
                          (w.sha(e["record"]), e["persona"], e["fact_type"])).fetchone()
        if not pf: raise KeyError(f"no {e['fact_type']} fact of {e['persona']} on that record")
        ev.append((w.sha(e["record"]), pf[0], e.get("citation", "harness")))
    return divorce(w.cx, w.tid, w.person(x["a"]), w.person(x["b"]), x["date"], ev, x.get("by", BY), x.get("note", "harness"))

def conflict_question(w, x, closed=False):
    """The person's one conflict question whose detail has `detail_has`: an open one, or with closed one the rule resolved
    (its own question, not one closed beside it)."""
    pid = w.person(x["person"])
    q = "SELECT id, detail_json FROM research_question WHERE subject_person_id=? AND kind='conflict' AND " + \
        ("status='closed' AND closed_reason='resolved' AND json_extract(detail_json,'$.resolution.question')=id AND json_extract(detail_json,'$.resolution.by') LIKE 'rule:%'" if closed else "status='open'")
    rows = [r for r in w.cx.execute(q, (pid,)) if x["detail_has"] in (r["detail_json"] or "")]
    if len(rows) != 1: raise KeyError(f"{len(rows)} {'conflict questions the rule resolved' if closed else 'open conflict questions'} match, expected exactly one")
    return rows[0]

def a_resolve_conflict(w, x):
    """A conflict question closed through tools/conclude.py resolve: the person's one open conflict whose detail has
    `detail_has` (with `over_rule`, the one the rule resolved instead, for the owner's own resolution over it), the
    statement kept a literal or bound assertion id, or {record, event_type} for that record's statement on the person's
    event of the type, with `note`; a refusal comes back as {"error": ...}."""
    from conclude import resolve
    pid = w.person(x["person"])
    rows = [conflict_question(w, x, closed=bool(x.get("over_rule")))]
    keep = x["keep"]
    if isinstance(keep, dict):
        row = w.cx.execute("""SELECT a.id FROM assertion a JOIN event e ON e.id=a.subject_id JOIN event_participant ep ON ep.event_id=e.id
                              WHERE a.tree_id=? AND a.subject_kind='event' AND a.artifact_sha256=? AND e.event_type=? AND ep.person_id=? ORDER BY a.asserted_at""",
                           (w.tid, w.sha(keep["record"]), keep["event_type"], pid)).fetchone()
        if not row: raise KeyError("no such statement")
        keep = row[0]
    return {**resolve(w.cx, w.tid, rows[0]["id"], keep, x.get("by", BY), x.get("note", "harness")), "question_id": rows[0]["id"]}

def a_reopen_conflict(w, x):
    """A conflict the rule resolved, reopened by the owner through tools/conclude.py reopen: the person's one question the
    rule resolved whose detail has `detail_has`, with `note`; a refusal comes back as {"error": ...}."""
    from conclude import reopen
    row = conflict_question(w, x, closed=True)
    return {**reopen(w.cx, w.tid, row["id"], x.get("by", BY), x.get("note", "harness")), "question_id": row["id"]}

def plant_geocoder(fixtures):
    """The geocoder's real answers planted in the resolver's cache, each fixture under tests/fixtures/geocoder/ a cache record
    exactly as the live resolver kept it ({query, fetched_at, results}, with the limit it was asked at when that is not the
    first page's), copied to the file name the resolver looks it up by (nominatim_cache_path); the records read, in order."""
    from resolve_places import PAGE, cache_dir, nominatim_cache_path
    os.makedirs(cache_dir(), exist_ok=True); records = []
    for name in fixtures:
        src = os.path.join(FIXTURES, "geocoder", name)
        with open(src, encoding="utf-8") as fh: records.append(json.load(fh))
        shutil.copyfile(src, nominatim_cache_path(records[-1]["query"], records[-1].get("limit", PAGE)))
    return records

def plant_wikidata(items):
    """Wikidata's real items planted in the resolver's own item cache, {qid: fixture}: each fixture under tests/fixtures/ an
    item as the live resolver kept it (Special:EntityData's answer), copied to the file name the resolver looks it up by."""
    from resolve_places import wikidata_cache_dir
    os.makedirs(wikidata_cache_dir(), exist_ok=True)
    for qid, fixture in (items or {}).items(): shutil.copyfile(os.path.join(FIXTURES, fixture), os.path.join(wikidata_cache_dir(), qid + ".json"))

def a_place_card(w, x):
    """A place_resolution card for a string of the tree, as the resolver would write it, its candidates the results of the
    geocoder's real answers (`geocoder`, plant_geocoder) planted in the cache so no request goes out."""
    from resolve_places import RESOLVER, candidate_summary
    raw = x["raw"]; ps = w.cx.execute("SELECT id FROM place_string WHERE raw=?", (raw,)).fetchone()
    if not ps: raise KeyError(f"no place string {raw!r} in the tree")
    records = plant_geocoder(x.get("geocoder", []))
    queries = [r["query"] for r in records]
    candidates = list({(c["osm_type"], c["osm_id"]): c for r in records for c in r["results"]}.values())
    rx = w.cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", RESOLVER).fetchone()
    rx_id = rx[0] if rx else w.treelib.ulid()
    if not rx: w.cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (rx_id, *RESOLVER, w.treelib.now()))
    pid_ = w.treelib.ulid()
    w.cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                 (pid_, w.tid, "place_resolution", w.treelib.dumps({"raw": raw, "place_string_id": ps[0], "parsed": {}, "queries": queries, "candidates": [candidate_summary(c, 1.0, {}) for c in candidates], "reason": "harness: the owner chooses"}), "harness: the owner chooses", rx_id, w.treelib.now()))
    w.cx.execute("UPDATE place_string SET resolver=?, resolved_at=? WHERE id=?", (f"ai:{RESOLVER[1]}@{RESOLVER[2]}", w.treelib.now(), ps[0]))
    return {"proposal": pid_, "place_string": ps[0], "raw": raw, "candidates": candidates}

def a_older_matcher(w, x):
    """The cards on a record marked as an older matcher's, so reconsider must propose them again."""
    from match import MATCHER
    older = w.treelib.ulid(); w.cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (older, MATCHER[0], MATCHER[1], x.get("version", "0.0.1"), w.treelib.now()))
    ids = [r["id"] for r in w.cards_on(x["record"], status="undecided")]
    w.cx.execute(f"UPDATE proposal SET generated_by=? WHERE id IN ({','.join('?' * len(ids))})", (older, *ids))
    return {"cards": ids, "version": MATCHER[2]}

def a_legacy_card(w, x):
    """A card an older matcher wrote for a row of a results page, planted as it left it, undecided, for reconsider to meet: the
    persona at sequence `row` on the record's current reading, put to `person`, written by the matcher at `version`. The
    matcher proposes no such card now (tools/match.py), so only an older one can stand."""
    from match import MATCHER
    sha = w.sha(x["record"]); pid = w.person(x["person"]); t = w.treelib
    pe = w.cx.execute("""SELECT pe.id, pe.extraction_id, pe.name_text, pe.role_in_record FROM persona pe JOIN extraction e ON e.id=pe.extraction_id
                         WHERE pe.artifact_sha256=? AND e.superseded_by IS NULL AND pe.sequence=?""", (sha, x["row"])).fetchone()
    older = w.cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", (MATCHER[0], MATCHER[1], x["version"])).fetchone()
    older = older[0] if older else t.ulid()
    w.cx.execute("INSERT OR IGNORE INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (older, MATCHER[0], MATCHER[1], x["version"], t.now()))
    prop = t.ulid()
    w.cx.execute("""INSERT INTO proposal (id,tree_id,kind,question_id,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,'persona_match',NULL,?,?,?,?,'undecided')""",
                 (prop, w.tid, t.dumps({"persona_id": pe["id"], "person_id": pid, "subject_person_id": pid, "extraction_id": pe["extraction_id"], "artifact_sha256": sha, "step_id": None}),
                  f"{pe['name_text']} ({pe['role_in_record']}) may be {w.name_of(pid)}, on the name alone.", older, t.now()))
    return {"card": prop, "persona": pe["id"]}

def a_older_reading(w, x):
    """A record's reading planted as an older reader left it, a row of the owner's catalog that its reader no longer writes:
    the extractor (`kind`, `name`, `version`) and each persona with its facts as the catalog holds them (a fact's date read
    from its date_text by treelib.parse_gedcom_date, as the reader wrote it, its `place` the words as written) and its
    `relations` (each `kind`, `value`, `region` and `to`, the sequence of the persona it relates to on the same reading). The
    reading stands as the record's current one."""
    from extract import Writer
    t = w.treelib; sha = w.sha(x["record"]); ex = x["extractor"]
    xid = w.cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=? AND prompt_sha256 IS NULL", (ex["kind"], ex["name"], ex["version"])).fetchone()
    xid = xid[0] if xid else t.ulid()
    w.cx.execute("INSERT OR IGNORE INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (xid, ex["kind"], ex["name"], ex["version"], t.now()))
    eid = t.ulid(); w.cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status) VALUES (?,?,?,?,'complete')", (eid, sha, xid, t.now()))
    places, at = Writer(w.cx, sha, eid), {}
    for pe in x["personas"]:
        pid = t.ulid(); at[pe["sequence"]] = pid
        w.cx.execute("INSERT INTO persona (id,extraction_id,artifact_sha256,name_text,sex,role_in_record,sequence,region_json) VALUES (?,?,?,?,?,?,?,?)",
                     (pid, eid, sha, pe["name"], pe.get("sex"), pe["role"], pe["sequence"], t.dumps(pe["region"]) if pe.get("region") else None))
        for f in pe["facts"]:
            d = t.parse_gedcom_date(f.get("date_text"))
            w.cx.execute("""INSERT INTO persona_fact (id,persona_id,fact_type,value_text,date_text,date_start,date_end,date_qualifier,calendar,place_string_id,region_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                         (t.ulid(), pid, f["type"], f.get("value"), f.get("date_text"), d["date_start"], d["date_end"], d["date_qualifier"], d["calendar"], places.place_string(f.get("place")),
                          t.dumps(f["region"]) if f.get("region") else None))
    for pe in x["personas"]:
        for r in pe.get("relations", []):
            w.cx.execute("INSERT INTO persona_relation (id,persona_id,related_persona_id,kind,value_text,region_json) VALUES (?,?,?,?,?,?)",
                         (t.ulid(), at[pe["sequence"]], at[r["to"]], r["kind"], r.get("value"), t.dumps(r["region"]) if r.get("region") else None))
    w.cx.commit()
    return {"extraction": eid}

def a_persona_link(w, x):
    """A person's decision on a persona of a record that no card carries today (a memorial's listed relative, which an older
    matcher put up as a card): the link set to `status` for the persona of that `role` (and `persona` name, and `sequence`,
    its row on the page) on the record's current reading, as conclude.decide writes it. With `card`, the link that card's
    decision wrote on every persona of the decided persona's name and role, another row among them, before a decision reached
    only its own entry of the page: the card's proposal, status and decider, the shape tools/initdb.py's 0.7.5 corrects."""
    q = """SELECT pe.id FROM persona pe JOIN extraction e ON e.id=pe.extraction_id WHERE pe.artifact_sha256=? AND e.superseded_by IS NULL AND pe.role_in_record=?"""
    args = [w.sha(x["record"]), x["role"]]
    if "persona" in x: q += " AND pe.name_text=?"; args.append(x["persona"])
    if "sequence" in x: q += " AND pe.sequence=?"; args.append(x["sequence"])
    rows = w.cx.execute(q, args).fetchall()
    if len(rows) != 1: raise KeyError(f"{len(rows)} personas for {short(x)}")
    card = w.card(x["card"]) if x.get("card") else None
    if x.get("card") and card is None: raise KeyError(f"no card {short(x['card'])}")
    link = (card["status"], card["id"], card["decided_by"], card["decided_at"]) if card else (x["status"], None, x.get("by", BY), w.treelib.now())
    w.cx.execute("INSERT OR REPLACE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (w.person(x["person"]), rows[0][0], *link))
    return {"persona": rows[0][0]}

def a_merge(w, x):
    """The owner's merge of a `duplicate` into the person it duplicates (`kept`), through conclude.merge. With `older`, the
    merge as an older tools/conclude.py left it, which re-pointed no proposal, moved no name alias and left on the duplicate's
    row a membership or a persona link the kept person already held and, open, a question whose key the kept person held:
    each proposal the merge re-pointed put back to name the duplicate, each membership it folded put back on the
    duplicate's row with the statements it moved, each persona link it folded put back there as it was (the kept person's
    own row as it was too), each alias it moved or folded put back on the duplicate, each question it closed open again, the
    shape the merge run again on the pair completes."""
    from conclude import merge
    dup, kept = w.person(x["duplicate"]), w.person(x["kept"])
    res = merge(w.cx, w.tid, dup, kept, BY, x.get("note", "harness: same identity"))
    if x.get("older"):
        for r in res["proposals_repointed"]:
            for k in r["rewritten"]: w.cx.execute("UPDATE proposal SET payload_json=json_set(payload_json, ?, ?) WHERE id=?", (f"$.{k}", dup, r["proposal"]))
        for m in res["folded_memberships"]:
            w.cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (m["family_id"], dup, m["role"]))
            w.cx.execute(f"UPDATE assertion SET subject_id=? WHERE id IN ({','.join('?' * len(m['statements']))})", (w.treelib.dumps([m["family_id"], dup, m["role"]]), *m["statements"]))
        for f in res["folded_links"]:
            row = lambda r: (r["status"], r["proposal_id"], r["decided_by"], r["decided_at"])
            w.cx.execute("INSERT INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (dup, f["persona"], *row(f)))
            w.cx.execute("UPDATE person_persona SET status=?, proposal_id=?, decided_by=?, decided_at=? WHERE person_id=? AND persona_id=?", (*row(f["kept"]), kept, f["persona"]))
        for a in res["aliases_moved"]: w.cx.execute("UPDATE alias SET entity_id=? WHERE id=?", (dup, a["alias"]))
        for a in res["folded_aliases"]: w.cx.execute(f"INSERT INTO alias ({','.join(a)}) VALUES ({','.join('?' * len(a))})", tuple(a.values()))
        for c in res["closed_questions"]: w.cx.execute("UPDATE research_question SET status='open', closed_reason=NULL, closed_at=NULL, answered_by_proposal_id=NULL WHERE id=?", (c["question"],))
    return res

def a_cite(w, x):
    from attach import cite_on_word
    try: sid = cite_on_word(w.cx, w.tid, w.person(x["person"]), x["row"], x["holder"], x["fields"], BY, note=x.get("note"))
    except ValueError as e:
        if x.get("refused"): return {"refused": str(e)}
        raise
    return {"step": sid, "refused": None}

def a_seed(w, x):
    """A record no parser reads, archived as a_archive archives it, for the harness to read only by a typed reading."""
    return a_archive(w, x)

def households_now(w):
    """The current stored households (tools/households.py stored), each member's file named by the label of the step that
    archived it (the first step bound to it), `record`, beside its persona's name as written."""
    from households import stored
    labels = {}
    for k, v in w.env.items():
        if k != "last" and isinstance(v, dict) and isinstance(v.get("sha"), str): labels.setdefault(v["sha"], k)
    return [{**{k: h[k] for k in ("form", "page", "complete", "missing", "ground", "grouped_by")},
             "members": [{**{k: m[k] for k in ("name", "relationship", "head", "line", "entry")}, "record": labels.get(m["sha"])} for m in h["members"]]} for h in stored(w.cx)]

def a_households(w, x):
    """The households grouped again and stored where they changed (tools/households.py regroup), as the plan groups them:
    what it wrote (`kept`, `written`, `superseded`, `ungrouped`), every row the table holds (`rows`, superseded ones among them)
    and the current households as households_now reads them."""
    from households import regroup
    st = regroup(w.cx, x.get("by", BY) if isinstance(x, dict) else BY)
    return {**st, "rows": w.cx.execute("SELECT COUNT(*) FROM household").fetchone()[0], "households": households_now(w)}

def a_question(w, x):
    """A research_question row patched by hand into any shape, for a migration or a later plan run to be checked
    against it. The row is found among the person's own by kind and a substring of its detail, and must be exactly one."""
    pid = w.person(x["person"])
    rows = w.cx.execute("SELECT id, kind, detail_json FROM research_question WHERE subject_person_id=?", (pid,)).fetchall()
    if x.get("kind"): rows = [r for r in rows if r["kind"] == x["kind"]]
    if x.get("detail_has"): rows = [r for r in rows if x["detail_has"] in (r["detail_json"] or "")]
    if len(rows) != 1: raise KeyError(f"{len(rows)} research_question rows match, expected exactly one")
    qid = rows[0]["id"]; set_ = x["set"]
    w.cx.execute(f"UPDATE research_question SET {', '.join(f'{k}=?' for k in set_)} WHERE id=?", (*set_.values(), qid))
    w.cx.commit()
    return {"question": qid}

ACTIONS = {"plan": a_plan, "migrate": a_migrate, "sync_sources": a_sync_sources, "backfill": a_backfill, "proof": a_proof, "dismiss": a_dismiss, "attach": a_attach, "archive": a_archive, "reread": a_reread, "match": a_match, "decide": a_decide, "withdraw": a_withdraw, "reconsider": a_reconsider,
           "fact": a_fact, "assertion": a_assertion, "place": a_place, "link_on_word": a_link_on_word, "living": a_living, "living_route": a_living_route, "transcribe": a_transcribe, "view": a_view,
           "person_view": a_person_view, "save": a_save, "collect": a_collect, "block_filing": a_block_filing, "attach_inbox": a_attach_inbox,
           "question": a_question, "post": a_post,
           "log": a_log, "reopen": a_reopen, "step": a_step, "event": a_event, "place_card": a_place_card, "file_family": a_file_family, "divorce": a_divorce, "resolve_conflict": a_resolve_conflict, "reopen_conflict": a_reopen_conflict, "older_matcher": a_older_matcher, "persona_link": a_persona_link, "merge": a_merge, "cite": a_cite, "seed": a_seed, "copies": a_copies}

ACTIONS["legacy_card"] = a_legacy_card
ACTIONS["older_reading"] = a_older_reading
ACTIONS["households"] = a_households

def a_tombstone(w, x):
    """A file withdrawn from the evidence through tools/tombstone.py: the `record` a step bound, with its `reason`, `destroy` for a
    takedown; the tool's result, or what its refusal said under `refused`."""
    from tombstone import tombstone
    try: return tombstone(w.cx, w.sha(x["record"]), x.get("reason"), x.get("by", BY), destroy=bool(x.get("destroy")))
    except SystemExit as e: w.cx.rollback(); return {"refused": str(e)}

ACTIONS["tombstone"] = a_tombstone

# ---------------------------------------------------------------- expectations: each returns (ok, what was found)

def e_last(w, x, want):
    v = w.env["last"]; return has(v, w.value(x)), v

def e_bound(w, x, want):
    v = w.value(x["value"]); return has(v, w.value(x["is"])), v

def e_cards(w, x, want):
    rows = w.cards_on(x["record"], status=x.get("status", "undecided"), kinds=tuple(x.get("kinds", ("persona_match", "new_person"))))
    got = {"people": sorted(w.name_of(json.loads(r["payload_json"]).get("person_id")) or "(a new person)" for r in rows), "kinds": sorted({r["kind"] for r in rows}), "count": len(rows),
           "personas": sorted(w.cx.execute("SELECT name_text FROM persona WHERE id=?", (json.loads(r["payload_json"])["persona_id"],)).fetchone()[0] for r in rows)}
    ok = True
    if "people" in x: ok &= got["people"] == sorted(w.name_of(p) for p in w.people(x["people"]))
    if "kind" in x: ok &= got["kinds"] == [x["kind"]] or (not rows and x.get("count") == 0)
    if "count" in x: ok &= has(got["count"], x["count"])
    if "personas" in x: ok &= has(got["personas"], x["personas"])
    if "personas_has" in x: ok &= all(p in got["personas"] for p in x["personas_has"])
    return ok, got

def e_card(w, x, want):
    card = w.card(x)
    if card is None: return x.get("exists") is False, None
    got = {"status": card["status"], "kind": card["kind"], "decided_by": card["decided_by"], "decided_at": card["decided_at"], "note": card["decision_note"], "rationale": card["rationale"], "person_name": w.name_of(json.loads(card["payload_json"]).get("person_id"))}
    pattern = {k: v for k, v in x.items() if k in ("status", "kind", "decided_by", "decided_at", "note", "rationale", "person_name")}
    return x.get("exists", True) and has(got, w.value(pattern)), got

def e_rule(w, x, want):
    from conclude import rule_accepts
    card = w.card(x)
    if card is None: return False, "no card"
    ok, why = rule_accepts(w.cx, w.tid, card)
    got = {"taken": bool(ok), "why": why}
    pattern = {k: v for k, v in x.items() if k in ("taken", "why")}
    return has(got, w.value(pattern)), got

def e_compare(w, x, want):
    """A card's persona against its person as the matcher compares them (match.compare): what agrees, disagrees and is
    absent, the disagreements the rule reads as vetoes (conclude.split_disagree), and the card's own fields with their
    verdicts (cards.card), {field: verdict}, and as `rows`, each field in the card's order with what the record says
    ({field, record, verdict}), a field the card lists twice listed twice."""
    from cards import card as card_view
    from catalog import Catalog
    from conclude import split_disagree
    from match import candidate, compare, personas_of, said
    card = w.card(x["card"]); pay = json.loads(card["payload_json"]); cat = Catalog(w.cx, w.tid)
    persona = next(p for p in personas_of(w.cx, pay["extraction_id"]) if p["id"] == pay["persona_id"])
    cand = candidate(cat, pay["person_id"])
    fits, agree, disagree, absent, near = compare(cat, persona, cand, {})
    vetoes, claims, conflicts = split_disagree(w.cx, w.tid, cand, persona, disagree, {})
    words = lambda fs: [said(f) for f in fs]
    fields = card_view(w.cx, w.tid, card["id"])["fields"]
    got = {"agree": words(agree), "disagree": words(disagree), "absent": words(absent), "vetoes": words(vetoes), "fields": {f["field"]: f["verdict"] for f in fields},
           "rows": [{k: f[k] for k in ("field", "record", "verdict")} for f in fields]}
    return has(got, w.value({k: v for k, v in x.items() if k != "card"})), got

def e_facts(w, x, want):
    from facts import fact_status
    pid = w.person(x["person"]); got = {f: fact_status(w.cx, pid, f) for f in x if f != "person"}
    return all(got[f] == v for f, v in x.items() if f != "person"), got

def e_alias(w, x, want):
    rows = [list(a) for a in w.cx.execute("SELECT value, kind, status FROM alias WHERE entity_kind='person' AND entity_id=?", (w.person(x["person"]),))]
    return has(rows, w.value(x["is"])), rows

def e_names(w, x, want):
    """The names a person is compared by, as (first given, surname) keys written "given surname" in sorted order
    (match.name_keys): `rule`, the name rows and the accepted aliases the standing rule stands on, and `matcher`, those and
    every alias not rejected, which the matcher reads to find and propose."""
    from catalog import Catalog
    from match import name_keys
    cat, pid = Catalog(w.cx, w.tid), w.person(x["person"])
    got = {side: sorted(f"{g} {s}" for g, s in name_keys(cat, pid, accepted=side == "rule")) for side in ("rule", "matcher")}
    return has(got, w.value({k: v for k, v in x.items() if k != "person"})), got

def e_parents(w, x, want):
    """A person's parents as the tree holds them (Catalog.family: the partners of every family the person is a child of, a
    membership whose statements are all rejected left out), by display name, in name order."""
    got = sorted(n for _, n in w.catalog().family(w.person(x["person"]))["parents"])
    return has(got, w.value(x["is"])), got

def e_linked(w, x, want):
    from match import linked
    v = bool(linked(w.catalog(), w.person(x["a"]), w.person(x["b"]))); return v == x.get("is", True), v

def e_memberships(w, x, want):
    """The person's memberships with the assertions on records other than the import: (role, status, placed) each."""
    pid = w.person(x["person"]); rows = []
    for fm in w.cx.execute("SELECT family_id, person_id, role FROM family_member WHERE person_id=?", (pid,)):
        for a in w.cx.execute("SELECT status, notes FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256 NOT IN (SELECT artifact_sha256 FROM tree_import)", (w.treelib.dumps([fm["family_id"], fm["person_id"], fm["role"]]),)):
            rows.append({"role": fm["role"], "status": a["status"], "placed": json.loads(a["notes"] or "{}").get("placed")})
    if x.get("rows_total") is not None: return has(w.cx.execute("SELECT COUNT(*) FROM family_member WHERE person_id=?", (pid,)).fetchone()[0], x["rows_total"]), rows
    return has(rows, w.value(x["is"])), rows

def e_persons(w, x, want):
    if "named" in x:
        rows = w.cx.execute("SELECT p.display_name, n.given, n.surname FROM person p LEFT JOIN person_name n ON n.person_id=p.id AND n.is_primary=1 WHERE p.tree_id=? AND p.display_name=?", (w.tid, x["named"])).fetchall()
        got = [dict(r) for r in rows]
        if x.get("exists") is False: return not rows, got
        return bool(rows) and has(got[0], {k: v for k, v in x.items() if k in ("given", "surname", "display_name")}), got
    n = w.cx.execute("SELECT COUNT(*) FROM person WHERE tree_id=?", (w.tid,)).fetchone()[0]
    return has(n, w.value(x["count"])), n

def e_event(w, x, want):
    """A person's event of a type: the place strings behind it with their assertion statuses, the place shown, the
    canonical event's date and the key fact's basis."""
    pid = w.person(x["person"]); cat = w.catalog(); ev = cat.events(pid)
    rows = w.cx.execute("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type=?", (pid, x["type"])).fetchall()
    strings = {}
    for e, in rows:
        for raw, st in w.cx.execute("""SELECT ps.raw, a.status FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN place_string ps ON ps.id=pf.place_string_id WHERE a.subject_kind='event' AND a.subject_id=?""", (e,)): strings[raw] = st
    canon = cat.canonical_event(ev, x["type"])
    got = {"events": len(rows), "strings": strings, "shown": (cat.place(rows[0][0], None) or {}).get("text") if rows else None, "canonical_date": canon["date_text"] if canon else None,
           "basis": cat.key_fact_basis(pid, ev).get(x["type"].lower())}
    pattern = {k: v for k, v in x.items() if k in ("events", "strings", "shown", "canonical_date", "basis")}
    return has(got, pattern), got

def e_family_event(w, x, want):
    """The events of a type on the family two people are partners in (`a`, `b`, `type`): how many, each one's date as
    written (`dates`, in date order), and with `record` the statements that record makes on them, by status, and how many
    it makes on each (`per_event`, in the same order; every statement on each without `record`)."""
    a, b = w.person(x["a"]), w.person(x["b"])
    fid = w.cx.execute("""SELECT fm.family_id FROM family_member fm JOIN family_member o ON o.family_id=fm.family_id AND o.person_id=? AND o.role='partner'
                          WHERE fm.person_id=? AND fm.role='partner'""", (b, a)).fetchone()
    if not fid: return False, "no family joins them"
    rows = w.cx.execute("SELECT e.id, e.date_text FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.family_id=? AND e.event_type=? ORDER BY e.date_start, e.id", (fid[0], x["type"])).fetchall()
    evs = [r[0] for r in rows]
    st = {}
    if x.get("record") and evs:
        for s, in w.cx.execute(f"SELECT status FROM assertion WHERE subject_kind='event' AND subject_id IN ({','.join('?' * len(evs))}) AND artifact_sha256=?", (*evs, w.sha(x["record"]))):
            st[s] = st.get(s, 0) + 1
    on = lambda e: w.cx.execute("SELECT COUNT(*) FROM assertion WHERE subject_kind='event' AND subject_id=?" + (" AND artifact_sha256=?" if x.get("record") else ""), (e, w.sha(x["record"])) if x.get("record") else (e,)).fetchone()[0]
    got = {"events": len(evs), "statements": st, "dates": [r[1] for r in rows], "per_event": [on(e) for e in evs]}
    return has(got, w.value({k: v for k, v in x.items() if k in got})), got

def e_disagreements(w, x, want):
    d = w.catalog().disagreements(w.person(x["person"])); return has(d, x["is"]), d

def e_question(w, x, want):
    q = "SELECT kind, status, closed_reason, detail_json FROM research_question WHERE subject_person_id=?"; args = [w.person(x["person"])]
    for k in ("kind", "status", "closed_reason"):
        if k in x: q += f" AND {k}=?"; args.append(x[k])
    rows = [dict(r) for r in w.cx.execute(q, args)]
    if "detail_has" in x: rows = [r for r in rows if x["detail_has"] in (r["detail_json"] or "")]
    if "count" in x: return has(len(rows), x["count"]), rows
    return bool(rows) == x.get("exists", True), rows

def e_assertions_on(w, x, want):
    kinds = x.get("kinds", ["person", "event"])
    got = {r[0]: r[1] for r in w.cx.execute(f"SELECT status, COUNT(*) FROM assertion WHERE artifact_sha256=? AND subject_kind IN ({','.join('?' * len(kinds))}) GROUP BY status", (w.sha(x["record"]), *kinds))}
    got = {"undecided": got.get("undecided", 0), "accepted": got.get("accepted", 0), "rejected": got.get("rejected", 0)}
    return has(got, {k: v for k, v in x.items() if k in got}), got

def e_links(w, x, want):
    """The statuses of a person's links to the personas of one name and role (and row, `sequence`) on a record, over every
    reading."""
    q = "SELECT pp.status FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id WHERE pp.person_id=? AND pe.artifact_sha256=?"; args = [w.person(x["person"]), w.sha(x["record"])]
    if "persona" in x: q += " AND pe.name_text=?"; args.append(x["persona"])
    if "role" in x: q += " AND pe.role_in_record=?"; args.append(x["role"])
    if "sequence" in x: q += " AND pe.sequence=?"; args.append(x["sequence"])
    if "persona_id" in x: q += " AND pe.id=?"; args.append(w.value(x["persona_id"]))
    got = sorted(r[0] for r in w.cx.execute(q, args))
    return has(got, x["is"]), got

def e_is_subject(w, x, want):
    v = bool(w.catalog().is_subject(w.sha(x["record"]), w.person(x["person"]))); return v == x.get("is", True), v

def e_citations_held(w, x, want):
    v = [c for c in w.catalog().person_citations(w.person(x["person"]), subject_only=True) if c[2]]; return has(len(v), x["count"]), v

def e_checklist_row(w, x, want):
    from checklist import build
    r = build(w.catalog(), w.person(x["person"]))
    row = next((row for row in r["checklist"]["A"] + r["checklist"]["B"] if row["record"] == x["record"] and ("instance" not in x or str(row.get("instance") or "") == str(x["instance"]))), None)
    got = {"status": row["status"], "sources": row.get("sources")} if row else None
    return row is not None and has(got, {k: v for k, v in x.items() if k in ("status", "sources")}), got

def e_baseline(w, x, want):
    b = w.catalog().baseline(w.person(x["person"])); return b["complete"] == x.get("complete", True), b

def e_waiting(w, x, want):
    """Catalog.waiting's own counts for a person: documents to decide, runs_next, needs_hand, conflicts, editable_only, and
    leads (a relative a memorial merely lists, never a document)."""
    got = w.catalog().waiting(w.person(x["person"])); return has(got, {k: v for k, v in x.items() if k != "person"}), got

def e_step(w, x, want):
    st = w.step(x); n = len(w.cx.execute("SELECT id FROM search_plan WHERE person_id=?", (w.person(x["person"]),)).fetchall()) if "person" in x and isinstance(x, dict) else None
    if st is None: return x.get("exists") is False, {"count_on_person": n}
    got = dict(st)
    got["query"] = json.loads(got.get("query_json") or "{}"); got["sources"] = json.loads(got.get("sources_json") or "[]")
    return x.get("exists", True) and has(got, w.value(x.get("fields", {}))), {k: got.get(k) for k in ("kind", "mode", "status", "row_key", "step_key", "locator_source_id", "locator_kind", "locator_value", "rationale", "query", "sources")}

def e_step_count(w, x, want):
    q = "SELECT COUNT(*) FROM search_plan WHERE person_id=?"; args = [w.person(x["person"])]
    for k in ("kind", "mode", "status"):
        if k in x: q += f" AND {k}=?"; args.append(x[k])
    if "step_key_like" in x: q += " AND step_key LIKE ?"; args.append(x["step_key_like"])
    n = w.cx.execute(q, args).fetchone()[0]; return has(n, x["is"]), n

def e_fetch_entries(w, x, want):
    """The fetch list's entries at a holder for the people named: their names, how each is saved, and its link."""
    from fetches import openable
    entries = openable(w.cx, w.tid)
    if "holder" in x: entries = [e for e in entries if e["holder_id"] == x["holder"]]
    if "person" in x: names = [w.name_of(p) for p in w.people(x["person"])]; entries = [e for e in entries if any(n in e["people"] for n in names)]
    if "url_has" in x: entries = [e for e in entries if x["url_has"] in (e.get("url") or "")]
    got = [{"save_as": e["save_as"], "how": e.get("how"), "people": e["people"], "url": e.get("url"), "tail": e["save_as"][-11:], "stem": e["save_as"][:-11]} for e in entries]
    return has(got, w.value(x["is"])), got

def e_search_log(w, x, want):
    """A step's runs as every reader reads them, the rows no restatement superseded; {"superseded": true} every row the step
    holds, each with `superseded` saying whether a later row restates it, in the order written."""
    st = w.step(x["step"])
    rows = [dict(r) for r in w.cx.execute("SELECT id, source_id, outcome, notes, artifacts_json, query_json, superseded_by FROM search_log WHERE plan_step_id=?"
                                          + ("" if x.get("superseded") else " AND superseded_by IS NULL") + " ORDER BY id", (st["id"],))] if st else []
    for r in rows: r["artifacts"] = json.loads(r["artifacts_json"] or "[]"); r["query"] = json.loads(r["query_json"] or "{}"); r["superseded"] = r["superseded_by"] is not None
    return has(rows, w.value(x["is"])), [{k: r[k] for k in ("source_id", "outcome", "notes", "artifacts", "superseded")} for r in rows]

def e_named_for(w, x, want):
    from match import persons_for
    got = sorted(w.name_of(p) for p, _, _ in persons_for(w.cx, w.sha(x["record"])))
    return has(got, x["is"]), got

def e_audit(w, x, want):
    q = "SELECT actor, action, diff_json FROM audit_log WHERE entity_kind=?"; args = [x["entity"]]
    if "person" in x: q += " AND entity_id=?"; args.append(w.person(x["person"]))
    elif "id" in x: q += " AND entity_id=?"; args.append(w.person(x["id"]) if x["entity"] == "person" else w.value(x["id"]))
    if "action" in x: q += " AND action=?"; args.append(x["action"])
    rows = [dict(r) for r in w.cx.execute(q + " ORDER BY at, id", args)]
    for r in rows: r["diff"] = json.loads(r["diff_json"] or "{}")
    if "diff_key" in x: rows = [r for r in rows if r["diff"].get(x["diff_key"]) is not None]
    got = [{"actor": r["actor"], "action": r["action"], "diff": r["diff"]} for r in rows]
    return has(got, w.value(x["is"])), got

def e_hints(w, x, want):
    from cards import hints_on
    h = hints_on(w.cx, w.tid, w.sha(x["record"]), w.person(x["person"]))
    got = {"count": len(h), "hints": [{"persona": k, "hint": v["hint"], "why": v["why"], "agrees": v["agrees"]} for k, v in h.items()]}
    if "persona" in x: got["one"] = next((v for k, v in h.items() if k == w.value(x["persona"])), None)
    return has(got, w.value({k: v for k, v in x.items() if k in ("count", "hints", "one")})), got

def e_living(w, x, want):
    v = w.catalog().living(w.person(x["person"])); return has(v, {k: v_ for k, v_ in x.items() if k in ("status", "tier", "reason")}), v

def e_mode(w, x, want):
    """The one mode of every search step the checklist opens for the person at a source with a connector (a cited row's
    fetch aside); "planned" reads the plan's own rows instead."""
    from checklist import build
    from connectors import answers
    cat = w.catalog()
    runnable = lambda record, sources: any(cat.sources.get(sid, {}).get("connector") and answers(cat.sources[sid]["connector"], record) for sid in sources)
    pid = w.person(x["person"])
    if x.get("planned"):
        modes = {r["mode"] for r in w.cx.execute("SELECT row_key, sources_json, mode FROM search_plan WHERE person_id=? AND kind='search' AND mode IN ('auto','assisted')", (pid,)) if runnable(r["row_key"].split(":")[0], json.loads(r["sources_json"]))}
    else:
        r = build(cat, pid)
        if not r["baseline"]["complete"]: return False, f"the baseline is not complete: undecided {r['baseline']['undecided']}"
        modes = {s["search"]["mode"] for s in r["checklist"]["A"] + r["checklist"]["B"] if s.get("search") and s["search"]["mode"] in ("auto", "assisted") and runnable(s["record"], s["sources"])}
    got = modes.pop() if len(modes) == 1 else sorted(modes)
    return got == x["is"], got

def e_foundation(w, x, want):
    from checklist import build
    f = next((f for f in build(w.catalog(), w.person(x["person"]))["foundation"] if f["field"] == x["field"]), None)
    return f is not None and has(f, {k: v for k, v in x.items() if k in ("value", "basis")}), f

def e_results_page(w, x, want):
    from cards import search_card
    sc = search_card(w.cx, w.tid, w.sha(x["record"]), w.person(x["person"])); w.cx.row_factory = sqlite3.Row
    rows = (sc or {}).get("rows", [])
    got = {"rows": len(rows), "fits": [r["n"] for r in rows if r["fits"]], "names": {str(r["n"]): r["name"] for r in rows}, "places": {str(r["n"]): r.get("burial") for r in rows}}
    return sc is not None and has(got, {k: v for k, v in x.items() if k in got}), got

def e_place_string(w, x, want):
    row = w.cx.execute("SELECT id, status, place_id, resolver, notes FROM place_string WHERE raw=?", (x["raw"],)).fetchone()
    if not row: return False, None
    cat = w.catalog()
    events = [r[0] for r in w.cx.execute("""SELECT DISTINCT e.id FROM event e JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                             JOIN place_string ps ON ps.id=pf.place_string_id WHERE e.tree_id=? AND ps.raw=?""", (w.tid, x["raw"]))]
    placed = [w.cx.execute("SELECT place_id FROM event WHERE id=?", (e,)).fetchone()[0] for e in events]
    got = {"status": row["status"], "has_place": bool(row["place_id"]), "resolver": row["resolver"], "notes": json.loads(row["notes"] or "{}"), "events": len(events),
           "events_placed": sum(1 for p in placed if p), "events_at_place": sum(1 for p in placed if p and p == row["place_id"]),
           "chain": cat.place(events[0], row["place_id"])["text"] if events and row["place_id"] else None,
           "audited": bool(w.cx.execute("SELECT 1 FROM audit_log WHERE entity_kind='place_string' AND entity_id=? AND action='accept'", (row["id"],)).fetchone())}
    return has(got, w.value({k: v for k, v in x.items() if k in got})), got

def e_artifact(w, x, want):
    from catalog import tier_sql
    row = w.cx.execute(f"""SELECT ar.source_id, ar.mime, ar.locator_kind, ar.locator_value, ar.redistributable, ar.manifest_json, ar.derived_from, ar.http_status, ar.http_etag, ar.http_last_modified, {tier_sql()} AS tier,
                                  (SELECT c.trust_tier FROM collection c WHERE c.id=ar.collection_id) AS collection_tier FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?""", (w.sha(x["record"]),)).fetchone()
    if not row: return False, None
    got = dict(row); got["manifest"] = json.loads(got.pop("manifest_json") or "{}")
    return has(got, w.value({k: v for k, v in x.items() if k in got})), {k: got[k] for k in ("source_id", "mime", "locator_kind", "locator_value", "redistributable", "tier", "collection_tier", "derived_from", "http_status", "http_etag", "http_last_modified")}

def e_artifact_where(w, x, want):
    row = w.cx.execute("SELECT redistributable, manifest_json FROM artifact WHERE mime=?", (x["mime"],)).fetchone()
    got = {"redistributable": row["redistributable"], "manifest": json.loads(row["manifest_json"] or "{}")} if row else None
    return row is not None and has(got, x["is"]), got

def e_conflict_rule(w, x, want):
    """The rule's test on a conflict (conclude.classes_decide) about a person's event of a `type`, on its `axis` (date or
    place): whether it keeps a statement (`taken`) and the reason in words (`why`)."""
    from conclude import classes_decide
    row = w.cx.execute("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type=? ORDER BY e.date_start",
                       (w.person(x["person"]), x["type"])).fetchone()
    if not row: return False, "no such event"
    keep, why = classes_decide(w.cx, w.tid, row[0], x["axis"])
    got = {"taken": keep is not None, "why": why}
    return has(got, w.value({k: v for k, v in x.items() if k in got})), got

def e_classes(w, x, want):
    """The classes of a record's statements about a person, in words (catalog.evidence_classes): the statements on the
    person's events of `event_type`, or on a family link (`link`: parents, spouses or children), that the record carries;
    some statement's classes match the pattern given (source, information, evidence, relationship, original)."""
    from catalog import evidence_classes
    from facts import fact_subjects
    pid = w.person(x["person"]); sha = w.sha(x["record"])
    subs = fact_subjects(w.cx, pid, x["link"]) if x.get("link") else \
           [("event", e) for e, in w.cx.execute("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type=?", (pid, x["event_type"]))]
    ids = [a for k, s in subs for a, in w.cx.execute("SELECT id FROM assertion WHERE subject_kind=? AND subject_id=? AND artifact_sha256=? ORDER BY asserted_at, id", (k, s, sha))]
    got = [{k: c[k] for k in ("source", "information", "evidence", "relationship", "original")} for c in (evidence_classes(w.cx, a) for a in ids)]
    pattern = {k: v for k, v in x.items() if k in ("source", "information", "evidence", "relationship", "original")}
    return any(has(g, pattern) for g in got), got

def e_statement(w, x, want):
    """Which reading of a record its statements on a person's events of `event_type` are read through
    (catalog.statement_of): one word each, current when it is the record's current reading, earlier when not."""
    from catalog import statement_of
    pid = w.person(x["person"]); sha = w.sha(x["record"])
    cur = w.cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND superseded_by IS NULL AND status<>'failed'", (sha,)).fetchone()[0]
    ids = [a for a, in w.cx.execute("""SELECT a.id FROM assertion a JOIN event_participant ep ON ep.event_id=a.subject_id JOIN event e ON e.id=a.subject_id
                                       WHERE a.subject_kind='event' AND ep.person_id=? AND e.event_type=? AND a.artifact_sha256=? ORDER BY a.asserted_at, a.id""", (pid, x["event_type"], sha))]
    got = ["current" if statement_of(w.cx, a)["extraction"] == cur else "earlier" for a in ids]
    return has(got, x["is"]), got

def e_states(w, x, want):
    """A record's statements on a person, in the order they were written: on their events of `event_type`, on the person
    themselves (`kind`: person) or on their own family links (`kind`: family_member); each one's `status`, who set it (`by`,
    assertion.asserted_by) and whether that was a person's own decision on it (`person_decided`)."""
    pid = w.person(x["person"]); sha = w.sha(x["record"]); kind = x.get("kind", "event")
    if kind == "event":
        rows = w.cx.execute("""SELECT a.status, a.asserted_by, a.person_decided FROM assertion a JOIN event_participant ep ON ep.event_id=a.subject_id JOIN event e ON e.id=a.subject_id
                               WHERE a.subject_kind='event' AND ep.person_id=? AND e.event_type=? AND a.artifact_sha256=? ORDER BY a.id""", (pid, x["event_type"], sha))
    elif kind == "person": rows = w.cx.execute("SELECT status, asserted_by, person_decided FROM assertion WHERE subject_kind='person' AND subject_id=? AND artifact_sha256=? ORDER BY id", (pid, sha))
    else: rows = w.cx.execute("""SELECT status, asserted_by, person_decided FROM assertion WHERE subject_kind='family_member' AND json_extract(subject_id,'$[1]')=? AND artifact_sha256=?
                                 ORDER BY id""", (pid, sha))
    got = [{"status": r[0], "by": r[1], "person_decided": bool(r[2])} for r in rows]
    return has(got, w.value(x["is"])), got

def e_extractor(w, x, want):
    """The extractor row of a reading, and what the reading kept: `kind`, `name`, `model_id`, `version`; `prompt_is_instruction`,
    whether the row's prompt hash is the sha256 of the instruction file as it stands; `image_is` and `year`, the extraction's own
    structured_json; `regions`, each persona's region_json in the order read."""
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server, hashlib
    row = w.cx.execute("SELECT x.kind, x.name, x.version, x.model_id, x.prompt_sha256, e.structured_json FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (w.value(x["extraction"]),)).fetchone()
    got = dict(row) if row else None
    if got:
        with open(server.READ_RECORD, "rb") as fh: got["prompt_is_instruction"] = got["prompt_sha256"] == hashlib.sha256(fh.read()).hexdigest()
        got.update(json.loads(got.pop("structured_json") or "{}"))
        got["regions"] = [json.loads(r) for r, in w.cx.execute("SELECT region_json FROM persona WHERE extraction_id=? ORDER BY sequence", (w.value(x["extraction"]),))]
    return row is not None and has(got, {k: v for k, v in x.items() if k in ("kind", "name", "model_id", "version", "prompt_is_instruction", "image_is", "year", "regions")}), got

def e_person_persona(w, x, want):
    row = w.cx.execute("SELECT status FROM person_persona WHERE person_id=? AND persona_id=?", (w.person(x["person"]), w.value(x["persona"]))).fetchone()
    got = row[0] if row else None
    return (got is None) if x.get("exists") is False else got == x["status"], got

def e_reach(w, x, want):
    from match import by_name_and_year
    reach = by_name_and_year(w.catalog(), w.cx, w.tid, {"name": x["name"], "birth": x.get("birth")})
    got = sorted(w.name_of(p) for p in reach)
    return all(w.person(p) in reach for p in x.get("has", [])) and all(w.person(p) not in reach for p in x.get("lacks", [])), got

def e_trusted(w, x, want):
    """Whether a membership, or a person's events of a type ({"person", "type"}), rest on trusted ground for the rule, stating
    a date or a place when `stating` says so."""
    from conclude import trusted_evidence
    if "event" in x:
        ev = x["event"]; kind = "event"
        ids = [r[0] for r in w.cx.execute("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type=?", (w.person(ev["person"]), ev["type"]))]
    else:
        m = x["membership"]; kind = "family_member"; ids = [w.treelib.dumps([w.value(m["family"]), w.person(m["person"]), m["role"]])]
    v = bool(trusted_evidence(w.cx, w.tid, kind, ids, stating=x.get("stating"), without=tuple(x.get("without", ()))))
    return v == x.get("is", True), v

def e_plan_idempotent(w, x, want):
    from plan import plan_person
    pids = [p for p, in w.cx.execute("SELECT id FROM person WHERE tree_id=? AND merged_into IS NULL", (w.tid,))] if x == "all" else w.people(x)
    for p in pids: plan_person(w.cx, w.tid, p, BY)
    w.cx.commit()
    st = {w.name_of(p): plan_person(w.cx, w.tid, p, BY) for p in pids}; w.cx.commit()
    off = {n: v for n, v in st.items() if v["steps_new"] or v["steps_dropped"] or v["questions_new"] or v["questions_closed"]}
    return not off, off

def e_no_repeats(w, x, want):
    n = w.cx.execute("SELECT count(*) FROM (SELECT 1 FROM assertion WHERE persona_fact_id IS NOT NULL GROUP BY subject_kind, subject_id, persona_fact_id, artifact_sha256, coalesce(notes,'') HAVING count(*)>1)").fetchone()[0]
    return n == 0, n

def e_one_event(w, x, want):
    """One statement, one event: no record fact stated on two events of its type that a person or a family holds (an event no
    one holds, left by a fold or a move, aside)."""
    n = w.cx.execute("""SELECT count(*) FROM (SELECT a.persona_fact_id FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN event e ON e.id=a.subject_id AND e.event_type=pf.fact_type
                        WHERE a.subject_kind='event' AND EXISTS (SELECT 1 FROM event_participant ep WHERE ep.event_id=a.subject_id)
                        GROUP BY a.persona_fact_id HAVING count(DISTINCT a.subject_id)>1)""").fetchone()[0]
    return n == 0, n

def e_whole(w, x, want):
    v = whole(w.cx); return v is None, v

def e_file(w, x, want):
    """Whether a file is there: `name` in the inbox, or in `folder`, or a whole `path` (bound); with `fixture`, holding that
    fixture's bytes, so a file written over by another of its name shows."""
    path = w.value(x["path"]) if x.get("path") else os.path.join(w.value(x["folder"]) if x.get("folder") else w.treelib.inbox_dir(), w.value(x["name"]))
    there = bool(path) and os.path.exists(path)
    if there and x.get("fixture"):
        with open(path, "rb") as fh, open(os.path.join(FIXTURES, x["fixture"]), "rb") as ref: there = fh.read() == ref.read()
    return there == x.get("exists", True), path

def e_count(w, x, want):
    """A count from one of the catalog's tables, for a few plain questions: the rows of a table for a person."""
    q = {"persona_links_of": "SELECT COUNT(*) FROM person_persona WHERE person_id=?", "family_rows_of": "SELECT COUNT(*) FROM family_member WHERE person_id=?",
         "steps_of": "SELECT COUNT(*) FROM search_plan WHERE person_id=?", "personas_of": "SELECT COUNT(*) FROM persona WHERE artifact_sha256=?", "logs_of_step": "SELECT COUNT(*) FROM search_log WHERE plan_step_id=? AND superseded_by IS NULL",
         "events_of": "SELECT COUNT(*) FROM event_participant WHERE person_id=?", "extractions_of": "SELECT COUNT(*) FROM extraction WHERE artifact_sha256=?"}
    kind = next(k for k in q if k in x)
    arg = w.sha(x[kind]) if kind in ("personas_of", "extractions_of") else w.step(x[kind])["id"] if kind == "logs_of_step" else w.person(x[kind])
    n = w.cx.execute(q[kind], (arg,)).fetchone()[0]
    return has(n, x["is"]), n

def e_proposal_status(w, x, want):
    row = w.cx.execute("SELECT status, decision_note, decided_by FROM proposal WHERE id=?", (w.value(x["id"]),)).fetchone()
    got = dict(row) if row else None
    return row is not None and has(got, {k: v for k, v in x.items() if k in ("status", "decision_note", "decided_by")}), got

def e_proposals_of(w, x, want):
    """Every proposal of a kind on the tree, by status: a place answer or a duplicate merged."""
    q = "SELECT status, decision_note, decided_by, kind FROM proposal WHERE tree_id=? AND kind=?"; args = [w.tid, x["kind"]]
    rows = [dict(r) for r in w.cx.execute(q, args)]
    return has(rows, w.value(x["is"])), rows

def e_person_merged(w, x, want):
    v = w.cx.execute("SELECT merged_into FROM person WHERE id=?", (w.person(x["person"]),)).fetchone()[0]
    return (v == w.person(x["into"])) if x.get("into") else (v is None), v

def e_find_person(w, x, want):
    v = w.catalog().find_person(x["name"]); return v == w.person(x["is"]), v

def e_listed(w, x, want):
    listed = [r[0] for r in w.cx.execute("SELECT id FROM person WHERE tree_id=? AND merged_into IS NULL", (w.tid,))]
    return all(w.person(p) in listed for p in x.get("has", [])) and all(w.person(p) not in listed for p in x.get("lacks", [])), len(listed)

def e_origins(w, x, want):
    """Where the tree comes from (overview.origins): the people by what brought them in (`people`: file, record) and the
    accepted documents by what fetched them (`documents`: citation, lead, search, hand)."""
    from overview import origins
    got = origins(w.cx, w.tid)
    return has(got, {k: v for k, v in x.items() if k in ("people", "documents")}), got

def e_overview(w, x, want):
    """A person's card on the tree overview (tools/overview.py overview), among the confirmed generations or the others at the
    edge, matching `is`: its `parents`, `claimed_parents`, `spouses`, `claimed_spouses` and the rest."""
    from overview import overview
    o = overview(w.cx, w.tid); pid = w.person(x["person"])
    card = next((c for gen in o["generations"] for c in gen if c["id"] == pid), None) or next((c for c in o["others"] if c["id"] == pid), None)
    return card is not None and has(card, w.value(x["is"])), card

def e_unsupported(w, x, want):
    """The untrusted data report (schema/catalog.sql's v_unsupported_person and v_unsupported_event) on a person: `listed`, whether
    the person is a row of v_unsupported_person, and `events`, how many rows of v_unsupported_event are events the person takes part
    in (event_participant), an event a merge folded and returned to the duplicate among them."""
    pid = w.person(x["person"])
    got = {"listed": bool(w.cx.execute("SELECT 1 FROM v_unsupported_person WHERE id=?", (pid,)).fetchone()),
           "events": w.cx.execute("SELECT COUNT(*) FROM v_unsupported_event e WHERE EXISTS (SELECT 1 FROM event_participant ep WHERE ep.event_id=e.id AND ep.person_id=?)", (pid,)).fetchone()[0]}
    return has(got, {k: v for k, v in x.items() if k in got}), got

def e_households(w, x, want):
    """The current stored households as households_now reads them, with `form` only those of that form, matching `is`."""
    got = [h for h in households_now(w) if "form" not in x or h["form"] == x["form"]]
    return has(got, w.value(x["is"])), got

def e_household_leads(w, x, want):
    """What each household not wholly held that the tree ties to a `person` leads to (tools/households.py candidates), one entry
    per household, matching `is`: its `answer` (the pages of its own search `held`, `count`, `total`, `next` and `next_url`), the
    candidates in `order` and those `open` (each `name`, `ark`, `born`, `for`, `why`), those `left_out` (`name`, `ark`, `why`) and
    those `tried` (`name`, `ark`, `where`)."""
    from households import candidates, waiting_for
    got = [candidates(w.cx, w.tid, h) for h in waiting_for(w.cx, w.tid, w.person(x["person"]))]
    return has(got, w.value(x["is"])), [{"next": c["answer"]["next"], "order": [(r["name"], r["for"]) for r in c["order"]], "left_out": [r["name"] for r in c["left_out"]],
                                         "tried": [r["name"] for r in c["tried"]], "first_why": (c["order"] or [{}])[0].get("why")} for c in got]

def e_assertion_subject(w, x, want):
    v = w.cx.execute("SELECT subject_id FROM assertion WHERE persona_id=?", (w.value(x["persona"]),)).fetchone()
    return v is not None and v[0] == w.person(x["is"]), v and w.name_of(v[0])

EXPECTS = {"last": e_last, "bound": e_bound, "cards": e_cards, "card": e_card, "rule": e_rule, "facts": e_facts, "alias": e_alias, "linked": e_linked, "memberships": e_memberships, "persons": e_persons,
           "event": e_event, "family_event": e_family_event, "disagreements": e_disagreements, "question": e_question, "assertions_on": e_assertions_on, "links": e_links, "is_subject": e_is_subject, "citations_held": e_citations_held,
           "checklist_row": e_checklist_row, "baseline": e_baseline, "waiting": e_waiting, "step": e_step, "step_count": e_step_count, "fetch_entries": e_fetch_entries, "search_log": e_search_log, "named_for": e_named_for,
           "audit": e_audit, "hints": e_hints, "living": e_living, "mode": e_mode, "foundation": e_foundation, "results_page": e_results_page, "place_string": e_place_string, "artifact": e_artifact,
           "artifact_where": e_artifact_where, "classes": e_classes, "statement": e_statement, "states": e_states, "conflict_rule": e_conflict_rule, "extractor": e_extractor, "person_persona": e_person_persona, "reach": e_reach, "trusted": e_trusted, "plan_idempotent": e_plan_idempotent,
           "no_repeats": e_no_repeats, "one_event": e_one_event, "whole": e_whole, "file": e_file, "count": e_count, "proposal_status": e_proposal_status, "proposals_of": e_proposals_of, "person_merged": e_person_merged,
           "find_person": e_find_person, "listed": e_listed, "assertion_subject": e_assertion_subject, "origins": e_origins, "overview": e_overview, "compare": e_compare, "names": e_names,
           "parents": e_parents, "households": e_households, "household_leads": e_household_leads, "unsupported": e_unsupported}

def load(folder):
    """Every scenario file under a folder, in name order."""
    for f in sorted(os.listdir(folder)):
        if f.endswith(".json"):
            with open(os.path.join(folder, f), encoding="utf-8") as fh: yield f, json.load(fh)

def named(only):
    """The scenario files, under every folder of scenarios, whose file name has `only` in it."""
    return [f for sub in sorted(os.listdir(SCENARIOS)) for f, _ in load(os.path.join(SCENARIOS, sub)) if only in f]

def check(folder, keep, show, only=None):
    """Every scenario under the folder walked on its own scratch, or those whose file name has `only` in it; one line each; the number that failed."""
    bad = 0
    for f, spec in load(folder):
        if only and only not in f: continue
        if spec.get("awaits") and not os.path.exists(os.path.join(FIXTURES, spec["awaits"])):   # a scenario on a capture only the owner's browser can make: named, never counted ok
            print(f"wait {spec.get('title', f)}: not run, it reads tests/fixtures/{spec['awaits']}, which is not captured yet ({spec.get('capture', 'tests/fixtures/README.md')})")
            continue
        os.environ[offline.WHO] = spec.get("title", "scenario")        # a request any process of this scenario is refused is named for it
        try: fails = Walker(spec, keep, show).walk()
        except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
        finally: os.environ.pop(offline.WHO, None)
        title = spec.get("title", f)
        if fails: bad += 1; print(f"FAIL {title}: " + "; ".join(fails))
        else: print(f"ok   {title}: {spec.get('line', '')}")
    return bad
