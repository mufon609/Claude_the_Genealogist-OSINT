"""One walker for the scenarios under tests/fixtures/scenarios/: the matcher, the standing rule, the decision writers
and the loop's tools run on the harness tree as the data says, and what they write or refuse checked as the data says.

A scenario file names the tree to ingest (tests/fixtures/harness.ged, the owner's own export cut down) and a list of
steps. A step does one thing (an action) and then checks any number of expectations; the vocabulary of both is in
tests/fixtures/README.md. People are named by the harness file's own entry ids, records by the label a step bound them
under, and nothing in this module names a person, a place or a page: another family's export, fixtures and scenarios run
through it unchanged.
"""
import json, os, shutil, sqlite3, subprocess, sys
from common import BY, FIXTURES, ROOT, TOOLS, Fails, connect, done, run, scratch, tool, whole

SCENARIOS = os.path.join(FIXTURES, "scenarios")
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"   # the smallest of JPEG files: a stand-in for a photograph the harness never parses

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

class Walker:
    """The scenario's state: the scratch, the tree, the labels steps bound, and the last action's result."""
    def __init__(self, spec, keep, show):
        self.spec, self.keep, self.show = spec, keep, show
        self.env = {}; self.fails = Fails(); self.step_no = 0

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

    def close(self):
        w = whole(self.cx)
        if w: self.fails.append(w)
        self.cx.close(); done(self.root, self.keep, self.spec.get("title", "scenario"))

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
        """The bytes an archive step archives: a fixture as it is, a stand-in (an image, a page saved from a URL, or
        nothing but a saved-from comment), with a suffix when the same page must be archived again as other bytes."""
        if a.get("fixture"):
            with open(os.path.join(FIXTURES, a["fixture"]), "rb") as fh: data = fh.read()
        elif a.get("stand_in") == "image": data = JPEG
        else: data = (f"<!-- saved from {a.get('saved_from', '')} -->\n" if a.get("saved_from") else "").encode() + b"<html></html>"
        return data + a.get("suffix", "").encode()

    # ---------------------------------------------------------------- the walk
    def walk(self):
        self.open()
        try:
            for step in self.spec["steps"]:
                self.step_no += 1
                self.env["last"] = None
                if self.show: print("    -", step.get("say") or short({k: v for k, v in step.items() if k not in ("expect", "say")}, 160))
                action = next((k for k in step if k in ACTIONS), None)
                if action:
                    try: self.env["last"] = ACTIONS[action](self, self.value(step[action]) if action not in ("transcribe", "place_card", "step", "fake_run", "fake_fetch", "run", "run_all", "run_connector") else step[action])
                    except Exception as e:
                        self.fails.append(f"step {self.step_no} ({step.get('say') or action}) raised {type(e).__name__}: {e}"); self.cx.rollback()
                        if self.show: import traceback; traceback.print_exc()
                        continue
                    self.cx.commit()
                    if "as" in step: self.env[step["as"]] = self.env["last"]
                for want in step.get("expect", []):
                    kind = next((k for k in want if k in EXPECTS), None)
                    if not kind: self.fails.append(f"step {self.step_no}: no such expectation {list(want)}"); continue
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
    version carries to be checked against a row put in the shape it corrects."""
    w.cx.commit()
    return {"printed": run(tool("initdb.py"), "--db", w.db, "--migrate").strip()}

def a_attach(w, x):
    """A fixture dropped into the inbox as a save would leave it and attached: the record's sha and the attach's report."""
    from attach import attach_inbox
    name = x.get("as_file") or x["fixture"]
    os.makedirs(w.treelib.inbox_dir(), exist_ok=True)
    with open(os.path.join(w.treelib.inbox_dir(), name), "wb") as fh: fh.write(w.fixture_bytes(x))
    kw = {"about": w.person(x["about"])} if x.get("about") else {}
    res = attach_inbox(w.cx, w.tid, w.slug, BY, [name], **kw)
    r = res[0] if res else {}
    return {"sha": r.get("sha256"), "file": name, "steps": r.get("steps"), "left": r.get("left"), "repeat": r.get("repeat"), "proposals": r.get("proposals"), "accepted_by_rule": r.get("accepted_by_rule"),
            "outcome": r.get("outcome"), "identity": r.get("identity"), "extraction": r.get("extraction"), "unparsed": r.get("unparsed"), "results": res,
            "taken": [(n, why) for _, n, why in (r.get("accepted_by_rule") or [])], "step_people": [n for _, n, _, _ in (r.get("steps") or [])]}

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
    from conclude import decide
    card = w.card(x["card"])
    if card is None: raise KeyError(f"no card {short(x['card'])}")
    r = decide(w.cx, w.tid, card["id"], x.get("status", "accepted"), x.get("by", BY), note=x.get("note", "harness"), choice=x.get("choice"))
    return {**r, "card": card["id"], "person_id": json.loads(card["payload_json"]).get("person_id")}

def a_withdraw(w, x):
    from conclude import withdraw
    card = w.card(x["card"]); withdraw(w.cx, w.tid, card["id"], x.get("by", BY), x.get("why", "harness: taken back"), w.treelib.now())
    return {"card": card["id"]}

def a_reconsider(w, x):
    from conclude import reconsider
    rows = reconsider(w.cx, w.tid, BY, dry_run=bool(x.get("dry")))
    return {"rows": rows}

def a_fact(w, x):
    from facts import decide_fact
    pid = w.person(x["person"]); out = {}
    for f in (x.get("fields") or [x["field"]]): out[f] = decide_fact(w.cx, w.tid, pid, f, x.get("status", "accepted"), x.get("note"), BY)
    return out

def a_assertion(w, x):
    """One statement of one record decided on its own, through tools/conclude.py assertion: the assertion found by the
    record, the person and the event type (or the subject kind)."""
    pid = w.person(x["person"]); sha = w.sha(x["record"]) if x.get("record") else None
    if x.get("membership"):                          # the file's own claim of a family link: the family found through one of its partners
        m = x["membership"]; fid = w.cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (w.person(m["family_of"]),)).fetchone()[0]
        row = w.cx.execute("SELECT id FROM assertion WHERE tree_id=? AND subject_kind='family_member' AND subject_id=? ORDER BY asserted_at", (w.tid, w.treelib.dumps([fid, pid, m["role"]]))).fetchone()
    elif x.get("event_type"):
        row = w.cx.execute("""SELECT a.id FROM assertion a JOIN event e ON e.id=a.subject_id JOIN event_participant ep ON ep.event_id=e.id
                              WHERE a.tree_id=? AND a.subject_kind='event' AND a.artifact_sha256=? AND e.event_type=? AND ep.person_id=? AND a.status=? ORDER BY a.asserted_at""", (w.tid, sha, x["event_type"], pid, x.get("was", "accepted"))).fetchone()
    else: row = w.cx.execute("SELECT id FROM assertion WHERE tree_id=? AND subject_kind=? AND subject_id=? AND artifact_sha256=? ORDER BY asserted_at", (w.tid, x.get("kind", "person"), pid, sha)).fetchone()
    if not row: raise KeyError("no such assertion")
    w.cx.commit()
    out = run(tool("conclude.py"), "assertion", row[0], x.get("verdict", "reject"), "--note", x.get("note", "harness"), "--db", w.db, "--tree", w.slug, "--by", BY)
    return {"assertion": row[0], "printed": out.strip()}

def a_link_on_word(w, x):
    from conclude import link_on_word
    fid = link_on_word(w.cx, w.tid, w.person(x["person"]), w.people(x["others"]), x.get("kind", "child"), w.sha(x["record"]), BY, x.get("note", "harness: the owner's word"))
    return {"family": fid, "person": w.person(x["person"])}

def a_living(w, x):
    from conclude import living
    return living(w.cx, w.tid, w.person(x["person"]), x["word"], BY, x.get("note", "harness"))

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

def a_save(w, x):
    """A page or an image saved in the browser, as a stand-in: into the inbox, or into a download folder for collect.
    Under the name the fetch list prints for it, unless `name` gives the file's own name instead (the sanitized shape a
    browser actually produced, to prove collect takes a page by its saved-from identity whatever it is named)."""
    from fetches import waiting
    pid = w.person(x["person"]) if x.get("person") else None
    entries = [e for e in waiting(w.cx, w.tid) if (not x.get("holder") or e["holder_id"] == x["holder"]) and (pid is None or any(s in e["step_ids"] for s in [s[0] for s in w.cx.execute("SELECT id FROM search_plan WHERE person_id=?", (pid,))]))]
    e = entries[0] if entries else None
    if "name" in x: name = x["name"]
    else:
        if not e: raise KeyError("no fetch entry waiting for that person at that holder")
        name = e["save_as"].replace("<year>", str(x.get("year", "")))
        for k, v in (x.get("fill") or {}).items(): name = name.replace(k, v)
    folder = os.path.join(w.root, x["folder"]) if x.get("folder") else w.treelib.inbox_dir(); os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "wb") as fh: fh.write(w.fixture_bytes({**x, "saved_from": x.get("saved_from") or (e.get("url") if e else None)}))
    return {"entry": e, "file": name, "folder": folder, "url": e.get("url") if e else None, "save_as": e["save_as"] if e else None, "how": e.get("how") if e else None, "steps": e.get("step_ids") if e else None}

def a_collect(w, x):
    from fetches import collect
    names, res = collect(w.cx, w.tid, w.slug, BY, folder=w.value(x["folder"]))
    return {"names": names, "results": res, "files": {r["file"]: r for r in res}}

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
    """A plan step written by the harness itself, as a step nothing generates or a plan the loop's tools are run on."""
    x = w.value(x); sid = w.treelib.ulid(); loc = x.get("locator") or {}
    w.cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,sources_json,mode,expected,status,rationale,on_json,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (sid, w.person(x["person"]), x["row_key"], x.get("seq", 1), x["step_key"], x.get("kind", "search"), x.get("query_type", "name"), json.dumps(x.get("query", {})),
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

def a_place_card(w, x):
    """A place_resolution card for a string of the tree, as the resolver would write it, its candidates' geocoder answers
    planted in the cache so no request goes out."""
    import hashlib
    from resolve_places import RESOLVER, cache_dir, candidate_summary
    raw = x["raw"]; ps = w.cx.execute("SELECT id FROM place_string WHERE raw=?", (raw,)).fetchone()
    if not ps: raise KeyError(f"no place string {raw!r} in the tree")
    os.makedirs(cache_dir(), exist_ok=True)
    for qy in x.get("queries", []):
        with open(os.path.join(cache_dir(), hashlib.sha1(qy.lower().encode()).hexdigest() + ".json"), "w", encoding="utf-8") as fh: json.dump({"query": qy, "fetched_at": w.treelib.now(), "results": x["candidates"]}, fh)
    rx = w.cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", RESOLVER).fetchone()
    rx_id = rx[0] if rx else w.treelib.ulid()
    if not rx: w.cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (rx_id, *RESOLVER, w.treelib.now()))
    pid_ = w.treelib.ulid()
    w.cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                 (pid_, w.tid, "place_resolution", w.treelib.dumps({"raw": raw, "place_string_id": ps[0], "parsed": {}, "queries": x.get("queries", []), "candidates": [candidate_summary(c, 1.0, {}) for c in x["candidates"]], "reason": "harness: the owner chooses"}), "harness: the owner chooses", rx_id, w.treelib.now()))
    w.cx.execute("UPDATE place_string SET resolver=?, resolved_at=? WHERE id=?", (f"ai:{RESOLVER[1]}@{RESOLVER[2]}", w.treelib.now(), ps[0]))
    return {"proposal": pid_, "place_string": ps[0], "raw": raw, "candidates": x["candidates"]}

def a_older_matcher(w, x):
    """The cards on a record marked as an older matcher's, so reconsider must propose them again."""
    from match import MATCHER
    older = w.treelib.ulid(); w.cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (older, MATCHER[0], MATCHER[1], x.get("version", "0.0.1"), w.treelib.now()))
    ids = [r["id"] for r in w.cards_on(x["record"], status="undecided")]
    w.cx.execute(f"UPDATE proposal SET generated_by=? WHERE id IN ({','.join('?' * len(ids))})", (older, *ids))
    return {"cards": ids, "version": MATCHER[2]}

def a_merge(w, x):
    from conclude import merge
    return merge(w.cx, w.tid, w.person(x["duplicate"]), w.person(x["kept"]), BY, x.get("note", "harness: same identity"))

def a_cite(w, x):
    from attach import cite_on_word
    try: sid = cite_on_word(w.cx, w.tid, w.person(x["person"]), x["row"], x["holder"], x["fields"], BY, note=x.get("note"))
    except ValueError as e:
        if x.get("refused"): return {"refused": str(e)}
        raise
    return {"step": sid, "refused": None}

def a_seed(w, x):
    """A stand-in artifact for a record the owner holds and the harness only reads by a typed reading."""
    return a_archive(w, x)

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

ACTIONS = {"plan": a_plan, "migrate": a_migrate, "attach": a_attach, "archive": a_archive, "reread": a_reread, "match": a_match, "decide": a_decide, "withdraw": a_withdraw, "reconsider": a_reconsider,
           "fact": a_fact, "assertion": a_assertion, "link_on_word": a_link_on_word, "living": a_living, "transcribe": a_transcribe, "view": a_view, "save": a_save, "collect": a_collect,
           "question": a_question,
           "log": a_log, "reopen": a_reopen, "step": a_step, "event": a_event, "place_card": a_place_card, "older_matcher": a_older_matcher, "merge": a_merge, "cite": a_cite, "seed": a_seed}

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
    got = {"status": card["status"], "kind": card["kind"], "decided_by": card["decided_by"], "note": card["decision_note"], "rationale": card["rationale"], "person_name": w.name_of(json.loads(card["payload_json"]).get("person_id"))}
    pattern = {k: v for k, v in x.items() if k in ("status", "kind", "decided_by", "note", "rationale", "person_name")}
    return x.get("exists", True) and has(got, w.value(pattern)), got

def e_rule(w, x, want):
    from conclude import rule_accepts
    card = w.card(x)
    if card is None: return False, "no card"
    ok, why = rule_accepts(w.cx, w.tid, card)
    got = {"taken": bool(ok), "why": why}
    pattern = {k: v for k, v in x.items() if k in ("taken", "why")}
    return has(got, w.value(pattern)), got

def e_facts(w, x, want):
    from facts import fact_status
    pid = w.person(x["person"]); got = {f: fact_status(w.cx, pid, f) for f in x if f != "person"}
    return all(got[f] == v for f, v in x.items() if f != "person"), got

def e_alias(w, x, want):
    rows = [list(a) for a in w.cx.execute("SELECT value, kind, status FROM alias WHERE entity_kind='person' AND entity_id=?", (w.person(x["person"]),))]
    return has(rows, w.value(x["is"])), rows

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
    got = {"events": len(rows), "strings": strings, "shown": cat.place(rows[0][0], None)["text"] if rows else None, "canonical_date": canon["date_text"] if canon else None,
           "basis": cat.key_fact_basis(pid, ev).get(x["type"].lower())}
    pattern = {k: v for k, v in x.items() if k in ("events", "strings", "shown", "canonical_date", "basis")}
    return has(got, pattern), got

def e_disagreements(w, x, want):
    d = w.catalog().disagreements(w.person(x["person"])); return has(d, x["is"]), d

def e_question(w, x, want):
    q = "SELECT kind, status, detail_json FROM research_question WHERE subject_person_id=?"; args = [w.person(x["person"])]
    if "kind" in x: q += " AND kind=?"; args.append(x["kind"])
    if "status" in x: q += " AND status=?"; args.append(x["status"])
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
    """The statuses of a person's links to the personas of one name and role on a record, over every reading."""
    q = "SELECT pp.status FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id WHERE pp.person_id=? AND pe.artifact_sha256=?"; args = [w.person(x["person"]), w.sha(x["record"])]
    if "persona" in x: q += " AND pe.name_text=?"; args.append(x["persona"])
    if "role" in x: q += " AND pe.role_in_record=?"; args.append(x["role"])
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
    st = w.step(x["step"])
    rows = [dict(r) for r in w.cx.execute("SELECT id, source_id, outcome, notes, artifacts_json, query_json FROM search_log WHERE plan_step_id=? ORDER BY id", (st["id"],))] if st else []
    for r in rows: r["artifacts"] = json.loads(r["artifacts_json"] or "[]"); r["query"] = json.loads(r["query_json"] or "{}")
    return has(rows, w.value(x["is"])), [{k: r[k] for k in ("source_id", "outcome", "notes", "artifacts")} for r in rows]

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
    got = {"count": len(h), "hints": [{"persona": k, "hint": v["hint"], "agrees": v["agrees"]} for k, v in h.items()]}
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
    row = w.cx.execute(f"SELECT ar.source_id, ar.mime, ar.locator_kind, ar.locator_value, ar.redistributable, ar.manifest_json, ar.derived_from, {tier_sql()} AS tier FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?", (w.sha(x["record"]),)).fetchone()
    if not row: return False, None
    got = dict(row); got["manifest"] = json.loads(got.pop("manifest_json") or "{}")
    return has(got, w.value({k: v for k, v in x.items() if k in got})), {k: got[k] for k in ("source_id", "mime", "locator_kind", "locator_value", "redistributable", "tier")}

def e_artifact_where(w, x, want):
    row = w.cx.execute("SELECT redistributable, manifest_json FROM artifact WHERE mime=?", (x["mime"],)).fetchone()
    got = {"redistributable": row["redistributable"], "manifest": json.loads(row["manifest_json"] or "{}")} if row else None
    return row is not None and has(got, x["is"]), got

def e_extractor(w, x, want):
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server
    row = w.cx.execute("SELECT x.kind, x.name, x.model_id, x.prompt_sha256 FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (w.value(x["extraction"]),)).fetchone()
    got = dict(row) if row else None
    if got and x.get("prompt") == "form": got["prompt_is_form"] = got["prompt_sha256"] == server.FORM_SHA256
    return row is not None and has(got, {k: v for k, v in x.items() if k in ("kind", "name", "model_id", "prompt_is_form")}), got

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
    from conclude import trusted_evidence
    m = x["membership"]; ids = [w.treelib.dumps([w.value(m["family"]), w.person(m["person"]), m["role"]])]
    v = bool(trusted_evidence(w.cx, w.tid, "family_member", ids, without=tuple(x.get("without", ()))))
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

def e_whole(w, x, want):
    v = whole(w.cx); return v is None, v

def e_file(w, x, want):
    path = os.path.join(w.value(x["folder"]) if x.get("folder") else w.treelib.inbox_dir(), w.value(x["name"]))
    return os.path.exists(path) == x.get("exists", True), path

def e_count(w, x, want):
    """A count from one of the catalog's tables, for a few plain questions: the rows of a table for a person."""
    q = {"persona_links_of": "SELECT COUNT(*) FROM person_persona WHERE person_id=?", "family_rows_of": "SELECT COUNT(*) FROM family_member WHERE person_id=?",
         "steps_of": "SELECT COUNT(*) FROM search_plan WHERE person_id=?", "personas_of": "SELECT COUNT(*) FROM persona WHERE artifact_sha256=?", "logs_of_step": "SELECT COUNT(*) FROM search_log WHERE plan_step_id=?",
         "events_of": "SELECT COUNT(*) FROM event_participant WHERE person_id=?"}
    kind = next(k for k in q if k in x)
    arg = w.sha(x[kind]) if kind == "personas_of" else w.step(x[kind])["id"] if kind == "logs_of_step" else w.person(x[kind])
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

def e_assertion_subject(w, x, want):
    v = w.cx.execute("SELECT subject_id FROM assertion WHERE persona_id=?", (w.value(x["persona"]),)).fetchone()
    return v is not None and v[0] == w.person(x["is"]), v and w.name_of(v[0])

EXPECTS = {"last": e_last, "bound": e_bound, "cards": e_cards, "card": e_card, "rule": e_rule, "facts": e_facts, "alias": e_alias, "linked": e_linked, "memberships": e_memberships, "persons": e_persons,
           "event": e_event, "disagreements": e_disagreements, "question": e_question, "assertions_on": e_assertions_on, "links": e_links, "is_subject": e_is_subject, "citations_held": e_citations_held,
           "checklist_row": e_checklist_row, "baseline": e_baseline, "step": e_step, "step_count": e_step_count, "fetch_entries": e_fetch_entries, "search_log": e_search_log, "named_for": e_named_for,
           "audit": e_audit, "hints": e_hints, "living": e_living, "mode": e_mode, "foundation": e_foundation, "results_page": e_results_page, "place_string": e_place_string, "artifact": e_artifact,
           "artifact_where": e_artifact_where, "extractor": e_extractor, "person_persona": e_person_persona, "reach": e_reach, "trusted": e_trusted, "plan_idempotent": e_plan_idempotent,
           "no_repeats": e_no_repeats, "whole": e_whole, "file": e_file, "count": e_count, "proposal_status": e_proposal_status, "proposals_of": e_proposals_of, "person_merged": e_person_merged,
           "find_person": e_find_person, "listed": e_listed, "assertion_subject": e_assertion_subject}

def load(folder):
    """Every scenario file under a folder, in name order."""
    for f in sorted(os.listdir(folder)):
        if f.endswith(".json"):
            with open(os.path.join(folder, f), encoding="utf-8") as fh: yield f, json.load(fh)

def check(folder, keep, show, only=None):
    """Every scenario under the folder walked on its own scratch; one line each; the number that failed."""
    bad = 0
    for f, spec in load(folder):
        if only and only not in f: continue
        try: fails = Walker(spec, keep, show).walk()
        except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
        title = spec.get("title", f)
        if fails: bad += 1; print(f"FAIL {title}: " + "; ".join(fails))
        else: print(f"ok   {title}: {spec.get('line', '')}")
    return bad
