# CLAUDE.md

Operating rules for an AI contributor in this repo. Read `MEMORY.md` before
changing code or docs; it holds the cross-cutting working patterns.
`README.md` says what the project is and where things are.

## What this is

A family-tree application with AI in the core, built data-first. Every
fact must trace to an archived copy of the record it came from. A fresh
tree must be able to distrust every earlier conclusion. The user researches
people; everything else exists to serve that.

**The goal.** In the owner's words: "Humans should be working off of defined
logical rules, so there is no reason why we cannot implement these policies in
code. Automation should be the goal as long as it is built off an accurate and
trusted foundation of documents." and "The human should only be used if there
are serious doubts." The work is a loop: the next person at the edge of the
confirmed tree, the records that should exist for them, fetched, read and
decided by the owner's written rules, then the next person; where a source
forbids automation, that person waits on the owner's browser and the loop goes
on to the next.

## Where decisions live

| Question | Read |
|---|---|
| Layers, archive, trees, trust boundaries, aliases, decision model | `docs/DATA-ARCHITECTURE.md` |
| Baseline → questions → search ladder → review, and where each part is stated | `docs/RESEARCH-WORKFLOW.md` |
| The terms (claim, lead, hint), which documents the rule may accept, the baseline, the questions | `docs/TERMS.md` |
| The search ladder, the plan's steps, the search, the fetch list and the research log | `docs/PLAN-AND-SEARCH.md` |
| The rule: extraction, matching, what an accept writes, the standing rule, identity, conflicts, reconsider, the proof standard | `docs/RULE.md` |
| Census households read off their form, their missing entries fetched | `docs/HOUSEHOLDS.md` |
| The loop (a turn, the queue, the runner), the schema of questions, steps and the log, the rules that hold throughout | `docs/LOOP.md` |
| Per-person checklist, gaps, search foundation, the screen | `docs/RESEARCH-CHECKLIST.md` |
| What the imported tree holds; how the work splits across the tools | `docs/SOURCE-PROFILE.md` |
| Source registry, free holders of cited collections, where records exist, countries, evidence classes, the reasoning | `data/data-sources.csv`, `data/holders.csv`, `data/jurisdictions.csv`, `data/countries.csv`, `data/evidence-classes.csv`, `data/DATA-SOURCES.md` |
| Tables, invariants, tools | `schema/README.md`, `schema/catalog.sql` |
| Deferred work | `BACKLOG.md` |
| The audit's terms of reference | `docs/AUDIT-PROMPT.md` |

Anything marked accepted in those docs stands. Do not reopen it in code;
propose a change as a `BACKLOG.md` entry with the reason, never by building
around it.

## Hard rules

1. **Three states.** Every human decision is `undecided | accepted |
   rejected`. No numeric confidence, no scores, no percentages, anywhere a
   person decides. Machine scores stay inside notes/JSON.
2. **Evidence is immutable.** `artifact`, `persona`, `persona_fact` are
   insert-only. Corrections are new rows; removals are tombstones. Errors in
   records are never corrected in evidence; they become aliases.
3. **A person accepts documents, and a document's facts come with it.**
   Imports and AI output arrive Undecided; a conclusion needs an Accepted
   assertion. The one decision is "is this record about this person"; yes
   accepts everything the record states, and a difference with the tree's
   value is a conflict question, never a silent overwrite or a silent drop.
   The owner's standing rule takes that decision for a document from a source
   nobody can edit at will that agrees with what the owner accepted on such
   sources, recorded as acting on their word and reversible; a person's own
   decision is never undone by the rule or by a re-read. A page anyone can
   edit (Find a Grave, member trees) identifies a person and never builds
   their facts. A memorial's gravestone photographs are primary sources.
   Anything less certain is a card for the owner. The full statement (the
   rule's points, the relatives it takes or creates, editable pages and the
   leads they make) is `docs/TERMS.md` §0 and `docs/RULE.md`.
4. **Trees are isolated.** No automatic reuse of evidence across trees:
   every import gets its own extraction and personas, even for identical
   bytes (`docs/DATA-ARCHITECTURE.md`, trust boundaries).
5. **One person per screen.** The work on a person runs foundation →
   checklist → tasks → results → review; the screen's layout is
   `docs/RESEARCH-CHECKLIST.md` §6b. No queue screens, no navigation by data
   type: an unresolved place, an uncited fact or a record to fetch surfaces
   only as a question about the person. No hints on a person whose baseline
   is not reviewed. Leads (follow-up work the evidence produced) and hints
   (documents that overlap the person but do not identify them) are defined
   in `docs/TERMS.md` §0 and live on the person. Define the
   screen's goal in one sentence and confirm it before building: a screen
   that mirrors internal queues makes sense to the pipeline and to nobody
   else.
6. **Plain over clever.** No bells and whistles. If a feature is not in the
   design docs, ask before building it.
7. **Data never enters git.** `archive/`, `catalog/*.db`, `derivatives/`,
   `inbox/`, `downloads/`, `trees/*/imports`, `trees/*/exports` are ignored, and the commit hook refuses them:
   install it once with `git config core.hooksPath tools/hooks`. Any archived
   document the owner chooses may sit in `tests/` as a fixture: these are the
   owner's family documents in the owner's repository, and none is excluded.
8. **No bandaids.** Fix the cause or file it in `BACKLOG.md`. No parking
   comments, no compensating checks. Comments describe current code, never
   history (see `MEMORY.md`).
9. **Commit each finished piece of code or doc work**, directly to `main`,
   with the tools green (`python3 tools/check.py`), and push it to `origin`,
   without waiting to be asked. Research decisions live in the catalog and
   never enter git.
10. **Working notes are a report**, returned to the user, never committed.

## Working the repo

Every tool, one line each: `schema/README.md`'s table; each tool's docstring
and `--help` have the rest. The ones a session uses:

```
python3 tools/check.py                      # green in one command; a failure in full, --verbose every check, --scenario NAME one scenario
python3 tools/initdb.py --migrate           # after a pull that moves the schema, once backed up: every tool refuses a catalog behind it
python3 tools/initdb.py --sync-sources      # after any change to data/data-sources.csv (--sync-event-types for the event types)
python3 tools/turns.py [--turns N]          # the loop: what was saved taken in, then the next person at the edge, their turn, the next; a person whose pages wait for the browser waits, the loop goes on
python3 tools/fetches.py next [K]           # the pages to save, one line each (`list` for all); then `tools/fetches.py collect`
python3 tools/turns.py --turns 0            # after the browser session: what was saved taken in, the turns of those who waited finished
python3 tools/run_task.py show [K]          # the next pages as a model's fetch task; the `tree-fetch` skill has a model save one, the owner present, and code judges and records it
python3 tools/cards.py "<person>"           # the records waiting for a decision, one card each; --full every field
python3 tools/conclude.py decide <proposal id> accept|reject --note "…"
python3 tools/conclude.py fact "<person>" <birth|death|parents|…> accept|reject|undecided   # a key fact; accept with no held evidence is your own word (a vouch)
python3 tools/conclude.py resolve <question id> --keep <assertion id> --note "…"   # a conflict closed with the reason; `reopen <question id> --note "…"` takes back one the rule decided
python3 tools/proof.py "<person>"           # each key fact against the proof standard: evidence and its classes, research, conflicts
python3 tools/kin.py "<person>" "<person>"  # the two people's relationship through accepted links alone: each link's record and standing, the chain's standing its weakest link's; with none, the nearest path the file claims and what each unaccepted link owes; --all the other paths
python3 tools/tree.py overview              # the tree as confirmed, from the home person upward, its edge, and where it comes from
python3 app/person/server.py --by user:<you>   # the person screen on http://127.0.0.1:8765/
DATA_ROOT=<scratch> python3 tools/<tool>.py   # a scratch run, for testing code: the catalog, archive, inbox and downloads under <scratch>; a --db outside DATA_ROOT is refused
```

## Working a person

The loop (`docs/LOOP.md` §8) does a person's work end to end;
by hand it is the same steps. Research decisions are made on the live
catalog; a scratch copy is for testing code, never for decisions.

1. `tools/queue.py` names the next person at the edge of the confirmed tree:
   a parent or spouse the file claims whose link is not yet accepted, a
   confirmed person with an open question, or a confirmed person whose parents
   nobody has accepted and the file names none, for the records that name
   parents, first in their plan; never a person two links away from anyone
   confirmed. `tools/turn.py "<person>"` runs their plan: every
   step a connector can run, the rule's decisions, the plan again.
2. A turn that leaves pages a connector cannot fetch lists them, and its
   person waits on them while the loop goes on: save the ones
   `tools/fetches.py next` names in the owner's browser by the
   page-saves-itself method (`docs/PLAN-AND-SEARCH.md` §4), or have a model save them one at a time
   with the `tree-fetch` skill (`tools/run_task.py`, the owner present to
   approve the browser); the next `tools/turns.py` (or
   `tools/turn.py --resume`) takes them in and finishes the turns of the
   people they were saved for. When a site blocks a save or a search (a
   challenge, a sign-in), notify the owner and wait; continue once they have
   passed it by hand. Never pass it yourself, and a block does not by itself
   make the source assisted-only.
3. What is left is the owner's: the cards (`tools/cards.py`, decided with
   `tools/conclude.py decide`), the key facts (`name`, `sex`, `birth`,
   `death`, `parents`, `spouses`, `children`, decided with
   `tools/conclude.py fact`; one the file makes no claim about counts as
   decided; searches open only when every key fact is decided), and the
   conflicts the rule leaves (`tools/conclude.py resolve`; the rule decides
   one only when the evidence classes favour a side without doubt). What an accept writes is `docs/TERMS.md` §0 and
   `docs/RULE.md`. A family link the record states is asserted when both people it
   relates are accepted on it, so a child's parents fact is decided by the
   parents' own cards on the same record, each their own turn: a turn that
   ends six of seven is not a failure.
4. `tools/proof.py "<person>"` says, per key fact, whether the conclusion
   meets the proof standard or what argument is still owed.

A name two people share is refused; name the person by the six characters
the listing shows: `"Noi Davidson [MEXW2C]"`. Report what was decided and on
what record, in words; never a score.

Every tool that writes takes `--by`. The owner acting is `user:<name>`; a
session acting on the owner's behalf is `agent:<session> for user:<name>`,
so the audit trail says who did what. A writing tool run without `--by`
records the shell user as the owner, except the runner and the planner, which
record themselves (`agent:run_step`, `rule:plan@0.1.0`). The read-only tools
and the registry syncs take no `--by`. A session writes the catalog only
through a tool: a correction no tool makes becomes a tool command first
(`docs/DATA-ARCHITECTURE.md` §7 decision 13). Living status is the tier rule
(`docs/DATA-ARCHITECTURE.md` §7 decision 3), the same for every tree: a
search step on a living or unknown person is assisted, never automatic, and
the owner's word (`tools/conclude.py living`) stands above everything.

- Stdlib Python only, so far. Portable SQL (SQLite now, Postgres later).
- Verify after every change: `PRAGMA integrity_check`, `foreign_key_check`,
  and the `v_unsupported_*` views. Test code changes on a scratch copy of
  the catalog, never on the real one; research decisions are made on the
  live catalog, which is the work.
- Place resolution auto-accepts a unique full match (the geocoder's, or a
  gazetteer's whose one candidate is the same place as exactly one geocoder
  candidate by an identifier both keep, `docs/DATA-ARCHITECTURE.md`
  "Gazetteers"), and also a string whose verified candidates are one
  territory under two names (a city and the county coterminous with it),
  tested on the geocoder's own boundaries coinciding within a small
  tolerance. A place nested in a larger,
  differently-sized unit of the same name (a village in its town, a city in
  its prefecture) stays Undecided with both offered. Never widen past that.
- External services: Nominatim public endpoint at 1 req/s with cache;
  Ancestry and Find a Grave have no API and forbid scraping — assisted
  fetch only. FamilySearch is the owner's browser only, never its API (the
  owner's decision).
- Other sources, always: the owner's standing instruction is "ALWAYS
  CONSIDER WHAT OTHER SOURCES WE COULD USE AND INTEGRATE." Whatever gap a
  piece of work meets, ask which free source could fill it, and record a
  candidate in `data/data-sources.csv` (with `data/DATA-SOURCES.md`'s
  reasoning) or a connector entry in `BACKLOG.md`.
