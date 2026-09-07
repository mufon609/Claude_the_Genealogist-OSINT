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
import argparse, glob, json, mimetypes, os, re, sqlite3, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from treelib import active_tree_slug, dumps, inbox_dir, now, ulid
from catalog import Catalog, fetch_target, held_apids, search_target
from checklist import build
from plan import RegistryOutOfStep, plan_person
from log_search import dismiss as dismiss_question, log as log_search, rendered_query
from extract import Writer
from attach import attach as attach_file, identity as attach_identity, steps_for as attach_steps_for
from cards import card as decision_card, render as render_card, render_search, search_card, search_cards_for
from conclude import decide as decide_document, match_record, record_says

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
    if field.startswith("event:"):                                    # any other event or attribute of the person, by id
        return [("event", r[0]) for r in cx.execute("SELECT event_id FROM event_participant WHERE person_id=? AND event_id=?", (pid, field[6:]))]
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
    held = held_apids(cx)
    out = []
    for k, i in fact_subjects(cx, pid, field):
        for r in cx.execute("""SELECT a.id, a.citation_text, a.status, a.notes, a.artifact_sha256, ar.trust_tier FROM assertion a
                               LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 WHERE a.subject_kind=? AND a.subject_id=?""", (k, i)):
            n = json.loads(r["notes"]) if r["notes"] and r["notes"].startswith("{") else {}
            apid = n.get("apid"); uncited = bool(n.get("uncited")); vouched = bool(n.get("vouched"))
            visible = uncited or vouched or (apid in held) or (r["trust_tier"] in ("T1", "T2", "T3"))   # the evidence the person can see
            ident = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in cx.execute("SELECT kind, value FROM artifact_locator WHERE artifact_sha256=? ORDER BY kind", (r["artifact_sha256"],))) if r["artifact_sha256"] else ""
            if not ident and r["artifact_sha256"]:
                loc = cx.execute("SELECT locator_value, manifest_json FROM artifact WHERE sha256=?", (r["artifact_sha256"],)).fetchone()
                m = re.search(r"scheduleId\W+(\d+)", (loc["locator_value"] or "") + " " + (loc["manifest_json"] or "")) if loc else None
                ident = f"schedule {m.group(1)}" if m else ""
            out.append({"id": r["id"], "citation": r["citation_text"], "status": r["status"], "apid": apid, "sha256": r["artifact_sha256"], "ident": ident,
                        **fetch_target(apid, n.get("url")), "uncited": uncited, "vouched": vouched, "tier": r["trust_tier"], "held": visible})
    return out

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
    if (field not in KEY_FACTS and not (field.startswith("event:") and fact_subjects(cx, pid, field))) or status not in ("accepted", "rejected", "undecided"): return {"error": "bad field or status"}
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
    steps = []; archived = held_apids(cx)
    for s in cx.execute("SELECT * FROM search_plan WHERE person_id=? ORDER BY seq", (pid,)):
        logs = [dict(l) for l in cx.execute("SELECT id, executed_at, executed_by, outcome, notes, artifacts_json FROM search_log WHERE plan_step_id=? ORDER BY executed_at", (s["id"],))]
        col = cx.execute("SELECT name FROM collection WHERE id=?", (s["collection_id"],)).fetchone() if s["collection_id"] else None
        if s["locator_kind"] == "apid": sha = archived.get(s["locator_value"])
        else: a = cx.execute("SELECT sha256 FROM artifact WHERE locator_kind=? AND locator_value=?", (s["locator_kind"], s["locator_value"])).fetchone() if s["locator_value"] else None; sha = a["sha256"] if a else None
        fields = json.loads(s["query_json"])
        steps.append({"id": s["id"], "seq": s["seq"], "row_key": s["row_key"], "question_id": s["question_id"], "kind": s["kind"], "type": s["query_type"], "status": s["status"], "archived": sha,
                      "mode": s["mode"], "sources": json.loads(s["sources_json"]), "fields": fields, "revisions": json.loads(s["revisions_json"] or "{}"),
                      "query": rendered_query(s["query_json"], s["revisions_json"]), "locator": {"source": s["locator_source_id"], "kind": s["locator_kind"], "value": s["locator_value"]},
                      "collection": col["name"] if col else None, "on": json.loads(s["on_json"] or "[]"),
                      **(fetch_target(s["locator_value"], (fields.get("url") or {}).get("value"), fields) if s["locator_kind"] == "apid"
                         else search_target(json.loads(s["sources_json"]), rendered_query(s["query_json"], s["revisions_json"])) if s["kind"] == "search" else {"url": None, "holder": None}),
                      "expected": s["expected"], "rationale": s["rationale"], "logs": logs})
    return {"questions": questions, "steps": steps}

def log_step(cx, tree_id, slug, step_id, body):
    """Write one run of a step. A found run with a file attaches the file (tools/attach.py): archived once, a found run logged
    on the step the person chose and on every other step the record's own identity fulfils, then a record page new to the
    archive is parsed and matched; the assertion and personas come later from extraction and review, never from the attach."""
    st = cx.execute("SELECT sp.* FROM search_plan sp JOIN person p ON p.id=sp.person_id WHERE sp.id=? AND p.tree_id=?", (step_id, tree_id)).fetchone()
    if not st: return {"error": "step not found"}
    outcome = body.get("outcome"); note = body.get("note") or None; query = body.get("query") or rendered_query(st["query_json"], st["revisions_json"])
    if outcome == "found" and body.get("file"):
        path = os.path.join(inbox_dir(), os.path.basename(body["file"]))
        if not os.path.isfile(path): return {"error": "file not in inbox"}
        kind, value, parsed = (None, None, None)
        if (mimetypes.guess_type(path)[0] or "").startswith("text/html"):
            with open(path, "rb") as fh: kind, value, parsed = attach_identity(fh.read().decode("utf-8", errors="replace"))
        steps = [st] + [s for s in (attach_steps_for(cx, tree_id, kind, value, parsed) if kind else []) if s["id"] != st["id"]]
        try: r = attach_file(cx, tree_id, slug, body["file"], steps, CFG["by"], note=note, query=query if kind != "search" else None, kind=kind, value=value, parsed=parsed)
        except ValueError as e: return {"error": str(e)}
        return {"ok": True, "log": r["logs"][0][1] if r["logs"] else None, "artifacts": [r["sha256"]], "unparsed": r["unparsed"], "identity": f"{kind} {value}" if kind else None,
                "steps": [s["id"] for s in steps], "proposals": len(r["proposals"])}
    lid = log_search(cx, tree_id, CFG["by"], step_id=step_id, outcome=outcome, artifacts=None, note=note, query=query)
    return {"ok": True, "log": lid, "artifacts": [], "unparsed": None}

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
    proposals = []
    for r in cx.execute("""SELECT p.id, p.kind, p.status, p.rationale, p.payload_json, p.decided_by, p.decision_note, c.display_name AS candidate FROM proposal p
                           LEFT JOIN person c ON c.id=json_extract(p.payload_json,'$.person_id')
                           WHERE p.tree_id=? AND json_extract(p.payload_json,'$.artifact_sha256')=? ORDER BY p.created_at""", (tree_id, sha)):
        c = decision_card(cx, tree_id, r["id"]) if r["kind"] in ("persona_match", "new_person") else None      # the same card the cards tool prints
        proposals.append({"id": r["id"], "kind": r["kind"], "status": r["status"], "rationale": r["rationale"], "persona_id": json.loads(r["payload_json"])["persona_id"],
                          "person_id": json.loads(r["payload_json"])["person_id"], "person": r["candidate"], "card": c, "card_text": render_card(c) if c else None,
                          "by_rule": (r["decided_by"] or "").startswith("rule:"), "note": r["decision_note"]})
    sc = search_card(cx, tree_id, sha, pid or None) if any(e["extractor"] == "rule:findagrave-search@0.1.0" for e in exts) else None   # a results page shows its candidate card
    return {"sha256": sha, "mime": a["mime"], "tier": a["trust_tier"], "filename": a["original_filename"], "collection": col["name"] if col else None,
            "url": fetch_target(a["locator_value"], cited.get("url"))["url"] if a["locator_kind"] == "apid" else a["locator_value"] if a["locator_kind"] == "url" else None,
            "candidates": sc, "candidates_text": render_search(sc) if sc else None, "extractions": exts, "proposals": proposals,
            "personas_on_record": [{"id": p["id"], "name": p["name"]} for e in exts for p in e["personas"]]}

def transcribe(cx, sha, body, by=None):
    """One persona read from a held record, by the person acting (extractor human:<user>) or by a model reading the image
    (extractor llm:<model>, docs/DATA-ARCHITECTURE.md §1): an extraction on the artifact (created on the first persona), the
    persona in the record's own role word, its facts as written, a birth calculated from an age and the record's year, and its
    relations to personas already on the record."""
    if not cx.execute("SELECT 1 FROM artifact WHERE sha256=?", (sha,)).fetchone(): return {"error": "not in the archive"}
    name = (body.get("name") or "").strip()
    if not name: return {"error": "a name is required"}
    ts = now(); kind, who = ((by or CFG["by"]).split(":", 1) + [None])[:2]; kind = "llm" if kind in ("llm", "model") else "human"
    x = cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version IS NULL", (kind, who)).fetchone()
    xid = x["id"] if x else ulid()
    if not x: cx.execute("INSERT INTO extractor (id,kind,name,created_at) VALUES (?,?,?,?)", (xid, kind, who, ts))
    e = cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND extractor_id=? AND superseded_by IS NULL", (sha, xid)).fetchone()
    eid = e["id"] if e else ulid()
    if not e: cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status,structured_json) VALUES (?,?,?,?,'complete',?)", (eid, sha, xid, ts, dumps({"read": "the page image, one person per row" if kind == "llm" else "typed by hand", "year": body.get("year")})))
    seq = cx.execute("SELECT COUNT(*) FROM persona WHERE extraction_id=?", (eid,)).fetchone()[0] + 1
    w = Writer(cx, sha, eid)
    sex = body.get("sex") if body.get("sex") in ("M", "F") else None
    pid = w.persona(name, sex, (body.get("role") or "").strip().lower() or None, seq, {"label": "transcription", "line": body.get("line")})
    w.fact(pid, "Name", name, labels=["name"])
    if sex: w.fact(pid, "Sex", body["sex"], labels=["sex"])
    if body.get("age"): w.fact(pid, "Age", str(body["age"]).strip(), labels=["age"])
    bdate = (body.get("birth_date") or "").strip() or None
    if not bdate and body.get("age") and body.get("year") and str(body["age"]).strip().isdigit(): bdate = f"CAL {int(body['year']) - int(str(body['age']).strip())}"   # from the age on the record's date
    for ftype, dk, pk in (("Birth", "birth_date", "birth_place"), ("Death", "death_date", "death_place")):
        d = bdate if ftype == "Birth" else (body.get(dk) or "").strip() or None
        if d or body.get(pk): w.fact(pid, ftype, None, d, (body.get(pk) or "").strip() or None, [k for k in (dk if d else None, pk if body.get(pk) else None) if k] + (["age"] if ftype == "Birth" and d and d.startswith("CAL") else []))
    if body.get("residence"): w.fact(pid, "Residence", None, str(body.get("year") or "") or None, body["residence"].strip(), ["residence"])
    for k in ("occupation", "marital_status"):
        if body.get(k): w.fact(pid, {"occupation": "Occupation", "marital_status": "Marital Status"}[k], str(body[k]).strip(), labels=[k])
    for r in body.get("relations") or []:
        if r.get("persona_id") and cx.execute("SELECT 1 FROM persona WHERE id=? AND artifact_sha256=?", (r["persona_id"], sha)).fetchone():
            w.relation(pid, r["persona_id"], r.get("kind") or "other", (r.get("text") or "").strip() or None, "transcription")
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, by or CFG["by"], "insert", "persona", pid, dumps({"extraction": eid, **w.n})))
    written, taken = match_record(cx, eid, CFG["by"])
    return {"ok": True, "extraction": eid, "persona": pid, "proposals": len(written), "accepted_by_rule": len(taken)}

def decision_outcome(cx, tree_id, p, status, person_id, persona_id, prop_id, answered, members):
    """What the decision closed and what the plan does next, in words: the link made, the questions answered, the checklist rows
    this record fulfils for the person, the facts now carrying held evidence to accept, the proposals still open on the record,
    the steps still planned. The last line is the one sentence a director can say."""
    pe = cx.execute("SELECT name_text, role_in_record, artifact_sha256 FROM persona WHERE id=?", (persona_id,)).fetchone()
    who = cx.execute("SELECT display_name FROM person WHERE id=?", (person_id,)).fetchone()["display_name"] if person_id else None
    what = f"{pe['name_text']} ({pe['role_in_record']})"
    closed, made, nxt = [], [], []
    if status == "rejected":
        made.append(f"rejected: {what} is not {who}" if p["kind"] == "persona_match" else f"rejected: {what} is not a new person for this tree")
    else:
        made.append(f"{what} is {who}" if p["kind"] == "persona_match" else f"{who} created in this tree from {what}")
        name = lambda i: cx.execute("SELECT display_name FROM person WHERE id=?", (i,)).fetchone()["display_name"]
        made += [f"{name(m['person'])} is a {'child' if m['role'] == 'child' else 'spouse'} of {name(m['of'])}: " + ("a new link, on this record" if m["new"] else "this record accepted as evidence on the link") for m in members]
        for q in cx.execute(f"SELECT kind, detail_json FROM research_question WHERE id IN ({','.join('?'*len(answered))})", answered) if answered else []:
            closed.append(f"question answered: {q['kind']} {json.loads(q['detail_json'] or '{}').get('detail') or ''}".strip())
        held = held_apids(cx); ids = {k for k, v in held.items() if v == pe["artifact_sha256"]}
        for st in cx.execute("SELECT row_key, locator_kind, locator_value FROM search_plan WHERE person_id=? AND kind='fetch' AND status='done' ORDER BY seq", (person_id,)):
            if (st["locator_kind"] == "apid" and st["locator_value"] in ids) or (st["locator_kind"] != "apid" and st["locator_value"] and cx.execute("SELECT 1 FROM artifact WHERE sha256=? AND locator_kind=? AND locator_value=?", (pe["artifact_sha256"], st["locator_kind"], st["locator_value"])).fetchone()):
                closed.append(f"the {st['row_key'].split(':')[0]} row for {who}: held, this record")
        rs = record_says(cx, tree_id, person_id, pe["artifact_sha256"]) if person_id else []
        if rs: made.append("accepted with the record: " + ", ".join(f["fact"] for f in rs if f["status"] == "accepted"))
        for f in rs:
            if f["disagrees"]: closed.append(f"conflict raised, {f['fact']}: {f['disagrees']}")
    left = cx.execute("SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person') AND json_extract(payload_json,'$.artifact_sha256')=?", (tree_id, pe["artifact_sha256"])).fetchone()[0]
    if left: nxt.append(f"{left} proposal(s) still undecided on this record")
    if person_id:
        planned = [r["row_key"].split(":")[0] for r in cx.execute("SELECT row_key FROM search_plan WHERE person_id=? AND status='planned' ORDER BY seq", (person_id,))]
        nxt.append(f"{len(planned)} step(s) still planned for {who}" + (f": {', '.join(dict.fromkeys(planned[:4]))}" + (", …" if len(planned) > 4 else "") if planned else ""))
    summary = "; ".join(made + closed) + (". Next: " + "; ".join(nxt) if nxt else ".")
    return {"made": made, "closed": closed, "next": nxt, "summary": summary}

def decide_proposal(cx, tree_id, prop_id, status, note=None):
    """The person's decision on a document (conclude.decide), with the reason they give when they set one aside, answered in
    words: what it made and closed and what the plan does next (decision_outcome)."""
    r = decide_document(cx, tree_id, prop_id, status, CFG["by"], note=note)
    if "error" in r: return r
    p = cx.execute("SELECT * FROM proposal WHERE id=?", (prop_id,)).fetchone()
    return {**r, **decision_outcome(cx, tree_id, p, status, r["person"], r["persona"], prop_id, r["answered"], r["memberships"])}

def other_facts(cx, cat, pid):
    """Every event or attribute of the person beyond the key facts (burial, residences, occupation, an inscription, ...), each a
    fact decided under the same three states with the same evidence rule, keyed event:<id>."""
    out = []
    for e in cx.execute("""SELECT e.id, e.event_type, e.date_text, e.place_id, e.description FROM event e JOIN event_participant ep ON ep.event_id=e.id
                           WHERE ep.person_id=? AND e.event_type NOT IN ('Birth','Death') ORDER BY e.date_start, e.event_type""", (pid,)):
        f = f"event:{e['id']}"
        out.append({"field": f, "type": e["event_type"], "date": e["date_text"], "place": cat.place(e["id"], e["place_id"])["text"] if e["place_id"] else None, "value": e["description"],
                    "status": fact_status(cx, pid, f), "evidence": evidence_rows(cx, pid, f)})
    return out

def person_view(cx, tree_id, pid):
    cat = Catalog(cx, tree_id); r = build(cat, pid); r["plan"] = plan_view(cx, pid)
    r["review"] = {f: {"status": fact_status(cx, pid, f), "evidence": evidence_rows(cx, pid, f)} for f in KEY_FACTS}
    r["facts"] = other_facts(cx, cat, pid)
    r["waiting"] = cat.waiting(pid)
    r["documents"] = [c for c in (decision_card(cx, tree_id, row[0]) for row in cx.execute("""SELECT id FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person')
        AND (json_extract(payload_json,'$.person_id')=? OR (kind='new_person' AND json_extract(payload_json,'$.subject_person_id')=?)) ORDER BY created_at""", (tree_id, pid, pid))) if c]
    r["candidates"] = [{"sha256": c["sha256"], "text": render_search(c)} for c in search_cards_for(cx, tree_id, pid)]
    r["decided"] = [{"id": d["id"], "kind": d["kind"], "status": d["status"], "by_rule": (d["decided_by"] or "").startswith("rule:"), "note": d["decision_note"], "at": d["decided_at"],
                     "persona": d["name_text"], "role": d["role_in_record"], "sha256": d["artifact_sha256"], "record": d["collection"] or d["original_filename"]}
                    for d in cx.execute("""SELECT p.id, p.kind, p.status, p.decided_by, p.decision_note, p.decided_at, pe.name_text, pe.role_in_record, pe.artifact_sha256, a.original_filename, c.name AS collection
                        FROM proposal p JOIN persona pe ON pe.id=json_extract(p.payload_json,'$.persona_id') JOIN artifact a ON a.sha256=pe.artifact_sha256 LEFT JOIN collection c ON c.id=a.collection_id
                        WHERE p.tree_id=? AND p.status<>'undecided' AND p.kind IN ('persona_match','new_person') AND coalesce(p.decision_note,'')<>'superseded'
                        AND (json_extract(p.payload_json,'$.person_id')=? OR (p.kind='new_person' AND json_extract(p.payload_json,'$.subject_person_id')=?)) ORDER BY p.decided_at DESC""", (tree_id, pid, pid))]
    fam = cat.family(pid)
    r["family"] = {k: [{"id": i, "name": n, "accepted": fact_status(cx, pid, k) == "accepted" if k in ("parents", "spouses", "children") else None} for i, n in fam[k]] for k in ("parents", "spouses", "children", "siblings")}
    held = cat.held_apids(); cited = cat.cited()
    for row in r["checklist"]["A"] + r["checklist"]["B"]:
        for c in row["citations"]: c.update(fetch_target(c["apid"], cited.get(c["apid"], {}).get("url"))); c["held"] = c["apid"] in held; c["sha256"] = held.get(c["apid"])   # a held row opens its record through the artifact
    for rec in r["footprint"]["records"]: rec.update(fetch_target(rec.get("apid"), cited.get(rec.get("apid"), {}).get("url")))
    return r

def person_card(cx, cat, pid):
    """One person as the overview shows them: name, years, how many key facts are accepted, and what waits on them."""
    name, sex = cx.execute("SELECT display_name, sex FROM person WHERE id=?", (pid,)).fetchone()
    ev = cat.events(pid); b = next((e["year"] for e in ev if e["type"] == "Birth"), None); d = next((e["year"] for e in ev if e["type"] == "Death"), None)
    return {"id": pid, "name": name, "sex": sex, "span": [b, d], "accepted": sum(1 for f in KEY_FACTS if fact_status(cx, pid, f) == "accepted"), "key_facts": len(KEY_FACTS), **cat.waiting(pid)}

def people(cx, tree_id, q=""):
    cat = Catalog(cx, tree_id)
    return [person_card(cx, cat, pid) for pid, in cx.execute("SELECT id FROM person WHERE tree_id=? AND display_name LIKE ? ORDER BY display_name", (tree_id, f"%{q}%"))]

def link_trusted(cx, tree_id, pid):
    """Whether the person's parents link rests on a trusted record (T1–T3) or on the owner's own word, rather than on a page
    anyone can edit alone."""
    from conclude import trusted_evidence
    rows = [dumps([fid, pid, "child"]) for fid, in cx.execute("SELECT family_id FROM family_member WHERE person_id=? AND role='child'", (pid,))]
    return trusted_evidence(cx, tree_id, "family_member", rows)

def overview(cx, tree_id):
    """The tree overview: the people the owner has confirmed, laid out from the home person upward one row per generation, a
    card's parents above it (father then mother). The walk follows a parents link only where the owner accepted it, so the tree
    ends at the last accepted link; beyond it the file's claim of parents is named on the card as a claim, and the people it
    names stay out of the tree until a decision puts them in. A link resting on an editable source alone is said so."""
    cat = Catalog(cx, tree_id)
    home = cx.execute("SELECT home_person_id FROM tree WHERE id=?", (tree_id,)).fetchone()[0]
    if not home: return {"home": None, "generations": [], "others": people(cx, tree_id), "unconfirmed": 0}
    gens, seen, row = [], set(), [home]
    while row and len(gens) < 12:
        cards = []
        for pid in row:
            if pid in seen: continue
            seen.add(pid); c = person_card(cx, cat, pid)
            parents = sorted(cat.family(pid)["parents"], key=lambda x: 0 if (cx.execute("SELECT sex FROM person WHERE id=?", (x[0],)).fetchone() or [""])[0] == "M" else 1)
            accepted = fact_status(cx, pid, "parents") == "accepted"
            c["parents"] = [p for p, _ in parents] if accepted else []
            c["link_trusted"] = link_trusted(cx, tree_id, pid) if accepted else None
            c["claimed_parents"] = [n for _, n in parents] if parents and not accepted else []
            cards.append(c)
        gens.append(cards); row = [p for c in cards for p in c["parents"]]
    others = [c for c in people(cx, tree_id) if c["id"] not in seen]
    return {"home": home, "generations": gens, "others": [c for c in others if c["documents"] or c["conflicts"]], "unconfirmed": len(others)}

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
            if u.path == "/api/overview": self.send(overview(cx, tree_id)); return
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
        mf = re.match(r"^/api/person/([A-Z0-9]+)/fact/([a-z]+|event:[A-Z0-9]+)$", u.path); mp = re.match(r"^/api/person/([A-Z0-9]+)/plan$", u.path)
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
                elif md: res = decide_proposal(cx, tree_id, md.group(1), body.get("status"), (body.get("note") or "").strip() or None)
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
