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

def check(keep, show):
    """Each guard as one line: ok when it holds, FAIL with every reason when it does not. Returns how many failed."""
    failed = 0
    for fn, says in ((screen_links, "the person screen writes a URL into a link only through its `web` helper, which keeps a web address, escaped, and drops any other scheme"),):
        bad = fn(); failed += bool(bad)
        print(f"ok   {says}" if not bad else f"FAIL {fn.__name__}: " + "; ".join(bad))
    return failed
