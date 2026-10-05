"""The small guards around the catalog, each run on what it guards and nothing of the owner's: the person screen's links, the
commit hook, the migration of an older catalog and the backup's bag.

The screen's script is run by node on the cases of tests/fixtures/rules.json (`web_url`, the same plain values the Python reader
of a file's URL is checked on); the hook runs in a throwaway git repository under a temporary directory; a catalog older than
the code is the scratch catalog with the tables, views and rows a later version added taken away, so the migration meets the
shape it was written for; the bag is written under the scratch data root and read back. Nothing here names a person, a place or
a record: it walks the data under tests/fixtures/.
"""
import json, os, re, shutil, sqlite3, subprocess, sys, tempfile
from common import BY, FIXTURES, ROOT, TOOLS, connect, done, scratch, tool

def screen_links():
    """Every link the person screen builds from data goes through its `web` helper: no `href="${` outside it, and the helper,
    run by node on the cases of rules.json `web_url`, gives the escaped address of a web address and nothing for any other
    (a `javascript:` or `data:` address among them, any case of a scheme, whitespace inside one)."""
    with open(os.path.join(ROOT, "app", "person", "index.html"), encoding="utf-8") as fh: html = fh.read()
    with open(os.path.join(FIXTURES, "rules.json"), encoding="utf-8") as fh: cases = json.load(fh)["web_url"]
    bad = [f"index.html builds a link from {m.group(0)!r} without `web`" for m in re.finditer(r'href="\$\{(?!web\()[^}]*\}', html)]
    helpers = [l for l in html.splitlines() if l.startswith("const $=") or l.startswith("const web=")]
    if len(helpers) != 2: return bad + ["app/person/index.html: the `h` and `web` helpers are not each declared on a line of their own at the start of the script"]
    if not shutil.which("node"): return bad + ["node is not installed: it runs the person screen's `web` helper on rules.json's web_url cases"]
    script = "\n".join(helpers) + "\nconst c=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(c.map(x=>web(x.url))))"
    r = subprocess.run(["node", "-e", script], input=json.dumps(cases), capture_output=True, text=True)
    if r.returncode: return bad + [f"node could not run the screen's helper: {r.stderr.strip()[:300]}"]
    return bad + [f"web({c['url']!r}) gave {got!r}, expected {c['href']!r}" for c, got in zip(cases, json.loads(r.stdout)) if got != c["href"]]

REFUSED = ["x.ged", "ü.ged", "archive/page.html", "archive/ü/page.html", 'archive/a"b.txt', "derivatives/ü.txt", "inbox/ü.html",
           "downloads/ü.html", "catalog/tree.db", "catalog/ü.db-wal", "trees/t/imports/ü.ged", "trees/t/exports/ü.txt",
           "catalog/tree.db.turn-state.json", "x.ged\ntests/fixtures/harness.ged"]
ALLOWED = ["notes.txt", "ü.txt", "tests/fixtures/harness.ged", "inbox/.gitkeep", "downloads/.gitkeep"]
IGNORED = ["ü.ged", "archive/page.html", ".claude/output-styles/style.md", ".claude/settings.local.json"]
KEPT = ["tests/fixtures/harness.ged", ".claude/agents/tree-fetch.md", ".claude/skills/tree-fetch/SKILL.md"]

def commit_hook():
    """The commit hook refuses data by the name git stages it under, and .gitignore keeps it out of `git add`: in a throwaway
    repository holding the repo's own .gitignore, every name of REFUSED staged alone is refused by tools/hooks/pre-commit with the
    name in what it says (a letter beyond ASCII, a quote and a newline in a name among them, names git writes quoted unless
    asked for NUL-separated), every name of ALLOWED passes (the harness's own .ged, the folders' .gitkeep), and `git add` skips
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

def older_catalog():
    """A catalog from before the same_record and task_run tables (the scratch catalog with both tables and their triggers
    dropped and the versions from 0.7.9 forgotten, the shape of the owner's backup from before 0.7.8) migrates to the code's
    version: `initdb.py --migrate` makes each table with its own triggers and no others, every version is recorded, the catalog
    holds both tables and their insert-only triggers, passes its integrity and foreign key checks, and a second run has
    nothing to apply."""
    from treelib import SCHEMA_VERSION
    d, db = scratch(False); bad = []
    try:
        cx = connect(db)
        for name, in cx.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name IN ('same_record','task_run')").fetchall(): cx.execute(f"DROP TRIGGER {name}")
        cx.execute("DROP TABLE same_record"); cx.execute("DROP TABLE task_run")
        cx.execute("DELETE FROM schema_migration WHERE version >= '0.7.9'"); cx.commit(); cx.close()
        for second in (False, True):
            r = subprocess.run([sys.executable, tool("initdb.py"), "--migrate", "--db", db], capture_output=True, text=True, env=os.environ)
            if r.returncode: return [f"initdb.py --migrate on the older catalog stopped: {(r.stderr.strip().splitlines() or [''])[-1]}"]
            if second and "already current" not in r.stdout: bad.append(f"a second --migrate had something to apply: {r.stdout.strip()}")
        cx = connect(db)
        if SCHEMA_VERSION not in {v for v, in cx.execute("SELECT version FROM schema_migration")}: bad.append(f"the migrated catalog lacks version {SCHEMA_VERSION}")
        for table in ("same_record", "task_run"):
            got = [n for n, in cx.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? ORDER BY name", (table,))]
            if got != [f"trg_{table}_no_delete", f"trg_{table}_no_update"]: bad.append(f"{table} has the triggers {got} after the migration")
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

def check(keep, show):
    """Each guard as one line: ok when it holds, FAIL with every reason when it does not. Returns how many failed."""
    failed = 0
    for fn, says in ((screen_links, "the person screen writes a URL into a link only through its `web` helper, which keeps a web address, escaped, and drops any other scheme"),
                    (commit_hook, "the commit hook refuses data by the name git stages it under (a letter beyond ASCII, a quote, a newline) and passes the harness's own .ged and the .gitkeep files; .gitignore keeps every .ged but the harness's, and the owner's own .claude settings, out of `git add`"),
                    (older_catalog, "a catalog from before the same_record and task_run tables migrates to the code's version: each table with its own triggers, every version recorded, integrity and foreign keys whole, a second run with nothing to apply"),
                    (older_view, "a catalog whose person vitals view is another definition gets the schema's own from the 0.8.4 migration")):
        bad = fn(); failed += bool(bad)
        print(f"ok   {says}" if not bad else f"FAIL {fn.__name__}: " + "; ".join(bad))
    return failed
