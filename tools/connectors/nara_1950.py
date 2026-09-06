"""The 1950 census on the National Archives site (1950census.archives.gov): free, no login, public domain.

Endpoint: https://1950census.archives.gov/api/search?name=<given surname>[&state=<abbr>][&county=<county>]&page=1, the search the
site's own page makes over its transcription; each result is one population schedule (a page of up to 30 name rows) with the
rows that matched under "highlight". A hit's own transcription is /api/search?scheduleId=<id> and its image the IIIF full-size
JPEG the result names. The site states no rate limit; the runner keeps to one request a second, the pace of a person using
the site. The search is fuzzy, so a result is a hit only when a highlighted name carries both the surname and the given name.
"""
import json, re, urllib.parse
from connectors import value
from connectors.loc_gov import US_STATES

SOURCE = "D05"
COLLECTION = "1950 Census (National Archives)"
RATE = {"search": 60, "json": 60, "image": 60}
ABBR = dict(zip(sorted(US_STATES), ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT",
                                    "NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]))

def place_parts(place):
    """(county, state abbreviation) from a place text such as 'Hempstead < Nassau County < New York < United States'."""
    parts = [p.strip() for p in re.split(r"[<,]", place or "") if p.strip()]
    state = next((p for p in parts if p.lower() in US_STATES), None)
    county = next((re.sub(r"\s+County$", "", p, flags=re.I) for p in parts if re.search(r"\bCounty$", p, re.I)), None)
    if county is None and state and len(parts) >= 2 and parts[parts.index(state) - 1] != parts[0]: county = parts[parts.index(state) - 1]
    return county, ABBR.get(state.lower()) if state else None

def requests(fields):
    surname, given = value(fields, "surname"), value(fields, "given")
    if not surname: return []
    county, state = place_parts(value(fields, "place"))
    if not state and value(fields, "state"): state = ABBR.get(str(value(fields, "state")).lower())
    q = [("name", " ".join(x for x in ((given or "").split()[0] if given else None, surname) if x))]
    if state: q.append(("state", state))
    if county: q.append(("county", county))
    q.append(("page", "1"))
    return [{"url": "https://1950census.archives.gov/api/search?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote), "kind": "search"}]

def total(body):
    t = json.loads(body).get("total"); return t if isinstance(t, int) else None

def key(s): return re.sub(r"[^a-z]", "", (s or "").lower())

def hits(url, body):
    d = json.loads(body); q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("name", [""])[0].split()
    given, surname = (key(q[0]), key(q[-1])) if len(q) > 1 else ("", key(q[0]) if q else "")
    out = []
    for r in d.get("results") or []:
        names = [n for v in (r.get("highlight") or {}).values() for n in v]
        matched = [n for n in names if surname and surname in key(n) and (not given or given in key(n))]
        if not matched: continue
        out.append({"label": f"{r.get('state')}, {r.get('county')}, ED {r.get('ed')}: {', '.join(matched)}",
                    "locator": {"kind": "url", "value": f"https://1950census.archives.gov/api/search?scheduleId={r['scheduleId']}"},
                    "notes": {"scheduleId": r.get("scheduleId"), "state": r.get("state"), "abbr": r.get("abbr"), "county": r.get("county"), "ed": r.get("ed"),
                              "matched": matched, "image": r.get("image")},
                    "fetch": [{"url": f"https://1950census.archives.gov/api/search?scheduleId={r['scheduleId']}", "kind": "json"},
                              {"url": "https://1950census.archives.gov/iiif/2/" + urllib.parse.quote(r["image"], safe="") + "/full/full/0/default.jpg", "kind": "image"}] if r.get("image") else
                             [{"url": f"https://1950census.archives.gov/api/search?scheduleId={r['scheduleId']}", "kind": "json"}]})
    return out
