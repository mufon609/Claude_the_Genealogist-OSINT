# schema/

| File | Purpose |
|---|---|
| `catalog.sql` | Portable DDL (SQLite 3.35+ and PostgreSQL 13+). 39 tables, 6 views. Schema 0.8.6. The live catalog holds the owner's decisions, so a schema change migrates them rather than rebuilding. |
| `seed_event_type.sql` | Event/attribute taxonomy borrowed from Gramps with GEDCOM 7 tags. |
| `sqlite_extras.sql` | SQLite-only: the insert-only triggers on the archive's rows, the evidence, the research log and the audit trail. |
| `manifest.schema.json` | JSON Schema for the provenance sidecar written next to every archived object. |

Build a fresh catalog with `tools/initdb.py` (add `--force` to overwrite). It seeds
`source` from `data/data-sources.csv`, so the CSV stays the registry of record;
after any change to the CSV run `tools/initdb.py --sync-sources` on an existing
catalog, or the plan stops with the missing source ids. `data/holders.csv` (free
holders of cited collections) is read by the tools directly.

## Table map by layer

```
1 REFERENCE    source, collection, event_type, place, place_name, place_string
2 ARCHIVE      artifact, artifact_locator, tombstone
3 EVIDENCE     extractor, extraction, persona, persona_fact, persona_relation, same_record,
               household, household_member
4 CONCLUSIONS  tree, tree_import, person, person_name, family, family_member, event,
               event_participant, person_persona, assertion, proposal, external_id, alias, note,
               research_question, search_plan, search_log, task_run
               (tree-scoped: person, family, event, assertion, proposal, note, tree_import,
                research_question, search_log, task_run; search_plan through its person)
OPS            schema_migration, audit_log, storage_target, artifact_copy
VIEWS          v_person_vitals, v_unsupported_person, v_unsupported_event,
               v_artifact_under_replicated, v_external_id_collision, v_person_search_key
```

## Invariants (enforced by DB where possible, otherwise by the app)

- `artifact`, `artifact_locator`, `tombstone`, `extractor`, `extraction`, `persona`,
  `persona_fact`, `persona_relation`, `same_record`, `household`, `household_member`, `search_log`,
  `task_run` and `audit_log` are
  insert-only: triggers abort every UPDATE and DELETE but the write-once `superseded_by`
  on `extraction`, `household` and `search_log`, set from empty to the row that restates the old one.
  Corrections are new rows; removals are `tombstone` rows. A run read again (its records
  fit no one, or no parser reads them) or carried onto the kept person's step by a merge
  is a new row restating it (`log_search.restate`), and every reader reads the rows whose
  `superseded_by` is empty. `tools/check.py` tries each column of each table. The 0.8.1
  migration (`tools/initdb.py`'s `insert_only`) added the column and the triggers.
- A model launched on a step is one `task_run` row (`tools/run_task.py`; `docs/DATA-ARCHITECTURE.md` §7 decisions 16 and 19,
  `docs/RESEARCH-WORKFLOW.md` §4), insert-only, a task run again being a new row. `launcher` says what started the task
  and returned its measures, `headless` (a `claude -p` prompt) or `session` (a subagent of a session the owner is at). `task_kind` (`fetch`), `holder_id` and
  `plan_step_ids_json` say what was asked and where; `task_json` is the task as code rendered it and `task_text_sha256` the
  kind's one text, so two runs are of one task form only when both agree; `model` and `effort` are what the launcher was
  asked for (a session's effort is its agent file's). `input_tokens`, `output_tokens`, `cost_usd`, `turns`, `duration_ms`,
  `usage_json` (per model), `ended` and `denials` are the headless launcher's own report, empty when it gave none (`ended`
  then `timeout`, `exit <n>` or `no result`); a session is given `total_tokens`, `tool_uses` and `duration_ms` and nothing
  else, and `total_tokens` is the one count both launchers give.
  `answer_json` is the model's report; `outcome` is what code found (`no_answer`, `invalid`, `nothing`, `mismatch`, or what
  the attach made of a page whose identity is the step's: `unread`, `none`, `read`, `card`, `taken`), `differs` is set where
  the two disagree with the reason in `note`, and `search_log_id` is the run the page's attach logged on a step of the task.
  The measures say what a task costs at a model; none is a score on a card. The 0.8.2 migration (`tools/initdb.py`'s
  `task_runs`) added the table and its triggers; 0.8.3 (`task_launchers`) added `launcher`, `total_tokens` and `tool_uses`.
- One record is one source wherever it is held (`docs/DATA-ARCHITECTURE.md` §7 decision 15):
  `same_record` joins two archived copies of one record, insert-only (triggers abort
  UPDATE/DELETE), a copy being a whole file or one numbered row of a listing (`a_entry`/`b_entry`,
  the row's `catalog.persona_key`). Code writes a join, shared by every tree, as each file is read
  (`conclude.join_copies`, from `tools/extract.py` and the screen's transcription path): archived
  under one record id (basis `citation`), one FamilySearch entry id on both readings (`entry`),
  one certificate number of one year (`number`), where an entry of both readings agrees by name,
  never a page anyone can edit with a record nor a search's results row. The owner's word
  (`tools/conclude.py copies`, `apart`; basis `owner`, the tree's own) stands above code's on its
  pair, the latest word last. A record is every copy joined (`catalog.record_copies`); its statements
  are grouped as one on the screen, in `tools/proof.py` and in a conflict's line (`catalog.record_of`),
  a decision on any copy's entry carries to every copy's persona of it under the one decision
  (`conclude.carry`), the matcher puts an entry to the owner once, and the rule counts the record
  once. The 0.7.9 migration (`tools/initdb.py`'s `same_records`) wrote code's joins of the copies
  already held under `migration:0.7.9`; `tools/conclude.py reconsider` carries the decisions.
- A census household is read off its form (`docs/DATA-ARCHITECTURE.md` §7 decision 21): `household` is
  the entries the form's own rule bounds as one household (`data/record-forms.csv`'s `page`,
  `household` and `lines`), across every copy that carries them, grouped by `tools/households.py`
  at the version `grouped_by` names; `household_member` is one row per copy's persona, its
  `entry` the member however many copies carry it, its `relationship` to the head as the copy
  states it, `head` and the `line` the form's rule reads. `complete` and `missing_json` say
  what the form's rule shows missing (the head, a line between held lines), `ground` what
  groups the entries, in words. Evidence shared by every tree, like code's `same_record` joins:
  no tree's decision goes into it. Insert-only: a household grouped again differently (a page
  newly held, a reading read again, the script at another version) is a new row, and the row
  it replaces names it in `superseded_by`, written once; one whose entries no current reading
  holds is replaced by a row of no members. The plan groups them again before it reads them
  (`tools/plan.py`'s `household_leads`: a household not wholly held is a lead on the people the
  tree ties to it). The 0.8.5 migration (`tools/initdb.py`'s `households`) added the tables
  and their triggers and wrote no row.
- Decisions are three-state: `undecided` | `accepted` | `rejected` on `assertion`,
  `person_persona`, `place_string`, `alias`, `proposal`. No numeric confidence columns.
- An `assertion` records who set the status it has (`asserted_by`, `asserted_at`) and whether
  that was a person's own decision on the statement (`person_decided`: a key fact or the
  statement decided, a vouch, the owner's word on a link or a divorce, a card's rejection;
  RESEARCH-WORKFLOW §5–7). No acceptance of its record, re-read, carry to another copy,
  withdrawal by the rule or give-back of a carry changes a statement that carries it; the
  rule's withdrawal is recorded under the rule, acting for whoever ran it. The 0.8.0
  migration (`tools/initdb.py`'s `person_decided`) marked the statements the audit log shows
  a person decided and still holding that decision, one `audit_log` row each under
  `migration:0.8.0`.
- `search_plan.mode` is `auto` only when `source.connector` names a built connector
  that answers the step's checklist row at one of the step's sources at least; the
  registry's free text never decides it, and every Connector value of the registry names
  a module under `tools/connectors/` (a tool that merely uses a source, the place
  resolver at the gazetteers, is named in the row's notes, never as its connector). A
  connector may declare the rows it answers (`ROWS` in `tools/connectors/`: the New
  Jersey death index the death row alone, its source sitting on the birth and marriage
  rows too; the Kentucky indexes the death and birth rows, not the marriage row their
  source also sits on), and is asked a search step only on those. A fetch step's `locator_source_id` is the
  free holder of the citation's collection (`data/holders.csv`); with no holder, or with a
  `scanned_index` holder (an archive.org collection of scanned index pages with no
  page-locating step built yet), the mode is `blocked`; with a holder that has no connector
  and whose link takes nothing from the citation (`catalog.prefills_nothing`), a search to run
  by hand and not a page to save, the mode is `assisted`.
- An assertion a document decision writes from a page anyone can edit (T4 by the artifact's own
  identity or its row, `catalog.tier_sql`) is `undecided`: accepting the page never accepts its
  facts or the family memberships it states, only the persona link.
- Every `persona_fact.fact_type` and `event.event_type` must exist in `event_type`.
- A `person` is supported only by an Accepted `assertion` (on the person or an
  event of theirs). `v_unsupported_person` lists the rest; after an import that
  is everyone, by design.
- A `person.merged_into` (`tools/conclude.py merge`) marks a duplicate found and merged
  (RESEARCH-WORKFLOW §2's `duplicate_person`): its persona links (one whose persona the kept person
  already links folded onto theirs, the kept person's row taking the duplicate's decision only where
  its own is undecided), assertions, family memberships (one the kept person already holds folded onto
  theirs), name aliases (one of words the kept person already holds folded onto theirs), plan steps
  and questions move to the kept person, a question whose key the kept person already holds staying
  on the duplicate, closed as answered by the merge where it was open; every proposal naming it is
  re-pointed to the kept person, a run on a step the kept person also has is carried onto the kept
  step as a new row (the duplicate's step left on its row, skipped), one `proposal` of kind
  `duplicate_person` and one `audit_log` row record what moved and what folded, and the row itself
  stays, out of every listing, overview, plan and matcher run, holding nothing open and no decision.
  The merge run again on a merged pair completes an older merge the same way.
- One statement, one event: a record's event fact is asserted on one `event` of its type,
  the person's or the family's (`Catalog.event_for`), or on none while the choice is the
  owner's (`Catalog.unplaced`), and a person's or a family's events of one type that are one
  event (`catalog.same_event`) are one `event` row: the import writes them so, a merge folds
  them (`conclude.fold`), and the 0.7.6 migration folded once what a catalog held apart
  (`tools/initdb.py` `fold_events`, one `audit_log` row per event folded under
  `migration:0.7.6`, refused, nothing written, where two events of one group each carry the
  owner's word). A folded event keeps its row and anything left on it, out of the owner's
  events: its `event_participant` row goes.
- An `assertion` links to layer 3 (`persona_fact` or `persona`); it links only to the
  artifact when the claim is a family link or family event that a tree file states on
  the family rather than on a persona.
- Layer-4 rows belong to exactly one `tree`. Layers 1-3 are shared across trees,
  but every import creates its own `extraction` + personas: evidence is never
  auto-reused between trees (see DATA-ARCHITECTURE.md, trust boundaries).
- A `persona_relation` row runs from the persona whose role it is to the persona it is
  toward, as the record states it: a household member to the head (`child`, "Son"), a
  named relative to the record's subject (`parent`, "Father's name"). A persona with no
  outgoing `persona_relation` row is the record's own subject (`catalog.is_subject`); a
  one-person checklist row (obituary, death/birth record, cemetery, naturalization, a
  draft card, Social Security) reads held only through the person's own accepted
  subject persona, never through a relation the record merely states about them
  (`docs/RESEARCH-CHECKLIST.md` §3, §7). Household rows (census, church, passenger
  lists) are unaffected.
- Errors in records are never corrected in evidence and never deleted: they become
  `alias` rows (persons) or `place_string.variant_kind` (places) and stay searchable.
- Vendor IDs go in `external_id`, never in a primary key.
- Raw place strings go in `place_string` first; `place_id` is filled by a resolver,
  or by the owner deciding the resolver's `place_resolution` proposal on the person
  screen's fact row (`conclude.decide_place`: the chosen candidate's hierarchy, the
  resolver and status the owner's, `event.place_id` filled where every string of the
  event is resolved), and a string that is not a real place is `rejected` with its
  reason in notes. A decision on a string applies wherever the same words appear, since
  `place_string.raw` is unique, and to every string whose card offers the same places
  (`resolve_places.place_groups`), each with its own audit row.
- A `research_question` of kind `identity` (schema 0.7.7, `tools/initdb.py`'s
  `rebuild_questions` widening the kind's CHECK) names a family link or an accepted
  statement beyond the limits of one life (`Catalog.beyond_life`, the bounds in
  `data/life-limits.csv`) with both records; it is generated, never typed, closes when
  its gap has gone or the owner dismisses it, and changes nothing itself. A
  `duplicate_person` question is raised for every person, reviewed or not, and never
  counts a person merged into another.
- A `search_log` run's `outcome` is `found`, `none`, `blocked`, `error` or `unread` (schema
  0.7.8). `unread` is a record archived that no parser reads, whatever its form: every
  extraction of it is the failed one `rule:extract` writes for a file no parser claims
  (`log_search.unread_record`; an image, a record a parser, the model or a person has read,
  and a file no parser is asked to read, an item's metadata or a search's own response,
  keep `found`). `tools/attach.py` logs it for a page saved by hand, and `tools/run_step.py`
  for a connector's run whose records are all such records, a web page or a JSON or text
  response alike; the run's note begins "no parser reads this record". The record is held
  on the step's log, the step stays planned (`tools/fetches.py` does not list it again
  while its run stands on the step's fields), and nothing is closed or read. The 0.7.8
  migration (`tools/initdb.py`'s `unread_runs`, widening the outcome's CHECK by
  `rebuild_table`) turned the found runs an older attach logged for such a page into unread
  ones, one `audit_log` row each under `migration:0.7.8` naming the step, the person, the
  holder and the page and holding the run as it stood; refused, nothing written, where such
  a run sits on a step standing done.
- Living status is computed by the app (`Catalog.living`) from the person's tier
  (their generation from the home person along every family link the tree holds that is
  not rejected; `docs/DATA-ARCHITECTURE.md` §7 decision 3), held death evidence
  (`v_person_vitals.has_death_evidence`: a death, burial, cremation, probate or will event
  with a statement not rejected, so the file's undecided claim counts and a claim the owner
  rejected does not; the 0.8.4 migration, `tools/initdb.py`'s `vitals_view`, made the view
  again) and `person.living_override`; it is never stored as a bare flag.

## Date columns

Every dated row carries the same group: `date_text` (as written), `date_start`
and `date_end` (ISO, partial allowed: `1852`, `1852-03`, `1852-03-14`),
`date_qualifier`, and `calendar` (`gregorian` | `julian` | `dual` | `unknown`).
Pre-1752 English-colony dates are `dual`.

## Migrating to Postgres

Dump with `sqlite3 tree.db .dump` and load. The DDL uses no engine-specific types or clauses. The
tools do not yet: most of them and the screen use SQLite's `json_valid` /
`json_extract`, `tools/backfill_aliases.py` uses `GLOB`, and `tools/log_search.py`
uses `GROUP_CONCAT`. Those calls are the porting work.

## Tools

One line each; the tool's docstring has the rest. Every tool but `initdb.py` and
`backup.py` opens the catalog through `treelib.connect`, which refuses one whose
`schema_migration` lacks the code's version.

| Tool | Purpose |
|---|---|
| `tools/initdb.py` | Create the catalog and seed reference tables; `--sync-sources` and `--sync-event-types` bring an existing catalog up to the files; `--migrate` applies the schema versions it lacks, never touching decisions. |
| `tools/tree.py create|list|use|show|overview|home` | Manage trees; `overview` prints the tree as confirmed from the home person upward with its edge, and where the tree comes from (its people by whether the file or a record brought them in, its accepted documents by what fetched them), `home` sets that person. |
| `tools/ingest_gedcom.py <file.ged>` | Archive a GEDCOM file as a T4 artifact and load it into the active tree, every claim Undecided, the file's repeated facts of one person or family that are one event written as one event with each fact's citations. The file is read in the encoding its bytes and header say (UTF-8, UTF-16 or ANSI) and refused, nothing recorded, when the encoding does not fit, is not read here (ANSEL) or the file holds no person; it is labelled with the exporter its header names (Ancestry's export is registry row B02, a file naming no exporter the registry has is A05); the same tree refuses a repeat. It ends by saying the tree has no home person and naming `tools/tree.py home`. |
| `tools/resolve_places.py` | Resolve place strings through Nominatim (GOV and Wikidata after it for Germany, Poland and Ireland) with hierarchy verification; a state's name or abbreviation alone is the state; a part verifies only as the name in full of the candidate or a unit in its hierarchy (a prefix, a truncation or a close spelling is marked near and offered on a card), and a unique full match, or one territory under two names, is accepted, only on an answer that was not cut (a full page of six is asked again for forty); the words a record writes for another line's place (Same House) are rejected; the rest is a `place_resolution` card, one question for every spelling that offers the same places. `resolve_strings` is the same run on the strings a caller names, which the turn does for the records it brings and the person's own events. |
| `tools/backfill_aliases.py` | Undecided aliases from the names records write, and each place string's variant kind. Re-runnable. |
| `tools/checklist.py "<person>"` | Read-only foundation, questions, Group A/B rows (held / cited / missing / n/a) and the step per gap (`docs/RESEARCH-CHECKLIST.md` §6a). |
| `tools/footprint.py "<person>"` | Read-only Layer 0: duplicates, unlinked same-surname persons, records on relatives ranked by the family members they share. |
| `tools/plan.py "<person>" / --all` | Materialize questions and steps into `research_question` and `search_plan`, idempotently: a fetch step per citation or lead (a census household not wholly held among them, its households grouped again first), a search step per missing row. |
| `tools/log_search.py` | A run (found / none / blocked / error; `unread` is the attach's and the runner's word for a record no parser reads) logged on a step, per source; `--dismiss` a question (a conflict only with `--note`, its written reason), `--reopen` a step done in error, `--list` a person's plan. |
| `tools/attach_inbox.py [file ...] [--about "<person>"]` | Every inbox file to the steps its own identity fulfils: archived once, logged, extracted and matched; a step is done only when the page is the record it cites. `--about` takes one file on the owner's word: a record no step cites, or a family-held photograph or scan. |
| `tools/attach.py` | The attach path `attach_inbox.py`, `fetches.py collect` and the person screen share. |
| `tools/fetches.py next [K] / list / collect` | The pages waiting to be saved in the owner's browser, with the link, the file name to save under and the save script's call, whose key names the steps the page serves: `next` the next K, one line each, `list` all of them; `collect` brings the saved pages in by their own identity and the steps their key names. |
| `tools/run_task.py show [K] / next --model M / done [--answer TEXT --tokens N --tool-uses N --duration-ms N] / fetch [K] --model M --effort E / capture --out FILE / write` | A model run on a page the fetch list names: the task rendered from the entry, the text of its kind under `tools/tasks/`, the answer checked by `collect` and never believed, one `task_run` row per launch, by either of two launchers. `next` hands the next task to a session the owner is at, which spawns the `tree-fetch` agent with it, and `done` collects, judges and records with the measures the session was given; `fetch` is the headless launcher (`claude -p`, its input closed, the browser's tools only, no connector's). `show` prints the tasks and launches nothing; `capture` writes one headless launch's output for the check's fixtures (`done --out` a session's report); `write` writes the agent and skill files under `.claude/`. |
| `tools/run_step.py <step id> / --all` | A step run through the connectors under `tools/connectors/` its sources have, every response archived and logged, then extracted and matched; a run whose requests or whose records' reading fail is an error run, its row kept and the step left runnable. |
| `tools/cite.py "<person>" --row … --holder … --field …` | A record the owner cites on their own word: a fetch step with the citation's details, asked at the holder like a record the file cites. |
| `tools/queue.py [--all]` | Read-only. The next person at the edge of the confirmed tree a turn can act on, and why each other person is passed over; refused on a tree with no home person. |
| `tools/turn.py "<person>" / --resume` | One person's plan run end to end, its tail included; the pages it leaves for the browser are printed and the person waits on them (`<db>.turn-state.json`). `--resume` takes what was saved, credits each file to the people whose steps it reached, and finishes the turns of those who wait. |
| `tools/turns.py [--turns N]` | The loop without a hand on it: what was saved taken in first, as `turn.py --resume` does, then the queue's next person, their turn, the next, until nobody is left or N turns are done; a person who waits never stops it, and one person's failure never stops the next turn; refused on a tree with no home person. |
| `tools/extract.py <sha256 or path>` | Personas, facts and relations from an archived page or a connector's response, one parser per page kind, each entry's place on its page (the record form's locators) in its persona's `region_json`; a page no parser claims is a failed extraction. `--stale` reads again every page an older version of its parser read. |
| `tools/match.py <extraction id>` | Every persona compared with the persons the record was fetched for and their relatives: one `persona_match` or `new_person` proposal each, its rationale in words. |
| `tools/conclude.py` | The decision on a document and what it writes, the standing rule and `reconsider` (which also matches again the cards the evidence has passed by, and decides the conflicts the evidence classes settle), and the owner's word: `decide`, `fact`, `assertion`, `place`, `resolve`, `reopen`, `link`, `divorce`, `merge`, `living`. |
| `tools/facts.py` | A person's key facts as the screen and `conclude.py fact` decide them, and a vouch on the owner's own knowledge. |
| `tools/cards.py "<person>" / --all` | Read-only. Every Undecided proposal as a decision card in plain words, the same card the person screen shows. |
| `tools/proof.py "<person>" [--fact …] [--json]` | Read-only. The proof standard's written conclusion per key fact: the value, the evidence grouped by original with its class words (`data/evidence-classes.csv`) and citations, each conflict with its question id and, while open, the rule's own reading of it, the research by checklist row, who decided, and whether it meets the standard or an argument is still owed. |
| `tools/overview.py` | The tree as confirmed from the home person upward, shared by `tree.py overview` and the screen, and where the tree comes from (`origins`). |
| `tools/check.py` | Green in one command: every tool compiles, every global name a tool reads resolves (a name another module of the repository gives is one it defines), the pure rules, every parser on its saved page and every scenario on a scratch catalog, none of them sending a request, `--scenario NAME` for one (`tests/fixtures/README.md`). |
| `tools/backup.py verify / bag <dir> / check <bag>` | Fixity of every archived object, and a BagIt bag of the archive with the catalog dumped to SQL; a bag never enters git. Every write carries an audit row under `--by`. |
| `tools/catalog.py` | Read-only access to a tree's people, events, places, citations and families, shared by the tools and the screen; the one home of the name rules every tool reads a name by (its parts, short forms, titles and suffixes, Soundex and edit distance). |
| `tools/forms.py` | Read-only. The record forms (`data/record-forms.csv`, `data/DATA-SOURCES.md` §5c): the form a census of a collection and year was made on, who it names, what it states, its locators, how it bounds a household and the locator a run of lines is read by, read by the checklist, the footprint, the readers, which keep each entry's locators in its persona's `region_json`, and the household script. |
| `tools/households.py show / write` | The households read off a census form: every current census reading's entries grouped by the form's own rule (one entry one member across its copies, a FamilySearch record one household, a run of lines on one page under its head), each member's relationship to the head as stated, what is missing named; `show` prints them as grouped now and the entries in none, `write` stores them insert-only where they changed (`docs/RESEARCH-WORKFLOW.md` §5–7, households). |
| `tools/treelib.py` | Shared helpers: ULIDs, GEDCOM parsing (its encoding from the byte order mark and the header's `CHAR`), data paths, a file written whole, and `connect`. |

### How the GEDCOM ingest maps records

| GEDCOM | Catalog |
|---|---|
| file | `artifact` (sha256, manifest sidecar, `artifact_copy` on `local`; its `source_id` the registry row of the exporter `HEAD.SOUR` names, with that row's terms and cost) + one `extraction` by extractor `rule:gedcom-ingest` + one `tree_import` |
| `SOUR` record | `collection`, keyed by Ancestry dbid where the record carries Ancestry's `_APID` (the dbid learned from citations when the record lacks it); same dbid or name merges |
| `INDI` | `persona` (what the tree says) + `person` + primary `person_name` + `person_persona` Accepted with the extractor as decider (definitional: the entry is the person, `docs/DATA-ARCHITECTURE.md` §1a) + `external_id` of the file's own entry id, system `ancestry_gedcom_xref` for Ancestry's export, `<exporter>_gedcom_xref` for another exporter the header names, `gedcom_xref` for none |
| `INDI` event tags | `persona_fact` + `event` + `event_participant` + one Undecided `assertion` per citation, or one Undecided uncited assertion (citation text "the file, no citation"); `asserted_by` is the extractor |
| `INDI`-level `MARR` etc. | family event on the person's family; each distinct date/place variant is its own event shared by both spouses, so conflicting copies stay visible |
| `FAM` | `family` + `family_member` (each with an Undecided assertion on the artifact: the file states the link, no persona fact) + family events |
| `2 SOUR` / `_APID` | `assertion.citation_text` (Undecided); the unique record citations are kept in the extraction JSON for the footprint engine |
| `OBJE` | media references kept in the extraction JSON (Ancestry's export carries no image files: the images stay on Ancestry) |
| `PLAC` | `place_string` rows, status `undecided` |
| header `_TREE NOTE` | `note` on the artifact (Ancestry's own tag) |
| header `SOUR` (`NAME`, `CORP`) | the artifact's registry row (`data/data-sources.csv`: the Hosted Tree row whose name opens one of the names given, else A05) and the label of its manifest |
| header `CHAR`, byte order mark | the encoding the file is read in; the file is refused when its bytes do not fit it |
