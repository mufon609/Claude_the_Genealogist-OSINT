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

### A1. The turn runner

Three tools the loop (`docs/RESEARCH-WORKFLOW.md` §8) needs and does not yet
have: a turn runner driving one person's plan end to end (fetches, assisted
saves, auto searches, the standing rule's decisions, the people it creates,
the plan regenerated); a queue reading the edge of the confirmed tree from
`tools/tree.py overview`, the home person's line first, then everyone a
record names after; and a way to resume a turn a challenge paused. Blocking
nothing yet.

---

## B. Parallel batch

### B1. Exporters

GEDCOM 7 (with GEDZIP of redistributable media) and Gramps XML, both from
the conclusions layer, honouring the living-person redaction. Ship together
so a tree can be round-tripped and opened in Gramps desktop.

The stored `artifact.redistributable` flag on artifacts archived before
13 Sept 2026 stays as written, false, whatever the registry's terms for
that source say now: artifact rows are insert-only, so that column is
never revisited after the fact. Read the registry's terms at export time
instead of trusting the stored flag on an old row — the same thing
`tools/treelib.py`'s `archive_object` now does at archive time.

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
is missing. Probed 11 September 2026 on the 1959 item (one item, brides and
grooms together): the search inside finds no block header (H540 matches
nothing; the OCR carries letters and digits one by one), so the block's pages
cannot be found by words. The codes run in order through the item, so the
step must find the block by the page order instead: a page's code read from
its image, the pages narrowed between two read, then the block's pages
fetched. The one New York marriage row open on a reviewed person (Raymond
Earl Davidson and Noi Davidson) carries no year to choose an item by.

### C2. A household record found through a search step marks only one member's step done

A page fetched through a search step, not a cited fetch, carries no identity
`tools/attach.py` can key against every household member's own row: a
FamilySearch record page saved from a name search
(`familysearch-record-1950-census-6XYS-NQ16.html`, archived with
`locator_kind='file'`, no ark learned before archiving) is not named in any
`search_log.artifacts_json`. Extraction and match ran directly on the file,
and three of its personas are accepted onto their own persons: Frederick
Micheal Ahearn Jr (son), Frederick Michael Ahearn (father), Helen Sara Brant
(mother). Frederick Micheal Ahearn Jr's own `census household:1950` row reads
`held` (his own step reached `done` some other way); the other two still read
`missing`, `mode auto` (`D05`, `D03`), because `catalog.fetched_rows` marks a
row held only through a `done` step on that person's own plan, and neither
father's nor mother's 1950 step ever received a found log for this artifact.
`tools/run_step.py --all` would search the NARA 1950 site again for a
household this tree has already read. The NARA 1950 connector already logs
found on every household member's own step from one page
(`docs/RESEARCH-WORKFLOW.md` §4); a household record arriving through
`tools/attach.py` instead (a saved search-results page, not a connector
answer) needs the same reach, from the record's own accepted personas to each
one's matching census-year step, once each is decided.

### C4. A record page saved for a church-register fetch step attaches to nothing

`tools/fetches.py list` sends a church-register citation (Ancestry's
Pennsylvania and New Jersey Church and Town Records, dbid 2451, cited on
seven people for Helen Sara Brant's 1909 birth) to its free holder's
collection (`data/holders.csv`: FamilySearch, Pennsylvania Births and
Christenings, 1709-1950), and the record page saved there
(`familysearch-pennsylvania-and-new-jersey-church-and-t-1909-HHGB-BQ3Z.html`)
comes back "no fetch step in this tree cites this record": `tools/attach.py`'s
`_steps_by_kind` reads the page's own event type (Birth) into the birth
record row and has no row for a church register, so the seven `church
register` steps citing the page's own collection at its own holder are never
reached. The fallback should reach every planned fetch step whose citation's
holder collection is the page's (`_matches_collection`) and whose name is the
page's principal, whatever checklist row the citation sits under, the row's
kind narrowing only when the citation's collection is unknown.

### C5. One person's two citations of one collection share a saved page's name

`tools/fetches.py list` names a page at a holder whose pages carry no identity
the attach reads (an SAR patriot page, a Legacy.com obituary, a Google News
Archive issue) once per person waiting on it, the name ending in that person's
six characters, so two people's pages of one collection no longer collide. Two
citations of the same collection on one person still do: Wilhelmina Dewees's
two SAR applications, Noi Davidson's own obituary and the relative's obituary
her footprint step cites at the same holder, each pair printed under one name,
and a file saved under it reaches whichever entry `named_for` meets first. Give
the name a piece unique to the citation as well (the citation's own record
locator when it has one, else the step's key), so one person's several pages
of one collection are told apart too.

### C6. The harness names the owner's family

`tools/check.py` checks each fixture by a dedicated function
(`check_census_1940`, `check_memorial`, `check_fs_numident`, …) whose
assertions spell out that record's own personas, facts and relations in
Python lines, and `decisions()` walks the Ahearn and Davidson households by
name throughout. A second family's documents cannot be dropped in beside
these without editing the harness itself, and several tool docstrings
(`tools/extract.py`, `tools/match.py`) use the family's own names as their
worked examples. Keep each fixture's expected personas, facts and relations
as data beside the fixture (a JSON sidecar, on the fixture's own naming
pattern) with a generic comparison the harness runs over every fixture the
same way, `check.py` reading the data rather than asserting it inline; make
the docstring examples neutral (a placeholder household) so a tool's own
documentation does not depend on whose tree this is.

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
On 11 September 2026 the site served its robots page but reset the connection
on the search path to a declared tool (urllib and curl alike); confirm it
answers again before building, and if it keeps refusing, the step is assisted.

### C10. Accepted links that pile up on a re-read

Every re-read of a page carries the decided links to its new personas and
leaves the earlier personas' accepted `person_persona` rows in place, so a
person read three times has three accepted links on one record. Evidence
rows are immutable, so the old personas stay; the link rows are decisions and
could be set aside (status `superseded`, or the earlier persona's link
withdrawn) when the new one is written, so counts of accepted links on a
record say what a person would say. Decide the shape, then apply it to the
live catalog's re-read pages.

### C9. A question's key collides when two questions share a long prefix

`tools/plan.py`'s `q_key()` truncates a question's detail to 120 characters
before keying it, so two distinct conflicts on the same person collapse into
one `research_question` row when their text agrees for the first 120
characters and only then differs: Noi Davidson's New Jersey death index
citation is a long archive.org URL, and both her birthplace conflicts
("... against Find a Grave: Morioka against Tokushima" and "... against the
file: Morioka against Ogau Tonan...") share that URL as their first 120
characters, so only one of the two ever opens as a question; the plan keeps
whichever the regeneration writes last, closing gap_gone or overwriting the
other on the next run. Key on a hash of the full detail (or the full detail
itself, if the column allows it) instead of a truncated prefix, so two
questions that happen to start alike stay two rows.

### C13. A connector for Open Archives, the Dutch records

api.openarch.nl answers a declared tool with no key: `records/search.json`
by name and event place (each record's person name, event type, date and
place, source type, archive and identifier) and `records/show.json` for one
record in A2A shape, the persons with their roles (Dopeling, Vader, Moeder)
and the event (`data/DATA-SOURCES.md` §4). Its registry row (I07) is the
church row's source for a Netherlands-born person. Build the connector, with
an extractor for the A2A record (one persona per person with a relation to
the record's subject, the event as the fact), when such a person is reviewed
and the step exists, so it is tested on a real step. On 11 September 2026 the
endpoint did not answer a declared tool from this machine (the connection timed
out, twice); confirm it answers before building.

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
