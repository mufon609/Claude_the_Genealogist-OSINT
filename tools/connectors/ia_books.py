"""Published family and local histories on the Internet Archive, through the Archive's full-text search (connectors/ia.py):
the genealogies, family and local histories among the OCR'd texts (by their titles). Compiled work is a hint, never proof (T3).

A compiled-genealogy step searches the first given name and the surname as a phrase beside the person's state, so a
common name alone asks nothing (a bare name across every book is a hint feed); the books kept are those from the person's
lifetime on. Each book kept is a hit: the page found by the search inside the item, the words around the match
as the record's text, the page image from the reader.
"""
from connectors import value
from connectors.ia import MOST_HITS, RATE, follow, fts_url, hit, items, phrase, total, within

SOURCE = "L02"
COLLECTION = "Internet Archive books"

def requests(fields):
    p = phrase(fields); st, b = value(fields, "state"), value(fields, "birth_year")
    if not p or not st: return []
    return [{"url": fts_url(f'{p} AND "{str(st).title()}" AND title:(genealogy OR genealogical OR history OR family OR descendants OR pioneers OR ancestry) AND NOT collection:newspaperarchive'),
             "kind": "search", "q": p, "surname": value(fields, "surname"), "given": value(fields, "given"), "years": [int(b) if b else None, None]}]

def hits(url, body, request=None):
    r = request or {}; lo = (r.get("years") or [None])[0]
    return [hit(it, r, f"{it['title'] or it['identifier']} ({it['year'] or '?'}): {(it['text'] or [''])[0][:120]}")
            for it in items(body) if it["identifier"] and within(it, lo, 9999)][:MOST_HITS]
