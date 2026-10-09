# The loop

## 8. The loop

A turn is one person's plan run end to end: the cited fetches at holders with
connectors, the auto searches, the standing rule's decisions on what comes
back, the people it creates, the plan regenerated at the end, and the pages
the person still needs from the owner's own browser session named. A page the
browser must save makes that person wait, never the loop: the loop goes on to
the next person, and the person's turn is finished once a page of theirs has
been saved. The queue a turn
draws from is the edge of the confirmed tree, in the overview's own order
(`tools/tree.py overview`): the home person's line first, then the people the
file names that a document or a conflict waits on and who are one link (a
parent, a child or a spouse) from someone confirmed, the nearest first. A
person further from the confirmed tree is not at its edge: their questions wait
with them until a link puts them within reach. The living default (`docs/DATA-ARCHITECTURE.md` §7)
stands unchanged inside a turn. A challenge in the owner's browser pauses the
session at the browser for the owner's hand (`docs/PLAN-AND-SEARCH.md` §4); it stops no turn, and it
does not by itself make the source assisted-only. What a turn leaves for the
owner are the conflict questions it raised, the cards the rule did not take
and the pages to save in the browser.

`tools/queue.py` names the next person. A tree with no home person is
refused, with the command that sets one (`tools/tree.py home`), since the
confirmed tree starts from them; `tools/turns.py` refuses the same way. It
walks the overview's own order,
the home person's line first, generation by generation, and at each confirmed
card takes a parent or spouse the file names whose link is not yet accepted
(the file's word, `docs/TERMS.md` §0: each one's membership the file's claim or an accepted
statement; a relative the tree links only by a sibling placement or a page
anyone can edit is not one) before the card's own person, then that person
when a document waits, a conflict is open or a key fact is undecided and a
turn can still act on them:
a step a connector can run with no run since the plan last wrote its fields,
or a page the fetch list can name. A confirmed person settled but for their
parents, whom nobody has accepted and the file names none, is the edge for
the records that name parents (a birth or death record, an obituary, a census
of the household in a year of their childhood), which their plan puts first:
the tree grows past the file on evidence, a parent such a record names created
by the rule from a trusted record (`docs/RULE.md`, the fitting check first) and the next
card above, at the edge in turn. A person whose open question is now the
owner's alone (a card to decide, a conflict, an assisted search with no link
to open), or whose parents' records are all such, is passed over. A person who
waits on pages to save in the browser (a turn named them, below) is passed over
while every step a turn could advance for them is one of those pages, with the
reason and the number of pages: a turn on them would name the same pages again.
They come back once a page of theirs has been saved: the run it brings is
logged on their step, so it is no longer a page they wait on, the collect that
took it finishes their turn, and the queue reads them again as it reads anyone,
named when a step a turn can advance is left for them. They come back sooner
when their plan opens a step that is not one of those pages. The command prints the next person with the reason and
the number passed over; `--all` lists everyone, each person passed over with the
reason.

`tools/turn.py "<person>"` runs the turn: `tools/plan.py` first, then every
step a connector can run on this person's plan, one commit each as
`tools/run_step.py --all` does, the standing rule deciding what comes back and
creating the people a record names. A run that fails is an error run and the
turn goes on (`docs/PLAN-AND-SEARCH.md` §4): a connector that cannot build its requests, or a record
whose reading or matching raises, is logged `error` with the exception in the
note, the log row kept (a run already logged found is restated as an error
run, as the Schema section below has a run read again) and the step left
runnable, so the next turn runs it again. Then the tail, in the same call:
`tools/fetches.py collect` on `downloads/`, `tools/attach_inbox.py` on
whatever else the inbox holds, one file per transaction (a file that fails
stays where it was and is named in the report, `docs/PLAN-AND-SEARCH.md` §4), the place resolver on the
place strings the turn's new records carry and those behind the person's own
events (a string it accepts places its events before the rule compares them;
one it cannot settle is a card on the fact row), `tools/conclude.py
reconsider`, and the plan regenerated. Each of these, and the plan that opens
the turn, runs in a transaction of its own: one that fails is rolled back
alone, named in the report with its exception, and the turn goes on to the
next (the steps already planned are run when the opening plan fails); the next
turn runs it again.
Last, this person's own pages at holders without a connector (`tools/fetches.py
next`'s own pages, narrowed to their unrun steps) are printed under the report
with the file name to save under and the save script's call, and the person
waits on them: their name and the steps of those pages are kept beside the
catalog (`<db>.turn-state.json`, one entry for each person who waits, beside
the place strings the geocoder left unanswered, the file gone when neither is
there), and the turn is over.

A page that comes in outside a collect (attached by hand, logged on the person
screen) is a run on the step of a person who waits, and the next turn or resume
finishes that person's turn all the same, their report naming what the runs of
their closed steps hold. A file a collect takes is credited to the people whose
steps it reached, and for a person who waits that finishes their turn in the
same call: the place
resolver reads the strings behind their own events beside the rest, the plan
is regenerated for them, and their own report follows, with the files
credited to them, what the rule took on those files, what is left for the
owner and the pages they still wait on; with none left they wait no more.
`tools/turn.py --resume` is that alone, with no turn of its own: it takes
whatever has been saved (`tools/fetches.py collect` on `downloads/`,
`tools/attach_inbox.py` on the inbox), credits each file, and finishes the
turns of the people who wait that it reached, running the resolver,
`reconsider` and the plans only when a file came in; its own report names the
files that reached nobody who waits, and with nothing saved it says who waits
on how many pages. Its resolver, and the resolver of every turn's tail, also
asks again every place string an earlier call left unanswered, tree-wide,
whoever's it is, through the geocoder's cache and at its rate (a resume with
nothing saved runs the resolver for them alone), and keeps the ones the
geocoder still does not answer: the strings a silent geocoder leaves behind a
person whose remaining work is the owner's would otherwise wait for a turn on
that person that the queue never gives. The turn run by hand
has the runner's guard: a turn that fails anywhere but in its runs and its tail's
parts stops there, what it had not committed rolled back, names its exception and
exits with a failure status. The people who wait are kept beside the catalog in
a file written whole, so a stop in the middle of a write leaves it as it was. The
turn writes nothing of its
own: every catalog write is one of those tools' under its own name. Its
report says what was held, what the rule decided (the proposals it took and,
one line each, the conflicts it resolved or took back while the turn ran, with
the person, the date or place kept, its reason and the question id
`tools/conclude.py reopen` gives it back by), who was created and what is
left for the owner, in words; a source that did not answer (a connector, or
the geocoder for the place strings) is named once, with the rows of the steps it
was asked on or the number of strings it left (those strings kept beside the
catalog for the next turn or resume), a run or a part of the tail
that failed is named once with its exception, and a file left in the inbox that
fulfils no step is named once per run, not in every report. A record the owner cites on their own word
(`tools/cite.py`) is a fetch step on the plan a turn runs like any other;
where the owner's word names who on the record is their person, that persona's
card is accepted on their word, the decision's note quoting it, and the record
is read outward from that person as any accepted record is.
`tools/turns.py` is the loop run without a hand on it: it first does what
`tools/turn.py --resume` does (whatever has been saved in the browser is taken,
each file credited to the people whose steps it reached, and the turns of the
people who wait that it reached are finished), then asks the queue for the
next person, runs their turn with `tools/turn.py`'s own code, prints the
turn's report and asks the queue again, until the queue names nobody a turn
can act on or `--turns N` turns are done (`--turns 0` finishes the turns of
the people who wait and starts none). A turn that leaves pages to save never
stops the run: its person waits and the run goes on to the next person, and
nobody waiting ever makes the runner refuse. One person's failure never stops
the next person's turn: a run or a part of the tail that fails is named in the
turn's report as above, and a turn that fails anywhere else stops there, what
it had not committed rolled back, is named with its exception, and its person
is passed over for the rest of the run with that reason. A person the
queue names again whose last turn held nothing new for them (no more records
held after it than before: a reconsider that withdraws an acceptance holds
fewer) is passed over for the rest of the run with that reason. The run's own count (the turns run, each
person's held count before and after, the passed-over, the inbox files already
named) lives in the run and ends with it; it writes nothing of its own to the
catalog. A connector's challenge is an error run, the source did not answer,
and the turn goes on: a challenge or maintenance page served in place of the
answer, which no reader of the connector parses, is archived as it came and
logged error with the reader's exception in the note, the step left runnable; a challenge in the browser is the session's pause,
outside the runner. Its summary says, in words, the turns run, the turns of
people who waited that it finished (in its opening resume, or in a turn's tail
when a page of theirs came in while the run went on), the people this run passed over and why,
the people who wait on pages to save in the browser with how many pages
(`tools/fetches.py next` names them; the next run takes what is saved), and
what is left for the owner as counts by kind
(documents to decide, conflicts open, key facts undecided, family links the file
names and nobody has accepted); `--detail` names each person with the reason, as
`tools/queue.py --all` does, and each person who waits with their pages.

## Worked example: Thomas Ahearn (1846–1902)

1. Baseline: birth 2 Oct 1846, death 21 Aug 1902, wife Alice McGee, son Patrick,
   no parents, **zero citations on Thomas himself**. Every fact is `unverified_claim`.
   Blocked until reviewed.
2. After review, questions: `missing_parents`; `unverified_claim` × n;
   `duplicate_person`: a second "Thomas Ahearn" with the **identical birth date
   2 Oct 1846** exists in the tree as a child of James Ahearn (1810–1899) and
   Johanna Barry. The dead end is a duplicate entry; the parents are already in
   the tree. The question is answered by resolved data before any search runs.
3. Plan for `missing_parents`:
   - L0 footprint: the 1880 census record cited on Alice and Patrick (Thomas
     should be head of household: age, birthplace, parents' birthplaces);
     the Massachusetts marriage record cited on Alice (names Thomas's parents);
     Patrick's Massachusetts birth record (names both parents, mother's maiden name).
     Three fetches, all records we already cite, before any search.
   - L0 via the duplicate: merging the two Thomas entries closes the question.
     The 1870 census (`1,7163::26817907`) cited on James Ahearn's family is the
     record that proves it (Thomas, 23, in James's household).
   - L1: same collections (MA marriages, MA births, 1870/1880 census) for Ahearn
     in Northampton / Hampshire County.
   - L2: Thomas's own MA death record 1902 (free, T1, names parents); obituary
     in Northampton papers 1902 (loc.gov); naturalization.
   - L4: only if the footprint fails to name the parents.

## Schema

```
research_question (id, tree_id, subject_person_id, kind, q_key, detail_json, status open|closed, closed_reason answered|dismissed|gap_gone|resolved, answered_by_proposal_id, created_at, closed_at)
                   kind: missing_parents | identity_incomplete | missing_spouse | missing_fact | unverified_claim | conflict | duplicate_person | unlinked_relative | identity
search_plan       (id, person_id, row_key, question_id?, seq, step_key, kind fetch|search, query_type, query_json {field: {value, basis}},
                   locator_source_id, locator_kind, locator_value, collection_id, on_json, sources_json, mode fetch|blocked|auto|assisted|awaiting_approval,
                   expected, status planned|done|skipped, rationale, revisions_json, created_at)
                   row_key: "<record>:<instance>" of the checklist row, or "footprint:<locator>" for a record on a relative
search_log        (id, tree_id, plan_step_id, question_id, executed_at, executed_by, source_id, query_json, outcome found|none|blocked|error|unread, artifacts_json, notes, superseded_by?)
proposal.question_id
source.connector
```

A question is fact-level; a missing checklist row is a unit of work, a step,
not a question, and a step carries a question id only when it answers one.
There is no separate review table: the baseline review is the status on the
assertions behind each key fact. Questions and steps are keyed so
`tools/plan.py` regenerates them idempotently, drops steps no longer generated
(a done one stays; one that was run but is not done is kept for its log as
`skipped`, and is planned again if it is generated again), and closes a
question whose gap has gone; a question a
person dismissed stays closed. `tools/log_search.py` (and the person screen)
record every run with the fields as rendered after include and revise; a
`found` run marks the step done, a `none` run leaves it planned and visible as
tried, and so does an `unread` run, the one the attach and the runner log for a
record no parser reads, a web page or a JSON or text response alike (schema
0.7.8: the record is held on the log, nothing is read from it). A found run that archived a file records the artifact on the log; the
row is then held, and the assertion comes from extraction and review.

The log is insert-only, like the evidence and the audit trail. A run read
again is a new row, never a row written over: a run is logged found before its
records are read, so that the matcher sees every person they were fetched for,
and when its records turn out to fit no one it is read again as `none`, and
when no parser reads them as `unread`; a merge carries the duplicate's run
onto the kept person's step the same way. The new row restates the run (its
moment, actor, source, fields and artifacts) with the outcome, note or step it
is now read with, and the old row's `superseded_by`, the one column written
after insert and only once, from empty, names it (`log_search.restate`, with
an audit row naming the row superseded), as a re-read extraction supersedes
the old one. Every reader (the plan, the runner, the fetch list, the
checklist, the queue, the screen, the cards, the proof) reads the rows whose
`superseded_by` is empty; a superseded row stays as the record of what was
first logged. The correction is a new row with a marker, not a second column
holding the corrected outcome: a merge's carry moves a run to another step,
which no write-once column can say, and one form serves both.

## Rules that hold throughout

- There is no hint feed on an unreviewed person. The record citations and
  media references that came with the Ancestry export are data (in the import's
  extraction JSON and on the assertions) and surface only as fetch steps, and
  as Layer 0 footprint steps under the questions of the people they support.
  Hints (`docs/TERMS.md` §0) live on a reviewed person's screen.
- The footprint is computed from accepted family links and citations, so it
  improves every time a review accepts something.
- Nothing is searched for a person until that person's baseline is reviewed.
  Fetching a record the tree already cites is allowed before review, because
  the review needs the record, and so is finding the rest of a census household
  a held page holds part of, on that page's own words (`docs/PLAN-AND-SEARCH.md` §3).
- The first screen is the person: claims, evidence, verdicts, then their
  questions and the plan for each.
- FamilySearch is reached through the owner's browser only, never its API
  (the owner's decision): its pages are saved one at a time and every
  decision on them is automated from the saved page.
