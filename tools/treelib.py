"""Shared helpers for tree tools: ULIDs, timestamps, GEDCOM date parsing, data paths.

ROOT is the repository. DATA_ROOT is where the data directories live (catalog/,
archive/, derivatives/, inbox/, downloads/, trees/<slug>/imports, trees/<slug>/exports):
the repository by default, or the directory named by the environment variable
DATA_ROOT, so a scratch run keeps its files apart from the owner's. DB is the
catalog every tool opens when no --db is given, the one under DATA_ROOT; a --db
outside DATA_ROOT is refused (in_data_root).
"""
import codecs, datetime as dt, hashlib, json, os, re, shutil, sqlite3, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.abspath(os.environ.get("DATA_ROOT") or ROOT)
DB = os.path.join(DATA_ROOT, "catalog", "tree.db")   # the default --db: a scratch run that sets DATA_ROOT opens its own catalog, never the owner's
SCHEMA_VERSION = "0.8.7"   # schema/catalog.sql's own; a catalog whose schema_migration lacks it is behind the code (tools/initdb.py --migrate)
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

def ulid_time(id_: str) -> str:
    """The moment a ULID was minted, from its first ten characters (the milliseconds), written as now() writes one."""
    ms = 0
    for ch in id_[:10]: ms = ms * 32 + _B32.index(ch)
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    """Where collect moves the pages it takes and where the inbox's attach reads them from: the data root's own inbox/ folder,
    created on first use, so a fresh data root collects and attaches as the owner's does."""
    d = os.path.join(DATA_ROOT, "inbox"); os.makedirs(d, exist_ok=True)
    return d

def downloads_dir() -> str:
    """Where the owner's browser saves the pages a turn waits on, and where collect takes them from: the data root's own downloads/
    folder, created on first use. No tool reads the owner's own download folder."""
    d = os.path.join(DATA_ROOT, "downloads"); os.makedirs(d, exist_ok=True)
    return d

def derivatives_dir() -> str:
    return os.path.join(DATA_ROOT, "derivatives")

def year_field(key: str) -> bool:
    """Whether a step's field holds a year: `year`, or a name ending in `_year` (birth_year, death_year)."""
    return key == "year" or key.endswith("_year")

_YEAR_IN = re.compile(r"(?<!\d)(1[5-9]\d\d|20\d\d)(?!\d)")

def year_in(value):
    """The year a stored value gives, read tolerantly: a whole number as it is, else the first year of four digits (1500 to
    2099) standing alone in its text ("1880", "1880?", "abt 1880" all 1880); None when it gives none."""
    if isinstance(value, int) and not isinstance(value, bool): return value
    m = _YEAR_IN.search(str(value if value is not None else ""))
    return int(m.group(1)) if m else None

def free_name(folder: str, name: str) -> str:
    """A name in the folder that no file holds: the name itself when it is free, else the name with " (2)", " (3)" ... before its
    extension, the first that is free (the shape Chrome gives a second download of one name). A file of the same name already
    there is never written over."""
    if not os.path.lexists(os.path.join(folder, name)): return name
    stem, ext = os.path.splitext(name); n = 2
    while os.path.lexists(os.path.join(folder, f"{stem} ({n}){ext}")): n += 1
    return f"{stem} ({n}){ext}"

def move_free(src: str, folder: str, name: str = None) -> str:
    """The file moved into the folder under its own name (or `name`), or under free_name's free one when that name is taken;
    the path it now has. Every move of a saved page or a filed original goes through here, so none overwrites another."""
    os.makedirs(folder, exist_ok=True)
    dst = os.path.join(folder, free_name(folder, name or os.path.basename(src)))
    shutil.move(src, dst)
    return dst

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
_HEADER_CHAR = re.compile(r"^1[ \t]+CHAR[ \t]+(\S[^\r\n]*?)[ \t]*$", re.M)
CHAR_CODECS = {"UTF-8": "utf-8", "UTF8": "utf-8", "ASCII": "utf-8", "ANSI": "cp1252"}   # a header's CHAR value to the codec that reads it; ASCII is read as UTF-8, which is the same bytes below 128

def gedcom_codec(raw: bytes, path: str):
    """(codec, what the file says it is) for the bytes of a GEDCOM file: a byte order mark first (UTF-8, UTF-16 either way),
    then UTF-16 without one (the first line's "0" followed or preceded by a zero byte), then the header's CHAR line; a file
    with no CHAR line is UTF-8, as GEDCOM 7 writes it. A character set this reads no further (ANSEL, the old DOS and
    Macintosh sets) and a UNICODE file that is not UTF-16 are refused, never guessed at."""
    if raw.startswith(codecs.BOM_UTF8): return "utf-8-sig", "UTF-8 with a byte order mark"
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE): return "utf-16", "UTF-16 with a byte order mark"
    if raw[:2] == b"0\x00": return "utf-16-le", "UTF-16, little-endian, no byte order mark"
    if raw[:2] == b"\x000": return "utf-16-be", "UTF-16, big-endian, no byte order mark"
    m = _HEADER_CHAR.search(raw[:65536].decode("latin-1"))
    char = m.group(1).upper() if m else "UTF-8"
    if char in CHAR_CODECS: return CHAR_CODECS[char], f"CHAR {char}"
    if char in ("UNICODE", "UTF-16"): raise SystemExit(f"{path}: its header says CHAR {char}, UTF-16, but the file has no UTF-16 byte order mark and its bytes are not UTF-16: re-export it as UTF-8")
    raise SystemExit(f"{path}: its header says CHAR {char}, a character set this does not read: re-export the file as UTF-8")

def parse_gedcom(path: str):
    """Return list of level-0 Nodes with CONC/CONT folded into values. The file is read in the encoding its own bytes and header
    say (gedcom_codec) and refused, naming the byte, when they do not fit it: a character is never replaced."""
    roots, stack = [], []
    with open(path, "rb") as fh: data = fh.read()
    codec, said = gedcom_codec(data, path)
    try: text = data.decode(codec)
    except UnicodeDecodeError as e: raise SystemExit(f"{path}: {said}, but byte {e.start} is not valid {codec} ({e.reason}): the file is mislabelled or damaged")
    for line in re.split(r"\r\n|\r|\n", text):                   # a line ends in any of the three; only these, never another Unicode separator inside a value
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
                   original_filename=None, notes=None, http=None, collection_name=None, pages=1, derived_from=None):
    """Put bytes in the archive: the object, its manifest, the artifact row and its local copy. Bytes already archived are left as
    they are (artifact rows are insert-only). The redistributable flag comes from the source row's terms (redistributable), and
    the manifest names the row that said so. derived_from is the sha256 of the artifact these bytes were computed from (a
    surname's own rows out of a whole downloaded file): the derivative gets its own row and its own extraction, never the
    parent's, so re-deriving the same rows from the same parent reuses the same bytes and the same row, and a different
    surname's rows never supersede this one's. Returns (sha256, True when the object is new)."""
    sha = hashlib.sha256(data).hexdigest(); ts = now()
    if cx.execute("SELECT 1 FROM artifact WHERE sha256=?", (sha,)).fetchone(): return sha, False
    redist = redistributable(terms)
    manifest = {"schema_version": "0.1.0", "sha256": sha, "bytes": len(data), "mime": mime, "source_id": source_id, "collection": collection_name,
                "locator": {"kind": locator_kind, "value": locator_value}, "retrieved_at": ts, "retrieved_by": retrieved_by, "http": http,
                "rights": {"terms": terms or "unknown", "redistributable": redist, "cost": cost or "unknown", **({"redistributable_by": source_id} if redist else {})}, "trust_tier": trust_tier,
                "original_filename": original_filename, "pages": pages, "derived_from": derived_from, "notes": notes or ""}
    manifest = {k: v for k, v in manifest.items() if v is not None}
    dst, man = object_path(sha), manifest_path(sha)
    os.makedirs(os.path.dirname(dst), exist_ok=True); os.makedirs(os.path.dirname(man), exist_ok=True)
    with open(dst, "wb") as fh: fh.write(data)
    with open(man, "w", encoding="utf-8") as fh: json.dump(manifest, fh, ensure_ascii=False, indent=2)
    cx.execute("""INSERT INTO artifact (sha256,byte_size,mime,source_id,collection_id,locator_kind,locator_value,retrieved_at,retrieved_by,terms,redistributable,cost,trust_tier,original_filename,page_count,derived_from,manifest_json,created_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (sha, len(data), mime, source_id, collection_id, locator_kind, locator_value, ts, retrieved_by,
                                                                  manifest["rights"]["terms"], redist, manifest["rights"]["cost"], trust_tier, original_filename, pages, derived_from, dumps(manifest), ts))
    cx.execute("INSERT INTO artifact_copy (artifact_sha256,target_name,stored_at,last_verified,verify_ok) VALUES (?,?,?,?,?)", (sha, "local", ts, ts, True))
    return sha, True


def write_text_whole(path, text):
    """The file at path holds text, whole: written to a file beside it that replaces it in one step, so a stop in the middle of the
    write leaves the file as it was and never half of the new one."""
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh: fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.remove(tmp)

def write_json_whole(path, data, **kw):
    """The file at path holds data as JSON, whole (write_text_whole): the text is made first, so a value that cannot be written
    raises before the file is touched."""
    write_text_whole(path, json.dumps(data, **kw))

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

def in_data_root(db: str) -> str:
    """The catalog path when it lies inside the data root; a --db outside it is refused. Every tool writes the archive, the inbox,
    the downloads folder and the tree's imports beside the catalog under DATA_ROOT, so a catalog elsewhere would have its records
    archived into another data root's archive (a scratch catalog into the owner's)."""
    root, path = os.path.realpath(DATA_ROOT), os.path.realpath(db)
    if os.path.commonpath([root, path]) != root:
        raise SystemExit(f"{db} is outside the data root {DATA_ROOT}: run with DATA_ROOT set to the folder whose catalog/ holds it (DATA_ROOT=<dir> python3 tools/<tool>.py)")
    return db

def connect(db: str, rows: bool = False) -> sqlite3.Connection:
    """The catalog a tool works on, foreign keys on, sqlite3.Row rows when asked. Refused when it lies outside the data root
    (in_data_root), when no catalog is there or when it is behind the code's schema, so no tool reads or writes a catalog its
    migrations have not reached, or archives its records into another data root."""
    in_data_root(db)
    if not os.path.exists(db): raise SystemExit(f"no catalog at {db}: create one with python3 tools/initdb.py --db {db}")
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON")
    try: have = {v for v, in cx.execute("SELECT version FROM schema_migration")}
    except sqlite3.OperationalError: raise SystemExit(f"{db} is not a catalog (no schema_migration table)")
    if SCHEMA_VERSION not in have:
        raise SystemExit(f"{db} is behind the code's schema {SCHEMA_VERSION}: back it up, then run python3 tools/initdb.py --migrate --db {db}")
    if rows: cx.row_factory = sqlite3.Row
    return cx

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
