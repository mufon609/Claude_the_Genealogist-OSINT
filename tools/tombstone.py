#!/usr/bin/env python3
"""An archived file withdrawn from the evidence: its tombstone written, the one way a removal from the archive is recorded
(CLAUDE.md hard rule 2; docs/DATA-ARCHITECTURE.md §2).

usage: tools/tombstone.py <sha256> --reason "…" [--destroy] [--db catalog/tree.db] [--by user:<you>]

The artifact row, its manifest, its extractions and personas stay as they were written (they are insert-only); the tombstone
row says the file is withdrawn, why, when and by whom, with one audit row holding the same. From then on no reader counts the
file as held (catalog.not_withdrawn: the holdings, a citation's held record, a done step's held rows, the person screen's
steps), the attach refuses its bytes, and the backup's fixity run skips it. Quarantined, the default, keeps its bytes in the
archive, where the backup's bag still copies them; --destroy, for a takedown, removes the object's bytes, the manifest kept to
say what was held. The sha256 may be given as its first twelve characters or more, as the tools print it, when one artifact
alone begins so. A file already withdrawn is refused, its tombstone named. What rests on the file in each tree (persona links
accepted on its personas, statements not rejected that cite it, cards still undecided on it) is printed: a decision on a
withdrawn record is the owner's to take again with tools/conclude.py, never undone here.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, object_path, ulid
from catalog import withdrawals

def artifact(cx, sha):
    """The artifact a full sha256, or the first twelve characters or more of one, names: its row, or SystemExit saying why not."""
    sha = (sha or "").strip().lower()
    if len(sha) < 12: raise SystemExit("give the sha256, or at least its first twelve characters")
    rows = cx.execute("SELECT sha256, source_id, locator_kind, locator_value, original_filename FROM artifact WHERE sha256 LIKE ? ORDER BY sha256", (sha + "%",)).fetchall()
    if not rows: raise SystemExit(f"no archived file begins {sha}")
    if len(rows) > 1: raise SystemExit(f"{len(rows)} archived files begin {sha}: give more of the sha256")
    return rows[0]

def resting(cx, sha):
    """What rests on the file, per tree: {tree slug: {"links": [person names accepted on one of its personas], "statements": n
    not rejected citing it (on the artifact or a fact of one of its personas), "cards": n undecided on it}}."""
    out = {}
    for slug, name in cx.execute("""SELECT DISTINCT t.slug, p.display_name FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN person p ON p.id=pp.person_id
                                    JOIN tree t ON t.id=p.tree_id WHERE pe.artifact_sha256=? AND pp.status='accepted' ORDER BY t.slug, p.display_name""", (sha,)):
        out.setdefault(slug, {"links": [], "statements": 0, "cards": 0})["links"].append(name)
    for slug, n in cx.execute("""SELECT t.slug, COUNT(DISTINCT a.id) FROM assertion a JOIN tree t ON t.id=a.tree_id LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                 LEFT JOIN persona pe ON pe.id=coalesce(pf.persona_id, a.persona_id)
                                 WHERE a.status<>'rejected' AND (a.artifact_sha256=? OR pe.artifact_sha256=?) GROUP BY t.slug""", (sha, sha)):
        out.setdefault(slug, {"links": [], "statements": 0, "cards": 0})["statements"] = n
    for slug, n in cx.execute("""SELECT t.slug, COUNT(*) FROM proposal pr JOIN tree t ON t.id=pr.tree_id
                                 WHERE pr.status='undecided' AND json_extract(pr.payload_json,'$.artifact_sha256')=? GROUP BY t.slug""", (sha,)):
        out.setdefault(slug, {"links": [], "statements": 0, "cards": 0})["cards"] = n
    return out

def tombstone(cx, sha, reason, by, destroy=False):
    """The file withdrawn: its tombstone row and one audit row under `by`, the archive being every tree's (no tree on the row);
    destroyed, its object's bytes removed after the rows are written. SystemExit, nothing written, for no reason given or a file already withdrawn. Returns {sha256, disposition, resting, filename, source_id, object
    (where its bytes are, or were)}."""
    reason = (reason or "").strip()
    if not reason: raise SystemExit("a file is withdrawn with its reason (--reason)")
    a = artifact(cx, sha)
    old = withdrawals(cx, [a[0]]).get(a[0])
    if old: raise SystemExit(f"{a[0][:12]} was withdrawn on {old['at']} by {old['by']}: {old['reason']}")
    ts, disposition = now(), "destroyed" if destroy else "quarantined"
    rest = resting(cx, a[0])
    cx.execute("INSERT INTO tombstone (artifact_sha256,reason,disposition,tombstoned_at,tombstoned_by) VALUES (?,?,?,?,?)", (a[0], reason, disposition, ts, by))
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), None, ts, by, "insert", "tombstone", a[0], dumps({"reason": reason, "disposition": disposition, "source_id": a[1],
                                                                           "locator": {"kind": a[2], "value": a[3]}, "original_filename": a[4], "resting": rest})))
    if destroy and os.path.exists(object_path(a[0])): os.remove(object_path(a[0]))
    return {"sha256": a[0], "disposition": disposition, "resting": rest, "filename": a[4], "source_id": a[1], "object": object_path(a[0])}

def main():
    ap = argparse.ArgumentParser(description="An archived file withdrawn from the evidence: its tombstone, its reason and an audit row.")
    ap.add_argument("sha256"); ap.add_argument("--reason", required=True, help="why the file is withdrawn, in words")
    ap.add_argument("--destroy", action="store_true", help="a takedown: the object's bytes removed, the manifest kept")
    ap.add_argument("--db", default=DB); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db)
    cx.execute("BEGIN")
    try: r = tombstone(cx, a.sha256, a.reason, a.by, a.destroy)
    except SystemExit: cx.rollback(); raise
    cx.commit()
    print(f"{r['sha256'][:12]} ({r['filename'] or 'no file name'}, {r['source_id'] or 'no source'}) withdrawn, {r['disposition']}: "
          + ("its bytes removed, its manifest kept" if r["disposition"] == "destroyed" else "its bytes stay in the archive, held by no reader"))
    for slug, x in r["resting"].items():
        print(f"  still resting on it in {slug}: " + "; ".join(s for s in (f"accepted on {', '.join(x['links'])}" if x["links"] else "", f"{x['statements']} statement(s) not rejected" if x["statements"] else "",
                                                                         f"{x['cards']} card(s) undecided" if x["cards"] else "") if s) + " (decide them again with tools/conclude.py)")

if __name__ == "__main__": main()
