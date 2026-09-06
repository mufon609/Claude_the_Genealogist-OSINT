---
id: meta/BACKLOG
type: meta
---

# BACKLOG

Deferred work — real, concrete, and would be lost otherwise; not on the
active roadmap. An item leaves when promoted to active work, addressed,
or superseded.

## How this file works

**This file is self-governing** — it is the root authority for how the
BACKLOG is written, identified, and closed. Nothing outside it governs it.

**Sections.** Open items are partitioned by dependency shape:
**A — Priority sequence** (ordering / coupling constraints),
**B — Parallel batch** (items that only make sense shipped together),
**C — Anytime** (no upstream blockers). **Default focus is C:** no
dependencies, finishable in one pass. Reserve A and B for sessions scoped
to them — starting a constrained item out of order half-bakes it and
clutters the file. Cross-reference entries with `**Blocks:**` /
`**Blocked by:**` lines so the dependency graph stays inline.

**Identifiers** (A1, B1, C1…) are positional working labels, not stable
IDs. A new entry takes the lowest unused number in its section, so numbers
**recycle**; once a section — and ultimately the whole BACKLOG — is cleared,
numbering restarts from 1. Because an ID is transient, **never reference it
outside this file** — not in code, docs, prompts, commit messages, or
`git log` searches. Describe the work; the commit diff + message are the
record.

**Opening an entry.** Write it forward-looking and prescriptive: the work
and why it matters. No "Surfaced from", audit/session label, or commit hash
pinning when the need arose — that history lives in `git log`.

**Closing an entry.** The goal is to REMOVE items, not annotate them.
Delete the block in full — no retirement marker, no placeholder; the
shipping commit's diff + message is the canonical record. Then sweep any
code comments that cited the closed ID (delete them, or rewrite to describe
current behavior) — that sweep is part of closing, not follow-up.

**Not a backlog.** Research to-dos about the family (merge a duplicate
person, fetch a cited census page, resolve a Silesian village) are questions
the app generates for a tree; they live in the catalog, not here.

**Externally-blocked items** waiting on an event the repo can't drive
(API approval, a registry we do not control) live under "Externally
blocked" at the foot of this file.

---

## A. Priority sequence

Items with ordering or coupling constraints.

No items.

---

## B. Parallel batch

### B1. Exporters

GEDCOM 7 (with GEDZIP of redistributable media) and Gramps XML, both from
the conclusions layer, honouring the living-person redaction. Ship together
so a tree can be round-tripped and opened in Gramps desktop.

### B2. Postgres extras

`schema/postgres_extras.sql` with tsvector indexes mirroring the SQLite
FTS5 tables, plus the dump/load procedure in `schema/README.md`.

---

## C. Anytime (no dependencies)

No upstream blockers; safe to pick up in any session. Default-focus tier.

### C1. Archive integrity scrub

Nightly sampled and monthly full SHA-256 verification of `archive/objects`
against `artifact_copy`, updating `last_verified` / `verify_ok`;
`v_artifact_under_replicated` becomes actionable.

### C2. BagIt export of the archive

Package `archive/` as BagIt bags for the external drive and, later, the
S3 master bucket. Bag manifest = fixity record.

### C3. Catalog SQL dump

Scheduled plain-SQL dump of `catalog/tree.db` into a bag beside the archive
bags, never git (it holds living-person data), so the conclusions layer has a
text history independent of the binary db.

### C4. Fetcher for assisted sources

Build the exact search URL and "what to look for" for Newspapers.com and the
FamilySearch record search from a gap's foundation fields (fetch steps for
cited records already carry the citation's details and the free holder's
URL); archive whatever the user drops in `inbox/` and attach it to the gap.

### C4a. Pennsylvania death and birth certificates have no free holder

Power Library shows a notice that the PA State Archives collections left the
site, and PHMC points only at Ancestry, so the steps for dbids 5164 and
60484 stay `blocked`. Watch for the certificates reappearing at a free
holder (PHMC, Power Library, FamilySearch) and add the row to
`data/holders.csv`.

### C5. OCR / HTR extractor for record images

Turn an archived record image into personas and persona facts by machine,
versioned by extractor, beside the human transcription the person screen
offers today. The Ancestry index extractor in `tools/extract.py` is still
unverified on a real page (Ancestry needs a membership this account lacks);
the Find a Grave memorial extractor is verified.

### C6. Place-string review from the catalog

The 41 Undecided place strings and their proposals need a way to be
decided that fits the person screen (a gap on the person whose facts use
the string), not a standalone place queue.

### C7. Per-tree access control

`tree_member` table keyed on `tree_id`; needed only when a second person
uses the same catalog.

### C8. FamilySearch Innovator application text

Draft the Third-Party Service Provider application for the user to submit;
approval moves most Layer 1–2 searches from assisted to automatic.
**Blocks:** Externally blocked / FamilySearch API.

### C9. Focus views on the tree overview

When a tree overview exists, let the user hide or highlight parts of it with
saved, hotkey-switchable views: hide the siblings they do not care about on a
line, keep one child of a large family, dim everything outside the line being
worked. A view changes only what is shown, never the data. Far out; needs a
tree overview first.

### C10. Proposal kinds with no decision path

`fact` proposals (the alias backfill's canonical-name fixes) can be decided
nowhere: the person screen decides only persona matches and new persons, and
no tool decides them. Either give them a control on the person whose name they
concern, or stop raising them and put the finding in a note.

### C11. Locator kinds on fetch steps

Every fetch step's `locator_kind` is `apid`, including Find a Grave memorials,
for which the schema names `memorial_id`, while the memorial URL rides in the
step's fields. Use the schema's kinds: `memorial_id` for Find a Grave, `ark`
for a FamilySearch record, `naid` for the National Archives, `apid` only for
the citation's own identity.

### C12. Name variants in the matcher

The matcher compares the first given name exactly (one-letter initials
aside), so Annie M Lukens on the 1900 census does not fit Anna Marie Bolton,
Charlotte's mother in the tree, even though the record's relationship agrees;
accepting her as a new person adds a third partner to Milton Lukens's family.
Give the given-name comparison the alias table's variants (Annie/Anna,
Lottie/Charlotte, Abram/Abraham) and let a married surname fit a birth
surname when the relationship agrees, so the proposal names the person the
tree already has. Nothing here changes what a person decides.

### C13. The DOM capture carries the browser extension's own nodes

A record page captured through the Chrome extension's DOM includes the
extension's injected elements (ids beginning `claude-`), so the archived
bytes are the rendered page plus a few nodes the site never served. The
parsers ignore them. Decide whether the capture strips them before hashing,
or the manifest notes the capture method; the page as served by the site
would need the site's own save or an endpoint.

### C14. Fetch steps at a holder with a connector

A cited 1950 census record (holder D05) carries the citation's indexed name,
county and enumeration district, which is exactly what the 1950 site's search
takes, yet the runner executes only `search` steps: a `fetch` step at a
holder whose registry row names a connector could run the same way, keeping
the page whose ED matches the citation. The same shape will serve
FamilySearch once its API is open.

### C15. A held census page is held only under the apid it was archived by

Ancestry cites each household member under their own record id, so the 1900
page archived at Charlotte D Lukens's apid does not count as held for Milton
Reager Lukens, whose citations name the same page under his apid; his facts
stay "record not held" and his baseline cannot be completed. The citation's
own details (collection, roll, page, ED) identify the page: on attach, write
every apid whose citation page text matches into `artifact_locator`, and let
the held rule read locators, not only the artifact's first one.

### C16. The 1950 connector reads only the first page of results

`nara_1950` judges hits on the first 25 schedules the site returns; a search
without a county (no residence near 1950 in the foundation) answers thousands
and the person sought may sit on a later page. Page while the total stays
small, or ask the person for a county on the step before searching a whole
state.

### C17. Basis word on residences

The foundation shows basis `mixed` on the residence trail; the docs define
only `accepted`, `lead`, `row` and `citation`. Give each residence its own
basis or drop the row from the foundation.

### C18. Standing approval: auto-accept a file claim a trusted record corroborates

The owner wants to decide sources as well as facts (each source Accepted,
Rejected or Undecided per tree) and to say in advance that a fact the
imported file already claims is Accepted automatically when a record from a
source they accepted corroborates it. That is a person deciding, delegated as
a standing rule, so it must be recorded as the rule acting on the owner's
behalf, auditable and reversible, and it changes the per-fact reading of the
"nothing Accepted without a person" rule. Needs more depth before any brief:
what "corroborates" means field by field (exact date, year only, place at
county level), the bar for the match itself (name plus how many independent
facts, no disagreement), what happens on a later contradicting record, how a
source decision is stored (tree-scoped, three states, on the registry row),
and what the card shows when the rule fired so the owner can undo it. Design
first, in `docs/RESEARCH-WORKFLOW.md`, then a brief.

---

## Externally blocked

Waiting on events the repo cannot drive.

- **FamilySearch API access** — Innovator Program approval after the
  application is submitted.
- **NARA Catalog API key** — issued by email on request.
- **German → Polish gazetteer for Silesia (GOV / Kartenmeister)** — needed
  to resolve Harpersdorf, Langneundorf and the Berthelsdorf question; no
  programmatic access confirmed yet.
