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

### A1. FamilySearch fetch of a cited census (Phase 3 of `docs/briefs/free-holders-fetch.md`)

The owner has a free FamilySearch account signed into Chrome, so the fetch
is possible. Not started. Abram C. Brant's 1900 census step (locator
`1,7602::47389682`, holder FamilySearch collection 1325221) carries the
citation's own details: Year 1900, Census Place Norristown, Montgomery,
Pennsylvania, Roll 1444, Page 2, ED 0240, indexed name Charlotte D Lukens.
Do it in the owner's browser, one record: collection page → the collection's
own search on the indexed name and place → the record page and its image;
capture the record page through the DOM and download the image through the
site's own control into `inbox/`; close the tab. On a scratch copy, archive
both, write the FamilySearch record-page parser into `tools/extract.py`
under its own extractor tag, compare field by field, run the matcher, report
verbatim. The DOM capture transport that worked for Find a Grave is in this
session's report (page cloned in-page, marker-encoded in a `<pre>`, read in
25,000-char slices, decoded and SHA-256-verified per chunk).
**Blocks:** nothing.

### A2. Swap in the rebuilt catalog

`catalog/tree-0.7.0.db` is the catalog rebuilt on schema 0.7.0 (initdb →
tree create → ingest → resolve_places → backfill_aliases → plan, 195
questions, 912 steps, the memorial archived). The real `catalog/tree.db` is
still 0.6.0 and the owner's own person-screen server runs old code on it.
Move the new file over the old one (the classifier would not let the worker
do it), restart the server, and delete the duplicate named GEDCOM copy the
rebuild's ingest left in `trees/ahearn/imports/`.
**Blocks:** A1 (the fetch step it targets exists only in the rebuilt catalog).

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

### C4b. Question closing precedes the fact decision

Accepting a persona match closes a `missing_fact` / `unverified_claim`
question as soon as the event and its Undecided assertion exist, because
the planner's gap definition asks for a cited event, not an accepted one.
The later fact decision then answers nothing. Decide whether the planner
should require an Accepted assertion before treating the gap as closed; if
so, the close moves to the fact decision.

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

---

## Externally blocked

Waiting on events the repo cannot drive.

- **FamilySearch API access** — Innovator Program approval after the
  application is submitted.
- **NARA Catalog API key** — issued by email on request.
- **German → Polish gazetteer for Silesia (GOV / Kartenmeister)** — needed
  to resolve Harpersdorf, Langneundorf and the Berthelsdorf question; no
  programmatic access confirmed yet.
