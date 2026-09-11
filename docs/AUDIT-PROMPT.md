# Audit prompt

Paste the block below into a fresh session opened in this repository.

---

You are auditing this repository. Do not build, refactor, or edit anything. Read, run
the read-only tools, test on a scratch copy of the catalog if you need to, and
report. The repository's own rules apply to you: `CLAUDE.md`, then `MEMORY.md`.

## The vision, in plain terms

This is a family-tree application with AI in the core, built data-first. The
person who owns it wants a simple, solid product with no bells and whistles.
The four ideas that everything else must serve:

1. **Nothing is trusted until a person accepts it, and a person accepts
   documents.** Every fact must trace to an archived copy of the record it came
   from. The decision is whether a record is about this person; yes accepts
   everything it states, a discrepancy becomes a conflict question. The owner's
   standing rule accepts a document that agrees with facts already accepted,
   recorded as acting on their word and reversible. Every human decision has
   exactly three states: Accepted, Rejected, Undecided. There are no numeric
   confidence scores, no percentages, no score badges anywhere a person decides.
2. **The user researches people, not data types.** There is one screen: a
   person. On it, in order: what we know and have accepted (the foundation),
   which records should exist and which we hold (the checklist, household
   records that name several family members first, individual records second,
   each row held / cited / missing / n/a), and what search fills each gap.
   Never a queue screen, never navigation by place or record type, never hints
   on a person whose baseline has not been reviewed.
3. **The search does not start from a name.** For a missing relative the first
   rung is the family's own footprint: records already attached to the known
   relatives, ranked by how many family members share them. Then the same
   collections, then relationship records about known relatives, then
   households, then a named search only once a candidate name exists. The
   user can say "go", uncheck facts they distrust, revise a spelling, or search
   for one gap at a time. Every run is logged, including nothing found.
4. **A fresh tree must be able to distrust every earlier tree.** Trees are
   isolated workspaces of conclusions over a shared, immutable archive.
   Evidence is never automatically reused across trees.

The intended end state is a clean, automated pipeline: baseline review by a
person, questions generated from the gaps, a plan per question, automatic
execution against sources that allow it and assisted execution (exact link plus
"what to look for", file dropped in an inbox) against sources that do not,
extraction of the fetched record into personas, matching against the tree as
proposals that answer the question, and review by the person on the same
screen. Then the loop repeats.

## The technical shape

- Four layers, strictly separated: reference (source registry, gazetteers),
  archive (content-addressed bytes plus a provenance manifest, insert-only),
  evidence (extractions and personas per artifact, insert-only), conclusions
  (persons, families, events, assertions, tree-scoped, mutable with three-state
  status). Read `docs/DATA-ARCHITECTURE.md`.
- Catalog: portable SQL, SQLite now, schema in `schema/catalog.sql` (0.7.1),
  invariants in `schema/README.md`. The live catalog holds the owner's
  decisions, so a schema change migrates them rather than rebuilding.
- Tools, all stdlib Python, in `tools/`: `initdb`, `tree`, `ingest_gedcom`
  (Ancestry GEDCOM 5.5.1 export → artifact, personas, persons, Undecided
  assertions), `resolve_places` (Nominatim with hierarchy verification;
  auto-accept only unique full matches), `backfill_aliases`, `checklist`
  (per-person foundation, questions, Group A/B rows, pre-built search step per
  gap), `footprint` (Layer 0), `plan` (materializes questions and steps into
  `research_question` / `search_plan`, idempotent), `log_search` (records runs
  into `search_log`), `extract` (personas, facts and relations from an archived
  record page; a parser claims a page by its own marker or the extraction
  fails), `match` (proposals against the tree, in words), `conclude` (what an
  accepted persona writes on the tree, the one decision that accepts a
  record's facts, the standing rule and its re-examination of its own
  decisions, the owner's word on a link), `attach` / `attach_inbox` (an inbox
  file to every step its identity fulfils, archived once, extracted, matched),
  `fetches` (every page waiting to be saved in the browser at a holder
  without a connector, and the saved ones collected), `cards` (every Undecided proposal as a decision
  card), `catalog` (shared read-only access), `treelib` (shared helpers),
  `run_step` (runs an auto search step through every connector its sources
  have under `tools/connectors/`: loc.gov for Chronicling America, the 1950
  census site, the Internet Archive's full-text search for newspapers,
  directories and books, WikiTree; archives every response, logs the run,
  extracts and matches). Parsers: the Find a Grave memorial parser and the FamilySearch
  record-page parser are verified on real pages; the Ancestry index parser is
  not (Ancestry needs a membership this account lacks). Connector-response
  extractors: the 1950 schedule and the loc.gov OCR variants are verified on
  real responses.
- Screen: `app/person/` — stdlib server plus one page, localhost only. A tree
  overview from the home person upward following accepted parent links only,
  the file's claims named as claims at the edge; the person page with the
  documents to decide first as cards (Add / Ignore with a reason), what is
  known with each fact's records, a transcription form for a record image, and
  the plan. Fact decisions write assertion status; plan generation; logging a run; attaching a
  downloaded file from `inbox/`, which archives it, parses and matches a record
  page on arrival, and shows the proposals for the person to decide; a persona
  match or new person accepted writes Accepted assertions for everything the
  record states, raises a conflict where it differs from the tree, and closes
  the questions it answered; the standing rule takes the matches it is certain
  of and says so on the card.
- Design docs: `docs/RESEARCH-WORKFLOW.md` (the loop and the search ladder),
  `docs/RESEARCH-CHECKLIST.md` (checklist, gaps, foundation controls, the
  screen), `docs/SOURCE-PROFILE.md` (what the seed tree holds, agent split),
  `data/data-sources.csv` and `data/DATA-SOURCES.md` (source registry, trust
  tiers T1–T5 which classify source kind and are never scores). Deferred work
  is in `BACKLOG.md`. Accepted decisions are marked as such in the docs.
- Seed data: one Ancestry export of 117 people (Pennsylvania Schwenkfelder and
  Mennonite lines, Massachusetts, Kentucky, Tennessee, New York; Silesian,
  Saxon, Dutch and Irish origins). Its claims arrive Undecided and are a guide,
  never a checklist: the loop starts from the people the owner accepted and
  walks outward on records. Plans exist for everyone; search steps exist only
  for reviewed people.
- Not built yet: connectors beyond those six (FamilySearch waits on the API
  application), exporters.

## What to look for

Report findings, most serious first, each with the file and line, what the
flaw is, why it matters against the vision above, and the smallest change that
fixes it. Use severity words, not numbers. Distinguish clearly between:

1. **Contradictions.** Anything in code, schema, tools, screen, or docs that
   contradicts an accepted decision or another doc. Include places where the
   docs say one thing and the code does another.
2. **Flaws that block the automated pipeline.** Look hard at the path from a
   planned step to an archived record to personas to a proposal to a review.
   Is the schema and tooling shaped so that adding automatic source connectors,
   the extractor and the matcher is straightforward, or will it force rework?
   Are the typed search steps actually executable by a program, or only
   readable by a person? Is `search_log` capturing what a program would need?
   Is the plan-per-checklist-row granularity (one research question per
   missing record) the right unit, or noise that will drown the real questions?
   Does anything assume Ancestry can be automated when it cannot?
3. **Violations of "plain over clever".** Anything that adds a concept, a
   table, a column, a state, a screen element or a rule that the vision does
   not need. Anything a user would find annoying. Anything that smells like a
   score or a hint feed.
4. **Trust leaks.** Any way an unreviewed or machine-produced value can become
   Accepted, be exported, feed a search as if accepted, or cross from one tree
   to another without a person deciding.
5. **Hygiene.** Comments or docs that narrate history instead of describing
   current state, stray working notes, data files that could reach git, dated
   stamps, migration residue.

Also answer two direct questions at the end: is the loop as built honest
about what is automated and what is not, and what is the one change you
would make first before any more building.

Do not propose bells and whistles. Do not reopen accepted decisions unless you
believe one is actually wrong, and if so say why in one paragraph and mark it
as a challenge, not a finding.
