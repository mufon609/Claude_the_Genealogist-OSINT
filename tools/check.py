#!/usr/bin/env python3
"""Green in one command: every parser read against a saved real page.

usage: tools/check.py [--show] [--keep]

A scratch catalog under a temporary data root, never the owner's. Every page under tests/fixtures/ is archived there and
read by tools/extract.py as the attach would read it, and the personas, facts and relations it writes are checked against
what the page says (tests/fixtures/README.md says where each page came from); the connectors' requests and their reading
of saved responses are checked with no network. One line per fixture, ok or FAIL with every
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
    db = os.path.join(d, "catalog", "tree.db"); os.makedirs(os.path.dirname(db)); os.makedirs(os.path.join(d, "inbox"))
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

def check_memorial(ps, fail, parsed):
    fail(len(ps) == 11, f"11 personas expected, {len(ps)} written")
    photos = parsed.get("photos") or []
    fail(len(photos) == 4 and [p["type"] for p in photos] == ["Grave", "Family", "Family", "Family"] and photos[0]["id"] == "49839510" and photos[0]["url"] == "https://images.findagrave.com/photos/2011/281/78019650_131821819991.jpg" and photos[0]["caption"] is None and photos[1]["caption"].startswith("Undated, About 1919"),
         f"the page's four photographs with the type the page gives each, the full-size image and the caption: {photos}")
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

def check_fs_birth(ps, fail):
    fail([(p["name"], p["role"], p["sex"]) for p in ps] == [("Frederick Michael Ahearu", "subject", "M"), ("James J. Ahearu", "father", "M"), ("Annie E. Scauusl", "mother", "F")],
         f"the birth record's subject and the parents its relatives table names, as written; got {[(p['name'], p['role'], p['sex']) for p in ps]}")
    fail(fact(ps[0], "Birth", date="22 May 1907", place="Northampton, Hampshire, Massachusetts"), "the birth on its day at its place, from the fields, whatever the heading says")
    fail(rel(ps[1], "parent", 1, "Father") and rel(ps[2], "parent", 1, "Mother"), "Father and Mother stated toward the child")

def check_fs_search(ps, fail):
    fail(len(ps) == 20, f"the page's twenty result rows, {len(ps)} written")
    p = ps[0]
    fail(p["name"] == "Fred M Ahearn" and p["role"] == "result" and "6XYS-NQ16" in p["region"], f"the first row as written with its ark as identity; got {p['name']} {p['region'][:80]}")
    fail(fact(p, "Birth", date="CAL 1933", place="Pennsylvania"), "the row's birth year, a census index's estimate, as a calculated year, and its place")
    fail(fact(p, "Unknown", value="Parents: Fred M Ahern, Helen B Ahearn") and fact(p, "Unknown", value="Siblings: Alice M Ahearn, John D Ahearn"), "the relatives named under each label")
    fail(fact(p, "Identification Number", value="ark:/61903/1:1:6XYS-NQ16"), "the ark as the persona's identification")
    q = ps[1]
    fail(q["name"] == "Frederick Horn" and fact(q, "Residence", date="3 April 1950", place="Sayre, Bradford, Pennsylvania"), f"a row's census event as a Residence on its date at its place; got {q['facts']}")
    fail(not any(p["name"].endswith("undefined") for p in ps) and not any(pl == "Other Places" for p in ps for _, _, _, pl in p["facts"]), "no stray 'undefined' in a name and no 'Other Places' as a place")
    fail('"collection":"United States, Census, 1950"' in p["region"] and '"role":"principal"' in p["region"], "the collection and the role word on the persona")

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
    fail(not any(t in ("Death", "Residence") for p in ps for t, _, _, _ in p["facts"]), "no date of life made from the page's date: running text states none")
    fail(all('"segment":"/service/ndnp' in p["region"] and '"date":"1918-05-10"' in p["region"] and "union city" in p["region"] for p in ps), "the page's segment, date and place in the persona's region")

def check_va(ps, fail):
    fail(len(ps) == 2 and [p["role"] for p in ps] == ["result", "result"], f"the page's two decedents as results; got {[(p['name'], p['role']) for p in ps]}")
    p = ps[1] if len(ps) > 1 else ps[0]
    fail(p["name"] == "Raymond E Davidson" and '"name_as_written":"DAVIDSON, RAYMOND E"' in p["region"], f"the name the right way round, the page's form in the region; got {p['name']} {p['region'][:80]}")
    fail(fact(p, "Birth", date="10/12/1939") and fact(p, "Death", date="01/27/2007"), f"the dates of birth and death as the page writes them; got {p['facts']}")
    fail(fact(p, "Burial", value="Plot: SECTION O1 SITE 2239", place="BG WILLIAM C DOYLE VET'S MEM CEM, Wrightstown, New Jersey"), f"the burial: the section and site as the plot, the cemetery at its town and state; got {fact(p, 'Burial')}")
    fail(fact(p, "Military Service", value="MSGT US AIR FORCE, VIETNAM"), "rank, branch and war period as one Military Service attribute")
    fail(fact(ps[0], "Burial", place="HILLCREST MEMORIAL PARK, Hermitage, Pennsylvania"), f"a private cemetery's burial at its town; got {fact(ps[0], 'Burial')}")

def check_va_page1(ps, fail):
    fail(len(ps) == 10 and all(p["role"] == "result" for p in ps), f"ten decedents on the first page, every one a result; got {len(ps)}")
    fail(ps[0]["name"] == "Raymond Jr Davidson" and fact(ps[0], "Birth", date="12/20/1926") and fact(ps[0], "Burial", value="Plot: SECTION 404 SITE 640", place="FLORIDA NATIONAL CEMETERY, Bushnell, Florida"), f"the first decedent as written; got {ps[0]['name']} {ps[0]['facts']}")

def check_ia_inside(ps, fail):
    fail(len(ps) >= 1, f"a persona per place the searched surname stands in the chosen pages' text; got {len(ps)}")
    fail(all("heebner" in p["name"].lower() for p in ps), f"every persona named around Heebner; got {[p['name'] for p in ps][:6]}")
    fail(not any(t in ("Death", "Residence") for p in ps for t, _, _, _ in p["facts"]), "no residence made from a book's date: only a directory entry states one")
    fail(all('"segment":"genealogicalreco01krie"' in p["region"] and '"date":"1879-01-01"' in p["region"] for p in ps), "the item and its date in the persona's region")

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
    ("familysearch-search-census-1950-ahearn-frederick-micheal.html", "text/html", "D03", "url", "https://www.familysearch.org/en/search/record/results?f.collectionId=4464515&q.givenName=Frederick%20Micheal&q.surname=Ahearn", "familysearch-search", check_fs_search),
    ("familysearch-massachusetts-birth-records-1907-FXJ3-Z7X.html", "text/html", "D03", "apid", "1,5062::1903623", "familysearch-record", check_fs_birth),
    ("findagrave-search-davidson-robert-1915-2004.html", "text/html", "E01", "url", "https://www.findagrave.com/memorial/search?firstname=Robert&lastname=Davidson&birthyear=1915&deathyear=2004", "findagrave-search", check_fg_search),
    ("va-gravesite-search-davidson-raymond-2007.html", "text/html", "E03", "url", "https://gravelocator.cem.va.gov/ngl/#lastName=Davidson&firstName=Raymond&deathYear=2007", "va-gravesite", check_va),
    ("va-gravesite-search-davidson-raymond-page1.html", "text/html", "E03", "url", "https://gravelocator.cem.va.gov/ngl/#lastName=Davidson&firstName=Raymond", "va-gravesite", check_va_page1),
]

def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=os.environ)
    if r.returncode: raise RuntimeError(f"{os.path.basename(args[0])} failed:\n{r.stdout}{r.stderr}")
    return r.stdout

def decisions(keep, show):
    """The matcher, the standing rule and the decision writers on a scratch catalog holding tests/fixtures/harness.ged (the
    Ahearn household of 1940 and Helen's parents), with the 1940 page, Abram C Brant's memorial and its gravestone photograph
    arriving as they would through the inbox. Returns the failures found."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from attach import attach_inbox
    from catalog import tier_sql
    from conclude import decide, rule_accepts
    from extract import extract
    from facts import fact_status
    from plan import plan_person
    fails = []; fail = lambda ok, why: None if ok else fails.append(why)
    say = (lambda *a: print("    ", *a)) if show else (lambda *a: None)
    run(os.path.join(ROOT, "tools", "tree.py"), "--db", db, "--by", BY, "create", "harness", "--name", "Harness")
    run(os.path.join(ROOT, "tools", "ingest_gedcom.py"), os.path.join(FIXTURES, "harness.ged"), "--keep", "--db", db, "--tree", "harness", "--by", BY)
    cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
    tid = cx.execute("SELECT id FROM tree WHERE slug='harness'").fetchone()[0]
    who = {r["display_name"]: r["id"] for r in cx.execute("SELECT id, display_name FROM person WHERE tree_id=?", (tid,))}
    name = lambda pid: next(n for n, i in who.items() if i == pid)
    for pid in who.values(): plan_person(cx, tid, pid, BY)
    cx.commit()
    fail(len(who) == 8, f"eight persons ingested, got {len(who)}")
    props = lambda **w: [dict(r) for r in cx.execute("SELECT * FROM proposal WHERE tree_id=? AND status=? AND kind IN ('persona_match','new_person') ORDER BY created_at, id", (tid, w.get("status", "undecided")))]
    person_of = lambda p: json.loads(p["payload_json"]).get("person_id")
    nassert = lambda: cx.execute("SELECT COUNT(*) FROM assertion WHERE tree_id=? AND status='accepted'", (tid,)).fetchone()[0]
    memberships = lambda: [(name(fm["person_id"]), fm["role"], a["status"], (json.loads(a["notes"] or "{}").get("placed")))
                           for fm in cx.execute("SELECT family_id, person_id, role FROM family_member")
                           for a in cx.execute("SELECT status, notes FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256 NOT IN (SELECT artifact_sha256 FROM tree_import)", (treelib.dumps([fm["family_id"], fm["person_id"], fm["role"]]),))]
    # ---- a place string the resolver left undecided is decided on the fact row (a place_resolution proposal, decided by
    # conclude.decide): the place chosen fills every event carrying the words; "not a place" leaves them and keeps the reason
    import hashlib
    from resolve_places import RESOLVER, cache_dir, candidate_summary
    from catalog import Catalog as _Cat
    ps_of = lambda raw: cx.execute("SELECT id, status, place_id FROM place_string WHERE raw=?", (raw,)).fetchone()
    ev_of = lambda raw: [r[0] for r in cx.execute("""SELECT DISTINCT e.id FROM event e JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                                     JOIN place_string ps ON ps.id=pf.place_string_id WHERE e.tree_id=? AND ps.raw=?""", (tid, raw))]
    rx = cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", RESOLVER).fetchone()
    rx_id = rx[0] if rx else treelib.ulid()
    if not rx: cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (rx_id, *RESOLVER, treelib.now()))
    def planted(raw, cands, queries):
        """A place_resolution proposal for the string as the resolver would write it, its candidates' full geocoder answers in the cache."""
        os.makedirs(cache_dir(), exist_ok=True)
        for qy in queries:
            with open(os.path.join(cache_dir(), hashlib.sha1(qy.lower().encode()).hexdigest() + ".json"), "w", encoding="utf-8") as fh: json.dump({"query": qy, "fetched_at": treelib.now(), "results": cands}, fh)
        pid_ = treelib.ulid()
        cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                   (pid_, tid, "place_resolution", treelib.dumps({"raw": raw, "place_string_id": ps_of(raw)[0], "parsed": {}, "queries": queries, "candidates": [candidate_summary(c, 1.0, {}) for c in cands], "reason": "harness: the owner chooses"}), "harness: the owner chooses", rx_id, treelib.now()))
        cx.execute("UPDATE place_string SET resolver=?, resolved_at=? WHERE id=?", (f"ai:{RESOLVER[1]}@{RESOLVER[2]}", treelib.now(), ps_of(raw)[0]))
        return pid_
    egypt = {"osm_type": "relation", "osm_id": 170912, "lat": "40.0676", "lon": "-74.5307", "name": "New Egypt", "display_name": "New Egypt, Plumsted Township, Ocean County, New Jersey, United States",
             "category": "boundary", "type": "administrative", "addresstype": "village", "address": {"village": "New Egypt", "county": "Ocean County", "state": "New Jersey", "country": "United States", "country_code": "us"}, "extratags": {"wikidata": "Q1024281"}}
    jersey = {"osm_type": "relation", "osm_id": 224951, "lat": "40.07", "lon": "-74.72", "name": "New Jersey", "display_name": "New Jersey, United States", "category": "boundary", "type": "administrative", "addresstype": "state",
              "address": {"state": "New Jersey", "country": "United States", "country_code": "us"}, "extratags": {}}
    prop_e = planted("New Egypt, Ocean, New Jersey, USA", [egypt], ["New Egypt, Ocean County, New Jersey, United States"]); prop_l = planted("New Jersey, USA", [jersey], ["New Jersey, United States"]); cx.commit()
    fail(ev_of("New Egypt, Ocean, New Jersey, USA") and all(cx.execute("SELECT place_id FROM event WHERE id=?", (e,)).fetchone()[0] is None for e in ev_of("New Egypt, Ocean, New Jersey, USA")), "before the answer, the events carrying the words have no place")
    r_pl = decide(cx, tid, prop_e, "accepted", BY, choice=0); cx.commit(); say("place accepted:", r_pl)
    row_e = ps_of("New Egypt, Ocean, New Jersey, USA")
    fail(r_pl.get("ok") and r_pl["kind"] == "place_resolution" and row_e[1] == "accepted" and row_e[2] and cx.execute("SELECT resolver FROM place_string WHERE id=?", (row_e[0],)).fetchone()[0] == BY,
         f"the string is accepted with a place, the resolver the one who answered: {tuple(row_e)}, {r_pl}")
    fail(ev_of("New Egypt, Ocean, New Jersey, USA") and all(cx.execute("SELECT place_id FROM event WHERE id=?", (e,)).fetchone()[0] == row_e[2] for e in ev_of("New Egypt, Ocean, New Jersey, USA")) and r_pl["placed"] == r_pl["events"] == len(ev_of("New Egypt, Ocean, New Jersey, USA")),
         f"every event carrying the words takes the place, and the answer says so: {r_pl}")
    fail(_Cat(cx, tid).place(ev_of("New Egypt, Ocean, New Jersey, USA")[0], row_e[2])["text"] == "New Egypt < Ocean County < New Jersey < United States", f"the event shows the chosen place's chain: {_Cat(cx, tid).place(ev_of('New Egypt, Ocean, New Jersey, USA')[0], row_e[2])}")
    fail(cx.execute("SELECT status FROM proposal WHERE id=?", (prop_e,)).fetchone()[0] == "accepted" and cx.execute("SELECT 1 FROM audit_log WHERE entity_kind='place_string' AND entity_id=? AND action='accept'", (row_e[0],)).fetchone(), "the proposal is decided and the string has its audit row")
    r_pr = decide(cx, tid, prop_l, "rejected", BY, note="harness: the words are a stand-in, not a place"); cx.commit(); say("place rejected:", r_pr)
    row_l = ps_of("New Jersey, USA")
    fail(r_pr.get("ok") and row_l[1] == "rejected" and row_l[2] is None and json.loads(cx.execute("SELECT notes FROM place_string WHERE id=?", (row_l[0],)).fetchone()[0])["reason"] == "harness: the words are a stand-in, not a place",
         f"the string is rejected with the reason kept in its notes: {tuple(row_l)}")
    fail(ev_of("New Jersey, USA") and all(cx.execute("SELECT place_id FROM event WHERE id=?", (e,)).fetchone()[0] is None for e in ev_of("New Jersey, USA")) and r_pr["placed"] == 0, f"the events carrying the rejected words are left as they were: {r_pr}")
    fail(decide(cx, tid, prop_l, "rejected", BY).get("error") == "already decided", "a place answer is given once")
    # ---- the 1940 page arrives: four people cite it under their own record ids, each is the record's own person; the rule takes none
    shutil.copy(os.path.join(FIXTURES, "familysearch-census-1940-KQX1-VT9.html"), os.path.join(treelib.inbox_dir(), "familysearch-census-1940-KQX1-VT9.html"))
    res = attach_inbox(cx, tid, "harness", BY, ["familysearch-census-1940-KQX1-VT9.html"]); cx.commit(); say("attach 1940:", res)
    ps = props(); named = sorted(name(person_of(p)) for p in ps if person_of(p))
    fail(named == ["Alicia Ahern", "Frederick Michael Ahearn", "Frederick Micheal Ahearn Jr", "Helen Sara Brant"], f"a card for each of the four the page names and cites, nobody else; got {named}")
    fail(all(p["kind"] == "persona_match" for p in ps), "every card a persona match: the tree has them all")
    reasons = {name(person_of(p)): rule_accepts(cx, tid, cx.execute("SELECT * FROM proposal WHERE id=?", (p["id"],)).fetchone()) for p in ps}
    say("rule:", reasons)
    fail(all(not ok for ok, _ in reasons.values()), "the rule takes nothing on a tree with no accepted fact")
    fail("not accepted" in reasons["Frederick Micheal Ahearn Jr"][1].lower(), f"the rule stands on accepted facts only, and the son has none: {reasons['Frederick Micheal Ahearn Jr'][1]}")
    fail("disagree" in reasons["Frederick Michael Ahearn"][1].lower(), f"a disagreement refuses the father: {reasons['Frederick Michael Ahearn'][1]}")
    card = {name(person_of(p)): p["id"] for p in ps}
    # ---- the son accepted: his facts, no family link yet
    n0 = nassert(); r = decide(cx, tid, card["Frederick Micheal Ahearn Jr"], "accepted", BY, "harness"); cx.commit(); say("son:", r)
    fail(r.get("ok") and r["assertions"] >= 6 and not r["memberships"], f"the son's facts accepted from the record and no family link before a parent is: {r}")
    fail(fact_status(cx, who["Frederick Micheal Ahearn Jr"], "name") == "accepted" and fact_status(cx, who["Frederick Micheal Ahearn Jr"], "birth") == "accepted", "his name and birth read accepted")
    fail(fact_status(cx, who["Frederick Micheal Ahearn Jr"], "parents") == "undecided", "his parents still undecided")
    # ---- a results page for him: the matcher's verdict on every row, checked directly on the candidate card
    from cards import search_card
    from treelib import archive_object
    with open(os.path.join(FIXTURES, "familysearch-search-census-1950-ahearn-frederick-micheal.html"), "rb") as fh: data = fh.read()
    src = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id='D03'").fetchone()
    sha_r, _ = archive_object(cx, data, mime="text/html", source_id="D03", collection_id=None, locator_kind="url", locator_value="https://www.familysearch.org/en/search/record/results?f.collectionId=4464515&q.givenName=Frederick%20Micheal&q.surname=Ahearn",
                              retrieved_by=BY, terms=src[1], cost="free", trust_tier=src[0], original_filename="familysearch-search-census-1950-ahearn-frederick-micheal.html")
    extract(cx, sha_r, BY); cx.commit()
    sc = search_card(cx, tid, sha_r, who["Frederick Micheal Ahearn Jr"]); cx.row_factory = sqlite3.Row
    verdicts = [(r["n"], r["name"], r["fits"]) for r in (sc or {}).get("rows", [])]; say("results page verdicts:", verdicts)
    fail(sc and len(verdicts) == 20 and verdicts[0][1] == "Fred M Ahearn" and verdicts[0][2] and not any(f for _, _, f in verdicts[1:]), f"on the 1950 results page row 1 fits him and rows 2 to 20 do not: {verdicts}")
    fail(sc and sc["rows"][1]["burial"] == "Sayre, Bradford, Pennsylvania, United States", f"a record row shows its residence as its place: {sc and sc['rows'][1]['burial']}")
    # ---- the mother accepted: the mother-son link
    r = decide(cx, tid, card["Helen Sara Brant"], "accepted", BY, "harness"); cx.commit(); say("mother:", r)
    fail(any(m.get("role") == "child" and m.get("person") == who["Frederick Micheal Ahearn Jr"] for m in r["memberships"]), f"accepting the mother asserts the son's child membership: {r['memberships']}")
    fail(fact_status(cx, who["Frederick Micheal Ahearn Jr"], "parents") == "accepted", "the son's parents read accepted on the record")
    fail(fact_status(cx, who["Helen Sara Brant"], "spouses") == "undecided", "her spouses wait for the father's card")
    # ---- the father accepted: the couple relation and the link from his side
    r = decide(cx, tid, card["Frederick Michael Ahearn"], "accepted", BY, "harness"); cx.commit(); say("father:", r)
    fail(any(m.get("role") == "child" for m in r["memberships"]) and any(m.get("role") == "partner" or m.get("role") == "spouse" for m in r["memberships"]), f"the father's accept asserts the child link and the couple: {r['memberships']}")
    fail(fact_status(cx, who["Helen Sara Brant"], "spouses") == "accepted" and fact_status(cx, who["Frederick Michael Ahearn"], "spouses") == "accepted", "both spouses facts accepted on the couple relation")
    # ---- his birth event now carries two place strings, the file's claim (undecided) and the census's (accepted): the event shows the accepted one, not whichever sorts first
    from catalog import Catalog as _Cat
    fb = cx.execute("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? AND e.event_type='Birth'", (who["Frederick Michael Ahearn"],)).fetchone()
    fb_strings = {r[0]: r[1] for r in cx.execute("""SELECT ps.raw, a.status FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN place_string ps ON ps.id=pf.place_string_id
                                                     WHERE a.subject_kind='event' AND a.subject_id=?""", (fb[0],))} if fb else {}
    fail(fb and fb_strings.get("Pennsylvania") == "accepted" and fb_strings.get("Northampton, Hampshire, Massachusetts, USA") == "undecided" and _Cat(cx, tid).place(fb[0], None)["text"] == "Pennsylvania",
         f"an event with an accepted and an undecided place string shows the accepted one: strings {fb_strings}, shown {_Cat(cx, tid).place(fb[0], None) if fb else None}")
    # ---- the family links the page asserted stand as links on a record for the matcher: mother and son, and the couple, each membership
    # carrying an accepted assertion on the 1940 page whose notes name neither vouched nor uncited
    from catalog import Catalog
    from match import linked
    fail(linked(Catalog(cx, tid), who["Helen Sara Brant"], who["Frederick Micheal Ahearn Jr"]), "the mother and son are linked on the 1940 page once both are accepted on it and her own membership is asserted")
    fail(linked(Catalog(cx, tid), who["Helen Sara Brant"], who["Frederick Michael Ahearn"]), "the couple is linked on the 1940 page")
    birth = cx.execute("""SELECT e.date_text, ps.raw FROM event e JOIN event_participant ep ON ep.event_id=e.id JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id AND a.status='accepted'
                          JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          WHERE ep.person_id=? AND e.event_type='Birth' AND a.artifact_sha256='3a1a54eb4b02209c0cc43714a6c8595f40c44de4cfad5ee19d73c2a6d68e6b8e'""", (who["Frederick Michael Ahearn"],)).fetchone()
    fail(birth and birth[0] == "22 May 1907" and birth[1] == "Pennsylvania", f"the record's birthplace accepted as what the record says, on the tree's own Birth event, whose value stays: {tuple(birth) if birth else None}")   # the conflict question itself needs the tree's place resolved, which takes the geocoder
    # ---- the father's birth record arrives: its row from the record's event type, his name one letter apart, the parents it states
    shutil.copy(os.path.join(FIXTURES, "familysearch-massachusetts-birth-records-1907-FXJ3-Z7X.html"), os.path.join(treelib.inbox_dir(), "familysearch-massachusetts-birth-records-1907-FXJ3-Z7X.html"))
    res = attach_inbox(cx, tid, "harness", BY, ["familysearch-massachusetts-birth-records-1907-FXJ3-Z7X.html"]); cx.commit(); say("attach birth record:", res)
    fail(res and res[0].get("steps") and all(n == "Frederick Michael Ahearn" and rk.startswith("birth record") and why for _, n, rk, why in res[0]["steps"]), f"the birth record attaches to his birth record step by the record's own event type and his name one letter apart: {res and res[0].get('steps')}")
    bp = [p for p in props() if json.loads(p["payload_json"]).get("artifact_sha256") == (res[0].get("sha256") if res else None)]
    fail(len(bp) == 1 and name(person_of(bp[0])) == "Frederick Michael Ahearn" and "one letter apart" in bp[0]["rationale"], f"one card, his, saying the surname is one letter apart: {[(name(person_of(p)) if person_of(p) else None, p['rationale'][:160]) for p in bp]}")
    if bp:
        r = decide(cx, tid, bp[0]["id"], "accepted", BY, "harness"); cx.commit(); say("birth record:", r)
        fail(r.get("ok") and cx.execute("""SELECT 1 FROM assertion a JOIN persona_fact f ON f.id=a.persona_fact_id WHERE a.status='accepted' AND a.artifact_sha256=? AND f.fact_type='Birth' AND f.date_text='22 May 1907'""", (res[0]["sha256"],)).fetchone(), "his birth on its day accepted from the record")
        after_b = [p for p in props() if json.loads(p["payload_json"]).get("artifact_sha256") == res[0]["sha256"]]
        fa = next((p for p in after_b if person_of(p) and name(person_of(p)) == "James Joseph Ahearn"), None)
        fail(fa is not None and "Father" in fa["rationale"] and fa["status"] == "undecided", f"the father the record names proposed as James Joseph Ahearn on the stated relationship once the child is accepted, a card: {[(name(person_of(p)) if person_of(p) else None, p['kind'], p['status']) for p in after_b]}")
        if fa:
            ok_r, why_r = rule_accepts(cx, tid, cx.execute("SELECT * FROM proposal WHERE id=?", (fa["id"],)).fetchone()); say("rule on one letter apart:", ok_r, why_r)
            fail(not ok_r and "one letter apart" in why_r, f"the rule does not take a name one letter apart: {why_r}")
    # ---- the sister accepted: placed beside her brother with an undecided assertion, the record states the sibling, not the parents
    r = decide(cx, tid, card["Alicia Ahern"], "accepted", BY, "harness"); cx.commit(); say("sister:", r, memberships())
    fail(any(n == "Alicia Ahern" and role == "child" and st == "undecided" and placed == "sibling" for n, role, st, placed in memberships()), f"the sister's membership carries an undecided sibling placement: {memberships()}")
    # ---- a link on the owner's word is a vouch, not a record: the sister placed with her parents by their word is linked to nobody for the matcher
    from conclude import link_on_word
    link_on_word(cx, tid, who["Alicia Ahern"], [who["Frederick Michael Ahearn"], who["Helen Sara Brant"]], "child", "3a1a54eb4b02209c0cc43714a6c8595f40c44de4cfad5ee19d73c2a6d68e6b8e", BY, "harness: the owner's word"); cx.commit()
    fail(fact_status(cx, who["Alicia Ahern"], "parents") == "accepted", "her parents read accepted on the owner's word")
    fail(not linked(Catalog(cx, tid), who["Alicia Ahern"], who["Frederick Micheal Ahearn Jr"]) and not linked(Catalog(cx, tid), who["Alicia Ahern"], who["Helen Sara Brant"]), "a vouched link is not a link on a record: the sister is linked to neither her brother nor her mother for the matcher")
    # ---- the memorial arrives: a page anyone can edit; the rule takes its subject as Abram on the identity alone (the name, both dates to the day, the burial place, the wife and daughter it lists agree with the tree's claims), his facts stay claims, the people it links come up as cards
    shutil.copy(os.path.join(FIXTURES, "findagrave-memorial-78019650.html"), os.path.join(treelib.inbox_dir(), "findagrave-memorial-78019650.html"))
    res = attach_inbox(cx, tid, "harness", BY, ["findagrave-memorial-78019650.html"]); cx.commit(); say("attach memorial:", res)
    sha_m = res[0].get("sha256") if res else None; taken = (res[0].get("accepted_by_rule") or []) if res else []
    fail(len(taken) == 1 and taken[0][1] == "Abram C Brant" and "identity" in taken[0][2], f"the rule takes the memorial's subject as Abram, an identity on a page anyone can edit: {taken}")
    fail(taken and all(w in taken[0][2] for w in ("birth date to the day", "death date to the day", "burial place", "Charlotte", "Helen")), f"its reason names the day of birth, the day of death, the burial place and the relatives listed: {taken and taken[0][2]}")
    abram = cx.execute("SELECT * FROM proposal WHERE tree_id=? AND status='accepted' AND decided_by LIKE 'rule:%' AND json_extract(payload_json,'$.person_id')=?", (tid, who["Abram C Brant"])).fetchone()
    fail(abram is not None and cx.execute("SELECT status FROM person_persona WHERE person_id=? AND persona_id=?", (who["Abram C Brant"], json.loads(abram["payload_json"])["persona_id"])).fetchone()[0] == "accepted", "the persona link accepted, decided by the rule")
    facts_on = lambda: {r[0]: r[1] for r in cx.execute("SELECT status, COUNT(*) FROM assertion WHERE artifact_sha256=? AND subject_kind IN ('person','event') GROUP BY status", (sha_m,))}
    fail(facts_on().get("undecided", 0) >= 4 and not facts_on().get("accepted"), f"every fact the page types is written undecided, none accepted: {facts_on()}")
    fail(fact_status(cx, who["Abram C Brant"], "birth") == "undecided" and fact_status(cx, who["Abram C Brant"], "death") == "undecided", "his birth and death stay undecided: a page anyone can edit builds no fact")
    after = [p for p in props() if json.loads(p["payload_json"]).get("artifact_sha256", "").startswith("576c97b3")]
    persona_name = lambda p: cx.execute("SELECT name_text FROM persona WHERE id=?", (json.loads(p["payload_json"])["persona_id"],)).fetchone()[0]
    matched = sorted(name(person_of(p)) for p in after if p["kind"] == "persona_match"); new = [p for p in after if p["kind"] == "new_person"]
    say("after Abram:", matched, [persona_name(p) for p in new])
    fail(matched == ["Charlotte D Lukens", "Helen Sara Brant"], f"his wife and daughter proposed once he is accepted, his father of nearly the same name a hint: {matched}")
    for p in [p for p in after if p["kind"] == "persona_match"]:
        ok, why = rule_accepts(cx, tid, cx.execute("SELECT * FROM proposal WHERE id=?", (p["id"],)).fetchone()); say("rule on a listed relative:", name(person_of(p)), ok, why)
        fail(not ok and "three" in why and "Abram C Brant agrees" in why, f"a relative the page lists by name and years alone is refused, the stated relation the one thing that agrees: {why}")
    fail(len(new) >= 3 and "Sarah D. Cassel Brant" in [persona_name(p) for p in new], f"his mother and siblings, not in the tree, proposed as new people: {[persona_name(p) for p in new]}")
    # ---- a rejection writes the proposal and nothing else; a new person accepted is created with the link the record states, accepted even from this page
    n1 = nassert(); persons1 = cx.execute("SELECT COUNT(*) FROM person WHERE tree_id=?", (tid,)).fetchone()[0]
    r = decide(cx, tid, new[-1]["id"], "rejected", BY, "harness"); cx.commit()
    fail(r.get("ok") and nassert() == n1 and cx.execute("SELECT COUNT(*) FROM person WHERE tree_id=?", (tid,)).fetchone()[0] == persons1, "rejecting a new person writes the proposal and nothing else")
    parent = next((p for p in new if persona_name(p) == "Sarah D. Cassel Brant"), None)
    if parent:
        r = decide(cx, tid, parent["id"], "accepted", BY, "harness"); cx.commit(); say("new person:", r)
        made = cx.execute("SELECT p.display_name, n.given, n.surname FROM person p JOIN person_name n ON n.person_id=p.id AND n.is_primary=1 WHERE p.id=?", (r.get("person"),)).fetchone()
        say("made:", tuple(made) if made else None)
        fail(made and "Sarah" in made[0] and made[2] == "Cassel", f"the person created with the name as written and the marked maiden name as her birth surname: {tuple(made) if made else None}")
        fail(r.get("identity") and any(m.get("role") == "child" and m.get("person") == who["Abram C Brant"] for m in r["memberships"]), f"Abram placed as the new parent's child on the record, the link accepted though the page's facts are not: {r['memberships']}")
        fail(fact_status(cx, who["Abram C Brant"], "parents") == "accepted" and not facts_on().get("accepted"), f"his parents link reads accepted on the page, his facts still not: {facts_on()}")
    # ---- reconsider keeps the identity and refuses the listed relatives with the reason; a decision taken back is taken again as a card
    from conclude import reconsider, withdraw
    rows = reconsider(cx, tid, BY, dry_run=True); say("reconsider:", [(x["kind"], x["person"], x.get("kept", x.get("taken")), x["why"][:60]) for x in rows])
    fail(any(x["kind"] == "decision" and x["kept"] and x["person"] == "Abram C Brant" for x in rows), f"reconsider keeps Abram's identity: {[x for x in rows if x['kind'] == 'decision']}")
    fail(rows and not any(x["taken"] for x in rows if x["kind"] == "card") and all("three" in x["why"] for x in rows if x["kind"] == "card" and x["person"] in ("Charlotte D Lukens", "Helen Sara Brant")), f"the cards it refused stay refused, each with the reason: {[x for x in rows if x['kind'] == 'card']}")
    withdraw(cx, tid, abram["id"], BY, "harness: taken back", treelib.now()); cx.commit()
    fail(cx.execute("SELECT status FROM proposal WHERE id=?", (abram["id"],)).fetchone()[0] == "undecided", "the card is undecided again once taken back")
    rows = reconsider(cx, tid, BY); cx.commit(); say("reconsider after a withdrawal:", [(x["kind"], x["person"], x.get("kept", x.get("taken"))) for x in rows])
    fail(any(x["kind"] == "card" and x["taken"] and x["person"] == "Abram C Brant" for x in rows) and (cx.execute("SELECT decided_by FROM proposal WHERE id=?", (abram["id"],)).fetchone()[0] or "").startswith("rule:"), "a card the rule would take is taken by reconsider, recorded as the rule")
    # ---- the page read again while the rule's decision stands: the link carries to the new persona; the decision withdrawn afterwards
    # resets both personas (the decision is about the record, not one reading of it), and the cemetery row is not held
    from catalog import Catalog as _Cat
    eid_r, n_r = extract(cx, sha_m, BY); cx.commit(); say("re-read while the rule's decision stands:", n_r)
    abram_links = lambda: [(r[0] == eid_r, r[1]) for r in cx.execute("""SELECT pe.extraction_id, pp.status FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                                                                          WHERE pp.person_id=? AND pe.artifact_sha256=? AND pe.name_text='Abram C Brant' AND pe.role_in_record='memorial'""", (who["Abram C Brant"], sha_m))]
    fail(sorted(abram_links()) == [(False, "accepted"), (True, "accepted")], f"after the re-read the rule's link stands on the earlier persona and on the new one: {abram_links()}")
    fail(_Cat(cx, tid).is_subject(sha_m, who["Abram C Brant"]), "the memorial's subject is Abram through the current reading")
    withdraw(cx, tid, abram["id"], BY, "harness: taken back after a re-read", treelib.now()); cx.commit()
    fail(sorted(abram_links()) == [(False, "undecided"), (True, "undecided")], f"the decision withdrawn after a re-read leaves no accepted link on either persona: {abram_links()}")
    fail(not _Cat(cx, tid).is_subject(sha_m, who["Abram C Brant"]), "withdrawn, the memorial has no accepted subject persona for Abram")
    cem_w = [c for c in _Cat(cx, tid).person_citations(who["Abram C Brant"], subject_only=True) if c[2]]
    fail(not cem_w, f"withdrawn, no citation of his is held through an accepted subject persona, the earlier reading's link included: {cem_w}")
    # ---- the rule's identity taken back and given by the owner: an identity still, the facts undecided, the links standing, every reading's persona linked
    r = decide(cx, tid, abram["id"], "accepted", BY, "harness"); cx.commit(); say("given by the owner:", r)
    fail(r.get("ok") and r.get("identity") and not facts_on().get("accepted") and fact_status(cx, who["Abram C Brant"], "parents") == "accepted", f"the owner's accept of the card is an identity too, the page's facts still undecided, the link to his mother standing: {facts_on()}")
    fail(sorted(abram_links()) == [(False, "accepted"), (True, "accepted")], f"the owner's decision applies to every reading's persona of that name and role on the record: {abram_links()}")
    # ---- a memorial's own subject holds the cemetery row; a relative it merely lists never does, even accepted (a separate
    # fixture, so as not to disturb the re-read below): Abram's own memorial holds his cemetery row, not Helen's (her own
    # memorial is not on this tree) (docs/RESEARCH-CHECKLIST.md §3, §7)
    from catalog import Catalog
    from checklist import build as build_checklist
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server; server.CFG["by"] = BY
    from attach import _cost
    src_m2 = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id='E01'").fetchone()
    cid_m2 = treelib.ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)",
                                         (cid_m2, "E01", "U.S., Find a Grave® Index, 1600s-Current", "other", "findagrave_subject_test"))
    sha_m2, _ = archive_object(cx, b"harness memorial fixture: Abram C Brant, plot lists his daughter Helen Sara Brant", mime="text/html", source_id="E01", collection_id=cid_m2,
                               collection_name="U.S., Find a Grave® Index, 1600s-Current", locator_kind="url", locator_value="https://www.findagrave.com/harness-memorial-subject-test",
                               retrieved_by=BY, terms=src_m2[1], cost=_cost(src_m2[2]), trust_tier=src_m2[0], original_filename="harness-memorial-subject-test.html")
    r_m2 = server.transcribe(cx, sha_m2, {"name": "Abram C. Brant", "role": "memorial"}, by="llm:harness", about=[who["Abram C Brant"]]); cx.commit()
    r_m2h = server.transcribe(cx, sha_m2, {"name": "Helen Sara Brant", "role": "daughter", "relations": [{"persona_id": r_m2.get("persona"), "kind": "child", "text": "daughter"}]}, by="llm:harness")
    cx.commit(); say("isolated memorial subject test:", r_m2, r_m2h)
    card_a2 = cx.execute("SELECT * FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.extraction_id')=? AND json_extract(payload_json,'$.persona_id')=?",
                          (tid, r_m2.get("extraction"), r_m2.get("persona"))).fetchone() if r_m2.get("ok") else None
    card_h2 = cx.execute("SELECT * FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.extraction_id')=? AND json_extract(payload_json,'$.persona_id')=?",
                          (tid, r_m2h.get("extraction"), r_m2h.get("persona"))).fetchone() if r_m2h.get("ok") else None
    if card_a2: decide(cx, tid, card_a2["id"], "accepted", BY, "harness: this memorial's own subject"); cx.commit()
    if card_h2: decide(cx, tid, card_h2["id"], "accepted", BY, "harness: the listed daughter, though the rule alone would not take her"); cx.commit()
    cat_m2 = Catalog(cx, tid)
    helen_cem = next(row for row in build_checklist(cat_m2, who["Helen Sara Brant"])["checklist"]["A"] if row["record"] == "cemetery / family plot")
    abram_cem = next(row for row in build_checklist(cat_m2, who["Abram C Brant"])["checklist"]["A"] if row["record"] == "cemetery / family plot")
    fail(abram_cem["status"] == "held", f"Abram is this memorial's own subject: his cemetery row is held by it: {abram_cem}")
    fail(helen_cem["status"] != "held", f"Helen is only listed on Abram's memorial as his daughter, never its subject; her own memorial is not on this tree: her cemetery row stays {helen_cem['status']}, never held by his: {helen_cem}")
    # ---- the page read again: the decided links carry to the new personas, the old cards close as superseded, the page's facts stay undecided
    eid, n = extract(cx, "576c97b3b1585aea0ac5814c8175b69c752bfa9d0cefab7d7e99f2cebaa30982", BY); cx.commit(); say("re-read:", n)
    fail(n.get("links_carried") == 2, f"the two decided links (Abram, his mother) carried to the new personas: {n}")
    old = cx.execute("SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND json_extract(payload_json,'$.artifact_sha256')='576c97b3b1585aea0ac5814c8175b69c752bfa9d0cefab7d7e99f2cebaa30982'", (tid,)).fetchone()[0]
    fail(old == 0 and not facts_on().get("accepted"), f"no undecided card left on the re-read page and no fact of it accepted: {old}, {facts_on()}")
    # ---- the gravestone photograph: the one photograph the page types Grave is a fetch step under the cemetery row; saved under the name the list prints it is archived under the gravestone row, tier 1, unparsed, and a reading by the model is a card for Abram the rule leaves to the owner
    plan_person(cx, tid, who["Abram C Brant"], BY); cx.commit()
    photo = cx.execute("SELECT * FROM search_plan WHERE person_id=? AND step_key LIKE 'fetch:photo:%'", (who["Abram C Brant"],)).fetchall()
    fail(len(photo) == 1 and photo[0]["step_key"] == "fetch:photo:49839510" and photo[0]["locator_source_id"] == "E05" and photo[0]["locator_kind"] == "url" and photo[0]["locator_value"].endswith("78019650_131821819991.jpg") and photo[0]["row_key"].startswith("cemetery"),
         f"one fetch step, for the photograph typed Grave, under the cemetery row with the image's URL as locator; the three family photographs make none: {[dict(x) for x in photo]}")
    from fetches import waiting
    w = next((e for e in waiting(cx, tid) if e["holder_id"] == "E05"), None)
    fail(w and w["save_as"] == "findagrave-photo-78019650-49839510.jpg" and w["how"] == "image" and photo and w["url"] == photo[0]["locator_value"], f"the fetch list names the image and the file to save it under: {w}")
    with open(os.path.join(treelib.inbox_dir(), "findagrave-photo-78019650-49839510.jpg"), "wb") as fh: fh.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")   # the smallest of JPEG files stands in for the photograph
    res = attach_inbox(cx, tid, "harness", BY, ["findagrave-photo-78019650-49839510.jpg"]); cx.commit(); say("attach photo:", res)
    fail(res and res[0].get("steps") and photo and res[0]["steps"][0][0] == photo[0]["id"] and res[0]["extraction"] is None, f"the photograph attaches to its step by the name the list gave it and is not parsed: {res}")
    art = cx.execute(f"SELECT ar.source_id, ar.mime, {tier_sql()} AS tier FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?", (res[0]["sha256"],)).fetchone() if res and res[0].get("sha256") else None
    fail(art and art["source_id"] == "E05" and art["mime"] == "image/jpeg" and art["tier"] == "T1" and photo and cx.execute("SELECT status FROM search_plan WHERE id=?", (photo[0]["id"],)).fetchone()[0] == "done",
         f"archived under the gravestone row, an image, tier 1, its step done: {dict(art) if art else None}")
    sys.path.insert(0, os.path.join(ROOT, "app", "person")); import server; server.CFG["by"] = BY
    r = server.transcribe(cx, res[0]["sha256"], {"name": "Abram C. Brant", "role": "named on the stone", "birth_date": "1880", "death_date": "1961"}, by="llm:harness") if res and res[0].get("sha256") else {}
    cx.commit(); say("the stone read:", r)
    xr = cx.execute("SELECT x.kind, x.name, x.model_id, x.prompt_sha256 FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (r.get("extraction"),)).fetchone() if r.get("ok") else None
    fail(xr and xr["kind"] == "llm" and xr["name"] == "harness" and xr["model_id"] == "harness" and xr["prompt_sha256"] == server.FORM_SHA256,
         f"the model's extractor row carries the model named after llm: and the hash of the form's field names, the only prompt there is: {dict(xr) if xr else None}")
    card_p = cx.execute("SELECT * FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.extraction_id')=?", (tid, r.get("extraction"))).fetchone() if r.get("ok") else None
    ok_p, why_p = rule_accepts(cx, tid, card_p) if card_p else (None, "no card")
    fail(r.get("ok") and r["proposals"] == 1 and r["accepted_by_rule"] == 0 and card_p and name(person_of(card_p)) == "Abram C Brant" and not ok_p and "not accepted" in why_p,
         f"a reading of the stone by the model is a kind the rule may take (the gravestone's own inscription, once read), refused here for the true reason: Abram's own name is not yet accepted on the harness tree, not for who read it: {r}, {why_p}")
    # ---- an obituary read by the model: Helen's own name is already accepted (the 1940 census), her husband Frederick Michael Ahearn already her accepted spouse; the text names him, the rule's only ground for this kind
    from attach import _cost
    src_o = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id='H04'").fetchone()
    cid_o = treelib.ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)",
                                        (cid_o, "H04", "U.S., Newspapers.com™ Obituary Index, 1800s-current", "other", "newspapers_obituary"))
    sha_o, _ = archive_object(cx, b"harness obituary fixture: Helen Sara Brant, survived by her husband Frederick Michael Ahearn", mime="text/html", source_id="H04", collection_id=cid_o,
                              collection_name="U.S., Newspapers.com™ Obituary Index, 1800s-current", locator_kind="url", locator_value="https://www.newspapers.com/harness-obituary",
                              retrieved_by=BY, terms=src_o[1], cost=_cost(src_o[2]), trust_tier=src_o[0], original_filename="harness-obituary.html")
    r_o = server.transcribe(cx, sha_o, {"name": "Helen Sara Brant", "sex": "F", "role": "deceased", "year": "1986", "age": "76"}, by="llm:harness", about=[who["Helen Sara Brant"]]); cx.commit(); say("obituary subject:", r_o)
    r_h = server.transcribe(cx, sha_o, {"name": "Frederick Michael Ahearn", "role": "husband", "residence": "Boca Raton, Florida", "relations": [{"persona_id": r_o.get("persona"), "kind": "spouse", "text": "husband"}]}, by="llm:harness")
    cx.commit(); say("obituary husband:", r_h)
    card_o = cx.execute("SELECT * FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.extraction_id')=? AND json_extract(payload_json,'$.persona_id')=?", (tid, r_o.get("extraction"), r_o.get("persona"))).fetchone() if r_o.get("ok") else None
    ok_o, why_o = rule_accepts(cx, tid, card_o) if card_o else (None, "no card")
    fail(r_o.get("ok") and card_o and name(person_of(card_o)) == "Helen Sara Brant" and ok_o and "spouse Frederick Michael Ahearn" in why_o,
         f"an obituary read by the model, naming her husband who already stands as her accepted spouse, is taken by the rule, the reason naming him: {why_o}")
    # ---- held is the record's own subject, never a relative it merely names: accepted, the obituary holds Helen's own
    # obituary row (she is the deceased, no relation of her own to another persona); her husband's row stays as it was
    # (missing or cited), never held by a record that only lists him as a relative (docs/RESEARCH-CHECKLIST.md §3, §7)
    from catalog import Catalog
    from checklist import build as build_checklist
    from match import match
    fh_before = next(row for row in build_checklist(Catalog(cx, tid), who["Frederick Michael Ahearn"])["checklist"]["A"] if row["record"] == "obituary")
    decide(cx, tid, card_o["id"], "accepted", BY, "harness: the deceased's own identity"); cx.commit()
    match(cx, r_h["extraction"], BY, about=[who["Helen Sara Brant"]]); cx.commit()   # her own identity just decided on this record: the husband is proposed against her now-open family
    card_h = cx.execute("SELECT * FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.extraction_id')=? AND json_extract(payload_json,'$.persona_id')=?",
                         (tid, r_h.get("extraction"), r_h.get("persona"))).fetchone() if r_h.get("ok") else None
    fail(bool(card_h), "the husband's own persona match is proposed on the same record too, once she is accepted on it")
    if card_h: decide(cx, tid, card_h["id"], "accepted", BY, "harness: the named husband, though the rule alone would not take him"); cx.commit()
    cat_ob = Catalog(cx, tid)
    helen_ob = next(row for row in build_checklist(cat_ob, who["Helen Sara Brant"])["checklist"]["A"] if row["record"] == "obituary")
    husband_ob = next(row for row in build_checklist(cat_ob, who["Frederick Michael Ahearn"])["checklist"]["A"] if row["record"] == "obituary")
    fail(helen_ob["status"] == "held", f"Helen is the obituary's own subject, the deceased: her obituary row is held by it: {helen_ob}")
    fail(husband_ob["status"] != "held", f"her husband is named as a survivor, not the record's subject: his own obituary row ({fh_before['status']} before, {husband_ob['status']} after his card is accepted) is never held by a record that only names him: {husband_ob}")
    # ---- the gravesite locator's page for Davidson, Raymond, died 2007: one card, his, among the namesakes; the rule takes it once his dates are his own word
    from match import match
    from facts import decide_fact
    with open(os.path.join(FIXTURES, "va-gravesite-search-davidson-raymond-2007.html"), "rb") as fh: data = fh.read()
    src = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id='E03'").fetchone()
    cid_v = treelib.ulid(); cx.execute("INSERT INTO collection (id,source_id,name,external_key_kind,external_key) VALUES (?,?,?,?,?)", (cid_v, "E03", "VA Nationwide Gravesite Locator", "other", "va_graves"))
    sha_v, _ = archive_object(cx, data, mime="text/html", source_id="E03", collection_id=cid_v, collection_name="VA Nationwide Gravesite Locator", locator_kind="url",
                              locator_value="https://gravelocator.cem.va.gov/ngl/#lastName=Davidson&firstName=Raymond&deathYear=2007", retrieved_by=BY, terms=src[1], cost="free", trust_tier=src[0],
                              original_filename="va-gravesite-search-davidson-raymond-2007.html")
    eid_v, n = extract(cx, sha_v, BY); wrote = match(cx, eid_v, BY, about=[who["Raymond Earl Davidson"]]); cx.commit(); say("gravesite page:", n, wrote)
    fail(len(wrote) == 1 and wrote[0][1] == "persona_match" and wrote[0][2] == "Raymond E Davidson" and wrote[0][3] == who["Raymond Earl Davidson"],
         f"one card on the gravesite page, Raymond E Davidson as Raymond Earl Davidson; the namesake who died the same year another day stays a hint: {[(k, nm) for _, k, nm, _ in wrote]}")
    vp = cx.execute("SELECT * FROM proposal WHERE id=?", (wrote[0][0],)).fetchone() if wrote else None
    fail(vp and "though something disagrees" in vp["rationale"] and all(x in vp["rationale"].lower() for x in ("burial place disagrees", "birth date agrees", "death date agrees")),
         f"the card says the dates agree to the day and the burial town differs (the locator's postal town against the memorial's): {vp and vp['rationale'][:300]}")
    ok_v, why_v = rule_accepts(cx, tid, vp) if vp else (False, "no card"); say("rule on the gravesite card:", ok_v, why_v)
    fail(not ok_v and why_v.startswith("disagrees") and "burial place" in why_v, f"a gravesite record is a kind the rule may take, and it refuses this one for the burial town, not as a hint: {why_v}")
    with open(os.path.join(FIXTURES, "va-gravesite-search-davidson-raymond-page1.html"), "rb") as fh: data = fh.read()
    sha_p, _ = archive_object(cx, data, mime="text/html", source_id="E03", collection_id=cid_v, collection_name="VA Nationwide Gravesite Locator", locator_kind="url",
                              locator_value="https://gravelocator.cem.va.gov/ngl/#lastName=Davidson&firstName=Raymond", retrieved_by=BY, terms=src[1], cost="free", trust_tier=src[0],
                              original_filename="va-gravesite-search-davidson-raymond-page1.html")
    eid_p, n = extract(cx, sha_p, BY); wrote_p = match(cx, eid_p, BY, about=[who["Raymond Earl Davidson"]]); cx.commit(); say("gravesite page of namesakes:", n, wrote_p)
    fail(n.get("personas") == 10 and wrote_p == [], f"ten namesakes agreeing on the name alone make no card: {[(k, nm) for _, k, nm, _ in wrote_p]}")
    # ---- hints under the record (docs/RESEARCH-WORKFLOW.md §0): a persona with no proposal and no link, compared with the person on
    # view; a newspaper hit on the surname alone is never a hint; a row agreeing on a year and a place is, once the baseline is reviewed
    from cards import hints_on
    with open(os.path.join(FIXTURES, "locgov-ocr-sn89058321-1918-05-10-p2.manifest.json"), encoding="utf-8") as fh: man_l = json.load(fh)
    with open(os.path.join(FIXTURES, "locgov-ocr-sn89058321-1918-05-10-p2.json"), "rb") as fh: data = fh.read()
    src_l = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id=?", (man_l["source_id"],)).fetchone()
    sha_l, _ = archive_object(cx, data, mime=man_l["mime"], source_id=man_l["source_id"], collection_id=None, collection_name=man_l.get("collection"), locator_kind=man_l["locator"]["kind"], locator_value=man_l["locator"]["value"],
                              retrieved_by=BY, terms=src_l[1], cost="free", trust_tier=src_l[0], original_filename="locgov-ocr-sn89058321-1918-05-10-p2.json", notes=json.dumps({**json.loads(man_l["notes"]), "step_type": "obituary"}))
    art_l = cx.execute("SELECT redistributable, manifest_json FROM artifact WHERE sha256=?", (sha_l,)).fetchone()
    fail(art_l and art_l["redistributable"] == 1 and json.loads(art_l["manifest_json"])["rights"]["redistributable"] is True and json.loads(art_l["manifest_json"])["rights"].get("redistributable_by") == "H01",
         f"a loc.gov page (public domain) is redistributable and its manifest names the registry row that said so: {dict(art_l) if art_l else None}")
    art_g = cx.execute("SELECT redistributable, manifest_json FROM artifact WHERE mime='text/x-gedcom'").fetchone()
    fail(art_g and art_g["redistributable"] == 0 and json.loads(art_g["manifest_json"])["rights"]["redistributable"] is False, f"an Ancestry export is not: {dict(art_g) if art_g else None}")
    eid_l, n_l = extract(cx, sha_l, BY); wrote_l = match(cx, eid_l, BY, about=[who["Raymond Earl Davidson"]]); cx.commit(); say("newspaper page:", n_l, wrote_l)
    hl = hints_on(cx, tid, sha_l, who["Raymond Earl Davidson"])
    fail(n_l.get("personas") and wrote_l == [] and len(hl) == n_l["personas"] and not any(v["hint"] for v in hl.values()), f"a newspaper hit on the surname alone makes no card and is no hint: {[(v['hint'], v['agrees']) for v in hl.values()][:3]}")
    r_rob = server.transcribe(cx, sha_p, {"name": "Robert Davidson", "role": "listed", "birth_date": "1939", "birth_place": "Suffolk County, New York"}, by="human:harness", about=[who["Raymond Earl Davidson"]]); cx.commit()
    fail(r_rob.get("ok") and r_rob["proposals"] == 0, f"a namesake's kin read from the page, agreeing on the surname, a year and a place but not the given name, gets no card: {r_rob}")
    hp = hints_on(cx, tid, sha_p, who["Raymond Earl Davidson"])
    fail(r_rob.get("persona") in hp and not hp[r_rob["persona"]]["hint"], f"before Raymond's baseline is reviewed nothing on the page is a hint: {hp.get(r_rob.get('persona'))}")
    for f_ in ("name", "sex", "birth", "death"): decide_fact(cx, tid, who["Raymond Earl Davidson"], f_, "accepted", None, BY)   # his key facts on the owner's word: the baseline reviewed
    cx.commit()
    fail(Catalog(cx, tid).baseline(who["Raymond Earl Davidson"])["complete"], "Raymond's baseline is reviewed on the owner's word")
    hp = hints_on(cx, tid, sha_p, who["Raymond Earl Davidson"]); rob = hp.get(r_rob.get("persona"))
    fail(rob and rob["hint"] and any(a.startswith("surname agrees") for a in rob["agrees"]) and any(a.startswith("birth date agrees") for a in rob["agrees"]) and any(a.startswith("birth place agrees") for a in rob["agrees"]),
         f"reviewed, the row agreeing on the surname, the birth year and the birth place is a hint with those words: {rob}")
    fail(hp and all(not v["hint"] for k, v in hp.items() if k != r_rob.get("persona")), f"the namesakes agreeing on the name alone are still no hint: {[(v['hint'], v['agrees'][:2]) for k, v in hp.items() if v['hint'] and k != r_rob.get('persona')]}")
    fail(not any(v["hint"] for v in hints_on(cx, tid, sha_l, who["Raymond Earl Davidson"]).values()), "reviewed, the surname-only newspaper hit is still no hint")
    av = server.artifact_view(cx, tid, sha_p, who["Raymond Earl Davidson"])
    fail(any(p.get("hint") and p["hint"]["hint"] for e in av["extractions"] for p in e["personas"] if p["id"] == r_rob.get("persona")), "the record view carries the hint on the persona row")
    # ---- Legacy.com (H05) is a source for an obituary row on a death from 1999 on: Raymond died 2007
    raymond_ob = next(row for row in build_checklist(Catalog(cx, tid), who["Raymond Earl Davidson"])["checklist"]["A"] if row["record"] == "obituary")
    fail(raymond_ob["sources"][:1] == ["H05"], f"a death in 2007 is in Legacy.com's 1999-on window: its row lists H05 first: {raymond_ob['sources']}")
    # ---- a page from a holder without a parser (the SAR database cited on James), saved under the name the fetch list printed, reaches its step: archived under the holder with its own URL, logged found, reported unparsed
    from fetches import collect, waiting as waiting_pages
    f04 = [e for e in waiting_pages(cx, tid) if e["holder_id"] == "F04"]
    sar = next((e for e in f04 if e["people"] == ["James Joseph Ahearn"]), None); son = next((e for e in f04 if e["people"] == ["Frederick Michael Ahearn"]), None)
    fail(sar and son and len(f04) == 2 and sar["save_as"].startswith("f04-") and sar["save_as"].endswith(f"-{who['James Joseph Ahearn'][-6:]}.html") and son["save_as"].endswith(f"-{who['Frederick Michael Ahearn'][-6:]}.html")
         and sar["save_as"][:-11] == son["save_as"][:-11] and sar["how"] == "page",
         f"the SAR page James's citation points at is listed twice, once for James and once for his son's footprint step, each name ending in its person's six characters: {f04}")
    dl = os.path.join(d, "downloads"); os.makedirs(dl, exist_ok=True)
    fname = sar["save_as"].replace("<year>", "1920") if sar else "x.html"
    with open(os.path.join(dl, fname), "w", encoding="utf-8") as fh: fh.write("<!-- saved from https://sarpatriots.sar.org/patriot/display/24680 -->\n<html><body><h1>Patriot</h1><p>AHEARN, JAMES</p></body></html>")
    names_c, res_c = collect(cx, tid, "harness", BY, folder=dl); cx.commit(); say("collect:", names_c, res_c)
    got = next((r for r in res_c if r["file"] == fname), None)
    fail(got and not got["left"] and [n for _, n, _, _ in got["steps"]] == ["James Joseph Ahearn"] and got.get("unparsed"), f"the page attaches to James's step alone by the list's name and is reported unparsed: {got}")
    fail(son and all(cx.execute("SELECT status FROM search_plan WHERE id=?", (sid,)).fetchone()[0] == "planned" for sid in son["step_ids"]), "his son's footprint step on the same citation, named for the son, still waits")
    art_c = cx.execute("SELECT source_id, locator_kind, locator_value, mime FROM artifact WHERE sha256=?", (got["sha256"],)).fetchone() if got and got.get("sha256") else None
    fail(art_c and art_c["source_id"] == "F04" and art_c["locator_kind"] == "url" and art_c["locator_value"] == "https://sarpatriots.sar.org/patriot/display/24680" and art_c["mime"] == "text/html", f"archived under the SAR row with the page's own URL as locator: {dict(art_c) if art_c else None}")
    fail(sar and all(cx.execute("SELECT status FROM search_plan WHERE id=?", (sid,)).fetchone()[0] == "done" for sid in sar["step_ids"]) and not os.path.exists(os.path.join(dl, fname)), "its step is done and the file has left the download folder")
    # ---- a step reopened after a found run: the run's row stays as written, and the record no longer names the step's person as one it was fetched for
    from log_search import reopen
    from match import persons_for
    named_before = {p for p, _, _ in persons_for(cx, got["sha256"])} if got and got.get("sha256") else set()
    fail(who["James Joseph Ahearn"] in named_before, f"the page's found run names James as a person it was fetched for: {named_before}")
    rows_before = [tuple(r) for r in cx.execute("SELECT id, outcome, artifacts_json FROM search_log WHERE plan_step_id IN (%s) ORDER BY id" % ",".join("?" * len(sar["step_ids"])), sar["step_ids"])] if sar else []
    for sid in (sar["step_ids"] if sar else []): reopen(cx, tid, BY, sid, "harness: wrongly matched")
    cx.commit()
    named_after = {p for p, _, _ in persons_for(cx, got["sha256"])} if got and got.get("sha256") else set()
    fail(sar and not named_after and all(cx.execute("SELECT status FROM search_plan WHERE id=?", (sid,)).fetchone()[0] == "planned" for sid in sar["step_ids"]), f"reopened, the steps are planned again and the record names nobody: {named_after}")
    rows_after = [tuple(r) for r in cx.execute("SELECT id, outcome, artifacts_json FROM search_log WHERE plan_step_id IN (%s) ORDER BY id" % ",".join("?" * len(sar["step_ids"])), sar["step_ids"])] if sar else []
    fail(rows_before and rows_after[:len(rows_before)] == rows_before and len(rows_after) == len(rows_before) + len(sar["step_ids"]) and all(r[1] == "none" for r in rows_after[len(rows_before):]), f"the found rows stay as they were, one reopen row added per step: before {rows_before}, after {rows_after}, steps {sar and sar['step_ids']}")
    # ---- a found run at a source other than a fetch step's holder leaves the step planned: the pages are held, the cited record is not
    from log_search import log as log_run
    ob = cx.execute("SELECT id, status FROM search_plan WHERE person_id=? AND kind='fetch' AND status='planned' LIMIT 1", (who["James Joseph Ahearn"],)).fetchone()
    if ob:
        log_run(cx, tid, BY, step_id=ob["id"], source_id="H07", outcome="found", artifacts=[sha_v], note="harness: another paper's page", done=False); cx.commit()
        fail(cx.execute("SELECT status FROM search_plan WHERE id=?", (ob["id"],)).fetchone()[0] == "planned" and cx.execute("SELECT outcome FROM search_log WHERE plan_step_id=? ORDER BY executed_at DESC LIMIT 1", (ob["id"],)).fetchone()[0] == "found",
             "a found run at a row-source connector is logged and the fetch step stays planned")
    # ---- a step the generator no longer produces is dropped and named in the run's audit row, the only trace of it afterwards
    gone = treelib.ulid()
    cx.execute("""INSERT INTO search_plan (id,person_id,row_key,seq,step_key,kind,query_type,query_json,sources_json,mode,expected,status,rationale,created_at)
                  VALUES (?,?,'obituary:',999,'search:harness:gone','search','obituary','{}','["H01"]','assisted','nothing','planned','harness: a step nothing generates',?)""", (gone, who["Raymond Earl Davidson"], treelib.now()))
    st_g = plan_person(cx, tid, who["Raymond Earl Davidson"], BY); cx.commit()
    audit_g = cx.execute("SELECT diff_json FROM audit_log WHERE entity_kind='search_plan' AND entity_id=? ORDER BY id DESC LIMIT 1", (who["Raymond Earl Davidson"],)).fetchone()
    named_g = json.loads(audit_g["diff_json"] if audit_g else "{}").get("dropped") or []
    fail(st_g["steps_dropped"] == 1 and st_g["dropped"] == [{"step_key": "search:harness:gone", "row_key": "obituary:", "rationale": "harness: a step nothing generates"}] and named_g == st_g["dropped"]
         and not cx.execute("SELECT 1 FROM search_plan WHERE id=?", (gone,)).fetchone(), f"the dropped step is gone and the audit row names it by key, row and rationale: {st_g.get('dropped')}, audit {named_g}")
    # ---- the plan is idempotent and the catalog whole
    st1 = {k: v for k, v in [(pid, plan_person(cx, tid, pid, BY)) for pid in who.values()]}; cx.commit()
    st2 = {k: v for k, v in [(pid, plan_person(cx, tid, pid, BY)) for pid in who.values()]}; cx.commit()
    fail(all(v["steps_new"] == 0 and v["steps_dropped"] == 0 and v["questions_new"] == 0 and v["questions_closed"] == 0 for v in st2.values()), f"a second plan run changes nothing: {[v for v in st2.values() if v['steps_new'] or v['steps_dropped'] or v['questions_new'] or v['questions_closed']]}")
    ok = cx.execute("PRAGMA integrity_check").fetchone()[0]; fk = cx.execute("PRAGMA foreign_key_check").fetchall()
    fail(ok == "ok" and not fk, f"scratch catalog: integrity {ok}, foreign keys {len(fk)}")
    repeats = cx.execute("""SELECT count(*) FROM (SELECT 1 FROM assertion WHERE persona_fact_id IS NOT NULL GROUP BY subject_kind, subject_id, persona_fact_id, artifact_sha256, coalesce(notes,'') HAVING count(*)>1)""").fetchone()[0]
    fail(repeats == 0, f"no statement of one record is written twice on one event by the decisions above: {repeats} repeated")
    cx.close()
    if keep: print("decisions scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

def rules():
    """The name rules as the docs state them, on their own."""
    from catalog import same_surname
    want = {("ahearn", "ahearn"): "agrees", ("ahern", "ahearn"): "variant", ("brant", "brandt"): "variant", ("ahearu", "ahearn"): "one letter apart",
            ("grant", "brant"): "", ("bran", "brant"): "", ("kriebel", "krebel"): "variant", ("horn", "ahearn"): ""}
    bad = [f"same_surname{k} gave {same_surname(*k)!r}, expected {v!r}" for k, v in want.items() if same_surname(*k) != v]
    from catalog import holder_search
    f = lambda **kw: {k: {"value": v, "basis": "citation"} for k, v in kw.items()}
    cases = [
        ({"HolderKind": "url", "HolderKey": "https://archive.org/search?query=title%3A%28%22{title}%22%29", "HolderCollection": "x"}, f(name="Abram C Brant", citation="The Genealogical Record of the Schwenkfelder Families"),
         "https://archive.org/search?query=title%3A%28%22The%20Genealogical%20Record%20of%20the%20Schwenkfelder%20Families%22%29"),
        ({"HolderKind": "url", "HolderKey": "https://www.legacy.com/obituaries/search?firstName={given}&lastName={surname}", "HolderCollection": "x"}, f(name="Helen Sara Brant"), "https://www.legacy.com/obituaries/search?firstName=Helen%20Sara&lastName=Brant"),
        ({"HolderKind": "url", "HolderKey": "{url}", "HolderCollection": "x"}, f(name="Noi Davidson", url="http://www.legacy.com/obituaries/x?n=noi"), "http://www.legacy.com/obituaries/x?n=noi"),
        ({"HolderKind": "url", "HolderKey": "https://archive.org/search?query=x+{year}", "HolderCollection": "x"}, f(name="Carol Evers"), None),
        ({"HolderKind": "url", "HolderKey": "", "HolderCollection": "x"}, f(name="Catherine Rittenhouse"), None),
        ({"HolderKind": "fs_images", "HolderKey": "1999196", "HolderCollection": "Pennsylvania, Probate Records, 1683-1994"}, f(name="Matthias Wool Rittenhouse"), None),
        ({"HolderKind": "fs_collection", "HolderKey": "1937489", "HolderCollection": "New York, State Census, 1925"}, f(name="Dorothy Peters", city="Hempstead", county="Nassau"),
         "https://www.familysearch.org/en/search/record/results?f.collectionId=1937489&q.givenName=Dorothy&q.residenceDate.from=1925&q.residenceDate.to=1925&q.residencePlace=Hempstead%2C%20Nassau&q.surname=Peters"),
        ({"HolderKind": "url", "HolderKey": "https://www.google.com/search?q=%22{title}%22&tbm=bks&tbs=cdr:1,cd_min:{mdy},cd_max:{mdy}", "HolderCollection": "x"},
         f(name="Helen Sara Brant", citation="Boca Raton News", **{"publication date": "27 Jan 1986"}),
         "https://www.google.com/search?q=%22Boca%20Raton%20News%22&tbm=bks&tbs=cdr:1,cd_min:1%2F27%2F1986,cd_max:1%2F27%2F1986"),
    ]
    for h, fields, want_url in cases:
        got = holder_search(h, fields)
        if got != want_url: bad.append(f"holder_search({h['HolderKind']}, {h['HolderKey'][:40]!r}) gave {got!r}, expected {want_url!r}")
    return bad

def connectors_offline():
    """The connectors' requests from a step's fields and their reading of saved responses, with no network: the Archive's
    title search for a cited book and the VA gravesite locator's posted search."""
    from connectors import ia, ia_books, va_graves
    from treelib import parse_gedcom_date
    bad = []; f = lambda **kw: {k: {"value": v, "basis": "citation"} for k, v in kw.items()}
    say = lambda ok, why: None if ok else bad.append(why)
    rq = ia_books.requests(f(collection="U.S., Family History Books", name="Abraham B Brant", citation="The Genealogical Record of the Schwenkfelder Families"))
    say(rq and rq[0]["url"].startswith(ia.ADVANCED) and "title%3A%28%22The%20Genealogical%20Record%20of%20the%20Schwenkfelder%20Families%22%29" in rq[0]["url"]
        and rq[0]["surname"] == "Brant" and str(rq[0]["given"]).startswith("Abraham"), f"a Family History Books citation asks the Archive's advanced search for its title with the citation's name: {rq}")
    rq2 = ia_books.requests(f(collection="North America, Family Histories, 1500-2000", name="Sarah Cassel", **{"book title": "A genealogical history of the Cassel family in America : being the descendants of Julius Kassel or"}))
    say(rq2 and rq2[0]["q"] == '"A genealogical history of the Cassel family in America"', f"a book title is asked by its main title, the subtitle and Ancestry's cut tail off: {rq2 and rq2[0]['q']}")
    say(ia_books.requests(f(collection="U.S., Family History Books", name="Robert Powell McCrary")) == [], "a book citation naming no title asks nothing")
    say(ia_books.requests(f(given="Abram C", surname="Brant", state="pennsylvania", birth_year=1880)) and "be-api.us.archive.org" in ia_books.requests(f(given="Abram C", surname="Brant", state="pennsylvania", birth_year=1880))[0]["url"], "a search step still asks the full-text search")
    with open(os.path.join(FIXTURES, "ia-advancedsearch-title-schwenkfelder-families.json"), "rb") as fh: body = fh.read()
    say(ia.total(body) == 3, f"the advanced search's total: {ia.total(body)}")
    hs = ia_books.hits(rq[0]["url"], body, rq[0]) if rq else []
    say([h["notes"]["item"] for h in hs] == ["genealogicalreco0000samu_a7w0", "genealogicalreco0000samu", "genealogicalreco00unse"], f"the three copies of the cited book, in the Archive's order: {[h['notes']['item'] for h in hs]}")
    say(hs and hs[0]["fetch"] == [{"url": "https://archive.org/metadata/genealogicalreco0000samu_a7w0", "kind": "json", "then": "metadata", "record": False}] and hs[0]["locator"]["value"] == "https://archive.org/details/genealogicalreco0000samu_a7w0",
        "a hit's first fetch is the item's metadata, the item's page its locator")
    say(ia_books.hits(rq2[0]["url"], body, rq2[0]) == [] if rq2 else False, "a response for another title gives no hit: every naming word of the cited title must be in the item's")
    rq = va_graves.requests(f(collection="U.S., Veterans' Gravesites, ca. 1775-2019", name="Raymond Earl Davidson"))
    say(rq and rq[0]["url"] == va_graves.URL and rq[0]["data"]["lastName"] == "Davidson" and rq[0]["data"]["firstName"] == "Raymond" and rq[0]["data"]["middleName"] == "E" and rq[0]["data"]["middleNameOpt"] == "2"
        and rq[0]["data"]["p_deathYY"] == "" and rq[0]["record"] is True and rq[0]["locator"] == "https://gravelocator.cem.va.gov/ngl/#lastName=Davidson&firstName=Raymond&middleName=E",
        f"a citation's name posts the locator's form, surname and first given name exact, the middle name's first letter as a beginning, the page the record: {rq}")
    rq = va_graves.requests({"given": {"value": "Chris M", "basis": "accepted"}, "surname": {"value": "Hahnle", "basis": "accepted"}, "death_year": {"value": 1960, "basis": "accepted"}})
    say(rq and rq[0]["data"]["p_deathYY"] == "1960" and rq[0]["data"]["firstName"] == "Chris" and rq[0]["data"]["middleName"] == "M", f"a search step's death year narrows the search: {rq}")
    say(va_graves.requests(f(name="Noi Davidson"))[0]["data"]["middleNameOpt"] == "1", "no middle name, none asked")
    with open(os.path.join(FIXTURES, "va-gravesite-search-davidson-raymond-page1.html"), "rb") as fh: page1 = fh.read()
    say(va_graves.total(page1) == 22 and len(va_graves.results(page1)) == 10 and va_graves.narrow(va_graves.URL, page1) is None
        and va_graves.next_page(va_graves.URL, page1) == "https://gravelocator.cem.va.gov/ngl/result/1lAHS2AnK4QkAoGcnXxp7TkBqZNjNMEghZnIjXo=",
        f"a first page of ten of 22 links its next page, and 22 is within what is read: {va_graves.total(page1)}, {va_graves.next_page(va_graves.URL, page1)}")
    say(va_graves.requests(f(collection="x")) == [], "no surname, nothing asked")
    with open(os.path.join(FIXTURES, "va-gravesite-search-davidson-raymond-2007.html"), "rb") as fh: body = fh.read()
    rows = va_graves.results(body)
    say(va_graves.total(body) == 2 and len(rows) == 2 and va_graves.narrow(va_graves.URL, body) is None and va_graves.next_page(va_graves.URL, body) is None, f"two decedents found, both on the page, no next page: {va_graves.total(body)}, {len(rows)}")
    say(rows and rows[1].get("name") == "DAVIDSON, RAYMOND E" and rows[1].get("birth") == "10/12/1939" and rows[1].get("death") == "01/27/2007" and rows[1].get("buried_at", "").startswith("SECTION O1 SITE 2239")
        and rows[1].get("cemetery") == "BG WILLIAM C DOYLE VET'S MEM CEM" and rows[1].get("city") == "WRIGHTSTOWN" and rows[1].get("state") == "NJ", f"the second decedent as the page writes him: {rows[1:] if rows else rows}")
    say(len(va_graves.hits(va_graves.URL, body, {"locator": "x"})) == 2 and va_graves.hits(va_graves.URL, body, {"locator": "x"})[0]["fetch"] == [], "one hit per decedent, fetching nothing: the page is the record")
    say(parse_gedcom_date("10/12/1939")["date_start"] == "1939-10-12" and parse_gedcom_date("13/12/1939")["date_start"] is None, "a month-first date is read, an impossible one is not")
    body_meta = json.dumps({"server": "ia800300.us.archive.org", "dir": "/1/items/genealogicalreco01krie", "metadata": {"identifier": "genealogicalreco01krie"}, "files": [{"name": "genealogicalreco01krie_jp2.zip"}]}).encode()
    h = ia.hit({"identifier": "genealogicalreco01krie", "doc": "genealogicalreco01krie", "title": "x", "year": 1879, "date": None, "collections": [], "page": None, "text": []}, {"q": '"Frederick Ahearn"~3', "surname": "Ahearn", "given": "Frederick", "variants": ["Ahern", "ahearn"]}, "x")
    inside = ia.follow(h["fetch"][0], body_meta, h)
    say([x.get("spelling") for x in inside] == ["Ahearn", "Ahern"] and all("inside.php" in x["url"] for x in inside) and "q=Ahern" in inside[1]["url"], f"the search inside is asked once per spelling, the surname first, a repeat spelling dropped: {[(x.get('spelling'), x['url'][-40:]) for x in inside]}")
    body_a = json.dumps({"ia": "x", "q": "Ahearn", "matches": [{"text": "Frederick Ahearn", "par": [{"page": 12}]}, {"text": "Ahearn", "par": [{"page": 40}]}]}).encode()
    body_b = json.dumps({"ia": "x", "q": "Ahern", "matches": [{"text": "Ahern", "par": [{"page": 40}]}, {"text": "Ahern", "par": [{"page": 55}]}, {"text": "Ahern", "par": [{"page": 60}]}]}).encode()
    imgs = ia.follow(inside[0], body_a, h) + ia.follow(inside[1], body_b, h)
    say(h["notes"]["pages"] == [12, 40, 55] and [x["page"] for x in imgs] == [12, 40, 55] and h["notes"].get("spellings_found") == ["Ahearn", "Ahern"], f"the pages of every spelling merged, three in all, each image once, the spellings found noted: {h['notes'].get('pages')}, {[x['page'] for x in imgs]}, {h['notes'].get('spellings_found')}")
    lent = ia.hit({"identifier": "lent", "doc": "lent", "title": "x", "year": 1900, "date": None, "collections": [], "page": None, "text": []}, {"surname": "Brant"}, "x")
    say(ia.follow(lent["fetch"][0], json.dumps({"server": "s", "dir": "/d", "metadata": {"access-restricted-item": "true"}, "files": []}).encode(), lent) == [] and lent["notes"].get("restricted") is True, "a book the Archive lends stops at its metadata, marked restricted")
    from run_step import outcome_of
    say(outcome_of([{"restricted": True}], [], ["a"]) == "none" and outcome_of([{"restricted": True}, {"restricted": False}], [], ["a"]) == "found" and outcome_of([], ["x"], []) == "error" and outcome_of([], [], ["a"]) == "none",
        "a run whose every hit is a lent book is none; one read is found; no answer at all is error")
    from connectors import loc_gov, ia_newspapers
    fq = f(collection="U.S., Newspapers.com Obituary Index, 1800s-current", name="Helen Sara Brant", **{"publication date": "27 Jan 1986", "publication place": "Boca Raton, Florida, USA"})
    lg = loc_gov.requests(fq); ian = ia_newspapers.requests(fq)
    say(lg and "q=Brant%20Helen" in lg[0]["url"] and "dates=1986%2F1986" in lg[0]["url"] and "location_state%3Aflorida" in lg[0]["url"], f"a cited obituary's fields ask loc.gov by the citation's name in the paper's year and state: {lg and lg[0]['url']}")
    say(ian and ian[0]["years"] == [1986, 1986] and "Helen%20Brant" in ian[0]["url"] and ian[0]["surname"] == "Brant" and ian[0]["given"] == "Helen Sara", f"and the Archive's newspapers within the paper's year, the citation's name split so the search inside asks the surname alone: {ian and (ian[0]['years'], ian[0]['surname'], ian[0]['url'][-60:])}")
    fts = json.dumps({"hits": {"total": {"value": 2}, "hits": [{"fields": {"identifier": ["st-joseph-herald-press-1967-02-11"], "meta_title": ["St Joseph Herald Press (1967-02-11)"], "meta_collection": ["newspaperarchive"], "filename": ["x_hocr_searchtext.txt.gz"]}, "highlight": {"text": ["Helen Brant"]}},
                                                                {"fields": {"identifier": ["boca-raton-news-1986-01-27"], "meta_title": ["Boca Raton News (1986-01-27)"], "meta_collection": ["newspaperarchive"]}, "highlight": {"text": ["Helen Ahearn"]}}]}}).encode()
    its = ia.items(fts)
    say([(i["year"], i["date"]) for i in its] == [(1967, "1967-02-11"), (1986, "1986-01-27")], f"a newspaper issue's day read from its title when the search gives no year: {[(i['year'], i['date']) for i in its]}")
    say([h["notes"]["item"] for h in ia_newspapers.hits(ian[0]["url"], fts, ian[0])] == ["boca-raton-news-1986-01-27"] if ian else False, "and only the issue of the paper's year is a hit")
    from run_step import spelling_variants
    say(spelling_variants("Ahearn", ["James J. Ahearu", "Frederick Ahern", "Helen Sara Brant Ahearn", "Alicia Ahern", "Mary Horn"]) == ["Ahearu", "Ahern"],
        f"the surname's spellings among the aliases: a slip and a variant once each, never a married name or another surname: {spelling_variants('Ahearn', ['James J. Ahearu', 'Frederick Ahern', 'Helen Sara Brant Ahearn', 'Alicia Ahern', 'Mary Horn'])}")
    from run_step import connectors_for
    class Cat2: sources = {"H05": {"connector": ""}, "H01": {"connector": "loc_gov"}, "H07": {"connector": "ia_newspapers"}, "H03": {}, "L02": {"connector": "ia_books"}}
    st = {"kind": "fetch", "locator_source_id": "H05", "sources_json": '["H01","H07","H03"]'}
    say([c.__name__.split(".")[-1] for c in connectors_for(Cat2, st)] == ["loc_gov", "ia_newspapers"], "a fetch step at a holder without a connector runs at the connectors of its row's sources")
    st2 = {"kind": "fetch", "locator_source_id": "L02", "sources_json": '["H07","L02"]'}
    say([c.__name__.split(".")[-1] for c in connectors_for(Cat2, st2)] == ["ia_books", "ia_newspapers"], "a fetch step's holder comes first, once")
    from run_step import coverage_years, step_years
    want = {"US 1756-1963": (1756, 1963), "US 1780s-1990s": (1780, 1999), "US 1950": (1950, 1950), "Global": None, "US veterans": None, "PA 1789-2013, few titles after the 1920s": (1789, 2013)}
    say(all(coverage_years(k) == v for k, v in want.items()), f"the registry's coverage years as read: {[(k, coverage_years(k)) for k in want]}")
    q = lambda **kw: {k: {"value": v, "basis": "accepted"} for k, v in kw.items()}
    say(step_years("obituary", q(death_year=2016, birth_year=1932)) == (2016, 2017) and step_years("household", q(year="1950", birth_year=1932)) == (1950, 1950)
        and step_years("name", q(birth_year=1880, death_year=1961)) == (1880, 1961) and step_years("name", q(birth_year=1880)) == (1880, 1980) and step_years("subject_record", q(surname="Brant")) is None
        and step_years("obituary", f(name="Helen Sara Brant", **{"publication date": "27 Jan 1986"})) == (1986, 1986),
        "a step's years: the death year for an obituary, the paper's year for a cited one, the census year for a household, the lifetime otherwise, none without a year")
    class Src: SOURCE = "H01"
    class Cat: sources = {"H01": {"coverage": "US 1756-1963"}, "L02": {"coverage": "Global"}}
    from run_step import outside
    say(outside(Cat, Src, "obituary", q(death_year=2016)) is not None and outside(Cat, Src, "obituary", q(death_year=1918)) is None and outside(Cat, Src, "name", q(birth_year=1932)) is None,
        "an obituary for a death after the newspapers end is not asked; one within them, or a lifetime overlapping them, is")
    return bad

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
    bad_rules = rules(); bad_files += bad_rules
    print("ok   the surname rule and the holder search: as written, a variant, one letter apart, not Grant for Brant; a template filled from the citation or the holder's page" if not bad_rules else "FAIL rules: " + "; ".join(bad_rules))
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    bad_conn = connectors_offline(); bad_files += bad_conn
    print("ok   connectors offline: a cited book asked by its title and its copies read from the Archive's answer, the search inside once per spelling, a lent book a none run; a cited obituary asked at the row's connectors in the paper's year; the gravesite locator's posted search and its results page read" if not bad_conn else "FAIL connectors: " + "; ".join(bad_conn))
    d, db = scratch(a.keep)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from treelib import archive_object
    from extract import extract
    from catalog import tier_sql
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
        ext = cx.execute("SELECT x.name, x.version, e.status, e.structured_json FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (eid,)).fetchone()
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
            try: check(ps, fail, json.loads(ext[3] or "{}")) if check.__code__.co_argcount > 2 else check(ps, fail)   # a check that reads the parsed page takes it
            except Exception as e: fails.append(f"check raised {type(e).__name__}: {e}")
        if fails: bad += 1; print(f"FAIL {name}: " + "; ".join(fails))
        else: print(f"ok   {name}: {ext[0]}@{ext[1]}, {len(ps)} persona(s)")
    ok = cx.execute("PRAGMA integrity_check").fetchone()[0]; fk = cx.execute("PRAGMA foreign_key_check").fetchall()
    if ok != "ok" or fk: bad += 1; print(f"FAIL scratch catalog: integrity {ok}, foreign keys {len(fk)}")
    cx.close()
    if a.keep: print("parsers scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    try: fails = decisions(a.keep, a.show)
    except Exception as e: fails = [f"raised {type(e).__name__}: {e}"]
    if fails: bad += 1; print("FAIL decisions on harness.ged: " + "; ".join(fails))
    else: print("ok   decisions on harness.ged: the matcher, the rule and the writers as the docs say")
    print("green" if not bad else f"{bad} failure(s)")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
