#!/usr/bin/env python3
"""Green in one command: every parser read against a saved real page.

usage: tools/check.py [--show] [--keep]

A scratch catalog under a temporary data root, never the owner's. Every page under tests/fixtures/ is archived there and
read by tools/extract.py as the attach would read it, and the personas, facts and relations it writes are checked against
what the page says (tests/fixtures/README.md says where each page came from). One line per fixture, ok or FAIL with every
reason; exit status 1 on any failure. --show prints what each extraction wrote, for writing a check; --keep leaves the
scratch directory in place and prints its path.
"""
import argparse, json, os, sqlite3, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
BY = "agent:check"

def scratch(keep):
    d = tempfile.mkdtemp(prefix="tree-check-")
    os.environ["DATA_ROOT"] = d                                  # before treelib is imported: every data path resolves under it
    db = os.path.join(d, "catalog", "tree.db"); os.makedirs(os.path.dirname(db))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "initdb.py"), "--db", db], capture_output=True, text=True)
    if r.returncode: sys.exit(f"initdb failed:\n{r.stdout}{r.stderr}")
    return d, db

def read(cx, eid):
    """What an extraction wrote: personas in sequence, each with its facts and the relations from it."""
    out = []
    for pid, seq, name, role, sex, region in cx.execute("SELECT id, sequence, name_text, role_in_record, sex, region_json FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,)):
        facts = [(t, v, d, p) for t, v, d, p in cx.execute("""SELECT f.fact_type, f.value_text, f.date_text, ps.raw FROM persona_fact f LEFT JOIN place_string ps ON ps.id=f.place_string_id
                                                              WHERE f.persona_id=? ORDER BY f.id""", (pid,))]
        rels = [(k, v, cx.execute("SELECT sequence FROM persona WHERE id=?", (o,)).fetchone()[0]) for k, v, o in cx.execute("SELECT kind, value_text, related_persona_id FROM persona_relation WHERE persona_id=?", (pid,))]
        out.append({"seq": seq, "name": name, "role": role or "", "sex": sex or "", "region": region or "", "facts": facts, "relations": rels})
    return out

def fact(p, ftype, **want):
    """The first fact of this type on a persona whose value, date or place is as wanted (a wanted place matches as a prefix)."""
    for t, v, d, place in p["facts"]:
        if t != ftype: continue
        if "value" in want and (v or "") != want["value"]: continue
        if "date" in want and (d or "") != want["date"]: continue
        if "place" in want and not (place or "").startswith(want["place"]): continue
        return (t, v, d, place)
    return None

def rel(p, kind, to_seq, value=None):
    return any(k == kind and o == to_seq and (value is None or v == value) for k, v, o in p["relations"])

# ---------------------------------------------------------------- the checks: one per fixture, each returns the failures it found

def check_memorial(ps, fail):
    fail(len(ps) == 11, f"11 personas expected, {len(ps)} written")
    a = ps[0]; fail(a["name"] == "Abram C Brant" and a["role"] == "memorial", f"the memorial's subject: {a['name']} [{a['role']}]")
    fail(fact(a, "Birth", date="20 Sep 1880", place="Worcester, Montgomery County, Pennsylvania"), "birth 20 Sep 1880 at Worcester")
    fail(fact(a, "Death", date="10 Oct 1961", place="Pottstown, Montgomery County, Pennsylvania"), "death 10 Oct 1961 at Pottstown")
    fail(fact(a, "Burial", place="Methacton Mennonite Cemetery, Norristown"), "burial at Methacton Mennonite Cemetery")
    fail("78019650" in a["region"], "the memorial id 78019650 on the subject")
    kinds = {}
    for p in ps[1:]:
        for k, v, o in p["relations"]:
            if o == 1: kinds[k] = kinds.get(k, 0) + 1
    fail(kinds == {"parent": 2, "spouse": 1, "sibling": 6, "child": 1}, f"family: 2 parents, 1 spouse, 6 siblings, 1 child toward the subject; got {kinds}")
    child = next((p for p in ps if rel(p, "child", 1)), None)
    fail(child and child["name"] == "Helen Sara Brant Ahearn" and '"maiden":"Brant"' in child["region"] and "142698059" in child["region"], "the child is Helen Sara Brant Ahearn, her birth surname marked and her own memorial linked")
    parent = next((p for p in ps if p["name"] == "Abraham Brant"), None)
    fail(parent and fact(parent, "Birth", date="1852") and fact(parent, "Death", date="1898"), "a linked parent's years as the page lists them (Abraham Brant 1852-1898)")

def check_census_1940(ps, fail):
    fail([(p["name"], p["role"], p["sex"]) for p in ps] == [("Frederick Ahern", "son", "M"), ("Helen Ahern", "mother", "F"), ("Frederick Ahern", "father", "M"), ("Alicia Ahern", "sister", "F")],
         f"the household in the page's own role words; got {[(p['name'], p['role'], p['sex']) for p in ps]}")
    son, mother, father, sister = ps[0], ps[1], ps[2], ps[3]
    fail(fact(son, "Birth", date="CAL 1933", place="Pennsylvania"), "the principal's birth calculated from age 7 on the 1940 record: CAL 1933, Pennsylvania")
    fail(fact(mother, "Birth", date="CAL 1910") and fact(father, "Birth", date="CAL 1908") and fact(sister, "Birth", date="CAL 1935"), "each member's birth calculated from their age")
    fail(fact(son, "Residence", date="1935", place="Caln Township, Chester, Pennsylvania"), "Residence Date 1935 / Same House read as the record's own place, not a place called Same House")
    fail(fact(son, "Residence", date="1940", place="Caln Township, Chester, Pennsylvania"), "the record's own residence: 1940 at Caln Township")
    fail(not any((place or "") == "Same House" for p in ps for _, _, _, place in p["facts"]), "no fact carries Same House as a place")
    fail(rel(mother, "parent", 1, "Mother") and rel(father, "parent", 1, "Father") and rel(sister, "sibling", 1, "Sister"), "Mother, Father and Sister stated toward the principal")
    fail(rel(mother, "spouse", 3, "Parents"), "the couple relation between the household's mother and father")

def check_census_1900(ps, fail):
    fail([(p["name"], p["role"]) for p in ps] == [("John Davidson", "head"), ("Ellan E Davidson", "mother"), ("Lena H Davidson", "wife"), ("Willie R Davidson", "son"), ("Cassie E Davidson", "daughter")],
         f"the household as the page lists it; got {[(p['name'], p['role']) for p in ps]}")
    head = ps[0]
    fail(fact(head, "Birth", date="Apr 1875", place="Kentucky"), "the head's birth as the 1900 index gives it: Apr 1875, Kentucky")
    fail(fact(head, "Residence", date="1900", place="Magisterial District 2 Adairville, Logan, Kentucky"), "the residence 1900 as written")
    fail(fact(ps[1], "Birth", date="CAL 1835", place="Tennessee"), "a member's birth calculated from her age: CAL 1835")
    fail(rel(ps[1], "parent", 1, "Mother") and rel(ps[2], "spouse", 1, "Wife") and rel(ps[3], "child", 1, "Son") and rel(ps[4], "child", 1, "Daughter"), "Mother, Wife, Son, Daughter toward the head")

def check_census_1950_fs(ps, fail):
    fail([(p["name"], p["role"]) for p in ps] == [("Christian Hahnle", "head"), ("Adeline Hahnle", "")], f"the 1950 page's two people; got {[(p['name'], p['role']) for p in ps]}")
    fail(fact(ps[0], "Birth", date="CAL 1899", place="New York"), "the head's birth calculated: CAL 1899, New York")
    fail(fact(ps[0], "Residence", date="11 April 1950", place="Lindenhurst, Babylon, Suffolk, New York"), "the residence on the census day as written")
    fail(rel(ps[1], "other", 1), "a member with no role word relates as other")

def check_schedule(ps, fail):
    fail(len(ps) == 30, f"30 rows of the schedule, {len(ps)} written")
    fail(ps[0]["name"] == "Dauck Thomas E." and ps[0]["role"] == "listed", f"the first row as transcribed; got {ps[0]['name']} [{ps[0]['role']}]")
    fail(all(fact(p, "Residence", date="1950", place="Nassau, New York, United States") for p in ps), "every row a Residence 1950 in Nassau, New York")
    fail(all(any(t == "Unknown" and (v or "").startswith("Enumeration District: 30-392") for t, v, _, _ in p["facts"]) for p in ps), "the enumeration district on every row")
    fail("3947385" in ps[0]["region"], "the schedule id on the row")

def check_aad_search(ps, fail):
    fail(len(ps) == 10, f"10 result rows, {len(ps)} written")
    fail(ps[0]["name"] == "Robert C Davidson", f"the first row's name; got {ps[0]['name']}")
    fail(fact(ps[0], "Birth", date="1915"), "the row's year of birth 1915")
    fail(fact(ps[0], "Residence", date="1945", place="Blair, Pennsylvania"), "the row's residence county and state, dated by the enlistment year")
    fail("247275" in ps[0]["region"], "the row's own record id on the persona")

def check_aad_record(ps, fail):
    fail(len(ps) == 1 and ps[0]["name"] == "Robert C Davidson", f"one persona, the enlistee as the file writes him; got {[p['name'] for p in ps]}")
    p = ps[0]
    fail(fact(p, "Birth", date="1915") and fact(p, "Residence", place="Blair, Pennsylvania"), "birth year and residence at enlistment")
    fail(fact(p, "Military Service", date="21 SEP 1945", place="Charleston Port Of Embarkation"), "the enlistment as a Military Service event on its day at its place")
    fail(fact(p, "Education", value="2 years of high school") and fact(p, "Marital Status", value="Married"), "education and marital status as written")

def check_fg_search(ps, fail):
    fail(len(ps) == 1 and ps[0]["name"] == "Robert Edgar Davidson", f"one result row; got {[p['name'] for p in ps]}")
    p = ps[0]
    fail("92726257" in p["region"], "the row's memorial id as its identity")
    fail(fact(p, "Birth", date="19 Feb 1915") and fact(p, "Death", date="5 Apr 2004"), "the row's dates")
    fail(fact(p, "Burial", value="Plot: sect S", place="Shelby-Oakland Cemetery, Shelby, Richland County, Ohio"), "the row's cemetery and plot as the burial")

def check_wikitree(ps, fail):
    fail(ps and ps[0]["name"].startswith("David") and "Hubner" in ps[0]["name"], f"the profile's subject David Hubner first; got {[p['name'] for p in ps[:1]]}")
    p = ps[0]
    fail(fact(p, "Birth", date="27 AUG 1696", place="Harpersdorf"), "birth 27 AUG 1696 at Harpersdorf, as the profile writes it")
    fail(fact(p, "Death", date="27 DEC 1784", place="Worcester Township, Montgomery"), "death 27 DEC 1784 at Worcester Township")
    fail(fact(p, "Name", value="David Hubner") and fact(p, "Name", value="David Heebner"), "the name at birth and the current name both as Name facts")
    spouse = next((q for q in ps if rel(q, "spouse", 1)), None)
    fail(spouse and spouse["name"] == "Maria Kriebel" and "Kriebel-138" in spouse["region"], "the spouse Maria Kriebel with her own profile id")
    fail(sum(1 for q in ps if rel(q, "child", 1)) == 3, "three children on the profile")
    fail("Hubner-223" in p["region"], "the profile id as the persona's identity")
    fail(len(ps) > 1 and any(r for q in ps[1:] for r in q["relations"]), "the relatives on the profile as personas with their relations")

def check_locgov(ps, fail):
    fail(len(ps) >= 1 and all("davidson" in p["name"].lower() for p in ps), f"a persona per place the searched surname stands in the page's OCR text; got {[p['name'] for p in ps][:6]}")
    fail(all(fact(p, "Death", date="Bef 1918-05-10") for p in ps), "on an obituary step, a Death before the page's date")
    fail(all('"segment":"/service/ndnp' in p["region"] for p in ps), "the page's segment as the persona's region")

def check_ia_inside(ps, fail):
    fail(len(ps) >= 1, f"a persona per place the searched surname stands in the chosen pages' text; got {len(ps)}")
    fail(all("heebner" in p["name"].lower() for p in ps), f"every persona named around Heebner; got {[p['name'] for p in ps][:6]}")
    fail(all(fact(p, "Residence", date="1879-01-01") for p in ps), "a Residence on the book's date for a compiled-genealogy hit")
    fail(all('"segment":"genealogicalreco01krie"' in p["region"] for p in ps), "the item as the persona's segment")

# file, mime, source id, locator kind, locator value, the extractor expected, the check, and for a connector's response what the
# run's log knew that its manifest does not; a fixture with a .manifest.json sidecar takes mime, source, locator and notes from
# it, so the reading is the one made on arrival
FIXTURE_SET = [
    ("wikitree-profile-Hubner-223.json", None, None, None, None, "wikitree-profile", check_wikitree),
    ("ia-search-inside-genealogicalreco01krie-heebner.json", None, None, None, None, "ia-search-inside", check_ia_inside),
    ("locgov-ocr-sn89058321-1918-05-10-p2.json", None, None, None, None, "loc-gov-ocr", check_locgov, {"step_type": "obituary"}),   # archived before the runner noted the step's kind: the run's log said obituary
    ("findagrave-memorial-78019650.html", "text/html", "E01", "memorial_id", "78019650", "findagrave-memorial", check_memorial),
    ("familysearch-census-1940-KQX1-VT9.html", "text/html", "D03", "apid", "1,2442::26440834", "familysearch-record", check_census_1940),
    ("familysearch-census-1900-M9HX-SWP.html", "text/html", "D03", "apid", "1,7602::5537739", "familysearch-record", check_census_1900),
    ("familysearch-census-1950-6X5P-KT7T.html", "text/html", "D03", "file", "familysearch-census-1950-6X5P-KT7T.html", "familysearch-record", check_census_1950_fs),
    ("nara-1950-schedule-3947385.json", "application/json", "D05", "url", "https://1950census.archives.gov/api/search?scheduleId=3947385", "nara-1950-schedule", check_schedule),
    ("aad-search-davidson-robert-15.html", "text/html", "F01", "url", "https://aad.archives.gov/aad/display-partial-records.jsp?txt_24995=DAVIDSON%20ROBERT&txt_24983=15", "aad-search", check_aad_search),
    ("aad-enlistment-247275.html", "text/html", "F01", "url", "https://aad.archives.gov/aad/record-detail.jsp?dt=893&cat=WR26&rid=247275", "aad-enlistment", check_aad_record),
    ("findagrave-search-davidson-robert-1915-2004.html", "text/html", "E01", "url", "https://www.findagrave.com/memorial/search?firstname=Robert&lastname=Davidson&birthyear=1915&deathyear=2004", "findagrave-search", check_fg_search),
]

def compiles():
    """Every tool and the screen's server compile; the first thing green means."""
    import py_compile
    bad = []
    for f in sorted(os.listdir(os.path.join(ROOT, "tools"))) + ["connectors/" + f for f in sorted(os.listdir(os.path.join(ROOT, "tools", "connectors")))] + ["../app/person/server.py"]:
        if not f.endswith(".py"): continue
        try: py_compile.compile(os.path.join(ROOT, "tools", f), doraise=True)
        except py_compile.PyCompileError as e: bad.append(f"{f}: {e.msg.splitlines()[0]}")
    return bad

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--show", action="store_true"); ap.add_argument("--keep", action="store_true"); a = ap.parse_args()
    bad_files = compiles()
    print("ok   every tool compiles" if not bad_files else "FAIL compile: " + "; ".join(bad_files))
    d, db = scratch(a.keep)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from treelib import archive_object
    from extract import extract
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON")
    bad = len(bad_files)
    for name, mime, source, lkind, lvalue, extractor, check, *extra in FIXTURE_SET:
        path = os.path.join(FIXTURES, name)
        if not os.path.isfile(path): print(f"FAIL {name}: fixture missing"); bad += 1; continue
        notes = None
        if os.path.isfile(path[:-5] + ".manifest.json"):                       # a connector's response: its manifest is the provenance
            with open(path[:-5] + ".manifest.json", encoding="utf-8") as fh: man = json.load(fh)
            mime, source, lkind, lvalue, notes = man["mime"], man["source_id"], man["locator"]["kind"], man["locator"]["value"], man.get("notes") or None
            if extra and notes: notes = json.dumps({**json.loads(notes), **extra[0]})
        src = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id=?", (source,)).fetchone() or (None, None, None)
        cost = next((c for c in ("free", "paid", "member") if (src[2] or "").strip().lower().startswith(c)), "unknown")   # the registry's cost text, as the attach reads it
        with open(path, "rb") as fh: data = fh.read()
        cx.execute("BEGIN")
        sha, _ = archive_object(cx, data, mime=mime, source_id=source, collection_id=None, locator_kind=lkind, locator_value=lvalue, retrieved_by=BY,
                                terms=src[1], cost=cost, trust_tier=src[0], original_filename=name, notes=notes)
        eid, n = extract(cx, sha, BY); cx.commit()
        fails = []
        fail = lambda ok, why: None if ok else fails.append(why)
        ext = cx.execute("SELECT x.name, x.version, e.status FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (eid,)).fetchone()
        fail(ext[2] == "complete", f"extraction {ext[2]}: {n.get('failed', '')}")
        fail(ext[0] == extractor, f"read by {ext[0]}@{ext[1]}, expected {extractor}")
        ps = read(cx, eid) if ext[2] == "complete" else []
        if a.show:
            print(f"== {name}: {ext[0]}@{ext[1]} {ext[2]} {n}")
            for p in ps:
                print(f"  {p['seq']}. {p['name']} [{p['role']}{', ' + p['sex'] if p['sex'] else ''}]  {p['region'][:80]}")
                for t, v, dt, pl in p["facts"]: print(f"       {t:16} {' | '.join(x for x in (v, dt, pl) if x)}")
                for k, v, o in p["relations"]: print(f"       -> {k} ({v}) of #{o}")
        if ext[2] == "complete" and ext[0] == extractor:
            try: check(ps, fail)
            except Exception as e: fails.append(f"check raised {type(e).__name__}: {e}")
        if fails: bad += 1; print(f"FAIL {name}: " + "; ".join(fails))
        else: print(f"ok   {name}: {ext[0]}@{ext[1]}, {len(ps)} persona(s)")
    ok = cx.execute("PRAGMA integrity_check").fetchone()[0]; fk = cx.execute("PRAGMA foreign_key_check").fetchall()
    if ok != "ok" or fk: bad += 1; print(f"FAIL scratch catalog: integrity {ok}, foreign keys {len(fk)}")
    if a.keep: print("scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    print("green" if not bad else f"{bad} failure(s)")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
