#!/usr/bin/env python3
"""Match the personas of an extraction against the tree and write proposals.

usage: tools/match.py <extraction id> [--db catalog/tree.db] [--by user:<you>]

The record was fetched for one or more persons: those whose step logged the
artifact, those whose fetch step points at the same locator (for a record id,
at any id naming the same census page: every household member cited on it),
and those already matched on it by an accepted persona link. The candidates
are those persons and their relatives as the catalog knows them (parents,
spouses, children, siblings); a person the record was fetched for keeps their
own step and question on the proposal, a relative takes the context they were
first met in. Every persona on the extraction is compared with
each candidate on name, sex, birth year and stated relationships. A persona fits
a candidate when the given name agrees, the surname or a relationship agrees,
and neither sex nor birth year disagrees; the surname agrees when any token of
the record's name after the given name is a surname the tree has for the
candidate (a memorial writes a married woman's birth surname inside her name). One proposal per persona: kind
persona_match with the candidate that fits (the one with more agreements when
two fit, the other named in the rationale), or new_person when nobody fits. The
proposal carries the question of the step the candidate came from, when it has
one. The rationale says in plain words which fields agree, which disagree, which
are absent. Nothing numeric is stored. A persona that already has a proposal is
skipped, so re-running adds nothing.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, ulid
from catalog import Catalog, same_page, year

MATCHER = ("rule", "matcher", "0.1.0")
REL_OF = {"parents": "parent", "children": "child", "spouses": "spouse", "siblings": "sibling"}

def key(s): return re.sub(r"[^a-z]", "", (s or "").lower())
def first_given(s): return key((s or "").split()[0]) if (s or "").strip() else ""

def name_keys(cat, pid):
    """(first given, surname) keys for a person: every name row and every non-rejected alias."""
    keys = set()
    for given, surname, *_ in cat.person(pid)["names"]: keys.add((first_given(given), key(surname)))
    for alias in cat.person(pid)["aliases"]:
        parts = alias.split()
        if len(parts) >= 2: keys.add((first_given(parts[0]), key(parts[-1])))
    return keys

def split_persona_name(name_text):
    """(first given name key, [every later token's key]): a memorial writes a woman's name with her birth surname inside it
    (Helen Sara Brant Ahearn), so any token after the given name may be the surname the tree knows."""
    parts = [p for p in (name_text or "").replace(",", " ").split() if key(p)]
    return (first_given(parts[0]) if parts else "", [key(p) for p in parts[1:]])

def compare(cat, persona, cand, chosen):
    """Agreements, disagreements and absences between a persona and a candidate person, in words."""
    agree, disagree, absent = [], [], []
    pg, rest = split_persona_name(persona["name"]); keys = name_keys(cat, cand["id"]); ps = rest[-1] if rest else ""
    given_ok = any(pg and pg == g for g, _ in keys) or any(pg and len(pg) == 1 and g.startswith(pg) for g, _ in keys)
    surname_ok = any(t and t == s for t in rest for _, s in keys)
    (agree if given_ok else disagree).append(f"given name {'agrees' if given_ok else 'disagrees'} (record {persona['name']}, tree {cand['name']})")
    if ps: (agree if surname_ok else disagree).append(f"surname {'agrees' if surname_ok else 'disagrees'} (record {persona['name']}, tree {cand['name']})")
    else: absent.append("surname")
    if persona["sex"] and cand["sex"] in ("M", "F"): (agree if persona["sex"] == cand["sex"] else disagree).append(f"sex {'agrees' if persona['sex'] == cand['sex'] else 'disagrees'} ({persona['sex']} in the record, {cand['sex']} in the tree)")
    else: absent.append("sex")
    if persona["birth_year"] and cand["birth_year"]:
        ok = abs(persona["birth_year"] - cand["birth_year"]) <= 2
        (agree if ok else disagree).append(f"birth year {'agrees' if ok else 'disagrees'} (record {persona['birth_text']}, tree {cand['birth_year']})")
    else: absent.append("birth year")
    rel_ok = False
    for kind, other_pid, as_written, other_name in persona["relations"]:
        other_cand = chosen.get(other_pid)
        if not other_cand: absent.append(f"relationship to {other_name} ({as_written}): {other_name} not yet matched"); continue
        fam = cat.family(cand["id"]); group = {"child": "parents", "parent": "children", "spouse": "spouses", "sibling": "siblings"}.get(kind)
        if group is None: absent.append(f"relationship to {other_name} ({as_written}): the record's heading is not one the matcher maps to a family link"); continue
        holds = any(rid == other_cand["id"] for rid, _ in fam[group])
        (agree if holds else disagree).append(f"relationship {'agrees' if holds else 'disagrees'}: {as_written or kind} of {other_name}, "
                                              f"{'and' if holds else 'but'} {other_cand['name']} is {'' if holds else 'not '}a {REL_OF[group]} of {cand['name']} in the tree")
        rel_ok = rel_ok or holds
    fits = given_ok and (surname_ok or rel_ok) and not any(d.startswith(("sex", "birth year")) for d in disagree)
    return fits, agree, disagree, absent

def personas_of(cx, eid):
    out = []
    for pid, name, sex, role in cx.execute("SELECT id, name_text, sex, role_in_record FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,)):
        b = cx.execute("SELECT date_text, date_start, date_end FROM persona_fact WHERE persona_id=? AND fact_type='Birth' AND (date_start IS NOT NULL OR date_end IS NOT NULL)", (pid,)).fetchone()
        rels = cx.execute("SELECT r.kind, r.related_persona_id, r.value_text, o.name_text FROM persona_relation r JOIN persona o ON o.id=r.related_persona_id WHERE r.persona_id=?", (pid,)).fetchall()
        out.append({"id": pid, "name": name, "sex": sex, "role": role, "birth_year": year(b[1]) or year(b[2]) if b else None, "birth_text": b[0] if b else None, "relations": rels})
    return out

def candidate(cat, pid):
    p = cat.person(pid); ev = cat.events(pid); b = next((e for e in ev if e["type"] == "Birth" and e["year"]), None)
    return {"id": pid, "name": p["name"], "sex": p["sex"], "birth_year": b["year"] if b else None}

def persons_for(cx, sha):
    """(person_id, question_id, step_id) for every person the artifact was fetched for: a step logged on it, a fetch step pointing at
    its locator, or an accepted persona link on it (question and step None)."""
    rows = cx.execute("""SELECT DISTINCT sp.person_id, sp.question_id, sp.id, sp.on_json='[]' AS own, l.executed_at, sp.seq FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id
                          WHERE l.artifacts_json LIKE ? ORDER BY own DESC, l.executed_at, sp.seq""", (f'%"{sha}"%',)).fetchall()
    rows = [r[:3] for r in rows]                                  # the step whose citation sits on the person themselves first, then in the order logged
    loc = cx.execute("SELECT locator_kind, locator_value FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if loc and loc[0] and loc[1]:
        values = sorted(same_page(cx, loc[1])) if loc[0] == "apid" else [loc[1]]
        rows += cx.execute(f"SELECT DISTINCT person_id, question_id, id FROM search_plan WHERE kind='fetch' AND locator_kind=? AND locator_value IN ({','.join('?'*len(values))}) ORDER BY seq", (loc[0], *values)).fetchall()
    rows += cx.execute("""SELECT DISTINCT pp.person_id, NULL, NULL FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                          WHERE pe.artifact_sha256=? AND pp.status='accepted'""", (sha,)).fetchall()
    seen, out = set(), []
    for r in rows:
        if r[0] not in seen: seen.add(r[0]); out.append(r)
    return out

def match(cx, eid, by):
    ext = cx.execute("SELECT artifact_sha256 FROM extraction WHERE id=?", (eid,)).fetchone()
    if not ext: raise SystemExit(f"no extraction {eid}")
    sha = ext[0]; ts = now()
    row = cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", MATCHER).fetchone()
    mid = row[0] if row else ulid()
    if not row: cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (mid, *MATCHER, ts))
    personas = personas_of(cx, eid); written = []
    by_tree = {}                                                # tree id -> [(person id, question id, step id)]
    for pid, qid, step_id in persons_for(cx, sha):
        by_tree.setdefault(cx.execute("SELECT tree_id FROM person WHERE id=?", (pid,)).fetchone()[0], []).append((pid, qid, step_id))
    for tree_id, contexts in by_tree.items():
        cat = Catalog(cx, tree_id); cands, ctx_of = [], {}    # candidate persons in order met; candidate id -> the context it came from
        for pid, qid, step_id in contexts:                      # a person the record was fetched for keeps their own step and question
            if pid not in ctx_of: ctx_of[pid] = (pid, qid, step_id); cands.append(candidate(cat, pid))
        for pid, qid, step_id in contexts:
            fam = cat.family(pid)
            for rid in [r for g in ("parents", "spouses", "children", "siblings") for r, _ in fam[g]]:
                if rid not in ctx_of: ctx_of[rid] = (pid, qid, step_id); cands.append(candidate(cat, rid))
        chosen = {}                                             # persona id -> candidate, settled in passes so relationships can be checked
        for _ in range(2):
            for pr in personas:
                best = None
                for c in cands:
                    fits, agree, disagree, absent = compare(cat, pr, c, chosen)
                    if fits and (best is None or len(agree) > len(best[1])): best = (c, agree, disagree, absent)
                if best: chosen[pr["id"]] = best[0]
        names = ", ".join(cat.person(pid)["name"] for pid, _, _ in contexts)
        for pr in personas:
            if cx.execute("SELECT 1 FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.persona_id')=?", (tree_id, pr["id"])).fetchone(): continue
            if pr["id"] in chosen:
                c = chosen[pr["id"]]; fits, agree, disagree, absent = compare(cat, pr, c, chosen)
                others = [o["name"] for o in cands if o["id"] != c["id"] and compare(cat, pr, o, chosen)[0]]
                text = f"{pr['name']} ({pr['role']}) may be {c['name']}. " + " ".join(s[0].upper() + s[1:] + "." for s in agree + disagree)
                if absent: text += " Absent: " + ", ".join(absent) + "."
                if others: text += " Also fits: " + ", ".join(others) + "."
                kind, person_id, (pid, qid, step_id) = "persona_match", c["id"], ctx_of[c["id"]]
            else:
                tried = [compare(cat, pr, c, chosen) for c in cands]
                why = "; ".join(f"{c['name']}: " + (", ".join(d) if d else "nothing agrees") for c, (_, a, d, _) in zip(cands, tried) if not a or d)[:600]
                text = f"{pr['name']} ({pr['role']}) fits nobody in the family of {names}. " + why
                kind, person_id, (pid, qid, step_id) = "new_person", None, contexts[0]
            prop = ulid()
            cx.execute("""INSERT INTO proposal (id,tree_id,kind,question_id,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,?,'undecided')""",
                       (prop, tree_id, kind, qid, dumps({"persona_id": pr["id"], "person_id": person_id, "subject_person_id": pid, "extraction_id": eid, "artifact_sha256": sha, "step_id": step_id}), text, mid, ts))
            written.append((prop, kind, pr["name"], person_id))
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, by, "insert", "proposal", eid, dumps({"proposals": len(written)})))
    return written

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("extraction"); ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args(); cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
    cx.execute("BEGIN"); written = match(cx, a.extraction, a.by); cx.commit()
    for prop, kind, name, person_id in written:
        print(f"{prop}  {kind:14} {name}"); print("   ", cx.execute("SELECT rationale FROM proposal WHERE id=?", (prop,)).fetchone()[0])
    if not written: print("no new proposals")

if __name__ == "__main__": main()
