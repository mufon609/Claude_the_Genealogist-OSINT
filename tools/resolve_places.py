#!/usr/bin/env python3
"""Resolve raw place strings to a place hierarchy using OpenStreetMap Nominatim.

usage: tools/resolve_places.py [--tree slug] [--limit N] [--dry-run] [--only "raw string"]

Rules
  * Every string is parsed into components; countries and US states are normalized.
  * Nominatim (free, ODbL, 1 req/s, cached under derivatives/geocode/) is asked for
    candidates. A candidate is verified by checking that EVERY component the string
    gave appears in the candidate's address hierarchy.
  * Auto-resolve only when exactly one candidate verifies fully. Everything else,
    including a place and its enclosing unit of the same name verifying together
    (a township and the borough inside it, a county and its seat), becomes a
    `place_resolution` proposal (tree-scoped) with every verified candidate listed;
    the owner decides between them on the person screen. Never widen auto-accept
    past a unique full match.
  * data/place-overrides.json can reject non-places, force review, add candidate
    queries, and attach notes. It is the only hand-authored input.
  * Every decision is undecided | accepted | rejected; match scores stay in notes JSON.
  * Every string the resolver accepts, rejects or resets (--reset) gets one audit row
    under the person or agent who ran it (--by), the resolver's tag and the change in
    the diff, so a reset-and-rerun can be read back afterwards.
"""
import argparse, difflib, hashlib, json, os, re, sqlite3, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, derivatives_dir, dumps, now, resolve_tree, ulid

RESOLVER = ("rule", "nominatim-resolver", "0.1.0")
UA = "tree-genealogy-dev/0.1 (personal genealogy research; single user)"
def cache_dir():
    """Where the geocoder's answers are kept, under the data root of the run (a scratch run keeps its own)."""
    return os.path.join(derivatives_dir(), "geocode", "nominatim")
ENDPOINT = "https://nominatim.openstreetmap.org/search"

COUNTRY_SYN = {"usa": "United States", "u.s.a.": "United States", "us": "United States", "united states": "United States",
               "united states of america": "United States", "allemagne": "Germany", "deutschland": "Germany",
               "germany": "Germany", "netherlands": "Netherlands", "ireland": "Ireland", "japan": "Japan",
               "poland": "Poland", "england": "United Kingdom", "great britain and ireland": "Ireland", "canada": "Canada"}
DROP = {"north america", "british colonies", "europe", "colonial america"}
US_STATES = {"alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia",
             "hawaii","idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts",
             "michigan","minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey",
             "new mexico","new york","north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island",
             "south carolina","south dakota","tennessee","texas","utah","vermont","virginia","washington","west virginia",
             "wisconsin","wyoming"}
US_ABBR = {"pa": "Pennsylvania", "ny": "New York", "nj": "New Jersey", "ma": "Massachusetts", "ky": "Kentucky", "tn": "Tennessee",
           "oh": "Ohio", "va": "Virginia", "fl": "Florida", "co": "Colorado", "ga": "Georgia", "tx": "Texas", "nc": "North Carolina",
           "sc": "South Carolina", "wa": "Washington"}
HISTORIC_REGION = {"silesia": "Silesia", "silesa": "Silesia", "schlesien": "Silesia"}
WARD_RE = re.compile(r"^(.*?)\s+((?:Lower|Upper)\s+Ward|Ward|Assembly District|District|Precinct)\s*\d*$", re.I)
ADDR_RE = re.compile(r"^\d+\s+\S|\b(Road|Street|Avenue|Lane|Drive|St\.?|Rd\.?|Ave\.?)$", re.I)
LOCALITY_KEYS = ("city", "town", "village", "hamlet", "municipality", "borough", "isolated_dwelling", "locality")
SUB_KEYS = ("suburb", "neighbourhood", "city_district", "quarter")

SYN = {"nordrhein-westfalen": "north rhine-westphalia", "sachsen": "saxony", "noord-holland": "north holland",
       "zuid-holland": "south holland", "friesland": "frisia", "köln": "cologne", "koln": "cologne", "bayern": "bavaria",
       "new york city": "new york", "philadelphia city": "philadelphia"}
STRIP = r"\b(county|township|twp|municipality|gemeente|co\.?|cty|prefecture|province|district|borough|metropolitan|stadtkreis|landkreis|kreis|gmina|powiat|town of|village of|city of|borough of|the municipal district of)\b"
def norm(s):
    s = re.sub(r"\s+", " ", re.sub(STRIP, "", s.lower())).strip(" ,.")
    return SYN.get(s, s)
def similar(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb: return False
    if a.strip().endswith(".") and len(na) >= 3 and nb.startswith(na): return True     # truncation: "Hemp." ~ Hempstead
    return na == nb or nb.startswith(na + " ") or difflib.SequenceMatcher(None, na, nb).ratio() >= 0.86

def parse(raw):
    """-> dict(components=[...], country, region, details=[...], warnings=[...])"""
    p = {"components": [], "country": None, "region": None, "details": [], "warnings": []}
    s = re.sub(r"\(alt\..*?\)", "", raw)
    for phrase in sorted(COUNTRY_SYN, key=len, reverse=True):          # "Kalagh Cork Great Britain and Ireland"
        if "," not in s and s.lower().endswith(" " + phrase):
            s = s[: -len(phrase)].strip(); p["country"] = COUNTRY_SYN[phrase]; s = ", ".join(s.split()); break
    toks, prev = [], None
    for t in [t.strip() for t in s.split(",")]:
        if not t or (prev and t.lower() == prev.lower()): continue
        toks.append(t); prev = t
    for t in toks:
        tl = t.lower().rstrip(".")
        if tl in COUNTRY_SYN: p["country"] = COUNTRY_SYN[tl]; continue
        if tl in DROP: continue
        if tl in HISTORIC_REGION: p["region"] = HISTORIC_REGION[tl]; continue
        if tl in US_ABBR: t = US_ABBR[tl]
        m = WARD_RE.match(t)
        if m: p["details"].append(t); t = m.group(1)
        if ADDR_RE.search(t) and len(toks) > 1: p["details"].append(t); continue
        t = re.sub(r"\b(Co\.?|Cty)$", "County", t); t = re.sub(r"\bTwp$", "Township", t)
        t = re.sub(r"^Near\s+", "", t, flags=re.I)
        if t.lower() in US_STATES and not p["country"]: p["country"] = "United States"
        p["components"].append(t)
    if p["region"] == "Silesia" and p["country"] == "Germany": p["country"] = None; p["warnings"].append("Silesia given as Germany; now mostly Poland")
    return p

def query_string(p, comps=None):
    parts = list(comps if comps is not None else p["components"])
    if p["region"]: parts.append("Lower Silesia" if p["region"] == "Silesia" else p["region"])
    if p["country"]: parts.append(p["country"])
    return ", ".join(parts)

def query_variants(p):
    """Primary query, then progressively looser ones. Verification, not the query, decides acceptance."""
    comps = []
    for c in p["components"]:                      # drop tokens that normalize to the previous one (Leiden, Leiden Municipality)
        if not comps or norm(c) != norm(comps[-1]): comps.append(re.sub(r"\s+(Municipality|Stadtkreis)$", "", c))
    out = [query_string(p, comps)]
    if len(comps) >= 3 and "county" not in comps[1].lower():
        out.append(query_string(p, [comps[0], comps[1] + " County"] + comps[2:]))
    if len(comps) >= 3: out.append(query_string(p, [comps[0]] + comps[2:]))
    if len(comps) >= 2: out.append(query_string(p, [comps[0]]))
    seen, uniq = set(), []
    for q in out:
        if q.lower() not in seen: seen.add(q.lower()); uniq.append(q)
    return uniq

def nominatim(q):
    os.makedirs(cache_dir(), exist_ok=True)
    key = hashlib.sha1(q.lower().encode()).hexdigest()
    path = os.path.join(cache_dir(), key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh: return json.load(fh)["results"]
    url = ENDPOINT + "?" + urllib.parse.urlencode({"q": q, "format": "jsonv2", "addressdetails": 1, "extratags": 1,
                                                    "namedetails": 1, "limit": 6, "accept-language": "en"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    time.sleep(1.1)
    with urllib.request.urlopen(req, timeout=30) as r: results = json.load(r)
    with open(path, "w", encoding="utf-8") as fh: json.dump({"query": q, "fetched_at": now(), "results": results}, fh, ensure_ascii=False)
    return results

def verify(p, cand):
    """Score a candidate: fraction of given components found in its hierarchy; country must match."""
    addr = cand.get("address") or {}; names = cand.get("namedetails") or {}
    hier = [v for k, v in addr.items() if k not in ("postcode", "country_code", "ISO3166-2-lvl4", "ISO3166-2-lvl6", "house_number")]
    hier += [v for k, v in names.items() if k.startswith("name") or k.startswith("old_name") or k.startswith("alt_name")]
    checks = {}
    for c in p["components"]:
        checks[c] = any(similar(c, h) for h in hier)
    if p["country"]:
        checks["country:" + p["country"]] = similar(p["country"], addr.get("country", "")) or \
            (p["country"] == "United Kingdom" and addr.get("country_code") == "gb")
    n = len(checks); ok = sum(checks.values())
    score = ok / n if n else 0.0
    if p["country"] and not checks.get("country:" + p["country"]): score = min(score, 0.4)
    return score, checks

def leaf_type(cand):
    cls, typ = cand.get("category") or cand.get("class"), cand.get("type")
    if cand.get("addresstype") in ("country",): return "country"
    if cand.get("addresstype") in ("state", "province", "region"): return "state"
    if cand.get("addresstype") == "county": return "county"
    if cand.get("addresstype") in LOCALITY_KEYS: return {"city": "city", "town": "town", "village": "village", "hamlet": "hamlet",
                                                            "municipality": "township", "borough": "town"}.get(cand["addresstype"], "town")
    if cand.get("addresstype") in SUB_KEYS: return "neighborhood"
    if cls == "amenity" and typ == "place_of_worship": return "church"
    if cls == "landuse" and typ == "cemetery": return "cemetery"
    if cls in ("highway", "building") or cand.get("addresstype") in ("road", "building"): return "address"
    return "unknown"

class Store:
    def __init__(self, cx): self.cx = cx; self.ts = now()
    LOCAL_TYPES = ("city", "town", "village", "hamlet", "township", "neighborhood")
    def place(self, name, ptype, parent, lat=None, lon=None, wikidata=None):
        if re.search(r"\bTownship$", name): ptype = "township"
        elif re.search(r"\bCounty$", name): ptype = "county"
        row = self.cx.execute("SELECT id, place_type FROM place WHERE name=? AND COALESCE(parent_id,'')=COALESCE(?,'')", (name, parent)).fetchone()
        if row and (row[1] == ptype or (row[1] in self.LOCAL_TYPES and ptype in self.LOCAL_TYPES)):
            if wikidata: self.cx.execute("UPDATE place SET wikidata_id=COALESCE(wikidata_id,?) WHERE id=?", (wikidata, row[0]))
            if lat is not None: self.cx.execute("UPDATE place SET latitude=COALESCE(latitude,?), longitude=COALESCE(longitude,?) WHERE id=?", (lat, lon, row[0]))
            return row[0]
        pid = ulid()
        self.cx.execute("INSERT INTO place (id,name,place_type,parent_id,latitude,longitude,wikidata_id,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                        (pid, name, ptype, parent, lat, lon, wikidata, self.ts))
        self.cx.execute("INSERT INTO place_name (id,place_id,name,is_primary) VALUES (?,?,?,?)", (ulid(), pid, name, True))
        return pid
    def hierarchy(self, cand):
        """Build country > state > county > locality > sub from a Nominatim candidate; return leaf id."""
        a = cand.get("address") or {}; parent = None
        chain = [("country", a.get("country")), ("state", a.get("state") or a.get("province") or a.get("region")),
                 ("county", a.get("county") or a.get("state_district"))]
        loc = next((a[k] for k in LOCALITY_KEYS if a.get(k)), None)
        sub = next((a[k] for k in SUB_KEYS if a.get(k)), None)
        if loc: chain.append(({"city": "city", "town": "town", "village": "village", "hamlet": "hamlet", "municipality": "township"}
                              .get(next(k for k in LOCALITY_KEYS if a.get(k)), "town"), loc))
        if sub and sub != loc: chain.append(("neighborhood", sub))
        lt = leaf_type(cand); leaf_name = cand.get("name") or cand.get("display_name", "").split(",")[0]
        names_in_chain = [c[1] for c in chain if c[1]]
        if leaf_name and lt not in ("unknown",) and not any(similar(leaf_name, n) for n in names_in_chain):
            chain.append((lt, leaf_name))
        for ptype, name in chain:
            if not name: continue
            is_leaf = (ptype, name) == chain[-1] or name == chain[-1][1]
            parent = self.place(name, ptype, parent,
                                float(cand["lat"]) if is_leaf else None, float(cand["lon"]) if is_leaf else None,
                                (cand.get("extratags") or {}).get("wikidata") if is_leaf else None)
        if cand.get("osm_type") and cand.get("osm_id") and parent:
            if not self.cx.execute("SELECT 1 FROM external_id WHERE entity_kind='place' AND entity_id=? AND system='osm'", (parent,)).fetchone():
                self.cx.execute("INSERT INTO external_id (id,entity_kind,entity_id,system,value,created_at) VALUES (?,?,?,?,?,?)",
                                (ulid(), "place", parent, "osm", f"{cand['osm_type']}/{cand['osm_id']}", self.ts))
        return parent

NONPLACE_CLASSES = {"railway", "natural", "highway", "shop", "tourism", "leisure", "building", "aeroway", "waterway", "man_made"}

def is_ancestor(a, b):
    """a is an enclosing unit of b: a's name appears in b's address hierarchy (not as b's own leaf)."""
    an = norm(a.get("name") or ""); ab = b.get("address") or {}
    if not an or a.get("osm_id") == b.get("osm_id"): return False
    vals = [v for k, v in ab.items() if k not in ("country_code", "postcode")]
    leaf = b.get("name") or ""
    return any(norm(v) == an for v in vals if v != leaf or norm(v) != norm(leaf))

def select_best(p, full):
    """Given >1 fully-verified candidates, filter out noise (non-place candidate classes, census-only rows) to explain why
    the string needs review, but never choose among what survives. A place and its enclosing unit of the same name
    (a township and the borough inside it, a county and its seat) is exactly the case that stays Undecided with both
    candidates offered: CLAUDE.md reserves any choice among multiple verified candidates for the owner, on the fact row.
    Returns (None, reason)."""
    cands = [c for _, _, c in full]
    head = p["components"][0].lower() if p["components"] else ""
    wants_feature = any(k in head for k in ("church", "cemetery", "road", "street"))
    kept = [c for c in cands if wants_feature or c.get("category") not in NONPLACE_CLASSES]
    if any(c.get("type") != "census" for c in kept): kept = [c for c in kept if c.get("type") != "census"]
    if not kept: return None, "only non-place candidates"
    if len(kept) == 1: return None, "one place among non-place candidates: the owner chooses"
    admin = [c for c in kept if c.get("category") == "boundary" and c.get("type") == "administrative"]
    if admin: kept = admin
    if len(kept) == 1: return None, "one administrative boundary among other candidates: the owner chooses"
    names = {norm(c.get("name") or "") for c in kept}
    chain = all(is_ancestor(a, b) or is_ancestor(b, a) for i, a in enumerate(kept) for b in kept[i + 1:])
    if len(names) == 1 and chain: return None, "same-name nested/coterminous units: the owner chooses"
    return None, f"{len(kept)} distinct candidates verify"

def candidate_summary(c, score, checks):
    return {"display_name": c.get("display_name"), "osm": f"{c.get('osm_type')}/{c.get('osm_id')}", "type": leaf_type(c),
            "lat": c.get("lat"), "lon": c.get("lon"), "wikidata": (c.get("extratags") or {}).get("wikidata"), "score": round(score, 2),
            "checks": checks}

def apply_to_events(cx, tree_id, actor, ts):
    """Fill event.place_id where every supporting fact's place string resolved to the same place. Logged per event."""
    rows = cx.execute("""
        SELECT e.id, GROUP_CONCAT(DISTINCT ps.place_id), COUNT(DISTINCT ps.id), COUNT(DISTINCT CASE WHEN ps.status='accepted' THEN ps.id END)
        FROM event e
        JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id AND a.status <> 'rejected'
        JOIN persona_fact pf ON pf.id=a.persona_fact_id
        JOIN place_string ps ON ps.id=pf.place_string_id
        WHERE e.tree_id=? AND e.place_id IS NULL
        GROUP BY e.id""", (tree_id,)).fetchall()
    n = 0
    for eid, place_ids, n_strings, n_resolved in rows:
        if not place_ids or "," in place_ids or n_resolved != n_strings: continue
        cx.execute("UPDATE event SET place_id=?, updated_at=? WHERE id=?", (place_ids, ts, eid))
        cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                   (ulid(), tree_id, ts, actor, "update", "event", eid, dumps({"place_id": place_ids, "from": "accepted place_string"})))
        n += 1
    return n, len(rows) - n

def audit_string(cx, tree_id, ts, by, psid, diff):
    """One audit row per place string whose status or place the resolver changes, under the person or agent who ran it (the
    resolver's own tag is in the diff), so a reset, which clears the resolver's rows, leaves the record of what it undid."""
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "place_string", psid, dumps(diff)))

def reset_ai_resolutions(cx, tree_id, by, ts):
    """Undo AI-made resolutions only. Human resolutions (resolver 'user:...') are kept. One audit row per string reset."""
    cx.execute("UPDATE event SET place_id=NULL WHERE tree_id=? AND id IN (SELECT entity_id FROM audit_log WHERE action='update' AND entity_kind='event' AND actor LIKE 'ai:%')", (tree_id,))
    cx.execute("DELETE FROM audit_log WHERE tree_id=? AND actor LIKE 'ai:%' AND action IN ('update','resolve')", (tree_id,))
    cx.execute("DELETE FROM proposal WHERE tree_id=? AND kind='place_resolution' AND status='undecided'", (tree_id,))
    for psid, raw, status, place_id, resolver in cx.execute("SELECT id, raw, status, place_id, resolver FROM place_string WHERE resolver LIKE 'ai:%' AND (status<>'undecided' OR place_id IS NOT NULL)").fetchall():
        audit_string(cx, tree_id, ts, by, psid, {"raw": raw, "reset": True, "resolver": resolver, "from": {"status": status, "place_id": place_id}, "to": {"status": "undecided", "place_id": None}})
    cx.execute("UPDATE place_string SET place_id=NULL, status='undecided', resolver=NULL, resolved_at=NULL, notes=NULL, variant_kind=NULL WHERE resolver LIKE 'ai:%'")
    # orphaned places (no string, no event points at them, and no child)
    while True:
        orphans = [r[0] for r in cx.execute("""SELECT p.id FROM place p
            WHERE NOT EXISTS (SELECT 1 FROM place_string s WHERE s.place_id=p.id)
              AND NOT EXISTS (SELECT 1 FROM event e WHERE e.place_id=p.id)
              AND NOT EXISTS (SELECT 1 FROM place c WHERE c.parent_id=p.id)""").fetchall()]
        if not orphans: break
        for pid in orphans:
            cx.execute("DELETE FROM place_name WHERE place_id=?", (pid,))
            cx.execute("DELETE FROM external_id WHERE entity_kind='place' AND entity_id=?", (pid,))
            cx.execute("DELETE FROM place WHERE id=?", (pid,))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--tree")
    ap.add_argument("--limit", type=int); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--only")
    ap.add_argument("--reset", action="store_true", help="undo AI-made resolutions (keeps human ones) before running")
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
    tree_id, slug = resolve_tree(cx, a.tree)
    with open(os.path.join(ROOT, "data", "place-overrides.json"), encoding="utf-8") as fh: ov = json.load(fh)
    row = cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", RESOLVER).fetchone()
    ext_id = row[0] if row else ulid()
    if not row:
        cx.execute("INSERT INTO extractor (id,kind,name,version,config_json,created_at) VALUES (?,?,?,?,?,?)",
                   (ext_id, *RESOLVER, dumps({"endpoint": ENDPOINT, "verify": "all components must match; unique full match auto-resolves"}), now()))
    resolver_tag = f"ai:{RESOLVER[1]}@{RESOLVER[2]}"
    st = Store(cx); ts = now()
    if a.reset: reset_ai_resolutions(cx, tree_id, a.by, ts)
    rows = cx.execute("SELECT id, raw FROM place_string WHERE status='undecided' AND place_id IS NULL AND resolver IS NULL " + ("AND raw=?" if a.only else "") + " ORDER BY raw",
                      (a.only,) if a.only else ()).fetchall()
    if a.limit: rows = rows[: a.limit]
    stats = {"accepted": 0, "undecided": 0, "rejected": 0, "no_candidates": 0}
    report = []
    for psid, raw in rows:
        note = ov["note"].get(raw)
        if raw in ov["reject"]:
            cx.execute("UPDATE place_string SET status='rejected', resolver=?, resolved_at=?, notes=? WHERE id=?",
                       (resolver_tag, ts, dumps({"reason": ov["reject"][raw]}), psid)); stats["rejected"] += 1
            audit_string(cx, tree_id, ts, a.by, psid, {"raw": raw, "resolver": resolver_tag, "from": {"status": "undecided", "place_id": None}, "to": {"status": "rejected", "place_id": None}, "reason": ov["reject"][raw]})
            report.append(("REJECT", raw, ov["reject"][raw])); continue
        p = parse(raw)
        if not p["components"] and not p["country"] and not p["region"]:
            report.append(("SKIP", raw, "nothing parseable")); continue
        variants = query_variants(p) if (p["components"] or p["country"]) else ["Silesia"]
        extras = ov["extra_queries"].get(raw, [])
        cands, queries = [], []
        for q in variants:                     # stop at the first variant that yields anything
            queries.append(q)
            try: got = nominatim(q)
            except Exception as e: report.append(("ERROR", raw, f"{q}: {e}")); got = []
            for c in got:
                if not any(x.get("osm_id") == c.get("osm_id") and x.get("osm_type") == c.get("osm_type") for x in cands): cands.append(c)
            if cands: break
        from_extra = set()
        for q in extras:                        # override queries carry tree context: rank their candidates first among ties
            queries.append(q)
            try: got = nominatim(q)
            except Exception as e: report.append(("ERROR", raw, f"{q}: {e}")); got = []
            for c in got:
                if not any(x.get("osm_id") == c.get("osm_id") and x.get("osm_type") == c.get("osm_type") for x in cands): cands.append(c)
                from_extra.add((c.get("osm_type"), c.get("osm_id")))
        if not p["components"] and not p["country"] and p["region"]:      # bare "Schlesien"
            p["components"] = ["Silesia"]
        head = p["components"][0].lower() if p["components"] else ""
        wants_feature = any(k in head for k in ("church", "cemetery", "road", "street", "lane", "avenue"))
        placeish = [c for c in cands if wants_feature or c.get("category") not in NONPLACE_CLASSES]
        scored = sorted(((*verify(p, c), c) for c in (placeish or cands)),
                        key=lambda x: (-x[0], (x[2].get("osm_type"), x[2].get("osm_id")) not in from_extra))
        full = [s for s in scored if s[0] >= 0.999 and (wants_feature or s[2].get("category") not in NONPLACE_CLASSES)]
        forced = ov["force_review"].get(raw)
        bare = len(p["components"]) == 1 and not p["country"]
        if not scored:
            payload = {"raw": raw, "place_string_id": psid, "parsed": p, "queries": queries, "candidates": [], "reason": "no candidates"}
            cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                       (ulid(), tree_id, "place_resolution", dumps(payload), (note or "") + " No geocoder candidates; resolve by hand.", ext_id, ts))
            cx.execute("UPDATE place_string SET resolver=?, resolved_at=?, notes=? WHERE id=?", (resolver_tag, ts, dumps({"result": "no_candidates", "note": note}), psid))
            stats["no_candidates"] += 1; report.append(("NONE", raw, "")); continue
        chosen, how = (full[0][2], "unique full match") if len(full) == 1 else (select_best(p, full) if len(full) > 1 else (None, None))
        if chosen is not None and not forced and not bare:
            score, checks = next((s_, ch) for s_, ch, c in full if c is chosen)
            c = chosen
            leaf = st.hierarchy(c)
            if not cx.execute("SELECT 1 FROM place_name WHERE place_id=? AND name=?", (leaf, raw)).fetchone():
                cx.execute("INSERT INTO place_name (id,place_id,name,is_primary) VALUES (?,?,?,?)", (ulid(), leaf, raw, False))
            cx.execute("UPDATE place_string SET place_id=?, status='accepted', resolver=?, resolved_at=?, notes=? WHERE id=?",
                       (leaf, resolver_tag, ts, dumps({"queries": queries, "how": how, "match": candidate_summary(c, score, checks),
                                                             "alternatives": [x.get("display_name") for _, _, x in full if x is not c],
                                                             "details": p["details"], "warnings": p["warnings"], "note": note}), psid))
            stats["accepted"] += 1; report.append(("OK", raw, (f"[{how}] " if how != "unique full match" else "") + c.get("display_name")))
            audit_string(cx, tree_id, ts, a.by, psid, {"raw": raw, "resolver": resolver_tag, "from": {"status": "undecided", "place_id": None}, "to": {"status": "accepted", "place_id": leaf}, "how": how, "place": c.get("display_name")})
        else:
            reason = forced or ("bare single token; needs context" if bare else
                                (how or f"{len(full)} fully-verified candidates") if full else "no candidate matches every component")
            payload = {"raw": raw, "place_string_id": psid, "parsed": p, "queries": queries,
                       "candidates": [candidate_summary(c, s, ch) for s, ch, c in scored[:12]],
                       "suggested": 0 if scored and scored[0][0] >= 0.6 else None, "reason": reason}
            cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                       (ulid(), tree_id, "place_resolution", dumps(payload), ((note + " ") if note else "") + reason, ext_id, ts))
            cx.execute("UPDATE place_string SET status='undecided', resolver=?, resolved_at=?, notes=? WHERE id=?",
                       (resolver_tag, ts, dumps({"result": "review", "reason": reason, "top": candidate_summary(*scored[0][2:3], scored[0][0], scored[0][1]) if scored else None, "note": note}), psid))
            stats["undecided"] += 1; report.append(("REVIEW", raw, reason))
    stats["events_placed"], stats["events_left_unplaced"] = apply_to_events(cx, tree_id, resolver_tag, ts)
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, resolver_tag, "resolve", "place_string", "batch", dumps(stats)))
    if a.dry_run: cx.rollback()
    else: cx.commit()
    for tag, raw, info in report: print(f"{tag:7} {raw[:60]:60} {str(info)[:90]}")
    print("\n" + dumps(stats))

if __name__ == "__main__":
    main()
