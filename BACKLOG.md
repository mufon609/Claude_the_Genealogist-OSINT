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
York vital records (C08), read by the model. The Archive's search inside an
item finds no name in these pages (the OCR carries none), so
`tools/connectors/ia.py` cannot serve them as it serves books. Make it a
step: for a missing marriage row, locate the Soundex block's pages in the
year's item from the OCR word patterns (the block headers survive), fetch
those pages through the reader as the module already does, and read them by
eye or by the model. The same shape serves every New York marriage the tree
is missing.

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
worked. A view changes only what is shown, never the data. The overview
exists and carries a placeholder line for these options; the placeholder goes
when the first view ships.

### C5. Given-name variants from the alias table

The matcher takes a wife under her husband's surname, a short form the
common list knows (Willie, Charley), a one-letter slip, and every name a
record gives (a WikiTree profile's name at birth and current surname). It
still compares the first given name against the tree's exactly beyond those,
so Annie M Lukens does not fit Anna Marie Bolton. Give the given-name
comparison the alias table's variants for the person, so the proposal names
the person the tree already has. Build it on the first fetched page where the
matcher misses for this reason. Nothing here changes what a person decides.

### C6. A reader for the FamilySearch results page

The FamilySearch search step carries the site's record search prefilled, and
the results page saved in the browser comes in through `inbox/` with no
parser, so nothing becomes a candidate card. Read the saved results page as
the Find a Grave and enlistment results pages are read (`tools/extract.py`,
`tools/attach.py` identity and steps), one persona per row with the record's
own ark as its identity, audited on the candidate card; a row that fits is
fetched as the record pages already are. This is the largest reach gain that
needs no API approval.

### C7. Hints on the person page

A run that found pages naming the person on the name alone (a directory
line, a book mention, a newspaper hit) leaves them held under the step, and
the personas it read stay on the page with no proposal, as
`docs/RESEARCH-WORKFLOW.md` §0 defines a hint. The person page shows them
only as records under the step's log. Show a reviewed person's hints as the
doc says: each with what agrees, what is missing and the page, for research
when the leads run dry, never as a feed.

### C8. A test harness on the saved real pages

The parsers, the matcher and the decision writers have no tests; two crashes
found tonight (a memorial writer numbering members from a name it did not
define, the screen's fact decision calling a function it never imported)
would have been caught by running each parser on one saved real page and
each writer on a scratch catalog. Keep one saved page per parser under a
fixtures directory that the commit guard allows (public pages only, no
family-held file), and a script that runs every parser on its fixture, the
matcher on the result, and the tools on a scratch copy, so a session can say
"green" from one command.

### C9. Bring the live catalog to the current rules

Owner runs, once, in this order, for the code this file is committed with:
sync the registry and the event types, the rule's re-examination of its own
decisions, the place resolver reset and re-run, plans regenerated, then a
first watched run of the connectors. Every writing command takes `--by`;
a session running them for the owner passes `--by "agent:<session> for
user:<owner>"`:

```
python3 tools/initdb.py --sync-sources
python3 tools/initdb.py --sync-event-types
python3 tools/conclude.py reconsider --dry-run
python3 tools/conclude.py reconsider
python3 tools/resolve_places.py --reset
python3 tools/resolve_places.py
python3 tools/plan.py --all
python3 tools/run_step.py --all --dry-run
python3 tools/backup.py verify
```

### C10. Fold the repeated assertions one decision wrote

Two events carry the same statement of the same record several times over
(eight extra rows, all written by one rule decision on 7 September; the
writers no longer repeat a statement). Keep the first row of each group and
delete the rest, then run the checks:

```
DELETE FROM assertion WHERE id IN (SELECT a.id FROM assertion a JOIN assertion b
  ON b.subject_kind=a.subject_kind AND b.subject_id=a.subject_id AND b.persona_fact_id=a.persona_fact_id
  AND b.artifact_sha256=a.artifact_sha256 AND coalesce(b.notes,'')=coalesce(a.notes,'') AND b.id<a.id);
```

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
