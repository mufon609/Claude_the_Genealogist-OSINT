#!/usr/bin/env python3
"""Resolve raw place strings to a place hierarchy using OpenStreetMap Nominatim, and GOV and Wikidata where it falls short.

usage: tools/resolve_places.py [--tree slug] [--limit N] [--dry-run] [--only "raw string"] [--reset]

Rules
  * Every string is parsed into components; countries are normalized, and the last part of a string that is no country is the state
    when it is a state's name or an abbreviation of it (catalog.us_state: NJ, N.J., Penna, Tenn., Mass.), so a string that is a
    state alone ("NJ", "Penna", "N.J., USA") is asked as the state and accepted when exactly one candidate verifies, as any
    string is. An abbreviation earlier in a string is left as written: Penn, in Penn, Cumberland, Pennsylvania, is a township.
  * Nominatim (free, ODbL, 1 req/s, cached under derivatives/geocode/) is asked for
    candidates. A candidate is verified by checking that EVERY component the string
    gave is, in full, the name of the candidate or of a unit in its address hierarchy, or one of
    its own old or alternative names (same_name: catalog.place_name_key, so case, accents,
    punctuation, spacing, an abbreviated word such as Mt., Twp or Ft. and the unit's own word
    such as Township or Ward N are set aside). A component that is only the start of a name
    ("Cadillac Memorial Gardens West" for "... Cemetery"), a truncation ("Hemp.") or a close
    spelling ("Worchester") is marked "near" in the candidate's checks and verifies nothing:
    the candidate is still offered on the string's card.
  * Auto-resolve when exactly one candidate verifies fully, and also when the
    verified candidates are one territory under two names — a city and the county
    coterminous with it (Philadelphia, Queens) — tested on the geocoder's own answer:
    their boundingboxes coincide within a small tolerance (see coterminous()). Choose
    the locality name and record "coterminous: one territory". A place genuinely
    nested in a larger, differently-sized unit of the same name (a village in its
    town, a city in its prefecture) fails that test and, like every other case of
    more than one verified candidate, becomes a `place_resolution` proposal
    (tree-scoped) with every verified candidate listed; the owner decides on the
    person screen. Never widen auto-accept past those two cases.
  * When Nominatim leaves a string open (no unique full match, a bare name, or a forced review), a gazetteer that knows
    its places is asked: GOV, genealogy.net's historical gazetteer (SOAP, no key, CC BY-SA), for Germany, Poland and
    Silesia; Wikidata (its own API: wbsearchentities, then the candidates' containing units followed up P131, CC0) for
    Ireland. Each is cached under derivatives/geocode/<gazetteer>/ like Nominatim's answers, at one request a second,
    with the project's User-Agent. GOV is asked under the string's own name and under the current name of every geocoder
    candidate that keeps one of the string's names as its own (an old German name OpenStreetMap records on today's
    Polish place); its populated places (GOV_POPULATED) whose names agree with the string's are its candidates. A
    gazetteer candidate is verified as a geocoder one is: its own name in full (same_letters: spaces and hyphens set
    aside; a close spelling, Harperdorf for Harpersdorf, is near and verifies nothing), and every other part of the
    string (a Kreis, a town, a county, a land, the region, the country) must be a unit it lies within, in any period of its history (GOV's own
    searchRelatedByName; Wikidata's P131 chain and P17). The same rule decides: the string is accepted only when exactly
    one gazetteer candidate verifies on every part, the string gives more than its name, and that candidate has exactly
    one geocoder twin (the same place by an identifier both keep: Wikidata's item id, or GOV's id through Wikidata's
    P2503 or the Polish SIMC register) with no other geocoder candidate verifying fully; the twin places it in today's
    hierarchy, the gazetteer's id goes onto the place (gov_id, wikidata_id) and GOV's names of it become dated
    place_name rows. Otherwise the card offers every gazetteer candidate with its checks, on its twin's entry where it
    has one, after the geocoder's own; a twin the owner chooses there carries the gazetteer's answer, and the next run
    writes it onto the place (backfill_gazetteer).
  * data/place-overrides.json can reject non-places (a string whole, or the words a record writes for the place of another of
    its lines, "Same House"), force review, add candidate queries, and attach notes. It is the only hand-authored input.
  * A string whose geocoder request got no answer (the endpoint unreachable, a refusal) is left exactly as it was: no card, no
    resolver, so the next run asks again; the geocoder is not asked again in the run that found it silent, and the run says how
    many strings it left.
  * Every decision is undecided | accepted | rejected; match scores stay in notes JSON.
  * Every string the resolver accepts, rejects or resets (--reset) gets one audit row
    under the person or agent who ran it (--by), the resolver's tag and the change in
    the diff, so a reset-and-rerun can be read back afterwards. --reset undoes every
    AI resolution; --reset --only "raw string" narrows it to that one string, leaving
    every other AI resolution and its audit trail untouched, and (since the string's
    resolver is cleared) the same run resolves it again under the current rules.
"""
import argparse, datetime, difflib, hashlib, json, math, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import DB, ROOT, USER_AGENT as UA, connect, derivatives_dir, dumps, now, resolve_tree, ulid
from catalog import US_STATES, country_words, place_name_key, us_state

RESOLVER = ("rule", "nominatim-resolver", "0.5.0")
def cache_dir():
    """Where the geocoder's answers are kept, under the data root of the run (a scratch run keeps its own)."""
    return os.path.join(derivatives_dir(), "geocode", "nominatim")
ENDPOINT = "https://nominatim.openstreetmap.org/search"

COUNTRY_SYN = country_words()   # data/countries.csv: a country's name and the words records write for it; read from a string's last part only
DROP = {"north america", "british colonies", "europe", "colonial america", "unknown"}   # words for no place more specific than the rest of the string ("UNKNOWN, Germany" is Germany)
HISTORIC_REGION = {"silesia": "Silesia", "silesa": "Silesia", "schlesien": "Silesia"}
WARD_RE = re.compile(r"^(.*?)\s+((?:Lower|Upper)\s+Ward|Ward|Assembly District|District|Precinct)\s*\d*$", re.I)
ADDR_RE = re.compile(r"^\d+\s+\S|\b(Road|Street|Avenue|Lane|Drive|St\.?|Rd\.?|Ave\.?)$", re.I)
LOCALITY_KEYS = ("city", "town", "village", "hamlet", "municipality", "borough", "isolated_dwelling", "locality")
SUB_KEYS = ("suburb", "neighbourhood", "city_district", "quarter")

SYN = {"nordrhein westfalen": "north rhine westphalia", "sachsen": "saxony", "noord holland": "north holland",
       "zuid holland": "south holland", "friesland": "frisia", "koln": "cologne", "bayern": "bavaria"}   # a name and its English translation, one place's two names, keyed as catalog.place_name_key writes them
NEAR_RATIO = 0.86
def norm(s):
    """A name as the resolver compares names: catalog.place_name_key, a translation (SYN) read as the English name."""
    k = place_name_key(s)
    return SYN.get(k, k)
def same_name(a, b):
    """Whether two names are one name in full: the same key (norm) once case, accents, punctuation, spacing, an abbreviated
    word and the unit's own word are set aside. This is the only way a part of a string verifies against a candidate's name."""
    na = norm(a)
    return bool(na) and na == norm(b)
def near_name(a, b):
    """Whether a differs from b yet resembles it: a is a word-for-word start of b ("Cadillac Memorial Gardens West" and "Cadillac
    Memorial Gardens West Cemetery"), a written with a period is the start of b ("Hemp." and Hempstead), or the two spell alike
    to difflib's NEAR_RATIO ("Worchester" and Worcester, "North Hampton" and Northampton). Never a verification: only what a
    card shows."""
    na, nb = norm(a), norm(b)
    if not na or not nb or na == nb: return False
    return (a.strip().endswith(".") and len(na) >= 3 and nb.startswith(na)) or nb.startswith(na + " ") or difflib.SequenceMatcher(None, na, nb).ratio() >= NEAR_RATIO
def agree(part, names):
    """How a part of a string stands to a candidate's names: True when it is one of them in full (same_name), "near" when it only
    resembles one (near_name), else False. Only True verifies the part."""
    if any(same_name(part, n) for n in names): return True
    return "near" if any(near_name(part, n) for n in names) else False

def parse(raw):
    """-> dict(components=[...], country, region, details=[...], warnings=[...])"""
    p = {"components": [], "country": None, "region": None, "details": [], "warnings": []}
    s = re.sub(r"\(alt\..*?\)", "", raw)
    whole = s.strip().lower().rstrip(".") in COUNTRY_SYN   # "United States of America" is one country's name, not "United States of" ahead of "America"
    for phrase in ([] if whole else sorted(COUNTRY_SYN, key=len, reverse=True)):          # "Kalagh Cork Great Britain and Ireland"
        if "," not in s and s.lower().endswith(" " + phrase):
            s = s[: -len(phrase)].strip(); p["country"] = COUNTRY_SYN[phrase]; s = ", ".join(s.split()); break
    toks, prev = [], None
    for t in [t.strip() for t in s.split(",")]:
        if not t or (prev and t.lower() == prev.lower()): continue
        toks.append(t); prev = t
    last = next((i for i in range(len(toks) - 1, -1, -1) if not (i == len(toks) - 1 and toks[i].lower().rstrip(".") in COUNTRY_SYN)), None)   # the last part that is no country
    if last is not None and us_state(toks[last]): toks[last] = us_state(toks[last])   # a state written as an abbreviation (NJ, N.J., Penna, Tenn.) is the state, there only: earlier, Penn or Col is a township's or a person's own
    for t in toks:
        tl = t.lower().rstrip(".")
        if tl in COUNTRY_SYN and t is toks[-1]: p["country"] = COUNTRY_SYN[tl]; continue   # the country a record writes last; earlier, a country's name is a place of that name (Lebanon, Pennsylvania)
        if tl in DROP: continue
        if tl in HISTORIC_REGION: p["region"] = HISTORIC_REGION[tl]; continue
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

WIKIDATA_ENDPOINT = "https://www.wikidata.org/wiki/Special:EntityData"

def wikidata_cache_dir():
    return os.path.join(derivatives_dir(), "geocode", "wikidata")

def wikidata_entity(qid):
    """The Wikidata item for qid (its labels and claims), fetched once and cached under derivatives/geocode/wikidata/;
    the public endpoint at one request a second, as Nominatim is. {} on any error, so a place missing from Wikidata
    or a network failure never stops the run."""
    os.makedirs(wikidata_cache_dir(), exist_ok=True)
    path = os.path.join(wikidata_cache_dir(), qid + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh: return json.load(fh)
    url = f"{WIKIDATA_ENDPOINT}/{qid}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        time.sleep(1.1)
        with urllib.request.urlopen(req, timeout=30) as r: data = json.load(r)
    except Exception:
        return {}
    with open(path, "w", encoding="utf-8") as fh: json.dump(data, fh, ensure_ascii=False)
    return data

def _wd_label(ent):
    labels = (ent or {}).get("labels") or {}
    if "en" in labels: return labels["en"].get("value")
    return next(iter(labels.values()), {}).get("value")

def _wd_time(claims, prop):
    """A Wikidata time claim's value, cut to its own precision (day, month or year): "+1992-04-01T00:00:00Z" at
    day precision (11) is "1992-04-01"; at year precision (9) it is "1992". None when the claim is absent."""
    c = ((claims or {}).get(prop) or [None])[0]
    v = ((c or {}).get("mainsnak") or {}).get("datavalue", {}).get("value") if c else None
    t = (v or {}).get("time")
    if not t: return None
    parts = t.lstrip("+-").split("T")[0].split("-")
    precision = v.get("precision", 11)
    if precision <= 9: return parts[0]
    if precision == 10: return "-".join(parts[:2])
    return "-".join(parts[:3])

def former_names(qid):
    """Former names for the Wikidata item qid, from what it replaces or was merged from (P1365, each with its own
    P571 inception and P576 dissolved dates): a list of {name, valid_from, valid_to, wikidata_id}. A replaced item
    with no P576 of its own is skipped: P1365 is a looser claim than a merger (a border adjustment, or two entries
    for a place that never actually dissolved, as Wikidata's own data for two neighbors of Morioka shows), and
    without the replaced item's own word that it stopped existing there is no date to stand on, so nothing is
    written rather than guessing one from the replacing item's own founding. Every call goes through
    wikidata_entity, so it is cached and rate-limited like any other Wikidata call; an item with no P1365 claim, or
    none of its own dissolved, gives an empty list."""
    ent = (wikidata_entity(qid).get("entities") or {}).get(qid) or {}
    claims = ent.get("claims") or {}
    out = []
    for c in claims.get("P1365") or []:
        rid = (c.get("mainsnak") or {}).get("datavalue", {}).get("value", {}).get("id")
        if not rid: continue
        rent = (wikidata_entity(rid).get("entities") or {}).get(rid) or {}
        rname = _wd_label(rent)
        if not rname: continue
        rclaims = rent.get("claims") or {}
        valid_to = _wd_time(rclaims, "P576")
        if not valid_to: continue
        out.append({"name": rname, "valid_from": _wd_time(rclaims, "P571"), "valid_to": valid_to, "wikidata_id": rid})
    return out

def add_former_names(cx, pid, wikidata_id):
    """Ask Wikidata for wikidata_id's former names (former_names) and write each as a place_name row on place pid,
    dated, skipping one already there (place, name and dates the same). Returns how many were added."""
    added = 0
    for fn in former_names(wikidata_id):
        if cx.execute("""SELECT 1 FROM place_name WHERE place_id=? AND name=? AND COALESCE(valid_from,'')=COALESCE(?,'')
                         AND COALESCE(valid_to,'')=COALESCE(?,'')""", (pid, fn["name"], fn["valid_from"], fn["valid_to"])).fetchone(): continue
        cx.execute("INSERT INTO place_name (id,place_id,name,valid_from,valid_to,is_primary) VALUES (?,?,?,?,?,0)",
                   (ulid(), pid, fn["name"], fn["valid_from"], fn["valid_to"]))
        added += 1
    return added

def backfill_former_names(cx):
    """Every place already carrying a wikidata_id (its own past resolution, this run's included) gets its former
    names asked of Wikidata: cheap to repeat, since a place already checked costs a cache read, not a request."""
    return sum(add_former_names(cx, pid, wdid) for pid, wdid in cx.execute("SELECT id, wikidata_id FROM place WHERE wikidata_id IS NOT NULL").fetchall())

# ---------------------------------------------------------------- gazetteers that know the places the geocoder does not

GOV_SERVICES = "https://gov.genealogy.net/services/"
GOV_DATA = "{http://gov.genealogy.net/data}"
GOV_ITEM = "https://gov.genealogy.net/item/show/"
# GOV's own populated-place types (the "Wohnplatz" group of its types.owl, and 51, a town as a settlement), with GOV's
# English label: the only objects offered as candidates. Its churches, parishes, registry offices, courts and
# administrative units of the same name are the settlement's offices and containers, not another place a record means.
GOV_POPULATED = {8: "castle", 17: "building", 21: "manor", 24: "farm", 39: "place", 40: "part of place", 51: "town",
                 54: "part of town", 55: "village", 64: "outlying estate", 65: "parish village", 66: "church village",
                 67: "solitude", 68: "main place", 69: "hamlet", 87: "mill", 90: "abandoned place", 102: "forester's house",
                 111: "palace", 120: "settlement", 121: "colony", 129: "settlement", 139: "isolated farmstead",
                 158: "part of municipality", 159: "khutor", 181: "hamlet", 193: "alpine pasture", 229: "group of houses",
                 230: "scattered settlement", 231: "farms", 232: "outskirts", 233: "market village", 236: "houses",
                 238: "urban-type settlement", 261: "farmstead group", 280: "quarter in town"}
# The names GOV knows a country or region by, for the names the parse gives it; any other part is asked as written,
# a leading unit word ("Kr. Goldberg") dropped.
GOV_NAMES = {"Germany": ("Germany", "Deutschland", "Deutsches Reich"), "Poland": ("Poland", "Polen"), "Silesia": ("Schlesien",)}
GOV_UNIT_WORD = re.compile(r"^(Kr\.?|Kreis|Landkreis|Stadtkreis|Amtshauptmannschaft|Kreishauptmannschaft|Regierungsbezirk|Provinz)\s+", re.I)
# A position word standing alone before the name it qualifies ("Nieder, Harpersdorf"), read with it as GOV writes it.
GOV_POSITION_WORDS = {"nieder", "ober", "mittel", "groß", "gross", "klein", "alt", "neu"}
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
TWIN_KM = 2.0
UNREACHED = set()   # the gazetteer requests that failed in this run, and the gazetteers that asked us to slow down
MISSED = []         # every gazetteer request this run answered with nothing, so a card can say its candidates may be missing

def gazetteer_for(p):
    """Which gazetteer knows a parsed string's places the geocoder may not: GOV (genealogy.net's historical gazetteer)
    for Germany, Poland and Silesia, whose records name places by their German names and their old Kreise; Wikidata
    for Ireland, whose townlands and civil parishes it holds; None elsewhere."""
    if p["country"] == "Ireland": return "wikidata"
    if p["country"] in ("Germany", "Poland") or p["region"] == "Silesia": return "gov"
    return None

def gazetteer_cache_path(service, args):
    """Where one gazetteer answer is kept: derivatives/geocode/<gazetteer>/<sha1 of the request>.json."""
    key = hashlib.sha1(json.dumps([service, *args], ensure_ascii=False).lower().encode()).hexdigest()
    return os.path.join(derivatives_dir(), "geocode", service.split(":")[0], key + ".json")

def gazetteer_answer(service, args, request):
    """A gazetteer's answer to one request (service names the gazetteer and its operation, args the request's own
    words), as the service sent it: read from the cache, or asked once (request()) at one request a second, with the
    project's User-Agent, and kept as {service, args, fetched_at, answer}. None when the service could not be
    reached; nothing is cached then, so a later run asks again."""
    path, gazetteer = gazetteer_cache_path(service, args), service.split(":")[0]
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh: return json.load(fh)["answer"]
    if path in UNREACHED or gazetteer in UNREACHED: MISSED.append(path); return None
    try:
        time.sleep(1.1)
        answer = request()
    except Exception as e:
        UNREACHED.add(path)   # asked once in a run: the same request is not sent again until the next run
        if getattr(e, "code", None) in (429, 503): UNREACHED.add(gazetteer)   # the service asks us to slow down: nothing more is asked of it this run
        MISSED.append(path)
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh: json.dump({"service": service, "args": list(args), "fetched_at": now(), "answer": answer}, fh, ensure_ascii=False)
    return answer

def http_text(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode("utf-8")

def gov(op, service="ComplexService", **parts):
    """One GOV SOAP call (rpc/literal, as its WSDL at gov.genealogy.net/services/<service>?wsdl describes it; no key):
    the answer's XML text, or None."""
    def request():
        body = "".join(f"<{k}>{escape(str(v))}</{k}>" for k, v in parts.items())
        env = ('<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
               f'xmlns:ws="http://gov.genealogy.net/ws"><soapenv:Body><ws:{op}>{body}</ws:{op}></soapenv:Body></soapenv:Envelope>')
        return http_text(GOV_SERVICES + service, env.encode("utf-8"), {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'})
    return gazetteer_answer(f"gov:{op}", list(parts.values()), request)

def gov_time(t):
    """A GOV time (a julian day and its precision: 0 a year, 1 a month, 2 a day) as an ISO date cut to that precision."""
    if t is None or not t.get("jd"): return None
    d = datetime.date.fromordinal(int(t.get("jd")) - 1721425)
    precision = int(t.get("precision") or 2)
    return f"{d.year:04d}" if precision == 0 else f"{d.year:04d}-{d.month:02d}" if precision == 1 else d.isoformat()

def gov_span(el):
    """The span of a GOV name or relation: its begin-year and end-year, or its timespan's begin and end."""
    ts = el.find(GOV_DATA + "timespan")
    vf = el.get("begin-year") or (gov_time(ts.find(GOV_DATA + "begin")) if ts is not None else None)
    vt = el.get("end-year") or (gov_time(ts.find(GOV_DATA + "end")) if ts is not None else None)
    return vf, vt

def gov_core(name):
    """A GOV name without its qualifier: "Berthelsdorf/Erzgeb." and "Harpersdorf (Ss. Trinitas)" are Berthelsdorf and Harpersdorf."""
    return re.split(r"\s*[/(]", name or "")[0].strip()

def gov_objects(xml):
    """The objects of a GOV answer: id, names (each with its language and the span GOV gives it), types, position,
    the units it is part of, and its references in other registers (SIMC, the Polish register of places)."""
    if not xml: return []
    out = []
    for o in ET.fromstring(xml).iter(GOV_DATA + "object"):
        pos = o.find(GOV_DATA + "position")
        names = []
        for n in o.findall(GOV_DATA + "name"):
            vf, vt = gov_span(n)
            names.append({"name": n.get("value"), "lang": n.get("lang"), "valid_from": vf, "valid_to": vt})
        out.append({"id": o.get("id"), "names": names, "types": [int(t.get("value")) for t in o.findall(GOV_DATA + "type") if (t.get("value") or "").isdigit()],
                    "lat": float(pos.get("lat")) if pos is not None else None, "lon": float(pos.get("lon")) if pos is not None else None,
                    "part_of": [r.get("ref") for r in o.findall(GOV_DATA + "part-of")], "refs": [r.get("value") for r in o.findall(GOV_DATA + "external-reference")]})
    return out

def gov_related(superordinate, subordinate):
    """The ids GOV finds named subordinate within a unit named superordinate, at any level and in any period of its
    history (SimpleService searchRelatedByName): GOV's own check of a string's containing unit."""
    xml = gov("searchRelatedByName", service="SimpleService", superordinateName=superordinate, subordinateName=subordinate)
    return {e.text for e in ET.fromstring(xml).iter() if e.tag.endswith("}item") and e.text} if xml else set()

def same_letters(a, b):
    """Two names are one name in full: the same letters once spaces and hyphens are set aside (Langneundorf and Lang
    Neundorf, GOV's own historical names being spelled both ways). What verifies a gazetteer candidate's name."""
    x, y = (re.sub(r"[\s-]+", "", norm(n)) for n in (a, b))
    return bool(x) and x == y

def names_agree(a, b):
    """Two names may be one name: the same letters in full (same_letters), or a slip of a letter or two between them
    (Harperdorf and Harpersdorf, spelling alike to difflib's NEAR_RATIO); never one name inside a longer one, which is
    another place (Berthelsdorf and Neuberthelsdorf, Ballyquirk and Ballyquirk Castle). What a gazetteer is asked under and
    offers; a close spelling verifies nothing (same_letters)."""
    x, y = (re.sub(r"[\s-]+", "", norm(n)) for n in (a, b))
    if not x or not y: return False
    return x == y or (abs(len(x) - len(y)) <= 2 and difflib.SequenceMatcher(None, x, y).ratio() >= NEAR_RATIO)

def osm_names(c):
    """A geocoder candidate's own names: its name and every name, old name and alternative name OpenStreetMap records."""
    return [c.get("name") or ""] + [v for k, v in (c.get("namedetails") or {}).items() if k.startswith(("name", "old_name", "alt_name"))]

def km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))

def gov_head(p):
    """The name a string gives GOV to search, and the parts left to verify: its first component, read with the next when
    it is a position word standing alone ("Nieder, Harpersdorf" is Nieder Harpersdorf)."""
    comps = p["components"]
    if len(comps) >= 2 and comps[0].strip().lower() in GOV_POSITION_WORDS: return f"{comps[0].strip()} {comps[1].strip()}", comps[2:]
    return comps[0], comps[1:]

def gov_candidates(p, cands):
    """GOV's candidates for a parsed string, each checked against every part of the string. GOV is asked under the
    string's own name and under the name of every geocoder candidate carrying one of the string's names among its own (a
    German name OpenStreetMap keeps as the old name of today's Polish place); a candidate is a populated place
    (GOV_POPULATED) one of whose own names agrees with the string's name, and each other part of the string (a Kreis, a
    town, a land, the region, the country) is verified when GOV finds the candidate within a unit of that name
    (gov_related). Its identity is its id, its references in other registers and a same-named unit it is part of (GOV
    keeps a village and its municipality as two objects), for the geocoder twin (twin_of)."""
    head, rest = gov_head(p)
    asked = [head] + [c.get("name") for c in cands if c.get("name") and any(names_agree(comp, n) for comp in p["components"] + [head] for n in osm_names(c) if n)]
    seen, everything = {}, {}
    for name in dict.fromkeys(asked):
        objs = gov_objects(gov("searchByName", placename=name))
        everything.update({o["id"]: o for o in objs})
        for o in objs:
            if o["id"] in seen or not set(o["types"]) & set(GOV_POPULATED): continue
            if not any(names_agree(head, gov_core(n["name"])) for n in o["names"]): continue
            seen[o["id"]] = {**o, "asked_as": name}
    parts = rest + [x for x in (p["region"], p["country"]) if x]
    out = []
    for o in seen.values():
        checks = {head: True if any(same_letters(head, gov_core(n["name"])) for n in o["names"]) else "near"}   # a close spelling of the name is offered, never verified
        for part in parts:
            checks[part] = any(o["id"] in gov_related(n, o["asked_as"]) for n in GOV_NAMES.get(part, (GOV_UNIT_WORD.sub("", part).strip(),)))
        same = {o["id"], *o["refs"]} | {r for r in o["part_of"] if r in everything and any(names_agree(gov_core(a["name"]), gov_core(b["name"])) for a in everything[r]["names"] for b in o["names"])}
        label = " / ".join(dict.fromkeys(n["name"] for n in o["names"]))
        types = [GOV_POPULATED[t] for t in o["types"] if t in GOV_POPULATED]
        out.append({"source": "gov", "id": o["id"], "display_name": f"{label} (GOV {o['id']}, {types[0] if types else 'place'}"
                    + (f", {o['lat']:.4f} N {o['lon']:.4f} E)" if o["lat"] is not None else ")"),
                    "type": types[0] if types else "unknown", "names": o["names"], "lat": o["lat"], "lon": o["lon"], "url": GOV_ITEM + o["id"],
                    "checks": checks, "verified": all(v is True for v in checks.values()), "parts": len(parts), "same": sorted(same)})
    return out

def wikidata_api(service, args, params):
    """One request of Wikidata's own API (www.wikidata.org/w/api.php), cached as every gazetteer answer is; an answer
    that is the API's error is no answer, and is not kept."""
    def request():
        text = http_text(WIKIDATA_API + "?" + urllib.parse.urlencode({**params, "format": "json"}))
        if "error" in json.loads(text): raise ValueError(text[:200])
        return text
    return gazetteer_answer(service, args, request)

def wd_ids(claims, prop):
    """The items a claim of prop names, in its order."""
    return [v["id"] for v in (((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") for c in (claims or {}).get(prop) or []) if isinstance(v, dict) and v.get("id")]

def wikidata_candidates(p):
    """Wikidata's candidates for a parsed string: the items its search (wbsearchentities) finds under the string's first
    component whose label or matched alias agrees with it and which have a position (P625), each checked against every
    other part of the string (a county, a parish, the country) on the units it lies in, its P131 followed up one level
    a request (wbgetclaims) to the country (P17), which is read and not followed; the labels of them all read in one
    request (wbgetentities)."""
    head, rest = p["components"][0], p["components"][1:]
    found = wikidata_api("wikidata:search", [head], {"action": "wbsearchentities", "search": head, "language": "en", "uselang": "en", "type": "item", "limit": 50})
    hits = [h for h in (json.loads(found).get("search") or [] if found else [])
            if names_agree(head, h.get("label") or "") or names_agree(head, (h.get("match") or {}).get("text") or "")]
    if not hits: return []
    qids = sorted({h["id"] for h in hits}, key=lambda q: int(q[1:]))
    got = wikidata_api("wikidata:entities", qids, {"action": "wbgetentities", "ids": "|".join(qids), "props": "labels|descriptions|claims", "languages": "en"})
    ents = (json.loads(got).get("entities") or {}) if got else {}
    up = {q: wd_ids((ents.get(q) or {}).get("claims"), "P131") for q in qids}
    countries = {q: wd_ids((ents.get(q) or {}).get("claims"), "P17") for q in qids}
    stop = {c for cs in countries.values() for c in cs}
    frontier = sorted({x for v in up.values() for x in v} - set(up) - stop, key=lambda q: int(q[1:]))
    while frontier:
        for q in frontier:
            claims = wikidata_api("wikidata:claims", [q, "P131"], {"action": "wbgetclaims", "entity": q, "property": "P131"})
            up[q] = wd_ids((json.loads(claims).get("claims") if claims else None), "P131")
        frontier = sorted({x for q in frontier for x in up[q]} - set(up) - stop, key=lambda q: int(q[1:]))
    types = {q: wd_ids((ents.get(q) or {}).get("claims"), "P31") for q in qids}
    named = sorted({x for v in list(up.values()) + list(countries.values()) + list(types.values()) for x in v} | set(up), key=lambda q: int(q[1:]))
    labels = {}
    for i in range(0, len(named), 50):
        batch = named[i:i + 50]
        ans = wikidata_api("wikidata:labels", batch, {"action": "wbgetentities", "ids": "|".join(batch), "props": "labels", "languages": "en"})
        for q, e in ((json.loads(ans).get("entities") or {}) if ans else {}).items():
            labels[q] = ((e.get("labels") or {}).get("en") or {}).get("value")
    parts = rest + ([p["country"]] if p["country"] else [])
    out = []
    for h in sorted(hits, key=lambda h: qids.index(h["id"])):
        q = h["id"]; claims = (ents.get(q) or {}).get("claims") or {}
        at = next((v for v in (((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") for c in claims.get("P625") or []) if isinstance(v, dict)), None)
        if not at: continue
        within, seen, todo = [], {q}, list(up.get(q) or [])
        while todo:
            x = todo.pop(0)
            if x in seen: continue
            seen.add(x); within.append(x); todo += up.get(x) or []
        names = list(dict.fromkeys(labels[x] for x in within + countries[q] if labels.get(x)))
        own = same_letters(head, h.get("label") or "") or same_letters(head, (h.get("match") or {}).get("text") or "")
        checks = {head: True if own else "near", **{part: agree(part, names) for part in parts}}   # a close spelling of the name is offered, never verified
        desc = ((ents.get(q) or {}).get("descriptions") or {}).get("en", {}).get("value") or ", ".join(names)
        out.append({"source": "wikidata", "id": q, "display_name": f"{h.get('label')} ({desc}; Wikidata {q})",
                    "type": next((labels.get(t) for t in types[q] if labels.get(t)), "unknown"), "names": [], "lat": at.get("latitude"), "lon": at.get("longitude"),
                    "url": "https://www.wikidata.org/wiki/" + q, "within": names, "checks": checks, "verified": all(v is True for v in checks.values()), "parts": len(parts), "same": [q]})
    return out

def gov_refs(c):
    """The GOV ids a geocoder candidate is known by: its SIMC (OpenStreetMap's teryt:simc, as GOV keeps it) and the GOV
    id Wikidata gives its item (P2503), read from the item wikidata_entity keeps."""
    ex = c.get("extratags") or {}
    refs = {"SIMC:" + ex["teryt:simc"]} if ex.get("teryt:simc") else set()
    qid = ex.get("wikidata")
    if qid:
        claims = (((wikidata_entity(qid).get("entities") or {}).get(qid) or {}).get("claims") or {})
        refs |= {((cl.get("mainsnak") or {}).get("datavalue") or {}).get("value") for cl in claims.get("P2503") or []} - {None}
    return refs

def twin_of(g, cands):
    """The geocoder candidates that are the gazetteer candidate g itself, by an identifier both keep: Wikidata's item id
    (OpenStreetMap's wikidata tag), or GOV's id or SIMC (gov_refs), asked only of a candidate within TWIN_KM of g whose
    own names agree with one of g's. The twin places g in today's hierarchy, as the geocoder's own answer."""
    if g["source"] == "wikidata":
        return [c for c in cands if (c.get("extratags") or {}).get("wikidata") in g["same"]]
    near = [c for c in cands if g["lat"] is not None and c.get("lat") and km(g["lat"], g["lon"], float(c["lat"]), float(c["lon"])) <= TWIN_KM
            and any(names_agree(gov_core(n["name"]), m) for n in g["names"] for m in osm_names(c) if m)]
    return [c for c in near if gov_refs(c) & set(g["same"])]

GAZETTEER_NAME = {"gov": "GOV", "wikidata": "Wikidata"}

def gazetteer_reason(scope, gz, unreached=False):
    """What the gazetteer said, for a card's reason: how many of its candidates verify on every part of the string, and
    whether the one that does has the geocoder twin that would place it; or that it could not be reached for some of its
    answer, so the card may lack its candidates (--reset --only asks again)."""
    name = GAZETTEER_NAME[scope]
    if unreached: return f"{name} could not be reached for every answer; ask again with --reset --only"
    if not gz: return f"{name} has no candidate"
    v = [g for g in gz if g["verified"]]
    said = f"{name}: {len(v)} of {len(gz)} candidate{'s' if len(gz) != 1 else ''} verified on every part"
    if len(v) == 1 and not v[0]["parts"]: said += ", the string giving nothing beyond the name to verify"
    elif len(v) == 1 and len(v[0]["twins"]) != 1: said += ", with no single geocoder answer to place it"
    return said

def gazetteer_summary(g):
    """What the card and the accepted string's notes keep of a gazetteer candidate."""
    return {k: g[k] for k in ("source", "id", "display_name", "type", "names", "lat", "lon", "url", "checks", "verified")}

def write_gazetteer(cx, pid, g):
    """A gazetteer candidate's id onto place pid (gov_id or wikidata_id, where the place has none) and GOV's names of it as
    place_name rows, each with its language and the span GOV gives it, skipping a name already there with the same
    span. Returns how many names were added."""
    if g.get("source") == "gov": cx.execute("UPDATE place SET gov_id=COALESCE(gov_id,?) WHERE id=?", (g["id"], pid))
    if g.get("source") == "wikidata": cx.execute("UPDATE place SET wikidata_id=COALESCE(wikidata_id,?) WHERE id=?", (g["id"], pid))
    added = 0
    for n in g.get("names") or []:
        if cx.execute("""SELECT 1 FROM place_name WHERE place_id=? AND name=? AND COALESCE(valid_from,'')=COALESCE(?,'')
                         AND COALESCE(valid_to,'')=COALESCE(?,'')""", (pid, n["name"], n["valid_from"], n["valid_to"])).fetchone(): continue
        cx.execute("INSERT INTO place_name (id,place_id,name,lang,valid_from,valid_to,is_primary) VALUES (?,?,?,?,?,?,0)",
                   (ulid(), pid, n["name"], n["lang"], n["valid_from"], n["valid_to"]))
        added += 1
    return added

def backfill_gazetteer(cx):
    """Every accepted string whose chosen candidate carries a gazetteer's answer (the resolver's own acceptance, or the
    owner's choice of a candidate the gazetteer annotated on the card) has that answer written onto its place
    (write_gazetteer): cheap to repeat, read from the string's own notes."""
    added = 0
    for pid, notes in cx.execute("SELECT place_id, notes FROM place_string WHERE status='accepted' AND place_id IS NOT NULL AND notes LIKE '%\"gazetteer\"%'").fetchall():
        g = (json.loads(notes or "{}").get("match") or {}).get("gazetteer")
        if g: added += write_gazetteer(cx, pid, g)
    return added

def chain_text(cx, pid):
    names = []
    while pid:
        r = cx.execute("SELECT name, parent_id FROM place WHERE id=?", (pid,)).fetchone()
        if not r: break
        names.append(r[0]); pid = r[1]
    return " < ".join(names)

def dated_candidate(cx, p):
    """A parsed string's own components read against every place's dated former names (place_name rows with a
    valid_from or valid_to), tail-word first so a hamlet or ward named ahead of it ("Ogau" in "Ogau Tonan") is never
    mistaken for the whole: {place_id, place (its modern chain), name, valid_from, valid_to, leading} for the first
    match, tried finest component first; None when nothing dated matches. Offered as a candidate only — a dated name
    is not a geocoder-verified match, so it never auto-resolves (CLAUDE.md's place-resolution rule stops at a unique
    full match and one territory under two names)."""
    dated = cx.execute("SELECT place_id, name, valid_from, valid_to FROM place_name WHERE valid_from IS NOT NULL OR valid_to IS NOT NULL").fetchall()
    if not dated: return None
    for comp in p["components"]:
        words = comp.split()
        for i in range(len(words)):
            tail = " ".join(words[i:])
            for pid, name, vf, vt in dated:
                if same_name(tail, name):
                    return {"place_id": pid, "place": chain_text(cx, pid), "name": name, "valid_from": vf, "valid_to": vt, "leading": " ".join(words[:i]) or None}
    return None

def verify(p, cand):
    """Check a candidate against the parsed string: each component the string gives is True when it is the candidate's name or the
    name of a unit in its hierarchy in full (agree: its own old and alternative names count), "near" when it only resembles one,
    False otherwise; the country must be the candidate's country, in full. Returns (score, checks), the score the fraction of the
    checks that are True: a near part is not a verified one."""
    addr = cand.get("address") or {}; names = cand.get("namedetails") or {}
    hier = [v for k, v in addr.items() if k not in ("postcode", "country_code", "ISO3166-2-lvl4", "ISO3166-2-lvl6", "house_number")]
    hier += [v for k, v in names.items() if k.startswith("name") or k.startswith("old_name") or k.startswith("alt_name")]
    checks = {}
    for c in p["components"]:
        checks[c] = agree(c, hier)
    if p["country"]:
        checks["country:" + p["country"]] = same_name(p["country"], addr.get("country", "")) or \
            (p["country"] == "United Kingdom" and addr.get("country_code") == "gb")
    n = len(checks); ok = sum(v is True for v in checks.values())
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
        if leaf_name and lt not in ("unknown",) and not any(same_name(leaf_name, n) for n in names_in_chain):
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

COTERMINOUS_IOU = 0.9

def bbox_iou(a, b):
    """Intersection-over-union of two Nominatim boundingbox answers ([south, north, west, east], as strings): near 1.0
    when the two answers describe the same territory, near 0 when one is a small part of a much larger other."""
    (as_, an_, aw, ae), (bs, bn, bw, be) = (list(map(float, x)) for x in (a, b))
    iw, ih = max(0.0, min(ae, be) - max(aw, bw)), max(0.0, min(an_, bn) - max(as_, bs))
    inter = iw * ih
    area_a, area_b = max(0.0, ae - aw) * max(0.0, an_ - as_), max(0.0, be - bw) * max(0.0, bn - bs)
    union = area_a + area_b - inter
    return inter / union if union else 0.0

def coterminous(cands):
    """Whether same-name verified candidates are one territory under two names (a city and the county coterminous with
    it), tested on the geocoder's own answer rather than guessed from the name: every pair's boundingbox coincides
    within a small tolerance (COTERMINOUS_IOU). A place genuinely nested in a larger unit of the same name (a village
    in its town, a city in its prefecture) fails this every time, since the larger unit's box dwarfs the smaller's."""
    boxes = [c.get("boundingbox") for c in cands]
    if not all(boxes): return False
    return all(bbox_iou(boxes[i], boxes[j]) >= COTERMINOUS_IOU for i in range(len(boxes)) for j in range(i + 1, len(boxes)))

def select_best(p, full):
    """Given >1 fully-verified candidates, filter out noise (non-place candidate classes, census-only rows) to explain why
    the string needs review. Same-name candidates in a nested/nominal chain (§is_ancestor) auto-resolve only when their
    boundingboxes coincide (§coterminous) — one territory under two names, a city and the county coterminous with it —
    choosing the locality-level name and recording "coterminous: one territory". Everything else among multiple
    verified candidates, nested same-name units included, stays Undecided for the owner on the fact row (CLAUDE.md).
    Returns (cand, note) or (None, reason)."""
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
    if len(names) == 1 and chain:
        if coterminous(kept):
            local = [c for c in kept if c.get("addresstype") not in ("county", "state", "country")]
            if len(local) == 1: return local[0], "coterminous: one territory"
        return None, "same-name nested/coterminous units: the owner chooses"
    return None, f"{len(kept)} distinct candidates verify"

def candidate_summary(c, score, checks):
    return {"display_name": c.get("display_name"), "osm": f"{c.get('osm_type')}/{c.get('osm_id')}", "type": leaf_type(c),
            "lat": c.get("lat"), "lon": c.get("lon"), "wikidata": (c.get("extratags") or {}).get("wikidata"), "score": round(score, 2),
            "checks": checks}

def candidate_key(c):
    """Which place one candidate of a card offers: a geocoder candidate by its OpenStreetMap id, a gazetteer's own candidate by its
    source and id, a dated former name by the place that held it."""
    if c.get("kind") == "gazetteer": return f"{c.get('source')}:{c.get('id')}"
    if c.get("kind") == "jurisdiction_change": return f"place:{c.get('place_id')}"
    return c.get("osm")

def place_groups(cx, tree_id):
    """The tree's open place cards in groups, one group a question: cards offering the same set of places, the same of them verified
    on every part of the card's string, ask the same thing of different spellings (Worcester, Montgomery County, Pennsylvania,
    USA, and Worcester, Montgomery, Pennsylvania, United States), so the owner answers it once. {proposal id: [{"proposal",
    "string", "raw"}, ...] by the string's words, the card's own included}, for every undecided place_resolution proposal whose
    string is still undecided; a card offering nothing is a group of itself."""
    by_key, rows = {}, {}
    for pid, psid, raw, cands in cx.execute("""SELECT p.id, ps.id, ps.raw, json_extract(p.payload_json,'$.candidates') FROM proposal p
            JOIN place_string ps ON ps.id=json_extract(p.payload_json,'$.place_string_id')
            WHERE p.tree_id=? AND p.kind='place_resolution' AND p.status='undecided' AND ps.status='undecided' ORDER BY ps.raw""", (tree_id,)):
        cands = json.loads(cands or "[]")
        key = (frozenset(candidate_key(c) for c in cands),
               frozenset(candidate_key(c) for c in cands if (c.get("verified") if c.get("kind") == "gazetteer" else (c.get("score") or 0) >= 0.999))) if cands else pid
        rows[pid] = {"proposal": pid, "string": psid, "raw": raw}
        by_key.setdefault(key, []).append(pid)
    return {pid: [rows[i] for i in ids] for ids in by_key.values() for pid in ids}

def place_ancestors(cx, pid):
    """pid and every place enclosing it, walking parent_id to the root."""
    chain, seen = [], set()
    while pid and pid not in seen:
        chain.append(pid); seen.add(pid)
        r = cx.execute("SELECT parent_id FROM place WHERE id=?", (pid,)).fetchone()
        pid = r[0] if r else None
    return chain

def most_specific_on_chain(cx, place_ids):
    """Among distinct place_ids, the most specific one when they all lie on a single root-to-leaf chain (a state, the
    county in it, the city in that county — facts at different levels of the same place do not disagree); None when
    any two are on different chains (Philadelphia and Pittsburgh, both under Pennsylvania but neither enclosing the
    other)."""
    if len(place_ids) == 1: return place_ids[0]
    ancestors = {pid: set(place_ancestors(cx, pid)) for pid in place_ids}
    return next((pid for pid in place_ids if all(other in ancestors[pid] for other in place_ids)), None)

def apply_to_events(cx, tree_id, actor, ts):
    """Fill event.place_id from its supporting facts' resolved places: facts on one chain (a state, the county in it, the
    city in that county) do not disagree, and the event takes the most specific place on the chain (most_specific_on_chain);
    only facts on different chains leave it unfilled. Logged per event."""
    rows = cx.execute("""
        SELECT e.id, COUNT(DISTINCT ps.id), COUNT(DISTINCT CASE WHEN ps.status='accepted' THEN ps.id END)
        FROM event e
        JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id AND a.status <> 'rejected'
        JOIN persona_fact pf ON pf.id=a.persona_fact_id
        JOIN place_string ps ON ps.id=pf.place_string_id
        WHERE e.tree_id=? AND e.place_id IS NULL
        GROUP BY e.id""", (tree_id,)).fetchall()
    n = 0
    for eid, n_strings, n_resolved in rows:
        if n_resolved != n_strings: continue
        place_ids = [r[0] for r in cx.execute("""SELECT DISTINCT ps.place_id FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id
                                                 JOIN place_string ps ON ps.id=pf.place_string_id
                                                 WHERE a.subject_kind='event' AND a.subject_id=? AND a.status <> 'rejected' AND ps.place_id IS NOT NULL""", (eid,)).fetchall()]
        chosen = most_specific_on_chain(cx, place_ids) if place_ids else None
        if chosen is None: continue
        cx.execute("UPDATE event SET place_id=?, updated_at=? WHERE id=?", (chosen, ts, eid))
        cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                   (ulid(), tree_id, ts, actor, "update", "event", eid, dumps({"place_id": chosen, "from": "accepted place_string"})))
        n += 1
    return n, len(rows) - n

def audit_string(cx, tree_id, ts, by, psid, diff):
    """One audit row per place string whose status or place the resolver changes, under the person or agent who ran it (the
    resolver's own tag is in the diff), so a reset, which clears the resolver's rows, leaves the record of what it undid."""
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, by, "update", "place_string", psid, dumps(diff)))

def reset_ai_resolutions(cx, tree_id, by, ts, only=None):
    """Undo AI-made resolutions only; human resolutions (resolver 'user:...') are always kept. Without --only, a plain
    reset is scoped to strings with an actual decision to undo (Accepted or a filled place_id) — an already-Undecided,
    AI-reviewed string is left alone, since re-querying it costs a Nominatim call for nothing already wrong. --only
    narrows to one raw value and drops that scoping: naming a string is enough to ask for it fresh, whatever its
    current status — the case that matters is a rule change that would now decide an already-reviewed Undecided string
    differently. Either way, every other AI resolution, its events and its audit trail stay untouched; the run-level
    'resolve' summary rows are left standing too, since a narrowed reset leaves most of what they describe still true.
    One audit row per string reset."""
    only_sql = " AND raw=?" if only else ""; only_args = (only,) if only else ()
    scope = "" if only else " AND (status<>'undecided' OR place_id IS NOT NULL)"
    psids = [r[0] for r in cx.execute("SELECT id FROM place_string WHERE resolver LIKE 'ai:%'" + scope + only_sql, only_args).fetchall()]
    if not psids: return
    qm = ",".join("?" * len(psids))
    ev_ids = [r[0] for r in cx.execute(f"""SELECT DISTINCT e.id FROM event e
        JOIN assertion a ON a.subject_kind='event' AND a.subject_id=e.id AND a.status<>'rejected'
        JOIN persona_fact pf ON pf.id=a.persona_fact_id
        WHERE e.tree_id=? AND e.place_id IS NOT NULL AND pf.place_string_id IN ({qm})""", (tree_id, *psids)).fetchall()]
    if ev_ids:
        eqm = ",".join("?" * len(ev_ids))
        cx.execute(f"UPDATE event SET place_id=NULL WHERE tree_id=? AND id IN ({eqm})", (tree_id, *ev_ids))
        cx.execute(f"DELETE FROM audit_log WHERE tree_id=? AND actor LIKE 'ai:%' AND action='update' AND entity_kind='event' AND entity_id IN ({eqm})", (tree_id, *ev_ids))
    cx.execute(f"DELETE FROM audit_log WHERE tree_id=? AND actor LIKE 'ai:%' AND action='update' AND entity_kind='place_string' AND entity_id IN ({qm})", (tree_id, *psids))
    if not only: cx.execute("DELETE FROM audit_log WHERE tree_id=? AND actor LIKE 'ai:%' AND action='resolve'", (tree_id,))
    cx.execute(f"DELETE FROM proposal WHERE tree_id=? AND kind='place_resolution' AND status='undecided' AND json_extract(payload_json,'$.place_string_id') IN ({qm})", (tree_id, *psids))
    for psid, raw, status, place_id, resolver in cx.execute(f"SELECT id, raw, status, place_id, resolver FROM place_string WHERE id IN ({qm})", psids).fetchall():
        audit_string(cx, tree_id, ts, by, psid, {"raw": raw, "reset": True, "resolver": resolver, "from": {"status": status, "place_id": place_id}, "to": {"status": "undecided", "place_id": None}})
    cx.execute(f"UPDATE place_string SET place_id=NULL, status='undecided', resolver=NULL, resolved_at=NULL, notes=NULL, variant_kind=NULL WHERE id IN ({qm})", psids)
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

class Unanswered(Exception):
    """The geocoder could not be reached."""

def geocode(p, extras, ask):
    """The geocoder's candidates for a parsed string: those of the first of its query variants that yields any, then those of the
    override's extra queries (they carry tree context, so their candidates rank first among ties). ask(query) raises Unanswered
    when the geocoder cannot be reached. Returns (candidates, the queries asked, the osm keys the extra queries gave)."""
    variants = query_variants(p) if (p["components"] or p["country"]) else ["Silesia"]
    cands, queries, from_extra = [], [], set()
    def add(got, extra=False):
        for c in got:
            if not any(x.get("osm_id") == c.get("osm_id") and x.get("osm_type") == c.get("osm_type") for x in cands): cands.append(c)
            if extra: from_extra.add((c.get("osm_type"), c.get("osm_id")))
    for q in variants:                     # stop at the first variant that yields anything
        queries.append(q); add(ask(q))
        if cands: break
    for q in extras:
        queries.append(q); add(ask(q), extra=True)
    return cands, queries, from_extra

def names_no_place(raw, ov):
    """Why a string names no place, or None: the override lists it whole (reject), or its words, in any case and spacing, are one of
    the phrases a record writes for the place of another line (reject_phrases: Same House)."""
    return ov["reject"].get(raw) or (ov.get("reject_phrases") or {}).get(re.sub(r"\s+", " ", raw.lower()).strip(" .,;:"))

def resolve_strings(cx, tree_id, by, rows, stats=None):
    """Resolve each (place_string id, raw) of rows, strings with no resolver yet, as the rules above say, writing under the person or
    agent `by`: the string accepted to its place, or rejected as no place, or left Undecided with a place_resolution card; then
    every event whose strings are all resolved takes its place (apply_to_events), and one audit row sums the run up. stats carries
    what the caller counted before (the places' former names) and is added to. A string whose geocoder request got no answer is
    left exactly as it was, no card, so the next run asks it again, and the geocoder is not asked again in this run. Returns
    (stats, report, unanswered): the report one (tag, string, what happened) per string, unanswered {"strings": [...], "said":
    the error} or None."""
    with open(os.path.join(ROOT, "data", "place-overrides.json"), encoding="utf-8") as fh: ov = json.load(fh)
    row = cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", RESOLVER).fetchone()
    ext_id = row[0] if row else ulid()
    if not row:
        cx.execute("INSERT INTO extractor (id,kind,name,version,config_json,created_at) VALUES (?,?,?,?,?,?)",
                   (ext_id, *RESOLVER, dumps({"endpoint": ENDPOINT, "gazetteers": {"gov": GOV_SERVICES, "wikidata": WIKIDATA_API},
                                           "verify": "every component must match a name of the candidate or of a unit in its hierarchy in full, a prefix, a truncation or a close spelling being near only; unique full match auto-resolves; a gazetteer's one verified candidate through its geocoder twin"}), now()))
    resolver_tag = f"ai:{RESOLVER[1]}@{RESOLVER[2]}"
    st = Store(cx); ts = now()
    stats = {"accepted": 0, "undecided": 0, "rejected": 0, "no_candidates": 0, "former_names_added": 0, "gazetteer_names_added": 0, **(stats or {})}
    report, unanswered, down = [], [], []
    def ask(q):
        if down: raise Unanswered(down[0])
        try: return nominatim(q)
        except Exception as e: down.append(str(e) or type(e).__name__); raise Unanswered(down[0])
    for psid, raw in rows:
        note = ov["note"].get(raw)
        not_a_place = names_no_place(raw, ov)
        if not_a_place:
            cx.execute("UPDATE place_string SET status='rejected', resolver=?, resolved_at=?, notes=? WHERE id=?",
                       (resolver_tag, ts, dumps({"reason": not_a_place}), psid)); stats["rejected"] += 1
            audit_string(cx, tree_id, ts, by, psid, {"raw": raw, "resolver": resolver_tag, "from": {"status": "undecided", "place_id": None}, "to": {"status": "rejected", "place_id": None}, "reason": not_a_place})
            report.append(("REJECT", raw, not_a_place)); continue
        p = parse(raw)
        if not p["components"] and not p["country"] and not p["region"]:
            report.append(("SKIP", raw, "nothing parseable")); continue
        dated = dated_candidate(cx, p)   # a component naming a place's own dated former name (Tonan, in "Ogau Tonan"); offered, never auto-resolved
        try: cands, queries, from_extra = geocode(p, ov["extra_queries"].get(raw, []), ask)
        except Unanswered: unanswered.append(raw); report.append(("NOANSWER", raw, down[0])); continue   # nothing is written: the string is asked again on the next run
        scope = gazetteer_for(p) if p["components"] else None
        if not p["components"] and not p["country"] and p["region"]:      # bare "Schlesien"
            p["components"] = ["Silesia"]
        head = p["components"][0].lower() if p["components"] else ""
        wants_feature = any(k in head for k in ("church", "cemetery", "road", "street", "lane", "avenue"))
        placeish = [c for c in cands if wants_feature or c.get("category") not in NONPLACE_CLASSES]
        scored = sorted(((*verify(p, c), c) for c in (placeish or cands)),
                        key=lambda x: (-x[0], -sum(v == "near" for v in x[1].values()), (x[2].get("osm_type"), x[2].get("osm_id")) not in from_extra))
        full = [s for s in scored if s[0] >= 0.999 and (wants_feature or s[2].get("category") not in NONPLACE_CLASSES)]
        forced = ov["force_review"].get(raw)
        bare = len(p["components"]) == 1 and not p["country"]
        chosen, how = ((full[0][2], "unique full match") if len(full) == 1 else (select_best(p, full) if len(full) > 1 else (None, None))) if scored else (None, None)
        gz, twin, gz_match, unreached, missed_before = [], None, None, False, len(MISSED)
        if scope and (chosen is None or forced or bare):   # the geocoder leaves the string open: ask the gazetteer that knows its places
            gz = gov_candidates(p, placeish or cands) if scope == "gov" else wikidata_candidates(p)
            unreached = len(MISSED) > missed_before
            for g in gz: g["twins"] = twin_of(g, [c for _, _, c in scored])
            verified = [g for g in gz if g["verified"]]
            if len(verified) == 1 and verified[0]["parts"] and len(verified[0]["twins"]) == 1 and all(c is verified[0]["twins"][0] for _, _, c in full):
                gz_match, twin = verified[0], verified[0]["twins"][0]
        if not scored and not gz:
            if dated:
                period = f"{dated['valid_from'] or '?'}–{dated['valid_to'] or '?'}"
                reason = f"no geocoder candidates; {dated['name']} is a dated former name of {dated['place']} ({period})"
                payload = {"raw": raw, "place_string_id": psid, "parsed": p, "queries": queries,
                           "candidates": [{**dated, "kind": "jurisdiction_change"}], "reason": reason}
                cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                           (ulid(), tree_id, "place_resolution", dumps(payload), ((note + " ") if note else "") + reason, ext_id, ts))
                cx.execute("UPDATE place_string SET resolver=?, resolved_at=?, notes=? WHERE id=?", (resolver_tag, ts, dumps({"result": "review", "reason": "dated former name", "candidate": dated, "note": note}), psid))
                stats["undecided"] += 1; report.append(("REVIEW", raw, f"dated name: {dated['name']} ({period})")); continue
            payload = {"raw": raw, "place_string_id": psid, "parsed": p, "queries": queries, "candidates": [], "reason": "no candidates"}
            cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                       (ulid(), tree_id, "place_resolution", dumps(payload), (note or "") + " No geocoder candidates; resolve by hand.", ext_id, ts))
            cx.execute("UPDATE place_string SET resolver=?, resolved_at=?, notes=? WHERE id=?", (resolver_tag, ts, dumps({"result": "no_candidates", "note": note}), psid))
            stats["no_candidates"] += 1; report.append(("NONE", raw, "")); continue
        if gz_match is not None and not forced:
            chosen, how = twin, f"gazetteer: {GAZETTEER_NAME[gz_match['source']]} {gz_match['id']}, the one candidate verified on every part, placed by its geocoder twin"
        elif bare or forced: chosen = None
        if chosen is not None:
            score, checks = next(((s_, ch) for s_, ch, c in scored if c is chosen))
            c = chosen
            leaf = st.hierarchy(c)
            if not cx.execute("SELECT 1 FROM place_name WHERE place_id=? AND name=?", (leaf, raw)).fetchone():
                cx.execute("INSERT INTO place_name (id,place_id,name,is_primary) VALUES (?,?,?,?)", (ulid(), leaf, raw, False))
            match = candidate_summary(c, score, checks)
            if gz_match is not None:
                match["gazetteer"] = gazetteer_summary(gz_match)
                stats["gazetteer_names_added"] += write_gazetteer(cx, leaf, match["gazetteer"])
            leaf_wd = cx.execute("SELECT wikidata_id FROM place WHERE id=?", (leaf,)).fetchone()
            if leaf_wd and leaf_wd[0]: stats["former_names_added"] += add_former_names(cx, leaf, leaf_wd[0])   # a place resolved for the first time, its own wikidata_id fresh from Nominatim's extratags
            cx.execute("UPDATE place_string SET place_id=?, status='accepted', resolver=?, resolved_at=?, notes=? WHERE id=?",
                       (leaf, resolver_tag, ts, dumps({"queries": queries, "how": how, "match": match,
                                                             "alternatives": [x.get("display_name") for _, _, x in full if x is not c],
                                                             "details": p["details"], "warnings": p["warnings"], "note": note}), psid))
            stats["accepted"] += 1; report.append(("OK", raw, (f"[{how}] " if how != "unique full match" else "") + c.get("display_name")))
            audit_string(cx, tree_id, ts, by, psid, {"raw": raw, "resolver": resolver_tag, "from": {"status": "undecided", "place_id": None}, "to": {"status": "accepted", "place_id": leaf}, "how": how, "place": c.get("display_name")})
        else:
            reason = forced or ("bare single token; needs context" if bare else
                                (how or f"{len(full)} fully-verified candidates") if full else "no candidate matches every component" if scored else "no geocoder candidates")
            if scope: reason += "; " + gazetteer_reason(scope, gz, unreached)
            candidates = [candidate_summary(c, s, ch) for s, ch, c in scored[:12]]
            at = {id(c): i for i, (_, _, c) in enumerate(scored[:12])}
            alone = []
            for g in sorted(gz, key=lambda g: not g["verified"]):
                if len(g["twins"]) == 1 and id(g["twins"][0]) in at and "gazetteer" not in candidates[at[id(g["twins"][0])]]:
                    candidates[at[id(g["twins"][0])]]["gazetteer"] = gazetteer_summary(g)
                else: alone.append({**gazetteer_summary(g), "kind": "gazetteer"})
            candidates += alone[:12]
            if dated: candidates.append({**dated, "kind": "jurisdiction_change"})
            payload = {"raw": raw, "place_string_id": psid, "parsed": p, "queries": queries,
                       "candidates": candidates,
                       "suggested": 0 if scored and scored[0][0] >= 0.6 else None, "reason": reason}
            cx.execute("INSERT INTO proposal (id,tree_id,kind,payload_json,rationale,generated_by,created_at,status) VALUES (?,?,?,?,?,?,?,'undecided')",
                       (ulid(), tree_id, "place_resolution", dumps(payload), ((note + " ") if note else "") + reason, ext_id, ts))
            cx.execute("UPDATE place_string SET status='undecided', resolver=?, resolved_at=?, notes=? WHERE id=?",
                       (resolver_tag, ts, dumps({"result": "review", "reason": reason, "top": candidate_summary(*scored[0][2:3], scored[0][0], scored[0][1]) if scored else None, "note": note}), psid))
            stats["undecided"] += 1; report.append(("REVIEW", raw, reason))
    stats["events_placed"], stats["events_left_unplaced"] = apply_to_events(cx, tree_id, resolver_tag, ts)
    if unanswered: stats["unanswered"] = len(unanswered)
    cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
               (ulid(), tree_id, ts, resolver_tag, "resolve", "place_string", "batch", dumps(stats)))
    return stats, report, ({"strings": unanswered, "said": down[0]} if down else None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB); ap.add_argument("--tree")
    ap.add_argument("--limit", type=int); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--only")
    ap.add_argument("--reset", action="store_true", help="undo AI-made resolutions (keeps human ones) before running; combine with --only to narrow to one raw string")
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    cx = connect(a.db)
    tree_id, slug = resolve_tree(cx, a.tree)
    if a.reset: reset_ai_resolutions(cx, tree_id, a.by, now(), only=a.only)
    former_names_added = backfill_former_names(cx)   # every place with a wikidata_id, before today's strings are read against it
    gazetteer_names_added = backfill_gazetteer(cx)   # every accepted string whose chosen candidate a gazetteer annotated
    rows = cx.execute("SELECT id, raw FROM place_string WHERE status='undecided' AND place_id IS NULL AND resolver IS NULL " + ("AND raw=?" if a.only else "") + " ORDER BY raw",
                      (a.only,) if a.only else ()).fetchall()
    if a.limit is not None: rows = rows[: a.limit]
    stats, report, unanswered = resolve_strings(cx, tree_id, a.by, rows, {"former_names_added": former_names_added, "gazetteer_names_added": gazetteer_names_added})
    if a.dry_run: cx.rollback()
    else: cx.commit()
    for tag, raw, info in report: print(f"{tag:8} {raw[:60]:60} {str(info)[:90]}")
    print("\n" + dumps(stats))
    if unanswered: print(f"\nthe geocoder did not answer ({unanswered['said'][:200]}): {len(unanswered['strings'])} string(s) left as they were; run again")

if __name__ == "__main__":
    main()
