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

---

## C. Anytime (no dependencies)

No upstream blockers; safe to pick up in any session. Default-focus tier.

### C1. Backups and fixity

Package `archive/` as BagIt bags for the external drive (the bag manifest is
the fixity record), put a plain-SQL dump of `catalog/tree.db` beside them
(never git: it holds living-person data), and verify `archive/objects`
against `artifact_copy` on a schedule so `v_artifact_under_replicated`
becomes actionable.

### C2. Search URL for an assisted search step at FamilySearch

A fetch step at FamilySearch carries the collection's own search prefilled
from the citation's details. A search step for a missing row at FamilySearch
(D03) carries no URL, so the step is worked by retyping the foundation into
the site. Build the URL from the step's fields with their basis, as the Find a
Grave search URL is built.

### C3. OCR / HTR extractor for record images

Turn an archived record image into personas and persona facts by machine,
versioned by extractor, beside the human transcription the person screen
offers today.

### C4. Place-string review from the catalog

The Undecided place strings and their `place_resolution` proposals have no
decision path. Decide them on the person screen as a question about the
person whose facts use the string, never as a standalone place queue.

### C5. Focus views on the tree overview

When a tree overview exists, let the user hide or highlight parts of it with
saved, hotkey-switchable views: hide the siblings they do not care about on a
line, keep one child of a large family, dim everything outside the line being
worked. A view changes only what is shown, never the data. Needs a tree
overview first.

### C6. Name variants in the matcher

The matcher compares the first given name exactly (one-letter initials
aside) and the surname as written, so a mother recorded under her married
name on a census (Ruth Davidson) does not fit the tree's Ruth M Peters even
when the record's relationship agrees, and Annie M Lukens does not fit Anna
Marie Bolton. Give the given-name comparison the alias table's variants and
let a married surname fit a birth surname when the relationship agrees, so
the proposal names the person the tree already has. Build it on the first
fetched page where the matcher actually misses. Nothing here changes what a
person decides.

### C7. The 1950 connector reads only the first page of results

`nara_1950` judges hits on the first 25 schedules the site returns; a search
without a county answers thousands and the person sought may sit on a later
page. Page while the total stays small, or ask the person for a county on the
step before searching a whole state.

### C8. The memorial's free-text biography is not extracted

A Find a Grave memorial can carry a biography that is the obituary itself
(Robert Edgar Davidson's names his parents, his siblings, his son and
daughter-in-law, his grandchildren and his great-grandson) or that refines or
contradicts the labelled fields (Noi Segawa Davidson: "Born in Morioka"
against a birth place field of "Tokushima, Japan"). The parser reads only the
labelled fields, so none of that reaches a persona fact or the card. Capture
the biography as its own fact type, as written, and let the matcher report
what it states beside the fields.

### C9. A sibling accepted from a memorial lands with no family link

Accepting a new-person proposal for a sibling on a memorial creates the
person but no family membership, because the record states the sibling of
the subject, not the parents. When the subject's parents are Accepted, place
the sibling as their child with an Undecided assertion on the record; until
then the card says the person would be unlinked, as it does now.

### C10. A household cemetery row reads held through a relative's memorial

The cemetery / family plot row is a Group A household row, so it reads held
for a person as soon as any relative's memorial is held, and the person never
gets a cemetery search step of their own (Ruth M Peters reads held through
her husband's and her son's memorials and is on neither). A memorial is about
one person. Decide whether the row stays a household row with a per-person
"own memorial" state, or splits into the plot (household) and the person's
memorial (individual).

---

## Externally blocked

Waiting on events the repo cannot drive.

- **FamilySearch API access** — Innovator Program approval after the
  application is submitted; the application text is written when the owner
  wants to submit it. Approval moves most Layer 1–2 searches from assisted to
  automatic.
- **NARA Catalog API key** — issued by email on request.
- **Pennsylvania death and birth certificates** — no free holder: Power
  Library shows the PA State Archives collections left the site and PHMC
  points only at Ancestry, so the steps for dbids 5164 and 60484 stay
  `blocked`. Add the row to `data/holders.csv` when they reappear at a free
  holder.
- **German → Polish gazetteer for Silesia (GOV / Kartenmeister)** — needed
  to resolve Harpersdorf, Langneundorf and the Berthelsdorf question; no
  programmatic access confirmed yet.
