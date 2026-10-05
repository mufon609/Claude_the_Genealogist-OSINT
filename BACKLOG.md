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

Items with ordering or coupling constraints: the healthy baseline, in order,
then the work that stands on it. Each is closed in full (a scenario failing before the change, the docs, the
checks green, pushed) before the next starts; an entry that changes what the
rule decides ends with a dry-run `tools/conclude.py reconsider` on a scratch
copy of the live catalog, reported, and the live run is made only once that
report has been reviewed.

### A1. Models run the steps no connector can, tasked and measured by code

`docs/DATA-ARCHITECTURE.md` §7 decisions 16 and 18: code judges, models
investigate. The fetch task exists (`tools/run_task.py`: the fetch list's
entry rendered by code, one text for the kind, the launcher, collect judging
what came in, every launch a `task_run` row), and nothing calls it yet: a
page at a holder without a connector still waits for a session at the owner's
browser, a held image for a session at the transcription form, an assisted
search for a hand. What is left, one piece closed before the next:

1. **What a session's launch leaves to its word.** Both launchers stand
   behind one seam and a model has saved its first page (4 Oct 2026, the
   smallest model: 8,895 tokens, five tool uses, 27 seconds, a card), judged
   by collect and recorded. A session's run still rests on the session for
   three things code could read: the model the subagent really ran on (the
   row holds what `next` was told, and a spawn without the parameter takes
   the session's own), and its tokens and time, which the session copies
   from what it was shown. Read them from the subagent's own record where the
   harness keeps one, and say on the row when they are the session's word.
   Beside it: several files saved for one task go to collect together and
   the judge does not notice (the first run ran the script three times); a
   page the browser saved into another folder is a report that differs from
   the finding with no cause named; `started_at` is when the task was handed
   out, not when the subagent began; `tools/save_image.js` still returns its
   line unawaited, as the page script did before it was made one awaited
   call; a launch names the browser it uses instead of taking the one picked
   last on the account; whether the subagent opened one new tab, as its text
   says, code cannot see; and an answer that is not the schema's has no
   scenario for want of a real one.
2. **Calibration: an estimate is the record of past runs** of the same task
   kind at the same holder, never a guess. A kind with no runs is calibrated
   first on work whose answer the catalog already holds: done fetch steps
   whose record ids are known, pages a parser reads (the model's reading
   compared with the parser's field by field), readings the owner decided. A
   calibration task is run more than once at each model and effort, so a
   model that answers the same task differently is seen.
3. **The choice is data and one rule, and nothing in it is asked of the
   owner** (decision 17: what the program can measure is measured). A data
   file lists the models and efforts in order of cost. Where code checks the
   whole result (a fetch: the saved page's identity is the step's), a wrong
   answer is refused whichever model gave it, so the runner takes the model
   and effort with the lowest recorded cost per result that passed. Where
   code cannot check the whole result (a reading), a model and effort
   qualifies only when no reading of its calibration differs from the known
   one, and in use a record is read twice, independently, and stands where
   the two agree: where they differ it goes one step up, and to a person only
   when the top step still differs, so no kind of record is a person's to
   read beforehand. A task code judged failed goes one step up, both runs
   recorded; at an interval the file sets, a task is run one step down as
   well, so a cheaper model that has become good enough is found. A run is
   stopped at the highest cost its kind's calibration recorded and counted
   failed; the turn's report says what was spent and what it bought.
4. **The loop runs it.** `tools/turns.py` hands a waiting person's pages to
   the runner once the choice names a model, one page at a time. A page the
   model reports blocked leaves a run on its step that says so, so the same
   page is not launched again until a person has passed the block; today only
   the `task_run` row holds it.
5. **The other kinds.** A search at a holder without a connector (C53: its
   results page is the save, its `none` the parser's reading of that page,
   never the model's word); a gravestone photograph (`tools/save_image.js`);
   a reading of a held record no parser reads (`app/person/read_record.md`
   is its text), entering as an undecided extraction with its lines or boxes;
   a source or a lead a model proposes, which becomes a plan step and is
   judged by that step's run.
6. **A question is a task too.** Anything that waits on a person (a card, a
   conflict, a place, a question about one life) can be handed to the top of
   the ladder as a task of its own kind, built by code from the question as
   the catalog holds it: the card, the rule's reason, the person and their
   relatives, what was tried. The model answers in a schema: the records it
   found, saved through the fetch task so the rule decides on them; an
   argument, for and against, whose every statement names the row or the
   file it rests on; and, where it could not settle the question, what
   would. Code checks each statement against the catalog and drops what it
   cannot find. The model's verdict is never a decision: the rule decides on
   the new evidence, a person on a checked argument. The run is a row like
   any other, with the question's class and what settled it.

A launch of one sentence on the smallest model costs about a cent before it
does anything, the standing instructions it loads, so a small task is given
only the tools and the text it needs, as the fetch task is.

### A2. A question reaches a person only after the investigation that could answer it

`docs/DATA-ARCHITECTURE.md` §7 decision 17. A record the rule does not take
is a card at once, a difference between two place strings a conflict at once,
and a string the geocoder leaves open a place card at once, whatever the
program could still find out. Measured on the live catalog of 4 Oct 2026
(`tools/cards.py --all` with the rule's reason on each card, the open
questions, the undecided place proposals), what waits on the owner:

- **62 record cards.** 13 are pages anyone can edit short of their three
  points because the tree holds the matching day or burial only as a claim;
  10 are trusted records one point short; 13 wait on a name or a relative's
  link nobody has accepted yet; 16 differ on a name (a woman under her birth
  surname whose parents the tree holds, a middle initial, an indexer's slip,
  a short form); 7 are no decision (no full name to create a person under, a
  relation of "other", an informant); 2 differ on a birth year; 1 is a kind
  the classes table has no row for.
- **28 open conflict and identity questions.** 10 are a couple's repeated
  marriage events in the file; 11 are places, among them one cemetery under
  its own name and under its locality, a town against the county it lies in,
  and a bare town name against its state; 2 are names, 1 a birth date, 2 a
  person's two events of one kind, 2 the limits of one life.
- **106 place cards.** 13 are a bare name that needs context; 26 are one
  place among candidates that are its own boundary or no place at all; 19
  are several candidates verifying; 11 a same-named nested unit; 20 no
  candidate matching every part; 8 no candidate; the rest carry notes of
  their own.

A first trial ran on a scratch copy of the live catalog on 4 Oct 2026.

Record cards: a model read each card against the tree and answered 34 of the
62 from what the catalog already holds, 21 as the person and 13 as no
decision to make (five namesakes born in another country or state, eight
personas nobody should be created from). Each answer stands on a general
ground: a parent named by a given name, by initials or by a surname alone on
a record of their accepted child, beside the other parent accepted; a
daughter under her father's surname where the tree's name is her married one,
or under a married surname in her mother's obituary; the same misspelt
surname as the accepted child's on the same record; a household whose
parents, a sibling and the month of birth all fit against one differing
middle initial; a full name, a year and a place of death with the mother
accepted on the record. With those decided the rule took 12 more by itself (3
of the 62, and 9 personas it then proposed, one a new person), a second run
changed nothing, and 25 were left: 13 pages anyone can edit waiting for a
trusted record of a day or a burial; 7 household members whose relationship
to the head is on their own page of the census (C36); a state index's line of
a certificate already accepted (a copy to join, decision 15); a marriage
index entry of two names (2 cards); a model's reading that differs in one
initial, to be read again; and one real question, a half-brother's mother.
The decisions opened 9 conflicts: 7 are one census page's two wordings of the
residence, once for every member of the household, and 2 are name variants
that are aliases. The owner's past decisions are a thin check on these
answers: 43 cards accepted, none rejected.

Place cards: the states and countries the catalog already holds for the same
record, for its collection or for the person pick one candidate for 16 of the
106 and narrow 25 more to one place offered twice. A bare state name or
abbreviation is the state. Cemeteries, churches and townships the geocoder
lacks want a second gazetteer for the United States (GeoNames, registry row
N01, carries the federal names).

Conflicts: of the 11 on places, 5 read as one place at two granularities or
under two names (a cemetery by its name and by its locality, a town against
its county or its state), to be shown by resolving both strings in the
record's own context; the 10 on repeated marriage events sit on people more
than one link from the confirmed tree, whom the queue no longer names.

The loop's automatic half was rehearsed the same day on a scratch copy, every
step a connector can run: 229 steps in 39 minutes with no error run; 73 found
and 301 `none`, 236 of those with no request sent (C28); 159 files
archived and 860 personas read, nearly all names in a book's running text;
one record taken by the rule, none of the 62 waiting cards answered, and 3
new cards, each a namesake's profile at WikiTree. Re-reading the 106 waiting
place strings with the current resolver settled 6 (state abbreviations and
one village the gazetteer knows): the cards were written by the resolver's
first version, and nothing re-reads a string an older version left open, as
`tools/extract.py --stale` re-reads a page.

The work, a class at a time, the docs first (§0, §5–7,
`docs/RESEARCH-CHECKLIST.md` §6b), each ground written as a test the rule
makes and shown on a copy of the live catalog before the live run: the
grounds above for a relative named in part and for a woman's two surnames; a
card short of a point as first a lead for the record that would supply it; an index's line joined to
the certificate it indexes; a record's own two wordings of a place as one
statement; a place difference compared once both strings are resolved in
context; a bare place name resolved in that context. The same-named nested
unit stays undecided as `CLAUDE.md` has it unless a trial shows context that
tells the two apart, which is then put to the owner as a change to that rule.
Nothing lowers what the rule takes: the rule is given more evidence. What
still reaches a person says what was tried.

The first class is built: a namesake a name search reached, and a persona
nobody is created from, are hints on the page that say why (50 record cards
wait on the live catalog of 5 Oct 2026, thirteen fewer). Left from it: a
profile a name search reached that agrees on the name alone and disagrees on
nothing is still a card, for want of a real page that shows it; a card closed
and proposed again by a new matcher can land on another copy of its record,
where the docs put an entry on the copy that first carried its card; a
new-person card stops being one only when the matcher's version next rises,
since the pass that re-examines cards reads persona matches alone; and a
surname-only parent on a child's record is a hint until the class that reads
a relative named in part knows them for the tree's own parent.

What a waiting question shows (`docs/DATA-ARCHITECTURE.md` §7 decision 18).
Each waiting question says, in words a person who knows no genealogy can act
on:
what is asked; why the rule did not take it (its reason is words already);
what was tried; what would settle it, worked out by code from the reason
(the record that would supply the missing point, the decision it waits on);
and a control that hands the question to the stronger model (A1, point 6),
with what such a run has cost for questions of its class. A question put to
the person is one only their family can answer (whether a man married
again), recorded as their word and used to guide the search. The stronger
model is for what the common grounds do not reach: of the 25 cards the trial
left, 22 want a routine step (a record fetched, a page saved again, a copy
joined, a second reading) and 3 want it (the marriage entry of two names, the
half-brother's mother). Each ground it finds that recurs becomes code or a
small task: the classes the stronger model settled and code does not yet are
that work's list, and their share of all questions is reported and should
fall.

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
`search_plan` by artifact or persona to its tree. Three more places cross
trees: a place card is written under the running tree for a string every tree
shares (`tools/resolve_places.py` takes the strings no resolver has read, so
a second tree sharing an undecided string gets its words and no card);
`reset_ai_resolutions` resets shared strings and clears `event.place_id` in
the calling tree alone; and `app/person/index.html` never sends `?tree=`, so
the screen serves the active tree only.

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
The same holds where some hits arrived and others did not: a 1950 district
search whose neighbour's schedule arrives while the household's own times out
is `found` and closes the step, the lost name logged unanswered and never asked
again; a run is `found` for the step only when the hit that answers the step's
own person arrived.

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
without the monotonic rule `treelib.py` promises.
The `derivative` and `artifact_page` tables are never used, the three FTS
tables are filled and never queried, and no tool writes `tombstone` although
hard rule 2 relies on it. `backfill_aliases.py` takes `--by` and ignores it. `connectors/ky_vital_index.year_of` does what `treelib.year_in` does, and the tracked `inbox/.gitkeep` is no longer needed now that `treelib.inbox_dir` makes the folder.
Keep each rule in `catalog.py`, drop what nothing reads (or give it its
reader), and make `tombstone` the one way a removal is written, and honoured:
`holdings`, `held_for`, `fetched_rows` and the screen still count a withdrawn
artifact as held, and the one live tombstone was written by hand. Also dead or
unfilled: `person.private`, `note.private`, `geonames_id`, `surname_prefix`, the
`page_id` columns, the place card's `suggested` key; `artifact.http_status`,
`etag` and `last_modified` are empty on every row though most manifests carry
them; `schema/catalog.sql`'s "REFERENCES … declared below" are never declared;
the `v_unsupported_*` views count merged persons and folded events; `v_person_vitals.birth_date` is read by nothing; `tools/tree.py` writes `.active-tree` whole with its own copy of what `treelib.write_json_whole` does for JSON; and the walk
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
`a_merge`'s `older` (a merge put back in the shape an older tool left it),
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
correct the README rows that rest on those copies. A tool refuses a `--db`
outside its data root (`treelib.in_data_root`) and every check runs under a
scratch `DATA_ROOT`, so this entry is the cleanup alone.

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
true equivalents. The words of kinship are held twice and in English: the
matcher's `KIN_WORD`, by which a new person is proposed, and the rule's
`FAMILY_WORD`, by which one is created, differ (a "Maternal Grandmother" is a
card the rule refuses).

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
logic and a failure leaves a version half applied and unrecorded. `rebuild_table`
also drops a rebuilt table's triggers, harmless while every rebuild comes
before the 0.8.1 triggers but not for a later migration that rebuilds a
protected table. Make the DDL order right, list every construct the port must
change, carry the triggers over (and recreate them after any rebuild), and
make each migration one transaction that names the code it needs. On the
live catalog the dump itself fails the recipe: `.dump` writes `search_plan`
before the rebuilt `research_question` it references, and booleans as 0 and
1; about a thousand statements go straight to `sqlite3` across the tools, and
the FTS tables are never queried. The backup bag's `tree.sql` cannot be loaded
into a fresh SQLite in one pass: `iterdump` writes the FTS tables through `writable_schema`,
and their inserts fail with no such table.

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
reads, and run `ANALYZE` after a migration. `overview.overview` builds a card
for every person on each load, `Catalog.tiers` walks the tree once per
instance and instances are made per call, and `assertion` has no index on
`persona_fact_id` or `persona_id`; `ANALYZE` has never run on the live
catalog. `cards.hints_on` runs the matcher each time a reviewed person's
record is viewed, unmeasured on a record of many names. Every turn's tail runs `conclude.reconsider` over the whole tree,
two to three minutes a turn at 145 people: a turn re-examines what its own
records and decisions touch.

### C46. Tools no check runs

Measured across every process a check run starts: `tools/backup.py` (the
archive's fixity and its bags) and `tools/cite.py` run no line; the screen's
HTTP layer (`do_GET`, `do_POST`) is never reached, the scenarios calling its
route functions directly; `run_step.fetch` (rate limit, User-Agent, POST),
`loc_gov.hits` and `total`, `catalog.*_search_url` and `search_target` never
run, and `cards.render_cli`, `cards_for` and `rule_verdict` (what the owner
reads) neither. No scenario reaches `proof.py`'s "the rule would keep assertion" line, nor a
turn that names a conflict the rule decided inside it: with real fixtures the
turn's place resolver stops at the first geocoder query it holds no answer for. Each can be shown on records the harness already holds: a bag
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
cannot be archived through it. And `has` passes a `lacks` or a `none` on a
value that is missing altogether.

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

### C52. A challenge page a non-JSON reader takes for an empty answer is logged none

A JSON connector raises on a challenge or maintenance page served with status
200 in place of its answer, and the run is logged error (`run_step.unreadable`).
The CSV and HTML connectors read such a page as an answer with nothing in it:
`nj_death_index.rows` and `ky_vital_index`'s readers find no row under the
surname, `va_graves.total` gives None and `results` an empty list where the page
lacks its table. The run is logged `none`, the holder's word that it holds
nothing, and `log_search.same_fields` closes the step at that source. Give each
such connector a test that the body is its answer (the index file's header
line, the year file's layout, the gravesite page's own result or no-result
markers), raising when it is not, so the page is an error run and the step is
asked again; show it on loop `106`'s turn, where New Jersey's index and the
gravesite locator log `none` on the harness's challenge page.

### C43. A cited record is not closed by the first page of a search's results

When no row of a saved FamilySearch results page fits the person, `attach`
restates the run `none`, the fetch list then hides the step and the queue
passes the person, though the page says it is the first of several: on the
live catalog of 4 Oct 2026, 76 FamilySearch fetch steps stand at `none`, 54 of
them on page 1 of several. A citation says the record exists, so that `none`
is a cut, not an absence (`docs/DATA-ARCHITECTURE.md` §7 decision 17). The
search narrowed by the citation's own fields, then the next page, is the
step's next save; the step is `none` only when every page has been read.

### C53. A new search at a holder without a connector is the loop's work

The fetch list holds fetch steps only (`tools/fetches.py`), the queue counts
only those and the steps a connector runs (`tools/queue.py`), and
`catalog.search_target` builds a search's link for the screen alone, so of
the 131 assisted searches planned on 4 Oct 2026 none is ever a turn's work:
41 have a link only the screen builds, 66 name a holder, 24 name no source.
The tree grows past the file only where a connector answers. Put a search
whose holder takes a link on the fetch list, its results page the save, as
§8 already reads; with A1 a model runs it.

### C56. The search ladder as built

`docs/RESEARCH-WORKFLOW.md` §3 has six layers and §2 a ranking. Layer 0 is
planned (twelve records at most), layer 3 as United States census rows, layer
2 only as each person's own rows; layer 1 is printed by the checklist and
never planned; layers 4 and 5 and the `surname_locality` query are in the doc
alone; no search step carries a question (0 of 186 on 4 Oct 2026), and the
ranking is not implemented. Build each layer, or make §2 and §3 say what is
built.

### C57. Names and records beyond English and the United States

Beside C19, C22 and C41: the checklist's census rows are the United States'
alone, and `before_civil` is computed and never used; `catalog.key` and
`soundex` drop every letter outside a to z (Müller keys as mller, and a name
in another script has no key); `split_name` takes the last word as the
surname (van der Berg is Berg); the page parsers' labels are English; and
Silesia is named in `tools/resolve_places.py` and `Catalog.place`. A tree
whose people lived in Ireland, Germany or the Netherlands gets blocked
fetches and assisted rows with no link. Show each on the second family's
export when the harness has one.

### C58. The name variants the rule stands on

`conclude.write_name_alias` writes an alias accepted whatever the tier of the
record it came from, and the rule reads every alias not rejected as the
person's name (`Catalog.person`, `match.name_keys`): on 4 Oct 2026, 3
accepted aliases come from pages anyone can edit and 60 undecided ones count
as names. A withdrawal leaves its alias undecided, so a decision taken back
still shapes later ones. `match.same_given` reads a bare initial as agreeing
with a given name, which §5–7 does not say, and with a day counting double a
name and one date then take a record. Say in §5–7 which variants the rule
counts as the name, write an alias with the standing of its record, and take
a withdrawn decision's alias with it.

### C59. A card a person or a session accepted can be taken back

`conclude.decide` rejects only an acceptance the rule made: a card accepted
by the owner or by a session answers "already decided", no tool turns that
persona link back, and `reconsider` never examines it (8 cards on 4 Oct 2026
were accepted by sessions). Give `tools/conclude.py decide` the taking back
of any acceptance, by a person, with its reason and audit row.

### C60. Where the rule and its words part in small ways

Each read in the code, none with a live case unless said: the identity of a
page anyone can edit counts a burial place at any granularity, where the
trusted route leaves out one coarser than the tree's; `rests_elsewhere` takes
undecided statements of a page anyone can edit, and marked values, as what
makes a relative's persona stand for the relative; the rule creates a
grandchild or a half sibling and writes no family link; `conclude.place`
writes its accepted statement without the proposal's id, so rejecting or
withdrawing the record leaves it accepted; `cards.card` works out its
verdicts without the record's state or the dated names, so a card can show
"disagrees" where the rule read "agrees"; a card code closed is stored
`rejected` under the session's or the owner's name, told from a person's
rejection only by the note `superseded` (1,334 of the 1,339 rejected cards
live); "a page anyone can edit" is tier T4 in one place and anything outside
T1 to T3 in another; the matcher never proposes a persona that carries any
rejected link, to anyone; and the proof makes "meets the standard" wait on
research the docs call "not a gate"; and `conclude.rule_creates` still words
refusals for a persona with no full name or no word of kinship, which the
matcher no longer proposes. Bring each to the docs, or the docs to it.

### C61. The proof shows every conflict and argues the family links

`proof.fact_of` shows only the conflicts on a birth, a death and a marriage,
so the open name conflicts and the limits-of-one-life questions are invisible
and a name reads as meeting the standard with a conflict open;
`proof.agreement` returns nothing for parents, spouses and children; the
reason a record was taken as the person's (`proposal.decision_note`) is never
printed; the argument a fact is said to owe has nowhere to be written; and a
statement a re-read set and one a carry set read alike, their notes telling
neither.
Print every open question on the fact, the agreement on a family link and
the linkage reason, so the written conclusion is the reasoning and not only
the verdict.

### C62. Insert-only against REPLACE, and the archive's files against a rewrite

`INSERT OR REPLACE` rewrites a row of a protected table under the live
triggers (shown on a scratch copy on `audit_log` and `artifact`); with
`PRAGMA recursive_triggers=ON` it is refused, no connection sets it (ten
places open one), and `tools/check.py`'s insert-only check tries UPDATE and
DELETE alone. No tool replaces into a protected table today. Beside C31:
`treelib.archive_object` writes the object and its sidecar again whenever its
catalog lacks the row, before the commit, and removes nothing when the
transaction fails: 10 sidecars disagree with their row's `manifest_json` (7
on the trust tier, 2 on `redistributable`) and 7 objects on disk have no row,
2 of them the runner's. Nothing compares a sidecar with its row, no code
reads `schema/manifest.schema.json`, and 20 sidecars carry `T1/T2`, outside
its list. Refuse REPLACE whatever the connection (a trigger, or the pragma
set where every connection is opened) and check it; write an object and its
sidecar once, never over one that exists; compare sidecars with rows in
`tools/backup.py verify`; hold the manifests to their schema.

### C63. The screen shows the record it asks about

No route of `app/person/server.py` serves an archived object, so the card's
archived copy cannot be opened and an image cannot be seen while it is read;
and a conflict's resolution with its
reason, `reopen`, `place` (C12), `merge` and `link` have no control, while the
revise route takes a fetch step the page offers no control for. The key-fact route ignores the `conflicts` `facts.decide_fact` now returns, so the
screen never says what the rule decided on them. A person
who runs no terminal cannot finish a person's work on the screen
(`docs/DATA-ARCHITECTURE.md` §7 decision 17).

### C64. Links the database can check

`assertion.subject_id` is one column for seven kinds of subject, its
composite keys JSON; a card's person, persona and artifact are in
`proposal.payload_json`; a citation's identity is in `assertion.notes`, found
by pattern. `foreign_key_check` sees none of them (none dangles on 4 Oct
2026), and 93 `json_extract` calls across 11 files read them. Beside C29 and
C45: give each link the column it is, with its foreign key, a link at a time.

### C66. What the reading of an event's value per part leaves

`docs/RESEARCH-WORKFLOW.md` §5–7 (what of an event's value is accepted) reads
a date per part everywhere and a place per part where it is shown; five
places still read the value the event shows, and each change to them changes
what the rule decides, so each ends with a dry-run `reconsider` on a copy of
the live catalog. A place's point (`conclude.rule_points`, `ground`) needs an
accepted statement that gives the shown place whole, so a record agreeing
with an accepted place earns nothing where the event shows another on a
claim. The matcher compares with the shown values (`match.candidate`,
`compare`), so a reading that differs from the claims on both dates is a
hint, never a card, though it agrees with the accepted statements.
`facts.decide_fact` accepts the file's claim citing a held record with the
file's own value, so accepting a birth whose held census gives a calculated
year makes the file's day read accepted. The veto (`conclude.against`) never
reads a place the owner's own word gives, where `ground` and
`trusted_evidence` do. `Catalog.disagreements` never compares two places both
finer than the event's own. Beside them: `checklist.build` gives the field
for a country abroad the year's basis.

### C67. A document that came through the browser is marked so, and listed with what would replace it

`docs/DATA-ARCHITECTURE.md` §7 decision 20. On 4 Oct 2026 about 160 archived
files came through the owner's browser or by hand (FamilySearch 113, Find a
Grave 23), about 58 of them carrying an accepted person, and nothing lists
them: how a file came is read off whether its holder has a connector and off
the words of its run's note. Say on the run that archives a file how it came,
as a value (a connector's request; a page saved in the browser, by a hand, a
session or a model's task; a file given by hand; an import), the runs already
logged read by their holder; and give a read-only listing, for the tree or a
person: each document that came through the browser, its holder, collection
and record id, the people accepted on it, its source class, and what would
replace it: the original a derivative indexes (`data/evidence-classes.csv`), a
free holder that serves its collection through an endpoint
(`data/holders.csv`, the registry), and whether a copy from such a source is
already held (`same_record`). Where a replacement is a step a connector can
run, the plan carries it. Nothing is removed when a better copy arrives: it
joins the record, and the page saved in the browser stays beneath it.

### C49. An assumed birth year is no claim either

A death nobody stated is no longer searched for under the year an assumed
lifespan gives. The plan still gives every search step a `birth_year` worked
out as twenty years before the person's first dated event, with basis
`claim`: a year nobody stated, sent to a holder as if the file said it. Say
in `docs/RESEARCH-CHECKLIST.md` what a search carries for a person with no
stated birth (a window from the dated events, said to be one), and build
that.

### C14. The census before 1850 is held back only when its year is known

The rule's guard for a census that names only the head of a household
(`conclude.py`, the kind and year in `HEAD_ONLY`) passes a census whose year
is unknown, and takes the year from the collection's name by pattern when the
record gives none. A census the rule cannot date is not shown to be one that
names every member: hold it back until its year is read from the record, and
read the year from the record or its citation, never from a name's digits. It
changes what the rule takes, so it ends with a dry-run `reconsider` on a copy
of the live catalog.

### C34. What the comparison as data leaves

The comparison returns findings and the rule reads them. Left: four places in
`tools/cards.py` still read words (the stored rationale of a card an older
matcher wrote, a results row served as words, the card's own name note), and
`tools/conclude.py` reads the lines of `Catalog.disagreements` by pattern, a
comparison of its own that returns no findings yet. `place_verdict` says a
record's place agrees as coarser ("the record gives only New York") where
`place_given` finds its first part nowhere in the tree's place and says the
two do not agree (Manhattan, New York, New York against Brooklyn, New York):
one of the two is wrong. And no scenario reaches the residence-place test of
a relative's grounding: a reader left unconverted there was caught only by
the dry run on a copy of the live catalog.

### C65. What the comparison gets wrong about months, wives, the shown event and marked values

`catalog.date_verdict` compares two dates on the year unless both give a day,
so June 1901 and July 1901 agree, earn a point, raise no veto and no conflict,
and `fuller_date` lets the fold (`conclude.py`) and the import replace an
accepted "Jul 1901" with "26 Jun 1901", the silent overwrite hard rule 3
forbids: compare the months where both give one. `match.compare`'s `married`
(a wife under her husband's surname) checks no sex, so a man whose record names
his wife passes the surname gate: require a woman. `match.candidate` and
`cards.card` compare against the earliest event of a type, not
`Catalog.canonical_event` (Catharine Rittenhouse's death is shown at Norriton
and compared against Worcester), and neither leaves out an event whose
statements are all rejected. `match.personas_of` takes a name the page keeps
beneath the shown one as the record's own, and `Catalog.disagreements` folds
such values into a record's group: leave every marked value out of both.
`match.fits_by_name_and_year`'s docstring says a spelling variant of the
surname agrees and the code wants it exact: say which §0 means and make them
one. Each changes what the rule decides: a dry-run `reconsider` on a copy of
the live catalog first, after a matcher version rise run for real on the copy.

### C68. A unique match on a geocoder answer that was cut

`tools/resolve_places.py` asks the geocoder for six candidates and accepts a
string when one of them verifies fully, though a full page of six may be cut
(55 of the 751 cached answers hold exactly six; none of the 149 live unique
acceptances came from a full page). A match unique within a cut list widens
`CLAUDE.md`'s rule: ask again with a larger limit when a page comes back full,
and accept only on an answer that was not cut.

### C69. What a merge still leaves on the duplicate

A merge moves the duplicate's persona links, statements, memberships, steps,
questions and cards onto the kept person, but three things stay on the merged
row: an open question whose key the kept person already holds, in any status,
stays open on the duplicate (live on 5 Oct 2026: five, Matthew Ahern's and
Diane Ahern's death dates, Noi Davidson's missing parents, Daniel Davidson's
birth and death dates); a `person_persona` row whose persona the kept person
already links stays, so a decision on it can stay with the merged person (none
live); and the duplicate's name aliases are never moved (none live). Close or
fold the question as the kept person's twin, fold the link as a membership
the kept person holds is folded, move the aliases, and have the merge run
again on a pair complete an older one, as it now does for cards and
memberships; show the five live questions closed on a copy of the live
catalog.

### C70. The fetch list prints one page twice

Where two entries of `tools/fetches.py list` share a link and a file name (the
Pennsylvania and New Jersey church-register search and the Pennsylvania
marriages search for Enos Heebner Cassel, live on 5 Oct 2026), the list and
`next` print the page twice, so the owner or a model saves it twice. Print one
entry for one link, its steps joined, as entries that share a record are.

### C71. A child's membership does not say which parent the record names

`link_family` no longer puts a child named with one parent beside a partner the
record does not name, but the shape it leaves still misleads. A child's
membership statement does not say which parent its record names, so `ground()`
counts it toward both partners (36 file-claimed statements live on 5 Oct 2026
whose records name one parent); a family made for one parent carries no
statement on that parent's own membership, so `claimed_or_accepted` never reads
the link; the spouse path reuses a husband's one-parent family, which makes a
new wife the parent of his earlier children (Carol Evers under Dolores Evers);
and a child's one-parent family takes as second partner someone named for one
child only. Six live memberships the old fallback wrote stay where it put them,
since no tool moves a child out of a family: Cassie, William Rhea, Charles
Beckham and Corinne Davidson in John Y Davidson and Lena Howard Bell's family
(the 1900 and 1920 censuses and the NUMIDENT, which name John Y alone), Joanne
and Dolores Evers in John Evers and Dolores Evers's (the 1950 census). Beside
C5, which asks what grounds a parent-child point: have a child's statement name
the parent its record states, give a one-parent family its parent's
membership, keep the spouse path off a family that holds children of one
parent, and give the owner a tool that moves a child to the family the record
supports, shown on the six above on a copy of the live catalog.

### C72. A re-read writes links with nobody going over them

`extract.carry_links`, which carries a decision onto the record's new reading,
writes statements and family links without regenerating the people's plans and
without the rule's pass over their conflicts and cards (`conclude.settle_people`),
which every decision now runs. Run it for the people a re-read touches.

### C73. Index entries of one census page are one household

FamilySearch indexes some censuses one person to a page with no household
table (the New York State Census 1925 among them: "No similar records were
found"), and each entry's citation gives the enumeration district, page and
line. The reader keeps none of these, so two entries of one household are two
unrelated records: Ruth Peters, daughter of the head, age 4 (KS4R-RTQ, page 19,
line 25), and Mary Peters, wife of the head, age 38 (KS4R-RTM, line 23), both
Hempstead A.D. 01, E.D. 06, archived 5 Oct 2026, are each a card, Ruth's short
of a point and Mary's on a name not yet accepted, though the page shows the
household the file claims. Read the place, district, page and line of such an
entry as its record's identity on the page; join the entries of one page and
household (the same district and page, lines in one run under one head) as one
household record, each member's relationship to the head read together as a
census states them (the wife and the daughter of one head are each the head's,
never stated as each other's), so the ground for a household whose members fit
(section A, the relatives named in part) can read them; and make the head's
entry, found by the search that listed the others, a lead. Show it on the two
pages above and the 1925 search page that listed seven Peters of Hempstead.

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
