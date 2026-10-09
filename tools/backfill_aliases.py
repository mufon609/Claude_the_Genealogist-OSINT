#!/usr/bin/env python3
"""Create `undecided` aliases for persons from the as-written names on their accepted
personas, and classify resolved place strings (place_string.variant_kind).

usage: tools/backfill_aliases.py [--tree slug] [--dry-run] [--by user:<you>]

Every alias, note and audit row it writes names --by as who wrote it. Never edits evidence. Never promotes an alias to a name. Re-runnable: existing
alias rows are left alone (UNIQUE on entity/value).
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, resolve_tree, ulid
from catalog import alias_key as key, classify, clean, edits

def backfill_persons(cx, tree_id, by, ts, stats, report):
    rows = cx.execute("""SELECT pp.person_id, pf.id, pf.value_text, pn.given, pn.surname, pn.suffix, pe.artifact_sha256
                         FROM person_persona pp
                         JOIN persona pe ON pe.id = pp.persona_id
                         JOIN persona_fact pf ON pf.persona_id = pe.id AND pf.fact_type = 'Name'
                         JOIN person_name pn ON pn.person_id = pp.person_id AND pn.is_primary
                         JOIN person p ON p.id = pp.person_id
                         WHERE pp.status = 'accepted' AND p.tree_id = ?""", (tree_id,)).fetchall()
    for person_id, fact_id, written, given, surname, suffix, sha in rows:
        canon = " ".join(x for x in (given, surname, suffix) if x)
        value = clean(written)
        if not value or key(value) == key(canon): continue
        # already a canonical or non-primary name of this person?
        if any(key(value) == key(" ".join(x for x in r if x)) for r in cx.execute(
                "SELECT given, surname, suffix FROM person_name WHERE person_id=?", (person_id,))):
            continue
        if cx.execute("SELECT 1 FROM alias WHERE entity_kind='person' AND entity_id=? AND value=?", (person_id, value)).fetchone():
            stats["already"] += 1; continue
        kind, note = classify(written, given, surname, suffix)
        cx.execute("""INSERT INTO alias (id,tree_id,entity_kind,entity_id,value,kind,status,source_persona_fact_id,source_artifact_sha256,added_by,added_at,notes)
                      VALUES (?,?,?,?,?,?,'undecided',?,?,?,?,?)""", (ulid(), tree_id, "person", person_id, value, kind, fact_id, sha, by, ts, note))
        stats["aliases"] += 1; stats["kind:" + kind] += 1
        report.append(("ALIAS", f"{canon}  <-  {value}", f"{kind}: {note}"))

def classify_place(raw, notes):
    n = json.loads(notes) if notes and notes.startswith("{") else {}
    if any("Silesia given as Germany" in w for w in n.get("warnings", [])): return "jurisdiction_error"
    match = n.get("match") or {}
    checks = match.get("checks") or {}
    first = raw.split(",")[0].strip()
    leaf = (match.get("display_name") or "").split(",")[0].strip()
    ln = lambda s: re.sub(r"\b(county|township|twp|town of|village of|city of)\b", "", s.lower()).strip()
    if first.endswith(".") and leaf and ln(leaf).startswith(ln(first.rstrip("."))): return "abbreviation"
    if first and leaf and ln(first) != ln(leaf) and (first in checks) and edits(ln(first), ln(leaf)) <= 3 and not re.search(r"\d", first):
        if first.endswith(".") or len(first) <= 5: return "abbreviation"
        return "typo"
    if re.search(r"\bAllemagne\b|\bSilesa\b", raw): return "translation"
    if re.search(r"British Colonies|North America", raw): return "historical"
    if n.get("details"): return "detail"
    if re.search(r"\b(PA|NY|NJ|MA|KY|TN|OH|VA|FL|CO|GA|TX|NC|SC|WA)\b,", raw) or re.search(r"\b(Co|Cty|Twp)\b", raw): return "abbreviation"
    return None

def flag_bad_canonical_names(cx, tree_id, by, ts, stats, report):
    """A canonical name carrying a code or digits (a research tag such as 'CFT19' copied into the suffix) is the tree owner's
    conclusion; the backfill edits nothing and writes one note on the person saying which part is not a name."""
    rows = cx.execute("""SELECT pn.person_id, pn.given, pn.surname, pn.suffix FROM person_name pn JOIN person p ON p.id=pn.person_id
                         WHERE p.tree_id=? AND (pn.suffix GLOB '*[0-9]*' OR pn.given GLOB '*[0-9]*' OR pn.surname GLOB '*[0-9]*')""", (tree_id,)).fetchall()
    for person_id, given, surname, suffix in rows:
        part = next(v for v in (suffix, given, surname) if v and re.search(r"\d", v))
        body = f"The primary name carries the code {part!r} from the imported file; it is a research tag, not part of the name."
        if cx.execute("SELECT 1 FROM note WHERE tree_id=? AND entity_kind='person' AND entity_id=? AND body=?", (tree_id, person_id, body)).fetchone(): continue
        cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)", (ulid(), tree_id, "person", person_id, body, by, ts))
        stats["bad_name_notes"] += 1; report.append(("NAME?", f"{given} {surname} {suffix}", "code in canonical name -> note on the person"))

def backfill_places(cx, stats, report):
    for psid, raw, notes in cx.execute("SELECT id, raw, notes FROM place_string WHERE status='accepted' AND variant_kind IS NULL").fetchall():
        kind = classify_place(raw, notes)
        if kind:
            cx.execute("UPDATE place_string SET variant_kind=? WHERE id=?", (kind, psid))
            stats["place_variants"] += 1; stats["place:" + kind] += 1
            report.append(("PLACE", raw, kind))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB); ap.add_argument("--tree")
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db)
    tree_id, slug = resolve_tree(cx, a.tree)
    import collections; stats = collections.Counter(); report = []
    ts = now()
    backfill_persons(cx, tree_id, a.by, ts, stats, report)
    flag_bad_canonical_names(cx, tree_id, a.by, ts, stats, report)
    backfill_places(cx, stats, report)
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, a.by, "insert", "alias", "batch", dumps(dict(stats))))
    cx.rollback() if a.dry_run else cx.commit()
    for tag, a_, b_ in report: print(f"{tag:6} {a_[:70]:70} {b_[:60]}")
    print("\n" + dumps(dict(stats)))

if __name__ == "__main__":
    main()
