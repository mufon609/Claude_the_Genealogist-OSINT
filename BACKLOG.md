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

### C6. A page saved from a holder without a parser reaches its step

`tools/fetches.py list` prints a file name for every page it asks for, but
`collect` moves only memorial, FamilySearch and AAD names into `inbox/`, and
the attach reads an identity from those three page shapes alone; a surname
file from the Alabama archives, an SAR patriot page, a VA gravesite result or
a Legacy.com obituary saved under the name the list gave it stays in the
download folder, and dropped in the inbox it matches no step. Let `collect`
take every name the list printed and attach such a page to the step it was
saved for (the holder and the citation are in the name), archived under the
holder with the page's URL as locator, logged found, no extraction until a
parser claims the page; the person screen's attach already does this for the
step the person chose.

### C7. Hints on the person page

A run that found pages naming the person on the name alone (a directory
line, a book mention, a newspaper hit) leaves them held under the step, and
the personas it read stay on the page with no proposal, as
`docs/RESEARCH-WORKFLOW.md` §0 defines a hint. The person page shows them
only as records under the step's log. Show a reviewed person's hints as the
doc says: each with what agrees, what is missing and the page, for research
when the leads run dry, never as a feed.

### C8. A connector for the Pennsylvania Newspaper Archive

The archive at panewsarchive.psu.edu runs Open ONI and answers a declared
tool: a JSON page search (`/search/pages/results/?searchType=advanced&proxtext=…&date1=YYYY-MM-DD&date2=…&dateFilterType=range&format=json`,
each item with its page id, title, date, city, county and the page's OCR
text) and a page's text at `<page id>ocr.txt`; titles 1789–2013, few after
the 1920s (`data/DATA-SOURCES.md` §4). Its registry row (H03) is on every
obituary step's sources. Build the connector when an obituary step for a
Pennsylvania death exists on a reviewed person, so it is tested on a real
step: a hit's record is the page's OCR text, read as the loc.gov text is
(one persona per place the surname stands, a name and nothing else), which
needs the extractor to claim a plain-text response by the runner's notes.

### C10. Accepted links that pile up on a re-read

Every re-read of a page carries the decided links to its new personas and
leaves the earlier personas' accepted `person_persona` rows in place, so a
person read three times has three accepted links on one record. Evidence
rows are immutable, so the old personas stay; the link rows are decisions and
could be set aside (status `superseded`, or the earlier persona's link
withdrawn) when the new one is written, so counts of accepted links on a
record say what a person would say. Decide the shape, then apply it to the
live catalog's re-read pages.

### C12. The four Ancestry-only collections not yet looked for at a free holder

The point of the project is the records Ancestry charges for, found free.
Ancestry itself is skipped: no membership, no parser, no fetch. Of the
collections whose fetch steps are blocked, eight have a registry note saying
no free holder is known (the Pennsylvania certificates, the Lancaster
Mennonite and Presbyterian records, the Korean and Civil War draft records,
the Colorado voter file, the Alabama surname files). Four have not been looked
for yet: Massachusetts wills and probate 1635–1991 (dbid 9069), the
Pennsylvania veterans' burial cards 1777–2012 (dbid 1967), the cemetery and
funeral home collection (dbid 2190) and the Revolutionary War burial index
(dbid 63156). Look for each at FamilySearch first (its catalog and
collections, a free account, in the browser: the collection list answers a
tool with a challenge), then at the state archive or another free holder, and
add the row to `data/holders.csv` with the collection's own search URL shape;
where none exists, say so on the registry row.

### C13. A connector for Open Archives, the Dutch records

api.openarch.nl answers a declared tool with no key: `records/search.json`
by name and event place (each record's person name, event type, date and
place, source type, archive and identifier) and `records/show.json` for one
record in A2A shape, the persons with their roles (Dopeling, Vader, Moeder)
and the event (`data/DATA-SOURCES.md` §4). Its registry row (I07) is the
church row's source for a Netherlands-born person. Build the connector, with
an extractor for the A2A record (one persona per person with a relation to
the record's subject, the event as the fact), when such a person is reviewed
and the step exists, so it is tested on a real step.

### C14. A cited record's free connectors are never asked when its holder has none

A fetch step runs at its holder's connector alone (`tools/run_step.py`
`connectors_for`), so a record cited at a closed source whose first free
holder has no connector is a hand fetch even when the row's other sources
have one: an obituary cited at Newspapers.com points at Legacy.com, which
holds obituaries from 1999, and the Archive's newspapers connector on the same
row is never asked, though the citation carries the paper, the date and the
place it would search with. Let a fetch step run at every connector among its
holders and its row's sources, one log row each, as a search step does, with
the citation's paper, date and place as the fields; the page saved by hand
and a connector's answer stay runs of the same step.

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
