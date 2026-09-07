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
    """Whether two surname keys are one name: written the same, or a spelling variant (the same Soundex code and at most two
    edits apart, so Ahearn and Ahern, Brant and Brandt, Kriebel and Krebel; not Brant and Grant). Returns "" when they differ,
    "agrees" when written the same, "variant" for a spelling variant."""
    if not a or not b: return ""
    if a == b: return "agrees"
    if len(a) >= 4 and len(b) >= 4 and soundex(a) == soundex(b) and edits(a, b) <= 2: return "variant"
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

def holder_search(h, fields):
    """The holder's own search URL from a fetch step's fields. FamilySearch: the collection search as the site itself builds it
    (f.collectionId, q.givenName, q.residenceDate.from/to and q.residencePlace from the citation's year and census place, q.surname).
    The National Archives 1950 site: its name search. None when the fields carry no name."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    given, surname, _ = split_name(v("name"))
    if not (given or surname): return None
    if h["HolderKind"] == "fs_collection":
        q = [("f.collectionId", h["HolderKey"]), ("q.givenName", given or "")]
        if v("year") and v("census place"): q += [("q.residenceDate.from", v("year")), ("q.residenceDate.to", v("year")), ("q.residencePlace", v("census place"))]
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

def place_verdict(record, tree):
    """agrees when the tree's place (its last two named parts below the country, e.g. town and county) is found in the record's
    place text, or the record's first part in the tree's; the tree's own resolved chain reads 'Town < County < State < Country'
    and the country's spellings are one. absent when either side has none."""
    if not record or not tree: return "absent"
    norm = lambda s: re.sub(r"\b(county|co\.?|township|twp\.?|magisterial district \d+|district \d+)\b", " ", COUNTRY.sub("usa", s.lower()))   # a jurisdiction word is not a place part
    tparts = [p.strip() for p in re.split(r"<|,", norm(tree)) if p.strip()]; rlow = key(norm(record))
    below = [p for p in tparts if p != "usa"]
    if not below: return "absent"                                 # a tree place that names only the country says nothing to compare
    if all(key(p) in rlow for p in below[-2:]): return "agrees"
    rparts = [p.strip() for p in norm(record).split(",") if p.strip()]
    if rparts and key(rparts[0]) in key(norm(tree)): return "agrees"
    return "disagrees"


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
        self.sources = {r[0]: {"name": r[1], "access": r[2] or "", "status": r[3] or "", "cost": r[4] or "", "connector": r[5] or ""}
                        for r in self.q("SELECT id, name, access, status, cost, connector FROM source")}
        self.holders = holders()
        self._groups = self._held = self._holdings = None
    def disagreements(self, pid):
        """Where an accepted record says something else than the tree's event: for each event of the person, every Accepted
        assertion whose persona fact disagrees with the event's own date (compared as dates) or place, as one line naming both
        values and the record. The tree's value is never changed by a record; the difference is a conflict question."""
        out = []
        for e in self.q("""SELECT e.id, e.event_type, e.date_text, e.date_start, e.date_qualifier, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id
                           WHERE ep.person_id=? ORDER BY e.event_type, e.date_start""", pid):
            tree_place = self.place(e[0], e[5])["text"] if e[5] else None
            for f in self.q("""SELECT pf.date_text, pf.date_start, pf.date_qualifier, ps.raw, coalesce(c.name, ar.original_filename, substr(ar.sha256,1,12)), ar.locator_value
                               FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                               JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN collection c ON c.id=ar.collection_id
                               WHERE a.subject_kind='event' AND a.subject_id=? AND a.status='accepted'""", e[0]):
                dv, _ = date_verdict({"start": f[1], "text": f[0], "qualifier": f[2]}, {"start": e[3], "text": e[2], "qualifier": e[4]})
                pv = place_verdict(f[3], tree_place)
                rec = f[4] + (f" ({f[5]})" if f[5] else "")
                if dv == "disagrees": out.append(f"{e[1].lower()} date: the tree says {e[2]}, {rec} says {f[0]}")
                if pv == "disagrees": out.append(f"{e[1].lower()} place: the tree says {tree_place}, {rec} says {f[3]}")
        return out
    def find_person(self, key):
        """A person by id, by the last six characters of the id in brackets or alone ("Noi Davidson [MEXW2C]", "MEXW2C"), by exact
        display name, or by a substring of the name. Several matches stop the tool and list them with their six characters, so a
        decision never lands on whichever sorts first."""
        m = re.search(r"\[([A-Z0-9]{6})\]\s*$", key or "") or re.fullmatch(r"[A-Z0-9]{6}", (key or "").strip())
        if m: r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND id LIKE ?", self.tree_id, "%" + (m.group(1) if m.groups() else m.group(0)))
        else:
            r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND (id=? OR display_name=?) ORDER BY display_name", self.tree_id, key, key)
            if not r: r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND display_name LIKE ? ORDER BY display_name LIMIT 8", self.tree_id, f"%{key}%")
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
        if place_id:
            chain, pid, region = [], place_id, {"country": None, "state": None}
            while pid:
                r = self.q("SELECT name, place_type, parent_id FROM place WHERE id=?", pid)[0]; chain.append(r[0])
                if r[1] == "country": region["country"] = r[0].lower()
                if r[1] == "state": region["state"] = r[0].lower()
                pid = r[2]
            return {"text": " < ".join(chain), "resolved": True, **region}
        raw = self.q("""SELECT ps.raw FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN place_string ps ON ps.id=pf.place_string_id
                        WHERE a.subject_kind='event' AND a.subject_id=? LIMIT 1""", eid)
        if not raw: return None
        text = raw[0][0]; low = " " + text.lower().replace(",", " ") + " "
        toks = [t.strip().lower() for t in text.split(",") if t.strip()]
        st = next((t for t in toks if t in US_STATES), None) or next((n for n in US_STATES if f" {n} " in low), None)
        if st or any(f" {n} " in low for n in US_NAMES): country = "united states"
        else: country = next((c for c in ("ireland", "germany", "netherlands", "poland", "japan", "england", "allemagne", "silesia", "schlesien") if f" {c} " in low), None)
        country = {"allemagne": "germany", "silesia": "poland", "schlesien": "poland", "england": "united kingdom"}.get(country, country)
        return {"text": text, "resolved": False, "country": country, "state": st}
    KEY_FACTS = ("name", "sex", "birth", "death", "parents", "spouses", "children")
    def key_fact_basis(self, pid, ev=None):
        """basis per key fact: accepted | claim | rejected | None (no claim)."""
        ev = self.events(pid) if ev is None else ev
        out = {"name": self.basis("person", pid), "sex": self.basis("person", pid)}
        for f in ("birth", "death"):
            e = next((e for e in ev if e["type"] == f.title()), None); out[f] = e["basis"] if e else None
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
    def citations(self, kind, sid, person_id=None):
        """[(collection name, apid, held artifact sha or None, collection id)] for a subject; held for the person given, when
        one is (a page holds a citation for the people it names), else for anyone."""
        out = []
        for cname, notes, sha, tier, cid in self.q(f"""SELECT COALESCE(c.name, ac.name), a.notes, a.artifact_sha256, {tier_sql()}, COALESCE(c.id, ac.id) FROM assertion a
                LEFT JOIN collection c ON json_valid(a.notes) AND c.id=json_extract(a.notes,'$.collection_id')
                LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256 LEFT JOIN source s ON s.id=ar.source_id
                LEFT JOIN collection ac ON ac.id=ar.collection_id
                WHERE a.subject_kind=? AND a.subject_id=? AND a.status<>'rejected'""", kind, sid):
            apid = json.loads(notes).get("apid") if notes and notes.startswith("{") else None
            held = sha if sha and (tier or "")[:2] in ("T1", "T2", "T3") else (self.held_for(apid, person_id) if person_id else self.held_apids().get(apid))   # the record a match attached, or the archived page the citation names; the T4 tree export is not a held record
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
    def person_citations(self, pid):
        """All citations attached to a person: on the person row and on every event of theirs."""
        cits = self.citations("person", pid, pid)
        for eid, in self.q("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=?", pid):
            cits += self.citations("event", eid, pid)
        return cits

