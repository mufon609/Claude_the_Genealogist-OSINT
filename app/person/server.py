#!/usr/bin/env python3
"""The person screen (docs/RESEARCH-CHECKLIST.md §6). Local only, stdlib only.

usage: app/person/server.py [--db catalog/tree.db] [--port 8765] [--by user:<you>]
then open http://127.0.0.1:8765/

One person per screen: foundation (key facts with Accept / Reject / Undecided),
footprint and checklist with the search step per gap, results for the row you
click. Deciding a fact sets the status of the assertions behind it and writes
an audit row. A plan step can be logged (nothing found, blocked, found with a
file from inbox/) and its fields included or revised for the search; every run
is written to search_log with the fields as rendered. Nothing here runs a
search against a source: automatic connectors do not exist yet, so there is no
Go button.
"""
import argparse, glob, json, mimetypes, os, re, shutil, sqlite3, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from treelib import active_tree_slug, dumps, manifest_path, now, object_path, sha256_file, tree_dir, ulid
from catalog import Catalog
from checklist import build
from plan import plan_person
from log_search import dismiss as dismiss_question, log as log_search, rendered_query

LOCK = threading.Lock()
CFG = {"db": None, "by": "user:unknown"}
KEY_FACTS = ("name", "sex", "birth", "death", "parents", "spouses", "children")

def db():
    cx = sqlite3.connect(CFG["db"]); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row; return cx

def tree_of(cx, slug=None):
    slug = slug or active_tree_slug()
    r = cx.execute("SELECT id, slug, name FROM tree WHERE slug=?", (slug,)).fetchone()
    return (r["id"], r["slug"], r["name"]) if r else (None, None, None)

# ------------------------------------------------------------------ what supports a key fact
def fact_subjects(cx, pid, field):
    """(subject_kind, subject_id) rows whose assertions carry this key fact."""
    if field in ("name", "sex"): return [("person", pid)]          # identity facts share the person-level citations
    if field in ("birth", "death"):
        return [("event", r[0]) for r in cx.execute("""SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                      WHERE ep.person_id=? AND e.event_type=?""", (pid, field.title()))]
    if field == "children":
        return [("family_member", dumps([f, c, "child"])) for f, in cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (pid,))
                for c, in cx.execute("SELECT person_id FROM family_member WHERE family_id=? AND role='child'", (f,))]
    role = "child" if field == "parents" else "partner"
    return [("family_member", dumps([r[0], pid, role])) for r in cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role=?", (pid, role))]

def fact_status(cx, pid, field):
    subs = fact_subjects(cx, pid, field)
    if not subs: return None
    sts = set()
    for k, i in subs:
        sts |= {r[0] for r in cx.execute("SELECT status FROM assertion WHERE subject_kind=? AND subject_id=?", (k, i))}
    if "accepted" in sts: return "accepted"
    if sts and sts <= {"rejected"}: return "rejected"
    return "undecided"

def evidence_rows(cx, pid, field):
    held_apids = {v for v, in cx.execute("SELECT locator_value FROM artifact WHERE locator_kind='apid'")}
    out = []
    for k, i in fact_subjects(cx, pid, field):
        for r in cx.execute("""SELECT a.id, a.citation_text, a.status, a.notes, a.artifact_sha256, ar.trust_tier FROM assertion a
                               LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 WHERE a.subject_kind=? AND a.subject_id=?""", (k, i)):
            n = json.loads(r["notes"]) if r["notes"] and r["notes"].startswith("{") else {}
            apid = n.get("apid"); uncited = bool(n.get("uncited"))
            held = uncited or (apid in held_apids) or (r["trust_tier"] in ("T1", "T2", "T3"))   # the evidence the person can see
            out.append({"id": r["id"], "citation": r["citation_text"], "status": r["status"], "apid": apid,
                        "url": ancestry_url(apid), "uncited": uncited, "tier": r["trust_tier"], "held": held})
    return out

def ancestry_url(apid):
    m = re.match(r"^\d+,(\d+)::(\d+)$", apid or "")
    return f"https://www.ancestry.com/discoveryui-content/view/{m.group(2)}:{m.group(1)}" if m else None

def decide_fact(cx, tree_id, pid, field, status, note):
    """Accept touches only assertions whose evidence is visible (the tree owner's uncited claim, records that are held);
    a citation to a record not yet fetched stays Undecided. Reject and Undecided apply to every assertion behind the fact."""
    if field not in KEY_FACTS or status not in ("accepted", "rejected", "undecided"): return {"error": "bad field or status"}
    ts = now(); n = 0
    ids = [e["id"] for e in evidence_rows(cx, pid, field) if status != "accepted" or e["held"]]
    for aid in ids:
        n += cx.execute("UPDATE assertion SET status=?, asserted_by=?, asserted_at=? WHERE id=? AND status<>?", (status, CFG["by"], ts, aid, status)).rowcount
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, CFG["by"], "accept" if status == "accepted" else ("reject" if status == "rejected" else "update"),
                "person", pid, dumps({"fact": field, "status": status, "assertions": n, "note": note or None})))
    if note:
        cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
                   (ulid(), tree_id, "person", pid, f"{field}: {status}. {note}", CFG["by"], ts))
    return {"ok": True, "field": field, "status": status, "assertions": n}

# ------------------------------------------------------------------ views
def plan_view(cx, pid):
    """The person's open fact-level questions and every step, each with its log and its fields as rendered."""
    questions = [{"id": q["id"], "kind": q["kind"], "detail": json.loads(q["detail_json"] or "{}"),
                  "steps": cx.execute("SELECT COUNT(*) FROM search_plan WHERE question_id=?", (q["id"],)).fetchone()[0]}
                 for q in cx.execute("SELECT id, kind, detail_json FROM research_question WHERE subject_person_id=? AND status='open' ORDER BY kind", (pid,))]
    steps = []
    for s in cx.execute("SELECT * FROM search_plan WHERE person_id=? ORDER BY seq", (pid,)):
        logs = [dict(l) for l in cx.execute("SELECT id, executed_at, executed_by, outcome, notes, artifacts_json FROM search_log WHERE plan_step_id=? ORDER BY executed_at", (s["id"],))]
        col = cx.execute("SELECT name FROM collection WHERE id=?", (s["collection_id"],)).fetchone() if s["collection_id"] else None
        steps.append({"id": s["id"], "seq": s["seq"], "row_key": s["row_key"], "question_id": s["question_id"], "kind": s["kind"], "type": s["query_type"], "status": s["status"],
                      "mode": s["mode"], "sources": json.loads(s["sources_json"]), "fields": json.loads(s["query_json"]), "revisions": json.loads(s["revisions_json"] or "{}"),
                      "query": rendered_query(s["query_json"], s["revisions_json"]), "locator": {"source": s["locator_source_id"], "kind": s["locator_kind"], "value": s["locator_value"]},
                      "collection": col["name"] if col else None, "on": json.loads(s["on_json"] or "[]"), "url": ancestry_url(s["locator_value"]) if s["locator_kind"] == "apid" else None,
                      "expected": s["expected"], "rationale": s["rationale"], "logs": logs})
    return {"questions": questions, "steps": steps}

def source_row(cx, sid):
    r = cx.execute("SELECT id, trust_tier, terms, cost FROM source WHERE id=?", (sid,)).fetchone() if sid else None
    return dict(r) if r else {}

def cost_of(text):
    t = (text or "").strip().lower()
    return next((c for c in ("free", "paid", "member") if t.startswith(c)), "unknown")

def archive_inbox_file(cx, slug, name, st, note):
    """Archive a file the person saved to inbox/ for a step. Bytes already in the archive are linked, not copied.
    Provenance comes from the registry: the record's kind (the step's first source) gives the trust tier; where it was
    retrieved (the step's locator source) gives terms and cost. Returns the sha256."""
    src = os.path.join(ROOT, "inbox", os.path.basename(name))
    if not os.path.isfile(src): raise ValueError("file not in inbox")
    sha = sha256_file(src); ts = now()
    filed = os.path.join(tree_dir(slug), "imports", "records"); os.makedirs(filed, exist_ok=True)
    if cx.execute("SELECT 1 FROM artifact WHERE sha256=?", (sha,)).fetchone():
        shutil.move(src, os.path.join(filed, f"{ts[:10]}_{re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.basename(src))}"))
        return sha
    size = os.path.getsize(src); mime = mimetypes.guess_type(src)[0] or "application/octet-stream"
    source_id, lkind, lvalue, col_id = st["locator_source_id"], st["locator_kind"] or "file", st["locator_value"], st["collection_id"]
    col = cx.execute("SELECT name FROM collection WHERE id=?", (col_id,)).fetchone() if col_id else None; col_name = col["name"] if col else None
    sources = json.loads(st["sources_json"])
    kind_row = source_row(cx, sources[0] if sources else None); from_row = source_row(cx, source_id) or kind_row
    tier = kind_row.get("trust_tier") or from_row.get("trust_tier"); terms = from_row.get("terms") or "unknown"; cost = cost_of(from_row.get("cost"))
    manifest = {"schema_version": "0.1.0", "sha256": sha, "bytes": size, "mime": mime, "source_id": source_id or (sources[0] if sources else None), "collection": col_name,
                "locator": {"kind": lkind, "value": lvalue or os.path.basename(src)}, "retrieved_at": ts, "retrieved_by": CFG["by"],
                "rights": {"terms": terms, "redistributable": False, "cost": cost}, "trust_tier": tier, "original_filename": os.path.basename(src), "pages": 1, "notes": note or ""}
    manifest = {k: v for k, v in manifest.items() if v is not None}
    dst, man = object_path(sha), manifest_path(sha)
    os.makedirs(os.path.dirname(dst), exist_ok=True); os.makedirs(os.path.dirname(man), exist_ok=True)
    shutil.copyfile(src, dst); json.dump(manifest, open(man, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    cx.execute("""INSERT INTO artifact (sha256,byte_size,mime,source_id,collection_id,locator_kind,locator_value,retrieved_at,retrieved_by,terms,redistributable,cost,trust_tier,original_filename,page_count,manifest_json,created_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (sha, size, mime, manifest.get("source_id"), col_id, lkind, manifest["locator"]["value"], ts, CFG["by"], terms, False, cost, tier, os.path.basename(src), 1, dumps(manifest), ts))
    cx.execute("INSERT INTO artifact_copy (artifact_sha256,target_name,stored_at,last_verified,verify_ok) VALUES (?,?,?,?,?)", (sha, "local", ts, ts, True))
    shutil.move(src, os.path.join(filed, f"{ts[:10]}_{re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.basename(src))}"))
    return sha

def log_step(cx, tree_id, slug, step_id, body):
    """Write one run of a step. A found run with a file archives the file and records it on the log; the
    assertion and personas come later from extraction and review, never from the attach."""
    st = cx.execute("SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (step_id, tree_id)).fetchone()
    if not st: return {"error": "step not found"}
    outcome = body.get("outcome"); note = body.get("note") or None; query = body.get("query") or rendered_query(st["query_json"], st["revisions_json"])
    artifacts = []
    if outcome == "found" and body.get("file"):
        try: artifacts.append(archive_inbox_file(cx, slug, body["file"], st, note))
        except ValueError as e: return {"error": str(e)}
    lid = log_search(cx, tree_id, CFG["by"], step_id=step_id, outcome=outcome, artifacts=artifacts or None, note=note, query=query)
    return {"ok": True, "log": lid, "artifacts": artifacts}

def revise_step(cx, tree_id, step_id, body):
    """Store the person's include/revise for a step: {field: {"include": false} | {"value": "..."}}."""
    if not cx.execute("SELECT 1 FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (step_id, tree_id)).fetchone(): return {"error": "step not found"}
    rev = {k: v for k, v in (body.get("revisions") or {}).items() if isinstance(v, dict) and (v.get("include") is False or v.get("value") not in (None, ""))}
    cx.execute("UPDATE search_plan SET revisions_json=? WHERE id=?", (dumps(rev) if rev else None, step_id))
    return {"ok": True, "revisions": rev}

def person_view(cx, tree_id, pid):
    cat = Catalog(cx, tree_id); r = build(cat, pid); r["plan"] = plan_view(cx, pid)
    r["review"] = {f: {"status": fact_status(cx, pid, f), "evidence": evidence_rows(cx, pid, f)} for f in KEY_FACTS}
    fam = cat.family(pid)
    r["family"] = {k: [{"id": i, "name": n} for i, n in fam[k]] for k in ("parents", "spouses", "children", "siblings")}
    held = cat.held_apids()
    for row in r["checklist"]["A"] + r["checklist"]["B"]:
        for c in row["citations"]: c["url"] = ancestry_url(c["apid"]); c["held"] = c["apid"] in held
    for rec in r["footprint"]["records"]: rec["url"] = ancestry_url(rec.get("apid"))
    return r

def people(cx, tree_id, q=""):
    cat = Catalog(cx, tree_id); out = []
    for pid, name in cx.execute("SELECT id, display_name FROM person WHERE tree_id=? AND display_name LIKE ? ORDER BY display_name", (tree_id, f"%{q}%")):
        r = build(cat, pid)
        acc = sum(1 for f in KEY_FACTS if fact_status(cx, pid, f) == "accepted")
        out.append({"id": pid, "name": name, "span": r["person"]["span"], "accepted": acc, "key_facts": len(KEY_FACTS),
                    "gaps": sum(1 for x in r["checklist"]["A"] if x["status"] == "missing"), "to_fetch": sum(1 for x in r["checklist"]["A"] + r["checklist"]["B"] if x["status"] == "cited"),
                    "questions": len(r["questions"])})
    return out

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, body, ctype="application/json; charset=utf-8", code=200):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query); cx = db()
        try:
            if u.path == "/" or u.path.startswith("/person/"):
                self.send(open(os.path.join(os.path.dirname(__file__), "index.html"), "rb").read(), "text/html; charset=utf-8"); return
            tree_id, slug, tname = tree_of(cx, q.get("tree", [None])[0])
            if tree_id is None: self.send({"error": "no tree"}, code=400); return
            if u.path == "/api/tree": self.send({"slug": slug, "name": tname, "by": CFG["by"], "trees": [r["slug"] for r in cx.execute("SELECT slug FROM tree ORDER BY slug")]}); return
            if u.path == "/api/people": self.send(people(cx, tree_id, q.get("q", [""])[0])); return
            if u.path == "/api/inbox": self.send(sorted(os.path.basename(f) for f in glob.glob(os.path.join(ROOT, "inbox", "*")) if os.path.isfile(f) and not f.endswith(".gitkeep"))); return
            m = re.match(r"^/api/person/([A-Z0-9]+)$", u.path)
            if m:
                if not cx.execute("SELECT 1 FROM person WHERE id=? AND tree_id=?", (m.group(1), tree_id)).fetchone(): self.send({"error": "not found"}, code=404); return
                self.send(person_view(cx, tree_id, m.group(1))); return
            self.send({"error": "not found"}, code=404)
        finally: cx.close()
    def do_POST(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        mf = re.match(r"^/api/person/([A-Z0-9]+)/fact/([a-z]+)$", u.path); mp = re.match(r"^/api/person/([A-Z0-9]+)/plan$", u.path)
        ms = re.match(r"^/api/step/([A-Z0-9]+)/(log|revise)$", u.path); mq = re.match(r"^/api/question/([A-Z0-9]+)/dismiss$", u.path)
        if not (mf or mp or ms or mq): self.send({"error": "not found"}, code=404); return
        with LOCK:
            cx = db()
            try:
                tree_id, slug, _ = tree_of(cx, q.get("tree", [None])[0])
                pid = (mf or mp).group(1) if (mf or mp) else None
                if pid and not cx.execute("SELECT 1 FROM person WHERE id=? AND tree_id=?", (pid, tree_id)).fetchone(): self.send({"error": "not found"}, code=404); return
                cx.execute("BEGIN")
                if mf: res = decide_fact(cx, tree_id, pid, mf.group(2), body.get("status"), body.get("note"))
                elif mp: res = {"ok": True, **plan_person(cx, tree_id, pid, CFG["by"])}
                elif mq:
                    try: dismiss_question(cx, tree_id, CFG["by"], mq.group(1), body.get("note")); res = {"ok": True}
                    except SystemExit as e: res = {"error": str(e)}
                elif ms.group(2) == "log": res = log_step(cx, tree_id, slug, ms.group(1), body)
                else: res = revise_step(cx, tree_id, ms.group(1), body)
                if res.get("error"): cx.rollback(); self.send(res, code=400)
                else:
                    cx.commit()
                    if mf: res["review"] = {f: fact_status(cx, pid, f) for f in KEY_FACTS}
                    if mp: res["plan"] = plan_view(cx, pid)
                    self.send(res)
            except Exception as e: cx.rollback(); self.send({"error": repr(e)}, code=500)
            finally: cx.close()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    ap.add_argument("--port", type=int, default=8765); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args(); CFG["db"] = a.db; CFG["by"] = a.by
    print(f"person screen: http://127.0.0.1:{a.port}/   (db {os.path.relpath(a.db, ROOT)}, acting as {a.by})")
    try: ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
    except KeyboardInterrupt: pass

if __name__ == "__main__": main()
