"""The Department of Veterans Affairs' Nationwide Gravesite Locator (gravelocator.cem.va.gov): free, no login, the public
record of veterans and dependents buried in national, state and tribal veterans' cemeteries, and of those in private
cemeteries with a government headstone or marker, with dates of birth and death, rank, branch and war period (T2).

Endpoint: https://gravelocator.cem.va.gov/ngl/result, the form the site's own search page posts: lastName, firstName and
middleName each with an option (1 exact, 2 begins with, 3 contains), p_birthMM / p_birthYY and p_deathMM / p_deathYY,
cemetery blank for every cemetery, nglUP 1 for burial locations. It answers a declared tool with the results page: each
decedent's name (SURNAME, GIVEN MIDDLE), rank and branch, war period, dates of birth and death, the cemetery with its
address, and for a national cemetery the section and site. The results page is the record itself. The site publishes no
robots.txt and states no rate limit; the connector keeps to a person's pace. A search asks the surname and the first given
name exactly, the middle name's first letter as a beginning when the name has one (the locator writes RAYMOND E for a
Raymond Earl; asked with it, Davidson, Raymond falls from 22 decedents to 5), and the death year when the step carries
one. The page lists ten decedents and links its next pages, followed while the total stays within MOST; beyond that the
step is asked to narrow.
"""
import re, urllib.parse
from connectors import value
from connectors.ia import name_parts

SOURCE = "E03"
COLLECTION = "VA Nationwide Gravesite Locator"
RATE = {"search": 20}
MOST = 50                                                        # decedents read before the step is asked to narrow: five pages of ten
NEXT = re.compile(r'<a[^>]*aria-label="Go to Next Page"[^>]*href="([^"]+)"')
URL = "https://gravelocator.cem.va.gov/ngl/result"
FORM = "https://gravelocator.cem.va.gov/ngl/"                      # the page a person runs the same search from
MARK = re.compile(r'<table[^>]*\bid="searchResults"')
LABELS = {"Name": "name", "Rank & Branch": "rank_branch", "War Period": "war", "Date of Birth": "birth", "Date of Death": "death",
          "Buried At": "buried_at", "Cemetery": "cemetery", "Cemetery Address": "address", "Telephone": "telephone"}

def wants(fields):
    return None if name_parts(fields)[1] else "a surname"

def requests(fields):
    surname, given = value(fields, "surname"), value(fields, "given")
    if not surname and value(fields, "name"):
        from catalog import split_name
        given, surname, _ = split_name(str(value(fields, "name")))
    if not surname: return []
    words = str(given).split() if given else []
    first = words[0] if words else ""; middle = words[1][0] if len(words) > 1 and words[1][0].isalpha() else ""
    d = value(fields, "death_year"); year = str(int(d)) if d else ""
    form = {"nglUP": "1", "cemetery": "", "lastNameOpt": "1", "lastName": surname, "firstNameOpt": "1", "firstName": first, "middleNameOpt": "2" if middle else "1", "middleName": middle,
            "p_birthMM": "", "p_birthYY": "", "p_deathMM": "", "p_deathYY": year}
    locator = FORM + "#" + urllib.parse.urlencode([(k, v) for k, v in (("lastName", surname), ("firstName", first), ("middleName", middle), ("deathYear", year)) if v], quote_via=urllib.parse.quote)
    return [{"url": URL, "kind": "search", "data": form, "locator": locator, "record": True, "surname": surname, "given": first}]

def text(body):
    return body.decode("iso-8859-1", "replace") if isinstance(body, bytes) else body

def total(body):
    """How many decedents the page says it found: 'Displaying 1 to 2 of 2 decedent's name found.'; 0 when it says none."""
    t = text(body)
    m = re.search(r"of\s+([\d,]+)\s+decedent", t)
    if m: return int(m.group(1).replace(",", ""))
    return 0 if re.search(r"no (?:records?|decedents?|results?) (?:were |was )?found|not found", t, re.I) else None

def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).replace("&amp;", "&").replace("&nbsp;", " ").strip()

def results(body):
    """The page's decedents, one dict each: n, name, rank_branch, war, birth, death, buried_at, cemetery, address, telephone, as
    the page writes them (upper case, dates MM/DD/YYYY), and from the address its city and state (the page sets the town off
    from the street by a double space)."""
    t = text(body); m = MARK.search(t)
    if not m: return []
    table = t[m.start():t.find("</table>", m.start())]
    out, cur = [], None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        n = re.search(r'<th[^>]*item-number[^>]*>(.*?)</th>', tr, re.S)
        if n and clean(n.group(1)).isdigit(): cur = {"n": int(clean(n.group(1)))}; out.append(cur)
        lab = re.search(r'<th[^>]*row-header[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>', tr, re.S)
        if lab and cur is not None:
            key = LABELS.get(clean(lab.group(1)).rstrip(":"))
            if key: cur[key] = clean(lab.group(2))
            if key == "address":
                raw = re.sub(r"<[^>]+>", "", lab.group(2)).replace("&nbsp;", " ").strip()
                m = re.search(r"(?:^|\s{2,}|,\s*)([A-Z][A-Z .'-]*?)\s*,\s*([A-Z]{2})\s+\d{5}", re.split(r"\s{2,}", raw)[-1])
                if m: cur["city"], cur["state"] = m.group(1).strip(), m.group(2)
    return out

def next_page(url, body):
    """The next page of the same search, the link the page carries (an encoded token the site made for this search), while the
    total stays within MOST; None at the end, and None beyond MOST, where narrow() says what to add."""
    t = total(body); m = NEXT.search(text(body))
    if not m or t is None or t > MOST: return None
    return urllib.parse.urljoin(URL, m.group(1).replace("&amp;", "&"))

def narrow(url, body):
    """What the step needs when the source found more decedents than MOST: a death year, then a fuller name."""
    t = total(body)
    if t is None or t <= MOST: return None
    return f"the source found {t} decedents and only the first {MOST} are read: add a death year to the step, or a fuller name, and run it again"

def hits(url, body, request=None):
    """One hit per decedent on the page: the page itself is the record (the request says so), so a hit fetches nothing."""
    r = request or {}; loc = r.get("locator") or url
    return [{"label": f"{x.get('name') or '?'} ({x.get('birth') or '?'}–{x.get('death') or '?'}), {x.get('cemetery') or x.get('buried_at') or '?'}",
             "locator": {"kind": "url", "value": f"{loc}#{x['n']}"}, "notes": {k: v for k, v in x.items()}, "fetch": []} for x in results(body)]
