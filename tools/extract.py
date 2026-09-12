#!/usr/bin/env python3
"""Extract personas and facts from an archived record page (HTML) or a connector response (JSON).

usage: tools/extract.py <sha256 | path> [--db catalog/tree.db] [--by user:<you>]

A parser claims the page by its own marker, or the extraction fails. A Find a
Grave memorial (body id memorial-summary) goes to rule:findagrave-memorial@0.3.0;
a FamilySearch record page (its "Cite This Record" block, data-testid
documentInformationCitation, naming an ark under familysearch.org/ark:/61903/1:1:)
goes to rule:familysearch-record@0.1.0; a FamilySearch search results page (rows
carrying a record ark as their data-testid) goes to rule:familysearch-search@0.1.0,
one persona per row with the ark as its identity, the row's events and the
relatives it names; an
Ancestry index page (a table whose rows pair a label cell with a value cell,
the shape that parser reads; unverified on a real page) goes to
rule:ancestry-index@0.1.0. A page no parser claims gets one extraction by
rule:extract@0.1.0 with status failed, the reason in structured_json, no
personas, and the matcher is not run. One extraction per run over the artifact, with:
  persona          one per person the page names: the record's subject, each
                   household member, and each relative named in a field
                   (Father, Mother, Spouse, Informant). role_in_record is the
                   page's own word (head, wife, son, deceased, informant).
  persona_fact     one per field, as written: Name, Sex, Age, Birth, Death,
                   Burial, Residence, Relationship, Occupation, Marital Status,
                   Race and whatever else the page carries (fact_type Unknown
                   keeps the label). A date and a place of the same kind
                   (Birth Date + Birth Place) are one fact. region_json is the
                   field label. Dates go through treelib's date grammar only;
                   places become place_string rows, Undecided, as written.
  persona_relation one row per stated relationship, from the persona whose
                   role it is to the persona it is toward: a household member
                   to the head (kind child, "Son"), a named relative to the
                   subject (kind parent, "Father's name"), value_text as
                   written.
extraction.structured_json holds the raw parsed page: every label/value pair
and every table. Re-running inserts a new extraction, marks the old one
superseded, and rejects the old one's undecided proposals with the note
superseded: they rested on personas that are no longer current. A persona the
old extraction had decided (accepted or rejected as a person) carries its
decision to the new persona of the same name and role on the same page: the
decision was about the record, and the bytes have not changed; an accepted link
then asserts the new extraction's facts and links the same way the decision did,
adding only what the record did not already assert. Everything else is
matched again.

Page structure assumed for an Ancestry index page: the record's fields are rows
of a table with a label cell (th, or the first cell) and a value cell; a table
whose header row has a Name column lists household members, one per row (a
Relationship column, when present, is the member's role). Anything the page
does not carry is absent.

A Find a Grave memorial (verified on a real page): the subject's name in the
h1 bio-name; birth and death as the time/span and place elements birthDateLabel,
birthLocationLabel, deathDateLabel ("10 Oct 1961 (aged 81)", the age becomes an
Age fact), deathLocationLabel; the cemetery name and its address spans as the
Burial place, the plot (plotValueLabel) as the Burial fact's value and the
inscription (inscriptionValue) as an Inscription fact, as written; the memorial
id as an Identification Number fact. Family members are the
member-family lists, each labelled Parents, Spouse, Siblings or Children: one
persona per member in the label's role word, with the name as written (a
maiden name is italic on the page and kept inside the name), the birth and
death years, and one relation from the member to the subject (parent, spouse,
sibling, child) with the label as written. The member's own memorial URL is in
its region_json. structured_json holds the fields, the members, the source
block (created by, added, citation) and the photographs: each one's id,
full-size image URL, caption and the type the page gives it (Grave, Person,
Family); those typed Grave become the gravestone fetch steps (tools/plan.py).

A FamilySearch record page (verified on a real 1900 census page): the subject's
name in the h1 and the collection in the h2; the "Document Information" table
(digital folder, microfilm, image number, batch) kept in structured_json; the
subject's details table under "Cite This Record" as the fields, labelled as the
page labels them (Name, Sex, Age, Birth Date, Birthplace, Marital Status, Race,
Relationship to Head of Household, Father's Birthplace, Mother's Birthplace,
Event Type, Event Date, Event Place, Event Place (Original), and the sheet and
line). Event Date and Event Place become one fact of the event's type (a Census
event is a Residence); Event Place (Original) and the parents' birthplaces stay
as Unknown facts under their labels; identifiers stay in structured_json. The
household tables ("Parents and Siblings", "Extended Family") give one persona
per member: the name, the page's own role word (Father, Sister, Maternal
Grandmother), sex, age and birthplace from the row, the member's own details
table as its facts, its record ark in region_json, and one relation from the
member to the subject with the role word as written. The page's own ark, from
the print header, is written to artifact_locator as kind ark.

Connector responses (JSON, archived by tools/run_step.py) have their own extractors, claimed by the response's shape:
  rule:nara-1950-schedule@0.1.0  one schedule from the 1950 census site (a single result with scheduleId and names and no
                                 search highlight, as /api/search?scheduleId= answers): one persona per
                                 transcribed row the search matched, named as transcribed, with a Residence in the county and
                                 state in 1950 and the enumeration district and row under their labels; the whole schedule in
                                 structured_json.
  rule:ia-search-inside@0.1.0    the Internet Archive's search inside one item (ia, q, matches with text and page): the matches'
                                 text read as loc-gov-ocr reads a page, the item's date and title as the page's; a directory
                                 entry (the Archive's directory connector) also gives a Residence on the directory's date.
  rule:loc-gov-ocr@0.1.0         a page's OCR text from loc.gov's text service (segments with full_text): one persona per place
                                 the searched surname stands in the text, named by the words around it, with the snippet and
                                 the page's date, title and place in the region, and no fact beyond the name: running text
                                 states no date of the person's life. The runner's notes on the response supply the surname,
                                 the step's kind and the connector.
"""
import argparse, html, json, os, re, sqlite3, sys, urllib.parse
from html.parser import HTMLParser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, object_path, parse_gedcom_date, sha256_file, ulid
from conclude import assert_facts, link_family

EXTRACTORS = {"ancestry": ("rule", "ancestry-index", "0.1.0"), "findagrave": ("rule", "findagrave-memorial", "0.3.0"), "findagrave_search": ("rule", "findagrave-search", "0.1.0"),
              "familysearch": ("rule", "familysearch-record", "0.1.0"), "familysearch_search": ("rule", "familysearch-search", "0.1.0"), "nara1950": ("rule", "nara-1950-schedule", "0.1.0"),
              "locgov": ("rule", "loc-gov-ocr", "0.1.0"), "ia_inside": ("rule", "ia-search-inside", "0.1.0"),
              "aad_search": ("rule", "aad-search", "0.1.0"), "aad_record": ("rule", "aad-enlistment", "0.1.0"), "wikitree": ("rule", "wikitree-profile", "0.1.0"),
              "va_graves": ("rule", "va-gravesite", "0.1.0"),
              None: ("rule", "extract", "0.1.0")}
EVENT_TYPES = {"census": "Residence", "residence": "Residence", "birth": "Birth", "death": "Death", "marriage": "Marriage", "burial": "Burial"}

# field label -> (fact_type, part): part is 'date', 'place' or 'value'
LABELS = [
    (r"^name$", "Name", "value"), (r"^(gender|sex)$", "Sex", "value"), (r"^age( in \d{4}|at death)?$", "Age", "value"),
    (r"^(estimated )?birth (date|year)$|^birth$|^born$", "Birth", "date"), (r"^birth ?place$|^birth location$", "Birth", "place"),
    (r"^death (date|year)$|^death$|^died$", "Death", "date"), (r"^death ?place$|^death location$", "Death", "place"),
    (r"^burial (date|year)$", "Burial", "date"), (r"^burial ?place$|^cemetery$", "Burial", "place"),
    (r"^marriage (date|year)$", "Marriage", "date"), (r"^marriage ?place$", "Marriage", "place"),
    (r"^(residence|home) (date|year)$", "Residence", "date"), (r"^residence$|^home in \d{4}$|^home$|^residence ?place$|^street address$", "Residence", "place"),
    (r"^(relation(ship)?( to head( of house(hold)?)?)?)$", "Relationship", "value"), (r"^occupation$", "Occupation", "value"),
    (r"^marital status$", "Marital Status", "value"), (r"^race$|^color( or race)?$", "Race", "value"), (r"^nationality$", "Nationality", "value"),
    (r"^arrival (date|year)$", "Arrival", "date"), (r"^arrival ?place$|^port of arrival$", "Arrival", "place"),
    (r"^immigration (date|year)$", "Immigration", "date"), (r"^naturalization (date|year)$", "Naturalization", "date"),
    (r"^religion$", "Religion", "value"), (r"^cause of death$", "Cause of Death", "value"), (r"^(ssn|social security number)$", "Social Security Number", "value"),
]
RELATIVE_LABELS = {"father": ("father", "parent"), "mother": ("mother", "parent"), "spouse": ("spouse", "spouse"), "husband": ("husband", "spouse"),
                   "wife": ("wife", "spouse"), "informant": ("informant", "informant"), "child": ("child", "child")}
HOUSEHOLD_KINDS = [(r"grand|in.law|aunt|uncle|niece|nephew|cousin|step", "other"), (r"^(self|head)", "head"), (r"wife|husband|spouse", "spouse"),
                   (r"son|daughter|child", "child"), (r"father|mother|parent", "parent"), (r"brother|sister", "sibling"), (r"boarder|lodger|servant|roomer", "boarder")]
SKIP = re.compile(r"source|citation|page|line|sheet|enumeration|district|roll|film|series|ward|township|county|state|record type|record number|title|url|household members|save|print"
                  r"|household identifier|affiliate|digital folder|image number|indexing batch|event type", re.I)

class Page(HTMLParser):
    """Collects every table as rows of cell texts (with th flagged), nested tables included, in document order."""
    def __init__(self):
        super().__init__(); self.tables, self.stack, self.title, self._in_title = [], [], "", False
    def handle_starttag(self, tag, attrs):
        if tag == "table": self.stack.append({"rows": [], "nested": []})
        elif tag == "tr" and self.stack: self.stack[-1]["rows"].append([])
        elif tag in ("td", "th") and self.stack and self.stack[-1]["rows"]: self.stack[-1]["rows"][-1].append({"th": tag == "th", "text": []})
        elif tag == "br" and self.stack and self.stack[-1]["rows"] and self.stack[-1]["rows"][-1]: self.stack[-1]["rows"][-1][-1]["text"].append("\n")
        elif tag == "title": self._in_title = True
    def handle_endtag(self, tag):
        if tag == "table" and self.stack:
            t = self.stack.pop(); t["rows"] = [[{"th": c["th"], "text": clean("".join(c["text"]))} for c in r] for r in t["rows"] if r]
            (self.stack[-1]["nested"] if self.stack else self.tables).append(t)
            if self.stack: self.tables.append(t)
        elif tag == "title": self._in_title = False
    def handle_data(self, data):
        if self._in_title: self.title += data
        if self.stack and self.stack[-1]["rows"] and self.stack[-1]["rows"][-1]: self.stack[-1]["rows"][-1][-1]["text"].append(data)

def clean(s): return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(s)).strip().strip(":").strip()

class Tree(HTMLParser):
    """A light element tree: {tag, attrs, children} nodes with text children as strings."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.root = {"tag": "root", "attrs": {}, "children": []}; self.stack = [self.root]
    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}; self.stack[-1]["children"].append(node)
        if tag not in self.VOID: self.stack.append(node)
    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag: del self.stack[i:]; break
    def handle_data(self, data): self.stack[-1]["children"].append(data)

def walk(node):
    yield node
    for c in node["children"]:
        if isinstance(c, dict): yield from walk(c)

def text_of(node):
    """The node's text with whitespace collapsed, a br as a newline."""
    out = []
    for c in node["children"]:
        if isinstance(c, str): out.append(c)
        elif c["tag"] == "br": out.append("\n")
        elif c["tag"] not in ("script", "style"): out.append(text_of(c))
    norm = lambda line: html.unescape(line).strip()
    return "\n".join(norm(line) for line in re.sub(r"[ \t\r\f\v]+", " ", "".join(out)).split("\n") if norm(line))

def by_id(root, id_): return next((n for n in walk(root) if n["attrs"].get("id") == id_), None)

def parse_memorial(text):
    """A Find a Grave memorial page: {"kind": "findagrave", "title", "fields": [[label, value]], "memorial_id", "members": [...], "source": {...},
    "photos": [{"id", "url", "caption", "type", "added_by"}]}: each photograph in the page's viewer with its full-size image, its caption and
    the type the page gives it (Grave, Person, Family)."""
    t = Tree(); t.feed(text); root = t.root
    get = lambda i: (text_of(by_id(root, i)) or None) if by_id(root, i) else None
    fields = []
    add = lambda label, value: fields.append([label, value]) if value else None
    add("Name", get("bio-name")); add("Birth Date", get("birthDateLabel")); add("Birth Place", get("birthLocationLabel"))
    add("Death Date", get("deathDateLabel")); add("Death Place", get("deathLocationLabel"))
    cemetery = [get(i) for i in ("cemeteryNameLabel", "cemeteryCityName", "cemeteryCountyName", "cemeteryStateName", "cemeteryCountryName")]
    add("Burial Place", ", ".join(x for x in cemetery if x)); add("Plot", get("plotValueLabel")); add("Inscription", get("inscriptionValue"))
    add("Biography", get("fullBio"))                            # the contributor's text, often the obituary itself, as written
    memorial_id = get("memNumberLabel"); add("Memorial ID", memorial_id)
    members = []
    for ul in (n for n in walk(root) if n["tag"] == "ul" and "member-family" in (n["attrs"].get("class") or "")):
        label_node = by_id(root, ul["attrs"].get("aria-labelledby") or ""); label = text_of(label_node) if label_node else "Family"
        for li in (c for c in ul["children"] if isinstance(c, dict) and c["tag"] == "li"):
            a = next((n for n in walk(li) if n["tag"] == "a" and n["attrs"].get("href")), None)
            h3 = next((n for n in walk(li) if n["tag"] == "h3"), None)
            if not h3: continue
            maiden = next((text_of(n) for n in walk(h3) if n["tag"] == "i"), None)
            years = {n["attrs"]["itemprop"]: text_of(n) for n in walk(li) if n["attrs"].get("itemprop") in ("birthDate", "deathDate")}
            members.append({"label": label, "name": text_of(h3).replace("\n", " "), "maiden": maiden, "birth": years.get("birthDate"), "death": years.get("deathDate"),
                            "url": a["attrs"]["href"] if a else None})
    src = by_id(root, "source"); source = {}
    if src:
        for li in (c for c in src["children"] if isinstance(c, dict) and c["tag"] == "li"):
            line = text_of(li).replace("\n", " ")
            if "citation" in (li["attrs"].get("class") or ""): source["citation"] = re.sub(r"^Source (Hide|Show) citation ", "", line)
            elif line.startswith("Created by"): source["created_by"] = line
            elif line.startswith("Added"): source["added"] = line
    photos = []
    for n in (n for n in walk(root) if n["tag"] == "div" and "viewer-item" in (n["attrs"].get("class") or "").split() and n["attrs"].get("data-photo-id")):
        img = next((x for x in walk(n) if x["tag"] == "img" and (x["attrs"].get("data-src") or x["attrs"].get("src"))), None)
        body = text_of(n)
        photos.append({"id": n["attrs"]["data-photo-id"], "url": (img["attrs"].get("data-src") or img["attrs"].get("src")) if img else None,
                       "caption": next((text_of(x).replace("\n", " ") for x in walk(n) if "photo-text" in (x["attrs"].get("class") or "") and text_of(x)), None),
                       "type": (re.search(r"Photo type:\s*(\w+)", body) or [None, None])[1], "added_by": (re.search(r"Added by:\s*(.+)", body) or [None, None])[1]})
    title = next((text_of(n) for n in walk(root) if n["tag"] == "title"), "")
    return {"kind": "findagrave", "title": title, "fields": fields, "memorial_id": memorial_id, "members": members, "source": source, "photos": photos}

FS_MARK = re.compile(r'data-testid="documentInformationCitation"[^\x00]{0,400}?https://(?:www\.)?familysearch\.org/ark:/61903/1:1:')

def rows_of(table):
    """The table's own rows (not a nested table's), each as its cells."""
    out = []
    for c in table["children"]:
        if not isinstance(c, dict): continue
        for r in ([c] if c["tag"] == "tr" else [x for x in c["children"] if isinstance(x, dict) and x["tag"] == "tr"] if c["tag"] in ("thead", "tbody", "tfoot") else []):
            out.append([x for x in r["children"] if isinstance(x, dict) and x["tag"] in ("th", "td")])
    return out

def visible(node):
    """The node with its display:none subtrees removed (a collapsed panel beside a value is not the value)."""
    return {"tag": node["tag"], "attrs": node["attrs"], "children": [visible(c) if isinstance(c, dict) else c for c in node["children"]
            if not (isinstance(c, dict) and re.search(r"display:\s*none", c["attrs"].get("style") or ""))]}

def label_rows(table):
    """[[label, value]] from a table whose rows pair a th with a td, the value as shown."""
    return [[text_of(r[0]), text_of(visible(r[1])).replace("\n", " ")] for r in rows_of(table) if len(r) >= 2 and r[0]["tag"] == "th" and text_of(r[0])]

def parse_record(text):
    """A FamilySearch record page: {"kind": "familysearch", "title", "name", "collection", "ark", "citation", "document": [[label, value]],
    "fields": [[label, value]], "members": [{"section", "name", "role", "sex", "age", "birthplace", "url", "fields"}]}."""
    t = Tree(); t.feed(text); root = t.root
    main = next((n for n in walk(root) if n["tag"] == "main"), root)
    head = lambda tag: next((text_of(n) for n in walk(main) if n["tag"] == tag), None)
    out = {"kind": "familysearch", "title": next((text_of(n) for n in walk(root) if n["tag"] == "title"), ""), "name": head("h1"), "collection": head("h2"),
           "ark": None, "citation": None, "document": [], "fields": [], "members": []}
    m = next((re.search(r"ark:/61903/1:1:[A-Z0-9-]+", text_of(n)) for n in walk(root) if n["tag"] == "h3" and "ark:/61903/1:1:" in text_of(n)), None)
    if m: out["ark"] = m.group(0)
    cite = next((n for n in walk(main) if n["attrs"].get("data-testid") == "documentInformationCitation"), None)
    if cite: out["citation"] = text_of(cite).replace("\n", " ")
    section, seen = "", set()
    for n in walk(main):
        if n["tag"] == "h3": section = text_of(n); continue
        if n["tag"] != "table" or id(n) in seen: continue
        seen.add(id(n)); rows = rows_of(n)
        if section.startswith("Document Information"): out["document"] += label_rows(n)
        elif not out["fields"] and (section.startswith("Cite This Record") or not section) and label_rows(n) and not (rows and any(len(r) == 5 for r in rows)):
            out["fields"] = label_rows(n)                                    # the record's own fields: the first label/value table, before any section heading
        elif rows and any(len(r) >= 5 and r[0]["tag"] == "th" for r in rows):   # household or relatives: a member row, then a row holding its details table
            member = None
            for r in rows:
                if len(r) >= 5 and r[0]["tag"] == "th":
                    a = next((x for x in walk(r[0]) if x["tag"] == "a"), None)
                    name = text_of(a) if a else text_of(r[0]).split("\n")[0]
                    role = text_of(r[0]).replace("\n", " ").replace(name, "", 1).strip()
                    cells = r[1:]
                    if not role and cells and re.fullmatch(r"[A-Za-z][A-Za-z ]{2,}", text_of(cells[0]).strip() or "") and text_of(cells[0]).strip().lower() not in ("male", "female"):
                        role, cells = text_of(cells[0]).strip(), cells[1:]       # a vital record's relatives: the role word in its own cell after the name
                    cell = lambda i: text_of(cells[i]) if i < len(cells) else ""
                    member = {"section": section, "name": name, "role": role, "sex": cell(0), "age": cell(1), "birthplace": cell(2),
                              "url": a["attrs"].get("href") if a else None, "fields": []}
                    out["members"].append(member)
                elif len(r) == 1 and member is not None:
                    for tbl in (x for x in walk(r[0]) if x["tag"] == "table"):
                        seen.add(id(tbl)); member["fields"] += label_rows(tbl)
    return out

SEARCH_PARAMS = ("firstname", "lastname", "birthyear", "birthyearfilter", "deathyear", "deathyearfilter", "linkedToName", "includeMaidenName", "location", "orderby", "page")

def parse_search(text):
    """A Find a Grave memorial search results page: {"kind": "findagrave_search", "query": {param: value} as the page's own form
    carries them, "url": the search URL rebuilt from them, "count": the matching records the page states, "pages": the page count
    (goto-max-pages), "page": the page shown, "rows": [{"n", "memorial_id", "url", "name", "birth", "death", "cemetery",
    "cemetery_url", "place", "plot"}]}. The name is the h2.name-grave's own text without the badges beside it; the dates are
    b.birthDeathDates; the cemetery is the form to /cemetery/<id>/<slug>; the place and the plot are the p.addr-cemet lines."""
    t = Tree(); t.feed(text); root = t.root
    form = next((n for n in walk(root) if n["tag"] == "form" and n["attrs"].get("id") == "memorialNewSearchForm"), None)
    query = {}
    for n in walk(form or root):
        name = n["attrs"].get("name")
        if name not in SEARCH_PARAMS: continue
        if n["tag"] == "input":
            if n["attrs"].get("type") == "checkbox":
                if "checked" in n["attrs"]: query[name] = n["attrs"].get("value") or "true"
            elif n["attrs"].get("value"): query.setdefault(name, n["attrs"]["value"])
        elif n["tag"] == "select":
            sel = next((o for o in walk(n) if o["tag"] == "option" and "selected" in o["attrs"]), None)
            if sel and sel["attrs"].get("value"): query.setdefault(name, sel["attrs"]["value"])
    m = re.search(r"[?&]page=(\d+)", text[:20000]); query.setdefault("page", m.group(1) if m else "1")
    url = "https://www.findagrave.com/memorial/search?" + "&".join(f"{k}={urllib.parse.quote(str(query[k]))}" for k in SEARCH_PARAMS if k in query and not (k == "page" and query[k] == "1"))
    count = next((int(m.group(1)) for n in walk(root) if n["tag"] == "h1" and (m := re.search(r"([\d,]+) matching record", text_of(n).replace(",", ""))) ), None)
    pages = next((int(re.sub(r"\D", "", text_of(n)) or 1) for n in walk(root) if n["attrs"].get("id") == "goto-max-pages"), 1)
    rows = []
    for n in walk(root):
        if n["tag"] != "div" or not (n["attrs"].get("id") or "").startswith("sr-") or "memorial-item" not in (n["attrs"].get("class") or ""): continue
        mid = n["attrs"]["id"][3:]
        a = next((x for x in walk(n) if x["tag"] == "a" and (x["attrs"].get("href") or "").startswith("/memorial/")), None)
        h2 = next((x for x in walk(n) if x["tag"] == "h2" and "name-grave" in (x["attrs"].get("class") or "")), None)
        i = next((x for x in walk(h2) if x["tag"] == "i"), None) if h2 else None
        dates = next((text_of(x) for x in walk(n) if x["tag"] == "b" and "birthDeathDates" in (x["attrs"].get("class") or "")), "")
        birth, death = ([s.strip() or None for s in re.split(r"\s[–-]\s", dates, 1)] + [None, None])[:2] if dates else (None, None)
        cem = next((x for x in walk(n) if x["tag"] == "form" and (x["attrs"].get("action") or "").startswith("/cemetery/")), None)
        btn = next((text_of(x) for x in walk(cem) if x["tag"] == "button"), None) if cem else None
        place = plot = None
        for pnode in (x for x in walk(n) if x["tag"] == "p" and "addr-cemet" in (x["attrs"].get("class") or "")):
            txt = re.sub(r"\s*,\s*", ", ", text_of(pnode).replace("\n", " ")).strip(" ,")
            if txt.lower().startswith("plot info"): plot = re.sub(r"^plot info:?\s*", "", txt, flags=re.I).strip() or None
            elif place is None: place = txt or None
        rows.append({"n": len(rows) + 1, "memorial_id": mid, "url": "https://www.findagrave.com" + a["attrs"]["href"] if a else f"https://www.findagrave.com/memorial/{mid}",
                     "name": text_of(i).replace("\n", " ").strip() if i else (text_of(h2).split("\n")[0].strip() if h2 else None), "birth": birth, "death": death,
                     "cemetery": btn, "cemetery_url": "https://www.findagrave.com" + cem["attrs"]["action"] if cem else None, "place": place, "plot": plot})
    return {"kind": "findagrave_search", "title": next((text_of(n) for n in walk(root) if n["tag"] == "title"), ""), "query": query, "url": url, "count": count,
            "pages": pages, "page": int(query.get("page") or 1), "rows": rows}

FS_SEARCH_MARK = re.compile(r'<tr[^>]*\bdata-testid="/ark:/61903/1:1:')
FS_EVENTS = {"census": "Residence", "residence": "Residence", "birth": "Birth", "christening": "Christening", "death": "Death", "marriage": "Marriage", "burial": "Burial"}

def parse_fs_search(text):
    """A FamilySearch record search results page saved in the browser: {"kind": "familysearch_search", "query": the search's own
    fields from the saved-from URL (q.givenName, q.surname, q.birthLikeDate.from/to, q.anyPlace, f.collectionId, …), "url", "count":
    the results the page states, "page", "pages", "rows": [{"n", "ark", "url", "name", "role", "collection", "events": [{"type",
    "date", "place"}], "relations": {"Parents": [names], "Spouses": …, "Children": …, "Siblings": …}}]}: one row per <tr> carrying
    a record ark as its data-testid, the name from the row's link, the role word and collection under it, each event as its
    label, date and place, each relationship label with the names after it."""
    saved = re.search(r"<!-- saved from (\S+) -->", text[:4000]); url = html.unescape(saved.group(1)) if saved else None
    query = {k: v for k, v in urllib.parse.parse_qsl(urllib.parse.urlsplit(url or "").query)} if url else {}
    count = re.search(r"Results \((\d[\d,]*)\)", text); count = int(count.group(1).replace(",", "")) if count else None
    rows = []
    for m in re.finditer(r'<tr[^>]*\bdata-testid="(/ark:/61903/1:1:[^"]+)"[^>]*>(.*?)</tr>', text, re.S):
        ark, body = m.group(1).lstrip("/"), m.group(2)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        if len(cells) < 3: continue
        strip = lambda s: clean(re.sub(r"<[^>]+>", " ", s))
        a = re.search(r'<a[^>]*href="(/ark:/61903/1:1:[^"?]+)[^"]*"[^>]*>(.*?)</a>', cells[1], re.S)
        name = strip(a.group(2)) if a else None
        under = re.search(r"</h2>|<div[^>]*>(.*?)</div>", cells[1], re.S)
        role_coll = re.search(r"<strong>.*?</strong>\s*<br\s*/?>\s*<div[^>]*>(.*?)</div>", cells[1], re.S)
        role, collection = (None, None)
        if role_coll:
            parts = [clean(x) for x in re.split(r"<br\s*/?>", role_coll.group(1)) if clean(re.sub(r"<[^>]+>", " ", x))]
            role, collection = (parts[0].lower() if parts else None), (parts[1] if len(parts) > 1 else None)
        events, relations = [], {}
        for d in re.findall(r"<div[^>]*>\s*<strong>([^<]+)</strong>(.*?)</div>", cells[2], re.S):
            label, rest = clean(d[0]), d[1]
            key = label.lower()
            if key in FS_EVENTS:
                parts = re.split(r"<br[^>]*>", rest)                     # the date's spans before the break, the place after it
                inline = [clean(s).strip() for s in re.findall(r"<span[^>]*>(.*?)</span>", parts[0], re.S)]
                date = next((s for s in inline if s), None) or None
                place = strip(parts[1]).strip() if len(parts) > 1 else None
                if date and not re.search(r"\d", date): place, date = (place or date), None   # a census with no date: what stands there is a place
                if place and place.lower() == "other places": place = None                       # the site's word for a place it does not show, not a place
                events.append({"type": FS_EVENTS[key], "label": label, "date": date, "place": place or None})
            else:
                names = [n.strip() for n in strip(rest).split(",") if n.strip()]
                if names: relations[label] = names
        if name: name = re.sub(r"\s+undefined$", "", name).strip() or None                 # a stray word the site's script leaves in the saved markup
        if collection and re.search(r"census", collection, re.I):                          # a census index's birth is estimated from an age: a calculated year
            for e in events:
                if e["type"] == "Birth" and e["date"] and re.fullmatch(r"\d{4}", e["date"]): e["date"] = "CAL " + e["date"]
        rows.append({"n": len(rows) + 1, "ark": ark, "url": "https://www.familysearch.org/" + ark + "?lang=en", "name": name, "role": role, "collection": collection, "events": events, "relations": relations})
    per = len(rows) or 20; offset = int(query.get("offset") or 0)
    page = offset // per + 1; pages = max(1, -(-count // per)) if count else 1
    return {"kind": "familysearch_search", "title": next((clean(t) for t in re.findall(r"<title>(.*?)</title>", text, re.S)), ""), "query": query, "url": url, "count": count, "page": page, "pages": pages, "rows": rows, "fields": []}

def parse(text):
    """The page's kind and its parsed form, or (None, reason) when no parser claims the page."""
    if re.search(r'<body[^>]*\bid="memorial-summary"', text): return "findagrave", parse_memorial(text)
    if re.search(r'<body[^>]*\bid="memorial-list"', text): return "findagrave_search", parse_search(text)
    if FS_MARK.search(text): return "familysearch", parse_record(text)
    if FS_SEARCH_MARK.search(text): return "familysearch_search", parse_fs_search(text)
    if AAD_MARK.search(text) and re.search(r'<table[^>]*\bid="queryResults"', text): return "aad_search", parse_aad_search(text)
    if AAD_MARK.search(text) and re.search(r"Display Full Records", text): return "aad_record", parse_aad_record(text)
    if VA_MARK.search(text) and re.search(r"Grave Locator", text): return "va_graves", parse_va(text)
    page = parse_page(text)
    if page["fields"] or page["household"]: return "ancestry", page
    return None, {"reason": "no parser claims this page: not a Find a Grave memorial or search results page, not a FamilySearch record page, and no table pairs a label cell with a value cell"}

AAD_MARK = re.compile(r"Access to Archival Databases \(AAD\)|<title>NARA - AAD")
VA_MARK = re.compile(r'<table[^>]*\bid="searchResults"')

def va_name(s):
    """A name as the gravesite locator writes it, DAVIDSON, RAYMOND E, the right way round: Raymond E Davidson."""
    parts = [p.strip() for p in (s or "").split(",", 1)]
    words = parts[1].split() + parts[0].split() if len(parts) == 2 else (s or "").split()
    return " ".join(w.capitalize() for w in words)

def parse_va(text):
    """A results page of the VA's Nationwide Gravesite Locator: {"kind": "va_graves", "url" (the saved-from comment when the page
    was saved by hand), "count", "rows"} with the rows as connectors/va_graves.results reads the page."""
    from connectors.va_graves import results, total
    saved = re.search(r"<!-- saved from (\S+) -->", text[:4000])
    return {"kind": "va_graves", "url": html.unescape(saved.group(1)) if saved else None, "count": total(text), "rows": results(text), "fields": []}
AAD_RECORD = "https://aad.archives.gov/aad/record-detail.jsp?dt=893&cat=WR26&tf=F&bc=,sl,fd&rid="

def aad_name(text):
    """A name as the enlistment file writes it, DAVIDSON#ROBERT#C#######, the right way round: Robert C Davidson."""
    parts = [p for p in (text or "").split("#") if p]
    if not parts: return text or ""
    return " ".join(w.capitalize() for w in (parts[1:] + parts[:1]))

def parse_aad_search(text):
    """A saved AAD partial-records page of the WWII Army enlistment file: {"kind": "aad_search", "query": {name, birth_year} as the
    page says it was searched, "url", "count", "page", "pages", "rows": [{"n", "rid", "url", "name", "serial", "state", "county",
    "enlisted_at", "enlisted_year", "source", "birth_year"}]}: one row per record the page lists, the record's own id from its link."""
    saved = re.search(r"<!-- saved from (\S+) -->", text[:4000])
    q = {}
    for m in re.finditer(r'class="criteria-field">([^<]+)</span>\s*<span class="criteria-op">[^<]*</span>\s*<span class="criteria-value">([^<]*)</span>', text):
        key = {"NAME": "name", "YEAR OF BIRTH": "birth_year", "RESIDENCE: STATE": "state", "RESIDENCE: COUNTY": "county"}.get(m.group(1).strip(), m.group(1).strip().lower())
        q[key] = html.unescape(m.group(2)).strip()
    count = re.search(r"You found\s*(?:<[^>]+>\s*)*([\d,]+)\s*(?:<[^>]+>\s*)*partial records", text); count = int(count.group(1).replace(",", "")) if count else None
    tbl = re.search(r'<table[^>]*\bid="queryResults".*?</table>', text, re.S); rows = []
    heads = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", tbl.group(0) if tbl else "", re.S)]
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl.group(0) if tbl else "", re.S):
        rid = re.search(r"[?&;]rid=(\d+)", tr); cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if not rid or len(cells) != len(heads): continue
        f = dict(zip(heads, cells)); yb = f.get("YEAR OF BIRTH") or ""
        rows.append({"n": len(rows) + 1, "rid": rid.group(1), "url": AAD_RECORD + rid.group(1), "name": aad_name(f.get("NAME")), "serial": f.get("ARMY SERIAL NUMBER"),
                     "state": (f.get("RESIDENCE: STATE") or "").title() or None, "county": (f.get("RESIDENCE: COUNTY") or "").title() or None,
                     "enlisted_at": (f.get("PLACE OF ENLISTMENT") or "").title() or None, "enlisted_year": ("19" + f["DATE OF ENLISTMENT YEAR"]) if re.fullmatch(r"\d\d", f.get("DATE OF ENLISTMENT YEAR") or "") else None,
                     "source": f.get("SOURCE OF ARMY PERSONNEL"), "birth_year": ("19" + yb) if re.fullmatch(r"\d\d", yb) and int(yb) < 40 else ("18" + yb if re.fullmatch(r"\d\d", yb) else None)})
    page = re.search(r"[?&]pg=(\d+)", saved.group(1) if saved else ""); pages = max([1] + [int(x) for x in re.findall(r"[?&;]pg=(\d+)", text)])
    return {"kind": "aad_search", "query": q, "url": html.unescape(saved.group(1)) if saved else None, "count": count, "page": int(page.group(1)) if page else 1, "pages": pages, "rows": rows}

def parse_aad_record(text):
    """A saved AAD full-record page: {"kind": "aad_record", "rid", "url", "fields": [[title, meaning]]}, the Meaning column being
    the value decoded (a state name for its code), the Value column kept where there is no meaning."""
    saved = re.search(r"<!-- saved from (\S+) -->", text[:4000]); rid = re.search(r"[?&;]rid=(\d+)", saved.group(1) if saved else text)
    fields = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) == 3 and cells[0] not in ("Field Title", "") and cells[0].isupper(): fields.append([cells[0], cells[2] if cells[2] and cells[2] != cells[1] or not cells[1] else cells[1]])
    return {"kind": "aad_record", "rid": rid.group(1) if rid else None, "url": AAD_RECORD + rid.group(1) if rid else (saved.group(1) if saved else None), "fields": fields}

def parse_page(text):
    """{"title", "fields": [[label, value]], "household": [{"columns": [...], "rows": [[...]]}], "tables": raw} from the HTML."""
    p = Page(); p.feed(text)
    fields, household, raw = [], [], []
    for t in p.tables:
        rows = t["rows"]; raw.append([[c["text"] for c in r] for r in rows])
        if not rows: continue
        header = [c["text"] for c in rows[0]] if all(c["th"] for c in rows[0]) and len(rows[0]) > 1 else None
        if header and any(re.fullmatch(r"name", h, re.I) for h in header) and len(rows) > 1:
            household.append({"columns": header, "rows": [[c["text"] for c in r] for r in rows[1:] if len(r) == len(header)]}); continue
        for r in rows:
            if len(r) >= 2 and (r[0]["th"] or len(r) == 2) and r[0]["text"] and "\n" not in r[0]["text"]:
                fields.append([r[0]["text"], r[1]["text"]])
    return {"title": clean(p.title), "fields": fields, "household": household, "tables": raw}

def fact_for(label):
    l = label.lower().strip()
    for rx, ftype, part in LABELS:
        if re.search(rx, l): return ftype, part
    return None, None

def sex_of(value):
    v = (value or "").strip().lower()
    return "M" if v in ("m", "male") else ("F" if v in ("f", "female") else None)

def household_kind(word):
    w = (word or "").lower()
    for rx, kind in HOUSEHOLD_KINDS:
        if re.search(rx, w): return kind
    return "other"

class Writer:
    def __init__(self, cx, sha, extraction_id):
        self.cx, self.sha, self.eid, self.n = cx, sha, extraction_id, {"personas": 0, "facts": 0, "relations": 0, "place_strings": 0}
    def place_string(self, raw):
        raw = (raw or "").strip()
        if not raw: return None
        row = self.cx.execute("SELECT id FROM place_string WHERE raw=?", (raw,)).fetchone()
        if row: return row[0]
        pid = ulid(); self.cx.execute("INSERT INTO place_string (id,raw,status) VALUES (?,?,'undecided')", (pid, raw)); self.n["place_strings"] += 1
        return pid
    def persona(self, name, sex, role, seq, region):
        pid = ulid()
        self.cx.execute("INSERT INTO persona (id,extraction_id,artifact_sha256,name_text,sex,role_in_record,sequence,region_json) VALUES (?,?,?,?,?,?,?,?)",
                        (pid, self.eid, self.sha, name, sex, role, seq, dumps(region)))
        self.n["personas"] += 1; return pid
    def fact(self, persona_id, ftype, value=None, date=None, place=None, labels=()):
        d = parse_gedcom_date(date) if date else {"date_start": None, "date_end": None, "date_qualifier": None, "calendar": "gregorian"}
        self.cx.execute("""INSERT INTO persona_fact (id,persona_id,fact_type,value_text,date_text,date_start,date_end,date_qualifier,calendar,place_string_id,region_json)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (ulid(), persona_id, ftype, value, date, d["date_start"], d["date_end"], d["date_qualifier"], d["calendar"],
                                                              self.place_string(place), dumps({"labels": list(labels)})))
        self.n["facts"] += 1
    def relation(self, a, b, kind, as_written, label):
        self.cx.execute("INSERT INTO persona_relation (id,persona_id,related_persona_id,kind,value_text,region_json) VALUES (?,?,?,?,?,?)",
                        (ulid(), a, b, kind, as_written, dumps({"label": label}))); self.n["relations"] += 1

def field_facts(fields, default_etype=None):
    """Group label/value rows into facts: {fact_type: {"date": (value, label), "place": (value, label), "values": [(value, label)]}}, and the
    relatives named in fields as [(label word, name)]. A date and a place of one type are one fact; a second date or place of the same
    type gets its own slot keyed by label. "Event Date" and "Event Place" take the type named by "Event Type" (Census is a Residence)."""
    by_type, named = {}, {}
    etype = next((EVENT_TYPES.get(v.lower().strip()) for l, v in fields if l.lower().strip() == "event type"), None) or default_etype   # a page with no Event Type row takes its collection's kind
    has_place = any(l.lower().strip() == "event place" and (v or "").strip() for l, v in fields)
    has_event = bool(etype) and any(l.lower().strip() in ("event date", "event place", "event place (original)") and (v or "").strip() for l, v in fields)
    for label, value in fields:
        if not value or SKIP.search(label): continue
        key = label.lower().strip()
        if key == "event place (original)" and not has_place: key = "event place"      # the place as written, when the page gives no standardized one
        is_event = etype and key in ("event date", "event place")
        if is_event: label = f"{etype} {key.split()[1].title()}"; key = label.lower()
        rel = re.fullmatch(r"(father|mother|spouse|husband|wife|informant|child)(?:'s)?(?: name)?", key)
        if rel: named[rel.group(1)] = value; continue
        if key == "birth year (estimated)":                              # the index's own estimate from the age: a calculated birth year
            slot = by_type.setdefault("Birth", {"date": None, "place": None, "values": []})
            if slot["date"] is None and re.search(r"\d{4}", value): slot["date"] = (f"CAL {re.search(r'\d{4}', value).group(0)}", label)   # the first year of an estimate; a range is one year in the index's practice
            continue
        ftype, part = fact_for(label)
        if ftype is None: ftype, part = "Unknown", "value"
        m = re.fullmatch(r"(home|residence) in (\d{4})", key)        # "Home in 1900": the label carries the year, and the stay is its own fact beside the record's own residence
        own = has_event and ftype == etype and not is_event and part in ("date", "place")   # a residence the record dates beside its own event (Residence Date 1935 on a 1940 census): its own stay
        slot = by_type.setdefault(ftype + "#" + label if m else ftype + "#own" if own else ftype, {"date": None, "place": None, "values": []})
        if m and slot["date"] is None: slot["date"] = (m.group(2), label)
        if part == "place" and re.fullmatch(r"\s*same (house|place)\s*", value, re.I):   # the census's shorthand: the same dwelling as on the census date, not a place name
            slot["same"] = label; continue
        if part == "value": slot["values"].append((value, label))
        elif slot[part] is None: slot[part] = (value, label)
        else: by_type.setdefault(ftype + "#" + label, {"date": None, "place": None, "values": []})[part] = (value, label)
    return by_type, list(named.items())

def write_facts(w, pid, by_type):
    """One fact per slot; a Residence dated by its label with no place of its own ("Home in 1935: Same House") takes the record's
    own residence place, since that is what the shorthand says."""
    home = next((s["place"] for k, s in by_type.items() if k.split("#")[0] == "Residence" and s["place"] and not s.get("same")), None)
    for ftype, slot in by_type.items():
        base = ftype.split("#")[0]
        if slot.get("same") and home and not slot["place"]: slot["place"] = (home[0], slot["same"])
        if slot["date"] or slot["place"]:
            w.fact(pid, base, None, slot["date"][0] if slot["date"] else None, slot["place"][0] if slot["place"] else None,
                   [x[1] for x in (slot["date"], slot["place"]) if x])
        for value, label in slot["values"]:
            w.fact(pid, base, value if base != "Unknown" else f"{label}: {value}", labels=[label])

def write_personas(w, parsed):
    """The subject from the field table, relatives named in fields, household members; facts and relations for each."""
    fields = parsed["fields"]
    by_type, named = field_facts(fields)
    name = next((v for l, v in fields if fact_for(l)[0] == "Name"), None) or parsed["title"] or "(unnamed)"
    sex = next((sex_of(v) for l, v in fields if fact_for(l)[0] == "Sex"), None)
    rel_word = next((v for l, v in fields if fact_for(l)[0] == "Relationship"), None)
    role = (rel_word or ("deceased" if "Death" in by_type else "subject")).lower()
    subject = w.persona(name, sex, role, 1, {"label": "record"})
    write_facts(w, subject, by_type)
    personas = {name.lower(): subject}
    seq = 2
    for word, value in named:
        role_word, kind = RELATIVE_LABELS[word]
        pid = w.persona(value, None, role_word, seq, {"label": word}); seq += 1
        w.fact(pid, "Name", value, labels=[word]); w.relation(pid, subject, kind, word, word)
        personas.setdefault(value.lower(), pid)
    for table in parsed["household"]:
        cols = [c.lower() for c in table["columns"]]
        col = lambda *names: next((i for i, c in enumerate(cols) if any(re.search(n, c) for n in names)), None)
        i_name, i_age, i_rel, i_sex, i_birth = col(r"^name"), col(r"^age"), col(r"relation"), col(r"gender|sex"), col(r"birth")
        head = None; members = []
        for row in table["rows"]:
            nm = row[i_name] if i_name is not None else None
            if not nm: continue
            rel = row[i_rel] if i_rel is not None else None
            pid = personas.get(nm.lower())
            if pid is None:
                pid = w.persona(nm, sex_of(row[i_sex]) if i_sex is not None else None, (rel or "household member").lower(), seq, {"label": "household"}); seq += 1
                w.fact(pid, "Name", nm, labels=["Name"]); personas[nm.lower()] = pid
                if i_age is not None and row[i_age]: w.fact(pid, "Age", row[i_age], labels=[table["columns"][i_age]])
                if i_birth is not None and row[i_birth]: w.fact(pid, "Birth", None, row[i_birth], labels=[table["columns"][i_birth]])
                if rel: w.fact(pid, "Relationship", rel, labels=[table["columns"][i_rel]])
            if rel and household_kind(rel) == "head": head = pid
            members.append((pid, rel))
        if head is None and members: head = members[0][0]
        for pid, rel in members:
            if pid != head: w.relation(pid, head, household_kind(rel) if rel else "household", rel, "household")

MEMBER_KIND = {"parents": "parent", "spouse": "spouse", "spouses": "spouse", "siblings": "sibling", "half siblings": "sibling", "children": "child"}

def write_memorial(w, parsed):
    """The memorial's subject with its facts, then one persona per family member with a relation to the subject."""
    f = dict(parsed["fields"])
    name = f.get("Name") or parsed["title"] or "(unnamed)"
    subject = w.persona(name, None, "memorial", 1, {"label": "memorial", "memorial_id": parsed.get("memorial_id")})
    w.fact(subject, "Name", name, labels=["Name"])
    if f.get("Birth Date") or f.get("Birth Place"): w.fact(subject, "Birth", None, f.get("Birth Date"), f.get("Birth Place"), [k for k in ("Birth Date", "Birth Place") if f.get(k)])
    if f.get("Death Date") or f.get("Death Place"):
        m = re.fullmatch(r"(.*?)\s*\(aged (.+?)\)", f.get("Death Date") or "")
        w.fact(subject, "Death", None, m.group(1) if m else f.get("Death Date"), f.get("Death Place"), [k for k in ("Death Date", "Death Place") if f.get(k)])
        if m: w.fact(subject, "Age", f"aged {m.group(2)}", labels=["Death Date"])
    if f.get("Burial Place") or f.get("Plot"): w.fact(subject, "Burial", f"Plot: {f['Plot']}" if f.get("Plot") else None, None, f.get("Burial Place"), [k for k in ("Burial Place", "Plot") if f.get(k)])
    if f.get("Inscription"): w.fact(subject, "Inscription", f["Inscription"], labels=["Inscription"])
    if f.get("Biography"): w.fact(subject, "Biography", f["Biography"], labels=["Biography"])
    if parsed.get("memorial_id"): w.fact(subject, "Identification Number", parsed["memorial_id"], labels=["Find a Grave Memorial ID"])
    for seq, m in enumerate(parsed["members"], 2):                # the subject is persona 1
        kind = MEMBER_KIND.get(m["label"].lower(), "other"); role = m["label"].lower().rstrip("s") if kind != "other" else m["label"].lower()
        if kind == "child": role = "child"
        pid = w.persona(m["name"], None, role, seq, {"label": m["label"], "url": m.get("url"), "maiden": m.get("maiden")})
        w.fact(pid, "Name", m["name"], labels=[m["label"]])
        if m.get("birth"): w.fact(pid, "Birth", None, m["birth"], None, ["birthDate"])
        if m.get("death"): w.fact(pid, "Death", None, m["death"], None, ["deathDate"])
        w.relation(pid, subject, kind, m["label"], m["label"])

def write_search(w, parsed):
    """One persona per result row of a memorial search: the name as written, birth and death as the row gives them (a year or a
    date), the cemetery with its place as the Burial place and the plot as its value, the memorial id as the persona's own
    identity (Identification Number, and the memorial URL in region_json)."""
    for r in parsed["rows"]:
        pid = w.persona(r["name"] or "(unnamed)", None, "result", r["n"], {"label": "result", "memorial_id": r["memorial_id"], "url": r["url"], "row": r["n"]})
        w.fact(pid, "Name", r["name"], labels=["name-grave"])
        if r["birth"]: w.fact(pid, "Birth", None, r["birth"], None, ["birthDeathDates"])
        if r["death"]: w.fact(pid, "Death", None, r["death"], None, ["birthDeathDates"])
        if r["cemetery"] or r["place"] or r["plot"]:
            w.fact(pid, "Burial", f"Plot: {r['plot']}" if r["plot"] else None, None, ", ".join(x for x in (r["cemetery"], r["place"]) if x) or None, ["cemetery", "addr-cemet"])
        w.fact(pid, "Identification Number", r["memorial_id"], labels=["Find a Grave Memorial ID"])

def write_fs_search(w, parsed):
    """One persona per result row of a FamilySearch record search: the name as written, the role word and collection, each event
    the row lists (a census as a Residence on its date at its place, birth, death, marriage, burial as they are), the relatives
    named under each relationship label as one fact per label, the record's own ark as the persona's identity (Identification
    Number, and the record URL in region_json)."""
    for r in parsed["rows"]:
        pid = w.persona(r["name"] or "(unnamed)", None, "result", r["n"], {"label": "result", "ark": r["ark"], "url": r["url"], "row": r["n"], "role": r["role"], "collection": r["collection"]})
        w.fact(pid, "Name", r["name"], labels=["name"])
        for e in r["events"]:
            if e["date"] or e["place"]: w.fact(pid, e["type"], None, e["date"], e["place"], [e["label"].lower()])
        for label, names in (r["relations"] or {}).items(): w.fact(pid, "Unknown", f"{label}: {', '.join(names)}", labels=[label.lower()])
        w.fact(pid, "Identification Number", r["ark"], labels=["ark"])

def wt_date(s):
    """A WikiTree date (1810-06-25, 1863-00-00, 0000-00-00) in GEDCOM form, or None."""
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", s or "")
    if not m or m.group(1) == "0000": return None
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    return " ".join(x for x in (str(d) if d else None, MONTHS[mo - 1] if mo else None, y) if x)

def wt_name(p):
    return " ".join(x for x in (p.get("FirstName"), p.get("MiddleName"), p.get("LastNameAtBirth")) if x).strip() or p.get("Name") or "(unnamed)"

def write_wikitree(w, parsed):
    """The profile's subject with its facts (the name at birth, a current surname as a married name, sex, birth and death with
    their places, the biography as written, the profile id as the identity), then one persona per parent, spouse, child and
    sibling the profile links, each with its own dates and places and a relation to the subject."""
    p = parsed["profile"]; name = wt_name(p)
    sex = {"Male": "M", "Female": "F"}.get(p.get("Gender"))
    subject = w.persona(name, sex, "profile", 1, {"label": "profile", "profile": p.get("Name"), "url": f"https://www.wikitree.com/wiki/{p.get('Name')}",
                                                  "maiden": p.get("LastNameAtBirth") if p.get("LastNameCurrent") and p.get("LastNameCurrent") != p.get("LastNameAtBirth") else None})
    w.fact(subject, "Name", name, labels=["FirstName", "MiddleName", "LastNameAtBirth"])
    if p.get("LastNameCurrent") and p.get("LastNameCurrent") != p.get("LastNameAtBirth"): w.fact(subject, "Name", " ".join(x for x in (p.get("FirstName"), p.get("LastNameCurrent")) if x), labels=["LastNameCurrent"])
    if sex: w.fact(subject, "Sex", sex, labels=["Gender"])
    if wt_date(p.get("BirthDate")) or p.get("BirthLocation"): w.fact(subject, "Birth", None, wt_date(p.get("BirthDate")), p.get("BirthLocation") or None, ["BirthDate", "BirthLocation"])
    if wt_date(p.get("DeathDate")) or p.get("DeathLocation"): w.fact(subject, "Death", None, wt_date(p.get("DeathDate")), p.get("DeathLocation") or None, ["DeathDate", "DeathLocation"])
    bio = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|\{\{[^}]*\}\}|\[\[(?:[^\]|]*\|)?([^\]]*)\]\]|'{2,}|==+", r"\1", p.get("bio") or p.get("Bio") or "")).strip()   # wiki markup off, the link text kept
    if bio: w.fact(subject, "Biography", bio, labels=["Bio"])
    w.fact(subject, "Identification Number", p.get("Name"), labels=["WikiTree ID"])
    seq = 2
    for group, kind, role in (("Parents", "parent", "parent"), ("Spouses", "spouse", "spouse"), ("Children", "child", "child"), ("Siblings", "sibling", "sibling")):
        rel = p.get(group); rel = list(rel.values()) if isinstance(rel, dict) else (rel if isinstance(rel, list) else [])
        for r in rel:
            if not isinstance(r, dict) or not r.get("Name"): continue
            rs = {"Male": "M", "Female": "F"}.get(r.get("Gender")); rn = wt_name(r)
            pid = w.persona(rn, rs, role, seq, {"label": group, "profile": r.get("Name"), "url": f"https://www.wikitree.com/wiki/{r.get('Name')}"}); seq += 1
            w.fact(pid, "Name", rn, labels=[group])
            if wt_date(r.get("BirthDate")) or r.get("BirthLocation"): w.fact(pid, "Birth", None, wt_date(r.get("BirthDate")), r.get("BirthLocation") or None, ["BirthDate"])
            if wt_date(r.get("DeathDate")) or r.get("DeathLocation"): w.fact(pid, "Death", None, wt_date(r.get("DeathDate")), r.get("DeathLocation") or None, ["DeathDate"])
            w.fact(pid, "Identification Number", r.get("Name"), labels=["WikiTree ID"])
            w.relation(pid, subject, kind, group[:-1] if group.endswith("s") else group, group)

def write_aad_search(w, parsed):
    """One persona per row of an enlistment search: the name the right way round, the birth year, a Residence in the county and
    state in the enlistment year, the serial number as its identity, the record's own page in region_json."""
    for r in parsed["rows"]:
        pid = w.persona(r["name"] or "(unnamed)", "M", "result", r["n"], {"label": "result", "rid": r["rid"], "url": r["url"], "row": r["n"],
                                                                        "where": ", ".join(x for x in (r["county"], r["state"]) if x) + (f" ({r['enlisted_year']})" if r["enlisted_year"] else "")})
        w.fact(pid, "Name", r["name"], labels=["NAME"])
        if r["birth_year"]: w.fact(pid, "Birth", None, r["birth_year"], None, ["YEAR OF BIRTH"])
        if r["county"] or r["state"]: w.fact(pid, "Residence", None, r["enlisted_year"], ", ".join(x for x in (r["county"], r["state"], "United States") if x), ["RESIDENCE: COUNTY", "RESIDENCE: STATE"])
        if r["serial"]: w.fact(pid, "Identification Number", r["serial"], labels=["ARMY SERIAL NUMBER"])

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

def write_va(w, parsed):
    """One persona per decedent the gravesite locator lists: the name the right way round, the dates of birth and death as
    written (month first), the burial in the cemetery at its town and state with the section and site as the plot, rank and
    branch and the war period as one Military Service attribute, the row and the page in the region. A row is a result: one
    that fits nobody stays on the page as a hint."""
    from connectors.nara_1950 import ABBR
    states = {v: k.title() for k, v in ABBR.items()}
    for r in parsed["rows"]:
        name = va_name(r.get("name")) or "(unnamed)"
        pid = w.persona(name, None, "result", r["n"], {"label": "result", "row": r["n"], "name_as_written": r.get("name"), "url": parsed.get("url")})
        w.fact(pid, "Name", name, labels=["Name"])
        if r.get("birth"): w.fact(pid, "Birth", None, r["birth"], None, ["Date of Birth"])
        if r.get("death"): w.fact(pid, "Death", None, r["death"], None, ["Date of Death"])
        place = ", ".join(x for x in (r.get("cemetery"), (r.get("city") or "").title() or None, states.get(r.get("state")) or r.get("state")) if x) or None
        if place or r.get("buried_at"): w.fact(pid, "Burial", f"Plot: {r['buried_at']}" if r.get("buried_at") else None, None, place, ["Cemetery", "Buried At", "Cemetery Address"])
        service = ", ".join(x for x in (r.get("rank_branch"), r.get("war")) if x)
        if service: w.fact(pid, "Military Service", service, labels=["Rank & Branch", "War Period"])

def write_aad_record(w, parsed):
    """The enlistee: the name the right way round; the birth year; the nativity as the birth place; a Residence in the county and
    state on the enlistment date; the enlistment itself as Military Service at the place of enlistment; marital status, education
    and civilian occupation as attributes as written; the serial number as the identity."""
    f = dict(parsed["fields"]); name = aad_name(f.get("NAME")) or "(unnamed)"
    pid = w.persona(name, "M", "enlistee", 1, {"label": "enlistee", "rid": parsed.get("rid"), "url": parsed.get("url")})
    w.fact(pid, "Name", name, labels=["NAME"])
    yb = f.get("YEAR OF BIRTH") or ""
    if re.fullmatch(r"\d\d", yb): w.fact(pid, "Birth", None, ("19" if int(yb) < 40 else "18") + yb, (f.get("NATIVITY") or "").title() or None, ["YEAR OF BIRTH", "NATIVITY"])
    d, m, y = f.get("DATE OF ENLISTMENT DAY"), f.get("DATE OF ENLISTMENT MONTH"), f.get("DATE OF ENLISTMENT YEAR")
    when = " ".join(x for x in (d.lstrip("0") if d and d.isdigit() else None, MONTHS[int(m) - 1] if m and m.isdigit() and 1 <= int(m) <= 12 else None, "19" + y if y and re.fullmatch(r"\d\d", y) else None) if x) or None
    place = ", ".join(x for x in ((f.get("RESIDENCE: COUNTY") or "").title() or None, (f.get("RESIDENCE: STATE") or "").title() or None, "United States") if x)
    if f.get("RESIDENCE: STATE"): w.fact(pid, "Residence", None, when, place, ["RESIDENCE: COUNTY", "RESIDENCE: STATE", "DATE OF ENLISTMENT"])
    if f.get("PLACE OF ENLISTMENT"): w.fact(pid, "Military Service", "enlisted, " + (f.get("SOURCE OF ARMY PERSONNEL") or "").strip(), when, (f["PLACE OF ENLISTMENT"] or "").title(), ["PLACE OF ENLISTMENT", "DATE OF ENLISTMENT"])
    for title, ftype in (("MARITAL STATUS", "Marital Status"), ("EDUCATION", "Education"), ("CIVILIAN OCCUPATION", "Occupation"), ("RACE AND CITIZENSHIP", "Race")):
        v = f.get(title)
        if v and not re.search(r"undefined code|^#+$", v, re.I): w.fact(pid, ftype, v, labels=[title])
    if f.get("ARMY SERIAL NUMBER"): w.fact(pid, "Identification Number", f["ARMY SERIAL NUMBER"], labels=["ARMY SERIAL NUMBER"])

def write_record(w, parsed):
    """The FamilySearch record's subject with its facts, then one persona per household member with its own facts and a relation to the subject."""
    fields = parsed["fields"]; f = dict(fields)
    kind_word = (parsed.get("collection") or "").split("•")[0].strip().lower()                     # "Census • United States, Census, 1950"
    by_type, named = field_facts(fields, EVENT_TYPES.get(kind_word))
    name = f.get("Name") or parsed.get("name") or parsed["title"] or "(unnamed)"
    role = (f.get("Relationship to Head of Household") or "subject").lower()
    subject = w.persona(name, sex_of(f.get("Sex")), role, 1, {"label": "record", "ark": parsed.get("ark")})
    year = re.search(r"\b(1[789]\d\d)\b", f.get("Event Date") or "") or re.fullmatch(r".*\b(1[789]\d\d)\b.*", re.sub(r"\b1[789]\d\d-1[789]\d\d\b", "", parsed.get("collection") or ""))   # the record's own date, else the collection's single year; a range is not a year
    age = re.match(r"\s*(\d{1,3})", f.get("Age") or "")
    if year and age and not (by_type.get("Birth") or {}).get("date"):     # the principal's birth year, calculated from the age on the record's date, as for a household member
        by_type.setdefault("Birth", {"date": None, "place": None, "values": []})["date"] = (f"CAL {int(year.group(1)) - int(age.group(1))}", "Age")
    write_facts(w, subject, by_type)
    seq0 = 2
    for label, who in named:                                         # a relative the record names in a field: Father's Name, Mother's Name, Spouse
        if len(who.split()) < 2: continue                            # a surname alone (a death index's "Father's Name: Davidson") names nobody
        pid = w.persona(who, None, label, seq0, {"label": label}); seq0 += 1
        w.fact(pid, "Name", who, labels=[label])
        w.relation(pid, subject, {"father": "parent", "mother": "parent", "spouse": "spouse", "husband": "spouse", "wife": "spouse", "child": "child"}.get(label, "other"), label.title(), label)
    members_written = []
    for seq, m in enumerate([x for x in parsed["members"] if len((x["name"] or "").split()) >= 2 and (x["name"] or "").strip().upper() != "UNKNOWN"], seq0):   # a surname alone or UNKNOWN names nobody
        mf = m["fields"] or [["Name", m["name"]], ["Sex", m["sex"]], ["Age", m["age"]], ["Birthplace", m["birthplace"]]]
        mb, _ = field_facts(mf)
        age = re.match(r"\s*(\d{1,3})", m.get("age") or "")
        if year and age and not (mb.get("Birth") or {}).get("date"):     # a household member's birth year, calculated from the age on the census date
            mb.setdefault("Birth", {"date": None, "place": None, "values": []})["date"] = (f"CAL {int(year.group(1)) - int(age.group(1))}", "Age")
        pid = w.persona(m["name"], sex_of(m["sex"]) or sex_of(dict(mf).get("Sex")), m["role"].lower(), seq, {"label": m["section"], "url": m.get("url")})
        write_facts(w, pid, mb)
        w.relation(pid, subject, household_kind(m["role"]), m["role"], m["section"])
        members_written.append((pid, m["role"].lower(), m["section"]))
    parents = [(pid, role, sec) for pid, role, sec in members_written if role in ("father", "mother")]
    if len(parents) == 2 and parents[0][1] != parents[1][1]:      # a census household lists the subject's father and mother together: the household's couple
        w.relation(parents[0][0], parents[1][0], "spouse", "Parents", parents[0][2])

def context_for(cx, sha):
    """What the runner recorded about a connector response: the manifest notes (the hit as the source described it) and the step
    type and query of the run that archived it."""
    man = cx.execute("SELECT manifest_json FROM artifact WHERE sha256=?", (sha,)).fetchone()
    notes = (json.loads(man[0]) if man and man[0] else {}).get("notes") or ""
    ctx = {"notes": json.loads(notes) if notes.startswith("{") else {}, "step_type": None, "query": {}}
    row = cx.execute("SELECT sp.query_type, l.query_json FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE l.artifacts_json LIKE ? ORDER BY l.executed_at DESC LIMIT 1", (f'%"{sha}"%',)).fetchone()
    if row: ctx["step_type"], ctx["query"] = row[0], {k: (v.get("value") if isinstance(v, dict) else v) for k, v in json.loads(row[1] or "{}").items()}
    else: ctx["step_type"] = ctx["notes"].get("step_type")          # a response read on its own: the runner noted the step's kind on it
    return ctx

def _asked(notes):
    """What a response was searched for, from the runner's notes on the artifact, when no log row carries the query (the
    response read on its own, as the harness reads a fixture): surname and given as the Archive connector notes them, or the
    one query string the loc.gov connector notes, surname first."""
    q = {k: notes[k] for k in ("surname", "given") if notes.get(k)}
    if not q and isinstance(notes.get("query"), str) and notes["query"].split():
        words = notes["query"].split(); q = {"surname": words[0], **({"given": " ".join(words[1:])} if len(words) > 1 else {})}
    return q

def _searched(ctx):
    """The surname and given name a text was searched for: the run's query when it carries a surname (a search step), else
    what the connector noted on the response (a fetch step's fields are the citation's, a name and a book; the connector
    split the name)."""
    q = ctx["query"] or {}
    return q if q.get("surname") else {**q, **_asked(ctx["notes"])}

def parse_json(data, ctx):
    """A connector response's kind and parsed form: a 1950 census schedule from the National Archives site (results with
    scheduleId and names), the OCR text of a Chronicling America page from loc.gov's text service (segments with full_text),
    else (None, reason)."""
    try: d = json.loads(data)
    except ValueError as e: return None, {"reason": f"not JSON: {e}"}
    res = d.get("results") if isinstance(d, dict) else None
    if res and len(res) == 1 and isinstance(res[0], dict) and "scheduleId" in res[0] and "names" in res[0] and not res[0].get("highlight"):
        return "nara1950", {"kind": "nara1950", "schedule": res[0], "matched": ctx["notes"].get("matched") or [], "fields": []}
    if isinstance(d, dict) and d and all(isinstance(v, dict) and "full_text" in v for v in d.values()):
        seg, body = next(iter(d.items()))
        return "locgov", {"kind": "locgov", "segment": seg, "full_text": body["full_text"] or "", "page": ctx["notes"], "step_type": ctx["step_type"], "query": _searched(ctx), "fields": []}
    if isinstance(d, list) and d and isinstance(d[0], dict) and isinstance(d[0].get("profile"), dict) and d[0]["profile"].get("Name"):   # a WikiTree profile with its relatives
        return "wikitree", {"kind": "wikitree", "profile": d[0]["profile"], "fields": []}
    if isinstance(d, dict) and "ia" in d and "matches" in d and "q" in d:      # the Archive's search inside one item: matches with their text and page
        n = ctx["notes"]; pages = n.get("pages") or []           # the pages the runner chose and fetched images of (connectors/ia.py)
        text = "\n".join(re.sub(r"</?IA_FTS_MATCH>", "", m.get("text") or "") for m in d["matches"] or [] if any(p.get("page") in pages for p in m.get("par") or []))
        page = {"date": n.get("date") or (str(n["year"]) if n.get("year") else None), "title": n.get("title"), "item": n.get("item"), "pages": pages, "variants": n.get("variants") or []}
        return "ia_inside", {"kind": "ia_inside", "segment": d["ia"], "full_text": text, "page": page, "step_type": ctx["step_type"], "query": _searched(ctx), "fields": []}
    return None, {"reason": "no extractor claims this response: not a 1950 census schedule, not a loc.gov page text, not the Archive's search inside an item"}

def write_schedule(w, parsed):
    """One persona per transcribed row the search matched (every row when nothing was matched): the name as transcribed, a
    Residence in the schedule's county and state in 1950, the enumeration district and row under their own labels."""
    sc = parsed["schedule"]; place = ", ".join(x for x in (sc.get("county"), sc.get("state"), "United States") if x)
    keys = {key_of(m) for m in parsed["matched"]}
    rows = [r for r in sc.get("names") or [] if r.get("name") and (not keys or key_of(r["name"]) in keys)]
    for seq, r in enumerate(rows, 1):
        pid = w.persona(r["name"], None, "listed", seq, {"label": "schedule", "row": r.get("row"), "scheduleId": sc.get("scheduleId"), "ed": sc.get("ed")})
        w.fact(pid, "Name", r["name"], labels=["name"]); w.fact(pid, "Residence", None, "1950", place, ["county", "state"])
        w.fact(pid, "Unknown", f"Enumeration District: {sc.get('ed')}", labels=["ed"])
        if r.get("row") is not None: w.fact(pid, "Unknown", f"Row: {r['row']}", labels=["row"])

def key_of(s): return re.sub(r"[^a-z]", "", (s or "").lower())

STOP = {"and", "or", "of", "the", "by", "to", "in", "at", "for", "with", "from", "mr", "mrs", "miss", "see", "also", "v", "vs"}

def write_ocr(w, parsed):
    """One persona per place the searched surname stands in the page's OCR text, named by the words around it, with the
    snippet, its offset and the page (its date, title and place) in the region. A page of running text states no date of the
    person's life, so the persona carries its name and nothing else; a directory entry (the Archive's directory connector)
    does state a residence, so it carries a Residence on the directory's date at its place. Nothing when the surname is not
    in the text."""
    text, q, page = parsed["full_text"], parsed["query"], parsed["page"] or {}
    surname = (q.get("surname") or "").strip()
    if not surname: return
    spellings = [surname] + [v for v in (page.get("variants") or []) if v and v.lower() != surname.lower()]   # the surname as the step gives it and the spellings the search inside was asked
    seq, seen = 1, set()
    for m in re.finditer(r"(?:\b[A-Z][A-Za-z.'-]*\s+){0,2}\b(?i:" + "|".join(re.escape(s) for s in spellings) + r")\b(?:\s+[A-Z][A-Za-z.]*)?", text):   # capitalized words around the surname, any spelling, in any case
        words = re.sub(r"\s+", " ", m.group(0)).strip().split()
        cut = [i for i, w_ in enumerate(words[:-1]) if w_.strip(".").lower() in STOP]     # "RECTOR AND Davidson": what stands before a stop word is not the name
        if cut: words = words[cut[-1] + 1:]
        name = " ".join(words)
        if key_of(name) in seen: continue
        seen.add(key_of(name)); start, end = max(0, m.start() - 160), min(len(text), m.end() + 160)
        place = ", ".join(x for x in (page.get("city"), page.get("state")) if x) or None
        region = {"label": "ocr", "offset": m.start(), "snippet": text[start:end], "segment": parsed["segment"],
                  "page": {k: v for k, v in (("date", page.get("date")), ("title", page.get("title")), ("place", place)) if v}}
        pid = w.persona(name, None, "named in the text", seq, region); seq += 1
        w.fact(pid, "Name", name, labels=["text"])
        if page.get("connector") == "ia_directories" and (page.get("date") or place): w.fact(pid, "Residence", None, page.get("date"), place, ["directory date", "directory place"])

def extract(cx, sha, by):
    art = cx.execute("SELECT sha256, mime FROM artifact WHERE sha256=?", (sha,)).fetchone()
    if not art: raise SystemExit(f"not in the archive: {sha[:12]}")
    mime = art[1] or ""
    with open(object_path(sha), "rb") as fh: data = fh.read()
    if mime.startswith("text/html"): kind, parsed = parse(data.decode("utf-8", errors="replace"))
    elif mime.startswith("application/json") or data[:1] in (b"{", b"["): kind, parsed = parse_json(data, context_for(cx, sha))
    else: kind, parsed = None, {"reason": f"not a record page or a connector response: {mime}"}
    extractor = EXTRACTORS[kind]; ts = now()
    row = cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", extractor).fetchone()
    ext_id = row[0] if row else ulid()
    if not row: cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)", (ext_id, *extractor, ts))
    eid = ulid()
    if kind is None:
        cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status,structured_json) VALUES (?,?,?,?,'failed',?)", (eid, sha, ext_id, ts, dumps(parsed)))
        cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
                   (ulid(), ts, by, "insert", "extraction", eid, dumps({"extractor": "rule:extract@0.1.0", "status": "failed", **parsed})))
        return eid, {"failed": parsed["reason"]}
    full_text = "\n".join(f"{l}: {v}" for l, v in parsed.get("fields") or [])
    if kind == "ancestry": full_text += "".join("\n" + " | ".join(r) for t in parsed["household"] for r in t["rows"])
    elif kind == "familysearch": full_text += "".join(f"\n{m['role']}: {m['name']} {m['sex']} {m['age']} {m['birthplace']}" for m in parsed["members"])
    elif kind == "findagrave": full_text += "".join(f"\n{m['label']}: {m['name']} {m.get('birth') or ''}-{m.get('death') or ''}" for m in parsed["members"])
    elif kind == "aad_record": full_text = "\n".join(f"{l}: {v}" for l, v in parsed["fields"])
    elif kind == "wikitree": full_text = "\n".join(f"{k}: {v}" for k, v in parsed["profile"].items() if isinstance(v, (str, int)) and v not in ("", None))
    elif kind == "aad_search": full_text = "\n".join(f"{r['n']}: {r['name']} b. {r['birth_year'] or '?'} {r['county'] or ''} {r['state'] or ''} enlisted {r['enlisted_year'] or '?'}" for r in parsed["rows"])
    elif kind == "findagrave_search": full_text = "\n".join(f"{r['n']}: {r['name']} {r['birth'] or ''}-{r['death'] or ''} {r['cemetery'] or ''} {r['place'] or ''} memorial {r['memorial_id']}" for r in parsed["rows"])
    elif kind == "va_graves": full_text = "\n".join(f"{r['n']}: {r.get('name')} {r.get('birth') or ''}-{r.get('death') or ''} {r.get('rank_branch') or ''} {r.get('war') or ''} {r.get('cemetery') or ''} {r.get('buried_at') or ''}" for r in parsed["rows"])
    elif kind == "familysearch_search": full_text = "\n".join(f"{r['n']}: {r['name']} " + "; ".join(f"{e['label']} {e['date'] or ''} {e['place'] or ''}".strip() for e in r["events"]) + " " + "; ".join(f"{k} {', '.join(v)}" for k, v in (r["relations"] or {}).items()) + f" {r['ark']}" for r in parsed["rows"])
    elif kind == "nara1950": full_text += "".join(f"\n{r.get('row')}: {r.get('name')}" for r in parsed["schedule"].get("names") or [])
    else: full_text = parsed["full_text"]
    cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status,full_text,structured_json) VALUES (?,?,?,?,'complete',?,?)",
               (eid, sha, ext_id, ts, full_text, dumps(parsed)))
    same = "extractor_id IN (SELECT id FROM extractor WHERE kind=? AND name=?)"      # every version of this parser
    old = [r[0] for r in cx.execute(f"SELECT id FROM extraction WHERE artifact_sha256=? AND {same} AND id<>? AND superseded_by IS NULL", (sha, *extractor[:2], eid))]
    cx.execute(f"UPDATE extraction SET superseded_by=? WHERE artifact_sha256=? AND {same} AND id<>? AND superseded_by IS NULL", (eid, sha, *extractor[:2], eid))
    for o in old:                                                # a superseded extraction's undecided proposals rest on personas no longer current
        cx.execute("""UPDATE proposal SET status='rejected', decided_by=?, decided_at=?, decision_note='superseded'
                      WHERE status='undecided' AND json_extract(payload_json,'$.extraction_id')=?""", (by, ts, o))
    if kind == "familysearch" and parsed.get("ark"):
        cx.execute("INSERT OR IGNORE INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (sha, "ark", parsed["ark"]))
    w = Writer(cx, sha, eid)
    {"findagrave": write_memorial, "findagrave_search": write_search, "familysearch": write_record, "familysearch_search": write_fs_search, "nara1950": write_schedule, "locgov": write_ocr, "ia_inside": write_ocr,
     "aad_search": write_aad_search, "aad_record": write_aad_record, "wikitree": write_wikitree, "va_graves": write_va}.get(kind, write_personas)(w, parsed)
    w.n["links_carried"] = carry_links(cx, old, eid, sha, by, ts)
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, by, "insert", "extraction", eid, dumps({"extractor": ":".join(extractor[:2]) + "@" + extractor[2], **w.n})))
    return eid, w.n

def carry_links(cx, old, eid, sha, by, ts):
    """A decided person-persona link on a superseded extraction moves to the new persona of the same name and role; an accepted
    one asserts the new facts and links onto the person as the decision did. Returns how many links were carried."""
    n = 0
    for o in old:
        for pp in cx.execute("""SELECT pp.person_id, pp.status, pp.proposal_id, pp.decided_by, pp.decided_at, pe.name_text, pe.role_in_record, p.tree_id
                                FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id JOIN person p ON p.id=pp.person_id WHERE pe.extraction_id=?""", (o,)).fetchall():
            new = cx.execute("SELECT id FROM persona WHERE extraction_id=? AND name_text=? AND role_in_record=?", (eid, pp[5], pp[6])).fetchone()
            if not new: continue
            cx.execute("INSERT OR IGNORE INTO person_persona (person_id,persona_id,status,proposal_id,decided_by,decided_at) VALUES (?,?,?,?,?,?)", (pp[0], new[0], pp[1], pp[2], pp[3], pp[4])); n += 1
    for o in old:                                                # links first, so the family relations see every accepted persona
        for pp in cx.execute("""SELECT pp.person_id, pp.proposal_id, pe.name_text, pe.role_in_record, p.tree_id FROM person_persona pp JOIN persona pe ON pe.id=pp.persona_id
                                JOIN person p ON p.id=pp.person_id WHERE pe.extraction_id=? AND pp.status='accepted'""", (o,)).fetchall():
            new = cx.execute("SELECT id FROM persona WHERE extraction_id=? AND name_text=? AND role_in_record=?", (eid, pp[2], pp[3])).fetchone()
            if not new: continue
            assert_facts(cx, pp[4], pp[0], new[0], pp[1], by, ts); link_family(cx, pp[4], pp[0], new[0], sha, pp[1], by, ts)
    return n

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("what", help="artifact sha256, or a path whose bytes are archived")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument("--about", help="the person the record is about when no step or link names them, on the owner's word")
    a = ap.parse_args()
    sha = a.what if re.fullmatch(r"[0-9a-f]{64}", a.what) else sha256_file(a.what)
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
    cx.execute("BEGIN"); eid, n = extract(cx, sha, a.by); cx.commit()
    print("extraction", eid, dumps(n))
    if "failed" in n: return
    from conclude import match_record
    about = None
    if a.about:
        from catalog import Catalog
        cx.row_factory = None; tid = cx.execute("SELECT tree_id FROM person WHERE id=? OR display_name=? LIMIT 1", (a.about, a.about)).fetchone()
        about = [Catalog(cx, tid[0]).find_person(a.about)] if tid else None
    cx.execute("BEGIN"); written, taken = match_record(cx, eid, a.by, about=about); cx.commit()          # the matcher runs on every extraction as it is written, then the rule
    print("proposals", len(written), "accepted by rule", len(taken))
    for pid, name, sex, role in cx.execute("SELECT id, name_text, sex, role_in_record FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,)):
        print(f"  {name} [{role}{', ' + sex if sex else ''}]")
        for ft, v, d, ps, rg in cx.execute("""SELECT pf.fact_type, pf.value_text, pf.date_text, ps.raw, pf.region_json FROM persona_fact pf
                                              LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pf.persona_id=?""", (pid,)):
            print(f"      {ft:14} {' '.join(x for x in (v, d, ps) if x)}")
        for kind, vt, other in cx.execute("SELECT r.kind, r.value_text, p.name_text FROM persona_relation r JOIN persona p ON p.id=r.related_persona_id WHERE r.persona_id=?", (pid,)):
            print(f"      {kind} of {other} ({vt})")

if __name__ == "__main__": main()
