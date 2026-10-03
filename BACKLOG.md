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

### C2. A page of a holder the script knows by no markup is taken by its key

`tools/fetches.py collect` takes a page at a holder whose pages carry no
identity the attach reads (a Legacy.com obituary, saved
with `true`) by the file name the list printed, so a name Chrome sanitized or
de-duplicated leaves the page in the download folder, though its bytes carry
the saved-from line and the key `tools/save_page.js` wrote (the plan steps it
was saved for). Have collect take such a page by its key as well: the named
steps (`attach.named_steps`, which has no identity to contradict them),
archived under their holder with the page's own URL as locator, as the
by-name path does. The test needs a real page of such a holder saved by the
script with its key; none is archived (the pages of those holders so far came
through connectors).

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

### C5. A relationship point stands on either membership of the family

`conclude.rule_points` grounds a stated relationship on the accepted statements
of either membership joining the two people (`ground` over both rows), so one
person's link stands in for the other's: Joe Davidson, whom the file alone
places as Lena Howard Bell's child and who was born seven years after her
death, takes "sibling Robert Edgar Davidson" on his brother's obituary from
Robert's own accepted child row, and a parent's accepted marriage grounds a
child's claimed parentage. `docs/RESEARCH-WORKFLOW.md` ("What the rule counts")
says a point rests on the tree's statement of that very link. Requiring both
rows withdraws decisions that are sound, because the tree states a couple's
parentage partly on partner rows: Francis Thomas Ahearn's 1904 birth record
(his own card, his father's and his mother's), Dan Davidson on his mother's
obituary, and Mary Castello, created as the bride's mother from the 1901
marriage index, whose partner row carries that parentage. Ground a link on both
memberships, and count a record that names both parents of a child against the
tree's accepted couple as that couple, so those stay taken; show both on
the Ahearn and Davidson records above.

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
hint; the New Jersey death index's birth or death with no
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
being unresolved strings; the rule's identity tests (`conclude.identity_refused`)
refusing a record it would take on its points: another person of the tree who
fits the persona as well as the candidate (the file's two Thomas Ahearns would
fit any record of his own equally, and the harness holds none: his 1902
Massachusetts death record or an 1870 or 1880 census would carry it), the person
already accepted as another row of the same reading (a page naming one person
twice), and a dated fact or a stated parent-child link outside the accepted life
(no harness record dates a fact after an accepted death, and Joe Davidson's link
to his mother is a sibling placement, not the rule's decision); and the identity
pass's other limits (`Catalog.beyond_life`): a parent too young or too old at a
birth, a statement dated after the death or before the birth (Ruth M Peters's
public record of 2000–2001 after her 29 February 2000 death, live, needs her
Social Security pages and that record in the cut), and one person in two places
in one census year; and a connector's run whose records are all records no
parser reads (`log_search.unread_record`), which `run_step.run` logs `unread` and
which closes no step, the household's steps with it, whether those records are
web pages or JSON or text responses (every page no parser reads the archive holds
was saved in the browser, and a parser claims every JSON or text response the
archive holds that a connector kept as a record: the responses no extractor claims
are searches' own answers and items' metadata, never read as records, so the path
has no real response to run against); and a person the rule creates through a
relation the record states from the other side (the head of a household created
through his daughter accepted on it, as the live 1950 Evers schedule did), whose
reason names the record's word for the daughter (`conclude.rule_creates`); and a relative's
persona whose birth place differs from a finer one another decision gave the
tree's person, which the rule reads as fitting all the same (`match.compare`
with `birth_place=False`): the harness's places for Robert Edgar Davidson's
birth stay unresolved strings, so no scenario reaches the Auburn the live
catalog holds against his obituary's Woodburn. When a real document
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

### C10. A run of several requests one of which got no answer is asked again

A run whose step carries one place name, or none, can still send several
requests: `connectors/ky_vital_index.py` asks one year's file at a time over
the step's years. One year's file unanswered (a timeout, a refusal) and another
answered with no row under the surname is logged `none` (`run_step.outcome_of`:
errors and an answer), and `log_search.same_fields` reads the run as the step's
own fields, so the step is closed at that source though one year was never
read. The runner marks only a place name whose request got no answer
(`unanswered`). Mark the run's unanswered requests whatever made them, so the
next turn asks again, and show it on a Kentucky index step over two years.

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

### C23. A conflict one side of which rests only on claims and editable pages

The rule resolves a conflict only when the side it keeps holds primary
information (`conclude.classes_decide`), so John Y Davidson's birth date stays
the owner's although 24 April 1876 rests only on the file's claim and three
Find a Grave memorials while Apr 1875 rests on the 1900 census and his 1946
death certificate, records nobody can edit. Decide in the docs whether a side
resting on records nobody can edit, agreeing with one another, outweighs a side
resting only on the file's claim and pages anyone can edit, the file's
uncited claim the owner accepted being their own word and never outweighed;
§7 decision 9 reads contested classes toward the owner, and the owner's own
words put the human only where doubt is serious. Then the rule applies it,
reasonably exhaustive research first: his memorial shows a gravestone
photograph not yet held (photo 102379026), which may carry 1876 itself.

### C24. Say where the tree comes from: the file, or the evidence

The owner's goal is a loop that builds the tree from documents, the imported
file a rough guide. On the live catalog of 3 Oct 2026, 124 of 140 people exist
because the file created them (16 from records), and 47 of the 65 accepted
documents were fetched because the file cited them (4 from leads in held
records, 6 from searches on accepted facts, 8 attached by hand). Nothing reports
this. Add it to `tools/tree.py overview`'s summary, two lines: the people, by
whether the file or a record brought them into the tree; the accepted
documents, by what fetched them (the file's citation, a lead a held record made,
a search on accepted facts, by hand), read from each document's runs and their
steps' field bases. Show it on the harness tree, where every count is known.

### C25. Two readings of one record are decided apart

John Y Davidson's 1946 Kentucky death certificate is held twice: FamilySearch's
index page of it (`familysearch-kentucky-deaths-1946-N983-M2R.html`, accepted
as his) and the certificate's image, read by the model
(`familysearch-kentucky-death-records-1946-N983-M2R.jpg`), both archived under
the file's citation of it (`1,3077::604036`) and named for its ark N983-M2R. The page gives the death as 1946 alone and the image as
11 Jun 1946, so the death date conflict waits on the owner while the image's
own card is refused: its relatives are named by name alone and his persona
disagrees with the file's claimed dates. When one reading of a record is
accepted for a person, the same entry on another reading of that record (the
same record id, the same role and an agreeing name, `catalog.record_original`)
is the same document: decide it the same way, recorded as the rule with the
reading it follows, and let the image's day stand as the certificate's own.

Decision wanted first: the two readings do not meet that test as the catalog
holds them. The image's reading carries no record id of its own (the ark is
the page's locator and is in the image's file name only); what the two
artifacts share is the file's citation (`apid 1,3077::604036`) they were both
archived under. And the roles differ: the page's reader writes the record's
own person `subject`, the image's reading `deceased`. Say whether the locator a
record was archived under identifies its entry across readings, and how a
reader-independent role for the record's own person is read. The image's John
has no card now (a rematch closed it as superseded, the matcher putting none
up since the file's claimed dates disagree), so following the accepted reading
also needs the rule to write the decision with no card standing.

### C27. An import from anywhere is read as itself

Beyond citations: the gazetteer routing for Ireland, Germany and Poland, the
Silesian place rules and the church denominations are written in code
(`resolve_places.py`, `catalog.py`, `checklist.py`, `footprint.py`). Read the
routing and the denominations from data, as `data/jurisdictions.csv` already
carries which records exist where. And an unresolved place string that names a
US state anywhere in it is read as American even when its last part names
another country ("Washington, Tyne and Wear, England": `Catalog.place`): read
the country the string ends with first.

### C28. The queue's edge reaches past the file

`tools/queue.py` names as the edge a parent or spouse the file names whose link
is not yet accepted, so growth stops where the file stops: Noi Davidson, John
Evers and Dolores Evers stand confirmed with "edge: no parents claimed", and 46
missing-parents questions are open. Make a confirmed person whose parents
nobody has accepted the edge for the records that name parents (a birth or
death record, a census with the parents in the household, an obituary), first
in their plan; a parent such a record names is created by the rule from a
trusted record as now (the fitting check first) and enters the queue like any
other. Show it on the harness: a confirmed person the file gives no parents
whose own record names them, and the parents created and queued.

### C29. One home for each shared rule, and no dead schema

Soundex is written twice (`catalog.py`, `backfill_aliases.py`), edit distance twice, name splitting three times, the
nickname table twice, the suffix set twice; `initdb.py` re-implements `ulid`
without the monotonic rule `treelib.py` promises; `turns.name_of` is dead.
The `derivative` and `artifact_page` tables are never used, the three FTS
tables are filled and never queried, and no tool writes `tombstone` although
hard rule 2 relies on it. `backfill_aliases.py` takes `--by` and ignores it.
Keep each rule in `catalog.py`, drop what nothing reads (or give it its
reader), and make `tombstone` the one way a removal is written.


### C33. A family-held photograph in the harness

`decisions/95-cited-on-the-owners-word` drops two family-held photographs into
the inbox, and the harness writes the smallest of JPEG files for them, the one
stand-in file `tests/fixtures/README.md` ("What is simulated") still names. The
only family-held photographs the archive holds are marked private and never
redistributed; whether one may sit in `tests/` is the owner's choice (CLAUDE.md,
hard rule 7). Once the owner names one, archive it as a fixture with its
manifest, attach it in place of the stand-in, and drop `stand_in` from
`tests/checks/scenario.py` and the README.

### C26. Runs that stand for an answer no holder gave

`docs/DATA-ARCHITECTURE.md` §7 decision 8 lets the harness simulate a holder's
failure to answer and nothing else, but a turn scenario's `fake_run` logs `none`
with no request behind it (loop `10`, `12`, `13`, `15`, `60`, `61`, `63`), and
the `log` action writes `none` and `found` runs by hand (loop `10`, `31`, `50`,
`63`, `72`, `101`; decisions `90`), each the catalog's word that a holder
answered nothing, or answered, where no holder did. `tests/fixtures/README.md`
lists them. Either answer each with a real run (the connectors through `run`
on the archive's own answers, a saved page through `save` and `collect`) or a
holder's silence where the path allows it, or have decision 8 say that a run
written to reach a path is the harness's bookkeeping and no answer.

### C30. A fact a reading no longer states stays on the person

A page read again by a newer reader can drop a fact the older reading wrote,
and the accepted statement on it stays: `catalog.statement_of` reads a
statement through the record's current reading and falls back on the
assertion's own reading where the current one has no such fact. The gravesite
locator's reader now gives a dependent's row's rank and branch to the veteran
the row names, yet Noi Davidson's two pages of the locator, read again, leave
her Military Service "MSGT US AIR FORCE" accepted on the superseded readings.
Decide what a statement the current reading no longer makes is (withdrawn with
its reading, or kept as the record's word), write it into
`docs/DATA-ARCHITECTURE.md`, and have the re-read do it; show it on that page.

### C31. Objects a check run archived into the live archive

Fifteen manifests under the live `archive/manifests/` say `retrieved_by:
agent:check`, all at 2026-09-15T14:44:31Z: the harness's own fixtures (the
memorial of Abram C Brant, the 1950 search for Frederick Micheal Ahearn, the
Hahnle 1950 record page, the 1950 schedule 3947385, the Find a Grave search for
Robert Davidson, the Schwenkfelder search inside, Hubner-223's profile, two
gravesite pages, the loc.gov page text and five FamilySearch record pages), each
under its fixture's own file name, archived by a check run whose data root was
the live one. For those fixtures the archive's copy proves
nothing about where the bytes came from, and the live catalog may hold rows
for them. Find what that run wrote (artifacts, extractions, personas, runs)
through a tool that reads the catalog, say what the owner should keep, and
correct the README rows that rest on those copies.

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

### C35. Family links accepted on a grouping the record does not state

An accept writes a family link the record's indexer computed undecided, but
decisions made before the FamilySearch reader marked its relations, the
owner's and the rule's alike, wrote FamilySearch's groupings as accepted
links: a census page's "Father", "Mother" and "Parents" couple around the
page's own person, a marriage page's in-law. A rule
decision `reconsider` keeps keeps them accepted, so a person's parents or
spouses can read accepted on a grouping alone. Have `reconsider`, when it
keeps a decision, turn each of that decision's accepted family-link statements
whose record's current reading marks the relationship computed to undecided,
noted as the indexer's, one audit row each; the same statements under the
owner's own decisions are the owner's to answer, listed for them, since a
person's decision is never undone by the rule.

### C36. A FamilySearch household page saved with every member's details open

A census states every member's relationship to the head, but a FamilySearch
record page shows that column only in each member's own details table, which
the page keeps closed until its "Open All" button is pressed. Of the twelve
census pages in the archive, one (the 1900 Lukens household) was saved with
every member's details open; on the rest the column shows for the page's own
person and the head alone, so on a page whose own person is not the head every
other member's relationship to the head is read only as FamilySearch's grouping
(computed), and the rule takes no one through it. Have `tools/save_page.js` press the page's "Open All" buttons on an
`fs-record` page and wait for the details tables before it saves (confirm on a
real page that the details render without a request the method does not make),
then save the archived census pages again by the same method.

### C37. The route through a stated relationship says a birth year agrees where none was compared

`conclude.rule_accepts` takes a persona through a relationship the record
states with the reason "the name and birth year agree", whatever the record
gives: the gravesite locator's row for Noi Davidson names the veteran she is
buried with by name alone, and the reason the rule takes the veteran as
Raymond Earl Davidson says the birth year agrees. `docs/RESEARCH-WORKFLOW.md` says a birth
year agrees "where both have one": say the birth year in the reason only when
both sides give one, and show it on that row.

### C37. Circumstances under which a record misstates a date on purpose

A record made at the event can carry a false age or date for good: a boy who
gave himself an earlier birth year to enlist under age keeps it on every
military, veterans' and Social Security record after, so primary records
disagree with his birth record for ever, and the proof standard's classes alone
would read the enlistment's side as first-hand. The same holds for a minor
marrying without consent, a child overstating age to work, a delayed birth
certificate copied from such a record, ages rounded on a census or a passenger
list, a dual-dated year before 1752. The owner wants structure for these before
such findings arrive: "this project needs a database of circumstances where we
could possibly see contradicting information in primary sources ... then
future lines of research can be ran under these specific entries in this new
file to pin down the real story." Add `data/circumstances.csv`, reference data
for any family: each row a circumstance, the record kinds and field it touches
(in the kinds `data/evidence-classes.csv` and the checklist use), the direction
and usual size of the misstatement, the condition that makes it likely (an age
threshold at the record's own event, an era), the incentive or convention, the
records made before or free of it (its research lines), and sources an
archivist or genealogist would cite, each opened and checked. Then a date
conflict that fits a row names the circumstance where the conflict is told
(the question, `tools/proof.py`, the person screen); the rule never settles
such a conflict for the record made under the incentive; and the row's research
lines become steps on the person's plan, leads whose origin is the
circumstance. A family's own story (a grandfather said to have enlisted under
age) is the owner's word on that person in the catalog, never a row: the file
holds what recurs in any family. Write the decision into
`docs/DATA-ARCHITECTURE.md` §7 and the proof standard before the code, and show
it on a real record the archive holds.

### C3. A decision taken on a claimed relationship that reconsider would withdraw

In scenario `60-confirmed-on-a-record` the rule takes Robert Davidson on the
1940 census through the relationship it states to his son, accepted on it,
while his own name is not yet held on trusted ground. Once the owner accepts
him on the Ohio death index (step 9), a dry-run `reconsider` would withdraw
that census decision: with his name now held, `conclude.rule_points` judges the
record by two points, not by the claimed-relationship route, and the son's
link is a claim (one point). More accepted ground refuses what less allowed.
The owner's ruling of 15 Sept covers "a person the file claims" whether or not
the name is held; the docs narrowed the route to a name not yet held. Let the
route stand when the points fall short (the change is one fallback before "two
are needed"), state it in `docs/RESEARCH-WORKFLOW.md` §5–7, and show on scenario
60 that a reconsider after step 9 keeps every decision. Before that, close the
gap it exposes in scenario `99c-a-sibling-born-after-a-parent-died`: with the
route widened, the mother is taken on her son's obituary before her death is
accepted, and the brother born seven years after it is placed as her child,
undecided; the placement is examined only when it is made, so accepting her
death afterwards leaves it. Examine an undecided sibling placement again when a
parent's death is accepted (`conclude.died_before`), as a re-read does, and
remove the placement the limits of one life refuse, with its note.

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
