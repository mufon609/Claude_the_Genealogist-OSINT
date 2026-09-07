"""A person's key facts as the screen and the command line decide them: what supports a fact, its status from the assertions
behind it, the evidence rows a person can see, a vouch on the owner's own knowledge, and the decision itself.

A fact's status comes from the documents accepted about the person. Accept touches only assertions whose evidence is visible
(the file's uncited claim, a held record); when none is, the accept is the person's own knowledge, recorded as a vouch on the
tree file's persona. Reject and Undecided apply to every assertion behind the fact. Every decision writes an audit row and
regenerates the person's plan.
"""
import json, re
from treelib import dumps, now, ulid
from catalog import fetch_target, held_apids, tier_sql
from conclude import answer_questions

KEY_FACTS = ("name", "sex", "birth", "death", "parents", "spouses", "children")

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
        for r in cx.execute(f"""SELECT a.id, a.citation_text, a.status, a.notes, a.artifact_sha256, {tier_sql()} AS trust_tier FROM assertion a
                               LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id WHERE a.subject_kind=? AND a.subject_id=?""", (k, i)):
            n = json.loads(r["notes"]) if r["notes"] and r["notes"].startswith("{") else {}
            apid = n.get("apid"); uncited = bool(n.get("uncited")); vouched = bool(n.get("vouched"))
            visible = uncited or vouched or (apid in held) or ((r["trust_tier"] or "")[:2] in ("T1", "T2", "T3"))   # the evidence the person can see
            ident = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in cx.execute("SELECT kind, value FROM artifact_locator WHERE artifact_sha256=? ORDER BY kind", (r["artifact_sha256"],))) if r["artifact_sha256"] else ""
            if not ident and r["artifact_sha256"]:
                loc = cx.execute("SELECT locator_value, manifest_json FROM artifact WHERE sha256=?", (r["artifact_sha256"],)).fetchone()
                m = re.search(r"scheduleId\W+(\d+)", (loc["locator_value"] or "") + " " + (loc["manifest_json"] or "")) if loc else None
                ident = f"schedule {m.group(1)}" if m else ""
            out.append({"id": r["id"], "citation": r["citation_text"], "status": r["status"], "apid": apid, "sha256": r["artifact_sha256"], "ident": ident,
                        **fetch_target(apid, n.get("url")), "uncited": uncited, "vouched": vouched, "tier": r["trust_tier"], "held": visible})
    return out

def vouch(cx, tree_id, pid, field, ts, by):
    """The person accepts a key fact on their own knowledge: one Accepted assertion per subject of the fact, by the person acting,
    on the tree file's persona for this person and the file itself, so the fact traces to the file as the archived claim and the
    acceptance to the person. Returns the assertion ids written (none when the person has no file persona)."""
    pe = cx.execute("""SELECT pe.id, pe.artifact_sha256 FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN artifact a ON a.sha256=pe.artifact_sha256
                       WHERE pp.person_id=? AND pp.status='accepted' AND a.mime='text/x-gedcom' ORDER BY pe.sequence LIMIT 1""", (pid,)).fetchone()
    if not pe: return []
    out = []
    for kind, sid in fact_subjects(cx, pid, field):
        had = cx.execute("SELECT id FROM assertion WHERE subject_kind=? AND subject_id=? AND json_valid(notes) AND json_extract(notes,'$.vouched')=1", (kind, sid)).fetchone()
        if had:                                                   # vouched before and set aside since: the same word stands again
            cx.execute("UPDATE assertion SET status='accepted', asserted_by=?, asserted_at=? WHERE id=? AND status<>'accepted'", (by, ts, had[0])); out.append(had[0]); continue
        aid = ulid(); out.append(aid)
        cx.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_id,artifact_sha256,citation_text,status,asserted_by,asserted_at,notes)
                      VALUES (?,?,?,?,?,?,?,'accepted',?,?,?)""", (aid, tree_id, kind, sid, pe["id"], pe["artifact_sha256"], "Tree owner's own knowledge", by, ts, dumps({"vouched": True})))
    return out

def decide_fact(cx, tree_id, pid, field, status, note, by):
    """Accept touches only assertions whose evidence is visible (the tree owner's uncited claim, records that are held);
    a citation to a record not yet fetched stays Undecided. When no assertion behind the fact has visible evidence, the accept
    is the person's own knowledge: a vouch (see vouch). Reject and Undecided apply to every assertion behind the fact.
    An accept regenerates the plan and marks the questions it closes answered by the proposal that brought the evidence."""
    if (field not in KEY_FACTS and not (field.startswith("event:") and fact_subjects(cx, pid, field))) or status not in ("accepted", "rejected", "undecided"): return {"error": "bad field or status"}
    ts = now(); n = 0; vouched = []
    ids = [e["id"] for e in evidence_rows(cx, pid, field) if status != "accepted" or e["held"]]
    for aid in ids:
        n += cx.execute("UPDATE assertion SET status=?, asserted_by=?, asserted_at=? WHERE id=? AND status<>?", (status, by, ts, aid, status)).rowcount
    if status == "accepted" and not ids:
        vouched = vouch(cx, tree_id, pid, field, ts, by); ids = list(vouched); n += len(vouched)   # a vouch counts as an assertion accepted
        if not vouched: return {"error": "nothing to accept: no held record supports this fact and the tree file makes no claim of it to vouch for; fetch the cited record, or accept a record that states it"}
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "accept" if status == "accepted" else ("reject" if status == "rejected" else "update"),
                "person", pid, dumps({"fact": field, "status": status, "assertions": n, "vouched": vouched, "note": note or None})))
    if note:
        cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
                   (ulid(), tree_id, "person", pid, f"{field}: {status}. {note}", by, ts))
    answered = []
    if status == "accepted" and ids:                             # the proposal whose match brought the accepted evidence answers what the plan now closes
        props = [json.loads(r["notes"]).get("proposal") for r in cx.execute(f"SELECT notes FROM assertion WHERE id IN ({','.join('?'*len(ids))}) AND notes LIKE '{{%'", ids)]
        answered = answer_questions(cx, tree_id, pid, next((x for x in props if x), None), by)
    return {"ok": True, "field": field, "status": status, "assertions": n, "evidence": len(ids), "vouched": vouched, "answered": answered}   # evidence: the assertions the decision could act on

