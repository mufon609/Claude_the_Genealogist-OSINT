"""Published family and local histories on the Internet Archive, through the Archive's full-text search and its advanced
search by title (connectors/ia.py): the genealogies, family and local histories among the OCR'd texts (by their titles).
Compiled work is a hint, never proof (T3).

A compiled-genealogy step searches the first given name and the surname as a phrase beside the person's state, so a
common name alone asks nothing (a bare name across every book is a hint feed); the books kept are those from the person's
lifetime on. A fetch step whose citation names a book (the book title or the citation text of a Family History Books or
North America Family Histories citation) asks the advanced search for the title and keeps the copies whose title carries
it; a citation naming no book asks nothing, and that step stays a link for a hand. Each book kept is a hit: the item's
metadata, then the search inside it for the citation's surname, the pages naming the given name first, the words around
the match as the record's text and the page image from the reader; the search inside is asked once per spelling of the
surname the alias table holds for the person. A book the Archive only lends is a none run with the reason. A name in a
book's text is a hint, never a card.
"""
import re
from connectors import value
from connectors.ia import MOST_HITS, MOST_TITLES, RATE, follow, fts_url, hit, items, name_parts, phrase, title_items, title_url, title_words, total, within

SOURCE = "L02"
COLLECTION = "Internet Archive books"
BOOKS = re.compile(r"family histor|history books|genealog|biograph", re.I)      # a collection of books: its citation text, unlabelled, is the book's title

def title_of(fields):
    """The book a fetch step's citation names: its 'book title' or 'title' part, or the citation text itself when the collection is
    one of books. None for a search step or a citation naming no book."""
    return value(fields, "book title") or value(fields, "title") or (value(fields, "citation") if BOOKS.search(str(value(fields, "collection") or "")) else None)

def requests(fields):
    t = title_of(fields)
    if t:
        url = title_url(t)
        if not url: return []
        given, surname = name_parts(fields)
        return [{"url": url, "kind": "search", "by": "title", "title": t, "q": '"' + " ".join(title_words(t)) + '"', "surname": surname, "given": given, "variants": value(fields, "surname_variants") or []}]
    p = phrase(fields); st, b = value(fields, "state"), value(fields, "birth_year")
    if not p or not st: return []
    return [{"url": fts_url(f'{p} AND "{str(st).title()}" AND title:(genealogy OR genealogical OR history OR family OR descendants OR pioneers OR ancestry) AND NOT collection:newspaperarchive'),
             "kind": "search", "q": p, "surname": name_parts(fields)[1], "given": name_parts(fields)[0], "variants": value(fields, "surname_variants") or [], "years": [int(b) if b else None, None]}]

def hits(url, body, request=None):
    r = request or {}
    if r.get("by") == "title":
        return [hit(it, r, f"{it['title'] or it['identifier']} ({it['year'] or '?'}): the cited book") for it in title_items(body, r.get("title"))][:MOST_TITLES]
    lo = (r.get("years") or [None])[0]
    return [hit(it, r, f"{it['title'] or it['identifier']} ({it['year'] or '?'}): {(it['text'] or [''])[0][:120]}")
            for it in items(body) if it["identifier"] and within(it, lo, 9999)][:MOST_HITS]
