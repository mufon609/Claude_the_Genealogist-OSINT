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

Items with ordering or coupling constraints: the healthy baseline, in order.
Each is closed in full (a scenario failing before the change, the docs, the
checks green, pushed) before the next starts; an entry that changes what the
rule decides ends with a dry-run `tools/conclude.py reconsider` on a scratch
copy of the live catalog, reported, and the live run is made only once that
report has been reviewed.

### A6. Nothing rewrites the audit trail, the evidence or the research log

Hard rule 2 and decision 13. The insert-only triggers
(`schema/sqlite_extras.sql`) cover `artifact`, `persona`, `persona_fact` and
`same_record`. Written over today: `audit_log` (`tools/resolve_places.py
--reset` deletes the resolver's rows, and was run live on 13 Sept),
`extraction` (`ingest_gedcom.py` rewrites `structured_json`) and
`search_log` (`run_step.py`, `attach.py` and `log_search.py` turn `found`
into `none` or `unread` with no audit row). Unprotected though nothing
rewrites them yet: `persona_relation`, `artifact_locator`, `extractor`,
`tombstone`. `tools/backup.py` writes `storage_target` and `artifact_copy`
with no `--by` and no audit row. Make the reset and the run's corrected
outcome new rows (say which in `docs/RESEARCH-WORKFLOW.md`'s schema
section), stop the ingest's rewrite, give the backup's writes a `--by` and
their audit rows, then add the triggers with a check that each refuses. The
tombstone's own writer and readers stay C29.

### A7. A turn survives a bad answer and a failed file

`run_step.run` catches network errors around the fetch alone: `conn.total`
is guarded for `ValueError` and `conn.hits` not at all, so a holder's
challenge or maintenance page served with status 200 to a JSON connector
raises, `turn.run_connectors` rolls back and re-raises, no error run is
logged, and every later turn crashes on the same step (§8: a challenge is an
error run and the turn goes on). `turn.finish` runs `fetches.collect` and
the attach as one transaction for the batch while `attach.py` moves each
original out of the inbox and `archive_object` writes the object before the
commit, so one failing file rolls back the rows of the files before it whose
originals have already left the inbox, never retried; `tools/attach_inbox.py`
already takes one file per transaction. And `--db` does not move the
archive, inbox and downloads (`treelib.py` reads them from `DATA_ROOT`), so a
scratch `--db` writes into the live archive, the cause of C31. Log an answer
no reader can parse as an error run, take one file per transaction, and make
the data root follow `--db` or refuse a `--db` outside it; a scenario for
each, the holder's challenge simulated as decision 8 allows.

### A8. One person's pages never stop the loop

`tools/turns.py` refuses to run while `<db>.turn-state.json` exists,
`turn.start` pauses the whole run as soon as one person has one page for the
browser, and nothing abandons or expires a pause. The live loop has stood on
Catherine Bonn VAN FOSSEN Rittenhouse since 20 Sept 2026, with about 225
connector steps waiting across the tree and nothing archived since. A pause
belongs to the person, not the loop: the turn runs its connector steps, the
rule and the tail, its pages join the fetch list, the person waits, and the
loop goes on to the next; a resume takes whatever has been saved for any
waiting person. A state written before the turn kept `since` and
`audit_mark` credits nothing later to that turn (`turn.resume`). The commit
hook refuses the state files, which hold people's names. Write the change
into §8 first, then the code and its scenarios; the live loop is restarted
once it is reviewed.

**Blocked by:** A7.

### A9. The person screen is safe and quick

The screen's Dismiss stands on every open question, conflicts included
(`app/person/index.html`), and closes a conflict through `log_search.dismiss`
with no value kept and no reason, against decision 5 (`tools/conclude.py
resolve --keep … --note`): a conflict is resolved by keeping a side with a
reason, or stays open. §5–7 lets a person dismiss a conflict; say whether a
dismissal needs a reason, and have the screen ask for it if so. The server's POSTs check no Origin or Host, so another
site open in the owner's browser can post decisions to it. A person's page
takes about 15 s (John Y Davidson: 14,024 statements): `catalog.page_people`'s
correlated subquery scans every Birth fact once per persona on a catalog never
analysed (`ANALYZE` alone brings it to under a second on a copy), and
module-level `holdings()` calls rebuild the Catalog's cached holdings about
23 times a view. The page's `list()` and `/api/people` are a queue-shaped
table reading fields nothing returns: remove them.

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
person's link stands in for the other's: a parent's accepted marriage grounds a
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

Decision wanted first, measured on a copy of the live catalog of 3 Oct 2026:
requiring both rows of one family withdraws 14 rule decisions, and the
entry's own cases do not read as it says. Joe Davidson is not in the file: the
owner created him from his brother's memorial, and his place in Lena Howard
Bell's family rests on undecided statements alone (sibling placements from his
brother's obituary and memorial, and the membership his father's memorial
states). He was taken on the obituary through the claimed-relationship route,
which reads no `ground()` at all and counts none of those statements as the
file's claim, so a dry-run `reconsider` withdraws that decision whichever rows a
point stands on. Mary Castello's partner row carries
only an undecided statement, from the 1917 death index; the 1901 marriage
index's parentage is on Annie's child row, and the couple Dennis Scannell and
Mary is not accepted, so no couple clause keeps her 1917 card. Dan Davidson's
obituary names his mother alone: his decision stands only on Noi's partner
row, the shape this entry calls the defect. Underneath: `link_family` writes a
parent–child statement on the child's row only, so a parent's partner row has
ground only from a record that states the couple, and "both rows" makes a
marriage's evidence a condition of every parentage point. Say what grounds a
parent–child point (the child's row, or the child's row and the parent's
partner row), how a record naming one parent counts, and whether Dan's and
Mary's decisions stand.

### C6. Rule paths the harness no longer exercises, for want of a real record

The pure name rules need no record: `match.same_given` (the one-letter slip
and the nicknames), `same_middle`, `middle_differs`, `name_words` and
`split_persona_name` take examples in `tests/fixtures/rules.json` as the other
pure rules there do, which covers the name side of the garbled-initials and
short-form paths below; the rest of this entry waits on real records.

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
catalog holds against his obituary's Woodburn. No scenario reaches a statement carrying a mark on a birth, a death, a burial
or a death place: every value FamilySearch keeps beneath a shown birth or death
date in the fixtures says the same as the shown one and is no fact of its own,
so neither the date and place veto skipping an accepted value a page keeps
beneath (`conclude._grounded`) nor the identity naming one it left out
(`conclude.event_claimed_or_accepted`) has a record to run on; nor does the
identity's naming of an undecided fact another page anyone can edit types (the
harness holds one page anyone can edit per person) or of a later decision of
the rule during reconsider. No scenario reaches the rule's own wording for a page's date kept as a
contradiction of a primary record: no trusted fixture gives John Y Davidson's
burial, so his memorial cannot reach three points, and his certificate's image,
which shows burial at Franklin, Kentucky, cannot be read so because the
transcription path (`app/person/read_record.md`, the form) has no burial field.
When a real document
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
about 400 characters, statements chained by semicolons (354 lines over 160
characters in `conclude.py`, 1,338 across the tools, and rising), and functions up to 225 lines
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
family reaching the second (the tree-isolation entry above). The harness is
narrower than `tools/check.py` and `tests/checks/scenario.py` say ("another
family's export runs unchanged"): the walker names people under the
`ancestry_gedcom_xref` id system alone, `a_file_family` writes that system and
"Ancestry member tree (no citation)" by hand, and `check.py` names its fixtures
and source ids; a second family's export from another program needs those
read from the import first.

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

### C24. A held image nobody has read is research waiting, not held

A gravestone photograph is a primary source (registry E05, T1) and becomes
evidence only once read: the transcription path (`app/person/server.py`
`transcribe`, `app/person/read_record.md`) writes the reading, and its people
are cards like any other record's, as Helen Sara Brant's and Frederick Michael
Ahearn's shared stone was read and taken for both. The live archive holds seven
more no one has read: two more of Helen's (memorial 142698059), Abraham B
Brant's, Sarah Cassel's, Anna Marie Bolton's, Ellen E McCrary's and John Young
Davidson's (1822–1877). Their fetch steps stand done and `tools/checklist.py`
calls the row held once a done step archived the record, so nothing asks for
the reading: no card, no step, no open question, and the queue passes the
person by. Read "held" as read: an archived image with no reading of its own is
"held, not read" on the checklist and in `tools/proof.py`'s research, and the
person's plan carries a step to read it (the reader the owner's ruling names,
the model, with a person where the image is in doubt), which the queue counts as
work a turn can do. Show it on a real image the harness holds, then read the
seven live and decide them like Helen's and Frederick's.

### C27. An import from anywhere is read as itself

Beyond citations: the gazetteer routing for Ireland, Germany and Poland, the
Silesian place rules and the church denominations are written in code
(`resolve_places.py`, `catalog.py`, `checklist.py`, `footprint.py`). Read the
routing and the denominations from data, as `data/jurisdictions.csv` already
carries which records exist where. And an unresolved place string that names a
US state anywhere in it is read as American even when its last part names
another country ("Washington, Tyne and Wear, England": `Catalog.place`): read
the country the string ends with first.

### C29. One home for each shared rule, and no dead schema

Soundex is written twice (`catalog.py`, `backfill_aliases.py`), edit distance twice, name splitting three times, the
nickname table twice, the suffix set twice; `initdb.py` re-implements `ulid`
without the monotonic rule `treelib.py` promises; `turns.name_of` is dead.
The `derivative` and `artifact_page` tables are never used, the three FTS
tables are filled and never queried, and no tool writes `tombstone` although
hard rule 2 relies on it. `backfill_aliases.py` takes `--by` and ignores it.
Keep each rule in `catalog.py`, drop what nothing reads (or give it its
reader), and make `tombstone` the one way a removal is written, and honoured:
`holdings`, `held_for`, `fetched_rows` and the screen still count a withdrawn
artifact as held, and the one live tombstone was written by hand. Also dead or
unfilled: `person.private`, `note.private`, `geonames_id`, `surname_prefix`, the
`page_id` columns, the place card's `suggested` key; `artifact.http_status`,
`etag` and `last_modified` are empty on every row though most manifests carry
them; `schema/catalog.sql`'s "REFERENCES … declared below" are never declared;
the `v_unsupported_*` views count merged persons and folded events; and the walk
to a record's current reading is written four times in `conclude.py` beside
`catalog.current_reading`.


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
written to reach a path is the harness's bookkeeping and no answer. The same
holds for the actions that write catalog rows by hand in the shape a writer of
the tools writes them (`a_step` in 27 scenarios, `a_place_card`,
`a_file_family`, `a_persona_link`, `a_legacy_card`, `a_event`, `a_question`,
and `older_reading`, which plants a reading an older reader made as the live
catalog holds it):
when the writer changes, those scenarios go on testing rows the code no longer
writes. Reach each through the tool that writes it.
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
correct the README rows that rest on those copies. The cause, a `--db` that
leaves the archive at the live data root, is A7's.

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

### C38. Circumstances under which a record misstates a date on purpose

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

### C39. A second copy of a held record is left in the inbox

`tools/attach.py` places a saved page on the plan step its identity reaches; once
one copy of a cited record is held (John Y Davidson's 1946 certificate page, done
on its citation `1,3077::604036`), a later save of another copy of the same
record (FamilySearch's index entry of it) finds no planned step and stays in the
inbox, so it is never archived, read or joined (`same_record`). Archive such a
page under the done step's citation when its identity reaches that step, read
it, and let `conclude.join_copies` and `conclude.carry` make it a copy of the
record the step holds; the harness scenario `99ze` archives the index entry by
hand for this reason.

### C40. A document's topic, and the leads it opens for a person and their family

The catalog classifies evidence by the kind of document and its trust, never by
the part of a life it reveals (military service, immigration, a church, a
trade): the source registry's `Category` sits on the holder (Fold3 "Military",
the VA gravesite locator "Burial"), not on what a document states. Raymond Earl
Davidson's accepted records state an Air Force master sergeant who served in
Vietnam ("MSGT US AIR FORCE, VIETNAM"), yet nothing marks him a veteran or Noi
Davidson, whom her own gravesite row names "WIFE OF DAVIDSON, RAYMOND E", a
veteran's wife, and the checklist's military service row opens only on a
military event no rule writes from that rank; so the loop never looks for the
records that service left (his service file, VA claim, the dependents it names)
for him or his family. The same holds for every immigrant, church member or
tradesman. Owner, 3 Oct 2026: this is the root issue behind "tag her as a
military wife". Give each record kind or fact type a topic in data, its detail
from the record's own words (Air Force, Vietnam); a person carries the topics of
their accepted records, derived, never typed; each topic names, as data, the
record sets it leaves for the person and their close family, which the plan
turns into leads. Start with military; write it as a design decision before
building. Noi's Military Service event, whose two statements are rejected,
waits on this.

### C25. A search's log says whether it was exhaustive

The proof standard asks for reasonably exhaustive research, and a program can
show it only from `search_log`, which records no request sent, no total the
holder reported, nothing about how many were read, and no truncation (a total
lives in free-text notes cut at 1,000 characters, `run_step.py`). Live, 89 of
the 140 connector runs logged `none` sent no request at all (a field the
source wants was missing, or the person's years lie outside it), told apart
from an empty answer only by the note. The connectors stop early and say
nothing: `connectors/ia.py` reads five items and three pages of each,
`wikitree.py` five profiles, `loc_gov.py` the first twenty results with no
next page, `ia_directories.py` six towns, and `plan.py` puts at most twelve
footprint records on a plan. `found` means the surname stood on a page: 42 of
the 44 `found` runs at the OCR and WikiTree sources led to no proposal and no
link. And `log_search.same_fields` leaves `surname_variants` out, so a
spelling learned later never asks a source again. Give the log the request,
the holder's total, the number read and whether the list was cut, as columns;
log a cap as a cut; let `found` mean a persona the matcher put to someone, the
rest `none` with the page held; and count the variants as fields.

### C28. Connectors that answer "none" where they never looked

`connectors/nj_death_index.py` reads the 2006–2017 file alone, but the
registry's coverage (C09, New Jersey 1848–2017) is what lets a step ask it, and
the connector checks no year: Dennis Scannell and Mary Castello are logged
`none` there and never asked again. `va_graves.py` asks the middle initial as
"begins with", so a veteran indexed with none is missed; `ky_vital_index.py`
takes a year equal to the birth year to mean the birth index, so an infant's
death is looked for among births; `loc_gov.py` asks the death year alone where
the gate allows that year and the next. Each connector asks over the years and
fields it can answer and says `none` only for those (the New Jersey 2001–2005
file wired or the step refused before it), and the two live `none` runs are
asked again. Every New Jersey step also downloads the 69 MB file again: cache
it as C18 says for Kentucky.

### C32. A record reaches a step on what it states, and is read once

Three paths put or read a record on less than it states. `extract.py`'s
Ancestry-index parser claims any HTML page holding a two-cell table, untested
on a real page by its own docstring, so a page no parser really reads (a
Legacy.com obituary, any page saved by name) becomes a full reading and closes
its step instead of being logged `unread`. `attach._steps_by_collection`
places a record on any planned step in the tree whose person has the record's
name within two years, so a namesake's step can be closed and `plan.py` keeps
it done. And `run_step.run` reads every record again on every run, bytes
already held included, superseding the old reading and rejecting its undecided
cards, with the OCR text read by whichever log row cites the file last (44
Internet Archive files read 130 times live), where `attach.py` reads new bytes
alone. Give the catch-all parser a real page or drop it, require the record's
own identity (a name and a fact that agrees) before the collection path closes
a step, and read held bytes again only when a reader is newer.

### C34. The rule decides on its facts, not on its own sentences

The rule reads the matcher's English: `conclude.py` tests
`startswith("disagrees: ")`, matches "the record gives only" by pattern, and
`split_disagree` keys relatives by their rendered line, so two relatives of one
name and word collide; `cards.py` reads the same lines. Rewording a line of
`match.compare` or `catalog.place_verdict` changes what the rule decides, and
the rule's three routes (points, identity, creation) speak to each other the
same way. `HEAD_ONLY` and `DATED_WITH_PARENTS` are labels of
`data/evidence-classes.csv` written in code, which no check holds to the file:
renaming the kind there turns off the pre-1850 census guard, which also passes
when the census year is unknown and takes the year from the collection's name
by pattern when the record gives none. Give
`compare` and `place_verdict` a structured result the rule reads, with the
words made from it for the card; check the labels against the file.

### C41. Code that holds what the data should, or this family's own words

Decision 7 (no code names a family's people, places or denominations) and
decision 12 (the limits of one life are data). `match.py`'s nickname table
carries this tree's members (Lura, Lou, Laura; Corinne, Carinne, Corrine;
Cassie; Ollie) and groups distinct names as one (Oliver and Olive, Emily and
Emma, Helen and Ellen, Christian and Christopher), and `same_given`'s one-letter
rule makes Harry Larry and Edwin Erwin, while a surname one letter apart is
refused. `conclude.died_before` holds a father's margin of a year and reads
unknown sex as a mother where `data/life-limits.csv` says ten months and reads
it as a father; `footprint.py` holds a ninety-year life, a birth twenty years
before the first event and a 15–50 parent window. Registry ids are written in
`plan.py`, `fetches.py`, `attach.py`, `turn.py` and `cards.py` (D03, E01 and
others). Decision 3's release years live in the registry and are never read:
`checklist.py` holds the 1950 census cut-off and the draft, Social Security and
directory eras, and finds military records by "Army|Navy|Veterans" (no Air
Force, which C40 needs). `checklist.py`'s `DEPENDS={"D03":"B01"}`, D03's
registry note and `docs/RESEARCH-WORKFLOW.md` §4's "FamilySearch after
Innovator approval" still wait on the API decision 4 rules out.
`backfill_aliases.py` names this tree's own misspelling "Silesa" and fifteen
states where `catalog.py` holds all. Move each into the data it belongs to, or
the table that already holds it, and the nickname groups to a data file of
true equivalents.

### C42. The move to Postgres is not a dump and restore yet

`schema/catalog.sql` says it runs on Postgres without edits, but `same_record`
references `tree` before `tree` is created. The code uses `INSERT OR
IGNORE`/`REPLACE`, `IS ?`, `json_set`, `json_each`, `LIKE` as a
case-insensitive match (the person lookup relies on it) and `ORDER BY rowid`
(`match.py`, `conclude.py`: fact order by physical insertion), none of which
`schema/README.md`'s porting list names, and that list drops the insert-only
triggers, so hard rule 2 would stand on nothing after a port. And the
one-time corrections in `initdb.py` (0.7.3 to 0.7.9) import today's `plan`,
`conclude` and `catalog`, while `rebuild_table` reads today's DDL and commits
in the middle of a migration, so an old backup migrated later runs today's
logic and a failure leaves a version half applied and unrecorded. Make the DDL
order right, list every construct the port must change, carry the triggers
over, and make each migration one transaction that names the code it needs.

### C43. A reader in the loop

"AI in the core" has no place in the code: no model is called anywhere, every
reading the loop makes is one of fifteen parsers of one site each, and the
eleven model readings the catalog holds were typed through the screen's
transcription path by a session. So an obituary's text, a gravestone
photograph and a scanned index wait for a session however long the loop runs
(C24 is one such case). Decision wanted from the owner before code: whether a
turn calls a model to read a held record no parser reads (`app/person/
read_record.md` is already its instruction, the reading recorded with its
model and prompt hash), within what cost per turn (decision 6), and which
records stay a person's to read.

### C44. A live reconsider reaches its end in one run

A live `tools/conclude.py reconsider` can leave decisions that a second run
withdraws (cards on several readings of one page, fits that depend on order),
so every live run is followed by a dry run expected to change nothing, and a
full copy of the catalog is taken before each live change (twenty sit in
`catalog/` now). Run the withdrawals, the cards and the conflicts until a pass
changes nothing, within the one call, and show on a scenario that a second
run changes nothing; then the habit can go.

### C45. Reads that scan the whole tree

Fine at 145 people, each grows with the tree: `catalog.cited_persons` scans
every assertion with `json_extract` per call; `held_for` walks every holding
per citation; proposals are found by `json_extract(payload_json, …)` over the
tree (`cards.py`, `catalog.py`, the screen); `search_log.artifacts_json LIKE
'%sha%'`; `footprint.duplicates` compares every pair on every plan
regeneration; `catalog.py` finds citations by `notes LIKE '{"apid":%'`, which
works only because of the JSON key order. Give each the column or index it
reads, and run `ANALYZE` after a migration.

### C46. Tools no check runs

Measured across every process a check run starts: `tools/backup.py` (the
archive's fixity and its bags) and `tools/cite.py` run no line; the screen's
HTTP layer (`do_GET`, `do_POST`) is never reached, the scenarios calling its
route functions directly; `run_step.fetch` (rate limit, User-Agent, POST),
`loc_gov.hits` and `total`, `catalog.*_search_url` and `search_target` never
run, and `cards.render_cli`, `cards_for` and `rule_verdict` (what the owner
reads) neither. Each can be shown on records the harness already holds: a bag
written and checked under the scratch root, a citation made and run, a POST
through the server.

### C47. What "the loop works" means

The goal says what the system is for and never what reaching it looks like,
so progress is read off commits. `tools/tree.py overview` already counts where
the tree comes from (people from the file and from records; documents from
citations, leads, searches and by hand). Decision wanted from the owner: the
state that counts as the loop working (people and documents brought by
evidence rather than the file, turns run without a session, what still reaches
the owner and why), written into `README.md` beside the goal and printed by
the overview.

### C48. A key the harness does not know inside an expectation or an action passes

An entry of `expect` and a step now fail on a key beside the one the walker
knows, but the expectations and actions read the value they are given by
picking the keys they know and dropping the rest (the `{k: v for k, v in
x.items() if k in (...)}` of `e_card`, `e_event`, `e_artifact` and most of
their neighbours, `x.get("status", "accepted")` in `a_decide`): a misspelt or
misplaced key inside a pattern, `stauts` for `status` in a `card`, is never
read, so the claim it carried holds whatever the code does. Give each
expectation and action in `tests/checks/scenario.py`, `loop.py` and
`imports.py` the keys it reads, and fail a value that carries another, so a
scenario can say nothing the harness does not check.
Two actions fail the same way: `withdraw` given a bound value (`"$x.sha"`)
where it wants a label finds no decision and does nothing, silently; and the
`archive` step with a manifest raises `JSONDecodeError` when the manifest's
`notes` is plain text, as the gravestone photograph's is, so a real fixture
cannot be archived through it.

### C49. The proof summary names the owner for a statement no person decided

`tools/proof.py`'s decider reads `assertion.asserted_by` alone, so a statement
whose status a session's re-read or a carry stamped `agent:… for user:…` reads
"the owner" in the proof summary though no person decided it. Name the owner
only where `assertion.person_decided` says a person's own decision set the
status, and say what set it otherwise (the record's acceptance, a re-read, the
rule).

### C50. "Claim" means two things in the code

`docs/RESEARCH-WORKFLOW.md` §0 defines a claim as the imported file's word.
`Catalog.basis`, `link_basis` and `family` label as `claim` every membership
whose statements are not all rejected, a page anyone can edit and a sibling
placement included, and their readers take the label at §0's word: the queue's
edge "a parent or spouse the file names" (`tools/queue.py`) counts a parent the
tree links only by a placement, and the limits of one life (§5–7,
`docs/DATA-ARCHITECTURE.md` §7 decision 12, `Catalog.beyond_life`) are said to
test "accepted or the file's claims" while they test every link not rejected.
The rule's own reader is `conclude.claimed_or_accepted`. Call Catalog's label
what it is, have each reader that means the file's word read the file's word,
and make the docs say what each test reads.

### C51. A refusal says the indexer's when the record also states the relationship

When the claimed-relationship route finds nothing, `conclude.rule_points` says
"the record's relationship to the person accepted on it is its indexer's, not
the record's own statement" whenever any relationship the indexer computed ties
the persona to a person accepted on the record, even beside one the record
states. Dennis Scannell on the 1917 Massachusetts death index is the father of
Annie Scannell Ahearn, which the index states; his couple with Mary Costello is
FamilySearch's grouping, so the reason misnames why the route failed (the tree
held his link to Annie only on that record's own statement). Say the indexer's
only when no stated relationship to a person accepted on the record is there,
and otherwise name the stated one and why it does not count, as the clause
naming the link the tree holds on nothing that claims it already does.

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
