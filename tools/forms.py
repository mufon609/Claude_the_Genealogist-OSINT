"""The record forms (data/record-forms.csv, docs/DATA-ARCHITECTURE.md §7 decision 21): one row for each shape a kind of record
took, the years and jurisdictions that share it on one row, each saying what the form states, the locators that place an
entry on it, which of them make one page, how a household is bounded and where its structure is documented
(data/DATA-SOURCES.md §5c). Read-only reference data, read once per process: the checklist's census rows and the footprint's
expectations of a relative's census read a census's structure here.

    form_for(year, jurisdiction="united states")   the form of that year, or None
    census_form(collection, year)                  the form a census record of that collection and year was made on
    settles(form)                                  what a household row of the form settles, in words
"""
import csv, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "record-forms.csv")
COLUMNS = ["id", "kind", "jurisdiction", "years", "lost", "names", "relationship", "birth", "parents_birthplace", "states",
           "locators", "page", "household", "source", "notes"]
LISTS = ("years", "states", "locators", "page", "household", "source")     # the columns that hold several values, separated by ;
NAMES = ("head", "every member")       # who the form names: the head alone, the rest counted, or every member of the household
# the locators that place an entry on a form, in the form's terms (data/DATA-SOURCES.md §5c): where the page is, the page, the
# entry's line and the numbers of its dwelling and family in order of visitation, and the image of the page
LOCATORS = ("state", "county", "minor_division", "ward", "block", "supervisor_district", "enumeration_district", "assembly_district",
            "election_district", "page", "sheet", "sheet_letter", "line", "dwelling", "family", "image")
# the locators a copy gives of its own, which no form prints: FamilySearch's household identifier and film, folder and image
# numbers, the 1950 census site's schedule id, a reading's line counted from the top of its image
COPY_LOCATORS = ("household_id", "digital_folder", "image_number", "film", "publication", "roll", "schedule_id", "image_line")
# how a household is bounded on a page: one line (a head-only form), a run of lines opened by the line that carries the family's
# number, a run opened by the head, carried over a page break; one schedule per family; or not bounded at all
HOUSEHOLD = ("one line", "family number", "opened by the head", "over a page break", "one schedule", "unbounded")

FORMS = None

def forms():
    """data/record-forms.csv as a list of rows in file order, each a dict of its columns, the several-valued ones as lists and
    the years as ints."""
    global FORMS
    if FORMS is None:
        with open(PATH, newline="", encoding="utf-8") as fh:
            FORMS = [read_row(r) for r in csv.DictReader(fh)]
    return FORMS

def read_row(r):
    """One row of the file with its several-valued columns split on ; and its years as ints."""
    out = {k: (v or "").strip() for k, v in r.items()}
    for k in LISTS: out[k] = [x.strip() for x in out[k].split(";") if x.strip()]
    out["years"] = [int(y) for y in out["years"] if y.isdigit()]
    return out

def form_for(year, jurisdiction="united states", kind="census household"):
    """The form a record of that kind, jurisdiction and year was made on, or None when the file has none."""
    if not year: return None
    return next((f for f in forms() if f["kind"] == kind and f["jurisdiction"] == jurisdiction and int(year) in f["years"]), None)

def census_form(collection, year):
    """The form of a census record by its collection's own name and the record's year: a state census (the collection says
    State Census and names a jurisdiction the file has a form of) on that state's form, any other census on the federal
    schedule of the year. None when the file has no form of that year."""
    coll = (collection or "").lower()
    if re.search(r"\bstate census\b", coll):
        for j in dict.fromkeys(f["jurisdiction"] for f in forms() if f["jurisdiction"] != "united states"):
            if re.search(r"\b" + re.escape(j) + r"\b", coll): return form_for(year, j)
        return None
    return form_for(year)

def settles(form):
    """What a household row of the form settles, in words: the head alone counted, or every member with what the form states
    of each (the relationship to the head where it has that column)."""
    if form["names"] == "head": return "head of household only; counted, not named"
    return "everyone in the house: ages, birthplaces" + (", relationships" if form["relationship"] else "")
