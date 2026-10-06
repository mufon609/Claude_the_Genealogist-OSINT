"""The small guards around the catalog, each run on what it guards and nothing of the owner's: the person screen's links, the
commit hook, the migration of an older catalog and the backup's bag.

The screen's `web` helper is held to the test catalog.web_url makes, whose cases are tests/fixtures/rules.json's `web_url`; the hook runs in a throwaway git repository under a temporary directory; a catalog older than
the code is the scratch catalog with the tables, views and rows a later version added taken away, so the migration meets the
shape it was written for; the bag is written under the scratch data root and read back. Nothing here names a person, a place or
a record: it walks the data under tests/fixtures/.
"""
import json, os, re, shutil, sqlite3, subprocess, sys, tempfile
from common import BY, FIXTURES, ROOT, connect, run, scratch, tool
from scenario import ACTIONS

def a_tree_home(w, x):
    """`tools/tree.py home` on the scenario's tree, a refusal not an error: the `person` named as `form` says (`bracketed`, the
    default: "Name [six characters]" as the tools print it; `id`: the whole id; `name`: the display name), the exit code, what it
    printed and the tree's home person afterwards as the harness file's entry id (None when there is none)."""
    pid = w.person(x["person"])
    name = w.cx.execute("SELECT display_name FROM person WHERE id=?", (pid,)).fetchone()[0]
    arg = {"bracketed": f"{name} [{pid[-6:]}]", "id": pid, "name": name}[x.get("form", "bracketed")]
    w.cx.commit()
    r = subprocess.run([sys.executable, tool("tree.py"), "--db", w.db, "--by", BY, "home", arg, "--tree", w.slug], capture_output=True, text=True, env=os.environ)
    home = w.cx.execute("""SELECT x.value FROM tree t JOIN external_id x ON x.entity_id=t.home_person_id AND x.entity_kind='person' AND x.system='ancestry_gedcom_xref'
                           WHERE t.id=?""", (w.tid,)).fetchone()
    return {"code": r.returncode, "said": r.stdout + r.stderr, "home": home[0] if home else None}

ACTIONS["tree_home"] = a_tree_home

WEB = "const web=u=>/^https?:\\/\\/\\S+$/i.test(String(u??''))?h(u):'';"   # the screen's helper: catalog.web_url's own test, a whole web address in any case

def screen_links():
    """Every link the person screen builds from data goes through its `web` helper: no `href="${` outside it, and the helper
    is declared as WEB, the test catalog.web_url makes (whose cases rules.json `web_url` holds), escaping what it keeps."""
    with open(os.path.join(ROOT, "app", "person", "index.html"), encoding="utf-8") as fh: html = fh.read()
    bad = [f"index.html builds a link from {m.group(0)!r} without `web`" for m in re.finditer(r'href="\$\{(?!web\()[^}]*\}', html)]
    if WEB not in html.splitlines(): bad.append(f"app/person/index.html: the `web` helper is not declared as {WEB}")
    return bad

REFUSED = ["x.ged", "ü.ged", "archive/page.html", "archive/ü/page.html", 'archive/a"b.txt', "derivatives/ü.txt", "inbox/ü.html",
           "downloads/ü.html", "catalog/tree.db", "catalog/ü.db-wal", "trees/t/imports/ü.ged", "trees/t/exports/ü.txt",
           "catalog/tree.db.turn-state.json", "x.ged\ntests/fixtures/harness.ged", "inbox/.gitkeep"]
ALLOWED = ["notes.txt", "ü.txt", "tests/fixtures/harness.ged", "downloads/.gitkeep"]
IGNORED = ["ü.ged", "archive/page.html", ".claude/output-styles/style.md", ".claude/settings.local.json"]
KEPT = ["tests/fixtures/harness.ged", ".claude/agents/tree-fetch.md", ".claude/skills/tree-fetch/SKILL.md"]

def commit_hook():
    """The commit hook refuses data by the name git stages it under, and .gitignore keeps it out of `git add`: in a throwaway
    repository holding the repo's own .gitignore, every name of REFUSED staged alone is refused by tools/hooks/pre-commit with the
    name in what it says (a letter beyond ASCII, a quote and a newline in a name among them, names git writes quoted unless
    asked for NUL-separated, and the inbox's .gitkeep, the folder being made on first use), every name of ALLOWED passes (the harness's own .ged, the downloads folder's .gitkeep), and `git add` skips
    the IGNORED names and takes the KEPT ones."""
    hook = os.path.join(ROOT, "tools", "hooks", "pre-commit")
    d = tempfile.mkdtemp(prefix="tree-hook-"); bad = []
    git = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, text=True)
    try:
        if git("init", "-q", ".").returncode: return ["git init failed in the throwaway repository"]
        shutil.copy(os.path.join(ROOT, ".gitignore"), d)
        for name in REFUSED + ALLOWED + KEPT:
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh: fh.write("x")
        for names, refused in ((REFUSED, True), (ALLOWED, False)):
            for name in names:
                git("add", "-f", "--", name)
                r = subprocess.run(["sh", hook], cwd=d, capture_output=True, text=True)
                if refused and not (r.returncode and all(part in r.stderr for part in name.split("\n"))): bad.append(f"the hook let {name!r} through staged alone: exit {r.returncode}, {r.stderr.strip()!r}")
                if not refused and r.returncode: bad.append(f"the hook refused {name!r}: {r.stderr.strip()!r}")
                git("rm", "-q", "--cached", "-f", "--", name)
        bad += [f"git add would take {n!r}, which .gitignore keeps out" for n in IGNORED if git("check-ignore", "-q", "--", n).returncode]
        bad += [f"git add would skip {n!r}, which .gitignore keeps in" for n in KEPT if git("check-ignore", "-q", "--", n).returncode != 1]
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

OLDER = {"same_record": ["no_delete", "no_update"], "task_run": ["no_delete", "no_update"], "household_member": ["no_delete", "no_update"],
         "household": ["no_delete", "no_update", "superseded_once"]}   # the tables a version from 0.7.9 on adds, and each one's insert-only triggers

def older_catalog():
    """A catalog from before the same_record, task_run and household tables (the scratch catalog with them and their triggers
    dropped and the versions from 0.7.9 forgotten, the shape of the owner's backup from before 0.7.8) migrates to the code's
    version: `initdb.py --migrate` makes each table with its own triggers and no others, every version is recorded, the catalog
    holds every table and its insert-only triggers, passes its integrity and foreign key checks, and a second run has
    nothing to apply."""
    from treelib import SCHEMA_VERSION
    d, db = scratch(False); bad = []
    try:
        cx = connect(db)
        for name, in cx.execute(f"SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name IN ({','.join('?' * len(OLDER))})", list(OLDER)).fetchall(): cx.execute(f"DROP TRIGGER {name}")
        for table in OLDER: cx.execute(f"DROP TABLE {table}")
        cx.execute("DELETE FROM schema_migration WHERE version >= '0.7.9'"); cx.commit(); cx.close()
        for second in (False, True):
            r = subprocess.run([sys.executable, tool("initdb.py"), "--migrate", "--db", db], capture_output=True, text=True, env=os.environ)
            if r.returncode: return [f"initdb.py --migrate on the older catalog stopped: {(r.stderr.strip().splitlines() or [''])[-1]}"]
            if second and "already current" not in r.stdout: bad.append(f"a second --migrate had something to apply: {r.stdout.strip()}")
        cx = connect(db)
        if SCHEMA_VERSION not in {v for v, in cx.execute("SELECT version FROM schema_migration")}: bad.append(f"the migrated catalog lacks version {SCHEMA_VERSION}")
        for table, kinds in OLDER.items():
            got = [n for n, in cx.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? ORDER BY name", (table,))]
            if got != [f"trg_{table}_{k}" for k in kinds]: bad.append(f"{table} has the triggers {got} after the migration")
        whole = cx.execute("PRAGMA integrity_check").fetchone()[0], cx.execute("PRAGMA foreign_key_check").fetchall()
        if whole != ("ok", []): bad.append(f"the migrated catalog: integrity {whole[0]}, foreign keys {len(whole[1])}")
        cx.close()
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

def older_view():
    """A catalog whose v_person_vitals is another definition than schema/catalog.sql's (here a stand-in that holds no death
    evidence) and whose version 0.8.4 is forgotten gets the view as the schema defines it from `initdb.py --migrate`: its
    stored definition is the one a new catalog's has."""
    d, db = scratch(False); bad = []
    try:
        cx = connect(db)
        sql = lambda: cx.execute("SELECT sql FROM sqlite_master WHERE name='v_person_vitals'").fetchone()[0]
        defined = sql()
        cx.execute("DROP VIEW v_person_vitals")
        cx.execute("CREATE VIEW v_person_vitals AS SELECT tree_id, id AS person_id, display_name, living_override, NULL AS birth_date, NULL AS death_date, 0 AS has_death_evidence FROM person")
        cx.execute("DELETE FROM schema_migration WHERE version='0.8.4'"); cx.commit()
        r = subprocess.run([sys.executable, tool("initdb.py"), "--migrate", "--db", db], capture_output=True, text=True, env=os.environ)
        if r.returncode: bad.append(f"initdb.py --migrate stopped: {(r.stderr.strip().splitlines() or [''])[-1]}")
        elif sql() != defined: bad.append("the migrated v_person_vitals is not the one schema/catalog.sql defines")
        cx.close()
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

DROPPED = [   # what the 0.8.6 and 0.8.7 migrations drop, as a catalog before them held it
    "CREATE TABLE artifact_page (id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256), page_no INTEGER NOT NULL, width_px INTEGER, height_px INTEGER, label TEXT, UNIQUE (artifact_sha256, page_no))",
    "CREATE TABLE derivative (id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256), page_id TEXT REFERENCES artifact_page(id), kind TEXT NOT NULL, path TEXT NOT NULL, generator TEXT, generated_at TEXT NOT NULL)",
    "CREATE INDEX ix_derivative_artifact ON derivative(artifact_sha256)",
    "ALTER TABLE extraction ADD COLUMN page_id TEXT REFERENCES artifact_page(id)",
    "ALTER TABLE persona ADD COLUMN page_id TEXT REFERENCES artifact_page(id)",
    "ALTER TABLE person ADD COLUMN private BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE note ADD COLUMN private BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE person_name ADD COLUMN surname_prefix TEXT",
    "ALTER TABLE person_name ADD COLUMN prefix TEXT",
    "ALTER TABLE person_name ADD COLUMN nick TEXT",
    "DROP TRIGGER trg_extraction_no_update",
    "CREATE TRIGGER trg_extraction_no_update BEFORE UPDATE OF id, artifact_sha256, page_id, extractor_id, ran_at, status, full_text, structured_json, notes ON extraction BEGIN SELECT RAISE(ABORT, 'extraction rows are immutable; re-run the extraction'); END",
    "CREATE VIRTUAL TABLE fts_extraction USING fts5(extraction_id UNINDEXED, full_text, tokenize = 'unicode61 remove_diacritics 2')",
    "CREATE TRIGGER trg_extraction_ai AFTER INSERT ON extraction WHEN NEW.full_text IS NOT NULL BEGIN INSERT INTO fts_extraction (extraction_id, full_text) VALUES (NEW.id, NEW.full_text); END",
    "CREATE VIRTUAL TABLE fts_persona USING fts5(persona_id UNINDEXED, name_text, tokenize = 'unicode61 remove_diacritics 2')",
    "CREATE TRIGGER trg_persona_ai AFTER INSERT ON persona WHEN NEW.name_text IS NOT NULL BEGIN INSERT INTO fts_persona (persona_id, name_text) VALUES (NEW.id, NEW.name_text); END",
    "CREATE VIRTUAL TABLE fts_note USING fts5(note_id UNINDEXED, body, tokenize = 'unicode61 remove_diacritics 2')",
    "CREATE TRIGGER trg_note_ai AFTER INSERT ON note BEGIN INSERT INTO fts_note (note_id, body) VALUES (NEW.id, NEW.body); END",
    "DROP VIEW v_person_vitals",
    """CREATE VIEW v_person_vitals AS SELECT p.tree_id, p.id AS person_id, p.display_name, p.living_override,
       (SELECT MIN(e.date_start) FROM event e JOIN event_participant ep ON ep.event_id = e.id WHERE ep.person_id = p.id AND e.event_type = 'Birth') AS birth_date,
       (SELECT MIN(e.date_start) FROM event e JOIN event_participant ep ON ep.event_id = e.id WHERE ep.person_id = p.id AND e.event_type IN ('Death','Burial','Cremation','Probate','Will')
          AND EXISTS (SELECT 1 FROM assertion a WHERE a.subject_kind = 'event' AND a.subject_id = e.id AND a.status <> 'rejected')) AS death_date,
       EXISTS (SELECT 1 FROM event e JOIN event_participant ep ON ep.event_id = e.id WHERE ep.person_id = p.id AND e.event_type IN ('Death','Burial','Cremation','Probate','Will')
          AND EXISTS (SELECT 1 FROM assertion a WHERE a.subject_kind = 'event' AND a.subject_id = e.id AND a.status <> 'rejected')) AS has_death_evidence
       FROM person p"""
]

def dropped_schema():
    """A catalog from before 0.8.6 (the scratch catalog with what that version and 0.8.7 drop put back as it stood: DROPPED) migrates to
    the code's version: afterwards nothing of DROPPED is left, its triggers and views are the ones schema/catalog.sql and
    schema/sqlite_extras.sql define (extraction's insert-only trigger and the person vitals view among them), it passes its
    integrity and foreign key checks, and its dump loads into an empty database in one pass."""
    d, db = scratch(False); bad = []
    try:
        cx = connect(db)
        schema = lambda: {(t, n): s for t, n, s in cx.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        columns = lambda: {(t, c) for t, in cx.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() for c in [r[1] for r in cx.execute(f"PRAGMA table_info({t})")]}
        defined, defined_columns = schema(), columns()
        for stmt in DROPPED: cx.execute(stmt)
        cx.execute("DELETE FROM schema_migration WHERE version IN ('0.8.6','0.8.7')"); cx.commit(); cx.close()
        r = subprocess.run([sys.executable, tool("initdb.py"), "--migrate", "--db", db], capture_output=True, text=True, env=os.environ)
        if r.returncode: return [f"initdb.py --migrate on the catalog from before 0.8.6 stopped: {(r.stderr.strip().splitlines() or [''])[-1]}"]
        cx = connect(db)
        now = schema()
        bad += [f"the migrated catalog still has the {t} {n}" for t, n in sorted(set(now) - set(defined))]
        bad += [f"the migrated catalog lacks the {t} {n}" for t, n in sorted(set(defined) - set(now))]
        bad += [f"the migrated catalog's {t} {n} is not the one the schema defines" for (t, n), s in sorted(now.items()) if t in ("trigger", "view") and (t, n) in defined and defined[(t, n)] != s]
        bad += [f"the migrated catalog still has {t}.{c}" for t, c in sorted(columns() - defined_columns)]
        whole = cx.execute("PRAGMA integrity_check").fetchone()[0], cx.execute("PRAGMA foreign_key_check").fetchall()
        if whole != ("ok", []): bad.append(f"the migrated catalog: integrity {whole[0]}, foreign keys {len(whole[1])}")
        try: sqlite3.connect(":memory:").executescript("\n".join(cx.iterdump()))
        except sqlite3.Error as e: bad.append(f"the migrated catalog's dump does not load into an empty database: {e}")
        cx.close()
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

PAGES = ["va-gravesite-search-davidson-raymond-2007", "va-gravesite-search-davidson-noi", "va-gravesite-search-davidson-raymond-e",
         "va-gravesite-search-davidson-raymond-page1"]

class MidDump:
    """The catalog's connection with a turn that writes in the middle of its dump: once the first row of `artifact` has been
    dumped, write() runs, as another process committing a record would, and the dump goes on."""
    def __init__(self, cx, write): self.cx, self.write, self.done = cx, write, False
    def __getattr__(self, name): return getattr(self.cx, name)
    def iterdump(self):
        for line in self.cx.iterdump():
            yield line
            if line.startswith('INSERT INTO "artifact" ') and not self.done: self.done = True; self.write()

def backup_bag():
    """A bag written under the scratch data root is whole and consistent: its manifest verifies, every artifact row of its
    dump has its object in the payload, no other row of the dump names an artifact it has no row for, and the dump loads into
    an empty database in one pass, though a turn
    commits a record after the objects are copied and another while the dump is written (`backup.py bag` then `check`
    run on the same catalog as the tool is)."""
    import re, backup
    from treelib import archive_dir, archive_object, object_path
    from extract import extract
    d, db = scratch(False); bad = []
    try:
        def archive(name):
            cx = connect(db)
            with open(os.path.join(FIXTURES, name + ".html"), "rb") as fh: data = fh.read()
            sha, _ = archive_object(cx, data, mime="text/html", source_id="E03", collection_id=None, locator_kind="file", locator_value=name + ".html", retrieved_by=BY, terms=None, cost="free", trust_tier=None)
            extract(cx, sha, BY); cx.commit(); cx.close()
            return sha
        held = [archive(n) for n in PAGES[:2]]
        cx = connect(db); drive = os.path.join(d, "drive"); os.makedirs(drive)
        real = shutil.copytree
        def copytree(src, dst, *a, **k):
            out = real(src, dst, *a, **k)
            if not hasattr(copytree, "late"): copytree.late = archive(PAGES[2])      # a record committed after the objects were copied
            return out
        backup.shutil.copytree = copytree
        try: bag, n, bad_objects = backup.write_bag(MidDump(cx, lambda: archive(PAGES[3])), drive, BY)
        finally: backup.shutil.copytree = real
        if bad_objects: bad.append(f"the bag holds altered objects: {bad_objects}")
        checked, broken = backup.check_bag(bag)
        if broken: bad.append(f"the bag's manifest does not verify: {broken}")
        with open(os.path.join(bag, "data", "catalog", "tree.sql"), encoding="utf-8") as fh: sql = fh.read()
        rows = lambda table, before=0: re.findall(rf"""^INSERT INTO "{table}" VALUES\({"'[^']*'," * before}'([0-9a-f]{{64}})'""", sql, re.M)   # the sha256 in a column, `before` columns in
        dumped = set(rows("artifact"))
        if not set(held) <= dumped: bad.append(f"the dump lacks artifact rows the catalog held before the bag: {sorted(set(held) - dumped)}")
        for sha in sorted(dumped):
            if not os.path.isfile(os.path.join(bag, "data", "archive", os.path.relpath(object_path(sha), archive_dir()))): bad.append(f"the dump has a row for artifact {sha[:12]} and the bag has no object for it")
        for table, before in (("extraction", 1), ("artifact_copy", 0)):
            bad += [f"the dump has a {table} row for artifact {sha[:12]} and no artifact row for it" for sha in sorted(set(rows(table, before)) - dumped)]
        try: sqlite3.connect(":memory:").executescript(sql)
        except sqlite3.Error as e: bad.append(f"the bag's catalog dump does not load into an empty database in one pass: {e}")
        r = run(tool("backup.py"), "bag", os.path.join(d, "second"), "--db", db)
        second = r.split(":")[0]
        if " 0 bad" not in r: bad.append(f"backup.py bag said: {r.strip()}")
        r = run(tool("backup.py"), "check", second, "--db", db)
        if " 0 bad" not in r: bad.append(f"backup.py check said: {r.strip()}")
        cx.close()
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

def active_tree():
    """`tools/tree.py use` writes catalog/.active-tree whole: when the write stops after the text is written and before it takes
    the file's place (os.replace raising, in a run of the tool itself), the file still names the tree it named, and nothing of the
    write's own is left beside it."""
    d, db = scratch(False); bad = []
    try:
        tool_run = lambda *args: subprocess.run([sys.executable, tool("tree.py"), "--db", db, *args], capture_output=True, text=True, env=os.environ)
        for slug in ("a", "b"): tool_run("create", slug, "--name", slug)
        path = os.path.join(d, "catalog", ".active-tree")
        with open(path, encoding="utf-8") as fh: before = fh.read()
        stop = "import os, runpy, sys\ndef stop(*a, **k): raise OSError('the write stopped')\nos.replace = stop\nsys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')"
        r = subprocess.run([sys.executable, "-c", stop, tool("tree.py"), "--db", db, "use", "b"], capture_output=True, text=True, env=os.environ)
        if not r.returncode: bad.append("`tree.py use` finished though the write stopped")
        with open(path, encoding="utf-8") as fh: after = fh.read()
        if after != before: bad.append(f"after a write that stopped .active-tree reads {after!r}, expected {before!r}")
        left = sorted(set(os.listdir(os.path.join(d, "catalog"))) - {".active-tree", "tree.db", "tree.db-wal", "tree.db-shm"})
        if left: bad.append(f"the write left {left} beside the catalog")
        if tool_run("use", "b").returncode or open(path, encoding="utf-8").read() != "b\n": bad.append("`tree.py use b` did not make b the active tree")
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

def check(keep, show):
    """Each guard as one line: ok when it holds, FAIL with every reason when it does not. Returns how many failed."""
    failed = 0
    for fn, says in ((screen_links, "the person screen writes a URL into a link only through its `web` helper, which keeps a web address, escaped, and drops any other scheme"),
                    (commit_hook, "the commit hook refuses data by the name git stages it under (a letter beyond ASCII, a quote, a newline) and passes the harness's own .ged and the downloads folder's .gitkeep; .gitignore keeps every .ged but the harness's, and the owner's own .claude settings, out of `git add`"),
                    (older_catalog, "a catalog from before the same_record, task_run and household tables migrates to the code's version: each table with its own triggers, every version recorded, integrity and foreign keys whole, a second run with nothing to apply"),
                    (older_view, "a catalog whose person vitals view is another definition gets the schema's own from the 0.8.4 migration"),
                    (dropped_schema, "a catalog from before 0.8.6 loses what nothing reads (the full-text tables and their triggers, the page tables and columns, the private flags, the surname prefix, a name's prefix and nickname, the vitals view's dates), its triggers and views the schema's own, whole, and its dump loads into an empty database"),
                    (active_tree, "the active tree is written whole: a write that stops after its text is written leaves .active-tree naming the tree it named, with nothing of the write's beside it"),
                    (backup_bag, "a bag written while a turn commits is whole and consistent: its manifest verifies, every artifact row of its catalog dump has its object in the payload, no row of the dump names an artifact it has no row for, and the dump loads into an empty database in one pass")):
        bad = fn(); failed += bool(bad)
        print(f"ok   {says}" if not bad else f"FAIL {fn.__name__}: " + "; ".join(bad))
    return failed
