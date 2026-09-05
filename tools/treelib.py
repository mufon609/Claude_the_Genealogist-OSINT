"""Shared helpers for tree tools: ULIDs, timestamps, GEDCOM date parsing, archive paths."""
import datetime as dt, hashlib, json, os, re, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def ulid() -> str:
    n = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    out = []
    for _ in range(26):
        out.append(_B32[n & 31]); n >>= 5
    return "".join(reversed(out))

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def object_path(sha: str) -> str:
    return os.path.join(ROOT, "archive", "objects", "sha256", sha[:2], sha[2:4], sha)

def manifest_path(sha: str) -> str:
    return os.path.join(ROOT, "archive", "manifests", "sha256", sha[:2], sha[2:4], sha + ".json")

# ---------------------------------------------------------------- GEDCOM dates
_MONTHS = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}
_QUAL = {"abt":"about","about":"about","est":"estimated","cal":"calculated",
         "bef":"before","bfr":"before","before":"before","aft":"after","after":"after"}

def _ymd(s: str):
    """'14 Mar 1852' | 'Mar 1852' | '1852' | '1701/02' -> (iso, calendar) or (None,None)."""
    s = s.strip().rstrip(".")
    m = re.fullmatch(r"(\d{4})/(\d{2})", s)                       # dual year 1701/02
    if m:
        return f"{int(m.group(1))+1:04d}", "dual"
    m = re.fullmatch(r"(?:(\d{1,2})\s+)?([A-Za-z]+)\.?\s+(\d{3,4})", s)
    if m:
        d, mon, y = m.groups()
        mi = _MONTHS.get(mon.lower()[:3])
        if mi:
            out = f"{int(y):04d}-{mi:02d}"
            if d: out += f"-{int(d):02d}"
            return out, "gregorian"
    m = re.fullmatch(r"(\d{3,4})", s)
    if m:
        return f"{int(m.group(1)):04d}", "gregorian"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s, "gregorian"
    return None, None

def parse_gedcom_date(text: str):
    """Return dict(date_start, date_end, date_qualifier, calendar). Unparseable -> all None."""
    res = {"date_start": None, "date_end": None, "date_qualifier": None, "calendar": "gregorian"}
    if not text:
        return res
    t = text.strip()
    tl = t.lower()
    m = re.fullmatch(r"bet\.?\s+(.+?)\s+and\s+(.+)", tl)
    if m:
        a, ca = _ymd(m.group(1)); b, cb = _ymd(m.group(2))
        res.update(date_start=a, date_end=b, date_qualifier="between", calendar=ca or cb or "unknown"); return res
    m = re.fullmatch(r"from\s+(.+?)\s+to\s+(.+)", tl)
    if m:
        a, ca = _ymd(m.group(1)); b, cb = _ymd(m.group(2))
        res.update(date_start=a, date_end=b, date_qualifier="between", calendar=ca or cb or "unknown"); return res
    m = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", tl)                  # 1852-1853
    if m:
        res.update(date_start=m.group(1), date_end=m.group(2), date_qualifier="between"); return res
    m = re.fullmatch(r"(abt|about|est|cal|bef|bfr|before|aft|after)\.?\s+(.+)", tl)
    if m:
        v, cal = _ymd(m.group(2))
        q = _QUAL[m.group(1)]
        if v:
            res.update(date_qualifier=q, calendar=cal)
            if q == "before": res["date_end"] = v
            else: res["date_start"] = v
            return res
        res["calendar"] = "unknown"; return res
    v, cal = _ymd(t)
    if v:
        res.update(date_start=v, date_qualifier="exact", calendar=cal); return res
    m = re.match(r"^(\d{1,2}\s+[A-Za-z]+\.?\s+\d{4})", t)          # "30 May 1758New Goshenhoppen"
    if m:
        v, cal = _ymd(m.group(1))
        if v:
            res.update(date_start=v, date_qualifier="exact", calendar=cal); return res
    res["calendar"] = "unknown"
    return res

# ---------------------------------------------------------------- GEDCOM lines
class Node:
    __slots__ = ("level", "xref", "tag", "value", "children")
    def __init__(self, level, xref, tag, value):
        self.level, self.xref, self.tag, self.value, self.children = level, xref, tag, value, []
    def first(self, tag):
        for c in self.children:
            if c.tag == tag: return c
        return None
    def all(self, tag):
        return [c for c in self.children if c.tag == tag]
    def val(self, tag, default=None):
        c = self.first(tag); return c.value if c else default

_LINE = re.compile(r"^(\d+)\s+(?:(@[^@]+@)\s+)?([A-Za-z0-9_]+)(?:\s(.*))?$")

def parse_gedcom(path: str):
    """Return list of level-0 Nodes with CONC/CONT folded into values."""
    roots, stack = [], []
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.strip(): continue
            m = _LINE.match(line)
            if not m: continue
            level, xref, tag, value = int(m.group(1)), m.group(2), m.group(3), m.group(4) or ""
            if tag in ("CONC", "CONT") and stack:
                parent = stack[-1]
                parent.value = (parent.value or "") + ("\n" if tag == "CONT" else "") + value
                continue
            node = Node(level, xref, tag, value)
            while stack and stack[-1].level >= level: stack.pop()
            if stack: stack[-1].children.append(node)
            else: roots.append(node)
            stack.append(node)
    return roots

def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


# ---------------------------------------------------------------- trees / profiles
ACTIVE_TREE_FILE = os.path.join(ROOT, "catalog", ".active-tree")

def active_tree_slug(explicit=None):
    """Resolution order: --tree flag, $TREE, catalog/.active-tree."""
    if explicit: return explicit
    if os.environ.get("TREE"): return os.environ["TREE"]
    try:
        with open(ACTIVE_TREE_FILE, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except FileNotFoundError:
        return None

def resolve_tree(cx, explicit=None):
    """Return (tree_id, slug) or exit with guidance."""
    slug = active_tree_slug(explicit)
    if not slug:
        raise SystemExit("no active tree: pass --tree <slug>, set $TREE, or run tools/tree.py use <slug>")
    row = cx.execute("SELECT id, slug FROM tree WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise SystemExit(f"tree '{slug}' does not exist (tools/tree.py list)")
    return row[0], row[1]

def tree_dir(slug: str) -> str:
    return os.path.join(ROOT, "trees", slug)
