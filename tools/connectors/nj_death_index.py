"""Reclaim The Records' New Jersey death index, 2006-2017, on the Internet Archive (collection njdeathindex): free, no key,
public domain mark, one flat CSV, columns FNAME, LNAME, MIDDLE_NAME, STATE_FILE_NUMBER, BIRTH_YEAR, BIRTH_MONTH, BIRTH_DAY,
BIRTH_CITY, BIRTH_STATE, BIRTH_COUNTRY, DEATH_YEAR, DEATH_MONTH, DEATH_DAY, DEATH_STATE (verified 13 Sep 2026,
data/DATA-SOURCES.md §5, data/holders.csv dbid 61260). The rows run by state file number, not by name, and the Archive's own
search does not reach inside a flat data file the way it reaches inside an OCR'd book (ia.py), so there is no way to ask the
Archive for one surname's rows; the file is fetched whole once (archived under C09 with its own URL as locator) and read here.

For a step's own surname, rows() picks out the file's own rows under it (as written; the file carries no Soundex or spelling
variants of its own) and hits() turns them into a derivative artifact of their own: a CSV of just those rows, with the header
line, archived under C09 too, derived_from the whole file's sha256 (run_step.py stamps it onto the request as archived_sha
once the whole file is kept) and locator the file's own URL with the surname as a fragment. Two steps on the same surname
derive the same bytes from the same parent and land on the same artifact row (archive_object dedupes by content); a step on
another surname gets its own, so extracting one surname's derivative never supersedes another's (tools/extract.py's
supersession is scoped to one artifact_sha256): the shape the backlog's own critique of one shared, whole-file, re-extracted
artifact ruled out, since that would reject an earlier surname's still-undecided cards as superseded on every later surname's
extraction.
"""
import csv, io, urllib.parse
from connectors import value
from connectors.ia import name_parts

SOURCE = "C09"
COLLECTION = "New Jersey, U.S., Death Index, 1848-1878, 1901-2017"
ROWS = ("death record",)                                          # C09 is on the birth and marriage rows too; this file answers only the death row
CSV_URL = "https://archive.org/download/newjerseydeathindex_2006-2017_data_csv/Reclaim_The_Records_-_New_Jersey_Death_Index_-_2006-2017.csv"
RATE = {"text": 6}                                                # a 69 MB file; a person's pace asks it no more often than this
FIELDS = ["FNAME", "LNAME", "MIDDLE_NAME", "STATE_FILE_NUMBER", "BIRTH_YEAR", "BIRTH_MONTH", "BIRTH_DAY", "BIRTH_CITY", "BIRTH_STATE", "BIRTH_COUNTRY", "DEATH_YEAR", "DEATH_MONTH", "DEATH_DAY", "DEATH_STATE"]

def wants(fields):
    """A citation of the death index itself (a marriage or birth citation at C09 asks nothing here), then a surname."""
    coll = (value(fields, "collection") or "").lower()
    if coll and "death" not in coll: return "a citation of the death index: this file is the death index alone"
    return None if name_parts(fields)[1] else "a surname"

def requests(fields):
    """The whole file, once, when the step's fields name a surname (the citation's own name, or a search step's). C09
    also holds the state's marriage and birth indexes (data/holders.csv), so a citation naming one of those (its own
    "collection" field says which) asks nothing here: this file is the death index alone."""
    coll = (value(fields, "collection") or "").lower()
    if coll and "death" not in coll: return []
    given, surname = name_parts(fields)
    if not surname: return []
    return [{"url": CSV_URL, "kind": "text", "record": False, "surname": surname, "given": given}]

def total(body):
    return None                                                   # the file names no count of its own; rows() and the note say what was found

def rows(body, surname):
    """The file's own rows under this surname, as written (case-insensitive; the file gives no spelling variants of its own,
    so a step's alias variants are asked as separate requests, each its own derivative)."""
    key = (surname or "").strip().lower()
    if not key: return []
    text = body.decode("utf-8", errors="replace")
    return [r for r in csv.DictReader(io.StringIO(text)) if (r.get("LNAME") or "").strip().lower() == key]

def derivative(matched):
    """The matched rows as CSV text with the header line, the shape a re-extraction of the same rows reproduces byte for byte."""
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore"); w.writeheader()
    for r in matched: w.writerow({k: r.get(k, "") for k in FIELDS})
    return buf.getvalue().encode("utf-8")

def hits(url, body, request):
    """One hit, this surname's own rows out of the whole file, its own derivative artifact to keep: none when the file
    carries no row under this surname."""
    surname = request.get("surname")
    matched = rows(body, surname)
    if not matched: return []
    frag = urllib.parse.quote(surname)
    return [{"label": f"{len(matched)} row(s) under {surname} in the New Jersey death index", "locator": {"kind": "url", "value": f"{url}#surname={frag}"},
             "notes": {"surname": surname, "given": request.get("given"), "rows": len(matched)},
             "fetch": [{"url": f"{url}#surname={frag}", "kind": "text", "record": True, "bytes": derivative(matched), "derived_from": request.get("archived_sha")}]}]
