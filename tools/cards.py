#!/usr/bin/env python3
"""Decision cards: every Undecided proposal about a person as one card, in plain text or as data.

usage: tools/cards.py "<person>" [--tree slug] [--db catalog/tree.db] [--full | --json]
       tools/cards.py --all [--tree slug] [--full | --json]          # every person with an Undecided proposal

One card per proposal, in the shape the owner approved (docs/RESEARCH-CHECKLIST.md §6b, the decision card): a one-line
highlight of what the record is and the links it makes; the person and the fact or link with the tree's value, each date or
place that is a claim beyond what an accepted statement gives said to be one (docs/RESEARCH-WORKFLOW.md §5–7); the record
with its holder, collection, own identity and trust tier; the primary document as the archived path and the holder's page;
what the record says field by field against the tree's value, as agrees, disagrees or absent; the relationships the record
states and who on it is already matched or accepted; what accepting closes, from the person's open questions when the step
carries one and from the checklist row otherwise; anything odd. No scores. The person screen's proposal panel shows the same
card from card() and render() here, so the two never drift. hints_on gives the record's hints for a person, the rows that
overlap them without identifying them, for the same screen. Nothing here writes.

The command line prints what the next decision needs: a row of a results page is one line (its proposal id, the name as the
page writes it, the collection, the year, the record's own id, what agrees and disagrees in the matcher's words); a record's
card states the comparison once (the fields both sides speak to, agreeing or not, and what only the matcher compares), leaves
the absent fields out, names the archived copy by its short hash, and ends with the standing rule's verdict and reason
(conclude.rule_accepts, read-only); the record, its holder and its hash are said once for the cards of one record. --full
prints every card whole, as render() and render_search() write it for the person screen.
"""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DATA_ROOT, DB, connect, object_path, resolve_tree
from catalog import Catalog, fetch_target, tier_sql, year, held_for, holds
from match import COUNTRY, candidate as match_candidate, compare, date_verdict, key as _key, personas_of, place_verdict as _place_verdict, proposals, same_surname
from conclude import rule_accepts, sibling_home
from plan import row_record

REL_WORD = {"parent": "parent", "child": "child", "spouse": "spouse", "sibling": "sibling"}

def _tokens(s): return [t for t in re.split(r"[,\s]+", (s or "").lower()) if re.sub(r"[^a-z]", "", t)]

def _fmt(date_text, place): return ", ".join(x for x in (date_text, place) if x) or None

def persona_facts(cx, persona_id):
    return [dict(r) for r in cx.execute("""SELECT pf.fact_type, pf.value_text, pf.date_text, pf.date_start, pf.date_end, pf.date_qualifier, ps.raw AS place, pf.region_json
                                           FROM persona_fact pf LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pf.persona_id=? ORDER BY pf.id""", (persona_id,))]

def persona_status(cx, tree_id, persona_id):
    """How a persona on the record stands to the tree: accepted as <person>, proposed as <person>, proposed as a new person,
    rejected, or no proposal."""
    pp = cx.execute("""SELECT pp.status, p.display_name FROM person_persona pp JOIN person p ON p.id=pp.person_id WHERE pp.persona_id=? AND p.tree_id=?""", (persona_id, tree_id)).fetchone()
    if pp and pp["status"] == "accepted": return f"accepted as {pp['display_name']}"
    pr = cx.execute("""SELECT pr.kind, pr.status, c.display_name FROM proposal pr LEFT JOIN person c ON c.id=json_extract(pr.payload_json,'$.person_id')
                       WHERE pr.tree_id=? AND json_extract(pr.payload_json,'$.persona_id')=? ORDER BY pr.created_at DESC LIMIT 1""", (tree_id, persona_id)).fetchone()
    if not pr: return "no proposal"
    if pr["status"] == "undecided": return f"proposed as {pr['display_name']}" if pr["kind"] == "persona_match" else "proposed as a new person"
    return f"{pr['status']}: {pr['kind'].replace('_', ' ')}" + (f" {pr['display_name']}" if pr["display_name"] else "")

def card(cx, tree_id, prop_id, cat=None):
    """The decision card for one proposal, as data. cat is the caller's Catalog when it builds many cards (the person screen's
    view): the cards then share its holdings and page groups, built once; one is made here when not given."""
    cx.row_factory = sqlite3.Row
    p = cx.execute("SELECT * FROM proposal WHERE id=? AND tree_id=?", (prop_id, tree_id)).fetchone()
    if not p or p["kind"] not in ("persona_match", "new_person"): return None
    pay = json.loads(p["payload_json"]); cat = cat or Catalog(cx, tree_id)
    pe = cx.execute("SELECT id, name_text, sex, role_in_record, region_json, artifact_sha256, extraction_id FROM persona WHERE id=?", (pay["persona_id"],)).fetchone()
    sha = pe["artifact_sha256"]
    a = cx.execute(f"""SELECT a.sha256, a.mime, {tier_sql('a')} AS trust_tier, a.locator_kind, a.locator_value, a.original_filename, a.retrieved_at, a.source_id, s.name AS source_name, c.name AS collection
                      FROM artifact a LEFT JOIN source s ON s.id=a.source_id LEFT JOIN collection c ON c.id=a.collection_id WHERE a.sha256=?""", (sha,)).fetchone()
    own_ids = [f"{r['kind']} {r['value']}" for r in cx.execute("SELECT kind, value FROM artifact_locator WHERE artifact_sha256=?", (sha,))]
    kinds = {x.split()[0] for x in own_ids}                        # the page's own identity says where it came from, whatever row it was archived under
    holder_id = "D03" if "ark" in kinds else "E01" if "memorial_id" in kinds else a["source_id"]
    holder_name = (cx.execute("SELECT name FROM source WHERE id=?", (holder_id,)).fetchone() or [a["source_name"]])[0]
    own_collection = None
    if "ark" in kinds:                                           # a FamilySearch record names its own collection on the page
        ex = cx.execute("SELECT structured_json FROM extraction WHERE artifact_sha256=? AND superseded_by IS NULL AND structured_json LIKE '%collection%' ORDER BY ran_at DESC LIMIT 1", (sha,)).fetchone()
        if ex: own_collection = re.sub(r"^[^•]*•\s*", "", (json.loads(ex[0]).get("collection") or "")).strip() or None
    region = json.loads(pe["region_json"] or "{}")
    mem = region.get("memorial_id") if pe["role_in_record"] == "result" else next((json.loads(r["region_json"] or "{}").get("memorial_id") for r in cx.execute("SELECT region_json FROM persona WHERE artifact_sha256=? AND role_in_record='memorial'", (sha,))), None)
    if mem: own_ids.append(f"memorial {mem}")
    cited = cat.cited().get(a["locator_value"], {}) if a["locator_kind"] == "apid" else {}
    page = region.get("url") if pe["role_in_record"] == "result" else (fetch_target(a["locator_value"], cited.get("url"))["url"] if a["locator_kind"] == "apid" else a["locator_value"] if a["locator_kind"] == "url" else None)
    ORDER = {"Name": 0, "Sex": 1, "Birth": 2, "Death": 3, "Burial": 4, "Age": 5}
    facts = sorted(persona_facts(cx, pe["id"]), key=lambda f: ORDER.get(f["fact_type"], 9))
    # ---- the person and the tree's value
    person_id = pay.get("person_id"); person = None; fields = []
    if person_id:
        pr = cat.person(person_id); ev = cat.events(person_id)
        first = lambda t: next((e for e in ev if e["type"] == t), None)
        claim = {"name": pr["name"], "sex": pr["sex"]}               # the tree's value, each event with what of it is accepted (docs/RESEARCH-WORKFLOW.md §5–7)
        for t in ("Birth", "Death", "Burial"):
            e = first(t); d = cx.execute("SELECT date_start, date_end, date_qualifier FROM event WHERE id=?", (e["id"],)).fetchone() if e else None
            r = cat.value_basis(e["id"]) if e and e["basis"] == "accepted" else None
            tags = cat.claim_tags(r)
            basis = ("accepted in part" if tags else "accepted") if r else (e["basis"] if e else None)
            claim[t.lower()] = {"date": e["date_text"], "start": d[0], "end": d[1], "qualifier": d[2], "place": e["place"]["text"] if e["place"] else None,
                                "basis": basis, "claimed": tags} if e else None
        person = {"id": person_id, "name": pr["name"], "span": [year(claim["birth"]["start"]) if claim["birth"] else None, year(claim["death"]["start"]) if claim["death"] else None], "claim": claim}
        # field by field
        name_f = next((f for f in facts if f["fact_type"] == "Name"), None)
        if name_f:                                                  # as the matcher compares it: every name the record gives, short forms, spelling variants, a married surname
            pers = next((x for x in personas_of(cx, pe["extraction_id"]) if x["id"] == pe["id"]), None)
            _, agree, disagree, absent, _ = compare(cat, pers, match_candidate(cat, person_id), {}) if pers else (None, [], [], [], None)
            g_ok = any(a.startswith("given name agrees") for a in agree); s_ok = any(a.startswith("surname agrees") for a in agree) or any(a.startswith("surname:") for a in absent)
            note = next((a[a.index("(") - 1:].strip() for a in agree if a.startswith("surname agrees as")), None) or next((a for a in absent if a.startswith("surname:")), None)
            fields.append({"field": "Name", "record": name_f["value_text"], "tree": pr["name"], "verdict": "agrees" if g_ok and s_ok else ("disagrees" if disagree or not g_ok else "absent"), "note": note})
        sx = pe["sex"] or next((f["value_text"] for f in facts if f["fact_type"] == "Sex"), None)
        fields.append({"field": "Sex", "record": sx, "tree": pr["sex"], "verdict": "absent" if not (sx and pr["sex"] in ("M", "F")) else ("agrees" if sx[:1].upper() == pr["sex"] else "disagrees")})
        for t in ("Birth", "Death", "Burial"):                  # a date and a place are two fields: each agrees, disagrees or is absent on its own
            f = next((x for x in facts if x["fact_type"] == t), None); c = claim[t.lower()]
            if not f and not c: continue
            v, note = date_verdict({"start": f["date_start"], "end": f["date_end"], "qualifier": f["date_qualifier"]} if f else None, c)   # the tree's own qualifier and range, as the matcher compares them
            fields.append({"field": f"{t} date", "record": f["date_text"] if f else None, "tree": c["date"] if c else None, "verdict": v, "note": note})
            pv, pnote = _place_verdict(f["place"] if f else None, c["place"] if c else None)
            fields.append({"field": f"{t} place", "record": f["place"] if f else None, "tree": c["place"] if c else None, "verdict": pv, "note": pnote})
            if f and f["value_text"]: fields.append({"field": t, "record": f["value_text"], "tree": None, "verdict": "absent"})
        for f in facts:
            if f["fact_type"] in ("Name", "Sex", "Birth", "Death", "Burial", "Identification Number"): continue
            fields.append({"field": f["fact_type"] if f["fact_type"] != "Unknown" else (json.loads(f["region_json"] or "{}").get("labels") or ["Unknown"])[0], "record": " ".join(x for x in (f["value_text"], f["date_text"], f["place"]) if x), "tree": None, "verdict": "absent"})
    else:
        for f in facts:
            if f["fact_type"] == "Identification Number": continue
            fields.append({"field": f["fact_type"], "record": " ".join(x for x in (f["value_text"], f["date_text"], f["place"]) if x), "tree": None, "verdict": "absent"})
    # ---- relationships the record states, both ways, with how the other persona stands
    rels = []
    for r in cx.execute("SELECT r.kind, r.value_text, o.id AS oid, o.name_text AS other FROM persona_relation r JOIN persona o ON o.id=r.related_persona_id WHERE r.persona_id=?", (pe["id"],)):
        rels.append({"direction": "is", "kind": r["kind"], "as_written": r["value_text"], "other": r["other"], "other_status": persona_status(cx, tree_id, r["oid"]).replace("no proposal", "waits on this decision"), "mapped": r["kind"] in REL_WORD, "oid": r["oid"]})
    for r in cx.execute("SELECT r.kind, r.value_text, o.id AS oid, o.name_text AS other FROM persona_relation r JOIN persona o ON o.id=r.persona_id WHERE r.related_persona_id=?", (pe["id"],)):
        rels.append({"direction": "has", "kind": r["kind"], "as_written": r["value_text"], "other": r["other"], "other_status": persona_status(cx, tree_id, r["oid"]).replace("no proposal", "waits on this decision"), "mapped": r["kind"] in REL_WORD, "oid": r["oid"]})
    def sibling_place(r):
        """Where a sibling stated on the record would put this persona: the other's accepted parents, or nothing."""
        pp = cx.execute("SELECT pp.person_id FROM person_persona pp JOIN person p ON p.id=pp.person_id WHERE pp.persona_id=? AND pp.status='accepted' AND p.tree_id=?", (r["oid"], tree_id)).fetchone()
        home = sibling_home(cx, tree_id, pp["person_id"]) if pp else None
        if not home: return None
        return " and ".join(n for n, in cx.execute("SELECT p.display_name FROM family_member fm JOIN person p ON p.id=fm.person_id WHERE fm.family_id=? AND fm.role='partner'", (home,))) or "the family with no parent named"
    # ---- what accepting closes
    closes = []; subject = pay.get("subject_person_id")
    if person_id:
        hs = cat.holdings(); ids = {k for k in holds(cx, sha, cat.page_groups()) if held_for(cx, k, person_id, hs) == sha}   # the citations this record holds for this person
        for st in cx.execute("SELECT id, row_key, question_id, status FROM search_plan WHERE person_id=? AND kind='fetch' ORDER BY seq", (person_id,)):
            loc = cx.execute("SELECT locator_kind, locator_value FROM search_plan WHERE id=?", (st["id"],)).fetchone()
            if not ((loc["locator_kind"] == "apid" and loc["locator_value"] in ids) or (loc["locator_kind"] != "apid" and cx.execute("SELECT 1 FROM artifact WHERE sha256=? AND locator_kind=? AND locator_value=?", (sha, loc["locator_kind"], loc["locator_value"])).fetchone())): continue
            q = cx.execute("SELECT kind, detail_json FROM research_question WHERE id=? AND status='open'", (st["question_id"],)).fetchone() if st["question_id"] else None
            if q: closes.append(f"the question {q['kind']} {json.loads(q['detail_json'] or '{}').get('detail') or ''}".strip() + f" ({st['row_key'].split(':')[0]} row)")
            else: closes.append(f"the {st['row_key'].split(':')[0]} row for {person['name']}: this record is the fetch")
        if pe["role_in_record"] == "result":                  # a search result: the memorial itself is fetched next, then attached like any memorial
            for st in cx.execute("SELECT row_key FROM search_plan WHERE person_id=? AND kind='search' AND sources_json LIKE '%\"E01\"%' ORDER BY seq", (person_id,)):
                closes.append(f"the {st['row_key'].split(':')[0]} row for {person['name']}: memorial {mem} is fetched next by the one-call method and attached like any memorial")
        evidence = [f"{f['fact_type']} {f['date_text'] or f['value_text'] or ''}".strip() for f in facts if f["fact_type"] in ("Name", "Birth", "Death", "Burial") and (f["date_text"] or f["value_text"] or f["place"])]
        if evidence: closes.append(("the page's statements, written undecided with the identity, never accepted: " if (a["trust_tier"] or "")[:2] == "T4" else "held evidence to accept on: " if pe["role_in_record"] != "result" else "the row states, as held evidence once accepted: ") + ", ".join(evidence))
        for q in cx.execute("SELECT kind, detail_json FROM research_question WHERE subject_person_id=? AND status='open' AND kind IN ('unverified_claim','missing_fact')", (person_id,)):
            d = json.loads(q["detail_json"] or "{}").get("detail") or ""
            if q["kind"] == "unverified_claim" and any(f["fact_type"] in d for f in facts if f["fact_type"] in ("Birth", "Death", "Burial")): closes.append(f"the question unverified_claim: {d}")
            if q["kind"] == "missing_fact" and any(f["fact_type"].lower() == d.split()[0] and (f["date_text"] if "date" in d else f["place"]) for f in facts): closes.append(f"the question missing_fact: {d}")
    else:
        joins = [r for r in rels if r["direction"] == "is" and r["kind"] in ("child", "parent", "spouse")]
        for r in joins:
            if r["other_status"].startswith("accepted as "): closes.append(f"creates {pe['name_text']} in this tree as {REL_WORD[r['kind']]} of {r['other_status'][12:]} (the record's {r['as_written']})")
            elif r["other_status"].startswith("proposed as "): closes.append(f"creates {pe['name_text']} in this tree; joins the family of {r['other_status'][12:]} as {REL_WORD[r['kind']]} once that match is accepted (the record's {r['as_written']})")
            else: closes.append(f"creates {pe['name_text']} in this tree; the record's {r['as_written']} of {r['other']}, who is {r['other_status']}")
        for r in [r for r in rels if r["kind"] == "sibling"]:
            where = sibling_place(r)
            if where: closes.append(f"creates {pe['name_text']} in this tree as a child of {where}, undecided: the record's {r['as_written']} of {r['other']} states a sibling, not the parents")
            else: closes.append(f"creates {pe['name_text']} in this tree with no family link yet: the record's {r['as_written']} of {r['other']} ({r['other_status']}) places nobody until the parents are accepted")
        if not joins and not any(r["kind"] == "sibling" for r in rels): closes.append(f"creates {pe['name_text']} in this tree with no family link: the record states none the matcher maps")
    # ---- anything odd
    odd = [f"{f['field']} disagrees: record {f['record']}, tree {f['tree']}" for f in fields if f["verdict"] == "disagrees"]
    m = re.search(r"Also fits: (.+?)\.$", p["rationale"] or "")
    if m: odd.append(f"also fits {m.group(1)}")
    odd += [f"the record's heading {r['as_written']!r} is not one the matcher maps to a family link" for r in rels if not r["mapped"]]
    if person and person["span"][0]:
        for f in facts:
            if f["fact_type"] in ("Death", "Burial", "Residence") and year(f["date_start"]) and year(f["date_start"]) < person["span"][0]: odd.append(f"{f['fact_type']} {f['date_text']} is before the tree's birth year {person['span'][0]}")
    if person and fields and fields[0]["field"] == "Name" and fields[0]["verdict"] == "agrees" and _key(_tokens(fields[0]["record"])[-1]) not in {_key(n[1]) for n in cat.person(person_id)["names"]}: odd.append(f"the record writes the name as {fields[0]['record']}; the tree has {person['name']}")
    if person and any(f["field"] == "Sex" and f["verdict"] == "absent" for f in fields) and not person["claim"]["sex"]: odd.append("the tree has no sex for this person")
    for f in fields:                                              # a place that is only a country agrees with any place in it; say so
        if f["field"].endswith(" place") and f["verdict"] == "agrees" and f["record"] and len([p for p in f["record"].split(",") if p.strip()]) == 1 and COUNTRY.fullmatch(f["record"].strip()): odd.append(f"{f['field']} on the record is only a country ({f['record']})")
    ext = cx.execute("SELECT ex.kind FROM extraction e JOIN extractor ex ON ex.id=e.extractor_id WHERE e.id=?", (pe["extraction_id"],)).fetchone()
    if ext and ext["kind"] == "human": odd.append(f"the record is {a['mime']}, read by hand")
    elif ext and ext["kind"] == "llm": odd.append(f"the record is {a['mime']}, read by the model")
    elif a["mime"] and not a["mime"].startswith("text/html"):
        deriv = cx.execute("SELECT derived_from FROM artifact WHERE sha256=?", (sha,)).fetchone()
        odd.append(f"the record is {a['mime']}, " + ("a derivative computed from an archived response" if deriv and deriv[0] else "a connector's answer"))
    # ---- highlight
    links = [f"{REL_WORD.get(r['kind'], r['kind'])} of {r['other']} ({r['other_status']})" for r in rels if r["direction"] == "is"] or \
            [f"{r['other']} as {r['as_written'].lower()} ({r['other_status']})" for r in rels if r["direction"] == "has"]
    rec_name = f"{a['source_name'] or a['source_id'] or 'record'}" + (f", {own_ids[-1]}" if own_ids else "")
    what = f"{pe['name_text']} ({pe['role_in_record']}) on {rec_name}"
    highlight = (f"{what} may be {person['name']}" if person else f"{what} is nobody in the tree yet") + (": " + "; ".join(links[:4]) if links else "") + ("" if len(links) <= 4 else f"; and {len(links) - 4} more")
    subj = cx.execute("SELECT display_name FROM person WHERE id=?", (subject,)).fetchone() if subject else None
    return {"id": p["id"], "kind": p["kind"], "status": p["status"], "highlight": highlight, "person": person, "subject": subj["display_name"] if subj else None,
            "persona": {"id": pe["id"], "name": pe["name_text"], "role": pe["role_in_record"], "sex": pe["sex"]},
            "record": {"holder": holder_name, "holder_id": holder_id, "collection": own_collection or a["collection"] or ("memorial search results page" if a["locator_kind"] == "url" else None),
                       "identity": ([x for x in (f"memorial {mem}" if mem else f"row {region['row']}" if region.get("row") else None, f"on the results page {a['locator_value']}") if x]
                                    if pe["role_in_record"] == "result" else [f"{a['locator_kind']} {a['locator_value']}"] + own_ids), "tier": a["trust_tier"],
                       "archived": os.path.relpath(object_path(sha), DATA_ROOT), "sha256": sha, "page": page, "retrieved_at": a["retrieved_at"], "filename": a["original_filename"]},
            "fields": fields, "relationships": rels, "closes": closes, "odd": odd or ["nothing"], "rationale": p["rationale"]}

def render(c):
    """The card as plain text."""
    w = 10; L = lambda k, v: f"{k:<{w}}{v}"
    out = [f"CARD {c['id']}  [{c['kind'].replace('_', ' ')}]", L("", c["highlight"])]
    if c["person"]:
        out.append(L("Person", f"{c['person']['name']}  the tree: {claim_text(c['person'])}"))
    else: out.append(L("Person", f"nobody yet; the record is about the family of {c['subject']}" if c["subject"] else "nobody yet"))
    r = c["record"]; out.append(L("Record", f"{r['holder'] or r['holder_id']}; {r['collection'] or 'collection unknown'}; {', '.join(r['identity'])}; tier {r['tier']}"))
    out.append(L("Document", f"{r['archived']}" + (f"  |  {r['page']}" if r["page"] else "")))
    for i, f in enumerate(c["fields"]):
        out.append(L("Fields" if i == 0 else "", f"{f['field']:<17}{f['verdict']:<11}record: {f['record'] or '-'}" + (f"  |  tree: {f['tree']}" if f["tree"] else "") + (f"  [{f['note']}]" if f.get("note") else "")))
    if not c["fields"]: out.append(L("Fields", "the record states nothing beyond the name"))
    for i, rl in enumerate(c["relationships"]):
        line = (f"{rl['as_written'] or rl['kind']} of {rl['other']}" if rl["direction"] == "is" else f"{rl['other']} listed under {rl['as_written'] or rl['kind']}") + f"  ({rl['other_status']})" + ("" if rl["mapped"] else "  [heading not mapped]")
        out.append(L("Relations" if i == 0 else "", line))
    if not c["relationships"]: out.append(L("Relations", "none stated"))
    for i, x in enumerate(c["closes"]): out.append(L("Closes" if i == 0 else "", x))
    if not c["closes"]: out.append(L("Closes", "nothing on the plan"))
    for i, x in enumerate(c["odd"]): out.append(L("Odd" if i == 0 else "", x))
    out.append(L("Matcher", c["rationale"] or ""))
    return "\n".join(out)

YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
VERDICT = re.compile(r"([A-Za-z ]{3,30}?) (agrees|disagrees)\b")
FIELD_WORDS = ("given name", "surname", "sex", "birth date", "birth place", "death date", "death place", "burial date", "burial place")

def matcher_words(rationale):
    """The matcher's comparison cut to its words, [(what, "agrees" | "disagrees")], from the sentences of its rationale after
    the first (which names the persona and the person): "given name", "surname", "residence place", "relationship"."""
    out = []
    for sentence in re.split(r"\.\s+(?=[A-Z])", rationale or "")[1:]:
        m = VERDICT.match(sentence.strip())
        if m: out.append((m.group(1).lower(), m.group(2)))
    return out

def _said(words, verdict):
    """The words of one verdict, the given name and surname as one "name"."""
    got = [w for w, v in words if v == verdict]
    if "given name" in got and "surname" in got: got = ["name"] + [w for w in got if w not in ("given name", "surname")]
    return got

def _row_id(c):
    """The record a results-page row stands for, as its own holder names it: a FamilySearch ark's id, a memorial, an AAD record."""
    page = c["record"].get("page") or ""; ident = " ".join(c["record"]["identity"]) if isinstance(c["record"]["identity"], list) else ""
    m = re.search(r"ark:/61903/1:1:([\w-]+)", page) or re.search(r"rid=(\d+)", page)
    return m.group(1) if m else (re.search(r"memorial \d+", ident) or re.search(r"row \d+", ident) or [""])[0]

def _when(c):
    """The year of the record's own event among the facts it states (a residence, a death, a marriage, a burial), a birth only
    when nothing else is dated."""
    stated = [f for f in c["fields"] if f["record"]]
    for first in ("Residence", "Death date", "Marriage", "Burial date", "Birth date", ""):
        for f in stated:
            m = f["field"].startswith(first) and YEAR.search(f["record"])
            if m: return ("b. " if first == "Birth date" else "") + m.group(1)
    return None

def rule_verdict(cx, tree_id, c):
    """The standing rule's word on a card, read-only: "takes: <why>" or "does not take: <why>" (conclude.rule_accepts)."""
    prop = cx.execute("SELECT * FROM proposal WHERE id=?", (c["id"],)).fetchone()
    taken, why = rule_accepts(cx, tree_id, prop)
    return ("takes: " if taken else "does not take: ") + why

def row_line(c, rule, with_person=False):
    """A results-page row as one line: the proposal id, the name as the page writes it, the collection and the year, the
    record's own id, what agrees and disagrees in a few words, and the rule's verdict unless it is the usual one for a row (a
    hint until a person reads the record)."""
    coll = c["record"]["collection"] or ""; when = _when(c)
    words = matcher_words(c["rationale"]); agrees, differs = _said(words, "agrees"), _said(words, "disagrees")
    who = (f"for {c['person']['name']}" if c["person"] else "a new person") if with_person or not c["person"] else None
    return "  ".join(x for x in (c["id"], c["persona"]["name"], coll + (f" {when}" if when and not coll.startswith(when) else ""), _row_id(c), who,
                                 ("agrees: " + ", ".join(agrees)) if agrees else None, ("disagrees: " + ", ".join(differs)) if differs else None,
                                 None if "is a hint until" in rule else f"rule {rule}") if x)

def _clip(text, n=110): return text if len(text) <= n else text[:n - 1] + "…"

def relation_lines(relationships):
    """The relationships a record states, one line per heading and standing: the people under it together, with how the other
    persona on the record stands to the tree."""
    groups = {}
    for rl in relationships: groups.setdefault((rl["direction"], rl["as_written"] or rl["kind"], rl["other_status"], rl["mapped"]), []).append(rl["other"])
    return [(f"{word} of {', '.join(names)}" if direction == "is" else f"{', '.join(names)} listed under {word}") + f"  ({status})" + ("" if mapped else "  [heading not mapped]")
            for (direction, word, status, mapped), names in groups.items()]

def claim_text(p):
    """The tree's value of a person, in words: born, died, buried, each with what of it is a claim (docs/RESEARCH-WORKFLOW.md
    §5–7, what of an event's value is accepted): nothing added where all of it is accepted, the parts accepted only in part
    ("the date a claim; the place accepted to Kentucky"), "a claim" where no accepted statement stands behind it."""
    cl = p["claim"]
    def said(word, e):
        if e.get("basis") == "accepted": tag = ""
        elif e.get("claimed"): tag = f" ({'; '.join(e['claimed'])})"
        elif e.get("basis") == "rejected": tag = " (rejected)"
        else: tag = " (a claim)"
        return f"{word} {_fmt(e['date'], e['place'])}{tag}"
    return "; ".join(said(w, cl[k]) for w, k in (("born", "birth"), ("died", "death"), ("buried", "burial")) if cl[k]) or "no dates"

def render_compact(c, rule, claim=True):
    """A record's card as the command line prints it: who it may be, the tree's value (unless the caller has said it once for
    everyone), the comparison once (the fields both sides speak to, then what only the matcher compares), what the record
    states when it is about nobody yet, who else is on it, what accepting closes, anything odd the comparison does not already
    say, and the rule's verdict."""
    w = 10; L = lambda k, v: f"{k:<{w}}{v}"; pe = c["persona"]; p = c["person"]
    out = [f"CARD {c['id']}  [{c['kind'].replace('_', ' ')}]  {pe['name']}" + (f" ({pe['role']})" if pe["role"] else "") + (f" may be {p['name']}" if p else " is nobody in the tree yet")]
    if p:
        if claim: out.append(L("Tree", claim_text(p)))
        agrees, differs, within = [], [], []
        for f in c["fields"]:
            if f["verdict"] == "absent": continue
            note = f.get("note"); note = None if not note or note.startswith("(record") else note
            text = f"{f['field']} {f['record']}" + (f" (tree {f['tree']})" if f["tree"] not in (None, f["record"]) else "") + (f" [{note}]" if note else "")
            {"agrees": agrees, "within": within}.get(f["verdict"], differs).append(text)   # a bound neither agrees nor differs (catalog.date_verdict)
        beyond = [(what, v) for what, v in matcher_words(c["rationale"]) if what not in FIELD_WORDS]
        agrees += _said(beyond, "agrees"); differs += _said(beyond, "disagrees")
        if agrees: out.append(L("Agrees", "; ".join(agrees)))
        if differs: out.append(L("Differs", "; ".join(differs)))
        if within: out.append(L("Within", "; ".join(within)))
        if not agrees and not differs and not within: out.append(L("Compare", "nothing the record and the tree both state"))
    else:
        out.append(L("Person", f"nobody yet; the record is about the family of {c['subject']}" if c["subject"] else "nobody yet"))
        stated = [f"{f['field']} {f['record']}" for f in c["fields"] if f["record"]]
        out.append(L("States", "; ".join(stated) if stated else "nothing beyond the name"))
    for i, x in enumerate(relation_lines(c["relationships"])): out.append(L("Relations" if i == 0 else "", x))
    for i, x in enumerate(c["closes"]): out.append(L("Closes" if i == 0 else "", x))
    if not c["closes"]: out.append(L("Closes", "nothing on the plan"))
    said = {f"{f['field']} disagrees: record {f['record']}, tree {f['tree']}" for f in c["fields"] if f["verdict"] == "disagrees"}
    for i, x in enumerate(x for x in c["odd"] if x != "nothing" and x not in said): out.append(L("Odd" if i == 0 else "", x))
    out.append(L("Rule", rule))
    return "\n".join(out)

def header_compact(sha, cards):
    """The record the cards under it are of, said once: its holder, collection, own identity, tier and short hash, and the
    holder's page when there is one."""
    r = cards[0]["record"]; ident = ", ".join(r["identity"]) if isinstance(r["identity"], list) else r["identity"]
    return f"== {r['holder'] or r['holder_id']}; {r['collection'] or 'collection unknown'}; {_clip(ident)}; tier {r['tier']}  ({len(cards)} card{'s' if len(cards) > 1 else ''}; record {sha[:12]})" + (f"  {_clip(r['page'], 80)}" if r.get("page") and r["page"] not in ident else "")

def lead_words(row):
    """What a fitting row of a results page has made of itself: the status of the fetch step for its own record, or that the plan has
    not written one yet."""
    return f"its own record: fetch {row['lead']}" if row["lead"] else "no lead yet"

def render_search_compact(c):
    """The candidate card for a results page as the command line prints it: the search, then a line per row with whether it
    fits, what agrees or disagrees and the row's own record id, then the leads the fitting rows make; what is absent and the
    runs' notes are left to --full."""
    s = c["search"]; q = s["query"]; p = c["person"]
    qs = " ".join(f"{k}={q[k]}" for k in q if q.get(k) not in (None, "", "false"))
    out = [f"SEARCH {s['holder']} search for {p['name']}: {qs}; {s['count'] if s['count'] is not None else s['rows_on_page']} matching records, page {s['page']} of {s['pages']}, {s['rows_on_page']} rows on this page; record {c['sha256'][:12]}"]
    for r in c["rows"]:
        head = f"{r['n']:>2}. {r['name']}  {r['birth'] or '?'} – {r['death'] or '?'}  {r['burial'] or 'no place'}  {r['memorial_id'] or ''}"
        agrees = _said([(m.group(1).lower(), m.group(2)) for a in r["agrees"] for m in [VERDICT.match(a)] if m], "agrees")
        why = ("FITS: " + ", ".join(agrees)) if r["fits"] else ("no fit" + (": " + "; ".join(r["disagrees"]) if r["disagrees"] else ""))
        out.append(head + "  " + why + (f"  [{r['decision']}]" if r["decision"] else ""))
    out.append("Leads     " + (", ".join(f"row {r['n']} ({lead_words(r)})" for r in c["leads"]) if c["leads"] else "no candidate fits; the run is logged as none and the candidates stay on this page"))
    return "\n".join(out)

def render_cli(cx, tree_id, cards, pid=None):
    """The cards as the command line prints them by default, grouped by record: a results-page row one line, a search page its
    rows, a record its header once and each card compact with the rule's verdict."""
    one = next((c["person"] for c in cards if c.get("kind") != "search" and c["person"]), None) if pid else None     # a person's own cards share the tree's value: said once
    blocks, rows = [f"{one['name']}: the tree: {claim_text(one)}"] if one else [], []
    for sha, _, group in grouped(cx, tree_id, cards, pid):
        if group[0].get("kind") == "search": blocks.append(render_search_compact(group[0])); continue
        if all(c["persona"]["role"] == "result" for c in group): rows += [row_line(c, rule_verdict(cx, tree_id, c), pid is None) for c in group]; continue
        blocks.append(header_compact(sha, group) + "\n\n" + "\n\n".join(render_compact(c, rule_verdict(cx, tree_id, c), not one) for c in group))
    if rows: blocks.append(f"{len(rows)} row(s) of results pages, decide each by its proposal id (the rule's verdict is named on a row only where it is not the usual one, a hint until a person reads its record):\n" + "\n".join(rows))
    return "\n\n".join(blocks)

def hints_on(cx, tree_id, sha, person_id):
    """The hints a held record carries for a person (docs/RESEARCH-WORKFLOW.md §0): on every persona of a current extraction
    of the record that has no proposal in this tree (one a newer matcher closed as superseded is none) and no link to anyone, as
    every row of a results page that points at records has, the matcher's comparison with the person, run once
    on view and stored nowhere, as its agreements, disagreements and absences. A row is a hint only when the surname agrees
    (or is the person's married name) and a place or a year agrees beyond the name, and only on a person whose baseline is
    reviewed; a name agreeing alone (a newspaper hit, a namesake on a results page) is not. A persona the matcher holds
    back (match.proposals' held: a namesake a name search alone reached, or nobody to create) is a hint on a reviewed person
    whatever agrees, with the matcher's reason as why. {persona id: {"hint": bool, "why": words or None, "agrees": [...],
    "disagrees": [...], "absent": [...]}}."""
    cx.row_factory = sqlite3.Row
    cat = Catalog(cx, tree_id); reviewed = cat.baseline(person_id)["complete"]; cand = match_candidate(cat, person_id)
    out = {}
    for e in cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND superseded_by IS NULL AND status<>'failed'", (sha,)).fetchall():
        held = {}
        if reviewed: proposals(cx, e["id"], held=held)          # what the matcher holds back and why, written nowhere
        for pe in personas_of(cx, e["id"]):
            if cx.execute("SELECT 1 FROM proposal WHERE tree_id=? AND json_extract(payload_json,'$.persona_id')=? AND NOT (status='rejected' AND decision_note='superseded')", (tree_id, pe["id"])).fetchone(): continue
            if cx.execute("SELECT 1 FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND o.tree_id=?", (pe["id"], tree_id)).fetchone(): continue
            _, agree, disagree, absent, _ = compare(cat, pe, cand, {})
            surname = any(a.startswith("surname agrees") for a in agree) or any(a.startswith("surname:") for a in absent)
            beyond = any(a.startswith(("birth date agrees", "death date agrees", "birth place agrees", "burial place agrees", "death place agrees", "residence place agrees")) for a in agree)
            why = held.get(pe["id"])
            out[pe["id"]] = {"hint": bool(reviewed and ((surname and beyond) or why)), "why": why, "agrees": agree, "disagrees": disagree, "absent": absent}
    return out

def search_card(cx, tree_id, sha, person_id=None):
    """The candidate card for one search results page: the search as run, the person it was run for, every row with its fields
    against the person as agrees, disagrees or absent, whether it fits, and for a row that fits the lead it makes (the fetch
    step for its own record, tools/plan.py's result_row_leads: its status, None before the plan is written again), and a person's
    decision on the row if there is one (a row is never proposed)."""
    cx.row_factory = sqlite3.Row
    a = cx.execute(f"SELECT ar.sha256, ar.locator_value, ar.retrieved_at, {tier_sql()} AS trust_tier, ar.source_id FROM artifact ar LEFT JOIN source s ON s.id=ar.source_id WHERE ar.sha256=?", (sha,)).fetchone()
    e = cx.execute("""SELECT e.id, e.structured_json, x.name AS parser FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.artifact_sha256=? AND x.name IN ('findagrave-search','aad-search','familysearch-search') AND e.superseded_by IS NULL ORDER BY e.ran_at DESC LIMIT 1""", (sha,)).fetchone()
    if not a or not e: return None
    parsed = json.loads(e["structured_json"] or "{}"); cat = Catalog(cx, tree_id)
    runs = cx.execute("""SELECT l.executed_at, l.executed_by, l.outcome, l.notes, sp.person_id FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE l.tree_id=? AND l.artifacts_json LIKE ? AND l.superseded_by IS NULL ORDER BY l.executed_at""", (tree_id, f'%"{sha}"%')).fetchall()
    person_id = person_id or (runs[0]["person_id"] if runs else None)
    if not person_id: return None
    cand = match_candidate(cat, person_id); pr = cat.person(person_id)
    rows = []
    for pe in personas_of(cx, e["id"]):
        region = json.loads(cx.execute("SELECT region_json FROM persona WHERE id=?", (pe["id"],)).fetchone()["region_json"] or "{}")
        fits, agree, disagree, absent, near = compare(cat, pe, cand, {})
        place = (pe["burial place"] or region.get("where")) if region.get("memorial_id") else (pe["residence place"] or pe["birth place"])   # a memorial row's cemetery; a record row's residence, else its birthplace
        link = cx.execute("SELECT pp.status, o.display_name FROM person_persona pp JOIN person o ON o.id=pp.person_id WHERE pp.persona_id=? AND o.tree_id=? AND pp.status<>'undecided'", (pe["id"], tree_id)).fetchone()
        decision = f"{link['status']} as {link['display_name']}" if link else None
        _, record, _, _ = row_record(e["parser"], region); step = cx.execute("SELECT status FROM search_plan WHERE person_id=? AND step_key=?", (person_id, f"fetch:row:{record}")).fetchone() if record else None
        rows.append({"n": region.get("row"), "name": pe["name"], "birth": pe["birth"]["text"], "death": pe["death"]["text"], "burial": place, "memorial_id": region.get("memorial_id") or region.get("rid") or region.get("ark"), "url": region.get("url"),
                     "fits": fits, "agrees": agree, "disagrees": disagree, "absent": absent, "decision": decision,
                     "lead": step["status"] if step else None})
    q = parsed.get("query") or {}
    return {"kind": "search", "sha256": sha, "person": {"id": person_id, "name": pr["name"], "birth": cand["birth"]["text"], "birth_place": cand["birth"]["place"], "death": cand["death"]["text"], "death_place": cand["death"]["place"], "burial_place": cand["burial place"]},
            "search": {"holder": {"findagrave-search": "Find a Grave", "familysearch-search": "FamilySearch", "aad-search": "the WWII Army enlistment file (AAD)"}[e["parser"]], "query": q, "url": a["locator_value"], "count": parsed.get("count"), "page": parsed.get("page"), "pages": parsed.get("pages"), "rows_on_page": len(rows)},
            "runs": [dict(r) for r in runs], "archived": os.path.relpath(object_path(sha), DATA_ROOT), "rows": rows,
            "leads": [r for r in rows if r["fits"]], "tier": a["trust_tier"]}

def render_search(c):
    """The candidate card as plain text."""
    w = 10; L = lambda k, v: f"{k:<{w}}{v}"
    q = c["search"]["query"]; s = c["search"]; p = c["person"]
    qs = " ".join(f"{k}={q[k]}" for k in q if q.get(k) not in (None, "", "false"))
    out = [f"SEARCH {s['holder']} search for {p['name']}: {qs}; {s['count'] if s['count'] is not None else s['rows_on_page']} matching records, page {s['page']} of {s['pages']}, {s['rows_on_page']} rows on this page",
           L("Person", f"{p['name']}  born {p['birth'] or '-'}" + (f", {p['birth_place']}" if p["birth_place"] else "") + f"; died {p['death'] or '-'}" + (f", {p['death_place']}" if p["death_place"] else "") + (f"; buried {p['burial_place']}" if p["burial_place"] else "")),
           L("Document", f"{c['archived']}  |  {s['url']}  (tier {c['tier']})")]
    for r in c["runs"]: out.append(L("Run", f"{r['executed_at']} {r['executed_by']} {r['outcome']}" + (f": {r['notes']}" if r["notes"] else "")))
    for i, r in enumerate(c["rows"]):
        head = f"{r['n']:>2}. {r['name']}  {r['birth'] or '?'} – {r['death'] or '?'}  {r['burial'] or 'no place'}  {r['url']}"
        why = ("FITS: " + "; ".join(r["agrees"])) if r["fits"] else ("does not fit: " + "; ".join(r["disagrees"] or ["nothing beyond the name agrees"]) + ("; agrees: " + "; ".join(r["agrees"]) if r["agrees"] and r["disagrees"] else ""))
        if r["absent"]: why += "; absent: " + ", ".join(r["absent"])
        out.append(L("Rows" if i == 0 else "", head)); out.append(L("", "    " + why + (f"  [{r['decision']}]" if r["decision"] else "")))
    out.append(L("Leads", ", ".join(f"row {r['n']} (record {r['memorial_id']}, {lead_words(r)})" for r in c["leads"]) if c["leads"] else "no candidate fits; the run is logged as none and the candidates stay on this page"))
    return "\n".join(out)

def search_cards_for(cx, tree_id, pid=None):
    """Candidate cards for the search results pages logged on a person's search steps (or anyone's), except a page whose every
    fitting row has its own record fetched (the lead done): its work is finished. A page no row fits stays, its rows kept as candidates."""
    rows = cx.execute(f"""SELECT DISTINCT l.artifacts_json, sp.person_id FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id JOIN person p ON p.id=sp.person_id
                          WHERE p.tree_id=? AND sp.kind='search' AND l.artifacts_json IS NOT NULL AND l.superseded_by IS NULL {'AND sp.person_id=?' if pid else ''}""", (tree_id, pid) if pid else (tree_id,)).fetchall()
    out = []
    for arts, person_id in rows:
        for sha in json.loads(arts):
            c = search_card(cx, tree_id, sha, person_id)
            if c and not (c["leads"] and all(r["lead"] == "done" for r in c["leads"])): out.append(c)
    return out

def cards_for(cx, tree_id, pid=None):
    """Undecided proposals for one person (as the matched person or the subject of a new-person proposal), or for everyone, with
    the candidate cards of the person's search runs."""
    if pid: rows = cx.execute("""SELECT id FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person')
                                 AND (json_extract(payload_json,'$.person_id')=? OR (json_extract(payload_json,'$.person_id') IS NULL AND json_extract(payload_json,'$.subject_person_id')=?)) ORDER BY created_at""", (tree_id, pid, pid)).fetchall()
    else: rows = cx.execute("SELECT id FROM proposal WHERE tree_id=? AND status='undecided' AND kind IN ('persona_match','new_person') ORDER BY created_at", (tree_id,)).fetchall()
    return search_cards_for(cx, tree_id, pid) + [c for c in (card(cx, tree_id, r[0]) for r in rows) if c]

def grouped(cx, tree_id, cards, pid=None):
    """The cards in groups, one per record, the record the person's steps most recently logged first (the record being worked),
    then the others by the latest run on them, a record no step logged last; inside a group the cards as they came.
    Returns [(sha256, one line naming the record, [cards])]."""
    by = {}
    for c in cards:
        sha = c["sha256"] if c.get("kind") == "search" else c["record"]["sha256"]
        by.setdefault(sha, []).append(c)
    latest = {}
    for sha in by:
        r = cx.execute(f"""SELECT MAX(l.executed_at) FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE l.tree_id=? AND l.artifacts_json LIKE ? AND l.superseded_by IS NULL {'AND sp.person_id=?' if pid else ''}""",
                       (tree_id, f'%"{sha}"%', *([pid] if pid else []))).fetchone()
        latest[sha] = r[0] or ""
    out = []
    order = sorted(by, key=lambda s: latest[s], reverse=True)
    for sha in order:
        c = by[sha][0]
        name = (f"{c['search']['holder']} search results page" if c.get("kind") == "search" else
                f"{c['record']['holder']}: {c['record']['collection'] or ''}" + (f", {', '.join(c['record']['identity']) if isinstance(c['record']['identity'], list) else c['record']['identity']}" if c["record"].get("identity") else ""))
        out.append((sha, name.strip(" :,"), by[sha]))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("who", nargs="?"); ap.add_argument("--all", action="store_true"); ap.add_argument("--tree"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--full", action="store_true", help="every card whole, as the person screen shows it")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args()
    cx = connect(a.db, rows=True); tree_id, slug = resolve_tree(cx, a.tree); cat = Catalog(cx, tree_id)
    if not a.all and not a.who: sys.exit("give a person or --all")
    pid = None if a.all else cat.find_person(a.who)
    out = cards_for(cx, tree_id, pid)
    if a.json: print(json.dumps(out, ensure_ascii=False, indent=1)); return
    if not out: print("no undecided proposal" + ("" if a.all else " for this person")); return
    if not a.full: print(render_cli(cx, tree_id, out, pid)); return
    blocks = []
    for sha, name, cards in grouped(cx, tree_id, out, pid):
        blocks.append(f"== {name}  ({len(cards)} card{'s' if len(cards) > 1 else ''}; record {sha[:12]})\n\n" + "\n\n".join(render_search(c) if c.get("kind") == "search" else render(c) for c in cards))
    print("\n\n".join(blocks))

if __name__ == "__main__": main()
