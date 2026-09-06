"""Read-only access to a tree's people, events, places, citations and families.

Shared by tools/checklist.py and tools/footprint.py. Nothing here writes.
"""
import collections, csv, json, os, re, sqlite3, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

US_STATES = {"alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia","hawaii",
             "idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
             "minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey","new mexico","new york",
             "north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota",
             "tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming"}
US_NAMES = {"united states","usa","united states of america","us","british colonies","north america"}

def year(s): return int(s[:4]) if s and s[:4].isdigit() else None

def holders():
    """Free holders of the Ancestry collections the tree cites (data/holders.csv): {dbid: [row, ...]}, first row preferred."""
    out = {}
    with open(os.path.join(ROOT, "data", "holders.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh): out.setdefault(r["AncestryDbid"], []).append(r)
    return out

def dbid_of(apid):
    m = re.match(r"^\d+,(\d+)::(\d+)$", apid or "")
    return m.group(1) if m else None

PAGE_PART = re.compile(r"^([A-Za-z][A-Za-z .]{0,40}): (.+)$")

def page_key(apid, page):
    """The census page a citation names, from the citation's own details: the collection with the year, census place,
    enumeration district and page (sheet) parts of its page text. None when the details do not name one page (no year, place
    or page part), so a certificate box or a number range never counts as one page."""
    parts = {}
    for part in (page or "").split("; "):
        m = PAGE_PART.match(part.strip())
        if m: parts.setdefault(m.group(1).lower(), m.group(2).strip())
    yr = parts.get("year") or parts.get("residence date")
    place = parts.get("census place") or next((v for k, v in parts.items() if k.startswith("home in ")), None)
    sheet = parts.get("page") or parts.get("sheet") or parts.get("sheet number")
    if not (yr and place and sheet): return None
    return (dbid_of(apid), yr, place, parts.get("enumeration district"), sheet)

def page_groups(cx):
    """{record id: the record ids whose citations name the same census page}, over every citation in the catalog. Ancestry
    cites each household member under their own record id; those ids are one page."""
    by_key = {}
    for apid, page in cx.execute("""SELECT DISTINCT json_extract(notes,'$.apid'), json_extract(notes,'$.page') FROM assertion WHERE notes LIKE '{"apid":%'"""):
        k = page_key(apid, page)
        if k: by_key.setdefault(k, set()).add(apid)
    return {a: frozenset(g) for g in by_key.values() for a in g}

def same_page(cx, apid, groups=None):
    """The record ids naming the same census page as this one, itself included."""
    return set((page_groups(cx) if groups is None else groups).get(apid) or {apid})

def held_apids(cx, groups=None):
    """{record id: sha256} for every citation whose record is in the archive: the id the record was archived under and every id
    that names the same census page (the household's page is held for every member cited on it)."""
    groups = page_groups(cx) if groups is None else groups
    out = {}
    for v, sha in cx.execute("SELECT locator_value, sha256 FROM artifact WHERE locator_kind='apid' ORDER BY retrieved_at, sha256"):
        for a in groups.get(v) or {v}: out.setdefault(a, sha)
    return out

HOLDERS = None                                                   # data/holders.csv, read on first use

def fetch_target(apid, url=None, fields=None):
    """Where a cited record is opened: {url, holder}. The citation's own memorial URL when the holder is Find a Grave; the free
    holder's own search prefilled from the step's fields (the citation's details, never the person's facts) when they are given,
    else its collection page; Ancestry's record page when no free holder is known (a membership is needed there)."""
    m = re.match(r"^\d+,(\d+)::(\d+)$", apid or "")
    if not m: return {"url": None, "holder": None}
    global HOLDERS
    if HOLDERS is None: HOLDERS = holders()
    h = (HOLDERS.get(m.group(1)) or [None])[0]
    if h and h["HolderKind"] == "memorial" and url: return {"url": url, "holder": h["HolderCollection"]}
    if h and h["HolderKind"] != "memorial": return {"url": holder_search(h, fields) or h["URL"], "holder": h["HolderCollection"]}
    return {"url": f"https://www.ancestry.com/discoveryui-content/view/{m.group(2)}:{m.group(1)}", "holder": "Ancestry"}

def holder_search(h, fields):
    """The holder's own search URL from a fetch step's fields. FamilySearch: the collection search as the site itself builds it
    (f.collectionId, q.givenName, q.residenceDate.from/to and q.residencePlace from the citation's year and census place, q.surname).
    The National Archives 1950 site: its name search. None when the fields carry no name."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    name = (v("name") or "").split()
    if not name: return None
    if h["HolderKind"] == "fs_collection":
        q = [("f.collectionId", h["HolderKey"]), ("q.givenName", " ".join(name[:-1]) or name[0])]
        if v("year") and v("census place"): q += [("q.residenceDate.from", v("year")), ("q.residenceDate.to", v("year")), ("q.residencePlace", v("census place"))]
        q.append(("q.surname", name[-1]))
        return "https://www.familysearch.org/en/search/record/results?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    if h["HolderKey"] == "1950census.archives.gov": return "https://1950census.archives.gov/search/?" + urllib.parse.urlencode([("name", " ".join(name))], quote_via=urllib.parse.quote)
    return None

def findagrave_search_url(fields):
    """The Find a Grave memorial search as the site's own form builds it, from a search step's fields: firstname (the first given
    name), lastname, the birth and death years each with the year filter at 3 (the audit narrows the result, not the search),
    includeMaidenName for a woman, linkedToName for the first spouse, orderby relevance; no location, which filters on the
    cemetery's place rather than the death place. None without a surname."""
    v = lambda k: ((fields or {}).get(k) or {}).get("value")
    if not v("surname"): return None
    q = [("firstname", (v("given") or "").split()[0] if v("given") else ""), ("lastname", v("surname"))]
    if v("birth_year"): q += [("birthyear", str(v("birth_year"))), ("birthyearfilter", "3")]
    if v("death_year"): q += [("deathyear", str(v("death_year"))), ("deathyearfilter", "3")]
    if v("sex") == "F": q.append(("includeMaidenName", "true"))
    if v("spouses"): q.append(("linkedToName", v("spouses")[0]))
    q.append(("orderby", "r"))
    return "https://www.findagrave.com/memorial/search?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)

def search_target(sources, fields):
    """Where an assisted search step is run by hand: {url, holder} for a source whose own search the tool can build from the
    step's fields (Find a Grave, E01), else nothing."""
    if "E01" in (sources or []):
        u = findagrave_search_url(fields)
        if u: return {"url": u, "holder": "Find a Grave"}
    return {"url": None, "holder": None}

class Catalog:
    def __init__(self, cx, tree_id):
        self.cx, self.tree_id = cx, tree_id
        self.q = lambda s, *a: cx.execute(s, a).fetchall()
        self.sources = {r[0]: {"name": r[1], "access": r[2] or "", "status": r[3] or "", "cost": r[4] or "", "connector": r[5] or ""}
                        for r in self.q("SELECT id, name, access, status, cost, connector FROM source")}
        self.holders = holders()
        self._groups = self._held = None
    def find_person(self, key):
        """A person by id, exact display name, or substring of the name (exact wins; several matches are listed on stderr)."""
        r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND (id=? OR display_name=?) ORDER BY display_name LIMIT 5", self.tree_id, key, key)
        if not r: r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND display_name LIKE ? ORDER BY display_name LIMIT 5", self.tree_id, f"%{key}%")
        if not r: sys.exit(f"no person matching {key!r}")
        if len(r) > 1: print("matches:", ", ".join(f"{n} [{i[-6:]}]" for i, n in r), file=sys.stderr)
        return r[0][0]
    def person(self, pid):
        r = self.q("SELECT id, display_name, sex FROM person WHERE id=?", pid)[0]
        names = self.q("SELECT given, surname, suffix, is_primary, name_type FROM person_name WHERE person_id=? ORDER BY is_primary DESC", pid)
        aliases = [a[0] for a in self.q("SELECT value FROM alias WHERE entity_kind='person' AND entity_id=? AND status<>'rejected'", pid)]
        return {"id": r[0], "name": r[1], "sex": r[2], "names": names, "aliases": aliases}
    def events(self, pid):
        out = []
        for eid, et, dt, ds, de, place_id in self.q("""SELECT e.id, e.event_type, e.date_text, e.date_start, e.date_end, e.place_id FROM event e
                JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=? ORDER BY e.date_start""", pid):
            out.append({"id": eid, "type": et, "date_text": dt, "year": year(ds) or year(de), "place": self.place(eid, place_id),
                        "basis": self.basis("event", eid), "citations": self.citations("event", eid)})
        return out
    def place(self, eid, place_id):
        if place_id:
            chain, pid, region = [], place_id, {"country": None, "state": None}
            while pid:
                r = self.q("SELECT name, place_type, parent_id FROM place WHERE id=?", pid)[0]; chain.append(r[0])
                if r[1] == "country": region["country"] = r[0].lower()
                if r[1] == "state": region["state"] = r[0].lower()
                pid = r[2]
            return {"text": " < ".join(chain), "resolved": True, **region}
        raw = self.q("""SELECT ps.raw FROM assertion a JOIN persona_fact pf ON pf.id=a.persona_fact_id JOIN place_string ps ON ps.id=pf.place_string_id
                        WHERE a.subject_kind='event' AND a.subject_id=? LIMIT 1""", eid)
        if not raw: return None
        text = raw[0][0]; low = " " + text.lower().replace(",", " ") + " "
        toks = [t.strip().lower() for t in text.split(",") if t.strip()]
        st = next((t for t in toks if t in US_STATES), None) or next((n for n in US_STATES if f" {n} " in low), None)
        if st or any(f" {n} " in low for n in US_NAMES): country = "united states"
        else: country = next((c for c in ("ireland", "germany", "netherlands", "poland", "japan", "england", "allemagne", "silesia", "schlesien") if f" {c} " in low), None)
        country = {"allemagne": "germany", "silesia": "poland", "schlesien": "poland", "england": "united kingdom"}.get(country, country)
        return {"text": text, "resolved": False, "country": country, "state": st}
    KEY_FACTS = ("name", "sex", "birth", "death", "parents", "spouses", "children")
    def key_fact_basis(self, pid, ev=None):
        """basis per key fact: accepted | lead | rejected | None (no claim)."""
        ev = self.events(pid) if ev is None else ev
        out = {"name": self.basis("person", pid), "sex": self.basis("person", pid)}
        for f in ("birth", "death"):
            e = next((e for e in ev if e["type"] == f.title()), None); out[f] = e["basis"] if e else None
        for f in ("parents", "spouses", "children"): out[f] = self.link_basis(pid, f)
        return out
    def baseline(self, pid, ev=None):
        """The baseline is complete when no key fact is Undecided; absent and rejected facts are decided."""
        kb = self.key_fact_basis(pid, ev); und = [f for f in self.KEY_FACTS if kb[f] == "lead"]
        return {"key_facts": len(kb), "key_facts_accepted": sum(1 for b in kb.values() if b == "accepted"), "undecided": und, "complete": not und}
    def link_rejected(self, fid, person_id, role):
        """True when every assertion behind this family membership is rejected."""
        st = {r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind='family_member' AND subject_id=?", json.dumps([fid, person_id, role], separators=(",", ":"), sort_keys=True))}
        return bool(st) and st <= {"rejected"}
    def link_basis(self, pid, field):
        """accepted | lead | None for parents / spouses / children, from the family_member assertions behind them."""
        if field == "children":
            subs = [json.dumps([f, c, "child"], separators=(",", ":"), sort_keys=True) for f, in self.q("SELECT family_id FROM family_member WHERE person_id=? AND role='partner'", pid)
                    for c, in self.q("SELECT person_id FROM family_member WHERE family_id=? AND role='child'", f)]
        else:
            role = "child" if field == "parents" else "partner"
            subs = [json.dumps([f, pid, role], separators=(",", ":"), sort_keys=True) for f, in self.q("SELECT family_id FROM family_member WHERE person_id=? AND role=?", pid, role)]
        if not subs: return None
        st = set()
        for sid in subs: st |= {r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind='family_member' AND subject_id=?", sid)}
        return "accepted" if "accepted" in st else ("rejected" if st and st <= {"rejected"} else "lead")
    def basis(self, kind, sid):
        st = {r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind=? AND subject_id=?", kind, sid)}
        return "accepted" if "accepted" in st else ("rejected" if st == {"rejected"} else "lead")
    def citations(self, kind, sid):
        """[(collection name, apid, held artifact sha or None, collection id)] for a subject."""
        out = []
        for cname, notes, sha, tier, cid in self.q("""SELECT COALESCE(c.name, ac.name), a.notes, a.artifact_sha256, ar.trust_tier, COALESCE(c.id, ac.id) FROM assertion a
                LEFT JOIN collection c ON json_valid(a.notes) AND c.id=json_extract(a.notes,'$.collection_id')
                LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256
                LEFT JOIN collection ac ON ac.id=ar.collection_id
                WHERE a.subject_kind=? AND a.subject_id=? AND a.status<>'rejected'""", kind, sid):
            apid = json.loads(notes).get("apid") if notes and notes.startswith("{") else None
            held = sha if sha and tier in ("T1", "T2", "T3") else self.held_apids().get(apid)   # the record a match attached, or the archived page the citation names; the T4 tree export is not a held record
            if cname or held: out.append((cname or "", apid, held, cid))
        return out
    def family(self, pid):
        """Relatives through family memberships; a membership whose assertions are all rejected does not count."""
        fam = {"parents": [], "spouses": [], "children": [], "siblings": [], "families": []}
        for fid, role in self.q("SELECT family_id, role FROM family_member WHERE person_id=?", pid):
            if self.link_rejected(fid, pid, role): continue
            members = [m for m in self.q("SELECT fm.person_id, fm.role, p.display_name FROM family_member fm JOIN person p ON p.id=fm.person_id WHERE fm.family_id=?", fid)
                       if not self.link_rejected(fid, m[0], m[1])]
            if role == "child":
                fam["parents"] += [(m[0], m[2]) for m in members if m[1] == "partner"]
                fam["siblings"] += [(m[0], m[2]) for m in members if m[1] == "child" and m[0] != pid]
            else:
                sp = [(m[0], m[2]) for m in members if m[1] == "partner" and m[0] != pid]
                fam["spouses"] += sp; fam["children"] += [(m[0], m[2]) for m in members if m[1] == "child"]
                marr = self.q("""SELECT e.id, e.date_start, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.family_id=? AND e.event_type='Marriage'""", fid)
                fam["families"].append({"id": fid, "spouse": sp[0][1] if sp else None, "spouse_id": sp[0][0] if sp else None,
                                        "marriages": [{"id": m[0], "year": year(m[1]), "place": self.place(m[0], m[2]), "basis": self.basis("event", m[0]), "citations": self.citations("event", m[0])} for m in marr]})
        return fam
    def fetched_rows(self, pid):
        """Checklist row keys (record:instance) with a done step whose record is held: an archived artifact in its log, or an
        artifact at the step's locator (for a record id, at any id naming the same census page)."""
        out = set()
        for sid, rk, lkind, lval in self.q("SELECT id, row_key, locator_kind, locator_value FROM search_plan WHERE person_id=? AND status='done'", pid):
            if self.q("SELECT 1 FROM search_log WHERE plan_step_id=? AND artifacts_json IS NOT NULL AND artifacts_json<>'[]'", sid): out.add(rk)
            elif lkind == "apid" and lval in self.held_apids(): out.add(rk)
            elif lkind and lval and self.q("SELECT 1 FROM artifact WHERE locator_kind=? AND locator_value=?", lkind, lval): out.add(rk)
        return out
    def page_groups(self):
        if self._groups is None: self._groups = page_groups(self.cx)
        return self._groups
    def held_apids(self):
        """{record id: sha256} for every citation whose record is in the archive, the household page counting for every member cited on it."""
        if self._held is None: self._held = held_apids(self.cx, self.page_groups())
        return self._held
    def same_page(self, apid): return same_page(self.cx, apid, self.page_groups())
    def cited(self):
        """The citation's own details per Ancestry record id, from the import's assertions: {apid: {page, url, names}}, names being
        the tree's names of the people the citation sits on, in the order met (the only name the export carries for the record)."""
        if getattr(self, "_cited", None) is not None: return self._cited
        out = {}
        for apid, page, url, name in self.q("""SELECT json_extract(a.notes,'$.apid'), json_extract(a.notes,'$.page'), json_extract(a.notes,'$.url'), p.display_name
                FROM assertion a LEFT JOIN person p ON p.id = CASE a.subject_kind WHEN 'person' THEN a.subject_id
                     ELSE (SELECT ep.person_id FROM event_participant ep WHERE ep.event_id=a.subject_id AND ep.person_id IS NOT NULL LIMIT 1) END
                WHERE a.tree_id=? AND a.notes LIKE '{"apid":%' ORDER BY a.asserted_at, a.id""", self.tree_id):
            c = out.setdefault(apid, {"page": page, "url": url, "names": []})
            c["page"] = c["page"] or page; c["url"] = c["url"] or url
            if name and name not in c["names"]: c["names"].append(name)
        self._cited = out
        return out
    def person_citations(self, pid):
        """All citations attached to a person: on the person row and on every event of theirs."""
        cits = self.citations("person", pid)
        for eid, in self.q("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=?", pid):
            cits += self.citations("event", eid)
        return cits

