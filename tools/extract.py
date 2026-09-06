#!/usr/bin/env python3
"""Extract personas and facts from an archived record page (HTML) or a connector response (JSON).

usage: tools/extract.py <sha256 | path> [--db catalog/tree.db] [--by user:<you>]

A parser claims the page by its own marker, or the extraction fails. A Find a
Grave memorial (body id memorial-summary) goes to rule:findagrave-memorial@0.1.0;
a FamilySearch record page (its "Cite This Record" block, data-testid
documentInformationCitation, naming an ark under familysearch.org/ark:/61903/1:1:)
goes to rule:familysearch-record@0.1.0; an
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
superseded: they rested on personas that are no longer current.

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
inscription (inscriptionValue) as an Unknown fact, both absent on the verified
page; the memorial id as an Identification Number fact. Family members are the
member-family lists, each labelled Parents, Spouse, Siblings or Children: one
persona per member in the label's role word, with the name as written (a
maiden name is italic on the page and kept inside the name), the birth and
death years, and one relation from the member to the subject (parent, spouse,
sibling, child) with the label as written. The member's own memorial URL is in
its region_json. structured_json holds the fields, the members, the source
block (created by, added, citation) and the photo captions.

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
  rule:loc-gov-ocr@0.1.0         a page's OCR text from loc.gov's text service (segments with full_text): one persona per place
                                 the searched surname stands in the text, named by the words around it, with the text region;
                                 a Death before the page's date for an obituary step, else a Residence on the page's date at
                                 the paper's place. The search that archived the response supplies the surname and step type.
"""
import argparse, html, json, os, re, sqlite3, sys
from html.parser import HTMLParser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import ROOT, dumps, now, object_path, parse_gedcom_date, sha256_file, ulid

EXTRACTORS = {"ancestry": ("rule", "ancestry-index", "0.1.0"), "findagrave": ("rule", "findagrave-memorial", "0.1.0"),
              "familysearch": ("rule", "familysearch-record", "0.1.0"), "nara1950": ("rule", "nara-1950-schedule", "0.1.0"),
              "locgov": ("rule", "loc-gov-ocr", "0.1.0"), None: ("rule", "extract", "0.1.0")}
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
    """A Find a Grave memorial page: {"kind": "findagrave", "title", "fields": [[label, value]], "memorial_id", "members": [...], "source": {...}, "photo_captions": [...]}."""
    t = Tree(); t.feed(text); root = t.root
    get = lambda i: (text_of(by_id(root, i)) or None) if by_id(root, i) else None
    fields = []
    add = lambda label, value: fields.append([label, value]) if value else None
    add("Name", get("bio-name")); add("Birth Date", get("birthDateLabel")); add("Birth Place", get("birthLocationLabel"))
    add("Death Date", get("deathDateLabel")); add("Death Place", get("deathLocationLabel"))
    cemetery = [get(i) for i in ("cemeteryNameLabel", "cemeteryCityName", "cemeteryCountyName", "cemeteryStateName", "cemeteryCountryName")]
    add("Burial Place", ", ".join(x for x in cemetery if x)); add("Plot", get("plotValueLabel")); add("Inscription", get("inscriptionValue"))
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
    captions = [text_of(n).replace("\n", " ") for n in walk(root) if "photo-text" in (n["attrs"].get("class") or "") and text_of(n)]
    title = next((text_of(n) for n in walk(root) if n["tag"] == "title"), "")
    return {"kind": "findagrave", "title": title, "fields": fields, "memorial_id": memorial_id, "members": members, "source": source, "photo_captions": captions}

FS_MARK = re.compile(r'data-testid="documentInformationCitation"[^\x00]{0,400}?https://www\.familysearch\.org/ark:/61903/1:1:')

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
        elif section.startswith("Cite This Record") and not out["fields"]: out["fields"] = label_rows(n)
        elif rows and any(len(r) == 5 for r in rows):                       # household: a member row, then a row holding its details table
            member = None
            for r in rows:
                if len(r) == 5 and r[0]["tag"] == "th":
                    a = next((x for x in walk(r[0]) if x["tag"] == "a"), None)
                    name = text_of(a) if a else text_of(r[0]).split("\n")[0]
                    role = text_of(r[0]).replace("\n", " ").replace(name, "", 1).strip()
                    member = {"section": section, "name": name, "role": role, "sex": text_of(r[1]), "age": text_of(r[2]), "birthplace": text_of(r[3]),
                              "url": a["attrs"].get("href") if a else None, "fields": []}
                    out["members"].append(member)
                elif len(r) == 1 and member is not None:
                    for tbl in (x for x in walk(r[0]) if x["tag"] == "table"):
                        seen.add(id(tbl)); member["fields"] += label_rows(tbl)
    return out

def parse(text):
    """The page's kind and its parsed form, or (None, reason) when no parser claims the page."""
    if re.search(r'<body[^>]*\bid="memorial-summary"', text): return "findagrave", parse_memorial(text)
    if FS_MARK.search(text): return "familysearch", parse_record(text)
    page = parse_page(text)
    if page["fields"] or page["household"]: return "ancestry", page
    return None, {"reason": "no parser claims this page: not a Find a Grave memorial, not a FamilySearch record page, and no table pairs a label cell with a value cell"}

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

def field_facts(fields):
    """Group label/value rows into facts: {fact_type: {"date": (value, label), "place": (value, label), "values": [(value, label)]}}, and the
    relatives named in fields as [(label word, name)]. A date and a place of one type are one fact; a second date or place of the same
    type gets its own slot keyed by label. "Event Date" and "Event Place" take the type named by "Event Type" (Census is a Residence)."""
    by_type, named = {}, {}
    etype = next((EVENT_TYPES.get(v.lower().strip()) for l, v in fields if l.lower().strip() == "event type"), None)
    for label, value in fields:
        if not value or SKIP.search(label): continue
        key = label.lower().strip()
        if etype and key in ("event date", "event place"): label = f"{etype} {key.split()[1].title()}"; key = label.lower()
        rel = re.fullmatch(r"(father|mother|spouse|husband|wife|informant|child)(?:'s)?(?: name)?", key)
        if rel: named[rel.group(1)] = value; continue
        ftype, part = fact_for(label)
        if ftype is None: ftype, part = "Unknown", "value"
        slot = by_type.setdefault(ftype, {"date": None, "place": None, "values": []})
        m = re.fullmatch(r"(home|residence) in (\d{4})", key)        # "Home in 1900": the label carries the year
        if m and slot["date"] is None: slot["date"] = (m.group(2), label)
        if part == "value": slot["values"].append((value, label))
        elif slot[part] is None: slot[part] = (value, label)
        else: by_type.setdefault(ftype + "#" + label, {"date": None, "place": None, "values": []})[part] = (value, label)
    return by_type, list(named.items())

def write_facts(w, pid, by_type):
    for ftype, slot in by_type.items():
        base = ftype.split("#")[0]
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
    if f.get("Inscription"): w.fact(subject, "Unknown", f"Inscription: {f['Inscription']}", labels=["Inscription"])
    if parsed.get("memorial_id"): w.fact(subject, "Identification Number", parsed["memorial_id"], labels=["Find a Grave Memorial ID"])
    for seq, m in enumerate(parsed["members"], 2):
        kind = MEMBER_KIND.get(m["label"].lower(), "other"); role = m["label"].lower().rstrip("s") if kind != "other" else m["label"].lower()
        if kind == "child": role = "child"
        pid = w.persona(m["name"], None, role, seq, {"label": m["label"], "url": m.get("url"), "maiden": m.get("maiden")})
        w.fact(pid, "Name", m["name"], labels=[m["label"]])
        if m.get("birth"): w.fact(pid, "Birth", None, m["birth"], None, ["birthDate"])
        if m.get("death"): w.fact(pid, "Death", None, m["death"], None, ["deathDate"])
        w.relation(pid, subject, kind, m["label"], m["label"])

def write_record(w, parsed):
    """The FamilySearch record's subject with its facts, then one persona per household member with its own facts and a relation to the subject."""
    fields = parsed["fields"]; f = dict(fields)
    by_type, _ = field_facts(fields)
    name = f.get("Name") or parsed.get("name") or parsed["title"] or "(unnamed)"
    role = (f.get("Relationship to Head of Household") or "subject").lower()
    subject = w.persona(name, sex_of(f.get("Sex")), role, 1, {"label": "record", "ark": parsed.get("ark")})
    write_facts(w, subject, by_type)
    for seq, m in enumerate(parsed["members"], 2):
        mf = m["fields"] or [["Name", m["name"]], ["Sex", m["sex"]], ["Age", m["age"]], ["Birthplace", m["birthplace"]]]
        mb, _ = field_facts(mf)
        pid = w.persona(m["name"], sex_of(m["sex"]) or sex_of(dict(mf).get("Sex")), m["role"].lower(), seq, {"label": m["section"], "url": m.get("url")})
        write_facts(w, pid, mb)
        w.relation(pid, subject, household_kind(m["role"]), m["role"], m["section"])

def context_for(cx, sha):
    """What the runner recorded about a connector response: the manifest notes (the hit as the source described it) and the step
    type and query of the run that archived it."""
    man = cx.execute("SELECT manifest_json FROM artifact WHERE sha256=?", (sha,)).fetchone()
    notes = (json.loads(man[0]) if man and man[0] else {}).get("notes") or ""
    ctx = {"notes": json.loads(notes) if notes.startswith("{") else {}, "step_type": None, "query": {}}
    row = cx.execute("SELECT sp.query_type, l.query_json FROM search_log l JOIN search_plan sp ON sp.id=l.plan_step_id WHERE l.artifacts_json LIKE ? ORDER BY l.executed_at DESC LIMIT 1", (f'%"{sha}"%',)).fetchone()
    if row: ctx["step_type"], ctx["query"] = row[0], {k: (v.get("value") if isinstance(v, dict) else v) for k, v in json.loads(row[1] or "{}").items()}
    return ctx

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
        return "locgov", {"kind": "locgov", "segment": seg, "full_text": body["full_text"] or "", "page": ctx["notes"], "step_type": ctx["step_type"], "query": ctx["query"], "fields": []}
    return None, {"reason": "no extractor claims this response: not a 1950 census schedule, not a loc.gov page text"}

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

def write_ocr(w, parsed):
    """One persona per place the searched surname stands in the page's OCR text, named by the words around it, with the text
    region; for an obituary step a Death fact before the page's date, otherwise a Residence on the page's date at the paper's
    place. Nothing when the surname is not in the text."""
    text, q, page = parsed["full_text"], parsed["query"], parsed["page"] or {}
    surname = (q.get("surname") or "").strip()
    if not surname: return
    seq, seen = 1, set()
    for m in re.finditer(r"(?:\b[A-Z][A-Za-z.'-]*\s+){0,2}\b" + re.escape(surname) + r"\b(?:\s+[A-Z][A-Za-z.]*)?", text, re.I):
        name = re.sub(r"\s+", " ", m.group(0)).strip()
        if key_of(name) in seen: continue
        seen.add(key_of(name)); start, end = max(0, m.start() - 160), min(len(text), m.end() + 160)
        pid = w.persona(name, None, "named in the text", seq, {"label": "ocr", "offset": m.start(), "snippet": text[start:end], "segment": parsed["segment"]}); seq += 1
        w.fact(pid, "Name", name, labels=["text"])
        place = ", ".join(x for x in (page.get("city"), page.get("state")) if x) or None
        if parsed["step_type"] == "obituary" and page.get("date"): w.fact(pid, "Death", None, "Bef " + page["date"], None, ["page date"])
        elif page.get("date") or place: w.fact(pid, "Residence", None, page.get("date"), place, ["page date", "newspaper place"])

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
    full_text = "\n".join(f"{l}: {v}" for l, v in parsed["fields"])
    if kind == "ancestry": full_text += "".join("\n" + " | ".join(r) for t in parsed["household"] for r in t["rows"])
    elif kind == "familysearch": full_text += "".join(f"\n{m['role']}: {m['name']} {m['sex']} {m['age']} {m['birthplace']}" for m in parsed["members"])
    elif kind == "findagrave": full_text += "".join(f"\n{m['label']}: {m['name']} {m.get('birth') or ''}-{m.get('death') or ''}" for m in parsed["members"])
    elif kind == "nara1950": full_text += "".join(f"\n{r.get('row')}: {r.get('name')}" for r in parsed["schedule"].get("names") or [])
    else: full_text = parsed["full_text"]
    cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status,full_text,structured_json) VALUES (?,?,?,?,'complete',?,?)",
               (eid, sha, ext_id, ts, full_text, dumps(parsed)))
    old = [r[0] for r in cx.execute("SELECT id FROM extraction WHERE artifact_sha256=? AND extractor_id=? AND id<>? AND superseded_by IS NULL", (sha, ext_id, eid))]
    cx.execute("UPDATE extraction SET superseded_by=? WHERE artifact_sha256=? AND extractor_id=? AND id<>? AND superseded_by IS NULL", (eid, sha, ext_id, eid))
    for o in old:                                                # a superseded extraction's undecided proposals rest on personas no longer current
        cx.execute("""UPDATE proposal SET status='rejected', decided_by=?, decided_at=?, decision_note='superseded'
                      WHERE status='undecided' AND json_extract(payload_json,'$.extraction_id')=?""", (by, ts, o))
    if kind == "familysearch" and parsed.get("ark"):
        cx.execute("INSERT OR IGNORE INTO artifact_locator (artifact_sha256,kind,value) VALUES (?,?,?)", (sha, "ark", parsed["ark"]))
    w = Writer(cx, sha, eid)
    {"findagrave": write_memorial, "familysearch": write_record, "nara1950": write_schedule, "locgov": write_ocr}.get(kind, write_personas)(w, parsed)
    cx.execute("INSERT INTO audit_log (id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?)",
               (ulid(), ts, by, "insert", "extraction", eid, dumps({"extractor": ":".join(extractor[:2]) + "@" + extractor[2], **w.n})))
    return eid, w.n

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("what", help="artifact sha256, or a path whose bytes are archived")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db")); ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    a = ap.parse_args()
    sha = a.what if re.fullmatch(r"[0-9a-f]{64}", a.what) else sha256_file(a.what)
    cx = sqlite3.connect(a.db); cx.execute("PRAGMA foreign_keys=ON")
    cx.execute("BEGIN"); eid, n = extract(cx, sha, a.by); cx.commit()
    print("extraction", eid, dumps(n))
    if "failed" in n: return
    for pid, name, sex, role in cx.execute("SELECT id, name_text, sex, role_in_record FROM persona WHERE extraction_id=? ORDER BY sequence", (eid,)):
        print(f"  {name} [{role}{', ' + sex if sex else ''}]")
        for ft, v, d, ps, rg in cx.execute("""SELECT pf.fact_type, pf.value_text, pf.date_text, ps.raw, pf.region_json FROM persona_fact pf
                                              LEFT JOIN place_string ps ON ps.id=pf.place_string_id WHERE pf.persona_id=?""", (pid,)):
            print(f"      {ft:14} {' '.join(x for x in (v, d, ps) if x)}")
        for kind, vt, other in cx.execute("SELECT r.kind, r.value_text, p.name_text FROM persona_relation r JOIN persona p ON p.id=r.related_persona_id WHERE r.persona_id=?", (pid,)):
            print(f"      {kind} of {other} ({vt})")

if __name__ == "__main__": main()
