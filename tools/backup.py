#!/usr/bin/env python3
"""Fixity and backup for the archive: verify the objects on disk against their hashes, package them as a BagIt bag with a
plain-SQL dump of the catalog beside them, and check a bag on the drive it was written to.

usage: tools/backup.py verify [--sample N] [--db catalog/tree.db]           every object (or a random N) hashed and compared
       tools/backup.py bag <dest dir> [--target <name>] [--db catalog/tree.db]   a bag at <dest dir>/<date>-tree/, the catalog dumped into it
       tools/backup.py check <bag dir> [--target <name>] [--db catalog/tree.db]  the bag's payload hashed against its manifest

verify: for every artifact that is not tombstoned, the object under archive/objects is hashed and compared with its sha256;
artifact_copy for the local target records when and whether it verified. A missing or altered object is reported and marked
verify_ok false; nothing is repaired here (docs/DATA-ARCHITECTURE.md §2: a correction is a new object, a deletion a
tombstone).

bag: a BagIt 1.0 bag (Library of Congress) holding archive/objects and archive/manifests under data/archive/ and the catalog
as data/catalog/tree.sql, written from the live connection so the dump is consistent, with manifest-sha256.txt over the
payload and tagmanifest-sha256.txt over the tag files. The bag's payload manifest is the fixity record of that copy. Every
object is hashed again after copying; with --target the bag counts as a copy of each object on that storage target
(a storage_target row named for the drive, kind local, uri file://<dest dir>, made when missing), so
v_artifact_under_replicated goes quiet for objects the drive holds. A dump holds living-person data: a bag is never
committed or shared.

check: a bag's payload hashed against its own manifest, for the drive that holds it; with --target the result is recorded on
artifact_copy for the objects in it.
"""
import argparse, datetime as dt, hashlib, os, random, shutil, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, archive_dir, now, object_path

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def record_copy(cx, sha, target, ok, ts):
    cx.execute("""INSERT INTO artifact_copy (artifact_sha256,target_name,stored_at,last_verified,verify_ok) VALUES (?,?,?,?,?)
                  ON CONFLICT(artifact_sha256,target_name) DO UPDATE SET last_verified=excluded.last_verified, verify_ok=excluded.verify_ok""", (sha, target, ts, ts, ok))

def ensure_target(cx, name, uri):
    if not cx.execute("SELECT 1 FROM storage_target WHERE name=?", (name,)).fetchone():
        cx.execute("INSERT INTO storage_target (name,kind,uri,is_master,object_lock,enabled,notes) VALUES (?,?,?,0,0,1,?)", (name, "local", uri, "BagIt bags written by tools/backup.py"))

def artifacts(cx):
    return [r[0] for r in cx.execute("SELECT sha256 FROM artifact a WHERE NOT EXISTS (SELECT 1 FROM tombstone t WHERE t.artifact_sha256=a.sha256) ORDER BY sha256")]

def verify(cx, sample=None):
    """(checked, bad): every object, or a random sample, hashed against its sha256; artifact_copy 'local' updated."""
    shas = artifacts(cx)
    if sample: shas = random.sample(shas, min(sample, len(shas)))
    ts = now(); bad = []
    for sha in shas:
        p = object_path(sha); ok = os.path.isfile(p) and sha256_of(p) == sha
        record_copy(cx, sha, "local", ok, ts)
        if not ok: bad.append((sha, "missing" if not os.path.isfile(p) else "altered"))
    return len(shas), bad

def dump_sql(cx, path):
    with open(path, "w", encoding="utf-8") as fh:
        for line in cx.iterdump(): fh.write(line + "\n")

def write_bag(cx, dest, target=None):
    """The bag directory written and its payload verified; returns (bag dir, objects bagged, bad objects)."""
    day = dt.date.today().isoformat(); bag = os.path.join(os.path.abspath(dest), f"{day}-tree")
    if os.path.exists(bag): raise SystemExit(f"{bag} exists; a bag is written once, check it or bag into another directory")
    data = os.path.join(bag, "data"); os.makedirs(os.path.join(data, "catalog"))
    entries = []                                              # (relative payload path, sha256, bytes)
    for sub in ("objects", "manifests"):
        src = os.path.join(archive_dir(), sub)
        if os.path.isdir(src): shutil.copytree(src, os.path.join(data, "archive", sub))
    dump_sql(cx, os.path.join(data, "catalog", "tree.sql"))
    for root, _, files in os.walk(data):
        for f in sorted(files):
            p = os.path.join(root, f); entries.append((os.path.relpath(p, bag).replace(os.sep, "/"), sha256_of(p), os.path.getsize(p)))
    with open(os.path.join(bag, "manifest-sha256.txt"), "w", encoding="utf-8") as fh:
        for rel, sha, _ in entries: fh.write(f"{sha}  {rel}\n")
    with open(os.path.join(bag, "bagit.txt"), "w", encoding="utf-8") as fh: fh.write("BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")
    with open(os.path.join(bag, "bag-info.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"Bagging-Date: {day}\nPayload-Oxum: {sum(b for _, _, b in entries)}.{len(entries)}\n"
                 f"External-Description: the tree archive (objects and manifests) and a plain-SQL dump of the catalog; holds living-person data, never shared\n")
    with open(os.path.join(bag, "tagmanifest-sha256.txt"), "w", encoding="utf-8") as fh:
        for f in ("bagit.txt", "bag-info.txt", "manifest-sha256.txt"): fh.write(f"{sha256_of(os.path.join(bag, f))}  {f}\n")
    bagged, bad = objects_in(entries)
    if target: note_copies(cx, target, os.path.abspath(dest), bagged, bad)
    return bag, len(bagged), bad

def objects_in(entries):
    """The archive objects a bag's manifest lists, by their own hash: (good shas, bad (sha, why))."""
    good, bad = [], []
    for rel, sha, _ in entries:
        parts = rel.split("/")                                 # data/archive/objects/sha256/ab/cd/<sha>
        if len(parts) == 7 and parts[:3] == ["data", "archive", "objects"]:
            if parts[-1] == sha: good.append(sha)
            else: bad.append((parts[-1], "altered"))
    return good, bad

def note_copies(cx, target, uri_dir, good, bad):
    ensure_target(cx, target, "file://" + uri_dir); ts = now()
    known = set(artifacts(cx))
    for sha in good:
        if sha in known: record_copy(cx, sha, target, True, ts)
    for sha, _ in bad:
        if sha in known: record_copy(cx, sha, target, False, ts)

def check_bag(bag, cx=None, target=None):
    """A bag's payload against its manifest: (files checked, [(path, why)]); with a target, the objects' copies recorded."""
    man = os.path.join(bag, "manifest-sha256.txt")
    if not os.path.isfile(man): raise SystemExit(f"{bag} has no manifest-sha256.txt")
    entries, bad = [], []
    with open(man, encoding="utf-8") as fh:
        for line in fh:
            sha, rel = line.rstrip("\n").split("  ", 1); p = os.path.join(bag, rel)
            actual = sha256_of(p) if os.path.isfile(p) else None
            entries.append((rel, actual or sha, os.path.getsize(p) if actual else 0))
            if actual != sha: bad.append((rel, "missing" if actual is None else "altered"))
    if target and cx is not None:
        good, _ = objects_in(entries); broken = {rel for rel, _ in bad}
        note_copies(cx, target, os.path.dirname(os.path.abspath(bag)), [s for s in good if not any(r.endswith(s) for r in broken)],
                    [(rel.split("/")[-1], why) for rel, why in bad if "/objects/" in rel])
    return len(entries), bad

def main():
    ap = argparse.ArgumentParser(description="Fixity and BagIt backup of the archive and the catalog.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="hash every object (or a random sample) against its sha256 and record the result"); v.add_argument("--sample", type=int)
    b = sub.add_parser("bag", help="write a BagIt bag of the archive with a plain-SQL dump of the catalog"); b.add_argument("dest"); b.add_argument("--target", help="record the bag as a copy on this storage target (the drive's name)")
    c = sub.add_parser("check", help="hash a bag's payload against its manifest"); c.add_argument("bag"); c.add_argument("--target")
    for x in (v, b, c): x.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
    if a.cmd == "verify":
        n, bad = verify(cx, a.sample); cx.commit()
        for sha, why in bad: print(f"{why}: {sha}")
        print(f"{n} object(s) verified, {len(bad)} bad; under-replicated: {cx.execute('SELECT COUNT(*) FROM v_artifact_under_replicated').fetchone()[0]}")
    elif a.cmd == "bag":
        bag, n, bad = write_bag(cx, a.dest, a.target); cx.commit()
        for sha, why in bad: print(f"{why}: {sha}")
        print(f"{bag}: {n} object(s) bagged with the catalog dump, {len(bad)} bad" + (f"; recorded as copies on {a.target}; under-replicated now: {cx.execute('SELECT COUNT(*) FROM v_artifact_under_replicated').fetchone()[0]}" if a.target else ""))
    else:
        n, bad = check_bag(a.bag, cx, a.target); cx.commit()
        for rel, why in bad: print(f"{why}: {rel}")
        print(f"{a.bag}: {n} file(s) checked, {len(bad)} bad")

if __name__ == "__main__": main()
