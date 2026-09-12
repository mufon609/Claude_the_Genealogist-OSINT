"""City and county directories on the Internet Archive, through the Archive's full-text search (connectors/ia.py): items with
"directory" in the title, newspapers left out.

A directory step searches the first given name and the surname as a phrase in directories whose title names one of the
towns the person's events place them in, and keeps the directories of the person's adult years (from eighteen to death, or
to eighty). Each directory kept is a hit: the page found by the search inside the item, the
entry's words as the record's text, the page image from the reader.
"""
from connectors import value
from connectors.ia import MOST_HITS, RATE, follow, fts_url, hit, items, name_parts, phrase, total, within

SOURCE = "K01"
COLLECTION = "Internet Archive city directories"

def years(fields):
    b, d = value(fields, "birth_year"), value(fields, "death_year")
    if b: return int(b) + 18, int(d) if d else int(b) + 80
    if d: return int(d) - 60, int(d)
    return None, None

def requests(fields):
    p = phrase(fields); towns = value(fields, "towns") or []
    if not p or not towns: return []                                # a surname across every directory in the country is a hint feed
    lo, hi = years(fields); named = " OR ".join(f'"{t}"' for t in towns[:6]); given, surname = name_parts(fields)
    return [{"url": fts_url(f'{p} AND title:({named}) AND title:directory AND NOT collection:newspaperarchive'), "kind": "search", "q": p, "surname": surname, "given": given, "variants": value(fields, "surname_variants") or [], "years": [lo, hi]}]

def hits(url, body, request=None):
    r = request or {}; lo, hi = r.get("years") or (None, None); out = []
    for it in items(body):
        if it["identifier"] and within(it, lo, hi): out.append(hit(it, r, f"{it['title'] or it['identifier']} ({it['year'] or '?'}): {(it['text'] or [''])[0][:120]}"))
    return out[:MOST_HITS]
