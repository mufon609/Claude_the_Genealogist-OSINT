"""The Internet Archive's own services, shared by the connectors that run against it (ia_newspapers, ia_directories,
ia_books): free, no key, public domain or the item's own terms.

Full-text search:  https://be-api.us.archive.org/fts/v1/search?q=<query>&size=<n>, the search the site's own full-text page
                   makes over every OCR'd text (query-string syntax: a phrase with "~n" slop, AND, NOT, collection:<name>,
                   title:<word>); each hit is one item with the page number and the words around the match.
Item metadata:     https://archive.org/metadata/<identifier>: the server and directory the item lives on and its files.
Search inside:     https://<server>/fulltext/inside.php?item_id=&doc=&path=&q=, the search the site's book reader makes in one
                   item: every match with its text and page. It takes plain words (a quoted phrase must be exact, a slop
                   is read as a numeral), so it is asked for the surname alone and the matches naming the given name come
                   first.
Page image:        https://<server>/BookReader/BookReaderImages.php?zip=<dir>/<doc>_jp2.zip&file=<doc>_jp2/<doc>_NNNN.jp2&id=&scale=2,
                   the reader's own page image (tif items name their zip and files _tif).
The archive states no rate limit for these; the connectors keep to a person's pace. Year filters are applied here on the
hit's own year, since the search does not take them.
"""
import json, re, urllib.parse
from connectors import value

FTS = "https://be-api.us.archive.org/fts/v1/search"
RATE = {"search": 20, "json": 30, "image": 20}
MOST_HITS = 5                                                    # items read per run: each costs a metadata, a search-inside and up to three page-image requests

def phrase(fields):
    """The name searched: the first given name and the surname as a phrase with slop, so "Brant, Abram C." and "Abram C. Brant"
    both match. None without a surname."""
    surname, given = value(fields, "surname"), value(fields, "given")
    if not surname and value(fields, "name"):                          # a fetch step carries the citation's name, not given and surname
        from catalog import split_name
        g, s, _ = split_name(value(fields, "name")); surname, given = s, g
    if not surname: return None
    first = (given or "").split()[0] if given else None
    return f'"{first} {surname}"~3' if first else f'"{surname}"'

def fts_url(q, size=40):
    return FTS + "?" + urllib.parse.urlencode([("q", q), ("size", str(size))], quote_via=urllib.parse.quote)

def total(body):
    t = (json.loads(body).get("hits") or {}).get("total")
    if isinstance(t, dict): t = t.get("value")
    return t if isinstance(t, int) else None

def one(v):
    """A field the search returns as a list, or as the string form of one."""
    if isinstance(v, list): return v[0] if v else None
    if isinstance(v, str) and v.startswith("["):
        try: return one(json.loads(v.replace("'", '"')))
        except ValueError: return v
    return v

def items(body):
    """The items a full-text search names: identifier, doc (the OCR'd file's base name), title, year, date, collections,
    page and the words around the match."""
    out = []
    for h in (json.loads(body).get("hits") or {}).get("hits") or []:
        f = h.get("fields") or {}; fn = one(f.get("filename")) or ""
        coll = f.get("meta_collection"); coll = coll if isinstance(coll, list) else ([coll] if coll else [])
        year = one(f.get("meta_year")); pages = f.get("page_num")
        out.append({"identifier": one(f.get("identifier")), "doc": re.sub(r"_hocr_searchtext\.txt\.gz$", "", fn) or one(f.get("identifier")),
                    "title": one(f.get("meta_title")), "year": int(year) if str(year).isdigit() else None, "date": (one(f.get("meta_date")) or "")[:10] or None,
                    "collections": coll, "page": one(pages[0]) if isinstance(pages, list) and pages and isinstance(pages[0], list) else one(pages),
                    "text": [re.sub(r"\{\{\{|\}\}\}", "", t) for t in (h.get("highlight") or {}).get("text") or []]})
    return out

def hit(it, request, label):
    """A search hit for the runner: the item's page on the site as the locator, what the search said about it in the notes
    (with the words searched), and the item's metadata as the first fetch, from which follow() derives the search inside it
    and its page images."""
    r = request or {}
    return {"label": label, "locator": {"kind": "url", "value": f"https://archive.org/details/{it['identifier']}"},
            "notes": {"item": it["identifier"], "doc": it["doc"], "title": it["title"], "year": it["year"], "date": it["date"], "collections": it["collections"],
                      "page": it["page"], "text": it["text"], "q": r.get("q"), "surname": r.get("surname"), "given": r.get("given")},
            "fetch": [{"url": f"https://archive.org/metadata/{it['identifier']}", "kind": "json", "then": "metadata", "record": False}]}

def follow(entry, body, hit):
    """More to fetch once a response is in: an item's metadata gives the server and directory, so the search inside the item
    for the same words; the search inside gives the pages, so each page's image (the first three) from the reader. A book
    the Archive lends rather than serves (access-restricted-item) stops at its metadata: the hit names it, nothing is read."""
    then = entry.get("then"); n = hit["notes"]
    if then == "metadata":
        d = json.loads(body); server, dirn = d.get("server"), d.get("dir")
        if str((d.get("metadata") or {}).get("access-restricted-item")).lower() == "true": n["restricted"] = True; return []   # a lending-library book: its text is not served
        if not (server and dirn): return []
        files = [f["name"] for f in d.get("files") or []]
        zipf = next((f for f in files if f.endswith("_jp2.zip")), None) or next((f for f in files if f.endswith("_tif.zip")), None)
        n["server"], n["dir"], n["zip"] = server, dirn, zipf
        n["doc"] = zipf[:-8] if zipf else n["doc"]
        q = urllib.parse.urlencode([("item_id", n["item"]), ("doc", n["doc"]), ("path", dirn), ("q", n.get("surname") or n.get("q") or "")], quote_via=urllib.parse.quote)
        return [{"url": f"https://{server}/fulltext/inside.php?{q}", "kind": "json", "then": "inside"}]
    if then == "inside":
        d = json.loads(body); n["pages"] = pages = ranked_pages(d.get("matches") or [], n.get("given"))[:3]
        if not n.get("zip"): return []
        ext = "tif" if n["zip"].endswith("_tif.zip") else "jp2"; doc = n["doc"]
        out = []
        for p in pages:
            q = urllib.parse.urlencode([("zip", f"{n['dir']}/{n['zip']}"), ("file", f"{doc}_{ext}/{doc}_{p:04d}.{ext}"), ("id", n["item"]), ("scale", "2"), ("rotate", "0")], quote_via=urllib.parse.quote)
            out.append({"url": f"https://{n['server']}/BookReader/BookReaderImages.php?{q}", "kind": "image", "page": p})
        return out
    return []

def ranked_pages(matches, given):
    """The pages the matches fall on, those naming the first given name beside the surname first, in the order met."""
    first = ((given or "").split() or [""])[0].lower(); named, rest = [], []
    for m in matches:
        text = (m.get("text") or "").lower()
        for p in m.get("par") or []:
            if not isinstance(p.get("page"), int): continue
            bucket = named if first and first in text else rest
            if p["page"] not in named and p["page"] not in rest: bucket.append(p["page"])
    return named + rest

def within(it, lo, hi):
    """Whether an item's year lies in [lo, hi]; an undated item passes, since the page itself will say."""
    return it["year"] is None or lo is None or hi is None or lo <= it["year"] <= hi
