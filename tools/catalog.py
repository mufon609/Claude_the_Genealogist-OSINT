"""Read-only access to a tree's people, events, places, citations and families.

Shared by tools/checklist.py and tools/footprint.py. Nothing here writes.
"""
import collections, json, re, sqlite3, sys

US_STATES = {"alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia","hawaii",
             "idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
             "minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey","new mexico","new york",
             "north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota",
             "tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming"}
US_NAMES = {"united states","usa","united states of america","us","british colonies","north america"}

def year(s): return int(s[:4]) if s and s[:4].isdigit() else None

class Catalog:
    def __init__(self, cx, tree_id):
        self.cx, self.tree_id = cx, tree_id
        self.q = lambda s, *a: cx.execute(s, a).fetchall()
        self.sources = {r[0]: {"name": r[1], "access": r[2] or "", "status": r[3] or "", "cost": r[4] or "", "connector": r[5] or ""}
                        for r in self.q("SELECT id, name, access, status, cost, connector FROM source")}
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
            held = sha if sha and tier in ("T1", "T2", "T3") else None       # the T4 tree export is not a held record
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
        """Checklist row keys (record:instance) with a done step, fetch or search, that has an archived artifact in its log."""
        return {k for k, in self.q("""SELECT DISTINCT sp.row_key FROM search_plan sp JOIN search_log l ON l.plan_step_id=sp.id
                                      WHERE sp.person_id=? AND sp.status='done' AND l.artifacts_json IS NOT NULL AND l.artifacts_json<>'[]'""", pid)}
    def held_apids(self):
        """Ancestry record ids whose record is in the archive."""
        return {v for v, in self.q("SELECT locator_value FROM artifact WHERE locator_kind='apid'")}
    def person_citations(self, pid):
        """All citations attached to a person: on the person row and on every event of theirs."""
        cits = self.citations("person", pid)
        for eid, in self.q("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=?", pid):
            cits += self.citations("event", eid)
        return cits

