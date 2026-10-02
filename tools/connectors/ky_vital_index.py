"""Reclaim The Records' Kentucky death index and birth index, 1911-1989, on the Internet Archive: free, no key, Public Domain
Mark, the state vital statistics program's own printouts, each page headed KENTUCKY STATE DEPARTMENT FOR HUMAN RESOURCES
(data/DATA-SOURCES.md §4, registry row C06). Two items, one plain-text file per year, its name read off the Archive's metadata
API (archive.org/metadata/<item>):
  reclaim-the-records-kentucky-death-index-01911-1989  Reclaim_The_Records_-_Kentucky_Death_Index_-_0<year>.TXT, 3-5 MB a year
  reclaim-the-records-kentucky-birth-index-01911-1989  Reclaim_The_Records_-_Kentucky_Birth_Index_-_0<year>-BRCI<yy>.TXT, 7-11 MB
Each file is the printout as the state's program wrote it: every line opens with one carriage-control byte (SUB for a line,
"i" at a page's end, VT and SOH and DC1 around the page headings), a HIPAA notice and a heading on every page, then fixed-width
rows sorted by surname and given name. A death row: surname, given name, middle initial, age (U/1 under a year), the county of
death as a five-letter code (SMPSN), the county of residence written out (SIMPSON, or a state or town for one who lived
elsewhere), the date of death, the certificate's volume, its number and its filing year. A birth row: surname, first and
middle names, the date of birth, the birth number (volume-number-year), the county of birth by the same code, the mother's
maiden name (given, middle initial, surname), the sex, the date filed. The later death items are not read here: 1990-2004
and 2011-2022 are scanned pages, and 2005-2010 text files of a shorter row with no age, residence or certificate.

The files are sorted, but the runner sends no byte range, so a year's file is asked whole, once per step and year, and kept
as it came (record False, archived under C06 with its own URL as locator); rows() reads it here. For each surname the step
asks under, hits() keeps the year's rows under it (and, when the step names a given name, those whose given name begins with
its first letter: an abbreviation, a truncation or an initial is kept, JNO for John) as a derivative artifact of their own,
the lines exactly as the file has them, derived_from the year file and located at the file's URL with the surname and given
name as its fragment; one surname's rows never supersede another's (as in nj_death_index.py).

Which index and which years a step asks:
  a fetch step (its fields carry the citation's "collection"): a citation of Kentucky's death index or birth index alone,
    in the year the citation's own details name ("year", or a date field); the plan's citations of the file name no year,
    and the index is one file per year, so such a step is logged none here, the note saying the year is wanted.
  a search step on the death or birth record row (ROWS) for a Kentucky event: the step's fields do not name the row, so a
    year equal to the step's birth year is the birth row's and any other year the death row's. The year alone when the
    tree's year is accepted, else the year either side too. The surname, its spellings the alias table holds
    (surname_variants), and on the death row the other surnames the person's names carry (a married woman dies under her
    husband's).
"""
import re, urllib.parse
from connectors import value
from connectors.ia import name_parts

SOURCE = "C06"
COLLECTION = "Kentucky, U.S., Death and Birth Indexes, 1911-1989"
ROWS = ("death record", "birth record")                             # C06 is on the marriage row too; these files hold deaths and births alone
RATE = {"text": 6}                                                # a whole year's file a request; a person's pace asks it no more often than this
YEARS = (1911, 1989)
DEATH_URL = "https://archive.org/download/reclaim-the-records-kentucky-death-index-01911-1989/Reclaim_The_Records_-_Kentucky_Death_Index_-_0{year}.TXT"
BIRTH_URL = "https://archive.org/download/reclaim-the-records-kentucky-birth-index-01911-1989/Reclaim_The_Records_-_Kentucky_Birth_Index_-_0{year}-BRCI{yy}.TXT"
COUNTIES = {                                                      # the files' five-letter county codes; each read off the 1946 death file, where every code stands beside the county of residence it most often names
    "ADAIR": "Adair", "ALLEN": "Allen", "ANDSN": "Anderson", "BALLD": "Ballard", "BARRN": "Barren", "BATH": "Bath", "BELL": "Bell", "BOONE": "Boone",
    "BOYD": "Boyd", "BOYLE": "Boyle", "BRCKN": "Bracken", "BRECK": "Breckinridge", "BRTHT": "Breathitt", "BULLT": "Bullitt", "BURBN": "Bourbon",
    "BUTLR": "Butler", "CALWY": "Calloway", "CARRL": "Carroll", "CARTR": "Carter", "CASEY": "Casey", "CLARK": "Clark", "CLAY": "Clay", "CLDWL": "Caldwell",
    "CLNTN": "Clinton", "CMBLD": "Cumberland", "CMPBL": "Campbell", "CRLIL": "Carlisle", "CRSTN": "Christian", "CRTDN": "Crittenden", "DAVES": "Daviess",
    "EDMSN": "Edmonson", "ELIOT": "Elliott", "ESTIL": "Estill", "FLMNG": "Fleming", "FLOYD": "Floyd", "FRNKL": "Franklin", "FULTN": "Fulton",
    "FYETE": "Fayette", "GARRD": "Garrard", "GLLTN": "Gallatin", "GRANT": "Grant", "GREEN": "Green", "GRNUP": "Greenup", "GRVES": "Graves",
    "GRYSN": "Grayson", "HANCK": "Hancock", "HARDN": "Hardin", "HARLN": "Harlan", "HARSN": "Harrison", "HART": "Hart", "HCKMN": "Hickman", "HENRY": "Henry",
    "HNDSN": "Henderson", "HPKNS": "Hopkins", "JCKSN": "Jackson", "JEFFN": "Jefferson", "JESMN": "Jessamine", "JHNSN": "Johnson", "KENTN": "Kenton",
    "KNOTT": "Knott", "KNOX": "Knox", "LARUE": "LaRue", "LAURL": "Laurel", "LEE": "Lee", "LESLI": "Leslie", "LEWIS": "Lewis", "LNCLN": "Lincoln",
    "LOGAN": "Logan", "LRNCE": "Lawrence", "LTCHR": "Letcher", "LVGST": "Livingston", "LYON": "Lyon", "MADSN": "Madison", "MAGFN": "Magoffin",
    "MARON": "Marion", "MARTN": "Martin", "MASON": "Mason", "MCCRK": "McCracken", "MCCRY": "McCreary", "MCLEN": "McLean", "MEADE": "Meade",
    "MENFE": "Menifee", "MERCR": "Mercer", "MLNBG": "Muhlenberg", "MNTGY": "Montgomery", "MONRO": "Monroe", "MORGN": "Morgan", "MRSHL": "Marshall",
    "MTCLF": "Metcalfe", "NCHLS": "Nicholas", "NELSN": "Nelson", "OHIO": "Ohio", "OLDHM": "Oldham", "OWEN": "Owen", "OWSLY": "Owsley", "PERRY": "Perry",
    "PIKE": "Pike", "PLSKI": "Pulaski", "PNLTN": "Pendleton", "POWEL": "Powell", "RBTSN": "Robertson", "RCKSL": "Rockcastle", "ROWAN": "Rowan",
    "RUSEL": "Russell", "SCOTT": "Scott", "SHLBY": "Shelby", "SMPSN": "Simpson", "SPNCR": "Spencer", "TAYLR": "Taylor", "TODD": "Todd", "TRIGG": "Trigg",
    "TRMBL": "Trimble", "UNION": "Union", "WARRN": "Warren", "WAYNE": "Wayne", "WBSTR": "Webster", "WDFRD": "Woodford", "WHTLY": "Whitley",
    "WOLFE": "Wolfe", "WSHGN": "Washington"}
DEATH_ROW = re.compile(r" {3}(?P<surname>\S.{15})(?P<given>.{11})(?P<middle>.{7})(?P<age>.{4}) {7}(?P<place>.{10})(?P<residence>.{14})"
                       r"(?P<date>\d\d/\d\d/\d{4}) (?P<vol>.{3}) {2}(?P<number>.{5}) ?/(?P<filed>\d{4})")
BIRTH_ROW = re.compile(r"[\x00 ](?P<surname>[A-Z].{18})(?P<given>.{13})(?P<middle>.{14})(?P<date>\d\d-\d\d-\d{4}) {2}(?P<number>\d{3}-\d{5}-\d{4}) "
                       r"(?P<county>.{6}) (?P<mother_given>.{11})(?P<mother_middle>.) (?P<mother_surname>.{17})(?P<rest>.*)")
SUFFIX = {"JR", "SR", "II", "III", "IV"}

def county(code):
    """The county a five-letter code names, as "<County> County, Kentucky"; None for a blank or unknown code."""
    name = COUNTIES.get((code or "").strip().upper())
    return f"{name} County, Kentucky" if name else None

def kentucky_county(written):
    """The Kentucky county a written-out county name is, by its letters ("LARUE" is LaRue), or None (a state, a town, a slip)."""
    k = re.sub(r"[^A-Z]", "", (written or "").upper())
    return next((n for n in COUNTIES.values() if re.sub(r"[^A-Z]", "", n.upper()) == k), None) if k else None

def surname_key(s):
    """A surname as the index is searched by: its letters, a suffix the index writes after it (DAVIDSON JR) set aside."""
    words = (s or "").upper().split()
    if len(words) > 1 and words[-1].strip(".") in SUFFIX: words = words[:-1]
    return re.sub(r"[^A-Z]", "", " ".join(words))

def rows(body):
    """Every row of a year's file (or of a derivative cut from one), in file order: {"index": "death" | "birth", the columns
    stripped, "raw": the line's own bytes, carriage control included}. Headings, notices and blank lines are not rows."""
    out = []
    for raw in (body or b"").split(b"\n"):
        raw = raw.rstrip(b"\r")
        text = raw[1:].decode("latin-1")                          # the first byte is the line's carriage control
        m = DEATH_ROW.fullmatch(text)
        if m: out.append({"index": "death", **{k: v.strip() for k, v in m.groupdict().items()}, "raw": raw}); continue
        m = BIRTH_ROW.fullmatch(text)
        if m:
            d = {k: v.strip() for k, v in m.groupdict().items() if k != "rest"}
            rest = m.group("rest")
            out.append({"index": "birth", **d, "sex": rest[:8].strip(), "filed": rest[8:].strip(), "raw": raw})
    return out

def lines(body):
    """How many lines a file holds that are not blank once their carriage control is set aside."""
    return sum(1 for raw in (body or b"").split(b"\n") if raw.rstrip(b"\r")[1:].strip(b" \x00"))

def under(body, index, surname, given=None):
    """The year's rows of this index under the surname (a suffix set aside, any case), and when a given name is named those
    whose given name begins with its first letter."""
    key, first = surname_key(surname), ((given or "").strip()[:1]).upper()
    return [r for r in rows(body) if r["index"] == index and surname_key(r["surname"]) == key and (not first or r["given"][:1].upper() == first)]

def derivative(matched):
    """The matched lines exactly as the file has them, each ending as the file ends a line: what a re-reading of the same rows
    reproduces byte for byte."""
    return b"".join(r["raw"] + b"\r\n" for r in matched)

def year_of(v):
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", str(v or ""))
    return int(m.group(1)) if m else None

def index_of(fields):
    """("death" | "birth", None), or (None, what the connector wants): a citation names its index in its collection; a search
    step's year equal to its birth year is the birth row's, any other year the death row's."""
    coll = (value(fields, "collection") or "").lower()
    if coll:
        if "kentucky" in coll and "death index" in coll: return "death", None
        if "kentucky" in coll and "birth index" in coll: return "birth", None
        return None, "a citation of the Kentucky death or birth index: these files are those indexes alone"
    year, birth = year_of(value(fields, "year")), year_of(value(fields, "birth_year"))
    if not year: return None, "the year of the death or birth: the index is one file per year"
    return ("birth" if birth == year else "death"), None

def asked(fields):
    """(index, years, surnames, given) the step's fields ask, or (None, what the connector wants)."""
    fetch = bool(value(fields, "collection"))
    state = str(value(fields, "state") or "").strip().lower()
    if not fetch and state != "kentucky": return None, f"a Kentucky death or birth: the step's state is {state or 'not named'}"
    index, why = index_of(fields)
    if not index: return None, why
    given, surname = name_parts(fields)
    if not surname: return None, "a surname"
    if fetch:
        y = year_of(value(fields, "year")) or next((year_of(value(fields, k)) for k in ("date", "death date", "birth date", "event date") if year_of(value(fields, k))), None)
        if not y: return None, f"the year of the {index}: the citation names none, and the index is one file per year"
        years = [y]
    else:
        y = year_of(value(fields, "year")); basis = (fields.get("year") or {}).get("basis") if isinstance(fields.get("year"), dict) else None
        years = [y] if basis == "accepted" else [y - 1, y, y + 1]
    years = [y for y in years if YEARS[0] <= y <= YEARS[1]]
    if not years: return None, f"a year the index covers ({YEARS[0]}-{YEARS[1]})"
    names = [surname] + list(value(fields, "surname_variants") or [])
    if index == "death" and not fetch:                            # a married woman dies under her husband's surname: the other surnames her names carry
        from catalog import split_name
        names += [split_name(str(v))[1] for v in (value(fields, "variants") or [])]
    surnames = []
    for s in names:
        if s and surname_key(s) and surname_key(s) not in [surname_key(x) for x in surnames]: surnames.append(s)
    return (index, years, surnames, (given or "").split()[0] if given else None), None

def wants(fields):
    plan, why = asked(fields)
    return None if plan else why

def url_for(index, year):
    return DEATH_URL.format(year=year) if index == "death" else BIRTH_URL.format(year=year, yy=f"{year % 100:02d}")

def requests(fields):
    """One request a year: the year's whole file, not itself the record, carrying the surnames and the given name to keep."""
    plan, _ = asked(fields)
    if not plan: return []
    index, years, surnames, given = plan
    return [{"url": url_for(index, y), "kind": "text", "record": False, "index": index, "year": y, "surnames": surnames, "given": given} for y in years]

def total(body):
    return None                                                   # the file's own count is of everyone; the derivative's rows are the note

def hits(url, body, request):
    """One hit per surname with rows in the year's file, its rows a derivative artifact of their own; none when no surname has
    any."""
    index, year, given = request.get("index"), request.get("year"), request.get("given")
    out = []
    for s in request.get("surnames") or []:
        matched = under(body, index, s, given)
        if not matched: continue
        loc = url + "#" + urllib.parse.urlencode([("surname", s)] + ([("given", given)] if given else []), quote_via=urllib.parse.quote)
        out.append({"label": f"{len(matched)} row(s) under {s}{' ' + given[:1].upper() + '.' if given else ''} in the Kentucky {index} index for {year}", "locator": {"kind": "url", "value": loc},
                    "notes": {"index": index, "year": year, "surname": s, "given": given, "rows": len(matched)},
                    "fetch": [{"url": loc, "kind": "text", "record": True, "bytes": derivative(matched), "derived_from": request.get("archived_sha")}]})
    return out
