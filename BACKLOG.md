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

### A1. The rule's points on the proof standard's classes

`conclude.rule_accepts` counts points the way `docs/RESEARCH-WORKFLOW.md`
"The proof standard" says it must not: it doubles any date given to the day on
a trusted statement and any relationship the tree holds on trusted evidence,
whatever the information class (`conclude.py` near "counts double"); it never
reads a relationship's computed flag, so FamilySearch's own groupings are taken
as stated links; records copied from one original each count; the kinds it
trusts come from English words in collection titles (`IDENTIFYING`), not from
`data/evidence-classes.csv`; a record giving only a state or a county earns a
death-place or burial-place point; and a reading of an image by the model or a
person reads as an original whatever the image shows
(`catalog.evidence_classes`). Make the rule read its kinds and its points from
the classes table: double only on primary information or the owner's word, a
computed relationship one point and never a stated link, one original once, a
place point only at the level of the tree's own place, a reading taking the
class of what it read (`docs/DATA-ARCHITECTURE.md` §7 decision 9). Rehearse
`reconsider` on a scratch copy and list what it would take back before it runs
on the live catalog.

### A2. Identity is tested, not assumed

`docs/DATA-ARCHITECTURE.md` §7 decision 12. The matcher compares a persona only
with the person a record was fetched for, their family and the tree's unlinked
people; the rule never reads the matcher's "Also fits"; nothing tests a life's
limits; the check before the rule creates a person looks only at people with no
family link, by exact surname (`match.by_name_and_year`); the duplicate check
(`footprint.py`) runs only on a reviewed person and counts merged persons. Add
to the rule the three tests of decision 12, a pass beside
`Catalog.disagreements` raising an identity question (a new
`research_question.kind`, by migration) naming both records, the life limits as
data, the creation check over the whole tree with spelling variants, and the
duplicate check before review with merged persons excluded. Live cases to
test against: Joe Davidson, born 1925, linked undecided as a child of Lena
Howard Bell, died 1918; Ruth M Peters and John Y Davidson, each with two
accepted Birth events.
**Blocked by:** A1, which changes the same function.

### A3. One statement, one event

`conclude.assert_facts` and `assert_family_events` assert a dated record fact
on every event of its type in the year (`_of_year`), so one register entry is
accepted on three 1901 Marriage events of James Joseph Ahearn and Annie E
Scannell; and an accept whose date falls outside the year of the tree's own
event creates a second Birth (John Y Davidson's CAL 1875 beside 24 April
1876). The import writes one event per GEDCOM fact, so the file's own
duplicates (William Rittenhouse's nine marriages) arrive as events. Assert a
fact on one event (several that fit are the unplaced question, as an undated
fact is); fold, at import and by migration, a person's or a couple's events of
one type that agree on the year with places agreeing or absent, the way
`conclude.complete_merge` folds a merge's; and land a calculated or about date
on the person's one event of a type that occurs once in a life.

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
is missing. On the 1959 item (one item, brides and grooms together) the
search inside finds no block header (H540 matches nothing; the OCR carries
letters and digits one by one), so the block's pages cannot be found by
words. The codes run in order through the item, so the
step must find the block by the page order instead: a page's code read from
its image, the pages narrowed between two read, then the block's pages
fetched. The one New York marriage row open on a reviewed person (Raymond
Earl Davidson and Noi Davidson) carries no year to choose an item by. The
planner blocks every fetch step at a `scanned_index` holder
(`data/holders.csv`) by the holder's kind alone, whatever record it cites;
this page-locating step is what unblocks them, for the New York index and
for the New Jersey marriage index's own scanned-page years alike. The same
step serves every free index that exists only as scanned pages: the
Pennsylvania State Archives' death index 1906–1975 and birth index 1906–1910
(PDFs on pa.gov, no text layer; ten of the blocked Pennsylvania death steps
fall in its years) and Reclaim the Records' Massachusetts death, marriage and
birth indexes (PDFs whose text layer is empty).

### C2. A saved page carries its fetch-list entry in its own bytes

`tools/fetches.py collect` reads a saved page's identity from the bytes (the
saved-from line `tools/save_page.js` writes), never from its file name, since
Chrome may sanitize or de-duplicate the name the list printed
(`docs/RESEARCH-WORKFLOW.md` §4). A FamilySearch search page, or a record page
whose citation carries no ark of the holder's, then reaches its steps only by
inference: the page's collection against the citation's holder collection
and the name searched against the name the citation sits on
(`attach._steps_by_collection`, `_fetch_steps_searched`, `steps_pointed`, the
repeat path). That inference is where most of the loop's fixes have landed,
each real run surfacing a new case (a name ending in a suffix, two census
searches of one person, a results page with no rows). Have the save script
write a second comment beside the saved-from line, the list entry's own key
(the steps it serves), given when the script is run from the list, and have
collect reach those steps first, the steps the page's identity reaches beside
them; the inference stays for a file dropped into the inbox by hand
(`docs/DATA-ARCHITECTURE.md` §7 decision 10). Write §4 as the code lands.

### C3. A page no parser reads is logged found

`tools/attach.py`'s `attach` logs a run `found` before the page is parsed and
turns it to `none` only for a results listing whose rows fit nobody. A page at
a holder without a parser (the SAR Patriot Research System's "No matching
records found") is therefore `found` in `search_log` though it holds nothing
and closes no step. Decide the word for a run whose page nobody has read (a
`found` with a note that says unread, or an outcome of its own), so the log
says what a program can rely on, and apply it to the rows already logged so.

### C4. Confirm the shadow-root save on archive.org

`tools/save_page.js` serializes the page's open shadow roots as declarative
shadow DOM (`getHTML` with every open root) when its plain copy comes out
nearly empty, the way archive.org's pages do (the plain copy holds only the
site's "Javascript is required" fallback). No browser was connected when it
was written, so it is untested on the real site: in the next browser session,
save one archive.org page the fetch list names (`[any page: save_page.js with
true]`) and check its one line and the saved file's text. If the line still
says `EMPTY` (closed shadow roots, or content drawn in a canvas), make those
steps assisted with the page's own link and say so in
`docs/RESEARCH-WORKFLOW.md` §4.

### C5. The fetch list repeats one bare search form per person

A page at a holder whose pages carry no identity is listed once per citation
and person (`tools/fetches.py waiting`). Where the holder's link prefills
nothing, every entry is the same empty form: the SAR patriot search is listed
twenty times under one URL, each entry a page nobody can save as an answer
without typing the search by hand. Such a link is a search a person runs, not
a page to save: make the step assisted with the citation's fields as what to
look for, or list the form once with the people and fields it serves.

### C6. Rule paths the harness no longer exercises, for want of a real record

When the harness became data (no invented test data, no names in the
harness code), every scenario that only a planted person or a made-up
record could carry was dropped rather than faked. Each is a path the code
still has and nothing now tests: an in-law resolving to a real link
through the relative it names; the spouse fit where the other party
carries another name; the fitting check on garbled initials and on a
short-form given name; a results row outliving its own record; a
namesake's kin shown as a hint; the SAR page at a holder without a parser
and its two-entry listing; the found half of the runner's listing run; the
unnamed fetch's own naming
(`fetches.save_as`'s holder-and-piece-and-six branch), now that the two
citations that carried it (the New Jersey and New York marriage indexes) are
both blocked as `scanned_index` holders; the merge's reach by name and year;
a memorial's listed relative whose one fit moves to another person between two
acceptances (`conclude.link_family` withdraws the earlier undecided trace); a
merge folding a family whose child the kept family already holds, and a merge
completed (`conclude.complete_merge`) folding two same-partner families; the
0.7.5 migration restoring a row an older decision wrote over (a page naming one
person twice, each persona decided, which no current parser writes). When a real document
that carries one of these is archived (the owner's own, saved by the
page-saves-itself method or a connector's answer), add it under
`tests/fixtures/` with its sidecar, write the scenario as data under
`tests/fixtures/scenarios/`, one per path, and strike it here.

### C7. Hints on the person page

A run that found pages naming the person on the name alone (a directory
line, a book mention, a newspaper hit) leaves them held under the step, and
the personas it read stay on the page with no proposal, as
`docs/RESEARCH-WORKFLOW.md` §0 defines a hint. The record view marks each
such persona that is a hint for a reviewed person with what agrees and what
is missing (`cards.hints_on`), but only once that record is opened from the
step's log: the person page has no place where a reviewed person's hints
across all their held records are kept, as §0 says they are. Add one, each
hint with what agrees, what is missing and the page, for research when the
leads run dry, never as a feed.

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
The JSON search answers a declared tool (132 hits for Heebner 1900–1930;
226 titles, among them the Evening Public Ledger 1914–1942, the Reading Gazette
and Democrat 1850–78 and German-language papers; no Norristown or Pottstown
title); it has reset connections before, so a refusal makes the step assisted.

### C9. Tree isolation has no harness, and some readers ignore the tree

Every scenario builds one tree, so nothing shows a second tree over the same
archive ignoring the first one's decisions (`CLAUDE.md` hard rule 4).
`catalog.page_groups` reads `assertion` over every tree's citations, and
`extraction` and `persona` carry no tree: `extract.extract` supersedes the
current extraction of a page and rejects its undecided proposals whichever
tree they belong to, so a second tree reading a page the first holds would
reset the first tree's cards. Decide how a page held by two trees is read
(hard rule 4 says every import gets its own extraction; fetched pages are
shared evidence in `docs/DATA-ARCHITECTURE.md` §4a), write a scenario with
two trees and one archived page, decided in the first and undecided in the
second, and scope every reader that joins `person_persona`, `proposal` or
`search_plan` by artifact or persona to its tree.

### C10. The turn's report and the person screen do not show the rule's conflict decisions

`conclude.rule_conflicts` decides a conflict the evidence classes settle and
writes its reason on the question and in the audit log, and `tools/proof.py`
prints it; `tools/turn.py`'s report and the person screen's decision summary
name neither the decision nor its reason, so the owner meets it only in the
proof summary. Name each one where the rule's other decisions are named, with
`tools/conclude.py reopen` beside it.

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

### C12. The person screen has no control for a record's unplaced fact

`Catalog.unplaced` raises an accepted record's undated fact, on a person with
several events of its type, as a conflict question, and only
`tools/conclude.py place` answers it. Show the question on the person screen
with the person's events of that type to choose from, writing through
`conclude.place` with its audit row, as the living line's control writes
through `conclude.living`.

### C13. A connector for Open Archives, the Dutch records

api.openarch.nl answers a declared tool with no key: `records/search.json`
by name and event place (each record's person name, event type, date and
place, source type, archive and identifier) and `records/show.json` for one
record in A2A shape, the persons with their roles (Dopeling, Vader, Moeder)
and the event (`data/DATA-SOURCES.md` §4). Its registry row (I07) is the
church row's source for a Netherlands-born person. Build the connector, with
an extractor for the A2A record (one persona per person with a relation to
the record's subject, the event as the fact), when such a person is reviewed
and the step exists, so it is tested on a real step. The API answers a
declared tool (70 records for Sijtske Lieuwes, 6 for Rittinghuysen at
Amsterdam) and has had outages: an unanswered request is an error run, asked
again next turn.

### C14. The decision code is hard to review

`tools/conclude.py`, `tools/cards.py` and `tools/match.py` hold lines up to
about 400 characters, statements chained by semicolons (262 lines over 160
characters in `conclude.py`, 1,208 across the tools), and functions up to 225 lines
(`checklist.build`, `conclude.rule_accepts`, `cards.card`), where a defect in
a write hides in the middle of a line. Reformat them one
statement per line at a width a review can read, behaviour unchanged and the
checks green, a file per commit, once the rule's points on the proof
standard's classes (section A) have landed, so the two do not collide.

### C16. A connector for the New York State death index

Reclaim the Records' New York State death index 1880–1971 (outside New York
City) is a CSV per year or five years on the Internet Archive (year, Soundex,
last, first, middle initial, residence, place of death as a code, age, date,
state file number), Soundex-ordered, public domain (`data/data-sources.csv`
C08). It answers a death row for the Nassau and Suffolk people the plan has
no free holder for. Build it as the New Jersey and Kentucky death-index
connectors are built: the year's file read once through the runner and
cached, the surname's rows kept as the derivative, one persona per row; the
place codes need their own table from the release's documentation before a
place is read.

### C17. One connector for CONTENTdm collections

The Tennessee Virtual Archive (death certificates, marriages, births), Ohio
Memory and the Alabama archives (L04) all run CONTENTdm, whose JSON search
(`/digital/api/search/collection/<alias>/searchterm/<term>/...`) answers a
declared tool. Tennessee's death certificates are titled by certificate number,
reached by name only through annual index volumes (1950–1974 found), so the
step is two hops: the index volume for the name, then the certificate by
number. Build one connector for the shape when a reviewed person's
Tennessee or Ohio step needs it.

### C18. A year-filed index read by byte range, and asked with the event's year

The Kentucky indexes (and the New Jersey one) are one sorted file per year,
3 to 11 MB, and the Archive serves byte ranges: a binary search by surname
finds a name in about a dozen small requests where the connector now reads the
whole year's file, because the runner sends no Range header and a connector
opens no connection of its own. Give the runner a ranged request (a probe that
is not a hit) and let these connectors search by range. Beside it: a fetch
step citing such an index carries no year (a citation's own details only), so
the connector logs none and FamilySearch stays the cited record's first
holder (`data/holders.csv`). Such an index takes the year of the person's
accepted event of that type (`docs/DATA-ARCHITECTURE.md` §7 decision 11): put
it first for those citations.

### C19. Reasonably exhaustive data for every place a family names

`data/jurisdictions.csv` holds the places this tree's research has needed:
seven states' statewide registration, two states' censuses, five countries'
church holders and civil registration. Any other place gets its rows with no
holder. Fill the table for every US state (statewide birth, death and marriage
registration years, state censuses, the holders that index them) and for the
countries emigrants came from, from the FamilySearch Research Wiki and the
state archives, each row citing where its years come from, with a registry
row for each new holder; then a family from anywhere gets a full checklist.

### C20. Place overrides belong to the tree

`data/place-overrides.json` holds this tree's own strings (the Berthelsdorf
review, the Silesian notes) in a file every tree reads. Read a tree's own
overrides from `trees/<slug>/` beside a shared file of corrections true for
any tree (a place string meaning no place), and move this tree's entries
there; the place scenarios plant their own.

### C21. Citations from exports other than Ancestry's

The planner turns a citation into a fetch step through Ancestry's own record
id (`_APID`) and `data/holders.csv`'s map of Ancestry collections to free
holders. A GEDCOM exported from FamilySearch, MyHeritage, Gramps or by hand
cites its sources otherwise: `ingest_gedcom.py` keeps a citation's record id
and URL only when it carries an `_APID`, so its citations make no fetch steps,
build no footprint, and the checklist reads a record the file cites as missing. Read the citation forms those exports write (a
FamilySearch ark in a citation, a URL, a source title with a page), and route
each to its holder.

### C22. A second family in the harness

The harness runs on a cut of the owner's export, by the owner's ruling (no
invented people or records), so nothing proves the tools on a family with
other places, other denominations and another export's citations. With the
owner's choice of a real second tree (another family's export they hold, or a
published public-domain one), add a scenario that ingests it beside the
harness tree, builds its checklists and plans, and shows nothing of the first
family reaching the second (the tree-isolation entry above).

### C23. reconsider settles over several runs

On the live catalog `tools/conclude.py reconsider` reaches its fixed point
only on its third run: its card pass takes cards on ground the next run's
re-examination (each decision on the ground that stood before it) refuses,
such as the relatives an obituary names accepted through one another. Make
the card pass judge a card on the ground before it the way the re-examination
does, so one run is the fixed point; until then the live run repeats
reconsider until a run changes nothing.

### C24. Places the resolver could settle

Of 1,858 undecided place strings 1,747 have no card, and no turn runs
`tools/resolve_places.py`, so a conflict waiting on a place's words (Noi
Davidson's death place "NJ") never closes. The resolver knows 15 state
abbreviations (`US_ABBR`) where `catalog.py` knows 50 and none of Mass, Penna,
Mich; one place is carded once per spelling ("Worcester, Montgomery County,
Pennsylvania" nine times); a string naming no place ("Same House") is carded.
One abbreviation table for both; one card per candidate set, deciding every
string it covers; the resolver in the turn's tail after the rule, through its
cache and the public endpoint's rate.

### C25. The proof summary's per-conflict reasoning and question ids

`tools/proof.py` computes "the classes favour X over Y" once per fact and
prints it under every conflict of that fact, so a conflict reads a preference
between values it does not hold (Noi Davidson's Morioka against Tokushima reads
"favour Morioka over Ogau Tonan"), and "favour" there means secondary over
indeterminable, not the rule's "without doubt". No read-only tool prints a
conflict's question id, which `tools/conclude.py resolve` needs. Compute the
line per conflict from the statements on each side and print the question id
beside each open conflict.

### C26. A model's reading records what read it

`docs/DATA-ARCHITECTURE.md` §1 asks for the model name, version and prompt
hash on every AI extraction. The screen's transcription path takes the model
name the session types, leaves the version empty, hashes the form's field
names as the "prompt" (the same for every model), keeps no region for most
model-read persons, and passes the screen's default identity rather than the
reader's to the matcher (`app/person/server.py` `transcribe`, the
`match_record` call). Record the model id and version the session states, the
hash of the instruction text actually given, a line or region per persona
(refused without one), and the reader as the actor of every write the reading
makes.

### C27. An import from anywhere is read as itself

Beyond citations: the gazetteer routing for Ireland, Germany and Poland, the
Silesian place rules and the church denominations are written in code
(`resolve_places.py`, `catalog.py`, `checklist.py`, `footprint.py`). Read the
routing and the denominations from data, as `data/jurisdictions.csv` already
carries which records exist where. And an unresolved place string that names a
US state anywhere in it is read as American even when its last part names
another country ("Washington, Tyne and Wear, England": `Catalog.place`): read
the country the string ends with first.

### C28. Cards the evidence has passed by

27 undecided cards sit on superseded readings (some duplicate a newer card on
the same persona), and a card is never matched again when the person's evidence
changes, so Robert Edgar Davidson's WikiTree namesakes, which now disagree on
both dates, are still cards, their rationale saying the death date is absent.
Reject a card on a superseded reading as superseded when the current reading
holds the same person (by the persona's key on its page); match a person's
undecided cards again whenever a decision changes that person's evidence, and
let a card that has become a hint leave.

### C29. One home for each shared rule, and no dead schema

Soundex is written three times (`catalog.py`, `backfill_aliases.py`,
`footprint.py`), edit distance twice, name splitting three times, the
nickname table twice, the suffix set twice; `initdb.py` re-implements `ulid`
without the monotonic rule `treelib.py` promises; `turns.name_of` is dead.
The `derivative` and `artifact_page` tables are never used, the three FTS
tables are filled and never queried, and no tool writes `tombstone` although
hard rule 2 relies on it. `backfill_aliases.py` takes `--by` and ignores it.
Keep each rule in `catalog.py`, drop what nothing reads (or give it its
reader), and make `tombstone` the one way a removal is written.

### C30. A tool run without --db opens the live catalog

Every tool defaults `--db` to the repository's `catalog/tree.db`, not to
`DATA_ROOT`'s, so a scratch run that sets `DATA_ROOT` and forgets `--db`
writes the owner's catalog. Default `--db` to `DATA_ROOT/catalog/tree.db`
(one constant in `treelib.py`) so a scratch run is scratch throughout.

## Externally blocked

Waiting on events the repo cannot drive.

- **NARA Catalog API key** — issued by email on request.
- **Pennsylvania death and birth certificates' images** — only on Ancestry
  (free with a Pennsylvania address through its portal), so the steps for
  dbids 5164 and 60484 stay `blocked` for the certificate itself; the State
  Archives' own indexes are free as scanned pages (the scanned-index entry
  above). Add the row to `data/holders.csv` when the images reach a free
  holder.
- **API keys the owner would request** — DPLA, Europeana and the Google Books
  API answer only with a key (`data/data-sources.csv` M02, M03, L05); each is
  low yield for this tree, so none is wanted until a step needs it.
