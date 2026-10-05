"""An import from anywhere is read as itself: the file's own encoding, the exporter its header names, the home person a fresh tree
lacks, and the checklist of a person whose places lie outside the United States.

The scenarios under tests/fixtures/scenarios/imports/ are walked by tests/checks/scenario.py with the actions and expectations
here added. A file under test is a real fixture (the harness tree, cut from the owner's own export) written as another exporter
would write it: its header's CHAR value changed, the bytes in another encoding, its header's exporter left out, or only its
header kept; the data names how (tests/fixtures/README.md). Nothing here names a person, a place or an exporter.
"""
import codecs, os, re, subprocess, sys
import scenario
from common import BY, FIXTURES, tool
from scenario import ACTIONS, EXPECTS, SCENARIOS, has

BOMS = {"utf-8": codecs.BOM_UTF8, "utf-16-le": codecs.BOM_UTF16_LE, "utf-16-be": codecs.BOM_UTF16_BE}

def written(text, how):
    """A fixture's text as an exporter with other habits would write it, as bytes. `char`: the header's CHAR value; `without_exporter`:
    the header's SOUR block dropped; `header_only`: everything from the first person on dropped; `codec` the encoding it is written in
    (utf-8 by default) with `bom` its byte order mark first. A character the codec cannot write becomes ?, as an exporter for that
    character set writes it."""
    lines = text.split("\n")
    head_end = next(i for i, l in enumerate(lines) if i and re.match(r"^0 ", l))
    head = lines[:head_end]
    if "char" in how: head = [f"1 CHAR {how['char']}" if l.startswith("1 CHAR ") else l for l in head]
    if how.get("without_exporter"):
        kept, skip = [], False
        for l in head:
            if l.startswith("1 SOUR "): skip = True; continue
            if skip and re.match(r"^[2-9] ", l): continue
            skip = False; kept.append(l)
        head = kept
    body = lines[head_end:]
    if how.get("header_only"): body = body[:next(i for i, l in enumerate(body) if l.endswith(" INDI"))]
    codec = how.get("codec", "utf-8")
    return (BOMS[codec] if how.get("bom") else b"") + "\n".join(head + body).encode(codec, errors="replace")

def a_ingest(w, x):
    """tools/ingest_gedcom.py on a fixture written as `written` says (see `written`), into the scenario's tree, its refusal not an
    error: the exit code, what it printed, and what the catalog holds of it afterwards (imports and artifacts)."""
    with open(os.path.join(FIXTURES, x["file"]), encoding="utf-8") as fh: text = fh.read()
    path = os.path.join(w.treelib.inbox_dir(), os.path.basename(x["file"]))
    with open(path, "wb") as fh: fh.write(written(text, x.get("written") or {}))
    r = subprocess.run([sys.executable, tool("ingest_gedcom.py"), path, "--keep", "--db", w.db, "--tree", w.slug, "--by", BY],
                       capture_output=True, text=True, env=os.environ)
    w.cx.commit()
    sha = (w.cx.execute("SELECT artifact_sha256 FROM tree_import WHERE tree_id=?", (w.tid,)).fetchone() or [None])[0]
    return {"code": r.returncode, "said": r.stdout + r.stderr, "sha": sha,
            "imports": w.cx.execute("SELECT COUNT(*) FROM tree_import WHERE tree_id=?", (w.tid,)).fetchone()[0],
            "artifacts": w.cx.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]}

def a_run_tool(w, x):
    """One of the tools run on the scenario's catalog, its refusal not an error: its exit code and what it printed. `args` follow
    the catalog (--db is put first, so a tool with subcommands takes it)."""
    r = subprocess.run([sys.executable, tool(x["tool"]), "--db", w.db, *x.get("args", [])], capture_output=True, text=True, env=os.environ)
    w.cx.commit()
    return {"code": r.returncode, "said": r.stdout + r.stderr}

ACTIONS.update({"ingest": a_ingest, "run_tool": a_run_tool})

# ---------------------------------------------------------------- expectations

def e_checklist_records(w, x, want):
    """The record kinds of a person's checklist rows, Group A and B: `has` and `lacks` name the ones that must and must not be there."""
    from checklist import build
    r = build(w.catalog(), w.person(x["person"]))
    got = [row["record"] for row in r["checklist"]["A"] + r["checklist"]["B"]]
    return has(got, {k: v for k, v in x.items() if k in ("has", "lacks")}), got

STORED = {"citation": "SELECT citation_text FROM assertion WHERE tree_id=:t", "collection": "SELECT name FROM collection",
          "note": "SELECT body FROM note WHERE tree_id=:t OR tree_id IS NULL", "place": "SELECT raw FROM place_string",
          "name": "SELECT display_name FROM person WHERE tree_id=:t"}

def e_stored(w, x, want):
    """Text the import stored, by where it went: a `citation` (an assertion's), a `collection` name, a `note` body, a `place` string, a
    person's `name`; some row there holds the words given, and under `absent` no row does. `clean`: no stored text anywhere holds the
    replacement character."""
    rows = lambda kind: [r[0] or "" for r in w.cx.execute(STORED[kind], {"t": w.tid})]
    got = {kind: any(words in r for r in rows(kind)) for kind, words in x.items() if kind in STORED}
    got.update({f"absent {kind}": not any(words in r for r in rows(kind)) for kind, words in (x.get("absent") or {}).items()})
    if x.get("clean"): got["clean"] = not any("\ufffd" in r for kind in STORED for r in rows(kind))
    return all(got.values()), got

def e_xref_systems(w, x, want):
    """The external id systems of the tree's persons: the file's own record ids, under the exporter's name."""
    got = sorted(r[0] for r in w.cx.execute("SELECT DISTINCT system FROM external_id WHERE tree_id=? AND entity_kind='person'", (w.tid,)))
    return got == sorted(x), got

EXPECTS.update({"checklist_records": e_checklist_records, "stored": e_stored, "xref_systems": e_xref_systems})

def check(keep, show, only=None):
    return scenario.check(os.path.join(SCENARIOS, "imports"), keep, show, only)
