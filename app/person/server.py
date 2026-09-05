#!/usr/bin/env python3
"""The person screen (docs/RESEARCH-CHECKLIST.md §6). Local only, stdlib only.

usage: app/person/server.py [--db catalog/tree.db] [--port 8765] [--by user:<you>]
then open http://127.0.0.1:8765/

One person per screen: foundation (key facts with Accept / Reject / Undecided),
footprint and checklist with the search step per gap, results for the row you
click. Deciding a fact sets the status of every assertion that supports it and
writes an audit row. Nothing here runs a search: the fetcher and the research
log are later work, so there is no Go button yet.
"""
import argparse, json, os, re, sqlite3, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from treelib import active_tree_slug, dumps, now, ulid
from catalog import Catalog
from checklist import build, MATCH

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

def fact_evidence(cx, pid, field):
    out = []
    for k, i in fact_subjects(cx, pid, field):
        for r in cx.execute("""SELECT a.id, a.citation_text, a.status, a.notes, a.artifact_sha256, ar.trust_tier FROM assertion a
                               LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 WHERE a.subject_kind=? AND a.subject_id=?""", (k, i)):
            n = json.loads(r["notes"]) if r["notes"] and r["notes"].startswith("{") else {}
            out.append({"id": r["id"], "citation": r["citation_text"], "status": r["status"], "apid": n.get("apid"),
                        "url": ancestry_url(n.get("apid")), "uncited": bool(n.get("uncited")), "tier": r["trust_tier"]})
    return out

def ancestry_url(apid):
    m = re.match(r"^\d+,(\d+)::(\d+)$", apid or "")
    return f"https://www.ancestry.com/discoveryui-content/view/{m.group(2)}:{m.group(1)}" if m else None

def decide_fact(cx, tree_id, pid, field, status, note):
    if field not in KEY_FACTS or status not in ("accepted", "rejected", "undecided"): return {"error": "bad field or status"}
    ts = now(); n = 0
    for k, i in fact_subjects(cx, pid, field):
        n += cx.execute("UPDATE assertion SET status=?, asserted_by=?, asserted_at=? WHERE subject_kind=? AND subject_id=? AND status<>?",
                        (status, CFG["by"], ts, k, i, status)).rowcount
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, CFG["by"], "accept" if status == "accepted" else ("reject" if status == "rejected" else "update"),
                "person", pid, dumps({"fact": field, "status": status, "assertions": n, "note": note or None})))
    if note:
        cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
                   (ulid(), tree_id, "person", pid, f"{field}: {status}. {note}", CFG["by"], ts))
    return {"ok": True, "field": field, "status": status, "assertions": n}

def row_pattern(row):
    """The collection-name pattern the checklist used for a row (mirrors tools/checklist.py MATCH)."""
    rec = row["record"]
    if rec == "census household" and row.get("instance"): return MATCH["census"](row["instance"])
    if rec.endswith("state census"): return MATCH["state_census"]("", row["instance"])
    for key, name in (("marriage", "marriage record"), ("church", "church register"), ("probate", "will / probate"), ("obituary", "obituary"), ("cemetery", "cemetery"),
                      ("passenger", "passenger"), ("pension", "pension"), ("deed", "land deed"), ("directory", "city directory"), ("compiled", "compiled"),
                      ("death_record", "death record"), ("birth_record", "birth record"), ("social_security", "Social Security"), ("naturalization", "naturalization"),
                      ("draft_ww1", "WWI"), ("draft_ww2", "WWII"), ("draft_civil", "Civil War"), ("military", "military service")):
        if rec.startswith(name) or name in rec: return MATCH[key]
    return None

# ------------------------------------------------------------------ views
def person_view(cx, tree_id, pid):
    cat = Catalog(cx, tree_id); r = build(cat, pid)
    r["review"] = {f: {"status": fact_status(cx, pid, f), "evidence": fact_evidence(cx, pid, f)} for f in KEY_FACTS}
    fam = cat.family(pid)
    r["family"] = {k: [{"id": i, "name": n} for i, n in fam[k]] for k in ("parents", "spouses", "children", "siblings")}
    # citations behind each checklist row (own first, then relatives'), with fetch links for Ancestry records
    rels = [(rel["name"], rel["id"]) for k in ("spouses", "children", "parents", "siblings") for rel in r["family"][k]]
    cites = [(None, c) for c in cat.person_citations(pid)] + [(n, c) for n, rid in rels for c in cat.person_citations(rid)]
    for grp in ("A", "B"):
        for row in r["checklist"][grp]:
            row["citations"] = []
            if row["status"] not in ("cited", "held"): continue
            pat = row_pattern(row)
            seen = set()
            for who, (cname, apid, held) in cites:
                if pat and cname and re.search(pat, cname, re.I) and (who is None or row.get("via") == who) and (cname, apid, who) not in seen:
                    seen.add((cname, apid, who)); row["citations"].append({"collection": cname, "apid": apid, "on": who, "url": ancestry_url(apid), "held": held})
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
            m = re.match(r"^/api/person/([A-Z0-9]+)$", u.path)
            if m:
                if not cx.execute("SELECT 1 FROM person WHERE id=? AND tree_id=?", (m.group(1), tree_id)).fetchone(): self.send({"error": "not found"}, code=404); return
                self.send(person_view(cx, tree_id, m.group(1))); return
            self.send({"error": "not found"}, code=404)
        finally: cx.close()
    def do_POST(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        m = re.match(r"^/api/person/([A-Z0-9]+)/fact/([a-z]+)$", u.path)
        if not m: self.send({"error": "not found"}, code=404); return
        with LOCK:
            cx = db()
            try:
                tree_id, slug, _ = tree_of(cx, q.get("tree", [None])[0])
                if not cx.execute("SELECT 1 FROM person WHERE id=? AND tree_id=?", (m.group(1), tree_id)).fetchone(): self.send({"error": "not found"}, code=404); return
                cx.execute("BEGIN"); res = decide_fact(cx, tree_id, m.group(1), m.group(2), body.get("status"), body.get("note"))
                if res.get("error"): cx.rollback(); self.send(res, code=400)
                else:
                    cx.commit(); res["review"] = {f: fact_status(cx, m.group(1), f) for f in KEY_FACTS}; self.send(res)
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
