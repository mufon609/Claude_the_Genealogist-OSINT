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
**D — Decisions wanted from the owner** (first in the file: a question only
the owner's word settles, one short paragraph saying what is asked and what
each answer changes; the work it unlocks stays in its own section under a
`**Blocked by:** D<n>` line, and the entry closes when the answer is written
where it belongs, the lines naming it going with it),
**A — Priority sequence** (ordering / coupling constraints),
**B — Parallel batch** (items that only make sense shipped together),
**C — Anytime** (no upstream blockers in the code; an entry may wait on an
owner's decision in D). **Default focus is C:** no dependencies,
finishable in one pass. Reserve A and B for sessions scoped
to them — starting a constrained item out of order half-bakes it and
clutters the file. Cross-reference entries with `**Blocks:**` /
`**Blocked by:**` lines so the dependency graph stays inline.

**Identifiers** (D1, A1, B1, C1…) are positional working labels, not stable
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

## D. Decisions wanted from the owner

Questions only the owner's word settles. Each says what is asked and what
each answer changes; the work it unlocks stays in C under a
`**Blocked by:**` line naming it.

### D1. What a parent–child point stands on

A record stating that someone is a person's parent counts as a point only
where the tree already holds that link. Today either family membership
carries it, the child's or the parent's own as partner, so a parent's
accepted marriage stands in for a child's parentage. If the child's
membership must carry it (alone, or with the parent's partner row): on a
copy of the live catalog of 3 Oct 2026 requiring both rows withdrew 14 of
the rule's decisions, among them Dan Davidson on his mother's obituary,
which names her alone, and Mary Castello's 1917 death-index card. If either
membership, as now: nothing is withdrawn. Either way, say how a record that
names one parent counts. Unlocks C4.

### D2. The claimed-relationship route once the name is held

The rule takes a person on a record through a relationship the record states
to someone already accepted on it while the person's own name is not yet
held on trusted ground. Once the name is held, the record is judged on its
points, and a reconsider withdraws what the route took (scenario 60: Robert
Davidson's 1940 census, after the Ohio death index is accepted). If the
route stands whenever the points fall short, as the 15 Sept ruling's "a
person the file claims" reads: more ground never takes back what less
allowed, and `docs/RULE.md` says so. If not: the docs stand as written, and such
decisions are withdrawn as the name becomes held. Unlocks C33.

### D3. A conflict one side of which rests only on claims and editable pages

The rule settles a conflict only when the side it keeps holds primary
information. If a side resting on records nobody can edit, agreeing with
one another, also outweighs a side resting only on the file's claim and
pages anyone can edit (the owner's own accepted word never outweighed):
John Y Davidson's birth settles as April 1875 (the 1900 census, his 1946
death certificate) against 24 April 1876 (the file, three Find a Grave
memorials), once his gravestone photograph is read, and such conflicts
leave the owner's list. If not: they stay the owner's, as today. Unlocks
C21.

### D4. A place written one letter apart

A surname one letter apart agrees as a spelling variant; a place has no such
rule (the resolver offers a close spelling on its card, marked near, and
verifies nothing). If a place string one letter or one space apart from a
resolved place's name, in the same state and county where the string gives
them, agrees as a variant:
Frederick Michael Ahearn's draft card ("North Hampton, Massachusetts"
against the tree's Northampton) is taken when its other points hold. If
not: such a record stays a card. Unlocks C10.

### D5. A fact the current reading of a record no longer states

A page read again by a newer reader can drop a fact the older reading
wrote, and the accepted statement on it stays, resting on the superseded
reading (`catalog.statement_of`). If such a statement is withdrawn with its
reading: a re-read takes back what its reader no longer finds, as it did by
hand for Noi Davidson's Military Service "MSGT US AIR FORCE", which the
gravesite locator's newer reader gives to her husband. If it is kept as the
record's word: it stays until a person takes it back. Either answer is written into `docs/DATA-ARCHITECTURE.md`
and the re-read does it. Unlocks C27.

### D6. The circumstances under which a record misstates a date on purpose

The owner asked for the structure ("this project needs a database of
circumstances where we could possibly see contradicting information in
primary sources"). The design that waits on their word: `data/circumstances.csv`,
reference data for any family (a circumstance, the record kinds and field it
touches, the direction and usual size of the misstatement, the condition
that makes it likely, the records free of it, sources checked); a date
conflict that fits a row names it; the rule never settles such a conflict
for the record made under the incentive; the row's research lines become
leads. If accepted: written into `docs/DATA-ARCHITECTURE.md` §7 and the
proof standard, then built. If changed: the design follows the owner's
words. Unlocks C32.

### D7. A document's topic

The catalog classes evidence by the kind of document and its trust, never by
the part of a life it reveals. If each record kind or fact type carries a
topic in data (military first), a person carries the topics of their
accepted records, derived and never typed, and each topic names the record
sets it leaves for the person and their close family as leads: Raymond Earl
Davidson's service records are sought for him and for Noi Davidson as a
veteran's wife, and her Military Service event is answered. If not: the
loop finds records by kind alone. Unlocks C35.

### D8. What "the loop works" means

The goal says what the system is for and not what reaching it looks like,
so progress is read off commits. The owner names the state that counts as
the loop working: for instance people and documents brought by evidence
rather than the file, turns run without a session, what still reaches the
owner and why. The answer is written into `README.md` beside the goal and
`tools/tree.py overview` prints it. Unlocks C42.

### D9. How a page two trees hold is read

Hard rule 4 gives every import its own extraction; `docs/DATA-ARCHITECTURE.md`
§4a makes fetched pages shared evidence. If each tree reads a fetched page
on its own: extraction and persona carry a tree, as an import's do. If the
trees share one reading with their decisions apart: extraction and persona
stay without a tree, and every reader that joins `person_persona`,
`proposal` or `search_plan` is scoped to its tree, so a second tree's
re-read never resets the first tree's cards. Unlocks C8.

### D10. What the harness may write by hand

`docs/DATA-ARCHITECTURE.md` §7 decision 8 lets the harness simulate a
holder's failure to answer and nothing else, yet scenarios log `none` and
`found` runs no holder gave and plant rows in a writer's shape. If decision
8 stands: each such run is answered by a real run, or a holder's silence
where the path allows, and each planted row is reached through the tool that
writes it. If decision 8 says a run written to reach a path is the harness's
bookkeeping and no answer: the scenarios stay and the docs say so. Unlocks
C26.

### D12. A family-held photograph as a fixture

The two family-held photographs a scenario drops into the inbox are a
stand-in file; the photographs the archive holds are marked private. Hard
rule 7 lets any archived document the owner chooses sit in `tests/`. The
owner names one, and the stand-in goes. Unlocks C25.

### D13. How many branches the loop works at once

The queue names one person, the next at the edge of the confirmed tree from
the home person, and the runner takes one turn at a time. A tree with several
roots (the file's people not reached from the home person; forty-five
presidents in one tree) on a machine with cores to spare could work several
branches at once. Asked: whether the number of branches worked at once is a
setting of the tree (one, as now, the default; N, each branch a turn of its
own on a connection of its own), and what a branch is (a root's confirmed
line; the home person's line and each of the file's others; a generation).
What each answer changes: with one, nothing; with N, two turns must never
write one person (a decision, the rule's re-examination, the plans
regenerated), so the queue would claim a person for a turn and a turn's
transaction would hold its writes, and SQLite serialises writers, so the gain
is in the fetches and the reads until Postgres. The analysis first, before the
setting is designed: a turn's time by phase (fetch, read, match, rule, settle)
measured on the live tree and on the second family, and where parallel turns
would gain.

### D14. DNA as an evidence class

Six DNA sources are registered (`data/data-sources.csv` P01–P06) and no
evidence class reads a DNA result, so a claim that rests on one (a maternal
line's haplogroup settling which of two women was a person's mother; a
shared segment between two testers) is a hint and never evidence, and the
conflict it would settle stays the owner's. Asked: whether a DNA result is an
evidence class at all, and of what (a relationship point between the two
people tested, or a line's descent; never a name or a date); what document
the archive holds for it (the raw file the owner downloads, a match page, a
published study); and its standing as the field reads it (original, primary,
indirect). What each answer changes: with no class, nothing, and the proof
says of such a conflict that no held record decides it; with a class,
`data/evidence-classes.csv` takes the rows, the proof reads them, and the
rule's conflict test says whether it may weigh one.

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
5. **The other kinds.** A search at a holder without a connector (C45: its
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
to the head is on their own page of the census (C30); a state index's line of
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
and 301 `none`, 236 of those with no request sent (C9); 159 files
archived and 860 personas read, nearly all names in a book's running text;
one record taken by the rule, none of the 62 waiting cards answered, and 3
new cards, each a namesake's profile at WikiTree. Re-reading the 106 waiting
place strings with the current resolver settled 6 (state abbreviations and
one village the gazetteer knows): the cards were written by the resolver's
first version, and nothing re-reads a string an older version left open, as
`tools/extract.py --stale` re-reads a page.

The work, a class at a time, the docs first (`docs/TERMS.md` §0, `docs/RULE.md`,
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

### A3. A record is read by its form, and a household is read off the form

`docs/DATA-ARCHITECTURE.md` §7 decision 21. The forms are data
(`data/record-forms.csv`, every federal schedule 1790 to 1950 and the New York
and Massachusetts state censuses, read through `tools/forms.py`; the checklist,
the footprint and the rule's census test read it), and the readers keep every
locator an entry carries as its place on its page (`persona.region_json`:
`{"form", "locators"}`; the FamilySearch record reader 0.8.0, the NARA 1950
reader 0.2.0, the transcription's sheet, dwelling and family); the held pages
were read again on the live catalog on 5 Oct 2026. Measured then: FamilySearch
gives every member of a federal household the page person's own line (the 1900
Lukens sheet image has Milton on line 4 and Charlotte on line 7, the page says
line 10 for all), while its household identifier matches the family number;
the 1925 New York pages carry page, line and districts and no image
identifier, their "View Original Document" control being a button with no link
beside one to Ancestry, so their image's own index cannot be reached from them;
no source opened documents page and line numbering for New York 1855 to 1915 or
Massachusetts, whose rows key a page by its image; the one census image held
(the 1900 Lukens sheet, `c7cebd8b`) is FamilySearch's, archived under an
Ancestry citation, and four FamilySearch record pages and all thirty census
search pages are filed under Ancestry collections. Left, one piece closed
before the next:

1. **What finding the missing entry leaves.** A household not wholly held
   leads to its missing entries (`tools/households.py`: its search's answer
   page by page, then the record of each row that could be one, one at a time
   in a stated order). Left: FamilySearch's paging (`count`, `offset`) is
   unconfirmed until a second page is saved; no head's page is held, so a
   household completed is shown nowhere; once the head's page is held it is
   matched against the household's members only, never against the person the
   tree claims in the head's place (Fredrick C Peters), which waits on point 3;
   `catalog.same_given` does not agree "Fred" with "Fredrick" (the nickname table
   is not read through spellings), so the claimed relative never orders a
   candidate live; FamilySearch's image index has no reader; and
   `checklist.names_parents` reads no state census row.
2. **Calibration, the special cases found.** A reading task (BACKLOG A1, the
   reading kind) run on the held records of each form, compared with the
   script field by field and household by household, more than once; each
   difference a special case fixed in the script or the form's row, or put
   down to the model (the repeated line above is the first); the row records
   the runs. Until a form is calibrated the rule does not count its
   households.
3. **The rule reads the household.** With section A2's household ground: a
   member's relationship to the head is the census's statement, the
   household's fit with the tree's family a ground the rule counts (a dry
   run on a copy of the live catalog first). Ruth M Peters and Mary Peters
   are the first to show it.

Beside it: the transcription form (`app/person/read_record.md`, the screen)
does not ask for the sheet, dwelling or family the reader now keeps; the
Ancestry index reader, which no real page reaches, still drops its locator
labels; and FamilySearch's search rows carry no locator at all.

### A4. Two people's relationship, through accepted links alone

"Are these two people related?" is the second family's first question, and
nothing answers it: the proof reads one person's key facts, the overview one
line. `tools/kin.py "<person>" "<person>"`, read-only, in layer 4 beside the
proof: the path between the two through the family links the tree has
accepted (the accepted memberships, as the queue reads the confirmed tree's
links through `Catalog.family`; never a claim, a sibling placement, an
editable page's link or a link a withdrawn decision left), printed one link
per line with the two people, the relation, the record the link rests on and
the proof's reading of that record (its classes, and whether the source is
one the rule trusts), the relationship named in words at the end (second
cousins; first cousins once removed; related by marriage through a named
couple), and the chain's own standing, which is its least-proven link's. When
no accepted path exists the answer is never "no": the nearest path the file
claims is printed with each link not yet accepted and what would prove it
(the records the checklist names for that link), so the owner reads what is
owed. Several paths: the shortest by links, among those the one whose weakest
link is strongest; `--all` prints the rest; `--json` the chain. A
relationship by marriage is a path through a spouse link and is said so.
Scenarios on the harness family: a pair joined by accepted links alone, a
pair joined through a claim, a pair with no path, a pair joined by marriage,
two paths of unequal standing. The docs: `docs/RULE.md`'s proof section gets
the paragraph with its own identifier, `schema/README.md`'s table the row,
`CLAUDE.md`'s command block the line. **Blocks:** the second family's
question (C20's family, and the presidents' chains after it).

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

## C. Anytime (no dependencies in the code)

No upstream blockers in the code; safe to pick up in any session. Default-focus tier. An entry that waits on the owner's word says so with a `**Blocked by:** D<n>` line.

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
fetched. On the live catalog of 9 Oct 2026 the open New York marriage rows are Carol
Evers and Frederick Micheal Ahearn Jr's (a fetch blocked at the cited index)
and John and Dolores Evers's (a search only). The
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

### C3. Confirm the shadow-root save on archive.org

`tools/save_page.js` serializes the page's open shadow roots as declarative
shadow DOM (`getHTML` with every open root) when its plain copy comes out
nearly empty, the way archive.org's pages do (the plain copy holds only the
site's "Javascript is required" fallback). No browser was connected when it
was written, so it is untested on the real site: in the next browser session,
save one archive.org page the fetch list names (`[any page: save_page.js with
true]`) and check its one line and the saved file's text. If the line still
says `EMPTY` (closed shadow roots, or content drawn in a canvas), make those
steps assisted with the page's own link and say so in
`docs/PLAN-AND-SEARCH.md` §4.

### C4. A relationship point stands on either membership of the family

`rule.rule_points` grounds a stated relationship on the accepted statements
of either membership joining the two people (`ground` over both rows), so one
person's link stands in for the other's: a parent's accepted marriage grounds a
child's claimed parentage. `docs/RULE.md` ("What the rule counts")
says a point rests on the tree's statement of that very link. Requiring both
rows withdraws decisions that are sound, because the tree states a couple's
parentage partly on partner rows: Francis Thomas Ahearn's 1904 birth record
(his own card, his father's and his mother's), Dan Davidson on his mother's
obituary, and Mary Castello, created as the bride's mother from the 1901
marriage index, whose partner row carries that parentage. Ground a link on both
memberships, and count a record that names both parents of a child against the
tree's accepted couple as that couple, so those stay taken; show both on
the Ahearn and Davidson records above.

Measured on a copy of the live catalog of 3 Oct 2026:
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
marriage's evidence a condition of every parentage point. What grounds a
parent–child point, and how a record naming one parent counts, is D1; the
work follows its answer, on a copy of the live catalog first.

**Blocked by:** D1.

### C5. Rule paths the harness no longer exercises, for want of a real record

**Harness gap**, one of seven (C5, C8, C20, C25, C26, C41, C43); the second family in the harness (C20) is the scenario they share. This one waits on real records, which a second family's export would bring.

The pure name rules need no record: `tests/fixtures/rules.json` holds
examples of `catalog.same_given`'s nicknames and initials, `name_words` and
`split_persona_name`; `same_given`'s one-letter slip, `same_middle` and
`middle_differs` take theirs there too, which covers the name side of the
garbled-initials and short-form paths below; the rest of this entry waits on
real records.

When the harness became data (no invented test data, no names in the
harness code), every scenario that only a planted person or a made-up
record could carry was dropped rather than faked. Each is a path the code
still has and nothing now tests: an in-law resolving to a real link
through the relative it names; the spouse fit where the other party
carries another name; the fitting check on garbled initials and on a
short-form given name; the matcher's window on a birth year
(`matcher.WINDOW`: a persona born more than three years from a candidate of
the same name is never a near match, which only a results page's rows
carried, and no row is a card now: the 1900 Lukens household, Annie against
her mother, needs the parents in the harness cut); a namesake's kin shown as a
hint; the New Jersey death index's birth or death with no
month or day (`readers.nj_date` keeps the year alone), which no row of the
2006-2017 file has, every one of its 837,351 rows carrying both dates whole; the
unnamed fetch's own naming
(`fetch_list.save_as`'s holder-and-piece-and-six branch), now that the two
citations that carried it (the New Jersey and New York marriage indexes) are
both blocked as `scanned_index` holders; the merge's reach by name and year;
a memorial's listed relative whose one fit moves to another person between two
acceptances (`decisions.link_family` withdraws the earlier undecided trace); a
merge folding a family whose child the kept family already holds, and a merge
completed (`merges.complete_merge`) folding two same-partner families; the
0.7.5 migration restoring a row an older decision wrote over (a page naming one
person twice, each persona decided, which no current parser writes); the import
folding a person's own repeated facts, and taking a fuller date onto an event a
coarser fact began (the cut holds only the Ahearn couple's repeated 1901
marriage, the couple's own first; Catharine Rittenhouse's births of 12 and
13 January 1772 and Abraham Wiegner Heebner's two of 28 Dec 1766 lie outside
it); a family fact equally close to two of the couple's events, raised by
`Catalog.unplaced` and placed on a family's event by `decisions.place` (no
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
being unresolved strings; the rule's identity tests (`rule.identity_refused`)
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
reason names the record's word for the daughter (`rule.rule_creates`); and a relative's
persona whose birth place differs from a finer one another decision gave the
tree's person, which the rule reads as fitting all the same (`matcher.compare`
with `birth_place=False`): the harness's places for Robert Edgar Davidson's
birth stay unresolved strings, so no scenario reaches the Auburn the live
catalog holds against his obituary's Woodburn. No scenario reaches a statement carrying a mark on a birth, a death, a burial
or a death place: every value FamilySearch keeps beneath a shown birth or death
date in the fixtures says the same as the shown one and is no fact of its own,
so neither the date and place veto skipping an accepted value a page keeps
beneath (`rule.against`) nor the identity naming one it left out
(`rule.event_claimed_or_accepted`) has a record to run on; nor does the
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

### C6. Hints on the person page

A run that found pages naming the person on the name alone (a directory
line, a book mention, a newspaper hit) leaves them held under the step, and
the personas it read stay on the page with no proposal, as
`docs/TERMS.md` §0 defines a hint. The record view marks each
such persona that is a hint for a reviewed person with what agrees and what
is missing (`cards.hints_on`), but only once that record is opened from the
step's log: the person page has no place where a reviewed person's hints
across all their held records are kept, as `docs/TERMS.md` §0 says they are. Add one, each
hint with what agrees, what is missing and the page, for research when the
leads run dry, never as a feed.

### C7. A connector for the Pennsylvania Newspaper Archive

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

### C8. Tree isolation has no harness, and some readers ignore the tree

**Harness gap**, one of seven (C5, C8, C20, C25, C26, C41, C43); the second family in the harness (C20) is the scenario they share. This one waits on it: two trees need a second family.

Every scenario builds one tree, so nothing shows a second tree over the same
archive ignoring the first one's decisions (`CLAUDE.md` hard rule 4).
`catalog.page_groups` reads `assertion` over every tree's citations, and
`extraction` and `persona` carry no tree: `readers.extract` supersedes the
current extraction of a page and rejects its undecided proposals whichever
tree they belong to, so a second tree reading a page the first holds would
reset the first tree's cards. Read a page held by two trees as D9 settles,
write a scenario with
two trees and one archived page, decided in the first and undecided in the
second, and scope every reader that joins `person_persona`, `proposal` or
`search_plan` by artifact or persona to its tree. Three more places cross
trees: a place card is written under the running tree for a string every tree
shares (`tools/resolve_places.py` takes the strings no resolver has read, so
a second tree sharing an undecided string gets its words and no card);
`reset_ai_resolutions` resets shared strings and clears `event.place_id` in
the calling tree alone; and `app/person/index.html` never sends `?tree=`, so
the screen serves the active tree only.

**Blocked by:** D9 for the reading of a shared page; the three places above
are not.

### C9. A run says what it asked

A run's log row is the catalog's word that a holder was asked and what it
answered, and the proof standard's reasonably exhaustive research can be read
only from `search_log`. Today a run can say `none` where the holder was never
asked, or asked in part, and the step closes at that source. Each connector
asks over the years and fields it can answer and says `none` only for those;
the row says what was sent, what the holder reported, how much was read and
whether the list was cut.

- **The log.** `search_log` records no request sent, no total the holder
  reported, nothing about how many were read, and no truncation (a total
  lives in free-text notes cut at 1,000 characters, `run_step.py`). Live on 4
  Oct 2026, 89 of the 140 connector runs logged `none` sent no request at all
  (a field the source wants was missing, or the person's years lie outside
  it), told apart from an empty answer only by the note. The connectors stop
  early and say nothing: `connectors/ia.py` reads five items and three pages
  of each, `wikitree.py` five profiles, `loc_gov.py` the first twenty results
  with no next page, `ia_directories.py` six towns, and `plan.py` puts at most
  twelve footprint records on a plan. `found` means a hit's record arrived,
  not that a persona was put to someone: 42 of the 44 `found` runs at the OCR
  and WikiTree sources on 4 Oct led to no proposal and no link. And
  `log_search.same_fields` leaves `surname_variants` out, so a spelling
  learned later never asks a source again. Give the log the request, the
  holder's total, the number read and whether the list was cut, as columns;
  log a cap as a cut; let `found` mean a persona the matcher put to someone,
  the rest `none` with the page held; and count the variants as fields.
- **A run of several requests, one unanswered.** A run whose step carries
  one place name, or none, can still send several requests:
  `connectors/ky_vital_index.py` asks one year's file at a time over the
  step's years. One year's file unanswered (a timeout, a refusal) and another
  answered with no row under the surname is logged `none`
  (`run_step.outcome_of`: errors and an answer), and `log_search.same_fields`
  reads the run as the step's own fields, so the step is closed though one
  year was never read. The runner marks only a place name whose request got
  no answer (`unanswered`). Mark the run's unanswered requests whatever made
  them, so the next turn asks again, and show it on a Kentucky index step over
  two years. The same where some hits arrived and others did not: a 1950
  district search whose neighbour's schedule arrives while the household's
  own times out is `found` and closes the step, the lost name logged
  unanswered and never asked again; a run is `found` for the step only when
  the hit that answers the step's own person arrived.
- **Connectors that never looked.** `connectors/nj_death_index.py` reads the
  2006–2017 file alone, but the registry's coverage (C09, New Jersey
  1848–2017) is what lets a step ask it, and the connector checks no year:
  Dennis Scannell and Mary Castello are logged `none` there and never asked
  again. `va_graves.py` asks the middle initial as "begins with", so a
  veteran indexed with none is missed; `ky_vital_index.py` takes a year equal
  to the birth year to mean the birth index, so an infant's death is looked
  for among births; `loc_gov.py` asks the death year alone where the gate
  allows that year and the next. Wire the New Jersey 2001–2005 file or refuse
  the step before it, and ask the two live `none` runs again. Every New
  Jersey step also downloads the 69 MB file again: cache it as C16 says for
  Kentucky.
- **A challenge page read as an empty answer.** A JSON connector raises on a
  challenge or maintenance page served with status 200 in place of its
  answer, and the run is logged error (`run_step.unreadable`). The CSV and
  HTML connectors read such a page as an answer with nothing in it:
  `nj_death_index.rows` and `ky_vital_index`'s readers find no row under the
  surname, `va_graves.total` gives None and `results` an empty list where the
  page lacks its table. Give each such connector a test that the body is its
  answer (the index file's header line, the year file's layout, the gravesite
  page's own result or no-result markers), raising when it is not, so the
  page is an error run and the step is asked again; show it on loop `106`'s
  turn, where New Jersey's index and the gravesite locator log `none` on the
  harness's challenge page.

### C10. A place written one letter apart disagrees

Frederick Michael Ahearn's card on his WWII draft registration card
(FamilySearch, ark `Q2SN-6M4R`, cited by the file) agrees on the name and the
birth day and disagrees on the birth place: the record writes "North Hampton,
Massachusetts", the tree has Northampton, Hampshire County, resolved and
accepted. The resolver offers such a close spelling on its card, marked near
and verifying nothing (`docs/DATA-ARCHITECTURE.md` §8, `resolve_places.near_name`),
but `catalog.place_verdict` (which `tools/match.py` uses) counts two places the
same only when both resolve to one place or one is a dated name of the other,
so the disagreement stands and the rule leaves the record a card. Once D4 is
answered, write the rule into the docs and the matcher applies it. Until then
such a record is a card.

**Blocked by:** D4.

### C11. The person screen has no control for a record's unplaced fact

`Catalog.unplaced` raises an accepted record's fact whose event is the owner's
choice (an undated fact among several events of its type, a dated one equally
close to two or more, one of a type a life holds once that fits none of
several, an attribute's fact, a family's fact) as a conflict question, and only `tools/conclude.py place` answers it. Show the question on the person screen
with the person's events of that type to choose from, writing through
`decisions.place` with its audit row, as the living line's control writes
through `decisions.living`.

### C12. A connector for Open Archives, the Dutch records

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

### C13. A family's own facts in the file lose their place

`tools/ingest_gedcom.py` writes a FAM record's own MARR (or DIV, ENGA, ...) as
an event whose statement carries no persona fact, a family being no persona:
its date stands only as the event's own value, and its PLAC becomes a place
string nothing points to, so the file's place for the couple's marriage is
lost (the Ahearn couple's own 26 Jun 1901 at Northampton reads placeless), is
never compared by `Catalog.disagreements` and never resolved, and the fold
reads it as absent, joining any marriage of its year. Write the FAM record's
facts as persona facts (on each partner's persona, as an Ancestry INDI-level
MARR already is), so the file's date and place are statements like any other.

### C14. A connector for the New York State death index

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

### C15. One connector for CONTENTdm collections

The Tennessee Virtual Archive (death certificates, marriages, births), Ohio
Memory and the Alabama archives (L04) all run CONTENTdm, whose JSON search
(`/digital/api/search/collection/<alias>/searchterm/<term>/...`) answers a
declared tool. Tennessee's death certificates are titled by certificate number,
reached by name only through annual index volumes (1950–1974 found), so the
step is two hops: the index volume for the name, then the certificate by
number. Build one connector for the shape when a reviewed person's
Tennessee or Ohio step needs it.

### C16. A year-filed index read by byte range, and asked with the event's year

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

### C17. Reasonably exhaustive data for every place a family names

`data/jurisdictions.csv` holds the places this tree's research has needed:
seven states' statewide registration, two states' censuses, four countries'
church holders and civil registration. Any other place gets its rows with no
holder. Fill the table for every US state (statewide birth, death and marriage
registration years, state censuses, the holders that index them) and for the
countries emigrants came from, from the FamilySearch Research Wiki and the
state archives, each row citing where its years come from, with a registry
row for each new holder; then a family from anywhere gets a full checklist.

### C18. Place overrides belong to the tree

`data/place-overrides.json` holds this tree's own strings (the Berthelsdorf
review, the Silesian notes) in a file every tree reads. Read a tree's own
overrides from `trees/<slug>/` beside a shared file of corrections true for
any tree (a place string meaning no place), and move this tree's entries
there; the place scenarios plant their own.

### C19. Citations from exports other than Ancestry's

The planner turns a citation into a fetch step through Ancestry's own record
id (`_APID`) and `data/holders.csv`'s map of Ancestry collections to free
holders. A GEDCOM exported from FamilySearch, MyHeritage, Gramps or by hand
cites its sources otherwise: `ingest_gedcom.py` keeps a citation's record id
and URL only when it carries an `_APID`, so its citations make no fetch steps,
build no footprint, and the checklist reads a record the file cites as missing. Read the citation forms those exports write (a
FamilySearch ark in a citation, a URL, a source title with a page), and route
each to its holder.

### C20. A second family in the harness

**Harness gap**, one of seven (C5, C8, C20, C25, C26, C41, C43); the second family in the harness (C20) is the scenario they share. This is that scenario.

The harness runs on a cut of the owner's export, by the owner's ruling (no
invented people or records), so nothing proves the tools on a family with
other places, other denominations and another export's citations. The second
family is the Lincoln tree: a claim file written from three published charts
(UsefulCharts' Abraham Lincoln, Roosevelt and "Are all the US Presidents
related?" videos), its people public figures, so the file may sit in `tests/`
(the charts' own text stays out of git), worked in a data root of its own
(`DATA_ROOT=/home/neural/Desktop/lincoln`, a live catalog of that tree's own),
never a tree in the family catalog while D9 is open. Add a scenario that
ingests the claim file beside the harness tree, builds its checklists and
plans, and shows nothing of the first family reaching the second (the
tree-isolation entry above). The harness is narrower than `tools/check.py`
and `tests/checks/scenario.py` say ("another family's export runs
unchanged"): the walker names people under the `ancestry_gedcom_xref` id
system alone, `a_file_family` writes that system and "Ancestry member tree
(no citation)" by hand, and `check.py` names its fixtures and source ids; a
second family's file from another origin needs those read from the import
first.

### C21. A conflict one side of which rests only on claims and editable pages

The rule resolves a conflict only when the side it keeps holds primary
information (`conflicts.classes_decide`), so John Y Davidson's birth date stays
the owner's although 24 April 1876 rests only on the file's claim and three
Find a Grave memorials while Apr 1875 rests on the 1900 census and his 1946
death certificate, records nobody can edit. Write D3's answer into the docs
(§7 decision 9 reads contested classes toward the owner, and the owner's own
words put the human only where doubt is serious); then the rule applies it,
reasonably exhaustive research first: his memorial shows a gravestone
photograph not yet held (photo 102379026), which may carry 1876 itself.

**Blocked by:** D3.

### C22. A held image nobody has read is research waiting, not held

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

### C23. An import from anywhere is read as itself

Beyond citations: the gazetteer routing for Ireland, Germany and Poland, the
Silesian place rules and the church denominations are written in code
(`resolve_places.py`, `catalog.py`, `checklist.py`, `footprint.py`). Read the
routing and the denominations from data, as `data/jurisdictions.csv` already
carries which records exist where. And an unresolved place string that names a
US state anywhere in it is read as American even when its last part names
another country ("Washington, Tyne and Wear, England": `Catalog.place`): read
the country the string ends with first.

### C24. A key fact resting on a withdrawn record asks nothing of the person

A file withdrawn by `tools/tombstone.py` is evidence for nothing, and the proof
says so, but `Catalog.basis` still reads a key fact accepted when its only
accepted statements rest on that file, so the overview, the queue, the
checklist and the person screen show it accepted and no question reaches the
person; the owner learns it only from the withdrawal's printout or the proof.
Raise a question on each person whose decided key fact or accepted record
rests on a withdrawn file, asking the owner to take the decision again
(`docs/DATA-ARCHITECTURE.md` §2: a decision on it stands until a person takes
it again). And the owner's own word (`facts.vouch`) is written on the tree
file's persona, so withdrawing an imported file would make every vouch on it
count for nothing: have the tombstone refuse a file a tree imported, or keep a
vouch standing whatever its carrier.

### C25. A family-held photograph in the harness

**Harness gap**, one of seven (C5, C8, C20, C25, C26, C41, C43); the second family in the harness (C20) is the scenario they share. This one does not wait on it: it waits on the owner's photograph.

`decisions/95-cited-on-the-owners-word` drops two family-held photographs into
the inbox, and the harness writes the smallest of JPEG files for them, the one
stand-in file `tests/fixtures/README.md` ("What is simulated") still names. The
only family-held photographs the archive holds are marked private and never
redistributed; hard rule 7 lets the one the owner chooses sit in `tests/`. Once
the owner names one (D12), archive it as a fixture with its
manifest, attach it in place of the stand-in, and drop `stand_in` from
`tests/checks/scenario.py` and the README.

**Blocked by:** D12.

### C26. Runs that stand for an answer no holder gave

**Harness gap**, one of seven (C5, C8, C20, C25, C26, C41, C43); the second family in the harness (C20) is the scenario they share. This one does not wait on it: it is the harness's own runs.

`docs/DATA-ARCHITECTURE.md` §7 decision 8 lets the harness simulate a holder's
failure to answer and nothing else, but a turn scenario's `fake_run` logs `none`
with no request behind it by its default (loop `12`, `13`, `111`, `112`), and
the `log` action writes `none` and `found` runs by hand (decisions `60`, `90`,
`90a`, `99zd`, `99zp`, `99zzt`; loop `10`, `31`, `32`, `46`, `50`, `63`, `70`,
`72`, `101`, `123`, `125`), each the catalog's word that a holder answered
nothing, or answered, where no holder did. `tests/fixtures/README.md` lists
them. As D10 settles: answer each with a real run (the connectors through
`run` on the archive's own answers, a saved page through `save` and
`collect`) or a holder's silence where the path allows it, or write into
decision 8 that a run written to reach a path is the harness's bookkeeping
and no answer. The same
holds for the actions that write catalog rows by hand in the shape a writer of
the tools writes them (`a_step` in 27 scenarios, `a_place_card`,
`a_file_family`, `a_persona_link`, `a_legacy_card`, `a_event`, `a_question`,
`a_merge`'s `older` (a merge put back in the shape an older tool left it),
and `older_reading`, which plants a reading an older reader made as the live
catalog holds it):
when the writer changes, those scenarios go on testing rows the code no longer
writes. Reach each through the tool that writes it.

**Blocked by:** D10.

### C27. A fact a reading no longer states stays on the person

A page read again by a newer reader can drop a fact the older reading wrote,
and the accepted statement on it stays: `catalog.statement_of` reads a
statement through the record's current reading and falls back on the
assertion's own reading where the current one has no such fact. The gravesite
locator's reader now gives a dependent's row's rank and branch to the veteran
the row names; Noi Davidson's two pages of the locator, read again, left her
Military Service "MSGT US AIR FORCE" accepted on the superseded readings until
a session rejected both statements on 3 Oct 2026. Write D5's answer into
`docs/DATA-ARCHITECTURE.md` and have the re-read do it; show it on that page.

**Blocked by:** D5.

### C28. Objects a check run archived into the live archive

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
correct the README rows that rest on those copies. Read-only on 9 Oct 2026:
no artifact row says `agent:check`; 10 of the 15 objects have rows under
another retriever, cited by search-log rows, and 5 have no row. A tool refuses a `--db`
outside its data root (`treelib.in_data_root`) and every check runs under a
scratch `DATA_ROOT`, so this entry is the cleanup alone.

### C30. A FamilySearch household page saved with every member's details open

A census states every member's relationship to the head, but a FamilySearch
record page shows that column only in each member's own details table, which
the page keeps closed until its "Open All" button is pressed. Of the twelve
census pages in the archive, one (the 1900 Lukens household) was saved with
every member's details open; on the rest the column shows for the page's own
person and the head alone, so on a page whose own person is not the head every
other member's relationship to the head is read only as FamilySearch's grouping
(computed), and the rule takes no one through it. `tools/save_page.js` presses
every "Open All" on an `fs-record` page before it saves, untried in a browser:
confirm on a real page that the details render without a request the method
does not make, then save the archived census pages again by the same method.

### C31. Where the rule and its words part

Each bullet is a place where the code and the rule's text say different
things, with its live case where one is known, and opens with the identifier
of each clause it concerns (`docs/TERMS.md`, `docs/RULE.md`; the docstring of
the function that implements a clause cites the same identifier). No accepted
decision of `docs/DATA-ARCHITECTURE.md` §7 makes the code right against the
words in any of them, so each is closed by code brought to the words, and the
bullet goes; a bullet that changes what the rule decides ends with a dry-run
`reconsider` on a copy of the live catalog.

- [rule.relation.1] **The route's reason.** The claimed-relationship route
  (`rule.rule_points`) gives the reason "the name and birth year agree"
  whatever the record gives, where `docs/RULE.md` says a birth year agrees "where both
  have one". Live: the gravesite locator's row for Noi Davidson names the
  veteran she is buried with by name alone, and the reason the rule takes him
  as Raymond Earl Davidson says the birth year agrees. Say the birth year only
  when both sides give one.
- [rule.relation.1] **A refusal that says "the indexer's".** When the route finds nothing,
  `rule_points` says the relationship is "its indexer's, not the record's own
  statement" whenever any computed relationship ties the persona to a person
  accepted on the record, even beside one the record states. Live: Dennis
  Scannell on the 1917 Massachusetts death index, father of Annie Scannell
  Ahearn as the index states, his couple with Mary Costello FamilySearch's
  grouping. Say the indexer's only when no stated relationship to a person
  accepted on the record is there, and otherwise name the stated one and why
  it does not count.
- [rule.standing.6] **The census before 1850.** The rule's census test reads the form
  (`forms.census_form`, `data/record-forms.csv`) and holds back a head-only
  form and a year with no form, but passes a census whose year is unknown,
  and takes the year from the collection's name by pattern when the record
  gives none. Hold such a census back until its year is read from the record
  or its citation, never from a name's digits.
- [rule.match.7], [rule.match.8] **The name variants.** `catalog.same_given` reads a bare initial as agreeing
  with a given name, where `docs/RULE.md` lets an initial agree only for a middle name,
  and with a day counting double a name and one date then take a record.
- [rule.value.2], [rule.value.5], [rule.value.6], [rule.value.7], [rule.value.8],
  [rule.match.4], [rule.terms.8] **What of an event's value is accepted.** `docs/RULE.md` reads a date per part
  everywhere and a place per part where it is shown; five places still read
  the value the event shows. A place's point (`rule_points`, `ground`) needs
  an accepted statement that gives the shown place whole, so a record
  agreeing with an accepted place earns nothing where the event shows another
  on a claim. The matcher compares with the shown values (`matcher.candidate`,
  `compare`), so a reading that differs from the claims on both dates is a
  hint, never a card, though it agrees with the accepted statements.
  `facts.decide_fact` accepts the file's claim citing a held record with the
  file's own value, so accepting a birth whose held census gives a calculated
  year makes the file's day read accepted. The veto (`rule.against`) never
  reads a place the owner's own word gives, where `ground` and
  `trusted_evidence` do. `Catalog.disagreements` never compares two places
  both finer than the event's own. Beside them: `checklist.build` gives the
  field for a country abroad the year's basis.
- [rule.match.6], [rule.match.15], [rule.conflict.1], [rule.points.13] **The
  comparison as data.** The comparison returns findings and the rule
  reads them, but four places in `tools/cards.py` still read words (the stored
  rationale of a card an older matcher wrote, a results row served as words,
  the card's own name note, an "accepted as" status), and `tools/conclude.py`
  reads the lines of `Catalog.disagreements` by pattern (`CONFLICT_AXIS`,
  `conflict_lines`), a comparison of its own that returns no findings yet.
  `place_verdict` says a record's place agrees as coarser ("the record gives
  only New York") where `place_given` finds its first part nowhere in the
  tree's place and says the two do not agree (Manhattan, New York, New York
  against Brooklyn, New York): one of the two is wrong. No scenario reaches
  the residence-place test of a relative's grounding.
- [rule.editable.1], [rule.editable.8], [rule.points.8], [rule.points.11],
  [rule.points.13], [rule.points.14] **A page anyone can edit.** Its identity counts a burial place at any
  granularity, where the trusted route leaves out one coarser than the
  tree's; it is tier T4 in one place and anything outside T1 to T3 in
  another; and `rests_elsewhere` takes undecided statements of such a page,
  and marked values, as what makes a relative's persona stand for the
  relative.
- [rule.relation.4], [rule.match.3] **What the rule creates.** It creates a grandchild or a half sibling and
  writes no family link; and `rule.rule_creates` still words refusals for
  a persona with no full name or no word of kinship, which the matcher no
  longer proposes.
- [rule.value.4], [rule.reconsider.1], [rule.own.2], [rule.match.15] **Cards.**
  `cards.card` works out its verdicts without the record's state
  or the dated names, so a card can show "disagrees" where the rule read
  "agrees"; a card code closed is stored `rejected` under the session's or the
  owner's name, told from a person's rejection only by the note `superseded`
  (1,334 of the 1,339 rejected cards live on 4 Oct 2026); and the matcher
  never proposes a persona that carries any rejected link, to anyone.
- [rule.proof.2] **The proof.** It makes "meets the standard" wait on research the docs call
  "not a gate".
- [rule.reconsider.5], [rule.name.1] **An alias in its own re-examination.** `reconsider` examines a decision
  without its own assertions and those of the decisions after it (`without`),
  but the name test (`matcher.compare`'s `accepted_names`, `matcher.name_keys`)
  reads every accepted alias, the decision's own and those of the decisions
  after it among them, and in a dry run those of the decisions it would
  withdraw and those it would set undecided. Live: the rule's decision taking
  Reiko Diane Davidson on the 2015 obituary
  (`h05-obituary-collection-current-2015-ZW0KTA.html`) agrees on the name only
  through the alias Diane Ahearn it wrote itself; without it the given name
  disagrees, and its withdrawal takes back the family links Patrick Michael
  Ahearn's and Matthew Alan Ahearn's decisions on the same obituary count, so
  both would be withdrawn too (a dry run on a copy of the live catalog of 9
  Oct 2026, the name test leaving out those aliases). Have the name test leave
  out the aliases of the decisions in `without`.
- [rule.name.2] **A name a trusted record writes, held first by the backfill.** `docs/RULE.md` makes
  the name as written on a record accepted for a person an accepted alias when
  the record is one nobody can edit at will, but `decisions.write_name_alias`
  leaves an alias of the same words alone unless a decision on that record
  wrote it, so a row `tools/backfill_aliases.py` wrote first keeps the words
  undecided, and the rule, and the proof with it, never count them. Live:
  Helen Sara Brant's married surname stands on no accepted alias: Helen Ahern
  from the 1940 census (a session's decision), Helen B Ahearn from her 1986
  obituary index entry and the 1950 census (the rule's) and Helen Brant Ahearn
  from her gravestone's photograph (the rule's) are the backfill's rows,
  undecided, so her proof says the two censuses and the obituary index name
  her otherwise. Have `write_name_alias` give such a row, one no decision
  wrote, the standing and the stamp of the record a decision accepts, and
  `reconsider` bring the rows already there.
- [rule.value.2], [rule.editable.9], [rule.points.13] **The owner's word gives
  no place.** `docs/RULE.md` has the owner's own word on a fact give the
  event's value whole, and a page's identity count a date or a place on any
  statement that gives it, but `rule.gives` reads a statement with no
  record fact of its own as giving the event's own date and no place, so a
  burial place the owner vouched for counts nothing toward a memorial's
  identity (`event_claimed_or_accepted`), nor toward a relative standing for
  the tree's on more than the relationship the record states
  (`rests_elsewhere`), where `ground` stands a vouch for the event's own date
  and place. No live case is known. Have `gives` read the owner's word as
  giving the event's own place too.
- [rule.accept.6] **An in-law's tie.** `rule.resolve_in_law` resolves a
  mother-, father-, son-, daughter-, brother- or sister-in-law's stated tie
  through the relative it names to the child, parent or spouse link it gives,
  and `link_family` writes that link as one the record states; no clause of
  `docs/RULE.md` says so (accept.6 names the child, parent or spouse the
  record states), and the function's docstring cites a hard rule on in-laws
  that `CLAUDE.md` does not hold. Find the owner's ruling the resolution rests
  on and write it as a clause of the accept part, or bring the code to
  accept.6 as it stands.

### C32. Circumstances under which a record misstates a date on purpose

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

**Blocked by:** D6.

### C33. A decision taken on a claimed relationship that reconsider would withdraw

In scenario `60-confirmed-on-a-record` the rule takes Robert Davidson on the
1940 census through the relationship it states to his son, accepted on it,
while his own name is not yet held on trusted ground. Once the owner accepts
him on the Ohio death index (step 9), a dry-run `reconsider` would withdraw
that census decision: with his name now held, `rule.rule_points` judges the
record by two points, not by the claimed-relationship route, and the son's
link is a claim (one point). More accepted ground refuses what less allowed.
If D2 lets the route stand when the points fall short (the change is one fallback before "two
are needed"), state it in `docs/RULE.md`, and show on scenario
60 that a reconsider after step 9 keeps every decision. Before that, close the
gap it exposes in scenario `99c-a-sibling-born-after-a-parent-died`: with the
route widened, the mother is taken on her son's obituary before her death is
accepted, and the brother born seven years after it is placed as her child,
undecided; the placement is examined only when it is made, so accepting her
death afterwards leaves it. Examine an undecided sibling placement again when a
parent's death is accepted (`decisions.died_before`), as a re-read does, and
remove the placement the limits of one life refuse, with its note.

**Blocked by:** D2.

### C34. A second copy of a held record is left in the inbox

`tools/attach.py` places a saved page on the plan step its identity reaches; once
one copy of a cited record is held (John Y Davidson's 1946 certificate page, done
on its citation `1,3077::604036`), a later save of another copy of the same
record (FamilySearch's index entry of it) finds no planned step and stays in the
inbox, so it is never archived, read or joined (`same_record`). Archive such a
page under the done step's citation when its identity reaches that step, read
it, and let `copies.join_copies` and `decisions.carry` make it a copy of the
record the step holds; the harness scenario `99ze` archives the index entry by
hand for this reason.

### C35. A document's topic, and the leads it opens for a person and their family

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

**Blocked by:** D7.

### C36. A record reaches a step on what it states, and is read once

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

### C37. Code that holds what the data should, or this family's own words

Decision 7 (no code names a family's people, places or denominations) and
decision 12 (the limits of one life are data). The rule's thresholds are
data, as the life limits are: the matcher's three-year window
(`matcher.WINDOW`), the two points a record needs and the three of four a page
anyone can edit needs (both in `rule.rule_points`), and the trusted tiers
(`rule.TRUSTED`, written again as literals elsewhere in `rule.py`, in
`catalog.py` and in `facts.py`, and the rule's creation reading T1 and T2).
`catalog.NICKNAMES` carries this tree's members (Lura, Lou, Laura; Corinne,
Carinne, Corrine; Cassie; Ollie) and groups distinct names as one (Oliver and
Olive, Emily and Emma, Helen and Ellen, Christian and Christopher), and
`catalog.same_given`'s one-letter rule makes Harry Larry and Edwin Erwin, while
a surname one letter apart is refused. `decisions.died_before` holds a
father's margin of a year and reads unknown sex as a mother where
`data/life-limits.csv` says ten months and `catalog.py` reads it as a father;
`footprint.py` holds a ninety-year life, a birth twenty years before the
first event and a 15–50 parent window. Registry ids are written in `plan.py`,
`fetches.py`, `attach.py`, `cards.py`, `households.py`, `catalog.py` and
`ingest_gedcom.py` (D03, E01 and others). Decision 3's release years live in
the registry and are never read: `checklist.py` sends the 1950 census to its
holder in code, holds the draft, Social Security and directory eras, and finds
military records by "Army|Navy|Veterans" (no Air Force, which C35 needs).
`checklist.py`'s `DEPENDS={"D03":"B01"}` and D03's registry note still wait on
the API decision 4 rules out. `backfill_aliases.py` names this tree's own
misspelling "Silesa" and fifteen states where `catalog.py` holds all. Move
each into the data it belongs to, or the table that already holds it, and the
nickname groups to a data file of true equivalents. The words of kinship are
held twice and in English: the matcher's `KIN_WORD`, by which a new person is
proposed, and the rule's `FAMILY_WORD`, by which one is created, differ (a
"Maternal Grandmother" is a card the rule refuses).

### C38. The move to Postgres is not a dump and restore yet

`schema/README.md` ("Migrating to Postgres") lists the porting work: the DDL
order (`same_record` is created before the `tree` it references), the
insert-only triggers to be written again and carried over, so hard rule 2
stands after a port, the SQL constructs the tools send, and `.dump`'s order
(`search_plan` before `research_question`) and booleans written as 0 and 1.
Do each: put the DDL in order, carry the triggers over, change each construct
(about 1,100 statements go straight to `sqlite3` across the tools and the
screen), and make the dump load. Two more the list leaves out: the one-time
corrections in `initdb.py` (0.7.3 to 0.7.9) import today's `plan`,
`conclude` and `catalog`, while `rebuild_table` reads today's DDL and commits
in the middle of a migration, so an old backup migrated later runs today's
logic and a failure leaves a version half applied and unrecorded; and
`rebuild_table` drops a rebuilt table's triggers, harmless while no rebuilt
table carries any (0.8.8 rebuilds `person_persona`, which has none) but not
for a later migration that rebuilds a protected table. Make each migration
one transaction that names the code it needs, and recreate the triggers after
any rebuild.

### C39. A live reconsider reaches its end in one run

A live `tools/conclude.py reconsider` can leave decisions that a second run
withdraws (cards on several readings of one page, fits that depend on order),
so every live run is followed by a dry run expected to change nothing, and a
full copy of the catalog is taken before each live change (thirty-seven sit
in `catalog/` on 9 Oct 2026). Run the withdrawals, the cards and the conflicts until a pass
changes nothing, within the one call, and show on a scenario that a second
run changes nothing; then the habit can go.

### C40. Reads that scan the whole tree

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
record is viewed, unmeasured on a record of many names. Every turn's tail runs `reconsider.reconsider` over the whole tree,
two to three minutes a turn at 145 people: a turn re-examines what its own
records and decisions touch.

### C41. Tools no check runs

**Harness gap**, one of seven (C5, C8, C20, C25, C26, C41, C43); the second family in the harness (C20) is the scenario they share. This one does not wait on it: each path can be shown on records the harness holds.

Measured across every process a check run starts: `tools/backup.py`'s fixity
(`verify`) and `tools/cite.py` run no line (the bag is written and checked);
the screen's GET routes other than `/api/tree` are never reached through
HTTP (its POST routes are); `run_step.fetch` (rate limit, User-Agent, POST),
`loc_gov.hits` and `total` never run, nor, as far as reading the checks shows,
`catalog.*_search_url` and `search_target`; and `cards.py`'s command line
neither: of its functions, measured on 5 Oct 2026, `render_cli`,
`render_compact`, `render_search_compact`, `cards_for`, `grouped`,
`rule_verdict`, `row_line`, `relation_lines`, `main` and their helpers never
run (what the owner reads with `tools/cards.py "<person>"`), nor
`rule.dated_with_parents` and `kept_agrees`, `facts.claimed_parts`,
`catalog.place_beyond` and `Catalog.same_page`. No scenario reaches
`proof.py`'s "the rule would keep assertion" line, nor a turn that names a
conflict the rule decided inside it: with real fixtures the turn's place
resolver stops at the first geocoder query it holds no answer for. Each can be
shown on records the harness already holds: the archive's fixity checked
under the scratch root, a citation made and run, a GET through the server.

### C42. What "the loop works" means

The goal says what the system is for and never what reaching it looks like,
so progress is read off commits. `tools/tree.py overview` already counts where
the tree comes from (people from the file and from records; documents from
citations, leads, searches and by hand). Once the owner has named the state
that counts as the loop working (D8), write it into `README.md` beside the
goal and have the overview print it.

**Blocked by:** D8.

### C43. A key the harness does not know inside an expectation or an action passes

**Harness gap**, one of seven (C5, C8, C20, C25, C26, C41, C43); the second family in the harness (C20) is the scenario they share. This one does not wait on it: it is the walker's own strictness.

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

### C44. A cited record is not closed by the first page of a search's results

When no row of a saved FamilySearch results page fits the person, `attach`
restates the run `none`, the fetch list then hides the step and the queue
passes the person, though the page says it is the first of several: on the
live catalog of 4 Oct 2026, 76 FamilySearch fetch steps stand at `none`, 54 of
them on page 1 of several. A citation says the record exists, so that `none`
is a cut, not an absence (`docs/DATA-ARCHITECTURE.md` §7 decision 17). The
search narrowed by the citation's own fields, then the next page, is the
step's next save; the step is `none` only when every page has been read.

### C45. A new search at a holder without a connector is the loop's work

The fetch list holds fetch steps only (`tools/fetches.py`), the queue counts
only those and the steps a connector runs (`tools/queue.py`), and
`catalog.search_target` builds a search's link for the screen alone, so of
the 131 assisted searches planned on 4 Oct 2026 none is ever a turn's work:
41 have a link only the screen builds, 66 name a holder, 24 name no source.
The tree grows past the file only where a connector answers. Put a search
whose holder takes a link on the fetch list, its results page the save, as
`docs/LOOP.md` §8 already reads; with A1 a model runs it.

### C46. The search ladder as built

`docs/PLAN-AND-SEARCH.md` §3 has six layers and `docs/TERMS.md` §2 a ranking. Layer 0 is
planned (twelve records at most), layer 3 as United States census rows, layer
2 only as each person's own rows; layer 1 is printed by the checklist and
never planned; layers 4 and 5 and the `surname_locality` query are in the doc
alone; no search step carries a question (0 of 180 on 9 Oct 2026), and the
ranking is not implemented. Build each layer, or make `docs/TERMS.md` §2 and `docs/PLAN-AND-SEARCH.md`
§3 say what is built.

### C47. Names and records beyond English and the United States

Beside C17, C20 and C37: the checklist's census rows are the United States'
alone, and `before_civil` is computed and never used; `catalog.key` and
`soundex` drop every letter outside a to z (Müller keys as mller, and a name
in another script has no key); `split_name` takes the last word as the
surname (van der Berg is Berg); the page parsers' labels are English; and
Silesia is named in `tools/resolve_places.py` and `Catalog.place`. A tree
whose people lived in Ireland, Germany or the Netherlands gets blocked
fetches and assisted rows with no link. Show each on the second family's
export when the harness has one.

### C50. The proof shows every conflict and argues the family links

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

### C51. The archive's files against a rewrite

Beside C28: `treelib.archive_object` writes the object and its sidecar again
whenever its catalog lacks the row, before the commit, and removes nothing when
the transaction fails: 10 sidecars disagree with their row's `manifest_json` (7
on the trust tier, 2 on `redistributable`) and 7 objects on disk have no row,
2 of them the runner's. Nothing compares a sidecar with its row, no code
reads `schema/manifest.schema.json`, and 20 sidecars carry `T1/T2`, outside
its list. Write an object and its sidecar once, never over one that exists;
compare sidecars with rows in `tools/backup.py verify`; hold the manifests to
their schema.

### C52. The screen shows the record it asks about

No route of `app/person/server.py` serves an archived object, so the card's
archived copy cannot be opened and an image cannot be seen while it is read;
and a conflict's resolution with its
reason, `reopen`, `place` (C11), `merge` and `link` have no control, while the
revise route takes a fetch step the page offers no control for. A fetch step whose locator is not an Ancestry record id shows no link (the
household lead's link sits only in its fields). The key-fact route ignores the `conflicts` `facts.decide_fact` now returns, so the
screen never says what the rule decided on them. A person
who runs no terminal cannot finish a person's work on the screen
(`docs/DATA-ARCHITECTURE.md` §7 decision 17).

### C53. Links the database can check

`assertion.subject_id` is one column for seven kinds of subject, its
composite keys JSON; a card's person, persona and artifact are in
`proposal.payload_json`; a citation's identity is in `assertion.notes`, found
by pattern. `foreign_key_check` sees none of them (none dangles on 4 Oct
2026), and 113 `json_extract` calls across 13 files read them (9 Oct). Beside C40:
give each link the column it is, with its foreign key, a link at a time.

### C54. A document that came through the browser is marked so, and listed with what would replace it

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

### C55. An assumed birth year is no claim either

A death nobody stated is no longer searched for under the year an assumed
lifespan gives. The checklist still gives every search step a `birth_year` worked
out as twenty years before the person's first dated event, with basis
`claim`: a year nobody stated, sent to a holder as if the file said it. Say
in `docs/RESEARCH-CHECKLIST.md` what a search carries for a person with no
stated birth (a window from the dated events, said to be one), and build
that.

### C56. A card read from a cut geocoder answer

A place is accepted only on an answer that was not cut, but a string that
ends as a card on a full page of six is not asked again, so its card offers
the first six candidates alone: the right place may be the seventh, and a
match there that a wider answer would have accepted goes to the owner instead.
Ask such a string again for forty before its card is written; the harness
holds no real forty-candidate answer, so capture one in a browser-free run of
the resolver first and plant it (the gravesite and Archive answers show how a
real answer becomes a fixture).

### C57. The fetch list prints one page twice

Where two entries of `tools/fetches.py list` share a link and a file name (the
Pennsylvania and New Jersey church-register search and the Pennsylvania
marriages search for Enos Heebner Cassel, live on 5 Oct 2026), the list and
`next` print the page twice, so the owner or a model saves it twice. Print one
entry for one link, its steps joined, as entries that share a record are.

### C58. A child's membership does not say which parent the record names

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
C4, which asks what grounds a parent-child point: have a child's statement name
the parent its record states, give a one-parent family its parent's
membership, keep the spouse path off a family that holds children of one
parent, and give the owner a tool that moves a child to the family the record
supports, shown on the six above on a copy of the live catalog.

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
