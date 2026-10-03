#!/usr/bin/env python3
"""Ingest a GEDCOM file into the catalog.

usage: tools/ingest_gedcom.py <file.ged> [--db catalog/tree.db] [--source <registry id>] [--by user:neural]

What happens
  0. The file is read in the encoding its own bytes and header say (UTF-8, UTF-16, ANSI; treelib.gedcom_codec) and is
     refused, with nothing recorded, when that encoding does not fit it, names a character set not read here, or the
     file holds no person.
  1. The file is archived (content-addressed copy + manifest) as a T4 artifact, labelled with the exporter its own header
     names: Ancestry's member-tree export is registry row B02 with its terms; an exporter with a Hosted Tree row in
     data/data-sources.csv gets that row; any other file is registry row A05, a family tree file of unknown origin.
     --source names the row instead.
  2. One extraction (extractor rule:gedcom-ingest) is recorded over it.
  3. Every INDI becomes a persona (what this tree says) + a person (conclusion)
     linked by an accepted person_persona. Every event becomes a persona_fact
     and an event with an assertion back to the fact and the artifact.
  4. SOUR records become collections (keyed by Ancestry dbid where the record carries one). Citations become
     assertion.citation_text (status 'undecided' until reviewed). The unique record
     citations and media references are kept in the extraction JSON for the
     footprint engine; they are not a queue.
  5. PLAC strings become place_string rows; Ancestry-HQ artifacts are flagged in an Ancestry export.
Nothing is updated in place; re-running on the same file is refused. A fresh tree has no home person: the run ends by
saying so and naming the command that sets it (tools/tree.py home), which tools/queue.py and tools/turns.py need.
"""
import argparse, collections, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from treelib import (ROOT, Node, connect, dumps, imports_dir, inbox_dir, manifest_path, now, object_path, parse_gedcom,
                     parse_gedcom_date, redistributable, resolve_tree, sha256_file, ulid)

EXTRACTOR = ("rule", "gedcom-ingest", "0.1.0")
EXTRACTOR_TAG = ":".join(EXTRACTOR[:2]) + "@" + EXTRACTOR[2]   # who asserts imported claims and links personas: the extractor, not the user
EVENT_TAGS = {"BIRT": "Birth", "DEAT": "Death", "BURI": "Burial", "CREM": "Cremation",
              "BAPM": "Baptism", "CHR": "Christening", "RESI": "Residence", "MARR": "Marriage",
              "PROB": "Probate", "WILL": "Will", "IMMI": "Immigration", "EMIG": "Emigration",
              "NATU": "Naturalization", "CENS": "Census", "OCCU": "Occupation", "_MILT": "Military Service",
              "ADDR": "Residence", "GRAD": "Graduation", "EDUC": "Education", "RELI": "Religion",
              "DIV": "Divorce", "ENGA": "Engagement", "MARL": "Marriage License", "MARB": "Marriage Banns"}
EVEN_TYPES = {"arrival": "Arrival", "departure": "Departure", "military": "Military Service",
              "military service": "Military Service", "draft": "Military Draft", "occupation": "Occupation",
              "tax": "Tax", "land": "Land Grant", "voter registration": "Voter Registration"}
FAMILY_EVENTS = {"Marriage", "Divorce", "Engagement", "Marriage License", "Marriage Banns"}
ARTIFACT_PLACE = re.compile(r"^(Lehi|Provo), UT, USA$")   # Ancestry's own headquarters, written into the publication place of its source records
APID_RE = re.compile(r"^(\d+),(\d+)::(\d+)$")
ANCESTRY = "B02"          # the registry row of Ancestry's member trees: its export is the one file whose terms and cost this ingest names itself
UNKNOWN_ORIGIN = "A05"    # the registry row for a family tree file whose header names no exporter the registry has

def header_exporter(head):
    """What the header's SOUR says wrote the file, in its own words: (system id, name, corporation), each None when absent."""
    src = head.first("SOUR") if head else None
    if not src: return None, None, None
    corp = src.first("CORP")
    return (src.value or None), (src.val("NAME") or None), ((corp.value if corp else None) or None)

def exporter_source(cx, exporter):
    """The registry row of the file's exporter: the Hosted Tree row whose name opens one of the names the header gives
    ("Ancestry.com" opens "Ancestry.com Family Trees"), else the row for a file of unknown origin."""
    key = lambda t: re.sub(r"[^a-z0-9]", "", (t or "").lower())
    for sid, name in cx.execute("SELECT id, name FROM source WHERE category='Hosted Tree' ORDER BY id"):
        if key(name) and any(key(n).startswith(key(name)) for n in exporter if n): return sid
    return UNKNOWN_ORIGIN

def xref_system(source_id, exporter):
    """external_id.system of the file's own record ids: Ancestry's export's, as it has always been named; another exporter's after
    the system id its header gives; a file naming none, bare."""
    if source_id == ANCESTRY: return "ancestry_gedcom_xref"
    own = re.sub(r"[^a-z0-9]+", "_", (exporter[0] or "").lower()).strip("_")
    return f"{own}_gedcom_xref" if own else "gedcom_xref"

class Ingest:
    def __init__(self, cx, path, source_id, by, tree_id, tree_slug):
        self.cx, self.path, self.source_id, self.by = cx, path, source_id, by   # source_id None: the registry row of the exporter the header names
        self.tree_id, self.tree_slug = tree_id, tree_slug
        self.archived_now = False
        self.ts = now()
        self.sha = None
        self.extraction_id = None
        self.extractor_id = None
        self.collections = {}      # SOUR xref -> (collection_id, name, dbid)
        self.place_strings = {}    # raw -> place_string id
        self.persons = {}          # INDI xref -> person_id
        self.personas = {}         # INDI xref -> persona_id
        self.families = {}         # FAM xref -> family_id
        self.apids = collections.defaultdict(lambda: {"subjects": [], "page": None, "url": None, "collection": None})
        self.stats = collections.Counter()
        self.head_note = None
        self.deferred_family_events = []   # (indi_node, event_node, etype, person_id, persona_id)
        self.family_events = {}            # (family_id, etype, date_text) -> event_id
        self.exporter = (None, None, None) # HEAD.SOUR's system id, name and corporation
        self.xref_system = "gedcom_xref"   # external_id.system of the file's own record ids

    # ------------------------------------------------------------ archive
    def label(self):
        """(collection, terms, cost, notes) the artifact's manifest carries: Ancestry's export as the registry's row B02 has it, any
        other file under its own registry row's terms and cost (unknown where the row gives none), named by the exporter's own words."""
        if self.source_id == ANCESTRY:
            return ("Ancestry Member Trees (GEDCOM export)", "ancestry-tos", "paid",
                    "User-exported GEDCOM. Conclusions of the tree owner; citations point at Ancestry records not yet archived.")
        name, terms, cost = self.cx.execute("SELECT name, terms, cost FROM source WHERE id=?", (self.source_id,)).fetchone()
        named = self.exporter[1] or self.exporter[0]
        return ((f"{named} (GEDCOM export)" if named else "Family tree file (GEDCOM), exporter not named"), terms or "unknown",
                (cost or "").lower() if (cost or "").lower() in ("free", "paid", "member") else "unknown",
                f"User-supplied GEDCOM, registry row {self.source_id} ({name}). Conclusions of whoever compiled the tree; its citations are leads, not records archived.")

    def archive_file(self):
        sha = self.sha = sha256_file(self.path)
        if self.cx.execute("SELECT 1 FROM tree_import WHERE tree_id=? AND artifact_sha256=?", (self.tree_id, sha)).fetchone():
            sys.exit(f"already imported into tree '{self.tree_slug}': sha256 {sha[:12]}…")
        exists = self.cx.execute("SELECT 1 FROM artifact WHERE sha256=?", (sha,)).fetchone()
        size = os.path.getsize(self.path)
        collection, terms, cost, notes = self.label()
        redist = redistributable(terms)
        manifest = {
            "schema_version": "0.1.0", "sha256": sha, "bytes": size, "mime": "text/x-gedcom",
            "source_id": self.source_id, "collection": collection,
            "locator": {"kind": "file", "value": os.path.basename(self.path)},
            "retrieved_at": self.ts, "retrieved_by": self.by,
            "rights": {"terms": terms, "redistributable": redist, "cost": cost},
            "trust_tier": "T4", "original_filename": os.path.basename(self.path), "pages": 1,
            "notes": notes,
        }
        dst, man = object_path(sha), manifest_path(sha)
        if not exists:
            self.archived_now = True
            os.makedirs(os.path.dirname(dst), exist_ok=True); os.makedirs(os.path.dirname(man), exist_ok=True)
            if not os.path.exists(dst): shutil.copyfile(self.path, dst)
            with open(man, "w", encoding="utf-8") as fh: json.dump(manifest, fh, ensure_ascii=False, indent=2)
        if not exists: self.cx.execute("""INSERT INTO artifact (sha256,byte_size,mime,source_id,locator_kind,locator_value,retrieved_at,
                           retrieved_by,terms,redistributable,cost,trust_tier,original_filename,page_count,manifest_json,created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (sha, size, "text/x-gedcom", self.source_id, "file", os.path.basename(self.path), self.ts,
                         self.by, terms, redist, cost, "T4", os.path.basename(self.path), 1, dumps(manifest), self.ts))
        if not exists: self.cx.execute("INSERT INTO artifact_copy (artifact_sha256,target_name,stored_at,last_verified,verify_ok) VALUES (?,?,?,?,?)",
                        (sha, "local", self.ts, self.ts, True))
        row = self.cx.execute("SELECT id FROM extractor WHERE kind=? AND name=? AND version=?", EXTRACTOR).fetchone()
        self.extractor_id = row[0] if row else ulid()
        if not row:
            self.cx.execute("INSERT INTO extractor (id,kind,name,version,created_at) VALUES (?,?,?,?,?)",
                            (self.extractor_id, *EXTRACTOR, self.ts))
        self.extraction_id = ulid()
        self.cx.execute("INSERT INTO extraction (id,artifact_sha256,extractor_id,ran_at,status) VALUES (?,?,?,?,'complete')",
                        (self.extraction_id, sha, self.extractor_id, self.ts))

    # ------------------------------------------------------------ reference
    def place_string(self, raw):
        raw = (raw or "").strip()
        if not raw: return None
        if raw in self.place_strings: return self.place_strings[raw]
        row = self.cx.execute("SELECT id FROM place_string WHERE raw=?", (raw,)).fetchone()   # shared layer: reuse
        if row:
            self.place_strings[raw] = row[0]; self.stats["place_strings_reused"] += 1; return row[0]
        pid = ulid()
        status, notes = "undecided", None
        if self.source_id == ANCESTRY and ARTIFACT_PLACE.match(raw):
            status, notes = "rejected", "Ancestry HQ address leaked into event place"
            self.stats["place_artifacts"] += 1
        self.cx.execute("INSERT INTO place_string (id,raw,status,notes) VALUES (?,?,?,?)", (pid, raw, status, notes))
        self.place_strings[raw] = pid
        self.stats["place_strings"] += 1
        return pid

    def _scan_citation_dbids(self, roots):
        """SOUR xref -> dbid, learned from citations (some SOUR records lack _APID)."""
        found = {}
        def walk(node):
            for c in node.children:
                if c.tag == "SOUR" and c.value and c.value.startswith("@"):
                    m = APID_RE.match(c.val("_APID", "") or "")
                    if m: found.setdefault(c.value, m.group(2))
                walk(c)
        for r in roots:
            if r.tag in ("INDI", "FAM"): walk(r)
        return found

    def load_sources(self, roots):
        seen_dbid, seen_name = {}, {}
        cited = self._scan_citation_dbids(roots)
        for n in roots:
            if n.tag != "SOUR": continue
            name = n.val("TITL") or n.xref
            dbid = None
            m = APID_RE.match(n.val("_APID", "") or "")
            if m: dbid = m.group(2)
            dbid = dbid or cited.get(n.xref)
            if dbid and dbid in seen_dbid:
                self.collections[n.xref] = seen_dbid[dbid]; self.stats["collections_merged"] += 1; continue
            if not dbid and name in seen_name:
                self.collections[n.xref] = seen_name[name]; self.stats["collections_merged"] += 1; continue
            # shared reference layer: reuse a collection already in the catalog
            row = (self.cx.execute("SELECT id, name FROM collection WHERE external_key_kind='ancestry_dbid' AND external_key=?", (dbid,)).fetchone()
                   if dbid else self.cx.execute("SELECT id, name FROM collection WHERE source_id=? AND name=? AND external_key IS NULL",
                                                (self.source_id, name)).fetchone())
            if row:
                self.collections[n.xref] = (row[0], row[1], dbid)
                if dbid: seen_dbid[dbid] = self.collections[n.xref]
                seen_name.setdefault(name, self.collections[n.xref])
                self.stats["collections_reused"] += 1; continue
            cid = ulid()
            pub = n.first("PUBL")
            notes = "; ".join(x for x in [n.val("AUTH"), pub.value if pub else None, pub.val("DATE") if pub else None] if x)
            self.cx.execute("""INSERT INTO collection (id,source_id,name,external_key_kind,external_key,trust_tier,notes)
                               VALUES (?,?,?,?,?,?,?)""",
                            (cid, self.source_id, name, "ancestry_dbid" if dbid else None, dbid,
                             "T4" if "Family Trees" in name else None, notes or None))
            self.collections[n.xref] = (cid, name, dbid)
            if dbid: seen_dbid[dbid] = self.collections[n.xref]
            seen_name.setdefault(name, self.collections[n.xref])
            self.stats["collections"] += 1

    # ------------------------------------------------------------ citations
    def citations(self, node):
        """Return list of (citation_text, apid, collection_id, page, name, url) for SOUR children of node: the citation's
        own details are its PAGE text and, for Find a Grave, the memorial URL under DATA/WWW."""
        out = []
        for s in node.all("SOUR"):
            col = self.collections.get(s.value)
            name = col[1] if col else s.value
            page = s.val("PAGE")
            apid = s.val("_APID")
            data = s.first("DATA"); url = data.val("WWW") if data else None
            text = name + (f"; {page}" if page else "") + (f"; {url}" if url else "")
            out.append((text, apid, col[0] if col else None, page, name, url))
        return out

    def assert_(self, subject_kind, subject_id, cits, persona_fact_id=None, persona_id=None):
        """Imported claims are 'undecided' until a human reviews them; the extractor is the asserter."""
        if not cits:
            self.cx.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,persona_id,artifact_sha256,
                               citation_text,status,asserted_by,asserted_at,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (ulid(), self.tree_id, subject_kind, subject_id, persona_fact_id, persona_id, self.sha,
                             "the file, no citation", "undecided", EXTRACTOR_TAG, self.ts, dumps({"uncited": True})))
            self.stats["assertions_uncited"] += 1
            return
        seen = set()                                          # the file may cite one record twice on one fact: one statement, one assertion
        for text, apid, cid, page, name, url in cits:
            if (apid or text) in seen: continue
            seen.add(apid or text)
            note = dumps({"apid": apid, "collection_id": cid, "page": page, "url": url}) if apid else None
            self.cx.execute("""INSERT INTO assertion (id,tree_id,subject_kind,subject_id,persona_fact_id,persona_id,artifact_sha256,
                               citation_text,status,asserted_by,asserted_at,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (ulid(), self.tree_id, subject_kind, subject_id, persona_fact_id, persona_id, self.sha,
                             text, "undecided", EXTRACTOR_TAG, self.ts, note))
            self.stats["assertions_cited"] += 1
            if apid:
                a = self.apids[apid]
                a["subjects"].append({"kind": subject_kind, "id": subject_id})
                a["page"] = a["page"] or page; a["url"] = a["url"] or url; a["collection"] = a["collection"] or name; a["collection_id"] = cid

    # ------------------------------------------------------------ people
    def event_from(self, node, etype, person_id=None, family_id=None, persona_id=None):
        d = parse_gedcom_date(node.val("DATE"))
        ps = self.place_string(node.val("PLAC"))
        value = node.value if node.tag in ("OCCU", "ADDR", "RELI", "EDUC") and node.value else None
        fact_id = None
        if persona_id:
            fact_id = ulid()
            self.cx.execute("""INSERT INTO persona_fact (id,persona_id,fact_type,value_text,date_text,date_start,date_end,
                               date_qualifier,calendar,place_string_id,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                            (fact_id, persona_id, etype, value, node.val("DATE"), d["date_start"], d["date_end"],
                             d["date_qualifier"], d["calendar"], ps, f"gedcom:{node.tag}"))
            self.stats["persona_facts"] += 1
        eid = ulid()
        self.cx.execute("""INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,description,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (eid, self.tree_id, etype, node.val("DATE"), d["date_start"], d["date_end"], d["date_qualifier"], d["calendar"],
                         value, self.ts, self.ts))
        self.cx.execute("INSERT INTO event_participant (id,event_id,person_id,family_id,role) VALUES (?,?,?,?,'primary')",
                        (ulid(), eid, person_id, family_id))
        self.assert_("event", eid, self.citations(node), persona_fact_id=fact_id)
        for nt in node.all("NOTE"):
            if nt.value:
                self.cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
                                (ulid(), self.tree_id, "event", eid, nt.value, self.by, self.ts)); self.stats["notes"] += 1
        self.stats["events"] += 1
        if node.val("DATE") and d["date_start"] is None and d["date_end"] is None:
            self.stats["dates_unparsed"] += 1
        return eid

    def load_people(self, roots):
        seq = 0
        for n in roots:
            if n.tag != "INDI": continue
            seq += 1
            xref = n.xref.strip("@")
            name = n.first("NAME")
            name_text = name.value if name else None
            sex = n.val("SEX") or "U"
            sex = sex if sex in ("M", "F", "X", "U") else "U"
            # persona = what the tree says
            pa = ulid()
            self.cx.execute("""INSERT INTO persona (id,extraction_id,artifact_sha256,name_text,sex,role_in_record,sequence,notes)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (pa, self.extraction_id, self.sha, name_text, sex, "tree_person", seq, f"gedcom:{n.xref}"))
            self.personas[n.xref] = pa
            names = n.all("NAME")
            name_fact_ids = []
            for nm in names:                                   # every NAME record is evidence; the first is primary
                fid_ = ulid(); name_fact_ids.append(fid_)
                self.cx.execute("INSERT INTO persona_fact (id,persona_id,fact_type,value_text,notes) VALUES (?,?,?,?,?)",
                                (fid_, pa, "Name", nm.value, "gedcom:NAME" + (":" + nm.val("TYPE") if nm.val("TYPE") else "")))
            self.cx.execute("INSERT INTO persona_fact (id,persona_id,fact_type,value_text,notes) VALUES (?,?,?,?,?)",
                            (ulid(), pa, "Sex", sex, "gedcom:SEX"))
            self.stats["persona_facts"] += 1 + len(names)
            # person = conclusion
            pid = ulid()
            given = name.val("GIVN") if name else None
            surname = name.val("SURN") if name else None
            suffix = name.val("NSFX") if name else None
            if name and not (given or surname):
                m = re.match(r"^(.*?)\s*/([^/]*)/\s*(.*)$", name.value or "")
                if m: given, surname, suffix = m.group(1).strip() or None, m.group(2).strip() or None, m.group(3).strip() or None
            display = " ".join(x for x in [given, surname, suffix] if x) or name_text
            self.cx.execute("INSERT INTO person (id,tree_id,sex,display_name,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                            (pid, self.tree_id, sex, display, self.ts, self.ts))
            self.persons[n.xref] = pid
            sort_key = f"{(surname or '').lower()}, {(given or '').lower()}".strip(", ")
            self.cx.execute("""INSERT INTO person_name (id,person_id,name_type,given,surname,suffix,is_primary,sort_key)
                               VALUES (?,?,?,?,?,?,?,?)""", (ulid(), pid, "birth", given, surname, suffix, True, sort_key))
            for nm in names[1:]:                               # additional NAME records -> non-primary names
                m = re.match(r"^(.*?)\s*/([^/]*)/\s*(.*)$", nm.value or "")
                g2, s2, x2 = (nm.val("GIVN") or (m.group(1).strip() if m else None) or None,
                              nm.val("SURN") or (m.group(2).strip() if m else None) or None,
                              nm.val("NSFX") or (m.group(3).strip() if m else None) or None)
                ntype = {"married": "married", "aka": "aka", "birth": "birth", "immigrant": "immigrant"}.get((nm.val("TYPE") or "").lower(), "aka")
                self.cx.execute("""INSERT INTO person_name (id,person_id,name_type,given,surname,suffix,is_primary,sort_key)
                                   VALUES (?,?,?,?,?,?,?,?)""",
                                (ulid(), pid, ntype, g2, s2, x2, False, f"{(s2 or '').lower()}, {(g2 or '').lower()}".strip(", ")))
                self.stats["extra_names"] += 1
            self.cx.execute("INSERT INTO person_persona (person_id,persona_id,status,decided_by,decided_at) VALUES (?,?,?,?,?)",
                            (pid, pa, "accepted", EXTRACTOR_TAG, self.ts))   # definitional: this GEDCOM entry *is* this person (DATA-ARCHITECTURE §1a)
            self.cx.execute("INSERT INTO external_id (id,tree_id,entity_kind,entity_id,system,value,created_at) VALUES (?,?,?,?,?,?,?)",
                            (ulid(), self.tree_id, "person", pid, self.xref_system, xref, self.ts))
            # person-level citations: the INDI and NAME levels carry the same citation twice; one assertion per record id
            cits = list({(c[1] or c[0]): c for c in self.citations(n) + [c for nm in names for c in self.citations(nm)]}.values())
            self.assert_("person", pid, cits, persona_id=pa)
            # events
            for c in n.children:
                etype = EVENT_TAGS.get(c.tag)
                if c.tag == "EVEN":
                    etype = EVEN_TYPES.get((c.val("TYPE") or "").lower(), "Unknown")
                    if etype == "Unknown": self.stats["even_unknown_type"] += 1
                if etype in FAMILY_EVENTS:
                    self.deferred_family_events.append((n, c, etype, pid, pa)); continue
                if etype:
                    self.event_from(c, etype, person_id=pid, persona_id=pa)
            for nt in n.all("NOTE"):
                if nt.value:
                    self.cx.execute("INSERT INTO note (id,tree_id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?,?)",
                                    (ulid(), self.tree_id, "person", pid, nt.value, self.by, self.ts)); self.stats["notes"] += 1
            for ob in n.all("OBJE"):
                self.media_links[ob.value].append(pid)
            self.stats["persons"] += 1

    def load_families(self, roots):
        for n in roots:
            if n.tag != "FAM": continue
            fid = ulid()
            rel = "married" if n.first("MARR") else "unknown"
            self.cx.execute("INSERT INTO family (id,tree_id,rel_type,created_at,updated_at) VALUES (?,?,?,?,?)", (fid, self.tree_id, rel, self.ts, self.ts))
            self.families[n.xref] = fid
            self.cx.execute("INSERT INTO external_id (id,tree_id,entity_kind,entity_id,system,value,created_at) VALUES (?,?,?,?,?,?,?)",
                            (ulid(), self.tree_id, "family", fid, self.xref_system, n.xref.strip("@"), self.ts))
            members = []
            for tag in ("HUSB", "WIFE"):
                for c in n.all(tag):
                    if c.value in self.persons: members.append((self.persons[c.value], "partner", None, None))
            for i, c in enumerate(n.all("CHIL")):
                if c.value in self.persons: members.append((self.persons[c.value], "child", "birth", i + 1))
            for person_id, role, child_rel, seq in members:
                self.cx.execute("INSERT INTO family_member (family_id,person_id,role,child_rel,seq) VALUES (?,?,?,?,?)",
                                (fid, person_id, role, child_rel, seq))
                self.assert_("family_member", dumps([fid, person_id, role]), self.citations(n))
                self.stats["family_members"] += 1
            for c in n.children:
                etype = EVENT_TAGS.get(c.tag)
                if etype in FAMILY_EVENTS:
                    eid = self.event_from(c, etype, family_id=fid)
                    d = parse_gedcom_date(c.val("DATE"))
                    dkey = d["date_start"] or d["date_end"] or (c.val("DATE") or "").strip().lower()
                    self.family_events[(fid, etype, dkey, (c.val("PLAC") or "").strip().lower())] = eid
            self.stats["families"] += 1

    def resolve_deferred_family_events(self):
        """INDI-level MARR etc. Ancestry stores marriage facts on each spouse, often with
        several conflicting date/place variants. Each variant becomes ONE family event,
        shared by both spouses; nothing is collapsed. Falls back to a person event only
        when the family cannot be determined."""
        def year(d): return (d.get("date_start") or d.get("date_end") or "")[:4]
        for indi, node, etype, pid, pa in self.deferred_family_events:
            fams = [self.families[f.value] for f in indi.all("FAMS") if f.value in self.families]
            d = parse_gedcom_date(node.val("DATE"))
            dkey = (d["date_start"] or d["date_end"] or (node.val("DATE") or "").strip().lower())
            pkey = (node.val("PLAC") or "").strip().lower()
            fid = None
            if len(fams) == 1:
                fid = fams[0]
            elif fams:
                cands = [f for f in fams for k in self.family_events if k[0] == f and k[1] == etype and k[2][:4] == year(d) and year(d)]
                if len(set(cands)) == 1: fid = cands[0]
            if fid is None:
                self.event_from(node, etype, person_id=pid, persona_id=pa); self.stats["family_events_unmatched"] += 1
                continue
            fact_id = ulid()
            ps = self.place_string(node.val("PLAC"))
            self.cx.execute("""INSERT INTO persona_fact (id,persona_id,fact_type,date_text,date_start,date_end,date_qualifier,calendar,place_string_id,notes)
                               VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (fact_id, pa, etype, node.val("DATE"), d["date_start"], d["date_end"], d["date_qualifier"], d["calendar"], ps, f"gedcom:{node.tag}"))
            self.stats["persona_facts"] += 1
            key = (fid, etype, dkey, pkey)
            eid = self.family_events.get(key)
            # a FAM-level event with the same date but no place also counts as the same event
            if eid is None and pkey:
                eid = self.family_events.get((fid, etype, dkey, ""))
            if eid is None:
                eid = ulid()
                self.cx.execute("""INSERT INTO event (id,tree_id,event_type,date_text,date_start,date_end,date_qualifier,calendar,created_at,updated_at)
                                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                (eid, self.tree_id, etype, node.val("DATE"), d["date_start"], d["date_end"], d["date_qualifier"], d["calendar"], self.ts, self.ts))
                self.cx.execute("INSERT INTO event_participant (id,event_id,family_id,role) VALUES (?,?,?,'primary')", (ulid(), eid, fid))
                self.family_events[key] = eid
                self.stats["events"] += 1; self.stats["family_events_from_indi"] += 1
            else:
                self.stats["family_events_merged"] += 1
            self.assert_("event", eid, self.citations(node), persona_fact_id=fact_id)

    # ------------------------------------------------------------ what the tree cited (kept as data, not as a queue)
    def collect_media(self, roots):
        """Media objects referenced by the export but not contained in it. Kept in the extraction JSON."""
        out = []
        for n in roots:
            if n.tag != "OBJE": continue
            file = n.first("FILE"); clon = n.first("_CLON")
            out.append({"oid": n.val("_OID"), "title": file.val("TITL") if file else None, "form": file.val("FORM") if file else None,
                        "mtype": n.val("_MTYPE"), "description": n.val("_DSCR"), "created": n.val("_CREA"),
                        "origin_pid": clon.val("_PID") if clon else None, "origin_tid": clon.val("_TID") if clon else None,
                        "persons": self.media_links.get(n.xref, [])})
        self.stats["media_refs"] = len(out)
        return out

    def collect_cited_records(self):
        """Unique Ancestry record citations with the subjects they support. Kept in the extraction JSON."""
        out = []
        for apid, a in self.apids.items():
            m = APID_RE.match(apid)
            if not m or (a["collection"] or "").startswith("Ancestry Family Trees"):
                self.stats["citations_tree_to_tree"] += len(a["subjects"]); continue
            out.append({"apid": apid, "dbid": m.group(2), "record_id": m.group(3), "collection": a["collection"],
                        "collection_id": a.get("collection_id"), "page": a["page"], "url": a["url"], "subjects": a["subjects"]})
        self.stats["cited_records"] = len(out)
        return out

    # ------------------------------------------------------------ run
    def run(self):
        roots = parse_gedcom(self.path)
        if not any(r.tag == "INDI" for r in roots): sys.exit(f"{self.path}: no INDI record, so no person to import; nothing was recorded")
        head = next((r for r in roots if r.tag == "HEAD"), None)
        self.exporter = header_exporter(head)
        self.source_id = self.source_id or exporter_source(self.cx, self.exporter)
        if not self.cx.execute("SELECT 1 FROM source WHERE id=?", (self.source_id,)).fetchone():
            sys.exit(f"the source registry has no row {self.source_id}: python3 tools/initdb.py --sync-sources")
        self.xref_system = xref_system(self.source_id, self.exporter)
        self.media_links = collections.defaultdict(list)
        self.archive_file()
        if head and self.archived_now:
            src = head.first("SOUR")
            tree = src.first("_TREE") if src else None
            if tree and tree.val("NOTE"):
                self.cx.execute("INSERT INTO note (id,entity_kind,entity_id,body,author,created_at) VALUES (?,?,?,?,?,?)",
                                (ulid(), "artifact", self.sha, "Tree description from GEDCOM header:\n" + tree.val("NOTE"), self.by, self.ts))
            if tree and tree.value:
                self.cx.execute("INSERT INTO external_id (id,entity_kind,entity_id,system,value,created_at) VALUES (?,?,?,?,?,?)",
                                (ulid(), "artifact", self.sha, "ancestry_tree_name", tree.value, self.ts))
        self.load_sources(roots)
        self.load_people(roots)
        self.load_families(roots)
        self.resolve_deferred_family_events()
        media = self.collect_media(roots); cited = self.collect_cited_records()
        summary = dict(self.stats)
        self.cx.execute("UPDATE extraction SET structured_json=? WHERE id=?",
                        (dumps({"summary": summary, "media": media, "cited_records": cited}), self.extraction_id))
        self.cx.execute("INSERT INTO audit_log (id,tree_id,at,actor,action,entity_kind,entity_id,diff_json) VALUES (?,?,?,?,?,?,?,?)",
                        (ulid(), self.tree_id, self.ts, self.by, "import", "artifact", self.sha, dumps(summary)))
        self.import_id = ulid()
        self.cx.execute("""INSERT INTO tree_import (id,tree_id,artifact_sha256,extraction_id,imported_at,imported_by,summary_json)
                           VALUES (?,?,?,?,?,?,?)""", (self.import_id, self.tree_id, self.sha, self.extraction_id, self.ts, self.by, dumps(summary)))
        return summary

    def file_original(self, move: bool):
        """Put a human-named copy under trees/<slug>/imports/<date>_<name>; move if it came from the inbox."""
        dst_dir = imports_dir(self.tree_slug)
        os.makedirs(dst_dir, exist_ok=True)
        base = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", re.sub(r"\s+", "-", os.path.basename(self.path)))
        already_filed = os.path.dirname(os.path.abspath(self.path)) == os.path.abspath(dst_dir)
        dst = os.path.abspath(self.path) if already_filed else os.path.join(dst_dir, f"{self.ts[:10]}_{base}")
        if not already_filed:
            if os.path.exists(dst): os.remove(dst)
            (shutil.move if move else shutil.copyfile)(self.path, dst)
        self.cx.execute("UPDATE tree_import SET original_path=? WHERE id=?", (dst, self.import_id))
        self.cx.commit()
        return dst

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--db", default=os.path.join(ROOT, "catalog", "tree.db"))
    ap.add_argument("--source", help="source registry id of the file's exporter (default: the row of the exporter its header names, else A05)")
    ap.add_argument("--by", default="user:" + (os.environ.get("USER") or "unknown"))
    ap.add_argument("--tree", help="tree slug (default: $TREE or catalog/.active-tree)")
    ap.add_argument("--keep", action="store_true", help="copy instead of moving the file out of the inbox")
    a = ap.parse_args()
    cx = connect(a.db)
    cx.execute("PRAGMA foreign_keys=ON")
    tree_id, slug = resolve_tree(cx, a.tree)
    ing = Ingest(cx, a.path, a.source, a.by, tree_id, slug)
    try:
        cx.execute("BEGIN")
        summary = ing.run()
        cx.commit()
    except Exception:
        cx.rollback()
        if ing.archived_now:
            for p in (object_path(ing.sha), manifest_path(ing.sha)):
                if os.path.exists(p): os.remove(p)
        raise
    in_inbox = os.path.abspath(a.path).startswith(inbox_dir() + os.sep)
    filed = ing.file_original(move=in_inbox and not a.keep)
    print(f"ingested {os.path.basename(a.path)} -> tree '{slug}', artifact {ing.sha[:12]}…\n  filed at {os.path.relpath(filed, ROOT)}")
    print(f"  {'exporter':28} {' / '.join(x for x in ing.exporter if x) or 'not named in the header'}: registry row {ing.source_id}")
    for k in sorted(summary): print(f"  {k:28} {summary[k]}")
    if not cx.execute("SELECT home_person_id FROM tree WHERE id=?", (tree_id,)).fetchone()[0]:
        print(f"\nno home person is set for tree '{slug}': tools/queue.py and tools/turns.py need one and refuse to run without it.\n"
              f"Set it with: python3 tools/tree.py home \"<person>\" --tree {slug}")

if __name__ == "__main__":
    main()
