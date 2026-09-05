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
        self.sources = {r[0]: {"name": r[1], "access": r[2] or "", "status": r[3] or "", "cost": r[4] or ""}
                        for r in self.q("SELECT id, name, access, status, cost FROM source")}
    def find_person(self, key):
        r = self.q("SELECT id, display_name FROM person WHERE tree_id=? AND (id=? OR display_name LIKE ?) ORDER BY display_name LIMIT 5", self.tree_id, key, f"%{key}%")
        if not r: sys.exit(f"no person matching {key!r}")
        if len(r) > 1 and not any(x[0] == key for x in r): print("matches:", ", ".join(f"{n} [{i[-6:]}]" for i, n in r), file=sys.stderr)
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
    def basis(self, kind, sid):
        st = {r[0] for r in self.q("SELECT status FROM assertion WHERE subject_kind=? AND subject_id=?", kind, sid)}
        return "accepted" if "accepted" in st else ("rejected" if st == {"rejected"} else "lead")
    def citations(self, kind, sid):
        """[(collection name, apid, held artifact sha or None)] for a subject."""
        out = []
        for cname, notes, sha, tier in self.q("""SELECT c.name, a.notes, a.artifact_sha256, ar.trust_tier FROM assertion a
                LEFT JOIN collection c ON json_valid(a.notes) AND c.id=json_extract(a.notes,'$.collection_id')
                LEFT JOIN artifact ar ON ar.sha256=a.artifact_sha256
                WHERE a.subject_kind=? AND a.subject_id=? AND a.status<>'rejected'""", kind, sid):
            apid = json.loads(notes).get("apid") if notes and notes.startswith("{") else None
            held = sha if sha and tier in ("T1", "T2", "T3") else None       # the T4 tree export is not a held record
            if cname or held: out.append((cname or "", apid, held))
        return out
    def family(self, pid):
        fam = {"parents": [], "spouses": [], "children": [], "siblings": [], "families": []}
        for fid, role in self.q("SELECT family_id, role FROM family_member WHERE person_id=?", pid):
            members = self.q("SELECT fm.person_id, fm.role, p.display_name FROM family_member fm JOIN person p ON p.id=fm.person_id WHERE fm.family_id=?", fid)
            if role == "child":
                fam["parents"] += [(m[0], m[2]) for m in members if m[1] == "partner"]
                fam["siblings"] += [(m[0], m[2]) for m in members if m[1] == "child" and m[0] != pid]
            else:
                sp = [(m[0], m[2]) for m in members if m[1] == "partner" and m[0] != pid]
                fam["spouses"] += sp; fam["children"] += [(m[0], m[2]) for m in members if m[1] == "child"]
                marr = self.q("""SELECT e.id, e.date_start, e.place_id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.family_id=? AND e.event_type='Marriage'""", fid)
                fam["families"].append({"id": fid, "spouse": sp[0][1] if sp else None, "spouse_id": sp[0][0] if sp else None,
                                        "marriages": [{"id": m[0], "year": year(m[1]), "place": self.place(m[0], m[2]), "citations": self.citations("event", m[0])} for m in marr]})
        return fam
    def person_citations(self, pid):
        """All citations attached to a person: on the person row and on every event of theirs."""
        cits = self.citations("person", pid)
        for eid, in self.q("SELECT e.id FROM event e JOIN event_participant ep ON ep.event_id=e.id WHERE ep.person_id=?", pid):
            cits += self.citations("event", eid)
        return cits

