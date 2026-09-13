"""Shared helpers for tree tools: ULIDs, timestamps, GEDCOM date parsing, data paths.

ROOT is the repository. DATA_ROOT is where the data directories live (archive/,
derivatives/, inbox/, trees/<slug>/imports, trees/<slug>/exports): the
repository by default, or the directory named by the environment variable
DATA_ROOT, so a scratch run keeps its files apart from the owner's.
"""
import datetime as dt, hashlib, json, os, re, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.abspath(os.environ.get("DATA_ROOT") or ROOT)
USER_AGENT = "tree-genealogy-dev/0.1 (personal genealogy research; single user)"   # sent on every request the tools make
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_last_ulid = [0, 0]                                   # (milliseconds, random part) of the id minted last, so ids stay in order within a millisecond

def ulid() -> str:
    """A ULID: 48 bits of milliseconds then 80 random bits, base32, so ids sort in the order they were minted. Within one
    millisecond (or if the clock steps back) the random part counts up from the last id instead, the spec's monotonic rule,
    so two rows written by one process in the same millisecond still compare in the order they were written."""
    ms = int(time.time() * 1000)
    if ms <= _last_ulid[0]: ms, rand = _last_ulid[0], _last_ulid[1] + 1
    else: rand = int.from_bytes(os.urandom(10), "big")
    _last_ulid[:] = [ms, rand]
    n = (ms << 80) | rand
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

def archive_dir() -> str:
    return os.path.join(DATA_ROOT, "archive")

def inbox_dir() -> str:
    return os.path.join(DATA_ROOT, "inbox")

def derivatives_dir() -> str:
    return os.path.join(DATA_ROOT, "derivatives")

def object_path(sha: str) -> str:
    return os.path.join(archive_dir(), "objects", "sha256", sha[:2], sha[2:4], sha)

def manifest_path(sha: str) -> str:
    return os.path.join(archive_dir(), "manifests", "sha256", sha[:2], sha[2:4], sha + ".json")

# ---------------------------------------------------------------- GEDCOM dates
_MONTHS = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}
_QUAL = {"abt":"about","about":"about","est":"estimated","cal":"calculated",
         "bef":"before","bfr":"before","before":"before","aft":"after","after":"after"}

def _ymd(s: str):
    """'14 Mar 1852' | 'Mar 1852' | '1852' | '1701/02' | '10/12/1939' (month first, as US records write it) -> (iso, calendar) or (None,None)."""
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
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        mo, d, y = (int(x) for x in m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}", "gregorian"
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


# ---------------------------------------------------------------- archive
def redistributable(terms):
    """Whether bytes archived under a registry row's terms may leave the archive (a GEDZIP export, a shared page): the terms say
    public domain (or PD, the Archive's own terms for its books and newspapers), or a government record (public record, or
    Public alone, a public body's own site). Everything else, a vendor's terms of service, a page's contributor terms, family-
    held material, stays false."""
    t = (terms or "").strip()
    return bool(re.search(r"\bpublic domain\b|\bPD\b|\bpublic record\b", t, re.I) or t.lower() == "public")

def archive_object(cx, data: bytes, *, mime, source_id, collection_id, locator_kind, locator_value, retrieved_by, terms, cost, trust_tier,
                   original_filename=None, notes=None, http=None, collection_name=None, pages=1):
    """Put bytes in the archive: the object, its manifest, the artifact row and its local copy. Bytes already archived are left as
    they are (artifact rows are insert-only). The redistributable flag comes from the source row's terms (redistributable), and
    the manifest names the row that said so. Returns (sha256, True when the object is new)."""
    sha = hashlib.sha256(data).hexdigest(); ts = now()
    if cx.execute("SELECT 1 FROM artifact WHERE sha256=?", (sha,)).fetchone(): return sha, False
    redist = redistributable(terms)
    manifest = {"schema_version": "0.1.0", "sha256": sha, "bytes": len(data), "mime": mime, "source_id": source_id, "collection": collection_name,
                "locator": {"kind": locator_kind, "value": locator_value}, "retrieved_at": ts, "retrieved_by": retrieved_by, "http": http,
                "rights": {"terms": terms or "unknown", "redistributable": redist, "cost": cost or "unknown", **({"redistributable_by": source_id} if redist else {})}, "trust_tier": trust_tier,
                "original_filename": original_filename, "pages": pages, "notes": notes or ""}
    manifest = {k: v for k, v in manifest.items() if v is not None}
    dst, man = object_path(sha), manifest_path(sha)
    os.makedirs(os.path.dirname(dst), exist_ok=True); os.makedirs(os.path.dirname(man), exist_ok=True)
    with open(dst, "wb") as fh: fh.write(data)
    with open(man, "w", encoding="utf-8") as fh: json.dump(manifest, fh, ensure_ascii=False, indent=2)
    cx.execute("""INSERT INTO artifact (sha256,byte_size,mime,source_id,collection_id,locator_kind,locator_value,retrieved_at,retrieved_by,terms,redistributable,cost,trust_tier,original_filename,page_count,manifest_json,created_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (sha, len(data), mime, source_id, collection_id, locator_kind, locator_value, ts, retrieved_by,
                                                                  manifest["rights"]["terms"], redist, manifest["rights"]["cost"], trust_tier, original_filename, pages, dumps(manifest), ts))
    cx.execute("INSERT INTO artifact_copy (artifact_sha256,target_name,stored_at,last_verified,verify_ok) VALUES (?,?,?,?,?)", (sha, "local", ts, ts, True))
    return sha, True


# ---------------------------------------------------------------- trees / profiles
ACTIVE_TREE_FILE = os.path.join(DATA_ROOT, "catalog", ".active-tree")

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
    """The tree's folder, holding its README: in the repository, or under DATA_ROOT for a scratch run."""
    return os.path.join(DATA_ROOT, "trees", slug)

def imports_dir(slug: str) -> str:
    """The tree's named copies of imported files, under DATA_ROOT."""
    return os.path.join(DATA_ROOT, "trees", slug, "imports")

def exports_dir(slug: str) -> str:
    return os.path.join(DATA_ROOT, "trees", slug, "exports")
