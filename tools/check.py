#!/usr/bin/env python3
"""Green in one command: every tool compiles, the pure rules hold, the connectors read their saved answers, every parser
reads its saved real page as its sidecar says, and the matcher, the standing rule, the writers and the loop's tools do on
the harness tree what the scenarios say.

usage: tools/check.py [--show] [--keep]

Each check runs on a scratch catalog under a temporary data root, never the owner's. The expectations are data beside
the fixtures (tests/fixtures/README.md): <stem>.expect.json beside each page for tests/checks/parsers.py, the scenarios
under tests/fixtures/scenarios/ for tests/checks/scenario.py and tests/checks/loop.py, tests/fixtures/rules.json for the
pure rules here and tests/fixtures/connectors.json for the offline connector checks here; the harness tree is
tests/fixtures/harness.ged, the owner's own export cut down. One line per check, ok or FAIL with every reason; exit
status 1 on any failure. --show prints what each reading and each scenario step did, for writing a sidecar; --keep
leaves the scratch directories in place and prints their paths. Nothing in the harness names a person: another family's
export, pages and sidecars run through it unchanged.
"""
import argparse, json, os, shutil, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "checks")); sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import BY, FIXTURES, scratch
import loop, parsers, scenario

def rules():
    """The name and place rules as the docs state them, on their own, against tests/fixtures/rules.json."""
    with open(os.path.join(FIXTURES, "rules.json"), encoding="utf-8") as fh: R = json.load(fh)
    from catalog import collection_state, holder_search, place_verdict, same_surname
    from conclude import AUTOMATED
    bad = []
    for c in R["same_surname"]:
        got = same_surname(c["record"], c["tree"])
        if got != c["verdict"]: bad.append(f"same_surname({c['record']!r}, {c['tree']!r}) gave {got!r}, expected {c['verdict']!r}")
    for c in R["holder_search"]:
        got = holder_search(c["holder"], {k: {"value": v, "basis": "citation"} for k, v in c["fields"].items()})
        if got != c["url"]: bad.append(f"holder_search({c['holder']['HolderKind']}, {c['holder']['HolderKey'][:40]!r}) gave {got!r}, expected {c['url']!r}")
    for kind in R["automated_kinds"]:
        if kind not in AUTOMATED: bad.append(f"conclude.AUTOMATED does not name {kind}: its records would stay a hint until a person reads them")
    for c in R["place_verdict"]:
        got = place_verdict(c["record"], c["tree"])
        if got != (c["verdict"], c["note"]): bad.append(f"place_verdict({c['record']!r}, {c['tree']!r}) gave {got!r}, expected {(c['verdict'], c['note'])!r}")
    for c in R["place_verdict_with_record_state"]:
        got = place_verdict(c["record"], c["tree"], record_state=c["record_state"])
        if got != (c["verdict"], c["note"]): bad.append(f"place_verdict({c['record']!r}, {c['tree']!r}, record_state={c['record_state']!r}) gave {got!r}, expected {(c['verdict'], c['note'])!r}")
    for c in R["collection_state"]:
        got = collection_state(c["name"])
        if got != c["state"]: bad.append(f"collection_state({c['name']!r}) gave {got!r}, expected {c['state']!r}")
    names = [tuple(x) for x in R["dated_names"]["names"]]
    for c in R["dated_names"]["cases"]:
        got = place_verdict(c["record"], c["tree"], dated_names=names)
        if got != (c["verdict"], c["note"]): bad.append(f"place_verdict({c['record']!r}, {c['tree']!r}, dated_names=...) gave {got!r}, expected {(c['verdict'], c['note'])!r}")
    return bad

def connectors_offline():
    """The connectors' requests from a step's fields and their reading of saved responses, with no network: the Archive's
    title search for a cited book and the VA gravesite locator's posted search, then the newspaper and death index
    connectors. What they are asked with and read against comes from tests/fixtures/connectors.json."""
    from connectors import ia, ia_books, va_graves
    from treelib import parse_gedcom_date
    with open(os.path.join(FIXTURES, "connectors.json"), encoding="utf-8") as fh: C = json.load(fh)
    bad = []; f = lambda **kw: {k: {"value": v, "basis": "citation"} for k, v in kw.items()}
    say = lambda ok, why: None if ok else bad.append(why)
    B = C["book"]
    rq = ia_books.requests(f(collection=B["collection"], name=B["name"], citation=B["citation"]))
    say(rq and rq[0]["url"].startswith(ia.ADVANCED) and B["title_words"] in rq[0]["url"] and rq[0]["surname"] == B["surname"] and str(rq[0]["given"]).startswith(B["given_starts"]),
        f"a Family History Books citation asks the Archive's advanced search for its title with the citation's name: {rq}")
    T = C["book_title"]
    rq2 = ia_books.requests(f(collection=T["collection"], name=T["name"], **{"book title": T["book title"]}))
    say(rq2 and rq2[0]["q"] == T["asked"], f"a book title is asked by its main title, the subtitle and Ancestry's cut tail off: {rq2 and rq2[0]['q']}")
    say(ia_books.requests(f(collection=C["book_untitled"]["collection"], name=C["book_untitled"]["name"])) == [], "a book citation naming no title asks nothing")
    st_ = f(**C["search_step"])
    say(ia_books.requests(st_) and "be-api.us.archive.org" in ia_books.requests(st_)[0]["url"], "a search step still asks the full-text search")
    with open(os.path.join(FIXTURES, B["fixture"]), "rb") as fh: body = fh.read()
    say(ia.total(body) == B["total"], f"the advanced search's total: {ia.total(body)}")
    hs = ia_books.hits(rq[0]["url"], body, rq[0]) if rq else []
    say([h["notes"]["item"] for h in hs] == B["items_in_order"], f"the copies of the cited book, in the Archive's order: {[h['notes']['item'] for h in hs]}")
    first = B["items_in_order"][0]
    say(hs and hs[0]["fetch"] == [{"url": f"https://archive.org/metadata/{first}", "kind": "json", "then": "metadata", "record": False}] and hs[0]["locator"]["value"] == f"https://archive.org/details/{first}",
        "a hit's first fetch is the item's metadata, the item's page its locator")
    say(ia_books.hits(rq2[0]["url"], body, rq2[0]) == [] if rq2 else False, "a response for another title gives no hit: every naming word of the cited title must be in the item's")
    G = C["gravesite"]
    rq = va_graves.requests(f(collection=G["collection"], name=G["name"]))
    say(rq and rq[0]["url"] == va_graves.URL and rq[0]["data"]["lastName"] == G["lastName"] and rq[0]["data"]["firstName"] == G["firstName"] and rq[0]["data"]["middleName"] == G["middleName"] and rq[0]["data"]["middleNameOpt"] == "2"
        and rq[0]["data"]["p_deathYY"] == "" and rq[0]["record"] is True and rq[0]["locator"] == G["locator"],
        f"a citation's name posts the locator's form, surname and first given name exact, the middle name's first letter as a beginning, the page the record: {rq}")
    Y = G["with_year"]
    rq = va_graves.requests({"given": {"value": Y["given"], "basis": "accepted"}, "surname": {"value": Y["surname"], "basis": "accepted"}, "death_year": {"value": Y["death_year"], "basis": "accepted"}})
    say(rq and rq[0]["data"]["p_deathYY"] == str(Y["death_year"]) and rq[0]["data"]["firstName"] == Y["firstName"] and rq[0]["data"]["middleName"] == Y["middleName"], f"a search step's death year narrows the search: {rq}")
    say(va_graves.requests(f(name=G["no_middle"]["name"]))[0]["data"]["middleNameOpt"] == "1", "no middle name, none asked")
    P1 = G["page1"]
    with open(os.path.join(FIXTURES, P1["fixture"]), "rb") as fh: page1 = fh.read()
    say(va_graves.total(page1) == P1["total"] and len(va_graves.results(page1)) == P1["rows"] and va_graves.narrow(va_graves.URL, page1) is None and va_graves.next_page(va_graves.URL, page1) == P1["next"],
        f"a first page of {P1['rows']} of {P1['total']} links its next page, and {P1['total']} is within what is read: {va_graves.total(page1)}, {va_graves.next_page(va_graves.URL, page1)}")
    say(va_graves.requests(f(collection="x")) == [], "no surname, nothing asked")
    PG = G["page"]
    with open(os.path.join(FIXTURES, PG["fixture"]), "rb") as fh: body = fh.read()
    rows = va_graves.results(body)
    say(va_graves.total(body) == PG["total"] and len(rows) == PG["total"] and va_graves.narrow(va_graves.URL, body) is None and va_graves.next_page(va_graves.URL, body) is None, f"{PG['total']} decedents found, all on the page, no next page: {va_graves.total(body)}, {len(rows)}")
    S2 = PG["second"]
    say(rows and rows[1].get("name") == S2["name"] and rows[1].get("birth") == S2["birth"] and rows[1].get("death") == S2["death"] and rows[1].get("buried_at", "").startswith(S2["buried_at_starts"])
        and rows[1].get("cemetery") == S2["cemetery"] and rows[1].get("city") == S2["city"] and rows[1].get("state") == S2["state"], f"the second decedent as the page writes them: {rows[1:] if rows else rows}")
    say(len(va_graves.hits(va_graves.URL, body, {"locator": "x"})) == PG["total"] and va_graves.hits(va_graves.URL, body, {"locator": "x"})[0]["fetch"] == [], "one hit per decedent, fetching nothing: the page is the record")
    D = C["dates"]
    say(parse_gedcom_date(D["read"])["date_start"] == D["read_as"] and parse_gedcom_date(D["impossible"])["date_start"] is None, "a month-first date is read, an impossible one is not")
    SI = C["search_inside"]; item = SI["item"]
    body_meta = json.dumps({"server": "ia800300.us.archive.org", "dir": f"/1/items/{item}", "metadata": {"identifier": item}, "files": [{"name": f"{item}_jp2.zip"}]}).encode()
    h = ia.hit({"identifier": item, "doc": item, "title": "x", "year": 1879, "date": None, "collections": [], "page": None, "text": []}, {"q": SI["q"], "surname": SI["surname"], "given": SI["given"], "variants": SI["variants"]}, "x")
    inside = ia.follow(h["fetch"][0], body_meta, h)
    say([x.get("spelling") for x in inside] == SI["spellings"] and all("inside.php" in x["url"] for x in inside) and f"q={SI['spellings'][1]}" in inside[1]["url"],
        f"the search inside is asked once per spelling, the surname first, a repeat spelling dropped: {[(x.get('spelling'), x['url'][-40:]) for x in inside]}")
    bodies = [json.dumps({"ia": "x", "q": sp, "matches": [{"text": m["text"], "par": [{"page": m["page"]}]} for m in SI["matches"][sp]]}).encode() for sp in SI["spellings"]]
    imgs = ia.follow(inside[0], bodies[0], h) + ia.follow(inside[1], bodies[1], h)
    say(h["notes"]["pages"] == SI["pages"] and [x["page"] for x in imgs] == SI["pages"] and h["notes"].get("spellings_found") == SI["spellings"],
        f"the pages of every spelling merged, each image once, the spellings found noted: {h['notes'].get('pages')}, {[x['page'] for x in imgs]}, {h['notes'].get('spellings_found')}")
    lent = ia.hit({"identifier": "lent", "doc": "lent", "title": "x", "year": 1900, "date": None, "collections": [], "page": None, "text": []}, {"surname": C["lent"]["surname"]}, "x")
    say(ia.follow(lent["fetch"][0], json.dumps({"server": "s", "dir": "/d", "metadata": {"access-restricted-item": "true"}, "files": []}).encode(), lent) == [] and lent["notes"].get("restricted") is True, "a book the Archive lends stops at its metadata, marked restricted")
    from run_step import outcome_of
    say(outcome_of([{"restricted": True}], [], ["a"]) == "none" and outcome_of([{"restricted": True}, {"restricted": False}], [], ["a"]) == "found" and outcome_of([], ["x"], []) == "error" and outcome_of([], [], ["a"]) == "none",
        "a run whose every hit is a lent book is none; one read is found; no answer at all is error")
    from connectors import loc_gov, ia_newspapers
    O = C["obituary"]
    fq = f(collection=O["collection"], name=O["name"], **{"publication date": O["publication date"], "publication place": O["publication place"]})
    lg = loc_gov.requests(fq); ian = ia_newspapers.requests(fq)
    say(lg and all(x in lg[0]["url"] for x in O["loc_gov_has"]), f"a cited obituary's fields ask loc.gov by the citation's name in the paper's year and state: {lg and lg[0]['url']}")
    say(ian and ian[0]["years"] == O["years"] and O["ia_has"] in ian[0]["url"] and ian[0]["surname"] == O["surname"] and ian[0]["given"] == O["given"], f"and the Archive's newspapers within the paper's year, the citation's name split so the search inside asks the surname alone: {ian and (ian[0]['years'], ian[0]['surname'], ian[0]['url'][-60:])}")
    fts = json.dumps({"hits": {"total": {"value": len(O["issues"])}, "hits": [{"fields": {"identifier": [i["identifier"]], "meta_title": [i["title"]], "meta_collection": ["newspaperarchive"]}, "highlight": {"text": [i["highlight"]]}} for i in O["issues"]]}}).encode()
    its = ia.items(fts)
    say([(i["year"], i["date"]) for i in its] == [(i["year"], i["date"]) for i in O["issues"]], f"a newspaper issue's day read from its title when the search gives no year: {[(i['year'], i['date']) for i in its]}")
    say([h["notes"]["item"] for h in ia_newspapers.hits(ian[0]["url"], fts, ian[0])] == O["hit_items"] if ian else False, "and only the issue of the paper's year is a hit")
    from run_step import spelling_variants
    SP = C["spellings"]
    say(spelling_variants(SP["surname"], SP["aliases"]) == SP["found"], f"the surname's spellings among the aliases: a slip and a variant once each, never a married name or another surname: {spelling_variants(SP['surname'], SP['aliases'])}")
    from run_step import connectors_for
    class Cat2: sources = {"H05": {"connector": ""}, "H01": {"connector": "loc_gov"}, "H07": {"connector": "ia_newspapers"}, "H03": {}, "L02": {"connector": "ia_books"}}
    st = {"kind": "fetch", "locator_source_id": "H05", "sources_json": '["H01","H07","H03"]'}
    say([c.__name__.split(".")[-1] for c in connectors_for(Cat2, st)] == ["loc_gov", "ia_newspapers"], "a fetch step at a holder without a connector runs at the connectors of its row's sources")
    st2 = {"kind": "fetch", "locator_source_id": "L02", "sources_json": '["H07","L02"]'}
    say([c.__name__.split(".")[-1] for c in connectors_for(Cat2, st2)] == ["ia_books", "ia_newspapers"], "a fetch step's holder comes first, once")
    class Cat3: sources = {"C09": {"connector": "nj_death_index"}, "C08": {"connector": ""}}
    st3 = {"kind": "search", "row_key": C["rows"]["marriage"], "locator_source_id": None, "sources_json": '["C08","C09"]'}
    st4 = {"kind": "search", "row_key": C["rows"]["death"], "locator_source_id": None, "sources_json": '["C08","C09"]'}
    say(connectors_for(Cat3, st3) == [] and [c.__name__.split(".")[-1] for c in connectors_for(Cat3, st4)] == ["nj_death_index"],
        f"a search step is asked at a connector only on a row it answers: the New Jersey death index reads the death row, never a marriage search: {connectors_for(Cat3, st3)}, {connectors_for(Cat3, st4)}")
    from connectors import answers
    say(answers("nj_death_index", "death record:") and not answers("nj_death_index", "birth record") and answers("loc_gov", "marriage record:"), "connectors.answers: a connector without ROWS answers every row")
    from run_step import coverage_years, step_years
    want = {"US 1756-1963": (1756, 1963), "US 1780s-1990s": (1780, 1999), "US 1950": (1950, 1950), "Global": None, "US veterans": None, "PA 1789-2013, few titles after the 1920s": (1789, 2013)}
    say(all(coverage_years(k) == v for k, v in want.items()), f"the registry's coverage years as read: {[(k, coverage_years(k)) for k in want]}")
    q = lambda **kw: {k: {"value": v, "basis": "accepted"} for k, v in kw.items()}
    YR = C["years"]
    say(step_years("obituary", q(death_year=2016, birth_year=1932)) == (2016, 2017) and step_years("household", q(year="1950", birth_year=1932)) == (1950, 1950)
        and step_years("name", q(birth_year=1880, death_year=1961)) == (1880, 1961) and step_years("name", q(birth_year=1880)) == (1880, 1980) and step_years("subject_record", q(**YR["subject_record"])) is None
        and step_years("obituary", f(**YR["obituary_cited"])) == (1986, 1986),
        "a step's years: the death year for an obituary, the paper's year for a cited one, the census year for a household, the lifetime otherwise, none without a year")
    class Src: SOURCE = "H01"
    class Cat: sources = {"H01": {"coverage": "US 1756-1963"}, "L02": {"coverage": "Global"}}
    from run_step import outside
    say(outside(Cat, Src, "obituary", q(death_year=2016)) is not None and outside(Cat, Src, "obituary", q(death_year=1918)) is None and outside(Cat, Src, "name", q(birth_year=1932)) is None,
        "an obituary for a death after the newspapers end is not asked; one within them, or a lifetime overlapping them, is")
    from connectors import nj_death_index as nj
    DF = C["death_index_file"]
    whole = (DF["header"] + "\r\n" + "\r\n".join(DF["rows"]) + "\r\n").encode()
    rq = nj.requests(f(name=DF["step_name"]))
    say(rq and rq[0]["url"] == nj.CSV_URL and rq[0]["kind"] == "text" and rq[0]["surname"] == DF["surname"] and rq[0]["record"] is False, f"the whole file is asked once, the step's own surname split from its citation's name, not itself the record: {rq}")
    say(nj.requests(f(collection="x")) == [], "no name on the step, nothing asked")
    rq0 = rq[0]; rq0["archived_sha"] = "parentsha000000000000000000000000000000000000000000000000000"
    hs = nj.hits(nj.CSV_URL, whole, rq0)
    say(len(hs) == 1 and hs[0]["notes"]["rows"] == DF["rows_under"] and hs[0]["locator"]["value"] == f"{nj.CSV_URL}#surname={DF['surname']}", f"one hit, the rows under the surname out of the file, the file's own URL with the surname as its own locator: {hs}")
    fetch0 = hs[0]["fetch"][0]
    say(fetch0["derived_from"] == rq0["archived_sha"] and fetch0["record"] is True and "bytes" in fetch0, f"the derivative carries its parent's sha and is itself the record, computed, not fetched: {fetch0}")
    deriv_text = fetch0["bytes"].decode()
    say(deriv_text.splitlines()[0] == DF["header"] and len(deriv_text.splitlines()) == DF["rows_under"] + 1 and DF["not_in_derivative"] not in deriv_text.lower(), f"the derivative carries the header and only the surname's rows, nobody else's: {deriv_text}")
    say(nj.hits(nj.CSV_URL, whole, {"surname": DF["absent_surname"], "archived_sha": rq0["archived_sha"]}) == [], "a surname the file carries no row under gives no hit")
    d, db = scratch(False)
    from treelib import archive_object as ao
    from extract import extract as ext_fn
    cx2 = sqlite3.connect(db); cx2.execute("PRAGMA foreign_keys=ON"); cx2.row_factory = sqlite3.Row
    parent_sha, _ = ao(cx2, whole, mime="text/csv", source_id="C09", collection_id=None, locator_kind="url", locator_value=nj.CSV_URL, retrieved_by=BY, terms="public-domain", cost="free", trust_tier="T2", original_filename="nj-death-index-whole.csv")
    _, n_whole = ext_fn(cx2, parent_sha, BY)
    say(n_whole.get("failed") and "whole file" in n_whole["failed"], f"the whole file, read on its own, is refused: more than one surname: {n_whole}")
    d_sha, is_new = ao(cx2, fetch0["bytes"], mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=hs[0]["locator"]["value"], retrieved_by=BY, terms="public-domain", cost="free",
                       trust_tier="T2", original_filename=None, notes=json.dumps({**hs[0]["notes"], "hit": hs[0]["label"], "locator": hs[0]["locator"]}), derived_from=parent_sha)
    say(is_new and cx2.execute("SELECT derived_from FROM artifact WHERE sha256=?", (d_sha,)).fetchone()[0] == parent_sha, "the derivative's own row names its parent")
    eid, n = ext_fn(cx2, d_sha, BY)
    say(n.get("personas") == DF["rows_under"] and not n.get("failed"), f"one persona per row under the surname: {n}")
    ps = [dict(r) for r in cx2.execute("SELECT id, name_text, sequence FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,))]
    first = next((p for p in ps if p["name_text"] == DF["first_row_name"]), None)
    say(first is not None, f"the first row's name as written: {[p['name_text'] for p in ps]}")
    if first:
        FF = DF["first_row_facts"]
        facts = {(t, v, dt, pl) for t, v, dt, pl in cx2.execute("SELECT fact_type, value_text, date_text, ps.raw FROM persona_fact pf LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE persona_id=?", (first["id"],))}
        say(("Birth", None, FF["birth"][0], FF["birth"][1]) in facts, f"birth date and place as the row's own columns give them: {facts}")
        say(("Death", None, FF["death"][0], FF["death"][1]) in facts, f"death date and state as written: {facts}")
        say(any(t == "Unknown" and v == FF["file_number"] for t, v, _, _ in facts), f"the state file number under its own label: {facts}")
    yo = next((p for p in ps if p["name_text"] == DF["year_only_row_name"]), None)
    if yo:
        afacts = {(t, dt) for t, v, dt, pl in cx2.execute("SELECT fact_type, value_text, date_text, place_string_id FROM persona_fact WHERE persona_id=?", (yo["id"],))}
        say(("Birth", DF["year_only"]) in afacts, f"a birth with no month or day carries the year alone: {afacts}")
    same_sha, same_new = ao(cx2, fetch0["bytes"], mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=hs[0]["locator"]["value"], retrieved_by=BY, terms="public-domain", cost="free",
                            trust_tier="T2", derived_from=parent_sha)
    say(same_sha == d_sha and not same_new, "re-deriving the same surname's rows from the same parent lands on the same artifact, archived once")
    other = (DF["header"] + "\r\n" + "\r\n".join(DF["other_rows"]) + "\r\n").encode()
    other_sha, _ = ao(cx2, other, mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=f"{nj.CSV_URL}#surname={DF['other_surname']}", retrieved_by=BY, terms="public-domain", cost="free", trust_tier="T2", derived_from=parent_sha)
    eid2, n2 = ext_fn(cx2, other_sha, BY)
    say(n2.get("personas") == len(DF["other_rows"]) and eid2 != eid, f"a different surname's derivative, a different artifact, its own extraction: {n2}")
    say(cx2.execute("SELECT superseded_by FROM extraction WHERE id=?", (eid,)).fetchone()[0] is None, "extracting another surname's derivative never supersedes this one's own extraction")
    ok2 = cx2.execute("PRAGMA integrity_check").fetchone()[0]; fk2 = cx2.execute("PRAGMA foreign_key_check").fetchall()
    say(ok2 == "ok" and not fk2, f"scratch catalog: integrity {ok2}, foreign keys {len(fk2)}")
    cx2.close(); shutil.rmtree(d, ignore_errors=True)
    return bad

def compiles():
    """Every tool, the screen's server and the check modules compile; the first thing green means."""
    import py_compile
    bad = []
    for f in sorted(os.listdir(os.path.join(ROOT, "tools"))) + ["connectors/" + f for f in sorted(os.listdir(os.path.join(ROOT, "tools", "connectors")))] + ["../app/person/server.py"] + ["../tests/checks/" + f for f in sorted(os.listdir(os.path.join(ROOT, "tests", "checks")))]:
        if not f.endswith(".py"): continue
        try: py_compile.compile(os.path.join(ROOT, "tools", f), doraise=True)
        except py_compile.PyCompileError as e: bad.append(f"{f}: {e.msg.splitlines()[0]}")
    return bad

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--show", action="store_true"); ap.add_argument("--keep", action="store_true"); a = ap.parse_args()
    bad = 0
    bad_files = compiles(); bad += bool(bad_files)
    print("ok   every tool and check module compiles" if not bad_files else "FAIL compile: " + "; ".join(bad_files))
    bad_rules = rules(); bad += bool(bad_rules)
    print("ok   the pure rules on tests/fixtures/rules.json: the surname rule, the holder search, the rule's automated kinds, place_verdict's coarser, finer and dated agreement, collection_state" if not bad_rules else "FAIL rules: " + "; ".join(bad_rules))
    bad_conn = connectors_offline(); bad += bool(bad_conn)
    print("ok   connectors offline on tests/fixtures/connectors.json: a cited book asked by its title and its copies read from the Archive's answer, the search inside once per spelling, a lent book a none run; a cited obituary asked at the row's connectors in the paper's year; the gravesite locator's posted search and its results page read; the death index's whole file asked once and its surname's rows derived" if not bad_conn else "FAIL connectors: " + "; ".join(bad_conn))
    bad += parsers.check(a.keep, a.show)
    bad += scenario.check(os.path.join(scenario.SCENARIOS, "decisions"), a.keep, a.show)
    bad += loop.check(a.keep, a.show)
    print("green" if not bad else f"{bad} failure(s)")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
