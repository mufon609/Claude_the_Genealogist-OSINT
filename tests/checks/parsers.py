"""Every parser read against its saved real page, the expectations beside the page.

A fixture under tests/fixtures/ is a page as the archive holds it; <stem>.expect.json beside it says how the page is
archived, which parser must claim it and what the reading must yield, in the vocabulary tests/fixtures/README.md
documents. This module walks every sidecar on one scratch catalog: the page archived as the sidecar says (a fixture with
a <stem>.manifest.json is a connector's response, archived from its manifest), read by tools/extract.py as the attach
would read it, and the personas, facts and relations compared with the sidecar by the one reader here. Nothing in this
file names a person or a page.
"""
import json, os, sqlite3
from common import BY, FIXTURES, Fails, connect, done, scratch, whole

def read(cx, eid):
    """What an extraction wrote: personas in sequence, each with its facts and the relations from it."""
    out = []
    for pid, seq, name, role, sex, region in cx.execute("SELECT id, sequence, name_text, role_in_record, sex, region_json FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,)):
        facts = [(t, v, d, p) for t, v, d, p in cx.execute("""SELECT f.fact_type, f.value_text, f.date_text, ps.raw FROM persona_fact f LEFT JOIN place_string ps ON ps.id=f.place_string_id
                                                              WHERE f.persona_id=? ORDER BY f.id""", (pid,))]
        rels = [(k, v, cx.execute("SELECT sequence FROM persona WHERE id=?", (o,)).fetchone()[0]) for k, v, o in cx.execute("SELECT kind, value_text, related_persona_id FROM persona_relation WHERE persona_id=?", (pid,))]
        out.append({"seq": seq, "name": name, "role": role or "", "sex": sex or "", "region": region or "", "facts": facts, "relations": rels})
    return out

def fact_matches(f, want):
    """A fact (type, value, date, place) against a fact pattern: type, value, value_starts, date, place (a prefix)."""
    t, v, d, place = f
    if t != want["type"]: return False
    if "value" in want and (v or "") != want["value"]: return False
    if "value_starts" in want and not (v or "").startswith(want["value_starts"]): return False
    if "date" in want and (d or "") != want["date"]: return False
    if "place" in want and not (place or "").startswith(want["place"]): return False
    return True

def has_fact(p, want): return any(fact_matches(f, want) for f in p["facts"])

def has_relation(p, want):
    return any(k == want["kind"] and o == want["to"] and ("value" not in want or v == want["value"]) for k, v, o in p["relations"])

def persona_matches(p, want):
    """A persona against a persona pattern: name, name_has, role, sex, region, facts, no_facts, relations."""
    if "name" in want and p["name"] != want["name"]: return False
    if any(s.lower() not in p["name"].lower() for s in want.get("name_has", [])): return False
    if "role" in want and p["role"] != want["role"]: return False
    if "sex" in want and p["sex"] != want["sex"]: return False
    if any(s not in p["region"] for s in want.get("region", [])): return False
    if any(not has_fact(p, f) for f in want.get("facts", [])): return False
    if any(has_fact(p, f) for f in want.get("no_facts", [])): return False
    if any(not has_relation(p, r) for r in want.get("relations", [])): return False
    return True

def shape(value, want):
    """A parsed value against a pattern: a dict matches the keys given, a list its length and each element, a string equals,
    null is None, {"$starts": s} a prefix."""
    if isinstance(want, dict):
        if "$starts" in want: return isinstance(value, str) and value.startswith(want["$starts"])
        return isinstance(value, dict) and all(k == "why" or shape(value.get(k), w) for k, w in want.items())
    if isinstance(want, list): return isinstance(value, list) and len(value) == len(want) and all(shape(v, w) for v, w in zip(value, want))
    return value == want

def brief(p): return f"{p['seq']}. {p['name']} [{p['role']}{', ' + p['sex'] if p['sex'] else ''}]"

def compare(ps, parsed, want, fail):
    """The reading against the sidecar's expectations; every failure named."""
    why = lambda w: f" ({w['why']})" if isinstance(w, dict) and w.get("why") else ""
    n = want.get("personas")
    if isinstance(n, int): fail(len(ps) == n, f"{n} persona(s) expected, {len(ps)} written")
    elif isinstance(n, dict): fail(len(ps) >= n["min"], f"at least {n['min']} persona(s) expected, {len(ps)} written")
    for seq, w in (want.get("sequence") or {}).items():
        p = next((p for p in ps if p["seq"] == int(seq)), None)
        if p is None: fail(False, f"persona {seq}: not written{why(w)}"); continue
        fail(persona_matches(p, w), f"persona {seq} is not as expected{why(w)}: got {brief(p)}, facts {p['facts']}, relations {p['relations']}, region {p['region'][:120]}")
    if "every" in want:
        w = want["every"]; off = [brief(p) for p in ps if not persona_matches(p, w)]
        fail(not off, f"every persona expected to match{why(w)}; these do not: {off[:6]}")
    for w in want.get("some") or []:
        got = [p for p in ps if persona_matches(p, w)]
        if "count" in w: fail(len(got) == w["count"], f"{w['count']} persona(s) expected to match{why(w)}, {len(got)} do: {[brief(p) for p in got]}")
        else: fail(bool(got), f"a persona expected to match{why(w)}; none does among {[brief(p) for p in ps][:12]}")
    for seq, kinds in (want.get("toward") or {}).items():
        counts = {}
        for p in ps:
            for k, v, o in p["relations"]:
                if o == int(seq) and p["seq"] != int(seq): counts[k] = counts.get(k, 0) + 1
        only = kinds.get("only"); expected = {k: v for k, v in kinds.items() if k != "only"}
        fail(all(counts.get(k, 0) == v for k, v in expected.items()) and (not only or set(counts) <= set(expected)),
             f"relations toward persona {seq} by kind expected {expected}{' and no other kind' if only else ''}; got {counts}")
    none = want.get("none") or {}
    for place in none.get("place", []): fail(not any((pl or "") == place for p in ps for _, _, _, pl in p["facts"]), f"no fact carries {place!r} as a place")
    for end in none.get("name_ends", []): fail(not any(p["name"].endswith(end) for p in ps), f"no name ends with {end!r}")
    if "parsed" in want: fail(shape(parsed, want["parsed"]), f"the parsed page is not as expected{why(want['parsed'])}: {json.dumps({k: parsed.get(k) for k in want['parsed'] if k != 'why'}, ensure_ascii=False)[:400]}")

def fixtures():
    """Every sidecar with the fixture it stands beside, in name order."""
    for f in sorted(os.listdir(FIXTURES)):
        if not f.endswith(".expect.json"): continue
        stem = f[:-len(".expect.json")]
        page = next((g for g in sorted(os.listdir(FIXTURES)) if g.startswith(stem + ".") and not g.endswith((".expect.json", ".manifest.json"))), None)
        with open(os.path.join(FIXTURES, f), encoding="utf-8") as fh: yield page or stem, json.load(fh)

def check(keep, show):
    """Every fixture read on one scratch; the number of failures, one line per fixture printed."""
    from treelib import archive_object
    from extract import extract
    d, db = scratch(keep); cx = connect(db); bad = 0
    for name, want in fixtures():
        path = os.path.join(FIXTURES, name)
        if not os.path.isfile(path): print(f"FAIL {name}: fixture missing"); bad += 1; continue
        notes = None; manifest = path.rsplit(".", 1)[0] + ".manifest.json"
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as fh: man = json.load(fh)
            mime, source, lkind, lvalue, notes = man["mime"], man["source_id"], man["locator"]["kind"], man["locator"]["value"], man.get("notes") or None
            if want.get("notes") and notes: notes = json.dumps({**json.loads(notes), **want["notes"]})
        else:
            a = want["archive"]; mime, source, lkind, lvalue = a["mime"], a["source"], a["locator"]["kind"], a["locator"]["value"]
        src = cx.execute("SELECT trust_tier, terms, cost FROM source WHERE id=?", (source,)).fetchone() or (None, None, None)
        cost = next((c for c in ("free", "paid", "member") if (src[2] or "").strip().lower().startswith(c)), "unknown")   # the registry's cost text, as the attach reads it
        with open(path, "rb") as fh: data = fh.read()
        cx.execute("BEGIN")
        sha, _ = archive_object(cx, data, mime=mime, source_id=source, collection_id=None, locator_kind=lkind, locator_value=lvalue, retrieved_by=BY,
                                terms=src[1], cost=cost, trust_tier=src[0], original_filename=name, notes=notes)
        eid, n = extract(cx, sha, BY); cx.commit()
        fails = Fails()
        ext = cx.execute("SELECT x.name, x.version, e.status, e.structured_json FROM extraction e JOIN extractor x ON x.id=e.extractor_id WHERE e.id=?", (eid,)).fetchone()
        fails(ext[2] == "complete", f"extraction {ext[2]}: {n.get('failed', '')}")
        fails(ext[0] == want["extractor"], f"read by {ext[0]}@{ext[1]}, expected {want['extractor']}")
        ps = read(cx, eid) if ext[2] == "complete" else []
        if show:
            print(f"== {name}: {ext[0]}@{ext[1]} {ext[2]} {n}")
            for p in ps:
                print(f"  {brief(p)}  {p['region'][:80]}")
                for t, v, dt, pl in p["facts"]: print(f"       {t:16} {' | '.join(x for x in (v, dt, pl) if x)}")
                for k, v, o in p["relations"]: print(f"       -> {k} ({v}) of #{o}")
        if ext[2] == "complete" and ext[0] == want["extractor"]:
            try: compare(ps, json.loads(ext[3] or "{}"), want, fails)
            except Exception as e: fails.append(f"the reader raised {type(e).__name__}: {e}")
        if fails: bad += 1; print(f"FAIL {name}: " + "; ".join(fails))
        else: print(f"ok   {name}: {ext[0]}@{ext[1]}, {len(ps)} persona(s)")
    w = whole(cx)
    if w: bad += 1; print("FAIL " + w)
    cx.close(); done(d, keep, "parsers")
    return bad
