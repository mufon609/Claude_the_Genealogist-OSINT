#!/usr/bin/env python3
"""Green in one command: every tool compiles, the pure rules hold, the connectors read their saved answers, the evidence layer
is insert-only, every parser reads its saved real page as its sidecar says, and the matcher, the standing rule, the writers and the loop's tools do on
the harness tree what the scenarios say.

usage: tools/check.py [--verbose] [--show] [--keep]

Each check runs on a scratch catalog under a temporary data root, never the owner's. The expectations are data beside
the fixtures (tests/fixtures/README.md): <stem>.expect.json beside each page for tests/checks/parsers.py, the scenarios
under tests/fixtures/scenarios/ for tests/checks/scenario.py, tests/checks/loop.py and tests/checks/imports.py, tests/fixtures/rules.json for the
pure rules here and tests/fixtures/connectors.json for the offline connector checks here; the harness tree is
tests/fixtures/harness.ged, the owner's own export cut down. A failing check prints its FAIL line with every reason and
the run ends with one line, `green: N checks` or the failure count; exit status 1 on any failure. --verbose prints the
ok line of every check too; --show prints what each reading and each scenario step did, for writing a sidecar (and the ok
lines); --keep leaves the scratch directories in place and prints their paths. Nothing in the harness names a person: another family's
export, pages and sidecars run through it unchanged.
"""
import argparse, contextlib, json, os, re, shutil, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "checks")); sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import BY, FIXTURES, scratch
import imports, loop, parsers, scenario

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
    from resolve_places import parse, query_variants
    for c in R["place_parse"]:
        p = parse(c["raw"]); got = {"components": p["components"], "country": p["country"], "queries": query_variants(p) if (p["components"] or p["country"]) else []}
        if got != c["parsed"]: bad.append(f"resolve_places.parse({c['raw']!r}) gave {got!r}, expected {c['parsed']!r}")
    names = [tuple(x) for x in R["dated_names"]["names"]]
    for c in R["dated_names"]["cases"]:
        got = place_verdict(c["record"], c["tree"], dated_names=names)
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
    say(outcome_of([{"restricted": True}], [], ["a"]) == "none" and outcome_of([{"restricted": True}, {"restricted": False}], [], ["a"]) == "found" and outcome_of([], ["x"], []) == "error" and outcome_of([], [], ["a"]) == "none",
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
    whole = (K["heading"] + "\r\n").encode("latin-1") + dbody
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

def evidence_insert_only():
    """The evidence layer is insert-only (CLAUDE.md hard rule 2): on a scratch catalog holding one real record read into personas
    and facts, an UPDATE and a DELETE on artifact, persona and persona_fact are each refused with the trigger's own words
    (schema/sqlite_extras.sql), so a dropped trigger turns this red; the rows are all still there afterwards."""
    from treelib import archive_object
    from extract import extract
    name = "va-gravesite-search-davidson-raymond-2007"
    with open(os.path.join(FIXTURES, name + ".expect.json"), encoding="utf-8") as fh: a = json.load(fh)["archive"]
    with open(os.path.join(FIXTURES, name + ".html"), "rb") as fh: data = fh.read()
    d, db = scratch(False); bad = []
    try:
        cx = sqlite3.connect(db); cx.execute("PRAGMA foreign_keys=ON"); cx.row_factory = sqlite3.Row
        sha, _ = archive_object(cx, data, mime=a["mime"], source_id=a["source"], collection_id=None, locator_kind=a["locator"]["kind"], locator_value=a["locator"]["value"], retrieved_by=BY, terms=None, cost="free", trust_tier=None)
        extract(cx, sha, BY); cx.commit()
        before = {t: cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("artifact", "persona", "persona_fact")}
        for table, key, update_says, delete_says in (("artifact", "sha256", "immutable", "never deleted"), ("persona", "id", "immutable", "never deleted"), ("persona_fact", "id", "immutable", "never deleted")):
            row = cx.execute(f"SELECT {key} FROM {table} LIMIT 1").fetchone()
            if not row: bad.append(f"{table} holds no row to try"); continue
            for sql, says in ((f"UPDATE {table} SET {key}={key} WHERE {key}=?", update_says), (f"DELETE FROM {table} WHERE {key}=?", delete_says)):
                try: cx.execute(sql, (row[0],)); bad.append(f"{sql.split()[0]} on {table} was allowed")
                except sqlite3.IntegrityError as e:
                    if says not in str(e): bad.append(f"{sql.split()[0]} on {table} was refused, but not by its trigger: {e}")
                cx.rollback()
        after = {t: cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
        if after != before: bad.append(f"rows changed: {before} then {after}")
        cx.close()
    finally: shutil.rmtree(d, ignore_errors=True)
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

class OkLines:
    """stdout that counts the `ok` lines of the checks and prints them only when asked; every other line (a FAIL with its
    reasons, --show's detail, a kept scratch path) prints as it comes."""
    def __init__(self, out, verbose): self.out, self.verbose, self.ok, self.failed, self.pending = out, verbose, 0, 0, ""
    def write(self, text):
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            self.ok += line.startswith("ok   "); self.failed += line.startswith("FAIL")
            if self.verbose or not line.startswith("ok   "): self.out.write(line + "\n")
    def flush(self): self.out.flush()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--show", action="store_true"); ap.add_argument("--keep", action="store_true"); ap.add_argument("--verbose", action="store_true"); a = ap.parse_args()
    bad = 0; lines = OkLines(sys.stdout, a.verbose or a.show)
    with contextlib.redirect_stdout(lines):
        bad_files = compiles(); bad += bool(bad_files)
        print("ok   every tool and check module compiles" if not bad_files else "FAIL compile: " + "; ".join(bad_files))
        bad_rules = rules(); bad += bool(bad_rules)
        print("ok   the pure rules on tests/fixtures/rules.json: the surname rule, the holder search, the rule's automated kinds, place_verdict's coarser, finer and dated agreement, collection_state" if not bad_rules else "FAIL rules: " + "; ".join(bad_rules))
        bad_conn = connectors_offline(); bad += bool(bad_conn)
        print("ok   connectors offline on tests/fixtures/connectors.json: a cited book asked by its title and its copies read from the Archive's answer, the search inside once per spelling, a lent book a none run; a cited obituary asked at the row's connectors in the paper's year; the gravesite locator's posted search and its results page read; the death index's whole file asked once and its surname's rows derived; Kentucky's death and birth indexes asked a year's file at a time, a surname's rows kept as the record and read by each index's own layout" if not bad_conn else "FAIL connectors: " + "; ".join(bad_conn))
        bad_kinds = save_page_kinds(); bad += bool(bad_kinds)
        print("ok   tools/save_page.js recognises every saved fixture page as the kind its parser family reads: a FamilySearch results page (rows or no results) or record, a Find a Grave memorial or search, an AAD page" if not bad_kinds else "FAIL save_page.js: " + "; ".join(bad_kinds))
        bad_ev = evidence_insert_only(); bad += bool(bad_ev)
        print("ok   the evidence layer is insert-only: an UPDATE and a DELETE on artifact, persona and persona_fact are each refused by their trigger, on a catalog holding a real record read" if not bad_ev else "FAIL evidence: " + "; ".join(bad_ev))
        bad += parsers.check(a.keep, a.show)
        bad += scenario.check(os.path.join(scenario.SCENARIOS, "decisions"), a.keep, a.show)
        bad += loop.check(a.keep, a.show)
        bad += imports.check(a.keep, a.show)
    print(f"green: {lines.ok} checks" if not bad else f"{bad} failure(s) of {lines.ok + lines.failed} checks")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
