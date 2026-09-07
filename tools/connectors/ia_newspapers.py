"""Digitized newspapers on the Internet Archive (the newspaperarchive collection: the Pottstown Mercury among them), through
the Archive's full-text search (connectors/ia.py).

An obituary step searches the first given name and the surname as a phrase within the newspapers and keeps the issues of the
death year and the year after; any other step keeps the issues of the person's lifetime. Each issue kept is a hit: the page
found by the search inside the item, the words around the match as the record's text, the page image from the reader.
"""
from connectors import value
from connectors.ia import MOST_HITS, RATE, follow, fts_url, hit, items, phrase, total, within

SOURCE = "H07"
COLLECTION = "Internet Archive newspapers"

def years(fields):
    d, b = value(fields, "death_year"), value(fields, "birth_year")
    if d: return int(d), int(d) + 1
    if b: return int(b), int(b) + 100
    return None, None

def requests(fields):
    p = phrase(fields)
    if not p: return []
    lo, hi = years(fields)
    return [{"url": fts_url(f"{p} AND collection:newspaperarchive"), "kind": "search", "q": p, "surname": value(fields, "surname"), "given": value(fields, "given"), "years": [lo, hi]}]

def hits(url, body, request=None):
    r = request or {}; lo, hi = r.get("years") or (None, None); out = []
    for it in items(body):
        if it["identifier"] and within(it, lo, hi): out.append(hit(it, r, f"{it['title'] or it['identifier']}: {(it['text'] or [''])[0][:120]}"))
    return out[:MOST_HITS]
