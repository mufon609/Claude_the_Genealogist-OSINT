"""Chronicling America through the loc.gov JSON API: free, no key, public domain.

Endpoint: https://www.loc.gov/collections/chronicling-america/?q=<surname given>&dates=<year>/<year>[&fa=location_state:<state>]&fo=json
(the collection search, first page of 20 results). Each result is one newspaper page; its OCR text comes from the text
service URL the result carries (word_coordinates_url with full_text=1), as JSON keyed by the page's ALTO segment.
Rate limits documented at https://www.loc.gov/apis/json-and-yaml/working-within-limits/: JSON API 20 requests per minute,
text services 150 per minute, image services 150 per minute; exceeding them blocks the client for an hour.
"""
import json, re, urllib.parse
from connectors import value

SOURCE = "H01"
COLLECTION = "Chronicling America (loc.gov)"
RATE = {"search": 20, "text": 150, "image": 150}
US_STATES = {"alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa",
             "kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan","minnesota","mississippi","missouri","montana","nebraska","nevada",
             "new hampshire","new jersey","new mexico","new york","north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island",
             "south carolina","south dakota","tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming"}

def state_of(place):
    """The US state named in a place text ('Pottstown < Montgomery County < Pennsylvania < United States', or a raw string)."""
    for part in re.split(r"[<,]", place or ""):
        if part.strip().lower() in US_STATES: return part.strip().lower()
    return None

def requests(fields):
    surname, given = value(fields, "surname"), value(fields, "given")
    if not surname: return []
    q = [("q", " ".join(x for x in (surname, (given or "").split()[0] if given else None) if x))]
    year = value(fields, "death_year") or value(fields, "year")
    if year: q.append(("dates", f"{year}/{year}"))
    st = state_of(value(fields, "place")) or (value(fields, "state") or "").lower() or None
    if st: q.append(("fa", f"location_state:{st}"))
    q += [("fo", "json"), ("c", "20")]
    return [{"url": "https://www.loc.gov/collections/chronicling-america/?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote), "kind": "search"}]

def total(body):
    """loc.gov's pagination 'of' is the result count ('total' is the size of the collection searched)."""
    p = json.loads(body).get("pagination") or {}
    return p.get("of") if isinstance(p.get("of"), int) else None

def hits(url, body):
    d = json.loads(body); out = []
    for r in d.get("results") or []:
        text_url = r.get("word_coordinates_url")
        if not text_url: continue
        one = lambda k: (r.get(k) or [None])[0] if isinstance(r.get(k), list) else r.get(k)
        out.append({"label": r.get("title") or r.get("id"), "locator": {"kind": "url", "value": r.get("id") or r.get("url")},
                    "notes": {"title": r.get("title"), "date": r.get("date"), "city": one("location_city"), "state": one("location_state"),
                              "lccn": one("number_lccn"), "page_id": r.get("page_id"), "page": one("number_page"), "query": urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("q", [""])[0]},
                    "fetch": [{"url": text_url + "&full_text=1", "kind": "text"}]})
    return out
