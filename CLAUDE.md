# CLAUDE.md

Operating rules for an AI contributor in this repo. Read `MEMORY.md` next;
it holds the cross-cutting working patterns. `README.md` says what the
project is and where things are.

## What this is

A family-tree application with AI in the core, built data-first. Every
fact must trace to an archived copy of the record it came from. A fresh
tree must be able to distrust every earlier conclusion. The user researches
people; everything else exists to serve that.

## Where decisions live

| Question | Read |
|---|---|
| Layers, archive, trees, trust boundaries, aliases, decision model | `docs/DATA-ARCHITECTURE.md` |
| Baseline → questions → search ladder → review | `docs/RESEARCH-WORKFLOW.md` |
| Per-person checklist, gaps, search foundation, the screen | `docs/RESEARCH-CHECKLIST.md` |
| What the imported tree holds; agent duties | `docs/SOURCE-PROFILE.md` |
| Source registry, free holders of cited collections, the reasoning | `data/data-sources.csv`, `data/holders.csv`, `data/DATA-SOURCES.md` |
| Tables, invariants, tools | `schema/README.md`, `schema/catalog.sql` |
| Deferred work | `BACKLOG.md` |
| What past sessions were asked to build (a record, not decisions); the audit's terms of reference | `docs/briefs/`, `docs/AUDIT-PROMPT.md` |

Anything marked accepted in those docs stands. Do not reopen it in code.

## Hard rules

1. **Three states.** Every human decision is `undecided | accepted |
   rejected`. No numeric confidence, no scores, no percentages, anywhere a
   person decides. Machine scores stay inside notes/JSON.
2. **Evidence is immutable.** `artifact`, `persona`, `persona_fact` are
   insert-only. Corrections are new rows; removals are tombstones. Errors in
   records are never corrected in evidence; they become aliases.
3. **A person accepts documents, and a document's facts come with it.**
   Imports and AI output arrive Undecided. Conclusions need an Accepted
   assertion. The one decision is "is this record about this person"; yes
   accepts everything the record states, and a discrepancy with the tree's
   value becomes a conflict question, never a silent overwrite or a silent
   drop. The owner's standing rule accepts a document from a source nobody can
   edit at will that agrees with facts the owner already accepted on such
   sources, recorded as acting on their word and reversible; a page anyone can
   edit (Find a Grave, member trees) is always a card; anything less certain is
   a card for the owner.
4. **Trees are isolated.** No automatic reuse of evidence across trees.
5. **One person per screen.** Foundation → checklist → tasks → results →
   review. No queue screens, no navigation by data type, no hints on a
   person whose baseline is not reviewed. Leads (follow-up work the evidence
   produced) and hints (documents that overlap the person but do not identify
   them) are defined in `docs/RESEARCH-WORKFLOW.md` §0 and live on the
   person. Define the screen's goal in one sentence and confirm it before
   building.
6. **Plain over clever.** No bells and whistles. If a feature is not in the
   design docs, ask before building it.
7. **Data never enters git.** `archive/`, `catalog/*.db`, `derivatives/`,
   `inbox/`, `trees/*/imports`, `trees/*/exports` are ignored, and the commit hook refuses them:
   install it once with `git config core.hooksPath tools/hooks`. Any archived
   document the owner chooses may sit in `tests/` as a fixture: these are the
   owner's family documents in the owner's repository, and none is excluded.
8. **No bandaids.** Fix the cause or file it in `BACKLOG.md`. No parking
   comments, no compensating checks. Comments describe current code, never
   history (see `MEMORY.md`).
9. **Commit each finished piece of code or doc work**, directly to `main`,
   with the tools green (`python3 tools/check.py`), without waiting to be asked. Research decisions
   live in the catalog and never enter git.
10. **Working notes are a report**, returned to the user, never committed.

## Working the repo

```
python3 tools/initdb.py --force              # a fresh catalog; the live one holds decisions and is migrated, never rebuilt
python3 tools/tree.py create <slug> --name "…"
python3 tools/tree.py home "<person>"          # the person the overview starts from
python3 tools/ingest_gedcom.py inbox/<file>.ged
python3 tools/resolve_places.py             # Nominatim, cached; --reset undoes AI resolutions only
python3 tools/backfill_aliases.py
python3 tools/checklist.py "<person>"       # read-only checklist + gaps (footprint on top); --json, --all
python3 tools/footprint.py "<person>"       # read-only Layer 0 on its own
python3 tools/plan.py --all                 # materialize questions + steps (idempotent)
python3 tools/log_search.py --list "<person>"   # the steps with outcomes; --step/--outcome to log a run; --dismiss <question>
python3 tools/attach_inbox.py               # every inbox file to the fetch steps its own identity fulfils: archived once, logged, extracted, matched
python3 tools/fetches.py list               # every page waiting to be saved in the browser, at every holder, with its link and file name; `collect` brings the saved pages in
python3 tools/cards.py "<person>"           # every Undecided proposal about the person as a decision card; --all, --json
python3 tools/conclude.py decide <proposal id> accept|reject --note "…"   # the decision on a card, as the screen's Add / Ignore
python3 tools/conclude.py fact "<person>" <birth|death|parents|…> accept|reject|undecided   # a key fact; accept with no held evidence is your own word (a vouch)
python3 tools/conclude.py assertion <id> accept|reject|undecided --note "…"   # one statement of one record on its own; ids from the person screen's evidence rows or the assertion table
python3 tools/extract.py <sha256>            # personas + facts from an archived record page (Find a Grave memorial or search, FamilySearch record or search, AAD, Ancestry index; HTML)
python3 tools/match.py <extraction id>       # proposals: persona match or new person, rationale in words
python3 tools/run_step.py <step id>          # run an auto search step through its connector; --all, --dry-run
python3 tools/conclude.py reconsider         # the standing rule re-examines its own decisions; one it would no longer take is a card again; --dry-run
python3 tools/conclude.py link "<person>" --spouse "<other>" --record <sha256> --note "…"   # your own word on a family link a record stops short of; --parent, --marriage; `divorce` likewise
python3 tools/backup.py verify                # every archived object hashed against its sha256; `bag <dir> --target <drive>` writes a BagIt bag with the catalog dumped to SQL; `check <bag>`
python3 tools/initdb.py --sync-sources       # after any change to data/data-sources.csv: source rows up to the registry on an existing catalog
python3 tools/initdb.py --sync-event-types   # after any change to schema/seed_event_type.sql: the new types on an existing catalog
python3 tools/check.py                        # green in one command: every tool compiles, every parser read against its saved page on a scratch catalog
python3 tools/tree.py show
python3 tools/tree.py overview                # the tree as confirmed, from the home person upward, and its edge
python3 app/person/server.py --by user:<you>  # person screen on http://127.0.0.1:8765/
DATA_ROOT=<scratch> python3 tools/<tool>.py --db <scratch>/tree.db   # scratch run: its own archive/, inbox/, derivatives/, trees/*/imports
```

## Working a person

One person, one document at a time. The live catalog is where research
decisions are made; a scratch copy is for testing code, never for decisions.

1. `python3 tools/tree.py overview` prints the tree as confirmed: the home
   person and everyone reached from them by a parents link the owner
   accepted, generation by generation, and at the edge the parents the file
   claims but nobody has accepted. Take the person at that edge: a parent or
   spouse the file claims whose link is not yet accepted, or a confirmed
   person with an open question. Never a person two links away from anyone
   confirmed. `python3 tools/checklist.py --all` lists everyone with whether
   their baseline is reviewed.
2. `python3 tools/checklist.py "<person>"`: the seven key facts (`name`,
   `sex`, `birth`, `death`, `parents`, `spouses`, `children`) with their
   basis. Decide each with `tools/conclude.py fact`: accept what a held
   record supports or what you know yourself (a vouch, recorded as your
   word), reject what is wrong, leave the rest undecided. A key fact the
   file makes no claim about (no spouse named) has nothing to decide and
   counts as decided. Searches open only when every key fact is decided;
   fetching cited records is open now.
   A name two people share is refused; name the person by the six
   characters the listing shows: `"Noi Davidson [MEXW2C]"`.
3. `python3 tools/plan.py "<person>"`, then `python3 tools/log_search.py
   --list "<person>"`: the fetch steps for records the file cites and the
   search steps for missing rows, each with its source and mode.
4. Auto steps: `python3 tools/run_step.py <step id>` (or `--all --dry-run`
   first). Assisted steps carry the source's own search prefilled: open it
   in the browser, save the page by the page-saves-itself method
   (`docs/RESEARCH-WORKFLOW.md` §4), then `python3 tools/fetches.py
   collect` or `python3 tools/attach_inbox.py <file>`.
5. `python3 tools/cards.py "<person>"`: every record waiting for a decision,
   one card each. Decide with `tools/conclude.py decide <id> accept|reject`.
   Accepting takes everything the record states about the person; a
   difference with the tree becomes a conflict question, never an
   overwrite. The record's other personas come up as cards only after that.
   A family link the record states is asserted when both people it relates
   are accepted on it, so a child's parents fact is decided by the parents'
   own cards on the same record, each their own turn.
6. `python3 tools/checklist.py "<person>"` again: what is held, what is
   still missing, what the plan does next. A turn can end with a key fact
   still undecided that only a relative's card on the same record closes
   (a child's parents, a wife's spouse): those cards are the next turns, and
   a six-of-seven is not a failure. When the person's rows are held or
   exhausted, move to the next person at the edge.
   `python3 tools/conclude.py facts "<person>"` lists every fact with its
   event id and every statement behind it with its assertion id.

Report what was decided and on what record, in words; never a score.

Every tool that writes takes `--by`. The owner acting is `user:<name>`; a
session acting on the owner's behalf is `agent:<session> for user:<name>`,
so the audit trail says who did what. A writing tool run without `--by`
records the shell user as the owner. The read-only tools (`checklist`,
`cards`, `footprint`, `backup verify`) and the registry syncs take no `--by`.
One default, the owner's to change: a search step on a person with no death
and born within a hundred years is assisted rather than automatic, so a
person runs it. Nothing else differs for them: a record fetched for a
relative that names them attaches to them as to anyone, and the records the
file cites on them are fetched like any other.

- Stdlib Python only, so far. Portable SQL (SQLite now, Postgres later).
- Verify after every change: `PRAGMA integrity_check`, `foreign_key_check`,
  and the `v_unsupported_*` views. Test code changes on a scratch copy of
  the catalog, never on the real one; research decisions are made on the
  live catalog, which is the work.
- Place resolution auto-accepts only unique full matches; everything else
  stays Undecided. Never widen that.
- External services: Nominatim public endpoint at 1 req/s with cache;
  Ancestry and Find a Grave have no API and forbid scraping — assisted
  fetch only.
