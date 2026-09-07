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

### C1. The New York State marriage index as a source

Reclaim the Records put the state marriage index 1881–1967 on the Internet
Archive, one item per year (brides and grooms apart before 1955), as scanned
pages with poor OCR: a Soundex block per page, each line surname, given name,
place the licence was issued, the spouse's surname to four letters, month,
day, certificate number. One such page is archived as a record under New
York vital records (C08), read by the model. Make it a step: for
a missing marriage row, locate the Soundex block's pages in the year range
from the OCR word patterns, archive the pages that carry the surname, and read
them; the OCR alone cannot find a name, so the pages must be looked at. The
same shape serves every New York marriage the tree is missing.

### C2. OCR / HTR extractor for record images

Turn an archived record image into personas and persona facts by machine,
versioned by extractor, beside the person screen's transcription form.

### C3. Place-string review from the catalog

The Undecided place strings and their `place_resolution` proposals have no
decision path. Decide them on the person screen as a question about the
person whose facts use the string, never as a standalone place queue.

### C4. Focus views on the tree overview

When a tree overview exists, let the user hide or highlight parts of it with
saved, hotkey-switchable views: hide the siblings they do not care about on a
line, keep one child of a large family, dim everything outside the line being
worked. A view changes only what is shown, never the data. Needs a tree
overview first.

### C5. Name variants in the matcher

The matcher compares the first given name exactly (one-letter initials
aside) and the surname as written, so a mother recorded under her married
name on a census (Ruth Davidson) does not fit the tree's Ruth M Peters even
when the record's relationship agrees, and Annie M Lukens does not fit Anna
Marie Bolton. Give the given-name comparison the alias table's variants and
let a married surname fit a birth surname when the relationship agrees, so
the proposal names the person the tree already has. Build it on the first
fetched page where the matcher actually misses. Nothing here changes what a
person decides.

### C6. A household cemetery row reads held through a relative's memorial

The cemetery / family plot row is a Group A household row, so it reads held
for a person as soon as any relative's memorial is held, and the person never
gets a cemetery search step of their own (Ruth M Peters reads held through
her husband's and her son's memorials and is on neither). A memorial is about
one person. Decide whether the row stays a household row with a per-person
"own memorial" state, or splits into the plot (household) and the person's
memorial (individual).

### C7. Place resolution accepts more than a unique full match

The resolver auto-accepts a string on "preferred administrative boundary",
"dropped non-place candidates" and "US state name" as well as on a unique
full match and the nested or coterminous choices `schema/README.md` sanctions;
the live catalog holds 22 such acceptances beyond the sanctioned kinds.
Either narrow `tools/resolve_places.py` to the rule in `CLAUDE.md` (a unique
full match, and the sanctioned nested choices) and reset the rest to
Undecided with `--reset`, or amend the rule in the docs with the reason.

### C8. Repeated assertions of one statement

The catalog holds groups of identical assertions (same subject, same persona
fact, same record): the import writes one per citation when the file cites
the same record twice on one fact, and twelve rows written on 7 September
repeat a record's statement on one event. The current writers do not repeat a
statement. Decide whether a repeated citation from the file is one assertion
or one per citation, and fold the rest.

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
