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
from treelib import active_tree_slug, archive_object, dumps, imports_dir, inbox_dir, now, ulid
from catalog import Catalog, holders
from checklist import build
from plan import RegistryOutOfStep, plan_person
from log_search import dismiss as dismiss_question, log as log_search, rendered_query
from extract import Writer, extract as extract_html
from match import match as match_personas

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
            apid = n.get("apid"); uncited = bool(n.get("uncited")); vouched = bool(n.get("vouched"))
            held = uncited or vouched or (apid in held_apids) or (r["trust_tier"] in ("T1", "T2", "T3"))   # the evidence the person can see
            out.append({"id": r["id"], "citation": r["citation_text"], "status": r["status"], "apid": apid,
                        **fetch_target(apid, n.get("url")), "uncited": uncited, "vouched": vouched, "tier": r["trust_tier"], "held": held})
    return out

HOLDERS = holders()

def fetch_target(apid, url=None, fields=None):
    """Where a cited record is opened: {url, holder}. The citation's own memorial URL when the holder is Find a Grave; the free
    holder's own search prefilled from the step's fields (the citation's details, never the person's facts) when they are given,
    else its collection page; Ancestry's record page when no free holder is known (a membership is needed there)."""
    m = re.match(r"^\d+,(\d+)::(\d+)$", apid or "")
    if not m: return {"url": None, "holder": None}
    h = (HOLDERS.get(m.group(1)) or [None])[0]
    if h and h["HolderKind"] == "memorial" and url: return {"url": url, "holder": h["HolderCollection"]}
    if h and h["HolderKind"] != "memorial": return {"url": holder_search(h, fields) or h["URL"], "holder": h["HolderCollection"]}
    return {"url": f"https://www.ancestry.com/discoveryui-content/view/{m.group(2)}:{m.group(1)}", "holder": "Ancestry"}

def holder_search(h, fields):
    """The holder's own search URL from a fetch step's fields. FamilySearch: the collection search as the site itself builds it
    (f.collectionId, q.givenName, q.residenceDate.from/to and q.residencePlace from the citation's year and census place, q.surname).
    The National Archives 1950 site: its name search. None when the fields carry no name."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    name = (v("name") or "").split()
    if not name: return None
    if h["HolderKind"] == "fs_collection":
        q = [("f.collectionId", h["HolderKey"]), ("q.givenName", " ".join(name[:-1]) or name[0])]
        if v("year") and v("census place"): q += [("q.residenceDate.from", v("year")), ("q.residenceDate.to", v("year")), ("q.residencePlace", v("census place"))]
        q.append(("q.surname", name[-1]))
        return "https://www.familysearch.org/en/search/record/results?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    if h["HolderKey"] == "1950census.archives.gov": return "https://1950census.archives.gov/search/?" + urllib.parse.urlencode([("name", " ".join(name))], quote_via=urllib.parse.quote)
    return None

def vouch(cx, tree_id, pid, field, ts):
    """The person accepts a key fact on their own knowledge: one Accepted assertion per subject of the fact, by the person acting,
    on the tree file's persona for this person and the file itself, so the fact traces to the file as the archived claim and the
    acceptance to the person. Returns the assertion ids written (none when the person has no file persona)."""
    pe = cx.execute("""SELECT pe.id, pe.artifact_sha256 FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN artifact a ON a.sha256=pe.artifact_sha256
                       WHERE pp.person_id=? AND pp.status='accepted' AND a.mime='text/x-gedcom' ORDER BY pe.sequence LIMIT 1""", (pid,)).fetchone()
    if not pe: return []
    out = []
    for kind, sid in fact_subjects(cx, pid, field):
        if cx.execute("SELECT 1 FROM assertion WHERE subject_kind=? AND subject_id=? AND json_valid(notes) AND json_extract(notes,'$.vouched')=1", (kind, sid)).fetchone(): continue
        aid = ulid(); out.append(aid)
        cx.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                      VALUES (?,?,?,?,?,?,?,'accepted',?,?,?)""", (aid, tree_id, kind, sid, pe["id"], pe["artifact_sha256"], "Tree owner's own knowledge", CFG["by"], ts, dumps({"vouched": True})))
    return out

def decide_fact(cx, tree_id, pid, field, status, note):
    """Accept touches only assertions whose evidence is visible (the tree owner's uncited claim, records that are held);
    a citation to a record not yet fetched stays Undecided. When no assertion behind the fact has visible evidence, the accept
    is the person's own knowledge: a vouch (see vouch). Reject and Undecided apply to every assertion behind the fact.
    An accept regenerates the plan and marks the questions it closes answered by the proposal that brought the evidence."""
    if field not in KEY_FACTS or status not in ("accepted", "rejected", "undecided"): return {"error": "bad field or status"}
    ts = now(); n = 0; vouched = []
    ids = [e["id"] for e in evidence_rows(cx, pid, field) if status != "accepted" or e["held"]]
    for aid in ids:
        n += cx.execute("UPDATE assertion SET status=?, asserted_by=?, asserted_at=? WHERE id=? AND status<>?", (status, CFG["by"], ts, aid, status)).rowcount
    if status == "accepted" and not ids: vouched = vouch(cx, tree_id, pid, field, ts); ids = list(vouched); n += len(vouched)   # a vouch counts as an assertion accepted
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, CFG["by"], "accept" if status == "accepted" else ("reject" if status == "rejected" else "update"),
                "person", pid, dumps({"fact": field, "status": status, "assertions": n, "vouched": vouched, "note": note or None})))
    if note:
        cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
                   (ulid(), tree_id, "person", pid, f"{field}: {status}. {note}", CFG["by"], ts))
    answered = []
    if status == "accepted" and ids:                             # the proposal whose match brought the accepted evidence answers what the plan now closes
        props = [json.loads(r["notes"]).get("proposal") for r in cx.execute(f"SELECT notes FROM assertion WHERE id IN ({','.join('?'*len(ids))}) AND notes LIKE '{{%'", ids)]
        answered = answer_questions(cx, tree_id, pid, next((x for x in props if x), None))
    return {"ok": True, "field": field, "status": status, "assertions": n, "evidence": len(ids), "vouched": vouched, "answered": answered}   # evidence: the assertions the decision could act on

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
        held = cx.execute("SELECT sha256 FROM artifact WHERE locator_kind=? AND locator_value=?", (s["locator_kind"], s["locator_value"])).fetchone() if s["locator_value"] else None
        fields = json.loads(s["query_json"])
        steps.append({"id": s["id"], "seq": s["seq"], "row_key": s["row_key"], "question_id": s["question_id"], "kind": s["kind"], "type": s["query_type"], "status": s["status"], "archived": held["sha256"] if held else None,
                      "mode": s["mode"], "sources": json.loads(s["sources_json"]), "fields": fields, "revisions": json.loads(s["revisions_json"] or "{}"),
                      "query": rendered_query(s["query_json"], s["revisions_json"]), "locator": {"source": s["locator_source_id"], "kind": s["locator_kind"], "value": s["locator_value"]},
                      "collection": col["name"] if col else None, "on": json.loads(s["on_json"] or "[]"),
                      **(fetch_target(s["locator_value"], (fields.get("url") or {}).get("value"), fields) if s["locator_kind"] == "apid" else {"url": None, "holder": None}),
                      "expected": s["expected"], "rationale": s["rationale"], "logs": logs})
    return {"questions": questions, "steps": steps}

def source_row(cx, sid):
    r = cx.execute("SELECT id, trust_tier, terms, cost FROM source WHERE id=?", (sid,)).fetchone() if sid else None
    return dict(r) if r else {}

def cost_of(text):
    t = (text or "").strip().lower()
    return next((c for c in ("free", "paid", "member") if t.startswith(c)), "unknown")

def archive_inbox_file(cx, slug, name, st, note):
    """Archive a file the person saved to inbox/ for a step and file the original under the tree. Bytes already in the archive are
    linked, not copied. Provenance comes from the registry: the record's kind (the step's first source) gives the trust tier; where
    it was retrieved (the step's locator source) gives terms and cost. Returns (sha256, why the page was not parsed or None)."""
    src = os.path.join(inbox_dir(), os.path.basename(name))
    if not os.path.isfile(src): raise ValueError("file not in inbox")
    ts = now(); filed = os.path.join(imports_dir(slug), "records"); os.makedirs(filed, exist_ok=True)
    mime = mimetypes.guess_type(src)[0] or "application/octet-stream"
    source_id, lkind, lvalue, col_id = st["locator_source_id"], st["locator_kind"] or "file", st["locator_value"], st["collection_id"]
    col = cx.execute("SELECT name FROM collection WHERE id=?", (col_id,)).fetchone() if col_id else None
    sources = json.loads(st["sources_json"])
    kind_row = source_row(cx, sources[0] if sources else None); from_row = source_row(cx, source_id) or kind_row
    with open(src, "rb") as fh: data = fh.read()
    sha, new = archive_object(cx, data, mime=mime, source_id=source_id or (sources[0] if sources else None), collection_id=col_id, collection_name=col["name"] if col else None,
                              locator_kind=lkind, locator_value=lvalue or os.path.basename(src), retrieved_by=CFG["by"], terms=from_row.get("terms"), cost=cost_of(from_row.get("cost")),
                              trust_tier=kind_row.get("trust_tier") or from_row.get("trust_tier"), original_filename=os.path.basename(src), notes=note)
    unparsed = None
    if new and mime.startswith("text/html"):                      # a record page is parsed and matched on arrival; an image waits for a transcription
        eid, n = extract_html(cx, sha, CFG["by"])
        if "failed" in n: unparsed = n["failed"]
        else: match_personas(cx, eid, CFG["by"])
    shutil.move(src, os.path.join(filed, f"{ts[:10]}_{re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.basename(src))}"))
    return sha, unparsed

def log_step(cx, tree_id, slug, step_id, body):
    """Write one run of a step. A found run with a file archives the file and records it on the log; the
    assertion and personas come later from extraction and review, never from the attach."""
    st = cx.execute("SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (step_id, tree_id)).fetchone()
    if not st: return {"error": "step not found"}
    outcome = body.get("outcome"); note = body.get("note") or None; query = body.get("query") or rendered_query(st["query_json"], st["revisions_json"])
    artifacts, unparsed = [], None
    if outcome == "found" and body.get("file"):
        try: sha, unparsed = archive_inbox_file(cx, slug, body["file"], st, note); artifacts.append(sha)
        except ValueError as e: return {"error": str(e)}
    lid = log_search(cx, tree_id, CFG["by"], step_id=step_id, outcome=outcome, artifacts=artifacts or None, note=note, query=query)
    return {"ok": True, "log": lid, "artifacts": artifacts, "unparsed": unparsed}

def revise_step(cx, tree_id, step_id, body):
    """Store the person's include/revise for a step: {field: {"include": false} | {"value": "..."}}."""
    if not cx.execute("SELECT 1 FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (step_id, tree_id)).fetchone(): return {"error": "step not found"}
    rev = {k: v for k, v in (body.get("revisions") or {}).items() if isinstance(v, dict) and (v.get("include") is False or v.get("value") not in (None, ""))}
    cx.execute("UPDATE search_plan SET revisions_json=? WHERE id=?", (dumps(rev) if rev else None, step_id))
    return {"ok": True, "revisions": rev}

def artifact_view(cx, tree_id, sha, pid):
    """A held record as the person screen shows it: the file, every current extraction with its personas, facts and
    relations, how each persona stands to this person, and every proposal the matcher wrote on the record: a record cited on
    several relatives is fetched for all of them, and each proposal names the person it concerns."""
    a = cx.execute("SELECT sha256, mime, trust_tier, locator_kind, locator_value, original_filename, collection_id FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if not a: return None
    cited = Catalog(cx, tree_id).cited().get(a["locator_value"], {}) if a["locator_kind"] == "apid" else {}
    col = cx.execute("SELECT name FROM collection WHERE id=?", (a["collection_id"],)).fetchone() if a["collection_id"] else None
    exts = []
    for e in cx.execute("""SELECT e.id, e.ran_at, x.kind, x.name, x.version FROM extraction e JOIN extractor x ON x.id=e.extractor_id
                           WHERE e.artifact_sha256=? AND e.superseded_by IS NULL ORDER BY e.ran_at""", (sha,)):
        personas = []
        for p in cx.execute("SELECT id, name_text, sex, role_in_record FROM persona WHERE extraction_id=? ORDER BY sequence", (e["id"],)):
            facts = [{"type": f["fact_type"], "value": f["value_text"], "date": f["date_text"], "place": f["raw"]} for f in cx.execute(
                "SELECT pf.fact_type, pf.value_text, pf.date_text, ps.raw FROM persona_fact pf LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pf.persona_id=?", (p["id"],))]
            rels = [{"kind": r["kind"], "text": r["value_text"], "other": r["name_text"]} for r in cx.execute(
                "SELECT r.kind, r.value_text, o.name_text FROM persona_relation r JOIN persona o ON o.id=r.related_persona_id WHERE r.persona_id=?", (p["id"],))]
            link = cx.execute("SELECT status FROM person_persona WHERE persona_id=? AND person_id=?", (p["id"], pid)).fetchone()
            personas.append({"id": p["id"], "name": p["name_text"], "sex": p["sex"], "role": p["role_in_record"], "facts": facts, "relations": rels, "link": link["status"] if link else None})
        exts.append({"id": e["id"], "extractor": f"{e['kind']}:{e['name']}" + (f"@{e['version']}" if e["version"] else ""), "ran_at": e["ran_at"], "personas": personas})
    proposals = [{"id": r["id"], "kind": r["kind"], "status": r["status"], "rationale": r["rationale"], "persona_id": json.loads(r["payload_json"])["persona_id"],
                  "person_id": json.loads(r["payload_json"])["person_id"], "person": r["candidate"]}
                 for r in cx.execute("""SELECT p.id, p.kind, p.status, p.rationale, p.payload_json, c.display_name AS candidate FROM proposal p
                                        LEFT JOIN person c ON c.id=json_extract(p.payload_json,'$.person_id')
                                        WHERE p.tree_id=? AND json_extract(p.payload_json,'$.artifact_sha256')=? ORDER BY p.created_at""", (tree_id, sha))]
    return {"sha256": sha, "mime": a["mime"], "tier": a["trust_tier"], "filename": a["original_filename"], "collection": col["name"] if col else None,
            "url": fetch_target(a["locator_value"], cited.get("url"))["url"] if a["locator_kind"] == "apid" else None, "extractions": exts, "proposals": proposals,
            "personas_on_record": [{"id": p["id"], "name": p["name"]} for e in exts for p in e["personas"]]}

def transcribe(cx, sha, body):
    """One persona typed from a held record by the person acting: an extraction by extractor human:<user> on the
    artifact (created on the first persona), the persona, its facts, and its relations to personas already on the record."""
    if not cx.execute("SELECT 1 FROM artifact WHERE sha256=?", (sha,)).fetchone(): return {"error": "not in the archive"}
    name = (body.get("name") or "").strip()
    if not name: return {"error": "a name is required"}
    ts = now(); who = CFG["by"].split(":", 1)[-1]
    x = cx.execute("SELECT id FROM extractor WHERE kind='human' AND name=? AND version IS NULL", (who,)).fetchone()
    xid = x["id"] if x else ulid()
    if not x: cx.execute("INSERT INTO extractor (id,kind,name,created_at) VALUES (?,?,?,?)", (xid, "human", who, ts))
    e = cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND extractor_id=? AND superseded_by IS NULL", (sha, xid)).fetchone()
    eid = e["id"] if e else ulid()
    if not e: cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status) VALUES (?,?,?,?,'complete')", (eid, sha, xid, ts))
    seq = cx.execute("SELECT COUNT(*) FROM persona WHERE extraction_id=?", (eid,)).fetchone()[0] + 1
    w = Writer(cx, sha, eid)
    sex = body.get("sex") if body.get("sex") in ("M", "F") else None
    pid = w.persona(name, sex, (body.get("role") or "").strip().lower() or None, seq, {"label": "transcription"})
    w.fact(pid, "Name", name, labels=["name"])
    if sex: w.fact(pid, "Sex", body["sex"], labels=["sex"])
    if body.get("age"): w.fact(pid, "Age", body["age"].strip(), labels=["age"])
    for ftype, dk, pk in (("Birth", "birth_date", "birth_place"), ("Death", "death_date", "death_place")):
        if body.get(dk) or body.get(pk): w.fact(pid, ftype, None, (body.get(dk) or "").strip() or None, (body.get(pk) or "").strip() or None, [k for k in (dk, pk) if body.get(k)])
    if body.get("residence"): w.fact(pid, "Residence", None, None, body["residence"].strip(), ["residence"])
    for r in body.get("relations") or []:
        if r.get("persona_id") and cx.execute("SELECT 1 FROM persona WHERE id=? AND artifact_sha256=?", (r["persona_id"], sha)).fetchone():
            w.relation(pid, r["persona_id"], r.get("kind") or "other", (r.get("text") or "").strip() or None, "transcription")
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, CFG["by"], "insert", "persona", pid, dumps({"extraction": eid, **w.n})))
    match_personas(cx, eid, CFG["by"])
    return {"ok": True, "extraction": eid, "persona": pid}

ANSWERABLE = ("missing_parents", "unverified_claim", "missing_fact")

def answer_questions(cx, tree_id, pid, prop_id):
    """Regenerate the person's plan; a question of an answerable kind that the regeneration closes was answered by the
    proposal: closed_reason answered, answered_by_proposal_id set. Other kinds stay as the planner closed them."""
    st = plan_person(cx, tree_id, pid, CFG["by"]); answered = []
    for qid in st.get("closed", []):
        q = cx.execute("SELECT kind FROM research_question WHERE id=?", (qid,)).fetchone()
        if q and q["kind"] in ANSWERABLE:
            cx.execute("UPDATE research_question SET closed_reason='answered', answered_by_proposal_id=? WHERE id=?", (prop_id, qid)); answered.append(qid)
    return answered

def assert_facts(cx, tree_id, person_id, persona_id, prop_id, ts):
    """Undecided assertions from a persona's facts to the person: Name and Sex facts assert the person row; an event fact asserts
    the person's event of that type and year, created from the fact's date when there is none; a fact of type Unknown (kept under
    the page's own label) asserts nothing. Returns how many were written."""
    n = 0
    sha = cx.execute("SELECT artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()["artifact_sha256"]
    a = cx.execute("SELECT c.name, ar.original_filename FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id WHERE ar.sha256=?", (sha,)).fetchone()
    cite = a["name"] or a["original_filename"] or sha[:12]
    def assert_(kind, sid, fid):
        nonlocal n
        if cx.execute("SELECT 1 FROM assertion WHERE subject_kind=? AND subject_id=? AND persona_fact_id=?", (kind, sid, fid)).fetchone(): return
        cx.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                      VALUES (?,?,?,?,?,?,?,'undecided',?,?,?)""", (ulid(), tree_id, kind, sid, fid, sha, cite, CFG["by"], ts, dumps({"proposal": prop_id}))); n += 1
    for f in cx.execute("""SELECT pf.id, pf.fact_type, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.calendar, et.kind
                           FROM persona_fact pf JOIN event_type et ON et.name=pf.fact_type WHERE pf.persona_id=?""", (persona_id,)):
        if f["fact_type"] in ("Name", "Sex"): assert_("person", person_id, f["id"]); continue
        if f["kind"] != "event" or f["fact_type"] == "Unknown": continue      # a fact under the page's own label names no event of the person
        fy = (f["date_start"] or f["date_end"] or "")[:4]           # an event corresponds by type and year; an undated fact only to an undated event
        events = [e for e in cx.execute("""SELECT e.id, e.date_start, e.date_end FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                           WHERE ep.person_id=? AND e.event_type=?""", (person_id, f["fact_type"]))
                  if (e["date_start"] or e["date_end"] or "")[:4] == fy]
        if not events:
            eid = ulid()
            cx.execute("INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (eid, tree_id, f["fact_type"], f["date_text"], f["date_start"], f["date_end"], f["date_qualifier"], f["calendar"], ts, ts))
            cx.execute("INSERT INTO event_participant (id,event_id,person_id,role) VALUES (?,?,?,'primary')", (ulid(), eid, person_id))
            events = [{"id": eid}]
        for e in events: assert_("event", e["id"], f["id"])
    return n, sha

def create_person(cx, tree_id, persona_id, ts):
    """A person in this tree from a persona: the name as written split into given names and a surname; a maiden name the
    record marks becomes the birth surname and the written surname a married name. Returns the person id."""
    pe = cx.execute("SELECT name_text, sex, region_json FROM persona WHERE id=?", (persona_id,)).fetchone()
    region = json.loads(pe["region_json"] or "{}"); parts = (pe["name_text"] or "").split()
    given, surname = (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else (pe["name_text"], None)
    pid = ulid()
    cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)", (pid, tree_id, pe["sex"], pe["name_text"], ts, ts))
    if region.get("maiden") and surname and region["maiden"] != surname:
        g = given.replace(region["maiden"], "").strip()
        cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (ulid(), pid, g, region["maiden"], f"{region['maiden']}, {g}".lower()))
        cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'married',?,?,0,?)", (ulid(), pid, g, surname, f"{surname}, {g}".lower()))
    else:
        cx.execute("INSERT INTO person_name (id,person_id,name_type,given,surname,is_primary,sort_key) VALUES (?,?,'birth',?,?,1,?)", (ulid(), pid, given, surname, f"{surname or ''}, {given}".lower()))
    return pid

def place_in_family(cx, tree_id, pid, persona_id, sha, prop_id, ts):
    """Family membership for a new person from the record's own relations: where the persona is the child, parent or spouse of a
    persona whose match is accepted, the new person joins that person's family (created when the person has none of the right
    shape), each membership with an Undecided assertion on the artifact. Returns the memberships written."""
    out = []
    for r in cx.execute("""SELECT r.kind, r.value_text, pp.person_id AS other FROM persona_relation r
                           JOIN person_persona pp ON pp.persona_id=r.related_persona_id AND pp.status='accepted'
                           JOIN person o ON o.id=pp.person_id AND o.tree_id=? WHERE r.persona_id=? AND r.kind IN ('child','parent','spouse')""", (tree_id, persona_id)):
        other = r["other"]
        if r["kind"] == "child":     # the new person is a child of the other: the other's family as partner
            fid = next((f["family_id"] for f in cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", (other,))), None); role = "child"
            if fid is None: fid = new_family(cx, tree_id, other, ts)
        elif r["kind"] == "parent":  # the new person is a parent of the other: the family the other is a child of
            fid = next((f["family_id"] for f in cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='child'", (other,))), None); role = "partner"
            if fid is None: fid = ulid(); cx.execute("INSERT INTO family (id,tree_id,created_at,updated_at) VALUES (?,?,?,?)", (fid, tree_id, ts, ts)); cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'child')", (fid, other))
        else:                        # spouse: a family of the other with room for a second partner, else a new one
            fid = next((f["family_id"] for f in cx.execute("""SELECT fm.family_id FROM family_member fm WHERE fm.person_id=? AND fm.role='partner'
                        AND (SELECT COUNT(*) FROM family_member x WHERE x.family_id=fm.family_id AND x.role='partner')=1""", (other,))), None); role = "partner"
            if fid is None: fid = new_family(cx, tree_id, other, ts)
        if cx.execute("SELECT 1 FROM family_member WHERE family_id=? AND person_id=? AND role=?", (fid, pid, role)).fetchone(): continue
        cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,?)", (fid, pid, role))
        cx.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                      VALUES (?,?,'family_member',?,?,?,?,'undecided',?,?,?)""",
                   (ulid(), tree_id, dumps([fid, pid, role]), persona_id, sha, f"{r['value_text'] or r['kind']} on the record", CFG["by"], ts, dumps({"proposal": prop_id})))
        out.append({"family": fid, "role": role, "of": other, "as": r["value_text"] or r["kind"]})
    return out

def new_family(cx, tree_id, partner, ts):
    fid = ulid(); cx.execute("INSERT INTO family (id,tree_id,created_at,updated_at) VALUES (?,?,?,?)", (fid, tree_id, ts, ts))
    cx.execute("INSERT INTO family_member (family_id,person_id,role) VALUES (?,?,'partner')", (fid, partner)); return fid

def decide_proposal(cx, tree_id, prop_id, status):
    """A person decides a proposal. A persona match accepted: person_persona accepted and Undecided assertions from the persona's
    facts (assert_facts). A new person accepted: the person is created in this tree, the persona link accepted, the same
    assertions, and the family memberships the record's relations give (place_in_family). Rejected: the link rejected for a
    match, nothing but the proposal for a new person. An accept then regenerates the plans of the person concerned and of the
    person the record was fetched for, and the questions that regeneration closes are marked answered by this proposal. The
    fact decision on the screen stays the only way to Accept a fact."""
    p = cx.execute("SELECT * FROM proposal WHERE id=? AND tree_id=?", (prop_id, tree_id)).fetchone()
    if not p or p["kind"] not in ("persona_match", "new_person") or status not in ("accepted", "rejected"): return {"error": "not a persona match or new person, or bad status"}
    if p["status"] != "undecided": return {"error": "already decided"}
    pay = json.loads(p["payload_json"]); persona_id, person_id = pay["persona_id"], pay.get("person_id"); ts = now(); n = 0; members = []
    cx.execute("UPDATE proposal SET status=?, decided_by=?, decided_at=? WHERE id=?", (status, CFG["by"], ts, prop_id))
    if p["kind"] == "new_person" and status == "accepted": person_id = create_person(cx, tree_id, persona_id, ts)
    if person_id:
        cx.execute("INSERT OR REPLACE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (person_id, persona_id, status, prop_id, CFG["by"], ts))
    answered = []
    if status == "accepted":
        n, sha = assert_facts(cx, tree_id, person_id, persona_id, prop_id, ts)
        if p["kind"] == "new_person": members = place_in_family(cx, tree_id, person_id, persona_id, sha, prop_id, ts)
        for pid in dict.fromkeys([person_id, pay.get("subject_person_id")]):
            if pid: answered += answer_questions(cx, tree_id, pid, prop_id)
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, CFG["by"], "accept" if status == "accepted" else "reject", "proposal", prop_id,
                dumps({"kind": p["kind"], "persona": persona_id, "person": person_id, "assertions": n, "memberships": members, "answered": answered})))
    return {"ok": True, "status": status, "person": person_id, "assertions": n, "memberships": members, "answered": answered}

def person_view(cx, tree_id, pid):
    cat = Catalog(cx, tree_id); r = build(cat, pid); r["plan"] = plan_view(cx, pid)
    r["review"] = {f: {"status": fact_status(cx, pid, f), "evidence": evidence_rows(cx, pid, f)} for f in KEY_FACTS}
    fam = cat.family(pid)
    r["family"] = {k: [{"id": i, "name": n} for i, n in fam[k]] for k in ("parents", "spouses", "children", "siblings")}
    held = cat.held_apids(); cited = cat.cited()
    for row in r["checklist"]["A"] + r["checklist"]["B"]:
        for c in row["citations"]: c.update(fetch_target(c["apid"], cited.get(c["apid"], {}).get("url"))); c["held"] = c["apid"] in held
    for rec in r["footprint"]["records"]: rec.update(fetch_target(rec.get("apid"), cited.get(rec.get("apid"), {}).get("url")))
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
            if u.path == "/api/inbox": self.send(sorted(os.path.basename(f) for f in glob.glob(os.path.join(inbox_dir(), "*")) if os.path.isfile(f) and not f.endswith(".gitkeep"))); return
            ma = re.match(r"^/api/artifact/([0-9a-f]{64})$", u.path)
            if ma:
                v = artifact_view(cx, tree_id, ma.group(1), q.get("person", [""])[0])
                self.send(v if v else {"error": "not found"}, code=200 if v else 404); return
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
        mt = re.match(r"^/api/artifact/([0-9a-f]{64})/persona$", u.path); md = re.match(r"^/api/proposal/([A-Z0-9]+)/decide$", u.path)
        if not (mf or mp or ms or mq or mt or md): self.send({"error": "not found"}, code=404); return
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
                elif mt: res = transcribe(cx, mt.group(1), body)
                elif md: res = decide_proposal(cx, tree_id, md.group(1), body.get("status"))
                elif ms.group(2) == "log": res = log_step(cx, tree_id, slug, ms.group(1), body)
                else: res = revise_step(cx, tree_id, ms.group(1), body)
                if res.get("error"): cx.rollback(); self.send(res, code=400)
                else:
                    cx.commit()
                    if mf: res["review"] = {f: fact_status(cx, pid, f) for f in KEY_FACTS}
                    if mp: res["plan"] = plan_view(cx, pid)
                    self.send(res)
            except RegistryOutOfStep as e: cx.rollback(); self.send({"error": str(e)}, code=400)   # the plan regeneration inside a decision found the registry out of step
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
