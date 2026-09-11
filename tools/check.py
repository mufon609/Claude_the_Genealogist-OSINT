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
    ("findagrave-search-davidson-robert-1915-2004.html", "text/html", "E01", "url", "https://www.findagrave.com/memorial/search?firstname=Robert&lastname=Davidson&birthyear=1915&deathyear=2004", "findagrave-search", check_fg_search),
]

def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=os.environ)
    if r.returncode: raise RuntimeError(f"{os.path.basename(args[0])} failed:\n{r.stdout}{r.stderr}")
    return r.stdout

def decisions(keep, show):
    """The matcher, the standing rule and the decision writers on a scratch catalog holding tests/fixtures/harness.ged (the
    Ahearn household of 1940 and Helen's parents), with the 1940 page and Abram C Brant's memorial arriving as they would
    through the inbox. Returns the failures found."""
    d, db = scratch(keep)
    import treelib; treelib.DATA_ROOT = d
    from attach import attach_inbox
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
    fail(len(who) == 7, f"seven persons ingested, got {len(who)}")
    props = lambda **w: [dict(r) for r in cx.execute("SELECT * FROM proposal WHERE tree_id=? AND status=? AND kind IN ('persona_match','new_person') ORDER BY created_at, id", (tid, w.get("status", "undecided")))]
    person_of = lambda p: json.loads(p["payload_json"]).get("person_id")
    nassert = lambda: cx.execute("SELECT COUNT(*) FROM assertion WHERE tree_id=? AND status='accepted'", (tid,)).fetchone()[0]
    memberships = lambda: [(name(fm["person_id"]), fm["role"], a["status"], (json.loads(a["notes"] or "{}").get("placed")))
                           for fm in cx.execute("SELECT family_id, person_id, role FROM family_member")
                           for a in cx.execute("SELECT status, notes FROM assertion WHERE subject_kind='family_member' AND subject_id=? AND artifact_sha256 NOT IN (SELECT artifact_sha256 FROM tree_import)", (treelib.dumps([fm["family_id"], fm["person_id"], fm["role"]]),))]
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
    birth = cx.execute("""SELECT e.date_text, ps.raw FROM event e JOIN event_participant ep ON ep.event_id=e.id JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id AND a.status='accepted'
                          JOIN persona_fact pf ON pf.id=a.persona_fact_id LEFT JOIN place_string ps ON ps.id=pf.place_string_id
                          WHERE ep.person_id=? AND e.event_type='Birth' AND a.artifact_sha256='3a1a54eb4b02209c0cc43714a6c8595f40c44de4cfad5ee19d73c2a6d68e6b8e'""", (who["Frederick Michael Ahearn"],)).fetchone()
    fail(birth and birth[0] == "22 May 1907" and birth[1] == "Pennsylvania", f"the record's birthplace accepted as what the record says, on the tree's own Birth event, whose value stays: {tuple(birth) if birth else None}")   # the conflict question itself needs the tree's place resolved, which takes the geocoder
    # ---- the sister accepted: placed beside her brother with an undecided assertion, the record states the sibling, not the parents
    r = decide(cx, tid, card["Alicia Ahern"], "accepted", BY, "harness"); cx.commit(); say("sister:", r, memberships())
    fail(any(n == "Alicia Ahern" and role == "child" and st == "undecided" and placed == "sibling" for n, role, st, placed in memberships()), f"the sister's membership carries an undecided sibling placement: {memberships()}")
    # ---- the memorial arrives: T4, a card for Abram alone; the people it links wait on his decision
    shutil.copy(os.path.join(FIXTURES, "findagrave-memorial-78019650.html"), os.path.join(treelib.inbox_dir(), "findagrave-memorial-78019650.html"))
    res = attach_inbox(cx, tid, "harness", BY, ["findagrave-memorial-78019650.html"]); cx.commit(); say("attach memorial:", res)
    ps = [p for p in props() if json.loads(p["payload_json"]).get("artifact_sha256", "").startswith("576c97b3")]
    persona_name = lambda p: cx.execute("SELECT name_text FROM persona WHERE id=?", (json.loads(p["payload_json"])["persona_id"],)).fetchone()[0]
    fail(len(ps) == 1 and ps[0]["kind"] == "persona_match" and name(person_of(ps[0])) == "Abram C Brant" and persona_name(ps[0]) == "Abram C Brant",
         f"one card on the memorial, its subject as Abram; his father of nearly the same name stays a hint, the people it links wait: {[(p['kind'], persona_name(p), name(person_of(p)) if person_of(p) else None) for p in ps]}")
    subject = ps[0] if ps else None
    ok, why = rule_accepts(cx, tid, cx.execute("SELECT * FROM proposal WHERE id=?", (subject["id"],)).fetchone()); say("rule on T4:", ok, why)
    fail(not ok and ("edit" in why.lower() or "find a grave" in why.lower()), f"the rule refuses a page anyone can edit: {why}")
    # ---- Abram accepted: his daughter and wife come up as cards, his parents and siblings as new people
    r = decide(cx, tid, subject["id"], "accepted", BY, "harness"); cx.commit(); say("Abram:", r)
    after = [p for p in props() if json.loads(p["payload_json"]).get("artifact_sha256", "").startswith("576c97b3")]
    matched = sorted(name(person_of(p)) for p in after if p["kind"] == "persona_match"); new = [p for p in after if p["kind"] == "new_person"]
    say("after Abram:", matched, [persona_name(p) for p in new])
    fail({"Charlotte D Lukens", "Helen Sara Brant"} <= set(matched), f"his wife and daughter proposed once he is accepted: {matched}")
    fail(len(new) >= 3 and "Sarah D. Cassel Brant" in [persona_name(p) for p in new], f"his mother and siblings, not in the tree, proposed as new people: {[persona_name(p) for p in new]}")
    # ---- a rejection writes the proposal and nothing else; a new person accepted is created with the link the record states
    n1 = nassert(); persons1 = cx.execute("SELECT COUNT(*) FROM person WHERE tree_id=?", (tid,)).fetchone()[0]
    r = decide(cx, tid, new[-1]["id"], "rejected", BY, "harness"); cx.commit()
    fail(r.get("ok") and nassert() == n1 and cx.execute("SELECT COUNT(*) FROM person WHERE tree_id=?", (tid,)).fetchone()[0] == persons1, "rejecting a new person writes the proposal and nothing else")
    parent = next((p for p in new if persona_name(p) == "Sarah D. Cassel Brant"), None)
    if parent:
        r = decide(cx, tid, parent["id"], "accepted", BY, "harness"); cx.commit(); say("new person:", r)
        made = cx.execute("SELECT p.display_name, n.given, n.surname FROM person p JOIN person_name n ON n.person_id=p.id AND n.is_primary=1 WHERE p.id=?", (r.get("person"),)).fetchone()
        say("made:", tuple(made) if made else None)
        fail(made and "Sarah" in made[0] and made[2] == "Cassel", f"the person created with the name as written and the marked maiden name as her birth surname: {tuple(made) if made else None}")
        fail(any(m.get("role") == "child" and m.get("person") == who["Abram C Brant"] for m in r["memberships"]), f"Abram placed as the new parent's child on the record: {r['memberships']}")
    # ---- the page read again: the decided links carry to the new personas, the old cards close as superseded
    eid, n = extract(cx, "3a1a54eb4b02209c0cc43714a6c8595f40c44de4cfad5ee19d73c2a6d68e6b8e", BY); cx.commit(); say("re-read:", n)
    fail(n.get("links_carried") == 4, f"four decided links carried to the new personas: {n}")
    old = cx.execute("SELECT COUNT(*) FROM proposal WHERE tree_id=? AND status='undecided' AND json_extract(payload_json,'$.artifact_sha256')='3a1a54eb4b02209c0cc43714a6c8595f40c44de4cfad5ee19d73c2a6d68e6b8e'", (tid,)).fetchone()[0]
    fail(old == 0, f"no undecided card left on the re-read page: {old}")
    # ---- the plan is idempotent and the catalog whole
    st1 = {k: v for k, v in [(pid, plan_person(cx, tid, pid, BY)) for pid in who.values()]}; cx.commit()
    st2 = {k: v for k, v in [(pid, plan_person(cx, tid, pid, BY)) for pid in who.values()]}; cx.commit()
    fail(all(v["steps_new"] == 0 and v["steps_dropped"] == 0 and v["questions_new"] == 0 and v["questions_closed"] == 0 for v in st2.values()), f"a second plan run changes nothing: {[v for v in st2.values() if v['steps_new'] or v['steps_dropped'] or v['questions_new'] or v['questions_closed']]}")
    ok = cx.execute("PRAGMA integrity_check").fetchone()[0]; fk = cx.execute("PRAGMA foreign_key_check").fetchall()
    fail(ok == "ok" and not fk, f"scratch catalog: integrity {ok}, foreign keys {len(fk)}")
    cx.close()
    if keep: print("decisions scratch kept at", d)
    else: shutil.rmtree(d, ignore_errors=True)
    return fails

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
