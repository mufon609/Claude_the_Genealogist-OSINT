#!/usr/bin/env python3
"""Materialize a person's questions and steps into the catalog (research_question, search_plan).

usage: tools/plan.py "<person>" [--tree slug]      tools/plan.py --all [--tree slug]

Questions are fact-level (missing parents, no surname, conflict, ...). A step
belongs to the person and a checklist row: a fetch of a record the tree already
cites (one per citation, with its locator), or a typed search for a missing row.
Footprint records on relatives become fetch steps under the fact-level question
they serve. A fetch is re-targeted to the free holder of the citation's
collection (data/holders.csv): the step's locator source is the holder and its
fields are the citation's own details (collection, the name the citation sits
on, the page text's parts, the memorial URL), basis citation. A citation whose
collection has no free holder, or whose holder is a scanned_index (an
archive.org collection of scanned index pages, readable only through a
page-locating step not yet built), stays a fetch step with mode blocked and
the reason in its rationale. A citation whose holder is browse-only
(catalog.browse_only: a FamilySearch images-only collection) stays a fetch step,
mode fetch, with the reason in its rationale: it is browsed by hand, film by
film, never saved as a page, so tools/fetches.py's list leaves it off (no
name with an unfilled placeholder is ever printed) and a turn never pauses on
it. A citation whose holder has no connector and whose link takes nothing from the citation (catalog.prefills_nothing: the
holder's form posts, or the link is the same whatever the citation says) is a fetch step with mode assisted and the reason in its
rationale: a search a person runs at the holder's page with the citation's details, not a page to save, so the list leaves it
off and a turn never pauses on it; its fields and its link are as for any fetch step, and its log stays through a re-plan. A memorial accepted as the person's own gives one
fetch step per photograph the page types Grave (the stone itself, registry row
E05, the image's URL as locator), and one fetch step per relative it merely
lists (the matcher writes no card for one, tools/match.py): the relative's own
memorial, under the tree person their name and birth year fit when exactly one
does, else on the memorial's own person as a lead, row_key "listed relative:
<memorial id>" (tools/plan.py's listed_relative_leads). A row of a results page (FamilySearch, Find a Grave, AAD) that fits the person
the page was fetched for (matcher.fitting_rows) is a lead the same way: a fetch step for the row's own record, row "search result:",
the results page's holder as the locator source, the row's words as its fields (tools/plan.py's result_row_leads); the matcher
proposes no row. A census household not wholly held (tools/households.py, grouped again here before it is read) is a lead
on each person the tree ties to one of its members, under a row of its own (household_row): FamilySearch's search of its
collection by the surname, the place and the year, never a given name, its next page while its answer is not held in full, and
the record page of the candidate for its missing entries households.candidates opens, the head's first, one at a time
(household_leads). Idempotent: questions and steps are keyed, so re-running updates what
changed, adds what is new, drops steps no longer generated (one that was run but
is not done is kept for its log as skipped, planned again if generated again;
one dropped is named in the run's audit row by its key, row and rationale, the
only trace of it once the row is deleted), marks a fetch step done when an
archived record holds its citation for the person (catalog.held_for: the step's own record id, a sheet image of the page,
or a record page naming the person), and plans again a done fetch step whose citation the archive does not hold and whose
found runs since it was last reopened carry only pages that point at its record or hold nothing (log_search.closed_by_pointers:
a results listing, a page no parser read), never one done on the owner's word, by a hand's found run, on a household record
or on a listing that is the record, logs a household record (a census page, whichever way it arrived) accepted onto the
person found on their own step for its census year (log_search.hold_household), so the row reads held and no runner
searches that census again for a household the tree has read, keeps done steps, puts first the steps on the records that
name parents (checklist.names_parents) for a person whose parents nobody has accepted, and closes questions
whose gap has gone (closed_reason 'gap_gone'). A question a person dismissed or answered stays closed. Nothing
here runs a search. Before writing anything the plan checks that every holder
in data/holders.csv and every source id the checklist emits is a row in the
catalog's source table, and stops with one line naming the missing ids and the
sync command (tools/initdb.py --sync-sources) when the registry is out of step.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, connect, dumps, now, resolve_tree, ulid
from catalog import Catalog, dbid_of, browse_only, not_withdrawn, prefills_nothing, year
from checklist import build, names_parents
from households import OPEN_AT_ONCE, ark_id, candidates, page_words, regroup, said, waiting_for
from log_search import closed_by_pointers, hold_household

FOOTPRINT_HOME = ("missing_parents", "identity_incomplete", "missing_spouse", "unverified_claim")
ANCESTRY = "B02"
PHOTOS = "E05"                                                   # the registry row gravestone photographs are archived under: an image of the stone, tier 1
PHOTO_COLLECTION = "Find a Grave memorial photographs"

def q_key(q):
    """Stable key: kind plus the other person's id when the question is about one, else kind plus the full detail, never
    truncated, so two conflicts that happen to agree for a while and then differ stay two rows (research_question.q_key is
    TEXT with a unique key per person: a full detail fits)."""
    if q.get("other_id"): return q["kind"] + ":" + q["other_id"]
    return q["kind"] + ":" + re.sub(r"\s+", " ", (q.get("detail") or "")).strip()

def citation_fields(cat, collection, cited, name, year=None, person_id=None):
    """The citation's own details as query fields, each {value, basis 'citation'}: the collection, the name the citation sits on,
    every 'Label: value' part of the page text under its label, the rest of the page text under 'citation', the memorial URL.
    A labelled part that is a place (its label ending "place") carries every accurate name for it, the citation's own string
    first (Catalog.place_search_names, as a search step's own place field does), when that string is itself a resolved place
    in the tree; unresolved, it is the citation's bare string alone."""
    f = lambda v: {"value": v, "basis": "citation"}
    out = {"collection": f(collection)}
    if name: out["name"] = f(name)
    rest = []
    for part in (cited.get("page") or "").split("; "):
        m = re.fullmatch(r"([A-Za-z][A-Za-z .]{0,40}): (.+)", part.strip())
        if m and m.group(1).lower() not in out:
            label, value = m.group(1).lower(), m.group(2).strip()
            if label.endswith("place"):
                ps = cat.q("SELECT place_id FROM place_string WHERE raw=? AND place_id IS NOT NULL", value)
                names = cat.place_search_names(ps[0][0], year=year, person_id=person_id) if ps else []
                out[label] = f([value] + [n for n in names if n != value])
            else: out[label] = f(value)
        elif part.strip(): rest.append(part.strip())
    if rest: out["citation"] = f("; ".join(rest))
    if cited.get("url"): out["url"] = f(cited["url"])
    return out

def fetch_step(cat, row_key, query_type, apid, collection, collection_id, on, expected, where, sources, name, question_key=None, year=None, person_id=None):
    cited = cat.cited().get(apid, {})
    holder = (cat.holders.get(dbid_of(apid)) or [None])[0]
    names = cited.get("names") or []
    fields = citation_fields(cat, collection, cited, names[0] if names else name, year=year, person_id=person_id)
    if holder and holder["HolderKind"] == "scanned_index":
        source, mode, why = holder["HolderSourceId"], "blocked", f"blocked: {holder['HolderCollection']} holds scanned index pages; the page-locating step is not built"
    elif holder and browse_only(holder):
        source, mode, why = holder["HolderSourceId"], "fetch", f"browsed by hand at {holder['HolderCollection']}: no search or record page there for the browser to save, film by film; off the fetch list"
    elif holder and not cat.sources.get(holder["HolderSourceId"], {}).get("connector") and prefills_nothing(holder, fields):
        source, mode, why = holder["HolderSourceId"], "assisted", f"searched by hand at {holder['HolderCollection']}: its link takes nothing from the citation, so there is no page to save, only a search to run with the citation's details; off the fetch list"
    elif holder: source, mode, why = holder["HolderSourceId"], "fetch", f"fetch the record at {holder['HolderCollection']}"
    else: source, mode, why = ANCESTRY, "blocked", "blocked: no free holder of this collection yet, and Ancestry needs a membership this account lacks"
    return {"step_key": f"fetch:{apid}", "row_key": row_key, "question_key": question_key, "kind": "fetch", "query_type": query_type, "query_json": dumps(fields),
            "locator_source_id": source, "locator_kind": "apid", "locator_value": apid, "collection_id": collection_id, "on_json": dumps(on),
            "sources_json": dumps(sources), "mode": mode, "expected": expected, "rationale": f"{where}; {why}"}

MEMORIAL = re.compile(r"/memorial/(\d+)(?:/|$)")
REL_TO = {"parent": "child", "child": "parent", "spouse": "spouse", "sibling": "sibling"}      # the record's subject, seen from the persona

def linked_records(cx, tree_id, cat, pid, me):
    """Fetch steps for the records a held record links from a persona accepted as this person: a Find a Grave memorial lists its
    family members with each one's own memorial, so once the owner has said the listed parent is John Y Davidson, John's own
    memorial is a lead on John (docs/TERMS.md §0), under his cemetery row, with the linked record's own identity as
    the locator and the page's words as its fields (basis record); the record is John's own, so the step sits on him and the
    "linked from" field says where it came from. Nothing is generated for a persona only proposed."""
    out = []; q = cx.cursor(); q.row_factory = sqlite3.Row
    col = q.execute("SELECT id, name FROM collection WHERE name LIKE 'U.S., Find a Grave%' ORDER BY name LIMIT 1").fetchone()
    for r in q.execute("""SELECT pe.name_text, pe.role_in_record, pe.region_json, s.display_name AS subject FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                           JOIN extraction e ON e.id=pe.extraction_id JOIN persona sub ON sub.extraction_id=e.id AND sub.role_in_record='memorial'
                           LEFT JOIN person_persona sp ON sp.persona_id=sub.id AND sp.status='accepted' LEFT JOIN person s ON s.id=sp.person_id
                           WHERE pp.person_id=? AND pp.status='accepted' AND e.superseded_by IS NULL AND pe.role_in_record<>'memorial'""", (pid,)):
        m = MEMORIAL.search((json.loads(r["region_json"] or "{}").get("url") or ""))
        if not m: continue
        mid = m.group(1); url = f"https://www.findagrave.com/memorial/{mid}/"
        subject = r["subject"] or "the memorial's subject"; rel = REL_TO.get(r["role_in_record"], r["role_in_record"])
        fields = {"collection": {"value": col["name"] if col else "Find a Grave", "basis": "record"}, "name": {"value": r["name_text"], "basis": "record"},
                  "url": {"value": url, "basis": "record"}, "linked from": {"value": f"{subject}'s memorial, where {r['name_text']} is listed under {r['role_in_record']}", "basis": "record"}}
        out.append({"step_key": f"fetch:memorial:{mid}", "row_key": "cemetery / family plot:", "question_key": None, "kind": "fetch", "query_type": "subject_record",
                    "query_json": dumps(fields), "locator_source_id": "E01", "locator_kind": "memorial_id", "locator_value": mid, "collection_id": col["id"] if col else None,
                    "on_json": "[]", "sources_json": dumps(["E01"]), "mode": "fetch", "expected": "the person's own memorial: name, dates, cemetery, plot, the family it links",
                    "rationale": f"named on {subject}'s memorial with a link to their own; fetch it by the one-call method"})
    return out

def gravestone_photos(cx, tree_id, cat, pid):
    """Fetch steps for the gravestone photographs on a memorial accepted as this person's own: the page types each photograph,
    and one typed Grave is an image of the stone itself, a primary source (registry row E05, tier 1) saved in the owner's
    browser one at a time and read by the transcription path into a card like any other image. One step per photograph, under
    the cemetery row, with the image's own URL as the locator and the page's words as the fields (the memorial, the photograph's
    id, its caption and type), basis record. Nothing for a memorial only proposed, and nothing for a photograph the page types
    otherwise (a portrait, a family photograph)."""
    out = []; q = cx.cursor(); q.row_factory = sqlite3.Row
    for r in q.execute("""SELECT pe.name_text, pe.region_json, e.structured_json FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN extraction e ON e.id=pe.extraction_id
                           JOIN extractor x ON x.id=e.extractor_id WHERE pp.person_id=? AND pp.status='accepted' AND e.superseded_by IS NULL AND pe.role_in_record='memorial' AND x.name='findagrave-memorial'""", (pid,)):
        parsed = json.loads(r["structured_json"] or "{}"); mid = str(parsed.get("memorial_id") or json.loads(r["region_json"] or "{}").get("memorial_id") or "")
        for ph in parsed.get("photos") or []:
            if (ph.get("type") or "").lower() != "grave" or not ph.get("url") or not ph.get("id"): continue
            f = lambda v: {"value": v, "basis": "record"}
            fields = {"collection": f(PHOTO_COLLECTION), "name": f(r["name_text"]), "memorial": f(mid), "photo": f(str(ph["id"])), "url": f(ph["url"]), "photo type": f(ph["type"]),
                      **({"caption": f(ph["caption"])} if ph.get("caption") else {})}
            out.append({"step_key": f"fetch:photo:{ph['id']}", "row_key": "cemetery / family plot:", "question_key": None, "kind": "fetch", "query_type": "subject_record", "query_json": dumps(fields),
                        "locator_source_id": PHOTOS, "locator_kind": "url", "locator_value": ph["url"], "collection_id": None, "on_json": "[]", "sources_json": dumps([PHOTOS]), "mode": "fetch",
                        "expected": "the stone as photographed: the names and dates cut on it, read one person at a time",
                        "rationale": f"photograph {ph['id']} on memorial {mid}, typed Grave by the page: the stone itself is a primary source, saved in the owner's browser and read by the transcription path"})
    return out

FAG_COLLECTION = "U.S., Find a Grave Index, 1600s-Current"

def listed_relative_leads(cx, tree_id, cat, pid):
    """Fetch steps for the relatives a memorial merely lists, once the memorial is accepted as somebody's own: the owner's
    word is that a memorial's family connections are leads to look over, not facts (docs/TERMS.md §0), so the
    matcher writes no card for one (tools/match.py). A relative whose given name, surname and birth year plainly fit
    exactly one person of the tree (matcher.fits_by_name_and_year: a listed relative may already be someone fully placed
    in the family, so this is not the fitting check's unlinked-only candidate list) gets a fetch step for their own
    memorial under that person's cemetery row; one fitting nobody, or more than one, stays a lead on the memorial's own
    person, row_key "listed relative:<memorial id>", with the relationship the page states in its rationale. Nothing
    here decides who the relative is or creates anyone: the fit is by name and year alone, so a wrong fit costs a
    wasted fetch, never a wrong identity. Dropped, like any generated step, once the memorial's acceptance is
    withdrawn: the query that finds it no longer does."""
    from matcher import fits_by_name_and_year, personas_of
    out = []; q = cx.cursor(); q.row_factory = sqlite3.Row
    for sub in q.execute("""SELECT pp.person_id AS subject_id, pe.extraction_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                             JOIN extraction e ON e.id=pe.extraction_id JOIN extractor x ON x.id=e.extractor_id JOIN person p ON p.id=pp.person_id
                             WHERE pp.status='accepted' AND pe.role_in_record='memorial' AND x.name='findagrave-memorial' AND e.superseded_by IS NULL
                             AND p.tree_id=? AND p.merged_into IS NULL""", (tree_id,)).fetchall():
        subject_id, eid = sub["subject_id"], sub["extraction_id"]
        subject_name = cat.person(subject_id)["name"]
        for pr in personas_of(cx, eid):
            if pr["role"] == "memorial" or not pr.get("memorial"): continue
            if q.execute("SELECT 1 FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status<>'undecided' AND o.tree_id=?", (pr["id"], tree_id)).fetchone(): continue   # decided some other way already: not a lead; decisions.link_family's own Undecided trace does not count
            fits = [c for c in fits_by_name_and_year(cat, cx, tree_id, pr) if c != subject_id]
            mid = pr["memorial"]; f = lambda v: {"value": v, "basis": "record"}
            fields = {"collection": f(FAG_COLLECTION), "name": f(pr["name"]), "url": f(f"https://www.findagrave.com/memorial/{mid}/"),
                      "linked from": f(f"{subject_name}'s memorial, where {pr['name']} is listed under {pr['role']}")}
            base = {"question_key": None, "kind": "fetch", "query_type": "subject_record", "query_json": dumps(fields), "locator_source_id": "E01",
                    "locator_kind": "memorial_id", "locator_value": mid, "collection_id": None, "on_json": "[]", "sources_json": dumps(["E01"]), "mode": "fetch",
                    "expected": "the relative's own memorial: name, dates, cemetery, plot, the family it links"}
            if len(fits) == 1 and fits[0] == pid:
                out.append({**base, "step_key": f"fetch:memorial:{mid}", "row_key": "cemetery / family plot:",
                            "rationale": f"listed as {pr['role']} on {subject_name}'s memorial, fits this person by name and birth year; fetch their own memorial next"})
            elif len(fits) != 1 and pid == subject_id:
                out.append({**base, "step_key": f"fetch:listed:{mid}", "row_key": f"listed relative:{mid}",
                            "rationale": f"listed as {pr['role']} on this memorial, {'fitting nobody' if not fits else 'fitting more than one person'} in the tree by name and birth year; "
                                         "a lead, not a person: fetch their own memorial to see who they are"})
    return out

AAD_COLLECTION = "WWII Army Enlistment Records (AAD)"

def row_record(parser, region):
    """(locator kind, the row's own record identity, the record's URL, its collection) for a row of a results page, from the
    parser that read it and the row's region: a FamilySearch row's ark, a Find a Grave row's memorial id, an AAD row's record
    URL; the identity is None when the row carries none."""
    if parser == "familysearch-search": return "ark", region.get("ark"), region.get("url"), region.get("collection") or "FamilySearch record search"
    if parser == "findagrave-search":
        mid = str(region.get("memorial_id") or ""); return "memorial_id", mid or None, f"https://www.findagrave.com/memorial/{mid}/", FAG_COLLECTION
    return "url", region.get("url"), region.get("url"), AAD_COLLECTION

def row_year(collection, pr):
    """The year a results row's record is about, for the name its page is saved under: a census collection's own year, else the
    row's death, else its birth; None when the row dates nothing."""
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", collection) if re.search(r"census", collection, re.I) else None
    return int(m.group(1)) if m else year((pr["death"] or {}).get("start")) or year((pr["birth"] or {}).get("start"))

def row_words(pr):
    """What a results row states, as written: its birth and death with their places, its burial and residence places."""
    parts = []
    for label in ("birth", "death"):
        said = ", ".join(x for x in ((pr[label] or {}).get("text"), pr.get(f"{label} place")) if x)
        if said: parts.append(f"{label} {said}")
    parts += [f"{label} {pr[label]}" for label in ("burial place", "residence place") if pr.get(label)]
    return "; ".join(parts)

def result_row_leads(cx, tree_id, cat, pid):
    """Fetch steps for the rows of a results page that fit this person (docs/TERMS.md §0): a row is never a card (the
    matcher proposes none, tools/match.py), but one that fits the person a page was fetched for, by the matcher's own definition
    (matcher.fitting_rows: more than a name and a year), and carries its own record's identity (an ark, a memorial id, an
    enlistment record's URL) is a lead on that person: a fetch step for the row's own record, key "fetch:row:<record id>", under
    row "search result:", with the holder of the results page as the locator source (so tools/fetches.py lists it for the browser
    when the holder has no connector), the row's words as its fields (basis record), the results page it was found on, and what
    agrees with the person in its rationale. A row a person rejected as this person, or accepted as somebody else, is no lead
    for them (a person's decision stands); one accepted as them still is, its record not yet fetched; a row that does not fit
    stays a hint on the page. Dropped, like any generated step, once the row no longer fits."""
    from readers import POINTING_LISTINGS
    from matcher import fitting_rows, said
    out = []; seen = set(); known = {}; q = cx.cursor(); q.row_factory = sqlite3.Row; f = lambda v: {"value": v, "basis": "record"}
    for page in q.execute(f"""SELECT DISTINCT e.id AS eid, x.name AS parser, ar.source_id, ar.locator_value AS url, e.ran_at FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id,
                               json_each(l.artifacts_json) j JOIN extraction e ON e.artifact_sha256=j.value JOIN extractor x ON x.id=e.extractor_id JOIN artifact ar ON ar.sha256=e.artifact_sha256
                               WHERE sp.person_id=? AND l.superseded_by IS NULL AND e.superseded_by IS NULL AND e.status='complete' AND x.name IN ({','.join('?' * len(POINTING_LISTINGS))}) ORDER BY e.ran_at, e.id""", (pid, *POINTING_LISTINGS)).fetchall():
        holder = cat.sources.get(page["source_id"], {}).get("name") or page["source_id"]
        for _, pr, agree in fitting_rows(cx, page["eid"], pid, known):
            region = json.loads(q.execute("SELECT region_json FROM persona WHERE id=?", (pr["id"],)).fetchone()[0] or "{}")
            lkind, rid, url, collection = row_record(page["parser"], region)
            if not rid or rid in seen: continue
            if any(who != pid or status == "rejected" for who, status in q.execute("SELECT pp.person_id, pp.status FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND pp.status<>'undecided' AND o.tree_id=?", (pr["id"], tree_id))): continue   # a person decided the row is somebody else, or not this person: no lead for them; a row accepted as them still has its record to fetch
            seen.add(rid)
            fields = {"collection": f(collection), "name": f(pr["name"]), "year": f(str(row_year(collection, pr) or "")), "url": f(url), "listed": f(row_words(pr)), "found on": f(f"{holder} results page {page['url']}, row {region.get('row')}")}
            out.append({"step_key": f"fetch:row:{rid}", "row_key": "search result:", "question_key": None, "kind": "fetch", "query_type": "subject_record", "query_json": dumps({k: v for k, v in fields.items() if v["value"]}),
                        "locator_source_id": page["source_id"], "locator_kind": lkind, "locator_value": rid, "collection_id": None, "on_json": "[]", "sources_json": dumps([page["source_id"]]), "mode": "fetch",
                        "expected": "the record the row stands for: the person's own facts as the record states them",
                        "rationale": f"row {region.get('row')} of a {holder} results page fits this person: {'; '.join(map(said, agree))}. A lead, not a card: fetch the row's own record"})
    return out

FAMILYSEARCH = "D03"

def household_row(h):
    """The plan row a household's own leads sit under, "household:<year>": not the person's census row, which the person's own
    census record holds (log_search.hold_household logs every planned step of that row found with it) and which a page about
    another entry must never read as held (Catalog.fetched_rows)."""
    return f"household:{h['year']}"

def household_leads(cx, tree_id, cat, pid):
    """Fetch steps for what a census household holding this person lacks (docs/DATA-ARCHITECTURE.md §7 decision 21,
    docs/TERMS.md §0 and docs/HOUSEHOLDS.md): a current household not wholly held (tools/households.py waiting_for: a
    member of it the tree ties to this person by a link or a card, neither rejected) gives, under its own row (household_row):
    its search, FamilySearch's search of the collection the household's copies are in (its key from data/holders.csv), by the
    surname most of the members are written under, the place their census residence gives and the year, never by a given name,
    which the head's own entry need not share, while a page of its answer is not held, its link the first such page
    (households.answer: a cut answer's next page is the step's next save), key "fetch:household:<form and page>:<surname>", its
    locator the same household and surname (kind household); and the record page of each candidate households.candidates opens
    (OPEN_AT_ONCE at a time, in its order), key "fetch:row:<ark>" as the record behind any row of a results page, its locator the
    row's ark, its fields the row's words and the household's (basis record), its rationale why it stands where it does in the
    order and what the candidates tried before it showed. FamilySearch has no connector, so tools/fetches.py lists both for the
    browser; a saved page carrying the list's key reaches them, and its own identity does too (tools/attach.py). The fields are
    the held records' (basis record), never the person's claims, so the steps open before the baseline is reviewed, as a cited
    record's fetch does: they find the rest of a page already held. A household with no surname, place, year or FamilySearch
    collection to search by gives no step. A candidate whose record page is held has been tried and the next is opened in its
    place; a step dropped, like any generated step, once the household is wholly held, its answer held in full (the search), its
    candidates have run out, or nobody ties the person to it: the household then stays as stored, incomplete, naming what it misses."""
    out = []; f = lambda v: {"value": v, "basis": "record"}
    for h in waiting_for(cx, tree_id, pid):
        if not (h["year"] and h["surname"] and h["place"] and h["fs_collection"]): continue
        lacks, who, where = "; ".join(h["missing"]), "; ".join(said(m) for m in h["members"]), page_words(h["page"])
        c = candidates(cx, tree_id, h); a = c["answer"]; stem = f"{h['key']}:{h['surname']}"; row = household_row(h)
        held = ((f"{a['count']} matching records on {a['total']} page{'s' if a['total'] != 1 else ''}, " if a["count"] is not None else "")
                + f"page{'s' if len(a['held']) != 1 else ''} {', '.join(map(str, a['held']))} held") if a["held"] else "no page of its answer held yet"
        tried = "; ".join(f"{t['name']} ({ark_id(t['ark'])}): {t['where']}" for t in c["tried"])
        if a["next"]:
            out.append({"step_key": f"fetch:household:{stem}", "row_key": row, "question_key": None, "kind": "fetch", "query_type": "household",
                        "query_json": dumps({"collection": f(h["collection"]), "surname": f(h["surname"]), "residence place": f(h["place"]), "year": f(str(h["year"])), "url": f(a["next_url"]),
                                             "household": f(f"{where}: {who}"), "missing": f(lacks)}),
                        "locator_source_id": FAMILYSEARCH, "locator_kind": "household", "locator_value": stem, "collection_id": h["collection_id"], "on_json": "[]",
                        "sources_json": dumps([FAMILYSEARCH]), "mode": "fetch", "expected": "a page of the search's answer: each row that carries the household's surname and place is a candidate for its missing entries",
                        "rationale": f"the {h['year']} household of {who}" + (f", {where}," if where else "") + f" is not wholly held: missing {lacks}; FamilySearch's {h['collection']} "
                                     f"searched by the surname, the place and the year the page gives, never by a given name, which the head's own entry need not share; {held}: page {a['next']} next"})
        for n, cand in enumerate(c["open"], 1):
            fields = {"collection": f(h["collection"]), "name": f(cand["name"]), "year": f(str(h["year"])), "url": f(cand["url"]), "listed": f(", ".join(x for x in (f"born {cand['born']}" if cand["born"] else None, cand["place"]) if x)),
                      "found on": f(f"FamilySearch results page {cand['found_on']}, row {cand['row']}"), "household": f(f"{where}: {who}"), "candidate for": f("; ".join(cand["for"]))}
            out.append({"step_key": f"fetch:row:{cand['ark']}", "row_key": row, "question_key": None, "kind": "fetch", "query_type": "household",
                        "query_json": dumps({k: v for k, v in fields.items() if v["value"]}), "locator_source_id": FAMILYSEARCH, "locator_kind": "ark", "locator_value": cand["ark"],
                        "collection_id": h["collection_id"], "on_json": "[]", "sources_json": dumps([FAMILYSEARCH]), "mode": "fetch",
                        "expected": "the row's own record page: its page, line and districts say whether it is on the household's page and in its run, its relationship whether it is the head",
                        "rationale": f"candidate {n} of {len(c['order'])} for {'; '.join(cand['for'])} of the {h['year']} household of {who}" + (f", {where}" if where else "")
                                     + f": {cand['name']}, row {cand['row']} of a FamilySearch results page" + (f"; {'; '.join(cand['why'])}" if cand["why"] else "")
                                     + (f"; {len(c['left_out'])} row{'s' if len(c['left_out']) != 1 else ''} left out, born where the head cannot be" if c["left_out"] else "")
                                     + (f"; tried before it: {tried}" if tried else "") + f". {OPEN_AT_ONCE} candidate{'s' if OPEN_AT_ONCE > 1 else ''} at a time: the next is opened once this page is held"})
    return out

class RegistryOutOfStep(Exception):
    """A source id the plan would write is not in the catalog's source table."""

def check_registry(cx, cat, r=None):
    """Every holder in data/holders.csv and every source id the checklist emits must be a row in source, or the plan would
    write a step against a missing row and fail on a foreign key. Raises RegistryOutOfStep naming the ids and the fix."""
    ids = {h["HolderSourceId"] for rows in cat.holders.values() for h in rows} | {PHOTOS}
    if r: ids |= {sid for grp in ("A", "B") for row in r["checklist"][grp] for sid in row.get("sources") or []}
    have = {row[0] for row in cx.execute("SELECT id FROM source")}
    missing = sorted(ids - have)
    if missing: raise RegistryOutOfStep(f"registry out of step with the catalog: source id(s) {', '.join(missing)} not in the source table; run python3 tools/initdb.py --sync-sources --db <this catalog>")

def searched_where(cat, s, mode):
    """What a step's rationale says of who searches where when its mode is auto yet some source of its row has no connector for it:
    the loop at the sources it asks, the owner by hand at the others. Empty for any other mode or a row every source of
    which the loop asks."""
    name = lambda sid: cat.sources.get(sid, {}).get("name") or sid
    modes = s.get("modes") or {}
    hand = [name(sid) for sid, m in modes.items() if m != "auto"]
    if mode != "auto" or not hand: return ""
    return f"; searched by the loop at {', '.join(name(sid) for sid, m in modes.items() if m == 'auto')}, by hand at {', '.join(hand)}"

def archived_at(cx, kind, value):
    """Whether the archive holds a file at a locator that is no record id (a URL, an ark, a memorial id), as the file was
    archived under or as artifact_locator names it, never one withdrawn (catalog.not_withdrawn): a fetch step at such a
    locator is done by that file alone."""
    return bool(cx.execute(f"""SELECT 1 FROM artifact WHERE locator_kind=? AND locator_value=? AND {not_withdrawn('sha256')}
                               UNION SELECT 1 FROM artifact_locator WHERE kind=? AND value=? AND {not_withdrawn('artifact_sha256')}""", (kind, value, kind, value)).fetchone())

def plan_person(cx, tree_id, pid, by):
    cat = Catalog(cx, tree_id); r = build(cat, pid); ts = now(); me = r["person"]["name"]
    check_registry(cx, cat, r)
    regroup(cx, by, ts)                                                  # the households grouped again, a page read since in them, before their leads are read
    wanted = {q_key(q): (q["kind"], dumps(q)) for q in r["questions"]}
    fetches, searches = [], []
    for grp in ("A", "B"):
        for row in r["checklist"][grp]:
            s = row.get("search")
            if not s: continue
            rk = f"{row['record']}:{row.get('instance') or ''}"
            if row["status"] == "cited":
                own = []
                yr = int(row["instance"]) if row.get("instance") and str(row["instance"]).isdigit() else None
                for c in row["citations"]:
                    where = "cited on " + ", ".join(n for n, _ in c["on"]) if c["on"] else "cited on this person"
                    own.append(fetch_step(cat, rk, s["type"], c["apid"], c["collection"], c["collection_id"], c["on"], row["settles"], where, row["sources"],
                                          c["on"][0][0] if c["on"] else me, year=yr, person_id=pid))
                fetches += own
                if r["baseline"]["complete"] and (not own or all(f["mode"] == "blocked" for f in own)) and s.get("free_mode"):   # nothing fetchable from the citations (none with a record id, or every one blocked): search the free sources as for a missing row
                    searches.append({"step_key": f"search:{rk}", "row_key": rk, "question_key": None, "kind": "search", "query_type": s["type"], "query_json": dumps(s["fields"]),
                                     "locator_source_id": None, "locator_kind": None, "locator_value": None, "collection_id": None, "on_json": None,
                                     "sources_json": dumps(s["sources"]), "mode": s["free_mode"], "expected": s["expect"], "rationale": f"{row['record']} is cited only at a holder this account cannot reach; searched at the free sources" + searched_where(cat, s, s["free_mode"])})
            else:
                searches.append({"step_key": f"search:{rk}", "row_key": rk, "question_key": None, "kind": "search", "query_type": s["type"], "query_json": dumps(s["fields"]),
                                 "locator_source_id": None, "locator_kind": None, "locator_value": None, "collection_id": None, "on_json": None,
                                 "sources_json": dumps(s["sources"]), "mode": s["mode"], "expected": s["expect"], "rationale": f"{row['record']} is missing for this person" + searched_where(cat, s, s["mode"])})
    for lk in linked_records(cx, tree_id, cat, pid, me):                # a held record that names this person and links their own record: a lead
        if not any(lk["locator_value"] in (json.loads(f["query_json"]).get("url") or {}).get("value", "") for f in fetches): fetches.append(lk)
    fetches += gravestone_photos(cx, tree_id, cat, pid)                 # the stone itself, photographed on the person's own memorial
    fetches += listed_relative_leads(cx, tree_id, cat, pid)             # a relative a memorial merely lists: their own memorial, a lead
    for lead in result_row_leads(cx, tree_id, cat, pid):                # a row of a results page that fits this person: the row's own record, a lead
        if not any(lead["locator_value"] == f["locator_value"] or lead["locator_value"] in (json.loads(f["query_json"]).get("url") or {}).get("value", "") for f in fetches): fetches.append(lead)
    for lead in household_leads(cx, tree_id, cat, pid):                 # a census household holding this person not wholly held: its search's next page and its candidates' record pages, leads
        if not (lead["locator_kind"] == "ark" and any(lead["locator_value"] == f["locator_value"] for f in fetches)): fetches.append(lead)   # a candidate whose record is already a step of the person's (a row that fits them) is that step
    home = next((k for k in wanted if wanted[k][0] in FOOTPRINT_HOME), None)
    have = {st["locator_value"] for st in fetches}
    for rec in r["footprint"]["records"][:12]:
        if not rec.get("apid") or rec["apid"] in have: continue
        fetches.append(fetch_step(cat, f"footprint:{rec['apid']}", "footprint_record", rec["apid"], rec["collection"], rec.get("collection_id"), rec["on"], rec["expect"],
                                  "already on " + ", ".join(f"{n} ({rel})" for n, rel in rec["on"]), [ANCESTRY], rec["on"][0][0] if rec["on"] else me, home, person_id=pid))
    stats = {"questions_new": 0, "questions_kept": 0, "questions_closed": 0, "questions_left_closed": 0, "steps_new": 0, "steps_kept": 0, "steps_dropped": 0, "steps_done_by_archive": 0,
             "dropped": []}                                          # each step deleted below by key, row and rationale: the audit row is the only trace of it afterwards
    existing = {row[1]: row[0] for row in cx.execute("SELECT id, q_key FROM research_question WHERE subject_person_id=? AND status='open'", (pid,))}
    qid_by_key = {}
    for key, (kind, detail) in wanted.items():
        if key in existing: qid = existing[key]; cx.execute("UPDATE research_question SET detail_json=? WHERE id=?", (detail, qid)); stats["questions_kept"] += 1
        else:
            closed = cx.execute("SELECT id, closed_reason FROM research_question WHERE subject_person_id=? AND q_key=?", (pid, key)).fetchone()
            if closed and closed[1] != "gap_gone": stats["questions_left_closed"] += 1; continue      # a person dismissed or answered it
            if closed: qid = closed[0]; cx.execute("UPDATE research_question SET status='open', closed_reason=NULL, closed_at=NULL, detail_json=? WHERE id=?", (detail, qid))
            else: qid = ulid(); cx.execute("INSERT INTO research_question (id,tree_id,subject_person_id,kind,q_key,detail_json,status,created_at) VALUES (?,?,?,?,?,?,'open',?)", (qid, tree_id, pid, kind, key, detail, ts))
            stats["questions_new"] += 1
        qid_by_key[key] = qid
    stats["closed"] = []                                                 # the ids closed by this run, for a caller that knows what answered them
    for key, qid in existing.items():
        if key not in wanted:
            cx.execute("UPDATE research_question SET status='closed', closed_reason='gap_gone', closed_at=? WHERE id=?", (ts, qid)); stats["questions_closed"] += 1; stats["closed"].append(qid)
    have_steps = {row[1]: row[0] for row in cx.execute("SELECT id, step_key FROM search_plan WHERE person_id=?", (pid,))}
    seen, wanted_keys = {}, set()
    steps = fetches + searches
    if cat.link_basis(pid, "parents") != "accepted":                 # nobody has accepted this person's parents: the records that name them come first
        steps.sort(key=lambda st: not names_parents(st["row_key"], r["person"]["span"][0]))
    for seq, st in enumerate(steps, 1):
        n = seen[st["step_key"]] = seen.get(st["step_key"], 0) + 1      # two identical steps (e.g. two spouses of the same name)
        if n > 1: st["step_key"] += f":{n}"
        wanted_keys.add(st["step_key"])
        qid = qid_by_key.get(st["question_key"]) if st["question_key"] else None
        cols = (st["row_key"], qid, seq, st["kind"], st["query_type"], st["query_json"], st["locator_source_id"], st["locator_kind"], st["locator_value"],
                st["collection_id"], st["on_json"], st["sources_json"], st["mode"], st["expected"], st["rationale"])
        if st["step_key"] in have_steps:                                 # generated again: a step set aside as skipped is planned work once more
            cx.execute("""UPDATE search_plan SET row_key=?, question_id=?, seq=?, kind=?, query_type=?, query_json=?, locator_source_id=?, locator_kind=?, locator_value=?,
                          collection_id=?, on_json=?, sources_json=?, mode=?, expected=?, rationale=?, status=CASE WHEN status='skipped' THEN 'planned' ELSE status END WHERE id=?""", cols + (have_steps[st["step_key"]],)); stats["steps_kept"] += 1
        else:
            cx.execute("""INSERT INTO search_plan (row_key,question_id,seq,kind,query_type,query_json,locator_source_id,locator_kind,locator_value,collection_id,on_json,sources_json,mode,expected,rationale,
                          id,person_id,step_key,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'planned',?)""", cols + (ulid(), pid, st["step_key"], ts)); stats["steps_new"] += 1
    for sid, lkind, lval in cx.execute("SELECT id, locator_kind, locator_value FROM search_plan WHERE person_id=? AND kind='fetch' AND status='planned'", (pid,)).fetchall():
        if (lkind == "apid" and cat.held_for(lval, pid)) or (lkind and lkind != "apid" and lval and archived_at(cx, lkind, lval)):
            cx.execute("UPDATE search_plan SET status='done' WHERE id=?", (sid,)); stats["steps_done_by_archive"] += 1
    for sid, lkind, lval in cx.execute("SELECT id, locator_kind, locator_value FROM search_plan WHERE person_id=? AND kind='fetch' AND status='done'", (pid,)).fetchall():
        if not (lkind and lval): continue                            # a done fetch step whose citation the archive does not hold, closed by pages that point at its record or hold nothing: planned again
        if (lkind == "apid" and cat.held_for(lval, pid)) or (lkind != "apid" and archived_at(cx, lkind, lval)): continue
        if closed_by_pointers(cx, sid): cx.execute("UPDATE search_plan SET status='planned' WHERE id=?", (sid,)); stats["steps_planned_again"] = stats.get("steps_planned_again", 0) + 1
    for sha, in cx.execute("SELECT DISTINCT pe.artifact_sha256 FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id WHERE pp.person_id=? AND pp.status='accepted'", (pid,)).fetchall():
        held = hold_household(cx, tree_id, pid, sha, by)                 # a household record accepted onto the person holds their own step for its census year, whenever the plan opens or keeps one
        if held: stats["steps_held_by_record"] = stats.get("steps_held_by_record", 0) + len(held)
    for skey, sid in have_steps.items():                                 # a step the generator no longer produces goes; done it stays; run but not done it is skipped, kept for its log
        if skey in wanted_keys: continue
        row = cx.execute("SELECT status, EXISTS (SELECT 1 FROM search_log l WHERE l.plan_step_id=search_plan.id), row_key, rationale, query_json FROM search_plan WHERE id=?", (sid,)).fetchone()
        if row[0] == "done": continue
        if any((f or {}).get("basis") == "owner" for f in json.loads(row[4] or "{}").values()): continue   # a step the owner's word wrote (attach.on_word, attach.cite_on_word) is theirs, never the generator's to drop
        if row[1]:
            if row[0] != "skipped": cx.execute("UPDATE search_plan SET status='skipped' WHERE id=?", (sid,)); stats["steps_skipped"] = stats.get("steps_skipped", 0) + 1
            continue
        cx.execute("DELETE FROM search_plan WHERE id=?", (sid,)); stats["steps_dropped"] += 1
        stats["dropped"].append({"step_key": skey, "row_key": row[2], "rationale": row[3]})
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "search_plan", pid, dumps(stats)))
    return stats

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who", nargs="?"); ap.add_argument("--tree"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--db", default=DB); ap.add_argument("--by", default="rule:plan@0.1.0")
    a = ap.parse_args()
    cx = connect(a.db); tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    pids = [r[0] for r in cx.execute("SELECT id FROM person WHERE tree_id=? AND merged_into IS NULL ORDER BY display_name", (tree_id,))] if a.all else [cat.find_person(a.who or sys.exit("give a person or --all"))]
    total = {}
    for pid in pids:
        cx.execute("BEGIN")
        try: st = plan_person(cx, tree_id, pid, a.by)
        except RegistryOutOfStep as e: cx.rollback(); sys.exit(str(e))
        cx.commit()
        for k, v in st.items():
            if isinstance(v, int): total[k] = total.get(k, 0) + v
        if not a.all: print(cat.person(pid)["name"], dumps(st))
    if a.all: print(len(pids), "persons", dumps(total))

if __name__ == "__main__": main()
