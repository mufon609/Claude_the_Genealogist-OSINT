#!/usr/bin/env python3
"""Green in one command: every tool compiles and every name it reads resolves (tests/checks/unresolved_names.py), the pure rules hold, the record forms (data/record-forms.csv) hold to their columns and their sources, the connectors read their saved answers,the evidence layer,
the research log and the audit trail are insert-only, the agent and skill files under .claude/ are the ones code writes, the small guards of tests/checks/housekeeping.py hold (the person screen's links, the commit hook, the migrations of an older catalog, the backup's bag, the active tree's file), every parser reads its saved real page as its sidecar says, and the matcher, the standing rule, the writers and the loop's tools do on
the harness tree what the scenarios say.

usage: tools/check.py [--verbose] [--show] [--keep] [--scenario NAME]

Each check runs on a scratch catalog under a temporary data root, never the owner's. The expectations are data beside
the fixtures (tests/fixtures/README.md): <stem>.expect.json beside each page for tests/checks/parsers.py, the scenarios
under tests/fixtures/scenarios/ for tests/checks/scenario.py, tests/checks/loop.py and tests/checks/imports.py, tests/fixtures/rules.json for the
pure rules here and tests/fixtures/connectors.json for the offline connector checks here; the harness tree is
tests/fixtures/harness.ged, the owner's own export cut down. A failing check prints its FAIL line with every reason and
the run ends with one line, `green: N checks` or the failure count; exit status 1 on any failure. A scenario that reads a
capture not yet made (its `awaits`: a launcher's output only the owner's browser can produce) prints a `wait` line naming the
file, is counted neither ok nor failed, and the last line says how many wait. --verbose prints the
ok line of every check too; --show prints what each reading and each scenario step did, for writing a sidecar (and the ok
lines); --keep leaves the scratch directories in place and prints their paths; --scenario NAME runs only the scenarios whose file name
has NAME in it (`104`, `a-constituent-country`), none of the other checks, and fails when none is named so. No check sends a request:
every process a check starts refuses a connection to any host but this machine, and a refusal fails the check it happened in
(tests/checks/offline.py), so a holder's answer is data planted before the run. Nothing in the harness names a person: another family's
export, pages and sidecars run through it unchanged.
"""
import argparse, contextlib, json, os, re, shutil, sqlite3, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "checks")); sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import BY, FIXTURES, scratch, tool
import housekeeping, imports, loop, offline, parsers, scenario, unresolved_names

def rules():
    """The name, place and date rules as the docs state them, and the version a reader's model id carries, on their own, against
    tests/fixtures/rules.json."""
    with open(os.path.join(FIXTURES, "rules.json"), encoding="utf-8") as fh: R = json.load(fh)
    from catalog import collection_state, date_verdict, fetch_target, holder_search, kinds_as, note, place_verdict, prefills_nothing, record_standing, same_surname, web_url
    bad = []
    for c in R["same_surname"]:
        got = same_surname(c["record"], c["tree"])
        if got != c["verdict"]: bad.append(f"same_surname({c['record']!r}, {c['tree']!r}) gave {got!r}, expected {c['verdict']!r}")
    from match import same_given
    for c in R["same_given"]:
        got = same_given(c["a"], c["b"])
        if got != c["same"]: bad.append(f"match.same_given({c['a']!r}, {c['b']!r}) gave {got!r}, expected {c['same']!r}")
    from backfill_aliases import classify
    for c in R["alias_kind"]:
        got = classify(c["written"], c["given"], c["surname"], c.get("suffix"))[0]
        if got != c["kind"]: bad.append(f"backfill_aliases.classify({c['written']!r}, {c['given']!r}, {c['surname']!r}, {c.get('suffix')!r}) gave {got!r}, expected {c['kind']!r}")
    from catalog import gedcom_name, name_words, split_name, split_persona_name
    for c in R["name_reading"]:
        got = {"split_name": list(split_name(c["name"])), "persona": list(split_persona_name(c["name"])), "words": name_words(c["name"])}
        want = {k: c[k] for k in got}
        if got != want: bad.append(f"the name {c['name']!r} read as {got!r}, expected {want!r}")
    for c in R["gedcom_name"]:
        got = gedcom_name(c["value"]); got = list(got) if got else None
        if got != c["parts"]: bad.append(f"gedcom_name({c['value']!r}) gave {got!r}, expected {c['parts']!r}")
    for c in R["holder_search"]:
        got = holder_search(c["holder"], {k: {"value": v, "basis": "citation"} for k, v in c["fields"].items()})
        if got != c["url"]: bad.append(f"holder_search({c['holder']['HolderKind']}, {c['holder']['HolderKey'][:40]!r}) gave {got!r}, expected {c['url']!r}")
    for c in R["web_url"]:
        got = web_url(c["url"]); want = c["url"] if c["href"] else None
        if got != want: bad.append(f"web_url({c['url']!r}) gave {got!r}, expected {want!r}")
    for c in R["fetch_target"]:
        got = fetch_target(c["apid"], c["url"])
        if got != c["target"]: bad.append(f"fetch_target({c['apid']!r}, {c['url']!r}) gave {got!r}, expected {c['target']!r}")
    from cards import name_verdict
    from catalog import Finding
    for c in R["name_verdict"]:
        findings = lambda k, verdict: [Finding(verdict, **f) for f in c.get(k, [])]
        got = name_verdict(findings("agree", "agrees"), findings("disagree", "disagrees"), findings("absent", "absent"))
        if got != c["verdict"]: bad.append(f"name_verdict({c}) gave {got!r}, expected {c['verdict']!r}")
    for c in R["prefills_nothing"]:
        got = prefills_nothing(c["holder"], {k: {"value": v, "basis": "citation"} for k, v in c["fields"].items()})
        if got != c["nothing"]: bad.append(f"prefills_nothing({c['holder']['HolderKind']}, {c['holder']['HolderKey'][:40]!r}, {c['fields']!r}) gave {got!r}, expected {c['nothing']!r}")
    for kind in R["automated_kinds"]:
        if record_standing(kinds_as([kind]))[0] != "automated": bad.append(f"data/evidence-classes.csv gives {kind} no automated standing: its records would stay a hint until a person reads them")
    for c in R["place_verdict"]:
        f = place_verdict(c["record"], c["tree"]); got = (f.verdict, note(f))
        if got != (c["verdict"], c["note"]): bad.append(f"place_verdict({c['record']!r}, {c['tree']!r}) gave {got!r}, expected {(c['verdict'], c['note'])!r}")
    for c in R["place_verdict_with_record_state"]:
        f = place_verdict(c["record"], c["tree"], record_state=c["record_state"]); got = (f.verdict, note(f))
        if got != (c["verdict"], c["note"]): bad.append(f"place_verdict({c['record']!r}, {c['tree']!r}, record_state={c['record_state']!r}) gave {got!r}, expected {(c['verdict'], c['note'])!r}")
    from treelib import parse_gedcom_date
    as_read = lambda t: {k: v for k, v in zip(("start", "end", "qualifier"), (parse_gedcom_date(t)[f] for f in ("date_start", "date_end", "date_qualifier")))}
    for c in R["date_verdict"]:
        f = date_verdict(as_read(c["record"]), as_read(c["tree"])); got, want = ((f.verdict, note(f)), (c["verdict"], c["note"])) if "note" in c else (f.verdict, c["verdict"])
        if got != want: bad.append(f"date_verdict({c['record']!r}, {c['tree']!r}) gave {got!r}, expected {want!r}")
    for c in R["collection_state"]:
        got = collection_state(c["name"])
        if got != c["state"]: bad.append(f"collection_state({c['name']!r}) gave {got!r}, expected {c['state']!r}")
    from resolve_places import parse, query_variants
    for c in R["place_parse"]:
        p = parse(c["raw"]); got = {"components": p["components"], "country": p["country"], "queries": query_variants(p) if (p["components"] or p["country"]) else []}
        if got != c["parsed"]: bad.append(f"resolve_places.parse({c['raw']!r}) gave {got!r}, expected {c['parsed']!r}")
    from resolve_places import agree
    for c in R["place_names"]:
        got = agree(c["part"], c["names"])
        if got != c["agrees"]: bad.append(f"resolve_places.agree({c['part']!r}, {c['names']!r}) gave {got!r}, expected {c['agrees']!r}")
    sys.path.insert(0, os.path.join(ROOT, "app", "person"))
    from server import model_version
    for c in R["model_version"]:
        got = model_version(c["id"])
        if got != c["version"]: bad.append(f"model_version({c['id']!r}) gave {got!r}, expected {c['version']!r}")
    from forms import census_form, form_for, settles
    for c in R["census_form"]:
        f = census_form(c["collection"], c["year"]); got = f["id"] if f else None
        if got != c["form"]: bad.append(f"census_form({c['collection']!r}, {c['year']}) gave {got!r}, expected {c['form']!r}")
    for c in R["census_settles"]:
        got = settles(form_for(c["year"]))
        if got != c["settles"]: bad.append(f"settles(form_for({c['year']})) gave {got!r}, expected {c['settles']!r}")
    from footprint import expect
    for c in R["footprint_expect"]:
        got = expect(c["collection"], c["rel"], lambda y: c["alive"], None)
        if got != c["expect"]: bad.append(f"footprint.expect({c['collection']!r}, {c['rel']!r}, alive {c['alive']}) gave {got!r}, expected {c['expect']!r}")
    names = [tuple(x) for x in R["dated_names"]["names"]]
    for c in R["dated_names"]["cases"]:
        f = place_verdict(c["record"], c["tree"], dated_names=names); got = (f.verdict, note(f))
        if got != (c["verdict"], c["note"]): bad.append(f"place_verdict({c['record']!r}, {c['tree']!r}, dated_names=...) gave {got!r}, expected {(c['verdict'], c['note'])!r}")
    return bad

def connectors_offline():
    """The connectors' requests from a step's fields and their reading of saved responses, with no network: the Archive's
    title search for a cited book and the VA gravesite locator's posted search, then the newspaper connectors, the New Jersey
    death index and the Kentucky death and birth indexes. What they are asked with and read against comes from
    tests/fixtures/connectors.json and the slices it names."""
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
    def saved(name):
        with open(os.path.join(FIXTURES, name), "rb") as fh: return fh.read()
    def asked(name):
        """The URL a saved response was asked at, from its manifest."""
        with open(os.path.join(FIXTURES, name.rsplit(".", 1)[0] + ".manifest.json"), encoding="utf-8") as fh: return json.load(fh)["locator"]["value"]
    body = saved(B["fixture"]); adv = body
    say(ia.total(body) == B["total"] and rq and rq[0]["url"] == asked(B["fixture"]), f"the advanced search is asked at the URL its saved answer was asked at, and the answer's total is read: {ia.total(body)}")
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
    SI = C["search_inside"]
    rqv = ia_books.requests(f(collection=B["collection"], name=B["name"], citation=B["citation"], surname_variants=SI["variants"]))
    h = next((x for x in ia_books.hits(rqv[0]["url"], adv, rqv[0]) if x["notes"]["item"] == SI["item"]), None)
    inside = ia.follow(h["fetch"][0], saved(SI["metadata"]), h)
    say([x.get("spelling") for x in inside] == SI["spellings"] and all("inside.php" in x["url"] for x in inside) and [x["url"] for x in inside] == [asked(SI["inside"][sp]) for sp in SI["spellings"]],
        f"the search inside is asked once per spelling, the surname first, a repeat spelling dropped, each at the URL its saved answer was asked at: {[(x.get('spelling'), x['url'][-40:]) for x in inside]}")
    imgs = ia.follow(inside[0], saved(SI["inside"][SI["spellings"][0]]), h) + ia.follow(inside[1], saved(SI["inside"][SI["spellings"][1]]), h)
    say(h["notes"]["pages"] == SI["pages"] and [x["page"] for x in imgs] == SI["pages"] and h["notes"].get("spellings_found") == sorted(SI["spellings"]),
        f"the pages of every spelling merged to three, each image once, the spellings found noted: {h['notes'].get('pages')}, {[x['page'] for x in imgs]}, {h['notes'].get('spellings_found')}")
    LT = C["lent"]; rql = ia_books.requests(f(**LT["fields"]))
    lent = next((x for x in ia_books.hits(rql[0]["url"], saved(LT["fixture"]), rql[0]) if x["notes"]["item"] == LT["item"]), None)
    say(lent and ia.follow(lent["fetch"][0], saved(LT["metadata"]), lent) == [] and lent["notes"].get("restricted") is True, "a book the Archive lends stops at its metadata, marked restricted")
    from run_step import outcome_of
    say(outcome_of([{"restricted": True}], [], True) == "none" and outcome_of([{"restricted": True}, {"restricted": False}], [], True) == "found" and outcome_of([], ["x"], False) == "error" and outcome_of([], [], True) == "none",
        "a run whose every hit is a lent book is none; one read is found; no answer at all is error")
    from connectors import loc_gov, ia_newspapers
    O = C["obituary"]
    fq = f(collection=O["collection"], name=O["name"], **{"publication date": O["publication date"], "publication place": O["publication place"]})
    lg = loc_gov.requests(fq); ian = ia_newspapers.requests(fq)
    say(lg and all(x in lg[0]["url"] for x in O["loc_gov_has"]), f"a cited obituary's fields ask loc.gov by the citation's name in the paper's year and state: {lg and lg[0]['url']}")
    say(ian and ian[0]["years"] == O["years"] and O["ia_has"] in ian[0]["url"] and ian[0]["surname"] == O["surname"] and ian[0]["given"] == O["given"], f"and the Archive's newspapers within the paper's year, the citation's name split so the search inside asks the surname alone: {ian and (ian[0]['years'], ian[0]['surname'], ian[0]['url'][-60:])}")
    fts = saved(O["fixture"])
    say(asked(O["fixture"]) == ian[0]["url"] and ia.total(fts) == O["total"], f"the Archive's newspaper search is asked at the URL its saved answer was asked at, and the answer's total is read: {ian and ian[0]['url']}, {ia.total(fts)}")
    its = ia.items(fts)
    say({i["identifier"]: [i["year"], i["date"]] for i in its if i["identifier"] in O["undated"]} == O["undated"], f"a newspaper issue's day read from its title when the search gives no year: {[(i['identifier'], i['year'], i['date']) for i in its if i['identifier'] in O['undated']]}")
    say([h["notes"]["item"] for h in ia_newspapers.hits(ian[0]["url"], fts, ian[0])] == O["hit_items"] if ian else False, "and an answer holding no issue of the paper's year gives no hit, an undated one among them")
    Y = O["in_year"]
    say([h["notes"]["item"] for h in ia_newspapers.hits(ian[0]["url"], fts, {**ian[0], "years": Y["years"]})] == Y["items"], "the same answer asked for a year it holds issues of gives those issues, the one the search dated by its title among them")
    from connectors import nara_1950
    DC = C["district"]; dq = {"surname": {"value": DC["surname"], "basis": "row"}, "given": {"value": DC["given"], "basis": "row"}, "place": {"value": DC["place"], "basis": "row"}}
    say(nara_1950.place_parts(DC["place"])[1] == DC["nara_state"] and DC["nara_has"] in nara_1950.requests(dq)[0]["url"] and loc_gov.state_of(DC["place"]) == DC["loc_gov_state"] and DC["loc_gov_has"] in loc_gov.requests(dq)[0]["url"],
        f"a place in the District of Columbia is asked in it, the state names and codes the catalog's own: {nara_1950.place_parts(DC['place'])}, {loc_gov.state_of(DC['place'])}")
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
    with open(os.path.join(FIXTURES, DF["fixture"]), "rb") as fh: whole = fh.read()
    header = whole.decode().splitlines()[0]
    rq = nj.requests(f(name=DF["step_name"]))
    say(rq and rq[0]["url"] == nj.CSV_URL and rq[0]["kind"] == "text" and rq[0]["surname"] == DF["surname"] and rq[0]["record"] is False, f"the whole file is asked once, the step's own surname split from its citation's name, not itself the record: {rq}")
    say(nj.requests(f(collection="x")) == [], "no name on the step, nothing asked")
    rq0 = rq[0]; rq0["archived_sha"] = "parentsha000000000000000000000000000000000000000000000000000"
    hs = nj.hits(nj.CSV_URL, whole, rq0)
    say(len(hs) == 1 and hs[0]["notes"]["rows"] == DF["rows_under"] and hs[0]["locator"]["value"] == f"{nj.CSV_URL}#surname={DF['surname']}", f"one hit, the rows under the surname out of the file, the file's own URL with the surname as its own locator: {hs}")
    fetch0 = hs[0]["fetch"][0]
    say(fetch0["derived_from"] == rq0["archived_sha"] and fetch0["record"] is True and "bytes" in fetch0, f"the derivative carries its parent's sha and is itself the record, computed, not fetched: {fetch0}")
    deriv_text = fetch0["bytes"].decode()
    say(deriv_text.splitlines()[0] == header and len(deriv_text.splitlines()) == DF["rows_under"] + 1 and DF["not_in_derivative"] not in deriv_text.lower(), f"the derivative carries the header and only the surname's rows, nobody else's: {deriv_text}")
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
    same_sha, same_new = ao(cx2, fetch0["bytes"], mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=hs[0]["locator"]["value"], retrieved_by=BY, terms="public-domain", cost="free",
                            trust_tier="T2", derived_from=parent_sha)
    say(same_sha == d_sha and not same_new, "re-deriving the same surname's rows from the same parent lands on the same artifact, archived once")
    hs_other = nj.hits(nj.CSV_URL, whole, {"surname": DF["other_surname"], "archived_sha": parent_sha})
    other_sha, _ = ao(cx2, hs_other[0]["fetch"][0]["bytes"], mime="text/plain", source_id="C09", collection_id=None, locator_kind="url", locator_value=hs_other[0]["locator"]["value"], retrieved_by=BY, terms="public-domain", cost="free", trust_tier="T2", derived_from=parent_sha)
    eid2, n2 = ext_fn(cx2, other_sha, BY)
    say(n2.get("personas") == hs_other[0]["notes"]["rows"] == DF["other_rows"] and other_sha != d_sha and eid2 != eid, f"a different surname's derivative, a different artifact, its own extraction: {n2}")
    say(cx2.execute("SELECT superseded_by FROM extraction WHERE id=?", (eid,)).fetchone()[0] is None, "extracting another surname's derivative never supersedes this one's own extraction")
    ok2 = cx2.execute("PRAGMA integrity_check").fetchone()[0]; fk2 = cx2.execute("PRAGMA foreign_key_check").fetchall()
    say(ok2 == "ok" and not fk2, f"scratch catalog: integrity {ok2}, foreign keys {len(fk2)}")
    cx2.close(); shutil.rmtree(d, ignore_errors=True)
    from connectors import ky_vital_index as ky
    K = C["ky_index"]; KD, KB = K["death"], K["birth"]
    q = lambda d, **kw: {**{k: {"value": d[k], "basis": "accepted"} for k in ("given", "surname", "year", "state", "birth_year")}, **{k: {"value": v, "basis": "accepted"} for k, v in kw.items()}}
    rq = ky.requests(q(KD))
    say(len(rq) == 1 and rq[0]["url"] == KD["url"] and rq[0]["kind"] == "text" and rq[0]["record"] is False and rq[0]["index"] == "death" and rq[0]["surnames"] == [KD["surname"]],
        f"a Kentucky death search with an accepted year asks that year's death file whole, once, not itself the record: {rq}")
    claim = {**q(KD), "year": {"value": KD["year"], "basis": "claim"}}
    say([r["year"] for r in ky.requests(claim)] == KD["claim_years"], f"a claimed year is asked with the year either side: {[r['year'] for r in ky.requests(claim)]}")
    rb = ky.requests(q(KB))
    say(len(rb) == 1 and rb[0]["url"] == KB["url"] and rb[0]["index"] == "birth", f"a year equal to the birth year is the birth row's, asked of the birth file: {rb}")
    say(ky.requests({**q(KD), "state": {"value": K["other_state"], "basis": "accepted"}}) == [] and "Kentucky" in (ky.wants({**q(KD), "state": {"value": K["other_state"], "basis": "accepted"}}) or ""),
        "a death in another state asks nothing, the note saying a Kentucky death is wanted")
    out_yr = {**q(KD), "year": {"value": K["outside_year"], "basis": "accepted"}}
    say(ky.requests(out_yr) == [] and "1911-1989" in (ky.wants(out_yr) or ""), f"a year the index does not cover asks nothing: {ky.wants(out_yr)}")
    CI = K["citation"]; cite = {k: {"value": v, "basis": "citation"} for k, v in CI.items()}; bare = {k: v for k, v in cite.items() if k != "year"}
    say(ky.requests(bare) == [] and "year" in (ky.wants(bare) or ""), f"a citation of the death index that names no year asks nothing, the year wanted: {ky.wants(bare)}")
    rc = ky.requests(cite)
    say(len(rc) == 1 and rc[0]["url"] == KD["url"] and rc[0]["surnames"] == [KD["surname"]] and rc[0]["given"] == KD["given"].split()[0], f"a citation naming its year asks that year's file for the citation's own name: {rc}")
    other = {k: {"value": v, "basis": "citation"} for k, v in K["other_citation"].items()}
    say(ky.requests(other) == [] and "citation of the Kentucky" in (ky.wants(other) or ""), "a citation of another collection on the same row asks nothing here")
    married = {"variants": {"value": K["married"]["variants"], "basis": "claim"}}
    say(ky.requests({**q(KD), **married})[0]["surnames"] == K["married"]["death_surnames"] and ky.requests({**q(KB), **married})[0]["surnames"] == [KB["surname"]],
        "a death is asked under the other surnames the person's names carry, a birth under the birth surname alone")
    say(answers("ky_vital_index", "death record:") and answers("ky_vital_index", "birth record:1915") and not answers("ky_vital_index", "marriage record:x"), "the Kentucky indexes answer the death and birth rows, never a marriage search")
    with open(os.path.join(FIXTURES, K["death_fixture"]), "rb") as fh: dbody = fh.read()
    with open(os.path.join(FIXTURES, K["birth_fixture"]), "rb") as fh: bbody = fh.read()
    rq0 = {**rq[0], "archived_sha": "parentsha000000000000000000000000000000000000000000000000000"}
    hs = ky.hits(rq0["url"], dbody, rq0)
    kept = [r["given"] for r in ky.rows(hs[0]["fetch"][0]["bytes"])] if hs else []
    say(len(hs) == 1 and kept == KD["kept"] and hs[0]["fetch"][0]["record"] is True and hs[0]["fetch"][0]["derived_from"] == rq0["archived_sha"] and hs[0]["locator"]["value"].startswith(KD["url"] + "#surname="),
        f"one hit, the rows under the surname whose given name shares the step's first letter, the year file's sha as parent: {kept}")
    say(hs and all(line + b"\r\n" in dbody for line in hs[0]["fetch"][0]["bytes"].split(b"\r\n") if line), "the derivative's lines are the file's own, carriage control and all")
    say(len(ky.under(dbody, "death", KD["surname"])) == KD["kept_without_given"], "a step with no given name keeps every row under the surname")
    say(ky.hits(rq0["url"], dbody, {**rq0, "surnames": [K["absent_surname"]]}) == [], "a surname with no row in the year gives no hit")
    rb0 = {**rb[0], "archived_sha": rq0["archived_sha"]}
    hb = ky.hits(rb0["url"], bbody, rb0)
    say(hb and [r["given"] for r in ky.rows(hb[0]["fetch"][0]["bytes"])] == KB["kept"] and ky.hits(rb0["url"], dbody, rb0) == [], "the birth file's rows read by the birth layout; a death file gives a birth search nothing")
    d, db = scratch(False)
    cx2 = sqlite3.connect(db); cx2.execute("PRAGMA foreign_keys=ON"); cx2.row_factory = sqlite3.Row
    with open(os.path.join(FIXTURES, K["death_page_fixture"]), "rb") as fh: whole = fh.read()
    w_sha, _ = ao(cx2, whole, mime="text/plain", source_id="C06", collection_id=None, locator_kind="url", locator_value=KD["url"], retrieved_by=BY, terms="Public Domain Mark 1.0", cost="free", trust_tier="T2")
    _, nw = ext_fn(cx2, w_sha, BY)
    say(nw.get("failed") and "whole file" in nw["failed"], f"a year file with its headings, read on its own, is refused: {nw}")
    k_sha, _ = ao(cx2, hs[0]["fetch"][0]["bytes"], mime="text/plain", source_id="C06", collection_id=None, locator_kind="url", locator_value=hs[0]["locator"]["value"], retrieved_by=BY,
                  terms="Public Domain Mark 1.0", cost="free", trust_tier="T2", notes=json.dumps(hs[0]["notes"]), derived_from=w_sha)
    keid, nk = ext_fn(cx2, k_sha, BY)
    say(nk.get("personas") == len(KD["kept"]) and cx2.execute("SELECT x.name FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (keid,)).fetchone()[0] == "ky-death-index",
        f"the derivative read by the death index's reader, one persona per row: {nk}")
    ok2 = cx2.execute("PRAGMA integrity_check").fetchone()[0]; fk2 = cx2.execute("PRAGMA foreign_key_check").fetchall()
    say(ok2 == "ok" and not fk2, f"scratch catalog: integrity {ok2}, foreign keys {len(fk2)}")
    cx2.close(); shutil.rmtree(d, ignore_errors=True)
    return bad

def save_page_kinds():
    """The browser script recognises every saved page the parsers read: the markers in tools/save_page.js's own table, read out
    of the file and run on each fixture page, name the kind its parser family expects (a FamilySearch results page or record,
    a Find a Grave memorial or search, an AAD page); the gravesite locator's pages are a connector's, never saved by the script."""
    with open(os.path.join(ROOT, "tools", "save_page.js"), encoding="utf-8") as fh: js = fh.read()
    table = {m.group(1): [p.replace("\\/", "/") for p in re.findall(r"/((?:\\.|[^/\\\n])+)/\.test\(h\)", m.group(2))] for m in re.finditer(r'^\s*"([a-z-]+)": h => (.+?),?$', js, re.M)}
    expect = [("familysearch-search-", "fs-search"), ("familysearch-massachusetts-marriage-search-", "fs-search"), ("familysearch-", "fs-record"), ("findagrave-memorial-", "fg-memorial"),
              ("findagrave-search-", "fg-search"), ("aad-", "aad")]
    bad = []
    for f in sorted(os.listdir(FIXTURES)):
        want = next((k for prefix, k in expect if f.startswith(prefix)), None)
        if not f.endswith(".html") or not want: continue
        with open(os.path.join(FIXTURES, f), encoding="utf-8", errors="replace") as fh: text = fh.read()
        got = next((k for k, ps in table.items() if any(re.search(p, text) for p in ps)), None)
        if got != want: bad.append(f"{f}: tools/save_page.js says {got}, the parser family is {want}")
    if sorted(table) != sorted({k for _, k in expect}): bad.append(f"the script's kinds {sorted(table)} are not the fixtures' {sorted({k for _, k in expect})}")
    return bad

def save_page_key():
    """The browser script writes the key the attach reads: the saved-from line and the key comment, built from the literals of
    tools/save_page.js's own `head` with a key and without one over a real saved page's own URL and document, are read back by the
    readers (fetches.saved_from, attach.saved_steps);
    the script takes the call's arguments in the order tools/fetches.py prints them (page_call), and ends in the call that the
    list's call replaces."""
    import tempfile
    from attach import saved_steps
    from fetches import page_call, saved_from
    with open(os.path.join(ROOT, "tools", "save_page.js"), encoding="utf-8") as fh: js = fh.read()
    m = re.search(r'const head = \(\) => "(.*?)" \+ location\.href \+ "(.*?)" \+ \(key \? "(.*?)" \+ key \+ "(.*?)" : ""\);', js)
    if not m: return ["the script's head() is not the saved-from line and the key comment this check reads"]
    lit = lambda s: s.encode().decode("unicode_escape")                      # the \n of a JavaScript literal
    page = os.path.join(FIXTURES, "familysearch-search-kentucky-deaths-bell-lena-howard.html")
    url, ids = saved_from(page), ["01M3ZTFSBTNXKPBMNT654TWQAF", "01M3ZTFSBTNXKPBMNT654TWQAG"]
    with open(page, encoding="utf-8") as fh: doc = fh.read().partition("\n")[2]   # the page below its own saved-from line
    plain = lit(m.group(1)) + url + lit(m.group(2)); keyed = plain + lit(m.group(3)) + ",".join(ids) + lit(m.group(4))
    bad = []
    for label, head, steps in (("with a key", keyed, ids), ("without one", plain, [])):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh: fh.write(head + doc); path = fh.name
        try:
            if saved_from(path) != url: bad.append(f"the saved-from line {label} is not read back as the page's URL")
        finally: os.remove(path)
        if saved_steps(head + doc) != steps: bad.append(f"the page saved {label} names {saved_steps(head)}, expected {steps}")
    if not re.search(r"\(async function \(name, force, key\) \{", js): bad.append("the script does not take (name, force, key), the order page_call prints")
    if not js.rstrip().endswith('})("FILENAME.html")'): bad.append('the script does not end in the call ("FILENAME.html") that the list\'s call replaces')
    for holder, force in (("D03", "false"), ("H05", "true")):
        got = page_call({"save_as": "a.html", "holder_id": holder, "serves": ["X", "Y"]})
        if got != f'("a.html", {force}, "X,Y")': bad.append(f"page_call for holder {holder} gave {got}")
    return bad

INSERT_ONLY = {"artifact": None, "artifact_locator": None, "tombstone": None, "extractor": None, "extraction": "superseded_by", "persona": None,
               "persona_fact": None, "persona_relation": None, "same_record": None, "household": "superseded_by", "household_member": None,
               "search_log": "superseded_by", "task_run": None, "audit_log": None}   # table: its write-once column

def insert_only():
    """The evidence, the research log and the audit trail are insert-only (CLAUDE.md hard rule 2, schema/sqlite_extras.sql): on a
    scratch catalog holding three real records read into personas, facts and a relation, three census households the household
    script grouped from four real census pages, a run logged on each record with its audit row, a
    locator, a tombstone, the owner's word keeping two apart and a task run that got no answer, an UPDATE of each column of every table in INSERT_ONLY and a
    DELETE of its row are each refused with the trigger's own words, so a dropped trigger, or a column a trigger leaves out,
    turns this red; a write-once column is refused set from empty to empty, allowed from empty to a value once, then refused to
    another value and back to empty. The rows are all still there afterwards."""
    from treelib import archive_object, now, ulid
    from extract import extract
    from households import regroup
    from log_search import log
    from tombstone import tombstone
    d, db = scratch(False); bad = []
    try:
        cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
        shas = []
        for name in ("va-gravesite-search-davidson-raymond-2007", "va-gravesite-search-davidson-noi", "va-gravesite-search-davidson-raymond-e"):
            with open(os.path.join(FIXTURES, name + ".html"), "rb") as fh: data = fh.read()
            sha, _ = archive_object(cx, data, mime="text/html", source_id="E03", collection_id=None, locator_kind="file", locator_value=name + ".html", retrieved_by=BY, terms=None, cost="free", trust_tier=None)
            extract(cx, sha, BY); shas.append(sha)
        for name in ("familysearch-census-1925-KS4R-RTQ", "familysearch-census-1925-KS4R-RTM", "familysearch-census-1900-M3QL-XYW", "familysearch-census-1900-M9HX-SWP"):   # three households: the 1925 pages of one run, and two 1900 record pages
            with open(os.path.join(FIXTURES, name + ".html"), "rb") as fh: data = fh.read()
            sha, _ = archive_object(cx, data, mime="text/html", source_id="D03", collection_id=None, locator_kind="file", locator_value=name + ".html", retrieved_by=BY, terms=None, cost="free", trust_tier=None)
            extract(cx, sha, BY)
        regroup(cx, BY)
        ts = now(); tid = ulid()
        cx.execute("INSERT INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (shas[0], "url", "https://gravelocator.cem.va.gov/ngl/#lastName=Davidson&firstName=Raymond&deathYear=2007"))
        tombstone(cx, shas[1], "check: a tombstone row to try", BY)
        cx.execute("INSERT INTO tree (id,slug,name,created_at,updated_at) VALUES (?,?,?,?,?)", (tid, "check", "the check's tree", ts, ts))
        cx.execute("INSERT INTO same_record (id,tree_id,a_sha256,b_sha256,same,basis,decided_by,decided_at) VALUES (?,?,?,?,?,?,?,?)", (ulid(), tid, shas[0], shas[1], False, "owner", BY, ts))
        for sha in shas: log(cx, tid, BY, source_id="E03", outcome="found", artifacts=[sha], query={"surname": {"value": "Davidson", "basis": "accepted"}})
        cx.execute("""INSERT INTO task_run (id,tree_id,task_kind,holder_id,plan_step_ids_json,task_json,task_text_sha256,model,effort,started_at,launched_by,duration_ms,ended,outcome,differs,note)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (ulid(), tid, "fetch", "E03", "[]", "{}", "0" * 64, "check", "low", ts, BY, 0, "timeout", "no_answer", False, "check: a task_run row to try"))
        cx.commit()
        before = {t: cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in INSERT_ONLY}
        for table, once in INSERT_ONLY.items():
            rows = [r[0] for r in cx.execute(f"SELECT rowid FROM {table} ORDER BY rowid")]
            if not rows: bad.append(f"{table} holds no row to try"); continue
            for col in [r[1] for r in cx.execute(f"PRAGMA table_info({table})") if r[1] != once]:
                bad += _refused(cx, f"UPDATE {table} SET {col}={col} WHERE rowid=?", (rows[0],), "immutable")
            bad += _refused(cx, f"DELETE FROM {table} WHERE rowid=?", (rows[0],), "never deleted")
            if not once: continue
            ids = [r[0] for r in cx.execute(f"SELECT id FROM {table} ORDER BY rowid")]
            if len(ids) < 3: bad.append(f"{table} holds {len(ids)} row(s), three wanted to try its write-once {once}"); continue
            bad += _refused(cx, f"UPDATE {table} SET {once}={once} WHERE id=?", (ids[0],), "written once")
            try: cx.execute(f"UPDATE {table} SET {once}=? WHERE id=?", (ids[1], ids[0]))
            except sqlite3.DatabaseError as e: bad.append(f"{table}.{once} set from empty was refused: {e}"); cx.rollback(); continue
            bad += _refused(cx, f"UPDATE {table} SET {once}=? WHERE id=?", (ids[2], ids[0]), "written once", keep=True)
            bad += _refused(cx, f"UPDATE {table} SET {once}=NULL WHERE id=?", (ids[0],), "written once", keep=True)
            cx.rollback()
        after = {t: cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
        if after != before: bad.append(f"rows changed: {before} then {after}")
        cx.close()
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

def _refused(cx, sql, args, says, keep=False):
    """[] when the statement is refused by an insert-only trigger saying `says`, else what happened. The transaction is rolled
    back after, unless keep: a write-once column's allowed write stands for the statements tried after it."""
    out = []
    try: cx.execute(sql, args); out.append(f"{sql} was allowed")
    except sqlite3.DatabaseError as e:
        if says not in str(e): out.append(f"{sql} was refused, but not by its trigger: {e}")
    if not keep: cx.rollback()
    return out

def data_root():
    """The data root's paths, on fresh scratch catalogs: a tool run with DATA_ROOT set and no --db opens the catalog under DATA_ROOT
    (treelib.DB), never the owner's; a --db outside DATA_ROOT is refused, by a tool that opens a catalog and by tools/initdb.py
    that makes one, so no scratch catalog archives into another data root; and collect run with no --folder takes the pages
    saved in <DATA_ROOT>/downloads/, never the download folder of the user's home (a home of the check's own, its Downloads named
    as the user's download directory, holding a real saved page of its own)."""
    d, db = scratch(False); other = tempfile.mkdtemp(prefix="tree-check-other-"); bad = []
    env = {**os.environ, "DATA_ROOT": d}
    try:
        subprocess.run([sys.executable, tool("tree.py"), "--db", db, "create", "scratch-default", "--name", "the scratch catalog"], capture_output=True, text=True, check=True, env=env)
        r = subprocess.run([sys.executable, tool("tree.py"), "list"], capture_output=True, text=True, env=env)
        if r.returncode or "scratch-default" not in r.stdout: bad.append(f"tools/tree.py list without --db did not open {db}: {r.stdout.strip() or r.stderr.strip()}")
        odb = os.path.join(other, "catalog", "tree.db")
        r = subprocess.run([sys.executable, tool("initdb.py"), "--db", odb], capture_output=True, text=True, env=env)
        if not r.returncode or "outside the data root" not in r.stderr or os.path.exists(odb): bad.append(f"tools/initdb.py made a catalog outside the data root: {r.stdout.strip() or r.stderr.strip()}")
        shutil.copy(db, os.path.join(other, "tree.db"))
        r = subprocess.run([sys.executable, tool("tree.py"), "--db", os.path.join(other, "tree.db"), "list"], capture_output=True, text=True, env=env)
        if not r.returncode or "outside the data root" not in r.stderr: bad.append(f"tools/tree.py opened a --db outside the data root: {r.stdout.strip() or r.stderr.strip()}")
        page = "findagrave-memorial-143847338.html"; home = os.path.join(other, "home")
        os.makedirs(os.path.join(home, ".config")); os.makedirs(os.path.join(home, "Downloads")); os.makedirs(os.path.join(d, "downloads"), exist_ok=True)
        with open(os.path.join(home, ".config", "user-dirs.dirs"), "w", encoding="utf-8") as fh: fh.write('XDG_DOWNLOAD_DIR="$HOME/Downloads"\n')
        for where in (os.path.join(home, "Downloads"), os.path.join(d, "downloads")): shutil.copy(os.path.join(FIXTURES, page), where)
        r = subprocess.run([sys.executable, tool("fetches.py"), "collect", "--tree", "scratch-default", "--by", BY], capture_output=True, text=True, env={**env, "HOME": home, "XDG_CONFIG_HOME": os.path.join(home, ".config")})
        if r.returncode: bad.append(f"tools/fetches.py collect failed: {r.stdout.strip()} {r.stderr.strip()}")
        if os.path.exists(os.path.join(d, "downloads", page)) or not os.path.exists(os.path.join(d, "inbox", page)): bad.append(f"collect did not take the page saved in {d}/downloads into the inbox: {r.stdout.strip()}")
        if not os.path.exists(os.path.join(home, "Downloads", page)): bad.append("collect took a page from the home's own download folder")
    finally: shutil.rmtree(d, ignore_errors=True); shutil.rmtree(other, ignore_errors=True)
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

def registry_connectors():
    """Every Connector value in data/data-sources.csv names a module under tools/connectors/ (what connectors.load imports): a
    source whose value names none would raise in the plan and the runner on any step its row puts that source on."""
    import csv, importlib.util
    def built(name):
        try: return importlib.util.find_spec(f"connectors.{name}") is not None
        except ImportError: return False
    with open(os.path.join(ROOT, "data", "data-sources.csv"), newline="", encoding="utf-8") as fh: rows = list(csv.DictReader(fh))
    return [f"{r['ID']}'s Connector {r['Connector']!r} is no module under tools/connectors/" for r in rows if r["Connector"] and not built(r["Connector"])]

def state_writes():
    """The state kept beside a catalog is written whole: a write that fails in the middle (here a value JSON cannot hold) leaves
    the file as it was, readable, and no file of the write's own beside it."""
    import shutil, tempfile, turn
    d = tempfile.mkdtemp(prefix="tree-state-"); db = os.path.join(d, "tree.db"); bad = []
    kept = [{"tree_id": "t", "person_id": "p", "person": "a person", "since": "2026-01-01T00:00:00Z", "steps": ["s"]}]
    try:
        turn.write_state(db, kept)
        try: turn.write_state(db, [{**kept[0], "steps": {"s"}}])
        except TypeError: pass
        try: got = turn.read_state(db)
        except ValueError as e: got = f"unreadable: {e}"
        if got != kept: bad.append(f"after a write that failed the state reads {got!r}, expected the state before it")
        if os.listdir(d) != [os.path.basename(turn.state_path(db))]: bad.append(f"the write left {sorted(os.listdir(d))} beside the catalog")
    finally: shutil.rmtree(d, ignore_errors=True)
    return bad

def record_forms():
    """data/record-forms.csv held to its own columns (forms.COLUMNS): one form per row, its id unique, its kind a kind of
    data/evidence-classes.csv, its jurisdiction the United States or a state data/jurisdictions.csv gives a state census, its
    years four digits in order and shared with no other form of its kind and jurisdiction, who it names, its locators and the
    ones that make one page and how it bounds a household each in forms' own words, the page's locators among its own, the
    locators read as an entry's line given exactly where a household is a run of lines (the copy's own line only on a form
    whose locators have a line), what it states given, and every row a source, each an https address. Every federal census year from 1790 to 1950 has a form, and
    so does every state census year data/jurisdictions.csv names."""
    import csv, forms
    from catalog import evidence_table, jurisdictions
    try:
        with open(forms.PATH, newline="", encoding="utf-8") as fh: rows = list(csv.reader(fh))
    except OSError as e: return [f"data/record-forms.csv cannot be read: {e}"]
    if not rows or rows[0] != forms.COLUMNS: return [f"data/record-forms.csv's header is {rows[0] if rows else []}, its columns are {forms.COLUMNS}"]
    bad, ids, held = [], set(), {}
    state_census = jurisdictions()["state_census"]
    for n, cells in enumerate(rows[1:], 2):
        if len(cells) != len(forms.COLUMNS): bad.append(f"line {n}: {len(cells)} cells for {len(forms.COLUMNS)} columns"); continue
        raw = dict(zip(forms.COLUMNS, cells)); f = forms.read_row(raw); at = f"line {n} ({f['id'] or 'no id'})"
        say = lambda ok, why: None if ok else bad.append(f"{at}: {why}")
        say(f["id"] and f["id"] not in ids, "an id, unique in the file"); ids.add(f["id"])
        say(f["kind"] in evidence_table(), f"kind {f['kind']!r} is no kind of data/evidence-classes.csv")
        say(f["jurisdiction"] == "united states" or f["jurisdiction"] in state_census, f"jurisdiction {f['jurisdiction']!r} is neither the United States nor a state data/jurisdictions.csv gives a state census")
        years = [y.strip() for y in raw["years"].split(";")]
        say(all(re.fullmatch(r"\d{4}", y) for y in years) and f["years"] == sorted(set(f["years"])), f"years {raw['years']!r} are not four-digit years in order")
        for y in f["years"]:
            other = held.setdefault((f["kind"], f["jurisdiction"], y), f["id"])
            say(other == f["id"], f"{y} is already {other}'s")
        say(f["names"] in forms.NAMES, f"names {f['names']!r} is none of {forms.NAMES}")
        say(not (f["names"] == "head" and f["relationship"]), "a form that names the head alone states no relationship to the head")
        say(f["states"], "what the form states, in its own words")
        say(f["locators"] and set(f["locators"]) <= set(forms.LOCATORS), f"locators {f['locators']} not all of {forms.LOCATORS}")
        say(f["page"] and set(f["page"]) <= set(f["locators"]), f"the page's locators {f['page']} are not all the form's own")
        say(f["household"] and set(f["household"]) <= set(forms.HOUSEHOLD), f"household {f['household']} not all of {forms.HOUSEHOLD}")
        runs = bool(set(f["household"]) & set(forms.RUNS))
        say(set(f["lines"]) <= set(forms.LINES) and bool(f["lines"]) == runs, f"lines {f['lines']}: the locators read as an entry's line, of {forms.LINES}, given exactly where a household is a run of lines ({' or '.join(forms.RUNS)})")
        say("line" not in f["lines"] or "line" in f["locators"], "lines reads the copy's line on a form whose locators have no line")
        say(f["source"] and all(s.startswith("https://") and " " not in s for s in f["source"]), f"source {raw['source']!r}: every row cites its sources, each an https address")
    have = lambda j, y: ("census household", j, y) in held
    bad += [f"no form of the federal census of {y}" for y in range(1790, 1951, 10) if not have("united states", y)]
    bad += [f"no form of the {j} state census of {y}, a year data/jurisdictions.csv names" for j, (years, _) in state_census.items() for y in years if not have(j, y)]
    return bad

def rule_kinds():
    """The kinds of data/evidence-classes.csv the standing rule names in code (tools/conclude.py: the census, ground only on a form
    that names every member, the register entry dated with the parents, the obituary that identifies through its survivors): a name no
    kind of the file carries is named, since the rule's test on it would never meet a record."""
    from catalog import evidence_table
    from conclude import CENSUS, DATED_WITH_PARENTS, NAMED_SURVIVORS
    named = {"CENSUS": CENSUS, "DATED_WITH_PARENTS": DATED_WITH_PARENTS, "NAMED_SURVIVORS": NAMED_SURVIVORS}
    return [f"conclude.{n} names {k!r}, no kind of data/evidence-classes.csv" for n, k in named.items() if k not in evidence_table()]

def claude_files():
    """The agent and skill files under .claude/ are what code writes (tools/run_task.py claude_files: the kind's one text, its
    answer's form, its tools, the session's part): a file edited by hand, or left behind when the text, the tools or the schema
    changed, differs and is named."""
    import run_task
    return [f"{path} differs from what code would write: python3 tools/run_task.py write" for path in run_task.stale_files()]

class OkLines:
    """stdout that counts the `ok` lines of the checks and prints them only when asked; every other line (a FAIL with its
    reasons, --show's detail, a kept scratch path) prints as it comes."""
    def __init__(self, out, verbose): self.out, self.verbose, self.ok, self.failed, self.waits, self.pending = out, verbose, 0, 0, 0, ""
    def write(self, text):
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            self.ok += line.startswith("ok   "); self.failed += line.startswith("FAIL"); self.waits += line.startswith("wait ")
            if self.verbose or not line.startswith("ok   "): self.out.write(line + "\n")
    def flush(self): self.out.flush()

def every_check(a):
    """The checks that are not scenarios, then every scenario: the number that failed."""
    bad = 0
    bad_files = compiles(); bad += bool(bad_files)
    print("ok   every tool and check module compiles" if not bad_files else "FAIL compile: " + "; ".join(bad_files))
    bad_names = unresolved_names.check(); bad += bool(bad_names)
    print("ok   every global name a tool, the screen's server or a check module reads is one it defines, imports or Python provides, and every name it takes from another module of the repository is one that module defines: the compiler's own reading of each function, run or not (tests/checks/unresolved_names.py)" if not bad_names else "FAIL unresolved names: " + "; ".join(bad_names))
    bad_rules = rules(); bad += bool(bad_rules)
    print("ok   the pure rules on tests/fixtures/rules.json: the surname rule, the holder search, the web addresses a file's citation may carry and the link made of one, the card's Name row from the matcher's findings, the rule's automated kinds, place_verdict's coarser, finer and dated agreement, date_verdict's bounded dates compared as their ranges and two dates that both give a month compared to the month, collection_state, a part of a place string against a candidate's names, the version a reader's model id carries, a census collection's record form, what a federal census row settles and what the footprint expects of one by its form" if not bad_rules else "FAIL rules: " + "; ".join(bad_rules))
    bad_conn = connectors_offline(); bad += bool(bad_conn)
    print("ok   connectors offline on tests/fixtures/connectors.json: a cited book asked by its title and its copies read from the Archive's answer, the search inside once per spelling, a lent book a none run; a cited obituary asked at the row's connectors in the paper's year; a place in the District of Columbia asked in it at loc.gov and the 1950 census site, by the catalog's own state names and codes; the gravesite locator's posted search and its results page read; the death index's whole file asked once and its surname's rows derived; Kentucky's death and birth indexes asked a year's file at a time, a surname's rows kept as the record and read by each index's own layout" if not bad_conn else "FAIL connectors: " + "; ".join(bad_conn))
    bad_kinds = save_page_kinds() + save_page_key(); bad += bool(bad_kinds)
    print("ok   tools/save_page.js recognises every saved fixture page as the kind its parser family reads: a FamilySearch results page (rows or no results) or record, a Find a Grave memorial or search, an AAD page; the key comment it writes under the saved-from line is the one the attach reads, and the fetch list's call carries its arguments in order" if not bad_kinds else "FAIL save_page.js: " + "; ".join(bad_kinds))
    bad_ev = insert_only(); bad += bool(bad_ev)
    print("ok   the evidence, the research log, the record of task runs and the audit trail are insert-only: an UPDATE of every column and a DELETE are refused by their trigger on " + ", ".join(INSERT_ONLY) + "; superseded_by on " + ", ".join(t for t, once in INSERT_ONLY.items() if once) + " is written once, from empty" if not bad_ev else "FAIL insert-only: " + "; ".join(bad_ev))
    bad_db = data_root(); bad += bool(bad_db)
    print("ok   the data root: a tool run with DATA_ROOT set and no --db opens the catalog under DATA_ROOT, a --db outside it is refused, and collect takes saved pages from <DATA_ROOT>/downloads/, never the home's download folder" if not bad_db else "FAIL data root: " + "; ".join(bad_db))
    bad_reg = registry_connectors(); bad += bool(bad_reg)
    print("ok   every Connector value of the source registry names a module under tools/connectors/" if not bad_reg else "FAIL registry connectors: " + "; ".join(bad_reg))
    bad_state = state_writes(); bad += bool(bad_state)
    print("ok   the state kept beside a catalog is written whole: a write that fails midway leaves the file as it was, readable, with nothing of the write's beside it" if not bad_state else "FAIL state files: " + "; ".join(bad_state))
    bad_forms = record_forms(); bad += bool(bad_forms)
    print("ok   data/record-forms.csv holds to its own columns and every row to a source: a form for every federal census year from 1790 to 1950 and every state census year data/jurisdictions.csv names, each saying who it names, what it states, its locators, which make one page, how it bounds a household and what a run of lines is read by" if not bad_forms else "FAIL record forms: " + "; ".join(bad_forms))
    bad_kinds = rule_kinds(); bad += bool(bad_kinds)
    print("ok   every kind the standing rule names in code (the census read by its form, the register entry dated with the parents, the obituary) is a kind of data/evidence-classes.csv" if not bad_kinds else "FAIL rule kinds: " + "; ".join(bad_kinds))
    bad_claude = claude_files(); bad += bool(bad_claude)
    print("ok   the agent and skill files under .claude/ are the ones code writes from the task kind's text, its answer schema and its tool list" if not bad_claude else "FAIL claude files: " + "; ".join(bad_claude))
    bad += housekeeping.check(a.keep, a.show)
    bad += parsers.check(a.keep, a.show)
    bad += scenario.check(os.path.join(scenario.SCENARIOS, "decisions"), a.keep, a.show)
    bad += loop.check(a.keep, a.show)
    bad += imports.check(a.keep, a.show)
    return bad

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--show", action="store_true"); ap.add_argument("--keep", action="store_true"); ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--scenario", metavar="NAME", help="only the scenarios whose file name has NAME in it"); a = ap.parse_args()
    if a.scenario and not scenario.named(a.scenario): sys.exit(f"no scenario file under tests/fixtures/scenarios/ has {a.scenario!r} in its name")
    bad = 0; lines = OkLines(sys.stdout, a.verbose or a.show); offline.start()
    with contextlib.redirect_stdout(lines):
        if a.scenario: bad += scenario.check(os.path.join(scenario.SCENARIOS, "decisions"), a.keep, a.show, a.scenario) + loop.check(a.keep, a.show, a.scenario) + imports.check(a.keep, a.show, a.scenario)
        else: bad += every_check(a)
        bad_net = offline.words(offline.sent()); bad += bool(bad_net)
        print("ok   no check sent a request: every process a check starts refused any connection to a host but this machine, and none tried" if not bad_net else "FAIL network: " + "; ".join(bad_net))
    waits = f"; {lines.waits} scenario(s) not run, awaiting a capture" if lines.waits else ""
    print((f"green: {lines.ok} checks" if not bad else f"{bad} failure(s) of {lines.ok + lines.failed} checks") + waits)
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
