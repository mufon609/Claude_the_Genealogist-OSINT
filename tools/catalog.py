"""Read-only access to a tree's people, events, places, citations and families.

Shared by every tool and by the person screen. Nothing here writes.
"""
import calendar, collections, csv, datetime, json, os, re, sqlite3, sys, unicodedata, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

US_STATE_TABLE = {   # each state and the District of Columbia with the abbreviations records write for it, the postal code and the older ones (Penna, Mass., N.J., W.Va.), set down without periods or spaces since a word is looked up without them
    "Alabama": ("al", "ala"), "Alaska": ("ak",), "Arizona": ("az", "ariz"), "Arkansas": ("ar", "ark"),
    "California": ("ca", "cal", "calif"), "Colorado": ("co", "col", "colo"), "Connecticut": ("ct", "conn"),
    "Delaware": ("de", "del"), "District of Columbia": ("dc",), "Florida": ("fl", "fla"), "Georgia": ("ga",),
    "Hawaii": ("hi",), "Idaho": ("id",), "Illinois": ("il", "ill"), "Indiana": ("in", "ind"), "Iowa": ("ia",),
    "Kansas": ("ks", "kan", "kans"), "Kentucky": ("ky",), "Louisiana": ("la",), "Maine": ("me",), "Maryland": ("md",),
    "Massachusetts": ("ma", "mass"), "Michigan": ("mi", "mich"), "Minnesota": ("mn", "minn"), "Mississippi": ("ms", "miss"),
    "Missouri": ("mo",), "Montana": ("mt", "mont"), "Nebraska": ("ne", "neb", "nebr"), "Nevada": ("nv", "nev"),
    "New Hampshire": ("nh",), "New Jersey": ("nj",), "New Mexico": ("nm", "nmex"), "New York": ("ny",),
    "North Carolina": ("nc",), "North Dakota": ("nd", "ndak"), "Ohio": ("oh",), "Oklahoma": ("ok", "okla"),
    "Oregon": ("or", "ore", "oreg"), "Pennsylvania": ("pa", "penn", "penna"), "Rhode Island": ("ri",),
    "South Carolina": ("sc",), "South Dakota": ("sd", "sdak"), "Tennessee": ("tn", "tenn"), "Texas": ("tx", "tex"),
    "Utah": ("ut",), "Vermont": ("vt",), "Virginia": ("va",), "Washington": ("wa", "wash"), "West Virginia": ("wv", "wva"),
    "Wisconsin": ("wi", "wis", "wisc"), "Wyoming": ("wy", "wyo"),
}
US_STATES = {name.lower() for name in US_STATE_TABLE}
_STATE_WORDS = {**{re.sub(r"\s", "", name.lower()): name for name in US_STATE_TABLE},
                **{abbr: name for name, abbrs in US_STATE_TABLE.items() for abbr in abbrs}}

def us_state(word):
    """The state (or the District of Columbia) a word names, written as its name is (New Jersey): the word is the name or an
    abbreviation records write for it (NJ, N.J., Penna, Mass., W. Va.), in any case, with or without periods and spaces.
    None for any other word."""
    return _STATE_WORDS.get(re.sub(r"[.\s]", "", (word or "").lower()))

US_NAMES = {"united states","usa","united states of america","us","british colonies","north america"}

def year(s): return int(s[:4]) if s and s[:4].isdigit() else None

SUFFIX = {"jr", "sr", "ii", "iii", "iv", "esq"}

def split_name(text):
    """(given names, surname, suffix) from a name as written: "John Alan Doe Jr" is given "John Alan",
    surname "Doe", suffix "Jr"; "Doe, John A" (surname first, as an index writes it) the same way round. None for a
    part that is not there."""
    t = re.sub(r"[\u201c\u201d\"']", " ", text or "").strip()
    m = re.match(r"^([^,\s]+)\s*,\s*(.+)$", t)
    if m: t = f"{m.group(2)} {m.group(1)}"
    parts = [p for p in t.replace(",", " ").split() if p]
    suffix = None
    if len(parts) > 1 and parts[-1].strip(".").lower() in SUFFIX: suffix = parts.pop()
    if not parts: return None, None, suffix
    if len(parts) == 1: return parts[0], None, suffix
    return " ".join(parts[:-1]), parts[-1], suffix

def holders():
    """Free holders of the Ancestry collections the tree cites (data/holders.csv): {dbid: [row, ...]}, first row preferred."""
    out = {}
    with open(os.path.join(ROOT, "data", "holders.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh): out.setdefault(r["AncestryDbid"], []).append(r)
    return out

def dbid_of(apid):
    m = re.match(r"^\d+,(\d+)::(\d+)$", apid or "")
    return m.group(1) if m else None

def first_value(v):
    """A query field's own value: itself, or its first name when it carries several accurate names for a place
    (checklist.PLACES, plan.citation_fields), the citation's own string or the one valid at year."""
    return v[0] if isinstance(v, list) else v

def browse_only(holder):
    """Whether a free holder's own pages carry no search or record page the page-saves-itself method can save: a
    FamilySearch images-only collection (fs_images), browsed by hand, film by film. Such a step stays on the plan,
    fetchable, with the reason in its rationale, but a browser session is never sent to it: nobody can save it that
    way (data/DATA-SOURCES.md §5)."""
    return bool(holder) and holder["HolderKind"] == "fs_images"

PAGE_PART = re.compile(r"^([A-Za-z][A-Za-z .]{0,40}): (.+)$")

def page_key(apid, page):
    """The census page a citation names, from the citation's own details: the collection with the year, census place,
    enumeration district and page (sheet) parts of its page text. None when the details do not name one page (no year, place
    or page part), so a certificate box or a number range never counts as one page."""
    parts = {}
    for part in (page or "").split("; "):
        m = PAGE_PART.match(part.strip())
        if m: parts.setdefault(m.group(1).lower(), m.group(2).strip())
    yr = parts.get("year") or parts.get("residence date")
    place = parts.get("census place") or next((v for k, v in parts.items() if k.startswith("home in ")), None)
    sheet = parts.get("page") or parts.get("sheet") or parts.get("sheet number")
    if not (yr and place and sheet): return None
    return (dbid_of(apid), yr, place, parts.get("enumeration district"), sheet)

def page_groups(cx):
    """{record id: the record ids whose citations name the same census page}, over every citation in the catalog. Ancestry
    cites each household member under their own record id; those ids are one page."""
    by_key = {}
    for apid, page in cx.execute("""SELECT DISTINCT json_extract(notes,'$.apid'), json_extract(notes,'$.page') FROM assertion WHERE notes LIKE '{"apid":%'"""):
        k = page_key(apid, page)
        if k: by_key.setdefault(k, set()).add(apid)
    return {a: frozenset(g) for g in by_key.values() for a in g}

def same_page(cx, apid, groups=None):
    """The record ids naming the same census page as this one, itself included."""
    return set((page_groups(cx) if groups is None else groups).get(apid) or {apid})

def soundex(s):
    """The American Soundex code of a surname, the index makers' own way of saying two spellings are one name."""
    s = re.sub(r"[^a-z]", "", (s or "").lower())
    if not s: return ""
    codes = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"), **dict.fromkeys("dt", "3"), "l": "4", **dict.fromkeys("mn", "5"), "r": "6"}
    out, last = s[0].upper(), codes.get(s[0], "")
    for ch in s[1:]:
        c = codes.get(ch, "")
        if c and c != last: out += c
        if ch not in "hw": last = c
    return (out + "000")[:4]

def edits(a, b):
    """The edit distance between two keys."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def same_surname(a, b):
    """Whether two surname keys are one name: written the same; a spelling variant (the same Soundex code and at most two
    edits apart, so Rowan and Rowen, Reid and Reed, Kriebel and Krebel); or one letter apart in a name of five letters or
    more, whatever the Soundex, an indexer's slip (Rowau for Rowan), as long as the first letter stands: a substitution, a
    missing or an extra letter, never Cowan for Rowan. Returns "" when they differ, "agrees" when written the same, "variant"
    for a spelling variant, "one letter apart" for the slip."""
    if not a or not b: return ""
    if a == b: return "agrees"
    if len(a) >= 4 and len(b) >= 4 and soundex(a) == soundex(b) and edits(a, b) <= 2: return "variant"
    if len(a) >= 5 and len(b) >= 5 and a[0] == b[0] and edits(a, b) == 1: return "one letter apart"
    return ""

def name_parts(text):
    """(the first given name's key, the keys of every later word) of a name as written, a title (Mr, Mrs, Dr) dropped; any later
    word may be the surname (a memorial writes a married woman's birth surname inside her name)."""
    parts = [key(x) for x in re.sub(r"^(mr|mrs|miss|ms|dr)\.?\s+", "", (text or "").strip(), flags=re.I).split() if key(x)]
    return (parts[0], parts[1:]) if parts else ("", [])

def person_named(cx, person_id, people):
    """Whether a record that names these people names this person. Each is a name as written or (name, birth year): one of them
    carries the person's first given name and a surname the tree holds for them, as written or as a spelling variant, or a wife's
    husband's surname, and where the record and the tree both give a birth year the two lie within three years (a calculated
    year allows two; a five-year-old and her aunt of the same name are not one person)."""
    keys = [(key((g or "").split()[0]) if g else "", key(sn)) for g, sn in cx.execute("SELECT given, surname FROM person_name WHERE person_id=?", (person_id,))]
    born = next((year(r[0]) for r in cx.execute("""SELECT e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                   WHERE ep.person_id=? AND e.event_type='Birth' AND e.date_start IS NOT NULL""", (person_id,))), None)
    keys += [(g, key((sp or "").split()[-1])) for g, _ in list(keys) for sp, in cx.execute("""SELECT p.display_name FROM family_member fm JOIN family_member x ON x.family_id=fm.family_id AND x.role='partner' AND x.person_id<>fm.person_id
                                                                                                   JOIN person p ON p.id=x.person_id WHERE fm.person_id=? AND fm.role='partner'""", (person_id,)) if sp]
    for item in people:
        n, y = item if isinstance(item, tuple) else (item, None)
        pg, rest = name_parts(n)
        if not (pg and any(pg == g and any(same_surname(t, s) for t in rest) for g, s in keys)): continue
        if y and born and abs(y - born) > 3: continue
        return True
    return False

def page_people(cx, sha):
    """The people a record page holds, as written: (name, birth year or None) per persona of its current extraction (the latest
    not superseded, not failed), the year from the persona's Birth fact, calculated from an age or given."""
    e = cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND status<>'failed' AND superseded_by IS NULL ORDER BY ran_at DESC LIMIT 1", (sha,)).fetchone()
    if not e: return []
    return [(n, year(b)) for n, b in cx.execute("""SELECT pe.name_text, (SELECT f.date_start FROM persona_fact f WHERE f.persona_id=pe.id AND f.fact_type='Birth' AND f.date_start IS NOT NULL LIMIT 1)
                                                   FROM persona pe WHERE pe.extraction_id=? ORDER BY pe.sequence""", (e[0],))]

def cited_persons(cx, apid):
    """The persons a citation sits on: the subject of every assertion carrying this record id, through the event's participant."""
    return [r[0] for r in cx.execute("""SELECT DISTINCT CASE a.subject_kind WHEN 'person' THEN a.subject_id
                     ELSE (SELECT ep.person_id FROM event_participant ep WHERE ep.event_id=a.subject_id AND ep.person_id IS NOT NULL LIMIT 1) END
                     FROM assertion a WHERE json_valid(a.notes) AND json_extract(a.notes,'$.apid')=?""", (apid,)) if r[0]]

def holds(cx, sha, groups=None):
    """The record ids an archived artifact holds. A sheet image or a schedule shows the whole sheet, so it holds every citation
    naming the sheet; an HTML record page shows one household, so it holds its own citation and those of the people it names
    (person_named against the page's personas), never another household's on the same sheet."""
    a = cx.execute("SELECT locator_kind, locator_value, mime FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if not a or a[0] != "apid" or not a[1]: return set()
    group = same_page(cx, a[1], groups)
    if not (a[2] or "").startswith("text/html"): return set(group)
    people = page_people(cx, sha)
    return {a[1]} | {x for x in group if x != a[1] and people and any(person_named(cx, p, people) for p in cited_persons(cx, x))}

def holdings(cx, groups=None):
    """[(sha256, the record id it was archived under, mime, the ids it holds, the people it holds or None for an image)] for every
    artifact archived under a record id, first archived first."""
    groups = page_groups(cx) if groups is None else groups
    return [(sha, own, mime or "", holds(cx, sha, groups), page_people(cx, sha) if (mime or "").startswith("text/html") else None)
            for sha, own, mime in cx.execute("SELECT sha256, locator_value, mime FROM artifact WHERE locator_kind='apid' AND locator_value IS NOT NULL ORDER BY retrieved_at, sha256")]

def held_for(cx, apid, person_id, holdings_=None):
    """The archived record that holds this citation for this person: an artifact archived under the id itself, a sheet image or a
    schedule naming the sheet, or a record page that names the person. None when the archive holds the sheet but not the
    person's household (a citation on a parent to the daughter's own record id is not held by the daughter's household page)."""
    for sha, own, mime, ids, people in (holdings(cx) if holdings_ is None else holdings_):
        if apid not in ids: continue
        if own == apid or people is None or person_named(cx, person_id, people): return sha
    return None

def held_apids(cx, groups=None):
    """{record id: sha256} for every citation whose record is in the archive: the id the record was archived under and every other
    id the artifact holds (holds: the whole sheet for an image, the household it names for a record page), the first archived winning."""
    groups = page_groups(cx) if groups is None else groups
    out = {}
    for sha, in cx.execute("SELECT sha256 FROM artifact WHERE locator_kind='apid' ORDER BY retrieved_at, sha256"):
        for a in holds(cx, sha, groups): out.setdefault(a, sha)
    return out

HOLDERS = None                                   # data/holders.csv, read once per process by fetch_target

def fetch_target(apid, url=None, fields=None):
    """Where a cited record is opened: {url, holder}. The citation's own memorial URL when the holder is Find a Grave; the free
    holder's own search prefilled from the step's fields (the citation's details, never the person's facts) when they are given,
    else its collection page; Ancestry's record page when no free holder is known (a membership is needed there)."""
    m = re.match(r"^\d+,(\d+)::(\d+)$", apid or "")
    if not m: return {"url": None, "holder": None}
    global HOLDERS
    if HOLDERS is None: HOLDERS = holders()
    h = (HOLDERS.get(m.group(1)) or [None])[0]
    if h and h["HolderKind"] == "memorial" and url: return {"url": url, "holder": h["HolderCollection"]}
    if h and h["HolderKind"] != "memorial": return {"url": holder_search(h, fields) or h["URL"], "holder": h["HolderCollection"]}
    return {"url": f"https://www.ancestry.com/discoveryui-content/view/{m.group(2)}:{m.group(1)}", "holder": "Ancestry"}

PLACEHOLDER = re.compile(r"\{(given|surname|name|title|year|date|mdy|place|city|url)\}")

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

def _mdy(date):
    """A citation's date ("27 Jan 1986") as Google Books' own cd_min/cd_max form ("1/27/1986"), month with no leading
    zero, day with none either; None when the date isn't day-month-year text."""
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})\b", date or "")
    if not m: return None
    mon = _MONTHS.get(m.group(2)[:3].lower())
    return f"{mon}/{int(m.group(1))}/{m.group(3)}" if mon else None

def holder_search(h, fields):
    """The holder's own search URL from a fetch step's fields (the citation's details, never the person's facts).
    fs_collection: FamilySearch's collection search as the site builds it (f.collectionId, q.givenName, q.surname, and for a
    census the year and place as q.residenceDate.from/to and q.residencePlace; the year from the collection's name when the
    citation gives none, the place from its census place or its city and county). fs_images: no search, the collection is
    browsed (None). url: the holder's search template in HolderKey with its placeholders filled from the citation ({given},
    {surname}, {name}, {title} from the book title or the citation text, {year}, {date}, {mdy} the publication date as
    Google Books' own cd_min/cd_max take it, {place}, {city}, {url} the citation's own URL), URL-encoded; None when a
    placeholder has no value, so the holder's own page opens instead. site: the National
    Archives 1950 site's name search. None when the fields carry nothing to ask with."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    given, surname, _ = split_name(v("name"))
    kind = h["HolderKind"]
    if kind == "fs_images": return None
    if kind == "url":
        tpl = h["HolderKey"] or ""
        if not tpl: return None
        year = v("year") or next((m.group(1) for k in ("publication date", "date", "event date") for m in [re.search(r"\b(1[5-9]\d\d|20\d\d)\b", v(k) or "")] if m), None)
        vals = {"given": given, "surname": surname, "name": " ".join(x for x in (given, surname) if x) or None, "title": v("book title") or v("title") or v("citation"),
                "year": year, "date": v("publication date") or v("date"), "mdy": _mdy(v("publication date") or v("date")),
                "place": first_value(v("publication place")) or first_value(v("census place")) or first_value(v("place")), "city": v("city"), "url": v("url")}
        if tpl == "{url}": return vals["url"]
        needed = set(PLACEHOLDER.findall(tpl))
        if any(not vals.get(k) for k in needed): return None
        return PLACEHOLDER.sub(lambda m: urllib.parse.quote(str(vals[m.group(1)]), safe=""), tpl)
    if not (given or surname): return None
    if kind == "fs_collection":
        q = [("f.collectionId", h["HolderKey"]), ("q.givenName", given or "")]
        yr = v("year") or (re.search(r"\b(1[78]\d\d|19\d\d)\b", h["HolderCollection"] or "") or [None, None])[1] if re.search(r"census", h["HolderCollection"] or "", re.I) else v("year")
        place = first_value(v("census place")) or ", ".join(x for x in (v("city"), v("county")) if x) or None
        if yr and place: q += [("q.residenceDate.from", yr), ("q.residenceDate.to", yr), ("q.residencePlace", place)]
        if surname: q.append(("q.surname", surname))
        return "https://www.familysearch.org/en/search/record/results?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    if h["HolderKey"] == "1950census.archives.gov": return "https://1950census.archives.gov/search/?" + urllib.parse.urlencode([("name", " ".join(x for x in (given, surname) if x))], quote_via=urllib.parse.quote)
    return None

def findagrave_search_url(fields):
    """The Find a Grave memorial search as the site's own form builds it, from a search step's fields: firstname (the first given
    name), lastname, the birth and death years each with the year filter at 3 (the audit narrows the result, not the search),
    includeMaidenName for a woman, linkedToName for the first spouse, orderby relevance; no location, which filters on the
    cemetery's place rather than the death place. None without a surname."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if not v("surname"): return None
    q = [("firstname", (v("given") or "").split()[0] if v("given") else ""), ("lastname", v("surname"))]
    if v("birth_year"): q += [("birthyear", str(v("birth_year"))), ("birthyearfilter", "3")]
    if v("death_year"): q += [("deathyear", str(v("death_year"))), ("deathyearfilter", "3")]
    if v("sex") == "F": q.append(("includeMaidenName", "true"))
    if v("spouses"): q.append(("linkedToName", v("spouses")[0]))
    q.append(("orderby", "r"))
    return "https://www.findagrave.com/memorial/search?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)

def familysearch_search_url(fields):
    """The FamilySearch record search as the site's own form builds it, from a search step's fields: q.givenName and q.surname,
    the birth year with the step's tolerance as q.birthLikeDate.from/to, a death year likewise, the state as q.anyPlace, the
    first spouse's names as q.spouseGivenName / q.spouseSurname, and for a census household step with a year the census
    collection itself as f.collectionId (data/holders.csv). None without a surname."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if not v("surname"): return None
    q = [("q.givenName", v("given") or ""), ("q.surname", v("surname"))]
    tol = ((fields or {}).get("birth_year") or {}).get("tolerance") or 2
    if v("birth_year"): q += [("q.birthLikeDate.from", str(int(v("birth_year")) - tol)), ("q.birthLikeDate.to", str(int(v("birth_year")) + tol))]
    if v("death_year"): q += [("q.deathLikeDate.from", str(int(v("death_year")) - tol)), ("q.deathLikeDate.to", str(int(v("death_year")) + tol))]
    if v("state"): q.append(("q.anyPlace", str(v("state")).title()))
    sp = (v("spouses") or [None])[0] if isinstance(v("spouses"), list) else v("spouse")
    sg, ss, _ = split_name(str(sp)) if sp else (None, None, None)
    if sg and ss: q += [("q.spouseGivenName", sg), ("q.spouseSurname", ss)]
    if v("year"):
        coll = next((h for rows in holders().values() for h in rows if h["HolderKind"] == "fs_collection" and h["HolderCollection"] == f"United States, Census, {v('year')}"), None)
        if coll: q.insert(0, ("f.collectionId", coll["HolderKey"]))
    return "https://www.familysearch.org/en/search/record/results?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)

def aad_search_url(fields):
    """The WWII Army enlistment file's fielded search at the National Archives (AAD), as the site's own form submits it: the
    name as the file writes it (SURNAME GIVEN), the year of birth as its two digits, fifty rows a page. The site answers a
    person's browser only, so the page is saved there and comes in through inbox/. None without a surname."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if not v("surname"): return None
    name = " ".join(x for x in (str(v("surname")).upper(), (str(v("given")).split()[0].upper() if v("given") else None)) if x)
    q = [("dt", "893"), ("sc", "24994,24995,24996,24998,24997,24993,24981,24983"), ("cat", "WR26"), ("tf", "F"), ("bc", ",sl,fd"), ("q", ""),
         ("nfo_24995", "V,24,1900"), ("op_24995", "0"), ("txt_24995", name)]
    if v("birth_year"): q += [("nfo_24983", "V,2,1900"), ("op_24983", "0"), ("txt_24983", f"{int(v('birth_year')) % 100:02d}")]
    q.append(("rpp", "50"))
    return "https://aad.archives.gov/aad/display-partial-records.jsp?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)

def hathitrust_search_url(fields):
    """HathiTrust's full-text search as its own form submits it: the first given name and the surname as a phrase, full view
    only. The site sits behind a browser challenge, so the results are read in the browser. None without a surname."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if not v("surname"): return None
    first = str(v("given")).split()[0] if v("given") else None
    q = [("q1", " ".join(x for x in (first, str(v("surname"))) if x)), ("anyall1", "phrase"), ("lmt", "ft")]
    return "https://babel.hathitrust.org/cgi/ls?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)

def search_target(sources, fields):
    """Where an assisted search step is run by hand: {url, holder} for a source whose own search the tool can build from the
    step's fields (Find a Grave, E01; FamilySearch, D03), else nothing."""
    for sid, build, holder in (("E01", findagrave_search_url, "Find a Grave"), ("F01", aad_search_url, "National Archives AAD"), ("D03", familysearch_search_url, "FamilySearch"),
                               ("L01", hathitrust_search_url, "HathiTrust")):
        if sid in (sources or []):
            u = build(fields)
            if u: return {"url": u, "holder": holder}
    return {"url": None, "holder": None}

# ---------------------------------------------------------------- comparing a record's value with the tree's
COUNTRY = re.compile(r"\b(united states of america|united states|u\.s\.a\.|u\.s\.|usa|us)\b", re.I)

def key(s): return re.sub(r"[^a-z]", "", (s or "").lower())
def date_verdict(rec, tree):
    """A record date against the tree's, each {"start", "text", "qualifier"}: (verdict, note). Both full dates: compared as dates,
    a different day in the same year disagrees. Otherwise the years: a bare year against a full date agrees on the year only and
    the note says which side gives only a year; a date marked about, estimated or calculated on either side agrees within two years."""
    rs, ts = (rec or {}).get("start"), (tree or {}).get("start")
    if not rs or not ts: return "absent", None
    if len(rs) == 10 and len(ts) == 10: return ("agrees", None) if rs == ts else ("disagrees", "same year, different day" if rs[:4] == ts[:4] else None)
    tol = 2 if (rec or {}).get("qualifier") in ("about", "estimated", "calculated") or (tree or {}).get("qualifier") in ("about", "estimated", "calculated") else 0   # either side approximate: two years
    if abs(int(rs[:4]) - int(ts[:4])) <= tol: return "agrees", "year only; " + ("the record gives only a year" if len(rs) < 10 else "the tree gives only a year") + (f", within {tol} years" if tol and rs[:4] != ts[:4] else "")
    return "disagrees", None

ONCE = ("Birth", "Death", "Burial", "Cremation")   # what a life holds once: a person's events of one of these types are one event wherever their places agree, and two that stand apart are a conflict question; residences, censuses, occupations and the like repeat
RECORD_FACTS = ("Unknown", "Age", "Identification Number", "Relationship")      # about the record or the page, not facts of the person
NEAR = ("calculated", "about", "estimated")      # a date marked so stands for a year give or take two
BOUNDS = ("before", "after", "between")          # a date bounded, not stated: it names no one year of its own

def date_closeness(a, b):
    """How closely two dates agree, each {"start", "end", "qualifier"}, for choosing the one event a record's statement
    belongs to (docs/RESEARCH-WORKFLOW.md §5–7): 0 the same day, 1 the same month where one side gives no day, 2 the same
    year where one side gives only the year, 3 the same year with another month or day, then 3 and the years apart within
    the two a date marked about, estimated or calculated on either side allows (4, 5); None when either has no date or
    they lie further apart."""
    sa, sb = (a.get("start") or a.get("end") or ""), (b.get("start") or b.get("end") or "")
    if not (sa[:4].isdigit() and sb[:4].isdigit()): return None
    if sa[:4] == sb[:4]:
        n = min(len(sa), len(sb))
        return 3 if sa[:n] != sb[:n] else 0 if n == 10 else 1 if n == 7 else 2
    apart = abs(int(sa[:4]) - int(sb[:4]))
    return 3 + apart if apart <= 2 and (a.get("qualifier") in NEAR or b.get("qualifier") in NEAR) else None

def dates_one(a, b):
    """Whether two dates name one day, month or year, as the fold reads them: both state a year (neither is bounded, before,
    after or between), the same, and where both give a month or a day, the same: 26 Jun 1901 and 1901 are one, 1728 and
    1730 are not, nor 25 and 26 Jun 1901."""
    return a.get("qualifier") not in BOUNDS and b.get("qualifier") not in BOUNDS and date_closeness(a, b) in (0, 1, 2)

def fuller_date(own, other):
    """Whether the event that holds date own takes date other when the two become one event (the fold, the import): own
    has no date and other has one; or the two agree (date_verdict, so a date marked about, estimated or calculated agrees
    within two years) and other says more: more of the day, month and year, or the same exactly where own is marked about,
    estimated or calculated (26 Jun 1901 over 1901, 24 April 1876 over CAL 1875). A bounded date (before, after, between) is
    never taken nor replaced by another, and dates that disagree leave own as it is."""
    so, sn = (own.get("start") or own.get("end") or ""), (other.get("start") or other.get("end") or "")
    if not sn or own.get("qualifier") in BOUNDS or other.get("qualifier") in BOUNDS: return bool(sn) and not so
    if not so: return True
    says = lambda d, s: (len(s), d.get("qualifier") not in NEAR)
    return date_verdict(other, own)[0] == "agrees" and says(other, sn) > says(own, so)

def places_one(a, b):
    """Whether two places are one, as the fold and the choice of an event read them: either absent, or one agrees with the
    other read either way (place_verdict: a coarser or finer naming of one place agrees, Pennsylvania with Montgomery
    County, Pennsylvania), so Amherst and Northampton are two."""
    return not a or not b or place_verdict(a, b)[0] == "agrees" or place_verdict(b, a)[0] == "agrees"

def same_event(etype, kind, a, b):
    """Whether two events of one person, or of one family, of one type are one event (docs/RESEARCH-WORKFLOW.md §5–7, the
    fold): their places are one (places_one), an attribute's values are the same, and the type is one a life holds once
    (ONCE) or their dates are one (dates_one). Each event is {"start", "end", "qualifier", "place", "value"}."""
    if not places_one(a.get("place"), b.get("place")): return False
    if kind == "attribute" and (a.get("value") or "") != (b.get("value") or ""): return False
    return etype in ONCE or dates_one(a, b)

LIMITS = None                                    # data/life-limits.csv, read once per process by life_limits

def life_limits():
    """data/life-limits.csv as {limit: value}, read once per process: the bounds of one life a family link or a dated statement
    is tested against (Catalog.beyond_life, tools/conclude.py's outside_life), a number as a number and a list of event types
    (after_death_types) as a tuple."""
    global LIMITS
    if LIMITS is None:
        LIMITS = {}
        with open(os.path.join(ROOT, "data", "life-limits.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                v = r["value"].strip()
                LIMITS[r["limit"]] = float(v) if re.fullmatch(r"\d+(?:\.\d+)?", v) else tuple(t.strip() for t in v.split(";") if t.strip())
    return LIMITS

def _day(s, last):
    """The first day (last: the last day) a date written YYYY, YYYY-MM or YYYY-MM-DD can stand for, or None."""
    m = re.fullmatch(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", s or "")
    if not m: return None
    y = int(m.group(1)); mo = int(m.group(2)) if m.group(2) else (12 if last else 1)
    if not (1 <= mo <= 12 and y >= 1): return None
    d = int(m.group(3)) if m.group(3) else (calendar.monthrange(y, mo)[1] if last else 1)
    try: return datetime.date(y, mo, d)
    except ValueError: return None

def date_span(start, end=None, qualifier=None):
    """(earliest, latest) day a date can stand for, each a datetime.date, None on a side the date leaves open (before, after);
    None when it states no year. A bare year spans the year, a month the month, between its first date to its last; a date
    marked about, estimated or calculated (NEAR) spans two whole years more on either side, as date_verdict allows."""
    s, e = start or None, end or None
    if not (s or e): return None
    if qualifier == "before":
        d = _day(e or s, True); return (None, d) if d else None
    if qualifier == "after":
        d = _day(s or e, False); return (d, None) if d else None
    lo, hi = _day(s or e, False), _day(e or s, True)
    if lo is None or hi is None: return None
    if qualifier in NEAR: lo, hi = datetime.date(max(lo.year - 2, 1), 1, 1), datetime.date(hi.year + 2, 12, 31)
    return lo, hi

def _years(a, b): return (b - a).days / 365.2425

def _plus_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return datetime.date(d.year + y, m + 1, min(d.day, calendar.monthrange(d.year + y, m + 1)[1]))

def parent_limit(sex, parent_birth, parent_death, child_birth):
    """The limit of one life (life_limits) a parent-child link breaks, or None: (the parent's date it rests on, "birth" or
    "death", and the limit in words). Each date is a date_span or None. A mother younger or older at the child's birth than
    the bounds allow, a father the same by his own, a child born after the mother's death or more months after the father's
    than the limit allows; a parent of unknown sex is held to the wider bounds. Only what holds over every day each date can
    stand for counts, so a bare year or an about date breaks nothing a finer date of it might keep."""
    L = life_limits(); cb = child_birth
    if not cb: return None
    who = {"F": "the mother", "M": "the father"}.get(sex, "the parent")
    young = {"F": L["mother_youngest"], "M": L["father_youngest"]}.get(sex, min(L["mother_youngest"], L["father_youngest"]))
    old = {"F": L["mother_oldest"], "M": L["father_oldest"]}.get(sex, max(L["mother_oldest"], L["father_oldest"]))
    if parent_birth:
        if parent_birth[0] and cb[1] and _years(parent_birth[0], cb[1]) < young:
            return "birth", f"{who} at most {int(_years(parent_birth[0], cb[1]))} at the birth, younger than {young:g}, the youngest one life allows"
        if parent_birth[1] and cb[0] and _years(parent_birth[1], cb[0]) > old:
            return "birth", f"{who} at least {int(_years(parent_birth[1], cb[0]))} at the birth, older than {old:g}, the oldest one life allows"
    if parent_death and parent_death[1] and cb[0]:
        months = int(L["after_mother_death_months"] if sex == "F" else L["after_father_death_months"])
        if cb[0] > _plus_months(parent_death[1], months):
            return "death", f"a child born {f'more than {months} months ' if months else ''}after {who}'s death"
    return None

def collection_state(name):
    """The US state a collection's own name states as its coverage, when the registry names it first ("<State>, U.S.,
    <kind>, <years>", data/data-sources.csv's own naming): the record's own event place, for a bare county place_verdict
    otherwise cannot place. None when the collection's name does not lead with one."""
    first = (name or "").split(",")[0].strip()
    return first if first.lower() in US_STATES else None

ABBREVIATION = ((re.compile(r"\bmt\b\.?"), "mount"), (re.compile(r"\bst\b\.?"), "saint"), (re.compile(r"\bft\b\.?"), "fort"))   # a place name's abbreviated word stands for the word: Mt. Holly is Mount Holly
ADMINISTRATIVE = re.compile(r"\b(?:village|borough|city|town) of\b|\b(?:town|borough|city|ward \d+|\d+(?:st|nd|rd|th) ward)\b")   # the unit's own word beside its name: Hempstead Town, Village of Lindenhurst, Northampton Ward 1

def _place_part(p, administrative=False):
    """One piece of a place string normalised for comparison: the country written as usa, a jurisdiction word dropped (a
    county, a township, a district), an abbreviated word written out, and with administrative, the unit's own word (Town,
    Village of, Borough, City, Ward N) dropped too."""
    s = COUNTRY.sub("usa", p.lower())
    for rx, word in ABBREVIATION: s = rx.sub(word, s)
    s = re.sub(r"\b(county|co\.?|township|twp\.?|magisterial district \d+|district \d+)\b", " ", s)
    if administrative: s = ADMINISTRATIVE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip().rstrip(".").strip()

def _place_parts(s, administrative=False):
    """(normalised, as written) for each part of a place string, '<' or ',' apart (_place_part), the last part that is not the
    country read as the state when it is the state's name or an abbreviation of it (us_state: NJ, N.J., Penna, Mass.): only
    there is an abbreviation the state, since earlier a word like Penn or Col is a township's or a person's own."""
    out = [(_place_part(p, administrative), p.strip(" .")) for p in re.split(r"<|,", s)]
    out = [(n, w) for n, w in out if n]
    i = next((i for i in range(len(out) - 1, -1, -1) if out[i][0] != "usa"), None)
    state = us_state(out[i][1]) if i is not None else None
    if state: out[i] = (state.lower(), out[i][1])
    return out

UNIT_WORD = re.compile(r"\b(?:the )?municipal district of\b|\b(?:cty|municipality|gemeente|prefecture|province|district|metropolitan|stadtkreis|landkreis|kreis|gmina|powiat)\b")   # the unit's own word that _place_part leaves: Cty, and in the countries the resolver reads beside the US Iwate Prefecture, Gmina Dluzec, Landkreis Freiberg
LETTERS = str.maketrans({"ß": "ss", "ø": "o", "ł": "l", "đ": "d", "æ": "ae", "œ": "oe"})   # the letters that have no accent to take off

def place_name_key(name):
    """One place name as every comparison of two names reads it; two names are the same name when their keys are equal. The
    case, the accents (Düsseldorf is Dusseldorf), the punctuation (an apostrophe goes, a hyphen is a space) and the spacing
    are set aside; an abbreviated word is written out (Mt. is Mount, St. is Saint, Ft. is Fort, Twp is Township); and the
    unit's own word is dropped from either side (Township, Town, Village of, Borough, City, County, Ward N, and abroad
    Prefecture, Gmina, Landkreis), as place_verdict's granularity rule drops it. A word is never run into its neighbour:
    North Hampton is not Northampton. '' for a name that is nothing but a unit's word."""
    s = unicodedata.normalize("NFKD", (name or "").lower().translate(LETTERS))
    s = _place_part("".join(ch for ch in s if not unicodedata.combining(ch)), administrative=True)
    return re.sub(r"[^a-z0-9]+", " ", UNIT_WORD.sub(" ", s).replace("'", "").replace("’", "")).strip()

def _place_verdict_once(record, tree, supply=None):
    parts = _place_parts                                              # (normalised, as written)
    tparts = [p for p, _ in parts(tree)]
    below = [p for p in tparts if p != "usa"]
    if not below: return "absent", None                             # a tree place that names only the country says nothing to compare
    rparts = [(p, w) for p, w in parts(record) if p != "usa"]         # the country is not a part to count on either side
    if not rparts: return "absent", None
    if supply: rparts = rparts + [(_place_part(supply), supply)]            # a bare county takes the record's own event place's state, for comparison only
    finer = rparts[:-len(below)] if len(rparts) > len(below) else []  # what the record names ahead of the tree's own finest part: a finer place, or a cemetery or building ahead of its town; not compared
    rparts = [p for p, _ in rparts[len(finer):]]
    tkeys = {key(p) for p in tparts}
    if not all(key(p) in tkeys for p in rparts): return "disagrees", None
    finest = rparts[0]                                                # the record's first-named jurisdiction is its finest
    if key(finest) == key(below[0]): return ("agrees", "the record is finer: " + ", ".join(w for _, w in finer)) if finer else ("agrees", None)
    name = next((p for p in below if key(p) == key(finest)), finest)
    return "agrees", f"the record gives only {name.title()}"

def _dated_agree(record, dated_names):
    """Whether some part of record, tail-word first (so a hamlet or ward named ahead of it, "Ogau" in "Ogau Tonan",
    is never mistaken for the whole), is one of dated_names ([(name, valid_from, valid_to), ...], a place's own
    former names from place_name): a note naming the name and the period it held it, or None."""
    for part in re.split(r"<|,", record):
        words = [w for w in part.strip().split() if w]
        for i in range(len(words)):
            tail = key(" ".join(words[i:]))
            for name, vf, vt in dated_names or []:
                if tail and tail == key(name): return f"as {name}, a name it held {vf or '?'}–{vt or '?'}"
    return None

def _same_granular(record, tree):
    """The note when two US place strings name one place at another granularity, else None: with the administrative word
    dropped from every part (Hempstead Town is Hempstead, Village of Lindenhurst is Lindenhurst, Northampton Ward 1 is
    Northampton), both name the same state as their last part, the same place as their first, and every part of the shorter
    is a part of the longer in the same order, so a county one side leaves out is no difference ("Northampton, Massachusetts"
    and "Northampton, Hampshire, Massachusetts"). A name that differs in a letter or a word is never the same place here:
    North Hampton is not Northampton, Norriton not Norristown."""
    def parts(s): return [n for n, _ in _place_parts(s, administrative=True) if n != "usa"]
    r, t = parts(record), parts(tree)
    if not r or not t or r[-1] not in US_STATES or r[-1] != t[-1] or r[0] != t[0]: return None
    short, long_ = (r, t) if len(r) <= len(t) else (t, r)
    it = iter(long_)
    if not all(p in it for p in short): return None
    return "the same place, written at another granularity"

def place_verdict(record, tree, record_state=None, dated_names=None):
    """(verdict, note): agrees when every part the record states, at or below the country, is a part of the tree's resolved
    chain — 'Town < County < State < Country' — matched whole after normalisation (a jurisdiction word stripped, an
    abbreviated word written out (Mt. is Mount, St. is Saint, Ft. is Fort), a two-letter US state code expanded to its name, with or
    without a period), never as a substring of another word: 'Kent'
    is not Kentucky and 'Frank' is not Franklin. The country is not a part to count on either side. A record with more
    parts below the country than the tree's own chain is read from the state backward, so what it names ahead of the
    tree's own finest part (the town when the tree holds only the state; a cemetery or building ahead of its town) is
    never compared: as a full date against a bare year agrees on the year, a finer record agrees on the level the tree
    states, and the note says the record is finer and names those leading parts. A
    coarser record (the state alone, or the county and state) still agrees, on the finest part it states, and the note
    names that part; a full match down to the tree's own finest part carries no note. A part that is a real place but is
    not in the tree's chain (a same-named town in another state, a county alone against a tree that holds only the state)
    disagrees — unless the record names a county alone: it then takes the state of the record's own event place
    (record_state, collection_state on the record's own collection) for the comparison, the note saying so; or unless the
    record names a dated former name of the tree's own place (dated_names, place_name rows with a valid_from or valid_to:
    Tonan, a village Morioka absorbed in 1992) — it then agrees on that name, the note naming the period it held it; or
    unless the two name one US place at another granularity (_same_granular: an administrative word such as Town, Village
    of, Borough, City or Ward N, or a county one side leaves out, with the rest of the name and the state agreeing) — it
    then agrees, the note saying so. The string itself is never changed, only compared. absent when either side has none."""
    if not record or not tree: return "absent", None
    v, note = _place_verdict_once(record, tree)
    if v == "disagrees" and record_state and re.search(r"\bcounty\b", record, re.I) and not re.search(r"<|,", record):
        v2, note2 = _place_verdict_once(record, tree, supply=record_state)
        if v2 == "agrees": return v2, (f"{note2}; " if note2 else "") + f"supplying {record_state}, the record's own event place, for the bare county"
    if v == "disagrees" and dated_names:
        note3 = _dated_agree(record, dated_names)
        if note3: return "agrees", note3
    if v == "disagrees":
        note4 = _same_granular(record, tree)
        if note4: return "agrees", note4
    return v, note


def served_as():
    """The registry's ServedAs column (data/data-sources.csv): [(holder id, words, registry id, tier)], one entry per
    collection another holder serves a row's records under (FamilySearch's own index of Find a Grave's memorials), the words
    being what that holder's collection name carries and the tier the row's own, its first tier word."""
    out = []
    with open(os.path.join(ROOT, "data", "data-sources.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            tier = (re.match(r"\s*(T\d|ref|n/a)", r.get("TrustTier") or "") or [None, None])[1]
            for part in (r.get("ServedAs") or "").split(";"):
                holder, _, words = part.strip().partition(":")
                if holder and words.strip(): out.append((holder.strip(), words.strip(), r["ID"], tier))
    return out

def country_words():
    """data/countries.csv: every country's name and the other words records write for it, lower case, to its name as the
    place resolver writes it ("deutschland" and "allemagne" to Germany, "usa" to United States); a name that is also a US
    state (Georgia) is left out, the state being what an American record means. Longest words first, for phrases."""
    out = {}
    with open(os.path.join(ROOT, "data", "countries.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for w in [r["country"]] + [x for x in (r["synonyms"] or "").split(";") if x]:
                w = w.strip().lower()
                if w and w not in US_STATES: out[w] = r["country"]
    return dict(sorted(out.items(), key=lambda kv: -len(kv[0])))

def jurisdictions():
    """data/jurisdictions.csv, the reference knowledge of where which records exist and who holds them, by US state or country
    (lower case; * for anywhere): {vital: {state: {birth|death|marriage: (from year, registry row)}}, state_census: {state:
    (years, rows)}, church: {place: rows}, civil: {country: from year}, land: {state: rows}, passenger: [(place, from, to,
    rows)]}, a passenger row's years being the person's birth years. A place with no row of a kind has none: the checklist
    names the missing data, never another place's holders."""
    out = {"vital": {}, "state_census": {}, "church": {}, "civil": {}, "land": {}, "passenger": []}
    yr = lambda v: int(v) if v else None
    with open(os.path.join(ROOT, "data", "jurisdictions.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            j, k, rows = r["jurisdiction"].strip().lower(), r["kind"].strip(), [x for x in (r["sources"] or "").split(";") if x]
            if k.startswith("vital_"): out["vital"].setdefault(j, {})[k[6:]] = (yr(r["from"]), rows[0] if rows else None)
            elif k == "state_census": out["state_census"][j] = ([int(y) for y in r["years"].split(";") if y], rows)
            elif k in ("church", "land"): out[k][j] = rows
            elif k == "civil": out["civil"][j] = yr(r["from"])
            elif k == "passenger": out["passenger"].append((j, yr(r["from"]), yr(r["to"]), rows))
    return out

def collection_tier(source_id, name, served=None):
    """The trust tier a collection takes from the data, or None: the tier of the registry row whose ServedAs names the
    collection's holder and words its name carries, any case (served_as). A collection no row names takes nothing, and its
    records take their holder's tier (tier_sql). Written onto collection.trust_tier by tools/initdb.py --sync-sources."""
    for holder, words, _, tier in (served_as() if served is None else served):
        if holder == source_id and words.lower() in (name or "").lower(): return tier
    return None

def tier_sql(ar="ar", s="s"):
    """SQL for an artifact's effective trust tier, given the artifact's alias and its joined source's alias: the tier of the
    record's own collection where the data gives that collection one (collection_tier, written by tools/initdb.py
    --sync-sources) and the collection is its holder's own, the holder being the source the artifact's own identity names
    (an ark is FamilySearch, a memorial id is Find a Grave) or else the one it was archived under; otherwise the tier of
    that source. artifact.trust_tier is the tier copied at archive time and can fall behind the registry."""
    own = f"""CASE WHEN EXISTS (SELECT 1 FROM artifact_locator l WHERE l.artifact_sha256={ar}.sha256 AND l.kind='ark') THEN 'D03'
                   WHEN EXISTS (SELECT 1 FROM artifact_locator l WHERE l.artifact_sha256={ar}.sha256 AND l.kind='memorial_id') THEN 'E01' END"""
    return f"""coalesce((SELECT c.trust_tier FROM collection c WHERE c.id={ar}.collection_id AND c.source_id=coalesce({own}, {ar}.source_id)),
                        (SELECT s2.trust_tier FROM source s2 WHERE s2.id = {own}), {s}.trust_tier)"""

def source_tier(cx, sha):
    """An artifact's effective trust tier (tier_sql), or None."""
    r = cx.execute(f"SELECT {tier_sql()} FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?", (sha,)).fetchone()
    return r[0] if r else None

# ---------------------------------------------------------------- a persona's entry on its page
ARK = re.compile(r"ark:/\d+/[0-9A-Za-z:-]+")
RECORD_NUMBERS = ("state_file_number", "number", "rid", "profile")   # the number an index gives its record: a New Jersey state file number, a Kentucky certificate or birth number, an AAD record id, a WikiTree profile id

def persona_key(role, sequence, name, region):
    """Which entry of its page a persona is, the same in every reading of the page, from what the reading wrote in its
    region_json (a dict or its JSON): an ark (its own, or the one inside its url: a FamilySearch record links each relative
    to their own record), a Find a Grave memorial id (its own, or the one inside its url), or the number an index gives the
    record (RECORD_NUMBERS); failing those, its role, its row on the page (the region's row or line, else the reading's
    own sequence) and its name as written. A url is read for an ark or a memorial id only: a results page writes its own
    address beside every row (the VA locator), so a bare url names the page, not the entry. Personas of a page with one
    key are one entry, whatever reading wrote them; two rows of one name are two entries."""
    if isinstance(region, str):
        try: region = json.loads(region)
        except ValueError: region = None
    r = region if isinstance(region, dict) else {}
    url = r.get("url") or ""
    ark = ARK.search(f"{r.get('ark') or ''} {url}")
    if ark: return ("ark", ark.group(0))
    memorial = re.search(r"/memorial/(\d+)", url)
    if r.get("memorial_id") or memorial: return ("memorial_id", str(r.get("memorial_id") or memorial.group(1)))
    for k in RECORD_NUMBERS:
        if r.get(k): return (k, str(r[k]))
    row = next((r[k] for k in ("row", "line") if r.get(k) is not None), sequence)
    return ("row", role, row, name)

def is_identity(key):
    """Whether a persona_key is a record identity the reading wrote, rather than the role, row and name it falls back to."""
    return key[0] != "row"

def page_entries(cx, sha, extraction_id=None):
    """Every persona of an archived page, of one reading when extraction_id names it: [(persona id, extraction id, name as
    written, role, persona_key)] in reading and sequence order."""
    where, args = ("extraction_id=?", (extraction_id,)) if extraction_id else ("artifact_sha256=?", (sha,))
    return [(pid, eid, name, role, persona_key(role, seq, name, region)) for pid, eid, name, role, seq, region in
            cx.execute(f"SELECT id, extraction_id, name_text, role_in_record, sequence, region_json FROM persona WHERE {where} ORDER BY extraction_id, sequence, id", args)]

def current_entry(cx, persona_id):
    """The persona of the same entry (persona_key) on the current reading of its page, the reading its own extraction is in
    turn superseded by; itself when its reading is current, None when the current reading has no persona of that entry."""
    row = cx.execute("SELECT extraction_id, artifact_sha256, role_in_record, sequence, name_text, region_json FROM persona WHERE id=?", (persona_id,)).fetchone()
    if not row: return None
    eid = row[0]
    while (later := cx.execute("SELECT superseded_by FROM extraction WHERE id=?", (eid,)).fetchone()[0]): eid = later
    if eid == row[0]: return persona_id
    k = persona_key(row[2], row[3], row[4], row[5])
    return next((pid for pid, _, _, _, key in page_entries(cx, row[1], eid) if key == k), None)

# ---------------------------------------------------------------- the proof standard's classes, in words
EVIDENCE = None                                  # data/evidence-classes.csv, read once per process by evidence_table
INDIRECT_DATES = ("calculated", "estimated", "before", "after")   # a date the reading worked out or bounded from another field: the record does not state it

def evidence_table():
    """data/evidence-classes.csv as {kind: [row, ...]} in file order, read once per process."""
    global EVIDENCE
    if EVIDENCE is None:
        EVIDENCE = {}
        with open(os.path.join(ROOT, "data", "evidence-classes.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh): EVIDENCE.setdefault(r["kind"], []).append(r)
    return EVIDENCE

def kinds_as(own):
    """The kinds of data/evidence-classes.csv a record naming these kinds (most specific first) reads as: only the kinds the
    table holds, each followed by the kinds its rows read as (reads_as), then `*`, the rows every record shares."""
    t = evidence_table()
    kinds = list(dict.fromkeys(k for k in own if k in t))
    for k in list(kinds):                                         # each kind's own reads_as chain, after every kind the record itself names
        nxt = next((r["reads_as"] for r in t.get(k, []) if r["field"] == "*" and r["reads_as"]), None)
        while nxt and nxt not in kinds:
            kinds.append(nxt); nxt = next((r["reads_as"] for r in t.get(nxt, []) if r["field"] == "*" and r["reads_as"]), None)
    return kinds + ["*"]

def record_kinds(cx, sha, extraction_id=None):
    """(kinds, year): the kinds of data/evidence-classes.csv an archived record reads as, most specific first (kinds_as), and
    the record's own year. A FamilySearch record page reads as its own collection, its Event Type and its collection's kind
    word (`FamilySearch: <words>`, the Event Type before the kind word, which can mislead: a Massachusetts birth filed under
    Death), then its parser; a record read by the model or a person (extractor llm or human) as what its reader says the
    image is (image_is: `reading of an index`, or `reading`, the image of the record made at the event), then the collection
    it is filed under, its registry row, the checklist rows of the steps it was fetched for and `reading`, so that a reading
    that does not say (one written before readers said) takes its class from a row of its collection or registry row; any
    other page as its parser. The reading is extraction_id's, else the record's current one. The year is the record's own,
    for an original's name: a FamilySearch page's event date or its collection's single year, a reading's own year."""
    if extraction_id is None:
        r = cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND status<>'failed' AND superseded_by IS NULL ORDER BY ran_at DESC LIMIT 1", (sha,)).fetchone()
        extraction_id = r[0] if r else None
    x = cx.execute("SELECT x.kind, x.name, e.structured_json FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (extraction_id,)).fetchone() if extraction_id else None
    xkind, xname, sj = x if x else (None, None, None)
    try: parsed = json.loads(sj) if sj else {}
    except ValueError: parsed = {}
    parsed = parsed if isinstance(parsed, dict) else {}
    own, yr = [], None
    if xname == "familysearch-record":
        word, _, name = (parsed.get("collection") or "").partition("•")
        word, name = (word.strip(), name.strip()) if name else ("", word.strip())
        fields = {str(k).lower(): v for k, v in parsed.get("fields") or []}
        etype = (fields.get("event type") or "").strip()
        own = [f"FamilySearch: {v}" for v in (name, etype, word) if v] + ["familysearch-record"]
        ym = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", fields.get("event date") or "") or re.fullmatch(r".*\b(1[5-9]\d\d|20\d\d)\b.*", re.sub(r"\b\d{4}-\d{4}\b", "", name))
        yr = ym.group(1) if ym else None
    elif xkind in ("llm", "human"):
        src = cx.execute("SELECT ar.source_id, c.name FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id WHERE ar.sha256=?", (sha,)).fetchone()
        rows = [rk.split(":", 1)[0] for rk, in cx.execute("""SELECT sp.row_key FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id
                                                           WHERE l.artifacts_json LIKE ? ORDER BY l.executed_at""", (f'%"{sha}"%',))]
        said = {"index": ["reading of an index"], "record": ["reading"]}.get(parsed.get("image_is"), [])   # the reader's own word on what the image is comes first
        own = said + [k for k in ((src[1], src[0]) if src else ()) if k] + rows + ["reading"]
        yr = str(parsed["year"]) if parsed.get("year") else None
    elif xname: own = [xname]
    return kinds_as(own), yr

def record_standing(kinds):
    """(standing, kind): how the standing rule may treat a record of these kinds (record_kinds' order), from
    data/evidence-classes.csv's standing on each kind's `*` row (docs/RESEARCH-WORKFLOW.md §0's table): automated (the rule
    may take it), identity (a page anyone can edit that identifies a person: the rule may take the identity, never a fact)
    or hint (the owner decides). The most specific kind that gives one decides; a record no kind gives one is a hint, and
    kind is None."""
    t = evidence_table()
    for k in kinds:
        s = next((r.get("standing") for r in t.get(k, []) if r["field"] == "*" and r.get("standing")), None)
        if s: return s, k
    return "hint", None

def _class_rows(t, kinds, keys, label=None):
    """The table's rows for one statement, most specific first: kind by kind, and within a kind the field patterns in the
    order keys gives them; a `relation [<words>]` row matches a relationship whose label is or ends with the words (a
    FamilySearch relatives table's heading after the subject's name)."""
    for k in kinds:
        rows = t.get(k, [])
        for key in keys:
            for r in rows:
                f = r["field"]
                if f == key or (key == "relation [*]" and label and f.startswith("relation [") and f.endswith("]") and (label == f[10:-1] or label.endswith(f[10:-1]))):
                    yield r

def _labels(region):
    """The field labels a persona fact's region_json names."""
    try: return (json.loads(region) or {}).get("labels") or [] if region else []
    except ValueError: return []

def statement_of(cx, assertion_id):
    """What one assertion states, as data/evidence-classes.csv keys it: {kind: fact | relation | file | vouch, fact_type,
    labels, qualifier, relation (kind, label, value as written, region), persona, extraction, sha}. A fact is the persona
    fact the assertion carries; a relation the record's own relationship behind a family link, found among the persona's
    relations on the record by the word the link was written with; a file statement a citation the tree file carries; a vouch
    the owner's own word. Both are read through the record's current reading: the persona of the same entry on it
    (current_entry), and its fact of the same type read under the same field label (the same labels first, then the same
    value) or its relationship of the same words; the assertion's own reading only where the current one has no such persona,
    fact or relationship. The assertion itself keeps pointing at the persona fact it was written from."""
    a = cx.execute("SELECT subject_kind, persona_fact_id, persona_id, artifact_sha256, citation_text, notes FROM assertion WHERE id=?", (assertion_id,)).fetchone()
    if not a: return None
    subject_kind, pf_id, persona_id, sha, cite, notes = a
    try: n = json.loads(notes) if notes and notes.startswith("{") else {}
    except ValueError: n = {}
    if n.get("vouched"): return {"kind": "vouch", "sha": sha}
    out = {"kind": "file", "sha": sha, "persona": persona_id, "extraction": None, "fact_type": None, "labels": [], "qualifier": None, "relation": None}
    if pf_id:
        f = cx.execute("SELECT persona_id, fact_type, date_qualifier, region_json, value_text, date_text, place_string_id FROM persona_fact WHERE id=?", (pf_id,)).fetchone()
        if f:
            labels, cur = _labels(f[3]), current_entry(cx, f[0])
            same = [] if cur in (None, f[0]) else \
                   [r for r in cx.execute("SELECT persona_id, fact_type, date_qualifier, region_json, value_text, date_text, place_string_id FROM persona_fact WHERE persona_id=? AND fact_type=? ORDER BY id", (cur, f[1]))
                    if set(_labels(r[3])) & set(labels) or not (labels or _labels(r[3]))]
            same.sort(key=lambda r: (_labels(r[3]) != labels, r[4:] != f[4:]))
            r = same[0] if same else f
            out.update({"kind": "fact", "persona": r[0], "fact_type": r[1], "qualifier": r[2], "labels": _labels(r[3])})
    elif subject_kind == "family_member" and persona_id:
        words = re.sub(r"\s+on the record$", "", cite or "")
        cur = current_entry(cx, persona_id)
        for pid in dict.fromkeys(x for x in (cur, persona_id) if x):
            rel = next(((kind, value, region) for kind, value, region in cx.execute("""SELECT kind, value_text, region_json FROM persona_relation WHERE persona_id=? OR related_persona_id=? ORDER BY id""", (pid, pid))
                        if (value or kind) and (words == (value or kind) or words.startswith((value or kind) + " of "))), None)
            if rel:
                try: rj = json.loads(rel[2]) if rel[2] else {}
                except ValueError: rj = {}
                out.update({"kind": "relation", "persona": pid, "relation": {"kind": rel[0], "value": rel[1], "label": (rj or {}).get("label"), "region": rj or {}}}); break
    if out["persona"]:
        e = cx.execute("SELECT extraction_id FROM persona WHERE id=?", (out["persona"],)).fetchone()
        out["extraction"] = e[0] if e else None
    return out

def evidence_classes(cx, assertion_id):
    """The classes of one assertion's statement, in words, from data/evidence-classes.csv (docs/RESEARCH-WORKFLOW.md §5-7,
    "The proof standard"): {source: original | derivative | authored, information: primary | secondary | indeterminable,
    evidence: direct | indirect, relationship: stated | computed for a family link's statement (else None), original: the
    original record a derivative was copied from (else None), kinds: what the record reads as, notes: the table's notes on
    the rows read}. Each class is read from the most specific row that gives it (record_kinds' order; within a kind the
    field with its label, then the field, then `*`), the source class's own default row last, so a field nothing names
    reads indeterminable. A date the reading worked out from another field (qualifier calculated, estimated, before or
    after) is indirect evidence, and so is a relationship the reading marks computed (persona_relation.region_json
    {"computed": true}), whatever the table says; a relationship the reading marks stated ({"computed": false}) is the
    record's own statement of it, direct evidence. A vouch is the owner's own word: {vouched: true} and no classes."""
    st = statement_of(cx, assertion_id)
    return None if st is None else classes_of(cx, st)

def relation_classes(cx, persona_id, related_id, kind, value):
    """The classes of one relationship a record gives between two of its personas (persona_relation: persona_id is the <kind>
    of related_id, as written value), as evidence_classes reads a family link's statement: through the record's current
    reading, the same relationship between the same two entries there (current_entry), else this reading's own."""
    r, a = None, persona_id
    for a, b in dict.fromkeys(((current_entry(cx, persona_id), current_entry(cx, related_id)), (persona_id, related_id))):
        if a and b:
            r = cx.execute("SELECT region_json FROM persona_relation WHERE persona_id=? AND related_persona_id=? AND kind=? AND coalesce(value_text,'')=coalesce(?,'')", (a, b, kind, value)).fetchone()
            if r: break
    try: region = json.loads(r[0]) if r and r[0] else {}
    except ValueError: region = {}
    sha, eid = cx.execute("SELECT artifact_sha256, extraction_id FROM persona WHERE id=?", (a,)).fetchone()
    return classes_of(cx, {"kind": "relation", "sha": sha, "persona": a, "extraction": eid, "fact_type": None, "labels": [], "qualifier": None,
                           "relation": {"kind": kind, "value": value, "label": (region or {}).get("label"), "region": region or {}}})

def record_original(cx, sha):
    """The original record an archived record was copied from, as its current reading's classes name it (the rows every
    field of its kind shares), or None: records copied from one original are one source."""
    return classes_of(cx, {"kind": "file", "sha": sha, "persona": None, "extraction": None, "fact_type": None, "labels": [], "qualifier": None, "relation": None})["original"]

def classes_of(cx, st):
    """The classes of one statement as statement_of describes it (evidence_classes)."""
    if st["kind"] == "vouch": return {"vouched": True, "source": None, "information": None, "evidence": None, "relationship": None, "original": None, "kinds": [], "notes": []}
    t = evidence_table()
    kinds, yr = record_kinds(cx, st["sha"], st["extraction"]) if st["sha"] else (["*"], None)
    rel = st["relation"]
    if st["kind"] == "fact": keys = [f"{st['fact_type']} [{lab}]" for lab in st["labels"]] + [st["fact_type"], "*"]
    elif rel: keys = ["relation [*]", f"relation:{rel['kind']}", "relation", "*"]
    else: keys = ["*"]
    first = lambda col, ks: next((r[col] for r in _class_rows(t, ks, keys, rel["label"] if rel else None) if r.get(col)), None)
    source = first("source", kinds) or "derivative"                 # a reading's own kinds end in `reading`, which says original
    cascade = kinds + [source]
    out = {"source": source, "information": first("information", cascade), "evidence": first("evidence", cascade),
           "relationship": first("relationship", cascade) if rel else None, "original": first("original", cascade), "kinds": kinds[:-1],
           "notes": list(dict.fromkeys(r["notes"] for r in _class_rows(t, cascade, keys, rel["label"] if rel else None) if r.get("notes")))}
    if out["original"]: out["original"] = re.sub(r"\s+", " ", out["original"].replace("{year}", yr or "")).strip()
    if st["kind"] == "fact" and st["qualifier"] in INDIRECT_DATES: out["evidence"] = "indirect"
    if rel and "computed" in rel["region"]:
        out["relationship"] = "computed" if rel["region"]["computed"] else "stated"
        out["evidence"] = "indirect" if rel["region"]["computed"] else "direct"
    return out

class Catalog:
    def __init__(self, cx, tree_id):
        self.cx, self.tree_id = cx, tree_id
        self.q = lambda s, *a: cx.execute(s, a).fetchall()
        self.sources = {r[0]: {"name": r[1], "access": r[2] or "", "status": r[3] or "", "cost": r[4] or "", "connector": r[5] or "", "coverage": r[6] or ""}
                        for r in self.q("SELECT id, name, access, status, cost, connector, coverage FROM source")}
        self.holders = holders()
        self._groups = self._held = self._holdings = self._tiers = None
    def disagreements(self, pid, event=None):
        """Where an accepted record says something else than the tree's event or than another statement on it: for each event
        of the person, and of each family they are a partner in (a marriage), and each of date and place, one line per
        differing value (event: that one event's lines alone, for tools/conclude.py resolve), naming every statement on each side and the
        tree's own value. Every Accepted assertion is compared against the event's own date (as dates) or shown place, and
        against every other statement on the event that is not rejected (undecided claims included: the file's own claim, a
        page anyone can edit), each a statement of the event's own type (a remarriage cited as a divorce's evidence is no
        value of the divorce); place is compared with Catalog.place_verdict, as the place its words are resolved to when they
        are (Auburn, Kentucky is in Logan County), so a coarser or finer record, or one naming a dated former name, agrees
        rather than disagreeing, and two statements that are each a part of the event's own place are no disagreement between themselves (a death index's state and an obituary's town, written without the state, are parts of one place). A record cited under two collection names but one locator (the same certificate indexed
        twice) is one statement, not two, and "the file" is the imported file alone. Statements whose values all agree with
        one another (among only those already found disagreeing with something) are grouped as one side, so six comparisons
        that all turn on the same 11th-against-10th read as one question, not six, while a coarse statement agreeing with two
        that differ (a county holding two towns) joins neither to the other. The tree's value is never changed by a record; the
        difference is a conflict question, and the shown value stays what Catalog.place chooses. A name an accepted record
        gives the person with a middle name or initial that differs from the one the tree's own name carries (match.
        middle_differs: John A. against John D) is a line too, one per record."""
        out = []
        from match import middle_differs                      # the matcher's own rule for a middle name, so a conflict is raised on exactly what made the card
        rows = [(g or "", s or "") for g, s in self.q("SELECT given, surname FROM person_name WHERE person_id=?", pid)]
        shown = (self.q("SELECT display_name FROM person WHERE id=?", pid) or [[None]])[0][0]
        for written, coll, loc in ([] if event else self.q("""SELECT pf.value_text, coalesce(c.name, ar.original_filename, substr(ar.sha256,1,12)), ar.locator_value FROM assertion a
                                            JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN collection c ON c.id=ar.collection_id
                                            WHERE a.subject_kind='person' AND a.subject_id=? AND a.status='accepted' AND pf.fact_type='Name' AND pf.value_text IS NOT NULL
                                            ORDER BY a.asserted_at, a.id""", pid)):
            if middle_differs(written, rows, [s for _, s in rows]):
                out.append(f"name: the tree against {coll}" + (f" ({loc})" if loc else "") + f": {shown} against {written}")
        for e in self.q(f"""SELECT DISTINCT e.id, e.event_type, e.date_text, e.date_start, e.date_qualifier, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                           WHERE (ep.person_id=? OR ep.family_id IN (SELECT family_id FROM family_member WHERE person_id=? AND role='partner')) {'AND e.id=?' if event else ''}
                           ORDER BY e.event_type, e.date_start""", pid, pid, *([event] if event else [])):
            place_now = self.place(e[0], e[5])
            tree_place = place_now["text"] if place_now else None
            kind = e[1].lower()
            rows = self.q("""SELECT pf.date_text, pf.date_start, pf.date_qualifier, ps.raw, coalesce(c.name, ar.original_filename, substr(ar.sha256,1,12)),
                                    ar.locator_value, a.status, a.id, ar.sha256 IN (SELECT artifact_sha256 FROM tree_import), CASE WHEN ps.status='accepted' THEN ps.place_id END
                             FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                             JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN collection c ON c.id=ar.collection_id
                             WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected' AND pf.fact_type=? ORDER BY a.asserted_at, a.id""", e[0], e[1])
            groups, order = {}, []                            # one group per record identity (its locator), whatever collection name cites it
            for f in rows:
                gk = f[5] or f[7]
                if gk not in groups:
                    groups[gk] = {"collections": [], "locator": f[5], "is_file": bool(f[8]), "status": "undecided", "date": None, "place": None, "place_cmp": None, "state": None}
                    order.append(gk)
                g = groups[gk]
                if f[4] and f[4] not in g["collections"]: g["collections"].append(f[4])
                if (f[0] is not None or f[1] is not None) and len(f[1] or "") > len(g["date"][1] if g["date"] else ""): g["date"] = (f[0], f[1], f[2])  # the same record's own most specific date wins (a full date over a bare year)
                if f[3] is not None and g["place"] is None: g["place"] = f[3]; g["place_cmp"] = self._place_chain(f[9])["text"] if f[9] else f[3]   # compared as the place its words are resolved to, when they are: Auburn, Kentucky is in Logan County
                g["state"] = g["state"] or collection_state(f[4])
                if f[6] == "accepted": g["status"] = "accepted"
            def label(gk):
                g = groups[gk]
                if g["is_file"]: return "the file"
                name = " / ".join(g["collections"]) if g["collections"] else (g["locator"] or "record")
                return f"{name} ({g['locator']})" if g["locator"] else name
            for axis in ("date", "place"):
                value_of = (lambda gk: ({"start": groups[gk]["date"][1], "text": groups[gk]["date"][0], "qualifier": groups[gk]["date"][2]} if groups[gk]["date"] else None)) if axis == "date" \
                            else (lambda gk: groups[gk]["place_cmp"])
                text_of = (lambda gk: groups[gk]["date"][0]) if axis == "date" else (lambda gk: groups[gk]["place"])
                tree_val = {"start": e[3], "text": e[2], "qualifier": e[4]} if axis == "date" else tree_place
                tree_text = e[2] if axis == "date" else tree_place
                tree_dated = self.dated_names(e[5]) if axis == "place" else None
                def cmp(av, asa, bv, bsa):
                    if axis == "date": return date_verdict(av, bv)
                    v, note = place_verdict(av, bv, record_state=asa, dated_names=tree_dated)
                    if v == "disagrees" and bsa:
                        v2, note2 = place_verdict(bv, av, record_state=bsa, dated_names=tree_dated)
                        if v2 == "agrees": return v2, note2
                    return v, note
                accepted = [gk for gk in order if groups[gk]["status"] == "accepted" and value_of(gk) is not None]
                pairs = []                                    # ("tree", key) or (key, key): a genuine disagreement found, before grouping
                on_tree = lambda k: axis == "place" and tree_val is not None and cmp(value_of(k), groups[k]["state"], tree_val, None)[0] == "agrees"   # a place that is a part of the event's own place chain
                for gk in accepted:
                    v, _ = cmp(value_of(gk), groups[gk]["state"], tree_val, None)
                    if v == "disagrees": pairs.append(("tree", gk))
                    for ok in order:
                        if ok == gk or value_of(ok) is None: continue
                        if ok in accepted and order.index(ok) < order.index(gk): continue   # two accepted statements compared once
                        if v == "agrees" and on_tree(ok): continue                           # two statements that are each a part of the event's own place are parts of one place: a state and a town in it, written without the state, are no disagreement
                        v2, _ = cmp(value_of(gk), groups[gk]["state"], value_of(ok), groups[ok]["state"])
                        if v2 == "disagrees": pairs.append((gk, ok))
                if not pairs: continue
                nodes = list(dict.fromkeys(n for p in pairs for n in p))
                parent = {n: n for n in nodes}
                def find(x):
                    while parent[x] != x: x = parent[x]
                    return x
                vs = lambda n: (tree_val, None) if n == "tree" else (value_of(n), groups[n]["state"])
                agrees = {(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:] if cmp(*vs(a), *vs(b))[0] == "agrees"}
                together = lambda a, b: (a, b) in agrees or (b, a) in agrees
                for i, a in enumerate(nodes):                  # group by mutual agreement, among only the statements already in some disagreement; every member of a side agrees with every other, so a coarse statement agreeing with two that differ (a county holding two towns) joins neither to the other
                    for b in nodes[i + 1:]:
                        ra, rb = find(a), find(b)
                        if ra != rb and together(a, b) and all(together(x, y) for x in nodes if find(x) == ra for y in nodes if find(y) == rb): parent[ra] = rb
                seen = set()
                for a, b in pairs:
                    ra, rb = find(a), find(b)
                    if ra != rb: seen.add(frozenset((ra, rb)))
                for pr in seen:
                    ra, rb = tuple(pr)
                    sides = ([n for n in nodes if find(n) == ra], [n for n in nodes if find(n) == rb])
                    priority = lambda ms: -1 if "tree" in ms else min(nodes.index(n) for n in ms)   # the tree first, else whichever statement was found first
                    members = sides if priority(sides[0]) <= priority(sides[1]) else sides[::-1]
                    def side(ms):
                        labels = list(dict.fromkeys(label(n) for n in ms if n != "tree"))
                        return ("the tree" + (", " + ", ".join(labels) if labels else "")) if "tree" in ms else " and ".join(labels)
                    def value(ms):
                        return tree_text if "tree" in ms else text_of(ms[0])
                    out.append(f"{kind} {axis}: {side(members[0])} against {side(members[1])}: {value(members[0])} against {value(members[1])}")
        return list(dict.fromkeys(out))
    def owner_events(self, etype, person=None, family=None):
        """A person's events of one type, or a family's (family), by date: {id, text, start, end, qualifier, place (the
        event's own place as Catalog.place shows it), value (an attribute's)}."""
        col, who = ("person_id", person) if person else ("family_id", family)
        return [{"id": i, "text": t, "start": s, "end": e, "qualifier": qu, "place": (self.place(i, pl) or {}).get("text"), "value": v}
                for i, t, s, e, qu, pl, v in self.q(f"""SELECT e.id, e.date_text, e.date_start, e.date_end, e.date_qualifier, e.place_id, e.description FROM event e
                                                       JOIN event_participant ep ON ep.event_id=e.id WHERE ep.{col}=? AND e.event_type=? ORDER BY e.date_start, e.id""", who, etype)]
    def fact_place(self, place_string_id):
        """A record fact's place as Catalog.disagreements compares it: the place its words are resolved to, when they are,
        else the words; None for no place."""
        r = self.q("SELECT raw, place_id, status FROM place_string WHERE id=?", place_string_id) if place_string_id else []
        if not r: return None
        return self._place_chain(r[0][1])["text"] if r[0][1] and r[0][2] == "accepted" else r[0][0]
    def event_for(self, f, events, once=False):
        """The one event among a person's events of the fact's type, or a family's (events, Catalog.owner_events), that a
        record's fact belongs to (docs/RESEARCH-WORKFLOW.md §5–7, one statement, one event): (event id, []) when there is
        one; (None, []) when there is none and the fact makes an event of its own; (None, [event ids]) when the choice
        among those is the owner's (Catalog.unplaced). once: the type is one a life holds once (ONCE), or the events are an
        attribute's of the fact's own value: a person with one such event has the fact on it whatever its date or place,
        and one with several and none fitting leaves the choice to the owner rather than make another. Otherwise one event
        of the type takes an undated fact, and several leave the choice to the owner; a dated fact takes the event whose own
        date agrees most closely (date_closeness: the same day, then the same month, then the same year, then within the
        two years an about, estimated or calculated date allows), among those whose places are one with the fact's
        (places_one) when any are, and two or more equally close leave the choice to the owner."""
        if not events: return None, []
        if len(events) == 1 and (once or not (f["date_start"] or f["date_end"])): return events[0]["id"], []
        if not (f["date_start"] or f["date_end"]): return None, [e["id"] for e in events]
        fd = {"start": f["date_start"], "end": f["date_end"], "qualifier": f["date_qualifier"]}
        ranked = [(r, e) for e in events for r in [date_closeness(fd, e)] if r is not None]
        if not ranked: return None, ([e["id"] for e in events] if once else [])
        where = self.fact_place(f["place_string_id"])
        pool = [x for x in ranked if places_one(where, x[1]["place"])] or ranked
        best = min(r for r, _ in pool)
        tied = [e["id"] for r, e in pool if r == best]
        return (tied[0], []) if len(tied) == 1 else (None, tied)
    def stated_on(self, sha, f, person=None, family=None):
        """The event of this person, or this family, on which the record already states this fact: a statement of the same
        record with the same type, date, value and place (an earlier reading's, or one the owner placed there), else None."""
        col, who = ("person_id", person) if person else ("family_id", family)
        r = self.q(f"""SELECT a.subject_id FROM assertion a JOIN persona_fact q ON q.id=a.persona_fact_id JOIN event_participant ep ON ep.event_id=a.subject_id
                       WHERE a.subject_kind='event' AND a.artifact_sha256=? AND ep.{col}=? AND q.fact_type=? AND coalesce(q.date_text,'')=coalesce(?,'')
                       AND coalesce(q.value_text,'')=coalesce(?,'') AND coalesce(q.place_string_id,'')=coalesce(?,'') ORDER BY a.asserted_at, a.id""",
                   sha, who, f["fact_type"], f["date_text"], f["value_text"], f["place_string_id"])
        return r[0][0] if r else None
    def unplaced(self, pid):
        """A record accepted onto this person whose fact asserts nothing because the choice of its event is the owner's
        (Catalog.event_for, tools/conclude.py assert_facts and assert_family_events): an undated fact on a person with
        several events of its type, a dated one that fits two or more equally, one of a type a life holds once that fits
        none of the person's several, or an attribute's among several of its value; a family fact (a marriage) the same
        among the events of the family the record joins the person to, once the spouse it names is accepted on it. One line
        per fact of the record (its readings are one), naming the record, the date, the type and the events to choose from
        in the order the person screen lists them (by date), so the owner reads the choice there and answers it with
        tools/conclude.py place. A fact the record already states on one of the person's events, or their family's, is
        placed (Catalog.stated_on)."""
        out, seen = [], set()
        fams = [f for f, in self.q("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", pid)]
        for row in self.q(f"""SELECT pf.id, pf.fact_type, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, pf.place_string_id, pf.value_text, et.kind, pe.id, pe.artifact_sha256,
                                     coalesce(c.name, ar.original_filename, substr(ar.sha256,1,12))
                              FROM persona_fact pf JOIN persona pe ON pe.id=pf.persona_id JOIN extraction x ON x.id=pe.extraction_id JOIN person_persona pp ON pp.persona_id=pe.id
                              JOIN event_type et ON et.name=pf.fact_type JOIN artifact ar ON ar.sha256=pe.artifact_sha256 LEFT JOIN collection c ON c.id=ar.collection_id
                              WHERE pp.person_id=? AND pp.status='accepted' AND et.kind IN ('event','attribute','family_event') AND pf.fact_type NOT IN ('Name','Sex',{','.join('?' * len(RECORD_FACTS))})
                              AND NOT (pf.fact_type='Residence' AND pf.date_start IS NULL AND pf.date_end IS NULL)
                              AND NOT EXISTS (SELECT 1 FROM assertion a WHERE a.persona_fact_id=pf.id) ORDER BY x.superseded_by IS NOT NULL, pf.id""", pid, *RECORD_FACTS):
            fid, ftype, dtext, kind, persona, sha, label = row[0], row[1], row[2], row[8], row[9], row[10], row[11]
            f = dict(zip(("id", "fact_type", "date_text", "date_start", "date_end", "date_qualifier", "place_string_id", "value_text"), row[:8]))
            ident = (sha, ftype, dtext or "", row[7] or "", row[6] or "")
            if ident in seen: continue
            seen.add(ident)
            if kind == "family_event":
                spouses = {p for p, in self.q("""SELECT pp.person_id FROM persona_relation r JOIN person_persona pp ON pp.status='accepted' AND pp.persona_id=CASE WHEN r.persona_id=? THEN r.related_persona_id ELSE r.persona_id END
                                                 WHERE r.kind='spouse' AND ? IN (r.persona_id, r.related_persona_id)""", persona, persona)}
                fam = next((fm for fm in fams if spouses & {p for p, in self.q("SELECT person_id FROM family_member WHERE family_id=? AND role='partner'", fm)}), None)
                if fam is None or self.stated_on(sha, f, family=fam): continue      # the spouse it names is not accepted on it yet: the fact waits for that decision
                events, whose = self.owner_events(ftype, family=fam), " with " + ", ".join(n for n, in self.q("SELECT p.display_name FROM family_member fm JOIN person p ON p.id=fm.person_id WHERE fm.family_id=? AND fm.role='partner' AND fm.person_id<>?", fam, pid))
            else:
                if self.stated_on(sha, f, person=pid): continue
                events, whose = self.owner_events(ftype, person=pid), ""
                if kind == "attribute": events = [e for e in events if (e["value"] or "") == (f["value_text"] or "")]
            eid, choice = self.event_for(f, events, once=ftype in ONCE or kind == "attribute")
            if eid or not choice: continue
            t = ftype.lower(); ids = ", ".join(choice); n = len(events)
            fd = {"start": f["date_start"], "end": f["date_end"], "qualifier": f["date_qualifier"]}
            if not (f["date_start"] or f["date_end"]): out.append(f"{t}: {label} has no date and fits none of your {n} {t} events{whose} ({ids}); place fact {fid} on one with tools/conclude.py place")
            elif any(date_closeness(fd, e) is not None for e in events): out.append(f"{t}: {label} dates it {dtext}, which fits {len(choice)} of your {n} {t} events{whose} equally ({ids}); place fact {fid} on the one it means with tools/conclude.py place")
            else: out.append(f"{t}: {label} dates it {dtext}, which fits none of your {n} {t} events{whose} ({ids}); place fact {fid} on the one it means with tools/conclude.py place")
        return list(dict.fromkeys(out))
    def _record(self, sha):
        """(the record's collection or file name, its locator or None) as Catalog.disagreements names a record; ("the file",
        None) for the imported tree file."""
        r = self.q("""SELECT coalesce(c.name, ar.original_filename, substr(ar.sha256,1,12)), ar.locator_value, ar.sha256 IN (SELECT artifact_sha256 FROM tree_import)
                      FROM artifact ar LEFT JOIN collection c ON c.id=ar.collection_id WHERE ar.sha256=?""", sha)
        if not r: return "no record", None
        name, loc, is_file = r[0]
        return ("the file", None) if is_file else (name, loc if loc and loc != name else None)
    def record_label(self, sha):
        """A record in words: its collection (or file name) and its locator; "the file" for the imported tree file."""
        return self._labels([self._record(sha)])
    @staticmethod
    def _labels(records):
        """Records in words, each collection once with every locator under it: [(name, locator or None)] in order."""
        locs = {}
        for name, loc in records:
            locs.setdefault(name, [])
            if loc and loc not in locs[name]: locs[name].append(loc)
        return " and ".join(f"{n} ({', '.join(l)})" if l else n for n, l in locs.items())
    def _statement(self, sha, pf, notes):
        vouched = False
        try: vouched = bool((json.loads(notes or "{}") or {}).get("vouched"))
        except (ValueError, AttributeError): pass
        return ("your own word", None) if pf is None and vouched else self._record(sha)
    def said_by(self, eid):
        """Who gives an event its date, in words: the record of each statement on it that is not rejected and whose date agrees
        with the event's own, or of every statement when none does; "your own word" for a vouch, which accepts the event's own
        date; "no statement" when nothing stands behind it."""
        ev = self.q("SELECT date_text, date_start, date_end, date_qualifier FROM event WHERE id=?", eid)[0]
        own = {"start": ev[1] or ev[2], "text": ev[0], "qualifier": ev[3]}
        agree, every = [], []
        for sha, pf, notes, text, start, end, qual in self.q("""SELECT a.artifact_sha256, a.persona_fact_id, a.notes, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier
                                                              FROM assertion a LEFT JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                                              WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected' ORDER BY a.asserted_at, a.id""", eid):
            label = self._statement(sha, pf, notes); every.append(label)
            said = own if pf is None else {"start": start or end, "text": text, "qualifier": qual}
            if date_verdict(said, own)[0] == "agrees": agree.append(label)
        return self._labels(agree or every) or "no statement"
    def said_on(self, kind, sid):
        """The records behind a subject's statements that are not rejected, in words: "the file", "your own word" for a vouch."""
        return self._labels([self._statement(sha, pf, notes) for sha, pf, notes in self.q("""SELECT artifact_sha256, persona_fact_id, notes FROM assertion
                                                                                          WHERE subject_kind=? AND subject_id=? AND status<>'rejected' ORDER BY asserted_at, id""", kind, sid)]) or "no statement"
    def life_event(self, pid, etype):
        """The person's event of a type a life holds once as the tree shows it (canonical_event: the one with the strongest
        ground, never one whose every statement is rejected), when it carries a date: {id, text, span (date_span), said
        (said_by)}; None otherwise."""
        ev = self.canonical_event([{"id": i, "type": etype, "basis": self.basis("event", i)} for i, in self.q("""SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                                                                                                             WHERE ep.person_id=? AND e.event_type=?""", pid, etype)], etype)
        if not ev: return None
        text, start, end, qual = self.q("SELECT date_text, date_start, date_end, date_qualifier FROM event WHERE id=?", ev["id"])[0]
        span = date_span(start, end, qual)
        return {"id": ev["id"], "text": text or start or end, "span": span, "said": self.said_by(ev["id"])} if span else None
    def beyond_life(self, pid):
        """Where the person's family links and accepted statements break the limits of one life (data/life-limits.csv,
        docs/DATA-ARCHITECTURE.md §7 decision 12), one line each naming both dates' records or claims and the limit broken,
        for an identity question: an accepted statement on the person's events or their marriages' dated after the death the
        tree shows (the types a life holds after its end excepted: life_limits' after_death_types) or before the birth (a
        birth statement excepted); as a child of each parent a family link gives (accepted or the file's claim, never a
        rejected one), a parent too young or too old at the birth, or a birth after the mother's death or too long after the
        father's (parent_limit); and two census records of one year (record_kinds' census household, the statement of the
        record's own year), each accepted, putting the person in places that do not agree either way (place_verdict). The
        dates compared are the events' own as the tree shows them (life_event), whatever stands behind them, each named, so
        the owner reads whether a claim or a record is what breaks. Nothing is changed here."""
        L = life_limits(); out = []; kinds = {}
        name = self.q("SELECT display_name FROM person WHERE id=?", pid)[0][0]
        birth, death = self.life_event(pid, "Birth"), self.life_event(pid, "Death")
        fams = [f for f, in self.q("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", pid) if not self.link_rejected(f, pid, "partner")]
        for sha, ftype, text, start, end, qual in self.q(f"""SELECT DISTINCT a.artifact_sha256, pf.fact_type, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier FROM assertion a
                                                             JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN event_participant ep ON ep.event_id=a.subject_id
                                                             WHERE a.subject_kind='event' AND a.status='accepted' AND coalesce(pf.date_start, pf.date_end) IS NOT NULL
                                                             AND (ep.person_id=? OR ep.family_id IN ({','.join('?' * len(fams)) or "''"})) ORDER BY pf.date_start, a.asserted_at, a.id""", pid, *fams):
            span = date_span(start, end, qual)
            if not span: continue
            said = f"{ftype.lower()} {text or start or end} ({self.record_label(sha)})"
            if death and ftype not in L["after_death_types"] and span[0] and death["span"][1] and span[0] > death["span"][1]:
                out.append(f"{said} is dated after {name}'s death, {death['text']} ({death['said']}): a statement after the death")
            if birth and ftype != "Birth" and span[1] and birth["span"][0] and span[1] < birth["span"][0]:
                out.append(f"{said} is dated before {name}'s birth, {birth['text']} ({birth['said']}): a statement before the birth")
        for fid, in (self.q("SELECT family_id FROM family_member WHERE person_id=? AND role='child'", pid) if birth else []):
            if self.link_rejected(fid, pid, "child"): continue
            link = self.said_on("family_member", json.dumps([fid, pid, "child"], separators=(",", ":"), sort_keys=True))
            for par, pname, psex in self.q("""SELECT fm.person_id, p.display_name, p.sex FROM family_member fm JOIN person p ON p.id=fm.person_id
                                               WHERE fm.family_id=? AND fm.role='partner' AND p.merged_into IS NULL ORDER BY p.display_name""", fid):
                if self.link_rejected(fid, par, "partner"): continue
                pb, pd = self.life_event(par, "Birth"), self.life_event(par, "Death")
                hit = parent_limit(psex, pb and pb["span"], pd and pd["span"], birth["span"])
                if not hit: continue
                on, words = hit; d = pb if on == "birth" else pd
                out.append(f"{name}, born {birth['text']} ({birth['said']}), a child of {pname} (the link: {link}), {'born' if on == 'birth' else 'who died'} {d['text']} ({d['said']}): {words}")
        census = {}
        for sha, start, raw, ps_id in self.q("""SELECT DISTINCT a.artifact_sha256, pf.date_start, ps.raw, ps.id FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                                 JOIN place_string ps ON ps.id=pf.place_string_id JOIN event_participant ep ON ep.event_id=a.subject_id
                                                 WHERE a.subject_kind='event' AND a.status='accepted' AND ep.person_id=? AND pf.fact_type IN ('Residence','Census')
                                                 AND pf.date_start IS NOT NULL ORDER BY pf.date_start, a.asserted_at""", pid):
            if sha not in kinds: kinds[sha] = record_kinds(self.cx, sha)
            k, yr = kinds[sha]
            if "census household" not in k or (yr and str(yr) != start[:4]): continue
            census.setdefault(start[:4], []).append((self.record_label(sha), raw, self.fact_place(ps_id)))
        for y, said in sorted(census.items()):
            for i, (la, ra, pa) in enumerate(said):
                for lb, rb, pb in said[i + 1:]:
                    if la != lb and place_verdict(pa, pb)[0] == "disagrees" and place_verdict(pb, pa)[0] == "disagrees":
                        out.append(f"census {y}: {la} puts {name} at {ra}, {lb} at {rb}: one person in two places in one census")
        return list(dict.fromkeys(out))
    def dated_names(self, place_id):
        """place_id's own former names (place_name rows with a valid_from or valid_to, written by tools/resolve_places.py
        from Wikidata): [(name, valid_from, valid_to), ...], for place_verdict to agree a record naming one with the
        place as it is now. [] for no place_id or none dated."""
        if not place_id: return []
        return self.q("SELECT name, valid_from, valid_to FROM place_name WHERE place_id=? AND (valid_from IS NOT NULL OR valid_to IS NOT NULL)", place_id)
    def place_search_names(self, place_id, year=None, person_id=None):
        """Every accurate name for place_id, ordered for a search (docs/RESEARCH-WORKFLOW.md §3): the one valid at year
        first (a dated name, dated_names, whose range covers it), then the as-written strings the person's own accepted
        records use for this place, then its current name, then every other dated name. A collection is found under the
        place's modern name and the record inside it under the name its own day used, so the modern name is never
        dropped even when a period name is offered first. A plain list of strings, de-duplicated in that order; []
        without a place_id."""
        if not place_id: return []
        dated = self.dated_names(place_id)
        def covers(vf, vt):
            if year is None: return False
            try:
                if vf and int(str(vf)[:4]) > year: return False
                if vt and int(str(vt)[:4]) < year: return False
            except ValueError: return False
            return True
        out = [n for n, vf, vt in dated if covers(vf, vt)]
        if person_id:
            out += [r[0] for r in self.q("""SELECT DISTINCT ps.raw FROM place_string ps JOIN persona_fact pf ON pf.place_string_id=ps.id
                                            JOIN person_persona pp ON pp.persona_id=pf.persona_id
                                            WHERE ps.place_id=? AND pp.person_id=? AND pp.status='accepted'""", place_id, person_id)]
        out.append(self._place_chain(place_id)["text"])
        out += [n for n, _, _ in dated]
        return list(dict.fromkeys(x for x in out if x))
    def find_person(self, key):
        """A person by id, by the last six characters of the id in brackets or alone ("Jane Roe [MEXW2C]", "MEXW2C"), by exact
        display name, or by a substring of the name. Several matches stop the tool and list them with their six characters, so a
        decision never lands on whichever sorts first. A person merged into another (`person.merged_into`) does not match:
        the merge moved everything about them onto the person they duplicate."""
        m = re.search(r"\[([A-Z0-9]{6})\]\s*$", key or "") or re.fullmatch(r"[A-Z0-9]{6}", (key or "").strip())
        if m: r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND merged_into IS NULL AND id LIKE ?", self.tree_id, "%" + (m.group(1) if m.groups() else m.group(0)))
        else:
            r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND merged_into IS NULL AND (id=? OR display_name=?) ORDER BY display_name", self.tree_id, key, key)
            if not r: r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND merged_into IS NULL AND display_name LIKE ? ORDER BY display_name LIMIT 8", self.tree_id, f"%{key}%")
        if not r: sys.exit(f"no person matching {key!r}")
        if len(r) > 1: sys.exit(f"{len(r)} people match {key!r}: " + ", ".join(f"{n} [{i[-6:]}]" for i, n in r) + "; name one by its six characters")
        return r[0][0]
    def person(self, pid):
        r = self.q("SELECT id, display_name, sex FROM person WHERE id=?", pid)[0]
        names = self.q("SELECT given, surname, suffix, is_primary, name_type FROM person_name WHERE person_id=? ORDER BY is_primary DESC", pid)
        aliases = [a[0] for a in self.q("SELECT value FROM alias WHERE entity_kind='person' AND entity_id=? AND status<>'rejected'", pid)]
        return {"id": r[0], "name": r[1], "sex": r[2], "names": names, "aliases": aliases}
    def events(self, pid):
        out = []
        for eid, et, dt, ds, de, place_id in self.q("""SELECT e.id, e.event_type, e.date_text, e.date_start, e.date_end, e.place_id FROM event e
                JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? ORDER BY e.date_start""", pid):
            out.append({"id": eid, "type": et, "date_text": dt, "year": year(ds) or year(de), "place": self.place(eid, place_id),
                        "basis": self.basis("event", eid), "citations": self.citations("event", eid)})
        return out
    def place(self, eid, place_id):
        """The event's place: the resolved place's chain when it has one, else among the place strings behind the event —
        the string on an accepted assertion before one on an undecided assertion before one on a rejected assertion, and
        within a tier the one resolved to the deepest place before a shallower or unresolved one, ties by its words: an
        event with two strings shows the one the owner's decision stands on and, when that string is itself resolved,
        its chain — never the alphabet over a resolved chain."""
        if place_id: return self._place_chain(place_id)
        rows = self.q("""SELECT ps.raw, ps.place_id, a.status FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN place_string ps ON ps.id=pf.place_string_id
                         WHERE a.subject_kind='event' AND a.subject_id=?""", eid)
        if not rows: return None
        tier = {"accepted": 0, "undecided": 1}
        rows.sort(key=lambda r: (tier.get(r[2], 2), -self._place_depth(r[1]) if r[1] else 0, r[0]))
        text, winner_place_id, _ = rows[0]
        if winner_place_id: return self._place_chain(winner_place_id)
        low = " " + text.lower().replace(",", " ") + " "
        toks = [t.strip().lower() for t in text.split(",") if t.strip()]
        st = next((t for t in toks if t in US_STATES), None) or next((n for n in US_STATES if f" {n} " in low), None)
        if st or any(f" {n} " in low for n in US_NAMES): country = "united states"
        else:                                                         # the country a record writes last; a country's name earlier in the string is a town or county of that name (Lebanon, Poland, Peru)
            last = toks[-1] if toks else ""
            country = (COUNTRIES.get(last) or ("Poland" if last in ("silesia", "schlesien") else None) or "").lower() or None   # Silesia, written as a country, lies mostly in today's Poland
        return {"text": text, "resolved": False, "country": country, "state": st}
    def _place_chain(self, place_id):
        chain, pid, region = [], place_id, {"country": None, "state": None}
        while pid:
            r = self.q("SELECT name, place_type, parent_id FROM place WHERE id=?", pid)[0]; chain.append(r[0])
            if r[1] == "country": region["country"] = r[0].lower()
            if r[1] == "state": region["state"] = r[0].lower()
            pid = r[2]
        return {"text": " < ".join(chain), "resolved": True, "place_id": place_id, **region}
    def _place_depth(self, place_id):
        d = 0
        while place_id:
            r = self.q("SELECT parent_id FROM place WHERE id=?", place_id)
            place_id = r[0][0] if r else None
            d += 1
        return d
    def _event_ground(self, eid):
        """(accepted, non-rejected) assertion counts on this event: how much of the record actually stands behind it."""
        st = [r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind='event' AND subject_id=?", eid)]
        return sum(s == "accepted" for s in st), sum(s != "rejected" for s in st)
    def canonical_event(self, ev, etype):
        """Among a person's events of one type, the one with the strongest ground. An event whose every assertion is
        rejected is discredited and shows nowhere as the value: it is never picked, even as the sole
        event of the type. Among the rest, an event with an accepted assertion beats one with none, more accepted
        assertions beat fewer, and a further tie (an accepted date on one duplicate beside an accepted place on
        another) breaks on total ground — every non-rejected assertion — so the more corroborated record wins."""
        cands = [e for e in ev if e["type"] == etype and e["basis"] != "rejected"]
        if not cands: return None
        scored = [(e, self._event_ground(e["id"])) for e in cands]
        scored.sort(key=lambda x: (x[0]["basis"] == "accepted", x[1][0], x[1][1]), reverse=True)
        return scored[0][0]
    KEY_FACTS = ("name", "sex", "birth", "death", "parents", "spouses", "children")
    def key_fact_basis(self, pid, ev=None):
        """basis per key fact: accepted | claim | rejected | None (no claim)."""
        ev = self.events(pid) if ev is None else ev
        out = {"name": self.basis("person", pid), "sex": self.basis("person", pid)}
        for f in ("birth", "death"):
            e = self.canonical_event(ev, f.title()); out[f] = e["basis"] if e else None
        for f in ("parents", "spouses", "children"): out[f] = self.link_basis(pid, f)
        return out
    def baseline(self, pid, ev=None):
        """The baseline is complete when no key fact is Undecided; absent and rejected facts are decided."""
        kb = self.key_fact_basis(pid, ev); und = [f for f in self.KEY_FACTS if kb[f] == "claim"]
        return {"key_facts": len(kb), "key_facts_accepted": sum(1 for b in kb.values() if b == "accepted"), "undecided": und, "complete": not und}
    def link_rejected(self, fid, person_id, role):
        """True when every assertion behind this family membership is rejected."""
        st = {r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind='family_member' AND subject_id=?", json.dumps([fid, person_id, role], separators=(",", ":"), sort_keys=True))}
        return bool(st) and st <= {"rejected"}
    def link_basis(self, pid, field):
        """accepted | claim | None for parents / spouses / children, from the family_member assertions behind them."""
        if field == "children":
            subs = [json.dumps([f, c, "child"], separators=(",", ":"), sort_keys=True) for f, in self.q("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", pid)
                    for c, in self.q("SELECT person_id FROM family_member WHERE family_id=? AND role='child'", f)]
        else:
            role = "child" if field == "parents" else "partner"
            subs = [json.dumps([f, pid, role], separators=(",", ":"), sort_keys=True) for f, in self.q("SELECT family_id FROM family_member WHERE person_id=? AND role=?", pid, role)]
        if not subs: return None
        st = set()
        for sid in subs: st |= {r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind='family_member' AND subject_id=?", sid)}
        return "accepted" if "accepted" in st else ("rejected" if st and st <= {"rejected"} else "claim")
    def basis(self, kind, sid):
        st = {r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind=? AND subject_id=?", kind, sid)}
        return "accepted" if "accepted" in st else ("rejected" if st == {"rejected"} else "claim")
    def is_subject(self, sha, person_id):
        """Whether the persona accepted as this person on this artifact is the record's own subject: the persona others on
        it relate to, with no relation of its own to another persona (the deceased of an obituary, the memorial's subject,
        a record page's principal). A persona that relates to another (a survivor, a listed relative, a household member)
        is named on the record, never its own; a record that merely names a person is a relative's record and a lead. Only a
        persona of a current extraction counts: a superseded reading's links are history."""
        return bool(self.q("""SELECT 1 FROM person_persona pp JOIN persona p ON p.id=pp.persona_id JOIN extraction e ON e.id=p.extraction_id
                               WHERE pp.person_id=? AND pp.status='accepted' AND p.artifact_sha256=? AND e.superseded_by IS NULL
                               AND NOT EXISTS (SELECT 1 FROM persona_relation pr WHERE pr.persona_id=p.id)""", person_id, sha))
    def citations(self, kind, sid, person_id=None, subject_only=False):
        """[(collection name, apid, held artifact sha or None, collection id)] for a subject; held for the person given, when
        one is (a page holds a citation for the people it names), else for anyone. subject_only restricts "held" to a
        citation whose accepted persona for person_id is the record's own subject (is_subject), for a one-person checklist
        row (an obituary, a death or birth record, a cemetery record, naturalization, a draft card, Social Security): a
        record that merely names the person, without being their own, stays cited, never held. Household rows (census,
        church, passenger lists) pass subject_only=False and count every member."""
        out = []
        for cname, notes, sha, tier, cid in self.q(f"""SELECT COALESCE(c.name, ac.name), a.notes, a.artifact_sha256, {tier_sql()}, COALESCE(c.id, ac.id) FROM assertion a
                LEFT JOIN collection c ON json_valid(a.notes) AND c.id=json_extract(a.notes,'$.collection_id')
                LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                LEFT JOIN collection ac ON ac.id=ar.collection_id
                WHERE a.subject_kind=? AND a.subject_id=? AND a.status<>'rejected'""", kind, sid):
            apid = json.loads(notes).get("apid") if notes and notes.startswith("{") else None
            held = sha if sha and (tier or "")[:2] in ("T1", "T2", "T3") else (self.held_for(apid, person_id) if person_id else self.held_apids().get(apid))   # the record a match attached, or the archived page the citation names; the T4 tree export is not a held record
            if held and subject_only and not (person_id and self.is_subject(held, person_id)): held = None
            if cname or held: out.append((cname or "", apid, held, cid))
        return out
    def waiting(self, pid):
        """What waits on a person, in plain counts: documents to decide (proposals about them: a persona proposed as them, a new
        person on a record fetched for them), planned steps that run on their own (a connector can take them), planned steps
        only a hand can take (a page saved in the owner's browser, an assisted search, a film browsed by hand), whether run
        before or not, conflicts open, and leads (a relative a memorial merely
        lists, tools/plan.py's listed_relative_leads, row_key "listed relative:<memorial id>": not a document, since the
        matcher never proposes one and the rule could never take it). Nothing here is a score."""
        docs = self.q("""SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person')
                         AND (json_extract(payload_json,'$.person_id')=? OR (kind='new_person' AND json_extract(payload_json,'$.subject_person_id')=?))""", self.tree_id, pid, pid)[0][0]
        leads = self.q("SELECT COUNT(*) FROM search_plan WHERE person_id=? AND status='planned' AND row_key LIKE 'listed relative:%'", pid)[0][0]
        conn = {sid for sid, s in self.sources.items() if s.get("connector")}
        runs, hand = 0, 0
        for kind, mode, holder in self.q("SELECT kind, mode, locator_source_id FROM search_plan WHERE person_id=? AND status='planned' AND row_key NOT LIKE 'listed relative:%'", pid):   # a lead is counted as a lead alone
            if (kind == "fetch" and mode == "fetch" and holder in conn) or (kind == "search" and mode == "auto"): runs += 1
            elif (kind == "fetch" and mode == "fetch") or (kind == "search" and mode == "assisted"): hand += 1
        conflicts = self.q("SELECT COUNT(*) FROM research_question WHERE subject_person_id=? AND kind='conflict' AND status='open'", pid)[0][0]
        tiers = {t for t, in self.q(f"""SELECT CASE WHEN json_valid(a.notes) AND (json_extract(a.notes,'$.vouched')=1 OR json_extract(a.notes,'$.uncited')=1) THEN 'vouch' ELSE {tier_sql()} END FROM assertion a
                                       LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                                       WHERE a.tree_id=? AND a.status='accepted' AND ((a.subject_kind='person' AND a.subject_id=?)
                                          OR (a.subject_kind='event' AND a.subject_id IN (SELECT event_id FROM event_participant WHERE person_id=?)))""", self.tree_id, pid, pid)}
        editable_only = bool(tiers) and tiers <= {"T4"}         # every accepted fact rests on a source anyone can edit
        return {"documents": docs, "runs_next": runs, "needs_hand": hand, "conflicts": conflicts, "editable_only": editable_only, "leads": leads}
    def family(self, pid):
        """Relatives through family memberships; a membership whose assertions are all rejected does not count."""
        fam = {"parents": [], "spouses": [], "children": [], "siblings": [], "families": []}
        for fid, role in self.q("SELECT family_id, role FROM family_member WHERE person_id=?", pid):
            if self.link_rejected(fid, pid, role): continue
            members = [m for m in self.q("SELECT fm.person_id, fm.role, p.display_name FROM family_member fm JOIN person p ON p.id=fm.person_id WHERE fm.family_id=?", fid)
                       if not self.link_rejected(fid, m[0], m[1])]
            if role == "child":
                fam["parents"] += [(m[0], m[2]) for m in members if m[1] == "partner"]
                fam["siblings"] += [(m[0], m[2]) for m in members if m[1] == "child" and m[0] != pid]
            else:
                sp = [(m[0], m[2]) for m in members if m[1] == "partner" and m[0] != pid]
                fam["spouses"] += sp; fam["children"] += [(m[0], m[2]) for m in members if m[1] == "child"]
                marr = self.q("""SELECT e.id, e.date_start, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.family_id=? AND e.event_type='Marriage'""", fid)
                div = self.q("""SELECT e.id, e.date_text, e.date_start FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.family_id=? AND e.event_type='Divorce'""", fid)
                fam["families"].append({"id": fid, "spouse": sp[0][1] if sp else None, "spouse_id": sp[0][0] if sp else None,
                                        "marriages": [{"id": m[0], "year": year(m[1]), "place": self.place(m[0], m[2]), "basis": self.basis("event", m[0]), "citations": self.citations("event", m[0])} for m in marr],
                                        "divorces": [{"id": x[0], "date": x[1], "year": year(x[2]), "basis": self.basis("event", x[0])} for x in div]})
        return fam
    def home(self):
        """The tree's home person (tools/tree.py home), or None."""
        r = self.q("SELECT home_person_id FROM tree WHERE id=?", self.tree_id)
        return r[0][0] if r else None
    def tiers(self):
        """{person id: generation relative to the home person} for everyone a chain of family links reaches from the home
        person (docs/DATA-ARCHITECTURE.md §7 decision 3): a parent one generation up, a child one down, a partner the same,
        along every membership whose assertions are not all rejected (accepted or claimed, as `family` reads them); a person
        reached by more than one path takes the nearest generation. Up is positive. Computed once per Catalog; empty when
        the tree has no home person."""
        if self._tiers is not None: return self._tiers
        self._tiers = {}
        home = self.home()
        if not home: return self._tiers
        fams = {}; best = {home: 0}; seen = {(home, 0)}; frontier = [(home, 0)]
        while frontier:
            nxt = []
            for pid, g in frontier:
                if pid not in fams: fams[pid] = self.family(pid)
                for rel, step in (("parents", 1), ("children", -1), ("spouses", 0)):
                    for other, _ in fams[pid][rel]:
                        og = g + step
                        if abs(og) > 12 or (other, og) in seen: continue
                        seen.add((other, og)); nxt.append((other, og))
                        if other not in best or abs(og) < abs(best[other]): best[other] = og
            frontier = nxt
        self._tiers = best
        return best
    def living(self, pid):
        """The person's living status as the default reads it (docs/DATA-ARCHITECTURE.md §7 decision 3): {status: living |
        unknown | deceased, tier, reason}. The owner's word (person.living_override) stands above everything; death evidence
        the tree holds (v_person_vitals.has_death_evidence) makes a person deceased at any tier; tiers 0 and 1 are living, tier
        2 unknown until the owner confirms the person (tools/conclude.py living), tier 3 and beyond and a person no chain of
        links reaches from the home person deceased. A tree with no home person places nobody, so everyone in it is unknown
        until one is set. The tier is the generation's distance, None for an unreached person."""
        override, death = self.q("SELECT living_override, has_death_evidence FROM v_person_vitals WHERE person_id=?", pid)[0]
        g = self.tiers().get(pid); tier = abs(g) if g is not None else None
        if override: return {"status": override, "tier": tier, "reason": "the owner's word"}
        if death: return {"status": "deceased", "tier": tier, "reason": "death evidence"}
        if not self.home(): return {"status": "unknown", "tier": None, "reason": "no home person set: tools/tree.py home"}
        if tier is None: return {"status": "deceased", "tier": None, "reason": "no link to the home person"}
        if tier <= 1: return {"status": "living", "tier": tier, "reason": f"tier {tier}, living by default"}
        if tier == 2: return {"status": "unknown", "tier": 2, "reason": "tier 2, unconfirmed"}
        return {"status": "deceased", "tier": tier, "reason": f"tier {tier}, deceased by default"}
    def fetched_rows(self, pid):
        """Checklist row keys (record:instance) with a done step whose record is held: an archived artifact in its log, or an
        artifact at the step's locator (for a record id, one that holds it for this person). {row key: whether a held record
        is on the person themselves (a step with on_json []) and is that record's own subject there (is_subject), not merely
        named on a record that is someone else's -- the same gate a one-person row's own citations already pass
        (person_citations subject_only=True). A household row is held by any of them regardless: the key's presence, not
        this value, is what a household row's own status_of check reads."""
        out = {}
        for sid, rk, lkind, lval, on in self.q("SELECT id, row_key, locator_kind, locator_value, on_json FROM search_plan WHERE person_id=? AND status='done'", pid):
            shas = {s for js, in self.q("SELECT artifacts_json FROM search_log WHERE plan_step_id=? AND artifacts_json IS NOT NULL AND artifacts_json<>'[]'", sid) for s in json.loads(js)}
            if not shas and lkind == "apid" and lval:
                h = self.held_for(lval, pid)
                if h: shas.add(h)
            if not shas and lkind and lval:
                shas |= {s for s, in self.q("SELECT sha256 FROM artifact WHERE locator_kind=? AND locator_value=?", lkind, lval)}
            if not shas: continue
            on_person = (on or "[]") == "[]"
            out[rk] = out.get(rk, False) or (on_person and any(self.is_subject(s, pid) for s in shas))
        return out
    def page_groups(self):
        if self._groups is None: self._groups = page_groups(self.cx)
        return self._groups
    def held_apids(self):
        """{record id: sha256} for every citation whose record is in the archive: what each artifact holds (holds)."""
        if self._held is None: self._held = held_apids(self.cx, self.page_groups())
        return self._held
    def holdings(self):
        if self._holdings is None: self._holdings = holdings(self.cx, self.page_groups())
        return self._holdings
    def held_for(self, apid, pid):
        """The archived record holding this citation for this person (held_for), or None."""
        return held_for(self.cx, apid, pid, self.holdings()) if apid else None
    def same_page(self, apid): return same_page(self.cx, apid, self.page_groups())
    def cited(self):
        """The citation's own details per Ancestry record id, from the import's assertions: {apid: {page, url, names}}, names being
        the tree's names of the people the citation sits on, in the order met (the only name the export carries for the record)."""
        if getattr(self, "_cited", None) is not None: return self._cited
        out = {}
        for apid, page, url, name in self.q("""SELECT json_extract(a.notes,'$.apid'), json_extract(a.notes,'$.page'), json_extract(a.notes,'$.url'), p.display_name
                FROM assertion a LEFT JOIN person p ON p.id = CASE a.subject_kind WHEN 'person' THEN a.subject_id
                     ELSE (SELECT ep.person_id FROM event_participant ep WHERE ep.event_id=a.subject_id AND ep.person_id IS NOT NULL LIMIT 1) END
                WHERE a.tree_id=? AND a.notes LIKE '{"apid":%' ORDER BY a.asserted_at, a.id""", self.tree_id):
            c = out.setdefault(apid, {"page": page, "url": url, "names": []})
            c["page"] = c["page"] or page; c["url"] = c["url"] or url
            if name and name not in c["names"]: c["names"].append(name)
        self._cited = out
        return out
    def person_citations(self, pid, subject_only=False):
        """All citations attached to a person: on the person row and on every event of theirs."""
        cits = self.citations("person", pid, pid, subject_only=subject_only)
        for eid, in self.q("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=?", pid):
            cits += self.citations("event", eid, pid, subject_only=subject_only)
        return cits

COUNTRIES = country_words()
