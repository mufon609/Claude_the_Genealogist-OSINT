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
MOST = 200                                                   # results read before the step is asked to narrow: a county on the place
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
    """A search step's fields (given, surname, place) become a name search in the state and county. A fetch step's fields are the
    citation's own (name, census place, enumeration district): the search is by surname within that enumeration district, which
    the site's own search takes as a filter, so the answer is the household's schedule and its neighbours' rather than a state."""
    surname, given = value(fields, "surname"), value(fields, "given")
    if not surname and value(fields, "name"):
        parts = str(value(fields, "name")).split(); surname, given = parts[-1], " ".join(parts[:-1]) or None
    if not surname: return []
    county, state = place_parts(value(fields, "place") or value(fields, "census place"))
    if not state and value(fields, "state"): state = ABBR.get(str(value(fields, "state")).lower())
    ed = re.sub(r"\s", "", str(value(fields, "enumeration district") or ""))
    q = [("name", surname if ed else " ".join(x for x in ((given or "").split()[0] if given else None, surname) if x))]
    if state: q.append(("state", state))
    if county: q.append(("county", county))
    if ed: q.append(("ed", ed))
    q.append(("page", "1"))
    return [{"url": "https://1950census.archives.gov/api/search?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote), "kind": "search"}]

def total(body):
    t = json.loads(body).get("total"); return t if isinstance(t, int) else None

def next_page(url, body):
    """The next page of the same search while the total stays within MOST and this page was full; None at the end, and None
    when the total is beyond MOST, where narrow() says what to add."""
    d = json.loads(body); results = d.get("results") or []; t = total(body)
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query); page = int(qs.get("page", ["1"])[0])
    if not results or t is None or t > MOST or page * len(results) >= t: return None
    qs["page"] = [str(page + 1)]
    return urllib.parse.urlunparse(urllib.parse.urlparse(url)._replace(query=urllib.parse.urlencode(qs, doseq=True, quote_via=urllib.parse.quote)))

def narrow(url, body):
    """What the step needs when the source answers with more than MOST results: a county on the place, then a state."""
    t = total(body); qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if t is None or t <= MOST: return None
    need = "a state" if not qs.get("state") else "a county" if not qs.get("county") else "a fuller name"
    return f"the source answered {t} results and only the first page was read: add {need} to the step's place and run it again"

def key(s): return re.sub(r"[^a-z]", "", (s or "").lower())

def hits(url, body):
    """A schedule is a hit when a highlighted name carries both the given name and the surname searched. Within an enumeration
    district the site's own fuzzy match is the filter (a surname the transcriber misread still comes back), so every schedule it
    returns is a hit and the whole page is read: the household is the record, not one row."""
    d = json.loads(body); qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query); q = qs.get("name", [""])[0].split()
    given, surname = (key(q[0]), key(q[-1])) if len(q) > 1 else ("", key(q[0]) if q else "")
    within_ed = bool(qs.get("ed")); out = []
    for r in d.get("results") or []:
        names = [n for v in (r.get("highlight") or {}).values() for n in v]
        matched = [n for n in names if surname and surname in key(n) and (not given or given in key(n))]
        if within_ed: matched = []                              # the whole schedule: every row becomes a persona
        elif not matched: continue
        out.append({"label": f"{r.get('state')}, {r.get('county')}, ED {r.get('ed')}: {', '.join(matched or names) or 'the schedule'}",
                    "locator": {"kind": "url", "value": f"https://1950census.archives.gov/api/search?scheduleId={r['scheduleId']}"},
                    "notes": {"scheduleId": r.get("scheduleId"), "state": r.get("state"), "abbr": r.get("abbr"), "county": r.get("county"), "ed": r.get("ed"),
                              "matched": matched, "highlighted": names, "image": r.get("image")},
                    "fetch": [{"url": f"https://1950census.archives.gov/api/search?scheduleId={r['scheduleId']}", "kind": "json"},
                              {"url": "https://1950census.archives.gov/iiif/2/" + urllib.parse.quote(r["image"], safe="") + "/full/full/0/default.jpg", "kind": "image"}] if r.get("image") else
                             [{"url": f"https://1950census.archives.gov/api/search?scheduleId={r['scheduleId']}", "kind": "json"}]})
    return out
