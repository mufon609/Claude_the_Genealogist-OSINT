"""What every check module shares: the repo's paths, the scratch catalog, a tool run, and the failure collector.

A check runs on a scratch catalog under a temporary data root, never the owner's: scratch() makes one and points every
data path at it before treelib is imported. Nothing here names a person, a place or a record: the modules walk the data
under tests/fixtures/ and this file only carries them there.
"""
import os, shutil, sqlite3, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
BY = "agent:check"
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)

def scratch(keep=False):
    """A fresh catalog under a temporary data root; (root, db path). Every data path resolves under it once treelib is loaded."""
    d = tempfile.mkdtemp(prefix="tree-check-")
    os.environ["DATA_ROOT"] = d
    db = os.path.join(d, "catalog", "tree.db"); os.makedirs(os.path.dirname(db)); os.makedirs(os.path.join(d, "inbox"))
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "initdb.py"), "--db", db], capture_output=True, text=True)
    if r.returncode: sys.exit(f"initdb failed:\n{r.stdout}{r.stderr}")
    import treelib; treelib.DATA_ROOT = d
    return d, db

def connect(db):
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    return cx

def run(*args):
    """A tool run as a subprocess, its stdout; a failure raises with everything it printed."""
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=os.environ)
    if r.returncode: raise RuntimeError(f"{os.path.basename(args[0])} failed:\n{r.stdout}{r.stderr}")
    return r.stdout

def tool(name): return os.path.join(TOOLS, name)

def done(d, keep, label):
    """Leaves the scratch in place and says where when asked, removes it otherwise."""
    if keep: print(f"{label} scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)

class Fails(list):
    """The failures a check found: fail(ok, why) records why when ok is false."""
    def __call__(self, ok, why):
        if not ok: self.append(why)
        return bool(ok)

def whole(cx):
    """The scratch catalog's integrity and foreign keys, as one failure text or None."""
    ok = cx.execute("PRAGMA integrity_check").fetchone()[0]; fk = cx.execute("PRAGMA foreign_key_check").fetchall()
    return None if ok == "ok" and not fk else f"scratch catalog: integrity {ok}, foreign keys {len(fk)}"
