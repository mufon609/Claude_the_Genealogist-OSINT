"""WikiTree's API (api.wikitree.com): free, no key, public profiles only; a single shared tree anyone can edit, so every
profile is T4, a lead and a card for the owner, never a ground for the rule.

Endpoint: https://api.wikitree.com/api.php?action=searchPerson&FirstName=&LastName=&BirthDate=<year>&dateInclude=both
&dateSpread=2&fields=...&limit=&format=json&appId=..., the search the site's own form makes; each match is one profile with
its dates, places and parents' ids. A profile's own page is action=getProfile&key=<Name> with its parents, spouses, children
and siblings. The API asks for an appId on every request and states no rate limit; the connector keeps to a person's pace.
A step without a birth or death year asks nothing: a bare name across the whole tree is a hint feed.
"""
import json, urllib.parse
from connectors import value

SOURCE = "B04"
COLLECTION = "WikiTree profiles"
RATE = {"search": 20, "json": 30}
API = "https://api.wikitree.com/api.php"
APP = "tree-genealogy-dev"
FIELDS = "Id,Name,FirstName,MiddleName,LastNameAtBirth,LastNameCurrent,BirthDate,DeathDate,BirthLocation,DeathLocation,Gender,Father,Mother,Privacy"
PROFILE = FIELDS + ",Parents,Spouses,Children,Siblings,Bio,Touched"
MOST_HITS = 5

def wants(fields):
    """A surname, then a birth or death year: the search by name alone lists too many profiles to read."""
    if not value(fields, "surname"): return "a surname"
    if not (value(fields, "birth_year") or value(fields, "death_year")): return "a birth or death year"
    return None

def requests(fields):
    surname, given = value(fields, "surname"), value(fields, "given")
    b, d = value(fields, "birth_year"), value(fields, "death_year")
    if not surname or not (b or d): return []
    q = [("action", "searchPerson"), ("LastName", surname)]
    if given: q.append(("FirstName", str(given).split()[0]))
    if b: q.append(("BirthDate", str(int(b))))
    if d: q.append(("DeathDate", str(int(d))))
    q += [("dateInclude", "both"), ("dateSpread", "2"), ("fields", FIELDS), ("limit", "20"), ("format", "json"), ("appId", APP)]
    return [{"url": API + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote), "kind": "search"}]

def total(body):
    d = json.loads(body); r = d[0] if isinstance(d, list) and d else d
    t = r.get("total") if isinstance(r, dict) else None
    return t if isinstance(t, int) else None

def hits(url, body, request=None):
    d = json.loads(body); r = d[0] if isinstance(d, list) and d else d
    out = []
    for m in (r.get("matches") or []) if isinstance(r, dict) else []:
        name = m.get("Name")
        if not name: continue
        label = f"{m.get('FirstName') or ''} {m.get('MiddleName') or ''} {m.get('LastNameAtBirth') or ''}".split()
        out.append({"label": f"{' '.join(label)} ({name}) {m.get('BirthDate') or '?'}–{m.get('DeathDate') or '?'} {m.get('BirthLocation') or ''}".strip(),
                    "locator": {"kind": "url", "value": f"https://www.wikitree.com/wiki/{name}"},
                    "notes": {"profile": name, "id": m.get("Id"), "birth": m.get("BirthDate"), "death": m.get("DeathDate"), "birth_place": m.get("BirthLocation"), "death_place": m.get("DeathLocation")},
                    "fetch": [{"url": API + "?" + urllib.parse.urlencode([("action", "getProfile"), ("key", name), ("fields", PROFILE), ("resolveRedirect", "1"), ("format", "json"), ("appId", APP)], quote_via=urllib.parse.quote), "kind": "json"}]})
    return out[:MOST_HITS]
