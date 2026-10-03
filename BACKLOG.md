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

### A1. The FamilySearch pages read again and the rule reconsidered, live

`tools/extract.py --stale` reads every FamilySearch page again at
`rule:familysearch-record@0.7.0`, then `tools/conclude.py reconsider` examines
the rule's decisions on those readings; the rehearsal on a scratch copy lists
what it takes back and what it takes.
**Blocks:** running `tools/conclude.py reconsider`, `tools/turn.py` or
`tools/turns.py` on the live catalog, until that list is reviewed and the run
made live.

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
Howard Bell, died 1918; John Y Davidson, whose one Birth holds the file's
24 April 1876 against the 1900 census's Apr 1875.

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
short-form given name; the matcher's window on a birth year
(`match.WINDOW`: a persona born more than three years from a candidate of
the same name is never a near match, which only a results page's rows
carried, and no row is a card now: the 1900 Lukens household, Annie against
her mother, needs the parents in the harness cut); a namesake's kin shown as a
hint; the SAR page at a holder without a parser
and its two-entry listing; the New Jersey death index's birth or death with no
month or day (`extract.nj_date` keeps the year alone), which no row of the
2006-2017 file has, every one of its 837,351 rows carrying both dates whole; the
unnamed fetch's own naming
(`fetches.save_as`'s holder-and-piece-and-six branch), now that the two
citations that carried it (the New Jersey and New York marriage indexes) are
both blocked as `scanned_index` holders; the merge's reach by name and year;
a memorial's listed relative whose one fit moves to another person between two
acceptances (`conclude.link_family` withdraws the earlier undecided trace); a
merge folding a family whose child the kept family already holds, and a merge
completed (`conclude.complete_merge`) folding two same-partner families; the
0.7.5 migration restoring a row an older decision wrote over (a page naming one
person twice, each persona decided, which no current parser writes); the import
folding a person's own repeated facts, and taking a fuller date onto an event a
coarser fact began (the cut holds only the Ahearn couple's repeated 1901
marriage, the couple's own first; Catharine Rittenhouse's births of 12 and
13 January 1772 and Abraham Wiegner Heebner's two of 28 Dec 1766 lie outside
it); a family fact equally close to two of the couple's events, raised by
`Catalog.unplaced` and placed on a family's event by `conclude.place` (no
record of the Ahearn marriage fits both its events); an attribute's fact among
several of the person's attributes of its value; the sibling route (a sibling
the record itself states, of a person accepted on it, taken where the tree
holds no parents), now that FamilySearch's readings mark every sibling their
own grouping; the note a decision writes when it does not place a sibling
beside a parent who died before the birth (only a re-read carries such a
placement in the harness, and a re-read writes no note); a reading the reader
says is of an index read derivative where neither its collection nor its
registry row says so (the tree's one index image is filed under the New York
marriage index, whose own row says derivative); and a death or burial place
point standing on a statement at the tree's own level, the harness's places
being unresolved strings. When a real document
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

`Catalog.unplaced` raises an accepted record's fact whose event is the owner's
choice (an undated fact among several events of its type, a dated one equally
close to two or more, one of a type a life holds once that fits none of
several) as a conflict question, and only `tools/conclude.py place` answers it. Show the question on the person screen
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
checks green, a file per commit.

### C15. A family's own facts in the file lose their place

`tools/ingest_gedcom.py` writes a FAM record's own MARR (or DIV, ENGA, ...) as
an event whose statement carries no persona fact, a family being no persona:
its date stands only as the event's own value, and its PLAC becomes a place
string nothing points to, so the file's place for the couple's marriage is
lost (the Ahearn couple's own 26 Jun 1901 at Northampton reads placeless), is
never compared by `Catalog.disagreements` and never resolved, and the fold
reads it as absent, joining any marriage of its year. Write the FAM record's
facts as persona facts (on each partner's persona, as an Ancestry INDI-level
MARR already is), so the file's date and place are statements like any other.

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

### C24. A FamilySearch household page saved with every member's details open

A census states every member's relationship to the head, but a FamilySearch
record page shows that column only in each member's own details table, which
the page keeps closed until its "Open All" button is pressed. Of the twelve
census pages in the archive, one (the 1900 Lukens household) was saved with
every member's details open; on the rest the column shows for the page's own
person and the head alone, so every other member's relationship to the head is
read only as FamilySearch's grouping (computed), and the rule takes no one
through it. Have `tools/save_page.js` press the page's "Open All" buttons on an
`fs-record` page and wait for the details tables before it saves (confirm on a
real page that the details render without a request the method does not make),
then save the archived census pages again by the same method.

### C25. The proof summary's per-conflict reasoning and question ids

`tools/proof.py` computes "the classes favour X over Y" once per fact and
prints it under every conflict of that fact, so a conflict reads a preference
between values it does not hold (Noi Davidson's Morioka against Tokushima reads
"favour Morioka over Ogau Tonan"), and "favour" there means secondary over
indeterminable, not the rule's "without doubt". No read-only tool prints a
conflict's question id, which `tools/conclude.py resolve` needs. Compute the
line per conflict from the statements on each side and print the question id
beside each open conflict.

### C26. Two FamilySearch rows the record states, worded as the site's own

Two kinds of relatives-table row stay computed though the record states the
relationship behind them, because the page shows FamilySearch's word and not
the record's; reading them as stated is the owner's choice. On a census page
whose own person is the head, each row (Wife, Son, Mother) restates that
member's relationship to the head, but the page does not show the column, and
FamilySearch's table is its own working-out (the 1950 Hahnle page leaves the
head's wife's row blank, the 1920 Ahearn page two sons'). On a page whose own
person is a parent of the record's subject ("Mentioned in the Record of"), the
other parent the record names is filed as her husband (Kentucky Deaths, Lena
Howard Bell's page of her son Ollie's death: "John Y. Davidson, Husband"), as a
marriage's bride's parents are filed as the groom's in-laws, which the reader
already reads as hers. If the owner takes either, the reader writes the head's
row as the member's stated relationship to him, and the husband as the
subject's stated parent, the husband row staying computed.

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

### C31. A results row no longer has a card to close

The matcher proposes no row of a results page (`tools/match.py`), so a row's
card never sits open beside the record it summarizes, and
`conclude.close_result_rows` finds nothing: remove it with its call in
`decide`, its sweep and `row` kind in `reconsider`, the `row` branch of
`tools/turn.py`'s report and the `closed_rows` line of `tools/conclude.py`'s
command line.

### C32. The runner asks the same request once for every name of a place

`run_step.run_connector` tries each name of a place field in turn and stops at
the first that gets a hit, but a connector reads a place only as a state and a
county (the 1950 census, Chronicling America), so two names of one place give
the identical request and the second is asked blind: a repeated request to a
rate-limited holder that cannot answer differently. Ask a name only when the
request it makes differs from every request already made on the run, and log
the names that made no new request as tried.

### C33. The harness's last two stand-ins

`docs/DATA-ARCHITECTURE.md` §7 decision 8 says every page the harness reads is
real, and two are not (`tests/fixtures/README.md`, "What is simulated"): the
smallest of JPEG files for a gravestone photograph and for the owner's
family-held photographs (`decisions/50-memorial`,
`decisions/95-cited-on-the-owners-word`), and a page of nothing but its
saved-from line for a cited obituary (`decisions/70-obituary-read-by-the-model`,
`decisions/97-proof-summary`, `loop/70-held-is-the-subject`). The archive holds
real ones to use: a Find a Grave gravestone photograph read by the model
(sha `7b2dd95d001a…`, photo 142698059, registry E05) and a Legacy.com obituary
page read by the model (sha `0ee95c3d0eba…`, H05). Re-target those scenarios
to the people those real pages are about, with their real readings, so no
stand-in page remains; the family-held photographs are marked private, and
whether one may sit in `tests/` is the owner's choice (hard rule 7).

### C34. An original names whose record it is

`data/evidence-classes.csv` names a record's original by its kind ("death
certificate", "birth register", "obituary"), with the year only where the
name carries one, so the standing rule's one-original test (`conclude.ground`)
reads two different documents of one kind on the same person's event as one
original: a parent's birthplace on a child's birth register beside the
parent's own birth register, two obituaries of one person in two papers. The
test errs toward the owner (a statement left out of a point, a card instead of
a decision), never toward a wrong decision. Name the original by the record's
own subject as well (the person whose death the certificate is), from the
reading's own persona roles, so only copies of one document count once.

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
