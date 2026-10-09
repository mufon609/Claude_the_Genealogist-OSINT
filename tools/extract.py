#!/usr/bin/env python3
"""Read an archived record page (HTML) or a connector response (JSON) for the tree: the reading with the decisions carried to it,
then the matcher and the standing rule.

usage: tools/extract.py <sha256 | path> [--about "<person>"] [--db catalog/tree.db] [--by user:<you>]
       tools/extract.py --stale [--db catalog/tree.db] [--by user:<you>]   every page whose current reading an older version of its parser made, read again

The readers are tools/readers.py (one parser per page kind, the personas, facts and relations each writes, the record form's
locators in each persona's region_json); the reading with the decisions carried to it is copies.read_page, which every caller
that reads a page runs; the matcher and the rule follow (decisions.match_record). --about names the person the record is about
on the owner's word, when no step or link names them: a fetch step on their plan, done with a found run naming the record
(attach.on_word), so every later reading finds them.
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, sha256_file
from readers import EXTRACTORS
from copies import read_page

def stale(cx):
    """The archived pages whose current reading a parser of this file made at a version older than its own now: (sha256,
    parser name, the version that read it), oldest reading first."""
    now_at = {name: version for kind, name, version in EXTRACTORS.values() if kind == "rule"}
    return [(sha, name, ver) for sha, name, ver in cx.execute("""SELECT e.artifact_sha256, x.name, x.version FROM extraction e JOIN extractor x ON x.id=e.extractor_id
                                                                 WHERE e.superseded_by IS NULL AND e.status<>'failed' AND x.kind='rule' ORDER BY e.ran_at""").fetchall()
            if name in now_at and ver != now_at[name]]

def read(cx, sha, by, about=None):
    """One page read and decided: the reading with the decisions carried to it (copies.read_page), then the matcher and the rule;
    about names the person the owner says the record is about. Returns (extraction id, counts, proposals written, taken)."""
    cx.execute("BEGIN"); eid, n = read_page(cx, sha, by); cx.commit()
    if "failed" in n: return eid, n, [], []
    from decisions import match_record
    cx.execute("BEGIN")
    if about:                                                       # the owner's word: a fetch step on their plan, done with a found run naming the record, so every later reading finds them
        from attach import on_word
        on_word(cx, about[1], about[0], sha, by)
    written, taken = match_record(cx, eid, by, about=[about[0]] if about else None); cx.commit()          # the matcher runs on every extraction as it is written, then the rule
    return eid, n, written, taken

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("what", nargs="?", help="artifact sha256, or a path whose bytes are archived")
    ap.add_argument("--stale", action="store_true", help="read again every page an older version of its parser read")
    ap.add_argument("--db", default=DB); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument("--about", help="the person the record is about when no step or link names them, on the owner's word")
    a = ap.parse_args()
    cx = connect(a.db)
    if a.stale:
        pages = stale(cx)
        for sha, name, ver in pages:
            eid, n, written, taken = read(cx, sha, a.by)
            print(f"{sha[:12]} {name} {ver} -> read again: {n.get('personas', 0)} persona(s), {len(written)} proposal(s), {len(taken)} taken by the rule" + (" (failed)" if "failed" in n else ""))
        print(f"{len(pages)} page(s) read again" if pages else "every page is read by its parser's current version"); return
    if not a.what: ap.error("name a page (sha256 or path), or --stale")
    sha = a.what if re.fullmatch(r"[0-9a-f]{64}", a.what) else sha256_file(a.what)
    about = None
    if a.about:
        from catalog import Catalog
        cx.row_factory = None; tid = cx.execute("SELECT tree_id FROM person WHERE id=? OR display_name=? LIMIT 1", (a.about, a.about)).fetchone()
        about = (Catalog(cx, tid[0]).find_person(a.about), tid[0]) if tid else None
    eid, n, written, taken = read(cx, sha, a.by, about)
    print("extraction", eid, dumps(n))
    if "failed" in n: return
    print("proposals", len(written), "accepted by rule", len(taken))
    for pid, name, sex, role in cx.execute("SELECT id, name_text, sex, role_in_record FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,)):
        print(f"  {name} [{role}{', ' + sex if sex else ''}]")
        for ft, v, d, ps, rg in cx.execute("""SELECT pf.fact_type, pf.value_text, pf.date_text, ps.raw, pf.region_json FROM persona_fact pf
                                              LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pf.persona_id=?""", (pid,)):
            print(f"      {ft:14} {' '.join(x for x in (v, d, ps) if x)}")
        for kind, vt, other in cx.execute("SELECT r.kind, r.value_text, p.name_text FROM persona_relation r JOIN persona p ON p.id=r.related_persona_id WHERE r.persona_id=?", (pid,)):
            print(f"      {kind} of {other} ({vt})")

if __name__ == "__main__": main()
