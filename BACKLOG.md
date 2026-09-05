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

### A3. Person screen

Foundation (Accepted facts, check / uncheck / revise), checklist with
tasks, results under the task clicked, three-state review. One person per
screen, linear flow, no tabs (`docs/RESEARCH-CHECKLIST.md` §6). Local
server, no framework.

### A4. Research log and typed search steps

`research_question`, `search_plan`, `search_log` tables and the
`proposal.question_id` link (`docs/RESEARCH-WORKFLOW.md`, schema
additions). Every run logged with the exact fields used, negatives included.

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

Scheduled plain-SQL dump of `catalog/tree.db` into a versioned location
so the conclusions layer has a text history independent of the binary db.

### C4. Fetcher for assisted sources

Build the exact search URL and "what to look for" for Ancestry, Find a
Grave and Newspapers.com from a gap's foundation fields; archive whatever
the user drops in `inbox/` and attach it to the gap.

### C5. Extractor for Ancestry index JSON and record images

Turn a fetched record into personas and persona facts: index-page parse
first, OCR/HTR later. Every extraction versioned by extractor.

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

---

## Externally blocked

Waiting on events the repo cannot drive.

- **FamilySearch API access** — Innovator Program approval after the
  application is submitted.
- **NARA Catalog API key** — issued by email on request.
- **German → Polish gazetteer for Silesia (GOV / Kartenmeister)** — needed
  to resolve Harpersdorf, Langneundorf and the Berthelsdorf question; no
  programmatic access confirmed yet.
