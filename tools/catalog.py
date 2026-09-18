"""Read-only access to a tree's people, events, places, citations and families.

Shared by every tool and by the person screen. Nothing here writes.
"""
import collections, csv, json, os, re, sqlite3, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

US_STATES = {"alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia","hawaii",
             "idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
             "minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey","new mexico","new york",
             "north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota",
             "tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming"}
US_NAMES = {"united states","usa","united states of america","us","british colonies","north america"}

def year(s): return int(s[:4]) if s and s[:4].isdigit() else None

SUFFIX = {"jr", "sr", "ii", "iii", "iv", "esq"}

def split_name(text):
    """(given names, surname, suffix) from a name as written: "Frederick Micheal Ahearn Jr" is given "Frederick Micheal",
    surname "Ahearn", suffix "Jr"; "Ahearn, Frederick M" (surname first, as an index writes it) the same way round. None for a
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
    edits apart, so Ahearn and Ahern, Brant and Brandt, Kriebel and Krebel); or one letter apart in a name of five letters or
    more, whatever the Soundex, an indexer's slip (Ahearu for Ahearn), as long as the first letter stands: a substitution, a
    missing or an extra letter, never Grant for Brant. Returns "" when they differ, "agrees" when written the same, "variant"
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
                "place": v("publication place") or v("census place") or v("place"), "city": v("city"), "url": v("url")}
        if tpl == "{url}": return vals["url"]
        needed = set(PLACEHOLDER.findall(tpl))
        if any(not vals.get(k) for k in needed): return None
        return PLACEHOLDER.sub(lambda m: urllib.parse.quote(str(vals[m.group(1)]), safe=""), tpl)
    if not (given or surname): return None
    if kind == "fs_collection":
        q = [("f.collectionId", h["HolderKey"]), ("q.givenName", given or "")]
        yr = v("year") or (re.search(r"\b(1[78]\d\d|19\d\d)\b", h["HolderCollection"] or "") or [None, None])[1] if re.search(r"census", h["HolderCollection"] or "", re.I) else v("year")
        place = v("census place") or ", ".join(x for x in (v("city"), v("county")) if x) or None
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

US_STATE = {   # a record place written as the bare two-letter code stands for the state it abbreviates
    "al": "alabama", "ak": "alaska", "az": "arizona", "ar": "arkansas", "ca": "california", "co": "colorado",
    "ct": "connecticut", "de": "delaware", "fl": "florida", "ga": "georgia", "hi": "hawaii", "id": "idaho",
    "il": "illinois", "in": "indiana", "ia": "iowa", "ks": "kansas", "ky": "kentucky", "la": "louisiana",
    "me": "maine", "md": "maryland", "ma": "massachusetts", "mi": "michigan", "mn": "minnesota",
    "ms": "mississippi", "mo": "missouri", "mt": "montana", "ne": "nebraska", "nv": "nevada",
    "nh": "new hampshire", "nj": "new jersey", "nm": "new mexico", "ny": "new york", "nc": "north carolina",
    "nd": "north dakota", "oh": "ohio", "ok": "oklahoma", "or": "oregon", "pa": "pennsylvania",
    "ri": "rhode island", "sc": "south carolina", "sd": "south dakota", "tn": "tennessee", "tx": "texas",
    "ut": "utah", "vt": "vermont", "va": "virginia", "wa": "washington", "wv": "west virginia",
    "wi": "wisconsin", "wy": "wyoming",
}

def collection_state(name):
    """The US state a collection's own name states as its coverage, when the registry names it first ("<State>, U.S.,
    <kind>, <years>", data/data-sources.csv's own naming): the record's own event place, for a bare county place_verdict
    otherwise cannot place. None when the collection's name does not lead with one."""
    first = (name or "").split(",")[0].strip()
    return first if first.lower() in US_STATES else None

def _place_verdict_once(record, tree, supply=None):
    norm = lambda s: re.sub(r"\b(county|co\.?|township|twp\.?|magisterial district \d+|district \d+)\b", " ", COUNTRY.sub("usa", s.lower()))   # a jurisdiction word is not a place part
    expand = lambda p: US_STATE.get(p, p)                             # a two-letter US state code stands for the state it abbreviates
    part = lambda p: expand(norm(p).strip().rstrip(".").strip())      # one piece normalised; "Ky." is the code with a period
    parts = lambda s: [(part(p), p.strip(" .")) for p in re.split(r"<|,", s) if part(p)]   # (normalised, as written)
    tparts = [p for p, _ in parts(tree)]
    below = [p for p in tparts if p != "usa"]
    if not below: return "absent", None                             # a tree place that names only the country says nothing to compare
    rparts = [(p, w) for p, w in parts(record) if p != "usa"]         # the country is not a part to count on either side
    if not rparts: return "absent", None
    if supply: rparts = rparts + [(part(supply), supply)]            # a bare county takes the record's own event place's state, for comparison only
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

def place_verdict(record, tree, record_state=None, dated_names=None):
    """(verdict, note): agrees when every part the record states, at or below the country, is a part of the tree's resolved
    chain — 'Town < County < State < Country' — matched whole after normalisation (a jurisdiction word stripped, a
    two-letter US state code expanded to its name, with or without a period), never as a substring of another word: 'Kent'
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
    Tonan, a village Morioka absorbed in 1992) — it then agrees on that name, the note naming the period it held it. The
    string itself is never changed, only compared. absent when either side has none."""
    if not record or not tree: return "absent", None
    v, note = _place_verdict_once(record, tree)
    if v == "disagrees" and record_state and re.search(r"\bcounty\b", record, re.I) and not re.search(r"<|,", record):
        v2, note2 = _place_verdict_once(record, tree, supply=record_state)
        if v2 == "agrees": return v2, (f"{note2}; " if note2 else "") + f"supplying {record_state}, the record's own event place, for the bare county"
    if v == "disagrees" and dated_names:
        note3 = _dated_agree(record, dated_names)
        if note3: return "agrees", note3
    return v, note


def tier_sql(ar="ar", s="s"):
    """SQL for an artifact's effective trust tier, given the artifact's alias and its joined source's alias: the tier of the
    source the artifact's own identity names (an ark is FamilySearch, a memorial id is Find a Grave), else of the source it
    was archived under. artifact.trust_tier is the tier copied at archive time and can fall behind the registry."""
    return f"""coalesce((SELECT s2.trust_tier FROM source s2 WHERE s2.id = CASE WHEN EXISTS (SELECT 1 FROM artifact_locator l WHERE l.artifact_sha256={ar}.sha256 AND l.kind='ark') THEN 'D03'
                                                                 WHEN EXISTS (SELECT 1 FROM artifact_locator l WHERE l.artifact_sha256={ar}.sha256 AND l.kind='memorial_id') THEN 'E01' END), {s}.trust_tier)"""

def source_tier(cx, sha):
    """An artifact's effective trust tier (tier_sql), or None."""
    r = cx.execute(f"SELECT {tier_sql()} FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?", (sha,)).fetchone()
    return r[0] if r else None

class Catalog:
    def __init__(self, cx, tree_id):
        self.cx, self.tree_id = cx, tree_id
        self.q = lambda s, *a: cx.execute(s, a).fetchall()
        self.sources = {r[0]: {"name": r[1], "access": r[2] or "", "status": r[3] or "", "cost": r[4] or "", "connector": r[5] or "", "coverage": r[6] or ""}
                        for r in self.q("SELECT id, name, access, status, cost, connector, coverage FROM source")}
        self.holders = holders()
        self._groups = self._held = self._holdings = None
    def disagreements(self, pid):
        """Where an accepted record says something else than the tree's event or than another statement on it: for each event
        of the person and each of date and place, one line per differing value, naming every statement on each side and the
        tree's own value. Every Accepted assertion is compared against the event's own date (as dates) or shown place, and
        against every other statement on the event that is not rejected (undecided claims included: the file's own claim, a
        page anyone can edit); place is compared with Catalog.place_verdict, so a coarser or finer record, or one naming a
        dated former name, agrees rather than disagreeing. A record cited under two collection names but one locator (the same
        certificate indexed twice) is one statement, not two. Statements whose values agree with each other (transitively,
        among only those already found disagreeing with something) are grouped as one side, so six comparisons that all turn
        on the same 11th-against-10th read as one question, not six. The tree's value is never changed by a record; the
        difference is a conflict question, and the shown value stays what Catalog.place chooses."""
        out = []
        for e in self.q("""SELECT e.id, e.event_type, e.date_text, e.date_start, e.date_qualifier, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                           WHERE ep.person_id=? ORDER BY e.event_type, e.date_start""", pid):
            place_now = self.place(e[0], e[5])
            tree_place = place_now["text"] if place_now else None
            kind = e[1].lower()
            rows = self.q("""SELECT pf.date_text, pf.date_start, pf.date_qualifier, ps.raw, coalesce(c.name, ar.original_filename, substr(ar.sha256,1,12)),
                                    ar.locator_value, a.status, a.id, ar.locator_kind
                             FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                             JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN collection c ON c.id=ar.collection_id
                             WHERE a.subject_kind='event' AND a.subject_id=? AND a.status<>'rejected' ORDER BY a.asserted_at, a.id""", e[0])
            groups, order = {}, []                            # one group per record identity (its locator), whatever collection name cites it
            for f in rows:
                gk = f[5] or f[7]
                if gk not in groups:
                    groups[gk] = {"collections": [], "locator": f[5], "is_file": f[8] == "file", "status": "undecided", "date": None, "place": None, "state": None}
                    order.append(gk)
                g = groups[gk]
                if f[4] and f[4] not in g["collections"]: g["collections"].append(f[4])
                if (f[0] is not None or f[1] is not None) and len(f[1] or "") > len(g["date"][1] if g["date"] else ""): g["date"] = (f[0], f[1], f[2])  # the same record's own most specific date wins (a full date over a bare year)
                if f[3] is not None and g["place"] is None: g["place"] = f[3]
                g["state"] = g["state"] or collection_state(f[4])
                if f[6] == "accepted": g["status"] = "accepted"
            def label(gk):
                g = groups[gk]
                if g["is_file"]: return "the file"
                name = " / ".join(g["collections"]) if g["collections"] else (g["locator"] or "record")
                return f"{name} ({g['locator']})" if g["locator"] else name
            for axis in ("date", "place"):
                value_of = (lambda gk: ({"start": groups[gk]["date"][1], "text": groups[gk]["date"][0], "qualifier": groups[gk]["date"][2]} if groups[gk]["date"] else None)) if axis == "date" \
                            else (lambda gk: groups[gk]["place"])
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
                for gk in accepted:
                    v, _ = cmp(value_of(gk), groups[gk]["state"], tree_val, None)
                    if v == "disagrees": pairs.append(("tree", gk))
                    for ok in order:
                        if ok == gk or value_of(ok) is None: continue
                        if ok in accepted and order.index(ok) < order.index(gk): continue   # two accepted statements compared once
                        v2, _ = cmp(value_of(gk), groups[gk]["state"], value_of(ok), groups[ok]["state"])
                        if v2 == "disagrees": pairs.append((gk, ok))
                if not pairs: continue
                nodes = list(dict.fromkeys(n for p in pairs for n in p))
                parent = {n: n for n in nodes}
                def find(x):
                    while parent[x] != x: x = parent[x]
                    return x
                for i, a in enumerate(nodes):                  # group by mutual agreement, among only the statements already in some disagreement
                    av, asa = (tree_val, None) if a == "tree" else (value_of(a), groups[a]["state"])
                    for b in nodes[i + 1:]:
                        bv, bsa = (tree_val, None) if b == "tree" else (value_of(b), groups[b]["state"])
                        if cmp(av, asa, bv, bsa)[0] == "agrees":
                            ra, rb = find(a), find(b)
                            if ra != rb: parent[ra] = rb
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
    def dated_names(self, place_id):
        """place_id's own former names (place_name rows with a valid_from or valid_to, written by tools/resolve_places.py
        from Wikidata): [(name, valid_from, valid_to), ...], for place_verdict to agree a record naming one with the
        place as it is now. [] for no place_id or none dated."""
        if not place_id: return []
        return self.q("SELECT name, valid_from, valid_to FROM place_name WHERE place_id=? AND (valid_from IS NOT NULL OR valid_to IS NOT NULL)", place_id)
    def find_person(self, key):
        """A person by id, by the last six characters of the id in brackets or alone ("Noi Davidson [MEXW2C]", "MEXW2C"), by exact
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
        else: country = next((c for c in ("ireland", "germany", "netherlands", "poland", "japan", "england", "allemagne", "silesia", "schlesien") if f" {c} " in low), None)
        country = {"allemagne": "germany", "silesia": "poland", "schlesien": "poland", "england": "united kingdom"}.get(country, country)
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
        church, passenger lists) pass subject_only=False and keep counting every member as before."""
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
        person on a record fetched for them), steps that run on their own (a connector can take them), steps that need a hand
        (a page saved in the owner's browser, an assisted search), and conflicts open. Nothing here is a score."""
        docs = self.q("""SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person')
                         AND (json_extract(payload_json,'$.person_id')=? OR (kind='new_person' AND json_extract(payload_json,'$.subject_person_id')=?))""", self.tree_id, pid, pid)[0][0]
        conn = {sid for sid, s in self.sources.items() if s.get("connector")}
        runs, hand = 0, 0
        for kind, mode, holder, sources in self.q("SELECT kind, mode, locator_source_id, sources_json FROM search_plan WHERE person_id=? AND status='planned'", pid):
            srcs = json.loads(sources or "[]")
            if (kind == "fetch" and mode == "fetch" and holder in conn) or (kind == "search" and mode == "auto"): runs += 1
            elif (kind == "fetch" and mode == "fetch") or (kind == "search" and mode == "assisted"): hand += 1
        conflicts = self.q("SELECT COUNT(*) FROM research_question WHERE subject_person_id=? AND kind='conflict' AND status='open'", pid)[0][0]
        tiers = {t for t, in self.q(f"""SELECT CASE WHEN json_valid(a.notes) AND (json_extract(a.notes,'$.vouched')=1 OR json_extract(a.notes,'$.uncited')=1) THEN 'vouch' ELSE {tier_sql()} END FROM assertion a
                                       LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                                       WHERE a.tree_id=? AND a.status='accepted' AND ((a.subject_kind='person' AND a.subject_id=?)
                                          OR (a.subject_kind='event' AND a.subject_id IN (SELECT event_id FROM event_participant WHERE person_id=?)))""", self.tree_id, pid, pid)}
        editable_only = bool(tiers) and tiers <= {"T4"}         # every accepted fact rests on a source anyone can edit
        return {"documents": docs, "runs_next": runs, "needs_hand": hand, "conflicts": conflicts, "editable_only": editable_only}
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
    def fetched_rows(self, pid):
        """Checklist row keys (record:instance) with a done step whose record is held: an archived artifact in its log, or an
        artifact at the step's locator (for a record id, one that holds it for this person). {row key: whether a held
        record is on the person themselves (a step with on_json []) rather than on a relative}."""
        out = {}
        for sid, rk, lkind, lval, on in self.q("SELECT id, row_key, locator_kind, locator_value, on_json FROM search_plan WHERE person_id=? AND status='done'", pid):
            held = (bool(self.q("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json IS NOT NULL AND artifacts_json<>'[]'", sid))
                    or (lkind == "apid" and bool(self.held_for(lval, pid))) or bool(lkind and lval and self.q("SELECT 1 FROM artifact WHERE locator_kind=? AND locator_value=?", lkind, lval)))
            if held: out[rk] = out.get(rk, False) or (on or "[]") == "[]"
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

