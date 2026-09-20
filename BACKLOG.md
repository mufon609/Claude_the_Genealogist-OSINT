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

Items with ordering or coupling constraints. None open.

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

### C3. A results page closes a fetch step, and the cited record's own page then holds nothing

A FamilySearch results page saved for a fetch step's own search is logged
`found` on the step when a row fits the person (`tools/attach.py`), so the
step is done and the checklist row reads held on a listing of 244 records,
though a row on a results page is a hint and its own record is the
document (`docs/RESEARCH-WORKFLOW.md` §0, §4). The record page that then
arrives reaches nothing: `attach`'s identity path logs a record on a done
step, but the fallback by collection and name takes planned steps only, so
the church-register pages HHGB-BQW2 and HHGB-BQZM in `inbox/` come back "no
fetch step in this tree cites this record" while the seven steps citing
their collection stand done on the results page of 18 Sept 2026 (Abraham B
Brant, Abram C Brant, Allen Brant, Alicia Ahern and others, run
2026-09-18T22:56:26Z). Decide the shape: a fitting row on a results page
leaves the fetch step planned and puts the row's own record (its ark, from
the row's persona) on the fetch list as the page to save next, the step
closing only when a record page holds it; or the fallback reaches a done
step whose found run holds only a results listing. Either way a record page
is never left unheld by the listing that pointed at it.

### C4. The page-saves-itself script captures nothing on a site that renders through shadow roots

`tools/save_page.js` clones `document.documentElement` and hands the clone
to the browser as a download; an element's shadow root attached by script
is not cloned, so on a site that renders its page inside such roots the
file holds only the site's no-script fallback. Seen on archive.org on
19 Sept 2026: the two pages a paused turn listed for Carol Evers came back
as 843 and 1,885 bytes, the body reading "Javascript is required for this
site", and the session rightly left them out of `inbox/`. Have the script
serialise every open shadow root it finds into the clone as declarative
shadow DOM (`<template shadowrootmode="open">` with the root's markup, in
the place of the host's children), so the saved page is what the browser
showed; the byte count and the markers it returns must still be checked
before the tab is closed, as §4 says. Until then a page from such a site
cannot be saved by this method.

### C6. Rule paths the harness no longer exercises, for want of a real record

When the harness became data (no invented test data, no names in the
harness code), every scenario that only a planted person or a made-up
record could carry was dropped rather than faked. Each is a path the code
still has and nothing now tests: an in-law resolving to a real link
through the relative it names; the spouse fit where the other party
carries another name; the fitting check on garbled initials and on a
short-form given name; a results row outliving its own record; a
namesake's kin shown as a hint; the SAR page at a holder without a parser
and its two-entry listing; the found halves of the runner's listing run
and of the results page saved for a fetch step; a step runnable again once
the plan writes the field a connector wanted; the dated-row half of the
unnamed fetch; the merge's reach by name and year. When a real document
that carries one of these is archived (the owner's own, saved by the
page-saves-itself method or a connector's answer), add it under
`tests/fixtures/` with its sidecar, write the scenario as data under
`tests/fixtures/scenarios/`, one per path, and strike it here.

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

### C10. Accepted links that pile up on a re-read

Every re-read of a page carries the decided links to its new personas and
leaves the earlier personas' accepted `person_persona` rows in place, so a
person read three times has three accepted links on one record. Evidence
rows are immutable, so the old personas stay; the link rows are decisions and
could be set aside (status `superseded`, or the earlier persona's link
withdrawn) when the new one is written, so counts of accepted links on a
record say what a person would say. Decide the shape, then apply it to the
live catalog's re-read pages.

### C11. A place written one letter apart disagrees

Frederick Michael Ahearn's card on his WWII draft registration card
(FamilySearch, ark `Q2SN-6M4R`, cited by the file) agrees on the name and the
birth day and disagrees on the birth place: the record writes "North Hampton,
Massachusetts", the tree has Northampton, Hampshire County, resolved and
accepted. `tools/catalog.py`'s `place_verdict` (which `tools/match.py` uses) counts two places the same when
both resolve to one place or one is a dated name of the other
(`docs/DATA-ARCHITECTURE.md` §8), and "North Hampton, Massachusetts" is an
unresolved string, so the disagreement stands and the rule leaves the record
a card. A surname has a rule (as written or a spelling variant,
`docs/RESEARCH-WORKFLOW.md` §5–7); a place has none, and §8's `typo` and
`transcription` kinds are classified only once a string is resolved. Decide
the rule in the docs: whether a string one letter (a space) apart from a
resolved place's name, in the same state and county where the string gives
them, agrees as a spelling variant, and whether the resolver offers the
resolved place as such a string's candidate on the same ground; then the
matcher applies it. Until then such a record is a card.

### C12. A fetch step's place field carries the citation's one string

`tools/plan.py`'s `citation_fields` writes a fetch step's place as the
citation's own text under the citation's label (`census place`: "Caln,
Chester, Pennsylvania"), one string, basis `citation`; a search step's
`place` is every accurate name of the place (`checklist.PLACES`: the name
valid at the record's date, as written, current, every other dated name,
`docs/RESEARCH-WORKFLOW.md` §3), and `run_step.run_connector` tries them one
at a time under `place` alone. A fetch step is asked under the one spelling,
and the prefilled FamilySearch search on the fetch list carries the same one.
Give a fetch step's place the same list, the citation's own string first,
under the field the citation labels it, and have the runner's name-by-name
try read `census place` as it reads `place`. Harness: a fetch step whose
citation's place has a dated name, the connector asked once per name until a
hit.

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

### C14. A memorial's listed relatives are counted as documents waiting

Over a hundred undecided cards propose a persona a Find a Grave memorial
lists as a relative of its subject (siblings most, then parents, children,
spouses and half siblings; persona matches and new people both), on confirmed
people and on the file's others alike: John Y Davidson, Robert Edgar Davidson
and Lena Howard Bell carry several each. `Catalog.waiting` counts every
undecided persona match or new person as a document to decide, so
`tools/tree.py overview` and `tools/queue.py` show them as documents waiting
and name the person next on them. The rule can never take such a card: a
listed relative carries a name, years and a link to their own memorial, never
the three to-the-day agreements the identity rule wants
(`docs/RESEARCH-WORKFLOW.md` §0), and accepting one by hand writes an identity
link and nothing more, since a page anyone can edit builds no facts. The
owner's word is that a memorial's family connections are leads to look over,
not facts. Make each one a lead: a fetch step for the relative's own memorial
under that relative's cemetery row, the card coming from that page once it is
fetched; and count them apart from documents to decide on the overview and in
the queue, so nobody is named next on cards nobody can take.

### C15. A record whose two personas each wait on the other

Carol Evers's card on the 1950 schedule the owner cited on their own word
(`tools/cite.py`: the Evers household at East Northport, the page read by the
model) proposes Evers, Carol Ann, daughter, as her on the name and sex alone;
her only stated relationship is to Evers, John, the head, who is nobody in
the tree. The rule does not take her: no accepted fact of hers agrees, and a
stated relationship counts a point only when the relative's persona fits
someone in the tree (`CLAUDE.md` rule 3). John Evers gets no card: a persona
is proposed as a new person only through a stated relationship to a persona
already accepted on the record, and none is. Each waits on the other, and the
record stays the owner's click though the owner's own citation says whose
household it is. Decide what seats the first persona on a record fetched on
the owner's word: the owner's citation as the ground that persona lacks (a
vouch, recorded as their word), the household then read outward from her
through its stated relationships as any accepted record is; or the card stays
the owner's.

### C16. A merge carries the duplicate's events beside the kept person's own

`tools/conclude.py merge` moves the duplicate's event participations onto
the kept person as they are, so a duplicate whose Birth and Death the file
states with the kept person's own dates leaves the kept person with two
Birth events and two Death events of one date, and the plan opens a
`conflict` question "more than one birth event" between values that agree:
Thomas Ahearn [6FX2NF] after the merge of 18 Sept 2026 carries Birth 2 Oct
1846 twice (five assertions and one) and Death 21 Aug 1902 twice. When the
duplicate's event is of the same type as one of the kept person's and its
date agrees to the day (its place agreeing or absent), move its assertions
onto the kept event and leave the duplicate's event behind with the
duplicate's row, so a merge never opens a conflict between equal values; a
differing value stays a second event and a real conflict, as now.

### C18. A merge leaves the kept person in two families with the same partner

The file's duplicate entry had its own family with the same partner (Alice
McGee, child Patrick Ahearn); the merge moves the membership across, so the
kept Thomas Ahearn is a partner of Alice McGee in two families, the
checklist lists her twice under spouses, and the plan carries every
marriage citation twice, the second step keyed `:2`. When, after the
merge, the duplicate's family has exactly the partners the kept person's
family has, fold it: the children's memberships and the family's events
and assertions move to the kept family, the emptied family row stays with
the duplicate for the audit trail, and the audit row names what moved.

### C19. The person screen has no living line and no control to confirm it

The living status is the tier from the home person
(`docs/DATA-ARCHITECTURE.md` §7): a person in the grandparents' generation
is unknown until the owner confirms them, and `tools/checklist.py` prints
the line ("living: unknown, confirm with tools/conclude.py living"). The
person screen's foundation shows the seven key facts only, so the owner
never meets the question on the one screen where they decide. Show the
living line in the foundation with its reason, and on an unknown person
the two-way control (living, deceased) that writes `person.living_override`
through `conclude.living` with one audit row, as the fact rows write their
decisions.

### C20. A record's undated event fact creates a second event beside the person's dated one

Accepting a death index page whose Death fact carries no date writes a
second Death event on the person: `conclude.decide` creates an event from
the record's date when the person has none of that type and year, and an
undated fact has no year to match. The new event's accepted statement then
outranks the file's dated claim, so the key fact reads accepted with no
date until that statement is rejected by hand. When a record's fact of a
type carries no date and the person has exactly one event of that type,
the statement asserts that event; with more than one, the difference is a
conflict question on the card, never a new undated event.

### C2. A birth page's parents are written twice

`tools/extract.py`'s FamilySearch record reader writes a parent once from the
page's fields (Father's Name, Mother's Name: a persona with the name and the
parent relation, no sex, the field's Father's Sex left as an Unknown fact on
the child) and once more from the relatives table (Parents and Siblings: a
persona with the name, sex and the same relation), when a page carries both,
as `tests/fixtures/familysearch-pennsylvania-and-new-jersey-church-and-t-1909-HHGB-BQ3Z.html`
does: five personas for three people, and the matcher proposes each parent
twice, two cards for one decision. The Massachusetts birth fixture carries
the table alone and reads clean. One persona per named person on a page: the
table's row, which carries the sex, with the field's statement on it.

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
