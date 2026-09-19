# schema/

| File | Purpose |
|---|---|
| `catalog.sql` | Portable DDL (SQLite 3.35+ and PostgreSQL 13+). 37 tables, 6 views. Schema 0.7.2. The live catalog holds the owner's decisions, so a schema change now migrates them rather than rebuilding. |
| `seed_event_type.sql` | Event/attribute taxonomy borrowed from Gramps with GEDCOM 7 tags. |
| `sqlite_extras.sql` | SQLite-only: FTS5 tables on extraction text, persona names, notes; immutability triggers on archive and evidence rows. |
| `manifest.schema.json` | JSON Schema for the provenance sidecar written next to every archived object. |

Build a fresh catalog with `tools/initdb.py` (add `--force` to overwrite). It seeds
`source` from `data/data-sources.csv`, so the CSV stays the registry of record;
after any change to the CSV run `tools/initdb.py --sync-sources` on an existing
catalog, or the plan stops with the missing source ids. `data/holders.csv` (free
holders of cited collections) is read by the tools directly.

## Table map by layer

```
1 REFERENCE    source, collection, event_type, place, place_name, place_string
2 ARCHIVE      artifact, artifact_locator, artifact_page, derivative, tombstone
3 EVIDENCE     extractor, extraction, persona, persona_fact, persona_relation
4 CONCLUSIONS  tree, tree_import, person, person_name, family, family_member, event,
               event_participant, person_persona, assertion, proposal, external_id, alias, note,
               research_question, search_plan, search_log
               (tree-scoped: person, family, event, assertion, proposal, note, tree_import,
                research_question, search_log; search_plan through its person)
OPS            schema_migration, audit_log, storage_target, artifact_copy
VIEWS          v_person_vitals, v_unsupported_person, v_unsupported_event,
               v_artifact_under_replicated, v_external_id_collision, v_person_search_key
```

## Invariants (enforced by DB where possible, otherwise by the app)

- `artifact`, `persona`, `persona_fact` are insert-only. Triggers abort UPDATE/DELETE.
  Corrections are new rows; removals are `tombstone` rows.
- Decisions are three-state: `undecided` | `accepted` | `rejected` on `assertion`,
  `person_persona`, `place_string`, `alias`, `proposal`. No numeric confidence columns.
- `search_plan.mode` is `auto` only when `source.connector` names a built connector
  that answers the step's checklist row; the registry's free text never decides it. A
  connector may declare the rows it answers (`ROWS` in `tools/connectors/`: the New
  Jersey death index the death row alone, its source sitting on the birth and marriage
  rows too), and is asked a search step only on those. A fetch step's `locator_source_id` is the
  free holder of the citation's collection (`data/holders.csv`); with no holder the
  mode is `blocked`.
- An assertion a document decision writes from a page anyone can edit (T4 by the artifact's own
  identity or its row, `catalog.tier_sql`) is `undecided`: accepting the page never accepts its
  facts or the family memberships it states, only the persona link.
- Every `persona_fact.fact_type` and `event.event_type` must exist in `event_type`.
- A `person` is supported only by an Accepted `assertion` (on the person or an
  event of theirs). `v_unsupported_person` lists the rest; after an import that
  is everyone, by design.
- A `person.merged_into` (`tools/conclude.py merge`) marks a duplicate found and merged
  (RESEARCH-WORKFLOW §2's `duplicate_person`): its persona links, assertions, plan steps,
  search log rows and open questions move to the kept person, one `proposal` of kind
  `duplicate_person` and one `audit_log` row record what moved, and the row itself stays,
  out of every listing, overview, plan and matcher run.
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
  `place_string.raw` is unique.
- Living status is computed by the app (`Catalog.living`) from the person's tier
  (their generation from the home person along the tree's family links, accepted or
  claimed; `docs/DATA-ARCHITECTURE.md` §7 decision 3), held death evidence
  (`v_person_vitals.has_death_evidence`) and `person.living_override`; it is never
  stored as a bare flag.

## Date columns

Every dated row carries the same group: `date_text` (as written), `date_start`
and `date_end` (ISO, partial allowed: `1852`, `1852-03`, `1852-03-14`),
`date_qualifier`, and `calendar` (`gregorian` | `julian` | `dual` | `unknown`).
Pre-1752 English-colony dates are `dual`.

## Migrating to Postgres

Dump with `sqlite3 tree.db .dump`, drop the `fts_*` tables and triggers, load,
then add tsvector indexes. The DDL uses no engine-specific types or clauses. The
tools do not yet: most of them and the screen use SQLite's `json_valid` /
`json_extract`, `tools/backfill_aliases.py` uses `GLOB`, and `tools/log_search.py`
and `tools/resolve_places.py` use `GROUP_CONCAT`. Those calls are the porting work.

## Tools

| Tool | Purpose |
|---|---|
| `tools/initdb.py` | Create the catalog and seed reference tables (`--force` to rebuild); `--sync-sources` and `--sync-event-types` bring an existing catalog's registry rows and event types up to the files; `--migrate` applies to an existing catalog whatever `schema/catalog.sql` has added since its `schema_migration` row, column by column, without touching decisions. |
| `tools/tree.py create|list|use|show|overview|home` | Manage trees (profiles). `overview` prints the tree as confirmed from the home person upward with its edge (`tools/overview.py`, shared with the screen); `use` sets the active tree in `catalog/.active-tree`; `home "<person>"` sets the person the overview lays the family out from; every tree-scoped tool also accepts `--tree` and `$TREE`. |
| `tools/ingest_gedcom.py <file.ged>` | Archive a GEDCOM 5.5.1 export as a T4 artifact and load it into the active tree. Files from `inbox/` are moved to `trees/<slug>/imports/<date>_<name>` (`--keep` copies instead). The same bytes may be imported into different trees; the same tree refuses a repeat. |
| `tools/resolve_places.py` | Resolve `place_string` rows via Nominatim: parse + normalize, verify every given component against the candidate's hierarchy, auto-accept a unique full match, and also a string whose verified candidates are one territory under two names (a city and the county coterminous with it), tested on the geocoder's own boundingboxes coinciding within a small tolerance; everything else — including a place genuinely nested in a larger, differently-sized unit of the same name — stays Undecided with a tree-scoped `place_resolution` proposal carrying every verified candidate. Then fills `event.place_id` only where every supporting fact resolved to the same place (audit-logged per event). `--reset` undoes AI-made resolutions and keeps human ones. One audit row per string accepted, rejected or reset, under `--by`. Overrides in `data/place-overrides.json`. Responses cached under `derivatives/geocode/`. |
| `tools/backfill_aliases.py` | Create `undecided` aliases from as-written persona names; set `place_string.variant_kind`; write a note on a person whose canonical name carries a code. Re-runnable. |
| `tools/checklist.py "<person>"` | Read-only per-person checklist and gap generator (`docs/RESEARCH-CHECKLIST.md` §6a): foundation, questions, Group A/B rows with held / cited / missing / n/a, pre-built step per gap with `{value, basis}` fields. Before review: fetch steps only. `--json`, `--all`. |
| `tools/footprint.py "<person>"` | Read-only Layer 0: duplicate check, unlinked same-surname persons as hints, records on relatives ranked by shared family members and by what they settle, collections to search next. Used by `checklist.py`; shown only once the baseline is reviewed. |
| `tools/plan.py "<person>" / --all` | Materialize fact-level questions and executable steps into `research_question` / `search_plan` from the checklist and footprint: one fetch step per citation with its locator, the citation's own details as fields (basis `citation`) and the free holder of its collection as locator source (`blocked` when there is none), one search step per missing row with `{value, basis}` fields and a registry-driven mode; one fetch step per photograph typed Grave on a memorial accepted as the person's own (the stone itself, registry row E05, the image's URL as locator); idempotent; drops steps no longer generated (done ones stay; one run but not done is kept for its log as `skipped`, planned again if generated again); marks a fetch step done when an archived record holds its citation for the person (its own record id, a sheet image of the page, or a record page naming the person); logs a household record (a census page, whichever way it arrived) accepted onto the person found on their own step for its census year (`log_search.hold_household`), so the row reads held and no runner searches that census again; closes questions whose gap has gone; leaves dismissed ones closed. |
| `tools/log_search.py --step <id> --outcome …` | Record a run (found / none / blocked / error) with the step's fields as rendered after include/revise; a run logged `error` is a source that did not answer, not a run on the fields, so the step stays runnable at that source and the next turn asks it again; each source's runs are read on their own (`search_log.source_id`), so a step at two connectors is closed at one by its own found or none run and stays open at the other; `--dismiss <question id>` closes a question for good; `--list "<person>"` shows the plan with outcomes. `hold_household` logs a household record accepted onto a person found on their own step for its census year (`extract.household_row`), and `release_household` plans it again on a rejection. |
| `tools/attach_inbox.py [file ...]` | Attach every inbox file (or the named ones) to the fetch steps its own identity fulfils: the memorial id or ark read from the file (kept as an `artifact_locator` too; the identity also names the holder the page came from and, for a FamilySearch record, its own collection), a gravestone photograph by the name the fetch list gave it (an image carries none in its bytes; archived under E05, not parsed), the file archived once, a found run logged on each step (a record of no census page reaches the person's checklist row of its kind: an obituary collection the obituary row, a death index the death record row), then the extractor and matcher once. A file matching no step stays in the inbox. `tools/attach.py` is the shared path the person screen's attach uses too. |
| `tools/run_step.py <step id> / --all` | Run a step through every connector its sources have (`loc_gov`, `nara_1950`, `ia_newspapers`, `ia_directories`, `ia_books`, `wikitree`, `va_graves`, `nj_death_index`; a connector that declares the rows it answers is asked a search step on those rows alone), one log row per source: an auto search step, or a fetch step at its holder's connector (the 1950 site by surname within the citation's enumeration district; the Archive by a cited book's title; the gravesite locator by the citation's name) and at those of its row's sources (a cited obituary at the Archive's newspapers and loc.gov in the paper's year). The search inside an Archive item is asked once per spelling of the surname the alias table holds for the step's person; a book the Archive only lends is a `none` run with the reason. A request may post a form, name the identity its response is archived under, and say the response is itself the record. A step whose years fall outside the source's coverage years (the registry column) is logged `none` without a request; so is a step whose fields give a connector nothing to ask (`connector.wants`: a birth or death year, a state, a title), the note naming the field, so the step is asked again once the plan writes it. A fetched response may name more to fetch (an Archive item's metadata, the search inside it, its page images). A step is asked at the connectors whose source has no found or none run on its current fields (`--all` and the turn), or at every one by its id; the other connectors' last answers are reported, not asked again. Every request at the source's rate, a search paging on while the connector says the total stays small and the note saying what to add to the step when it does not, every response archived with the request URL as locator, one log row with the query and outcome, the household's other steps logged found for the same page, then the extractor and `conclude.match_record` on each hit's record; a run whose records are results listings (`extract.RESULTS_LISTINGS`, one persona per row) is found only when a row fits a person, else none with the reason, the rows kept on the artifact as candidates. `--dry-run` prints the requests, saying per connector whether it would be asked. |
| `tools/queue.py [--all]` | Read-only. The next person at the edge of the confirmed tree in `tools/tree.py overview`'s own order: a parent or spouse the file names whose link is not yet accepted before the card's own person, then a confirmed person with an open question a turn can still act on (a step one of whose connectors' sources has no run on its current fields, an error run not counting, or a page the fetch list can name, read the way the runner's runnable steps and the fetch list read a run: per source); a person whose open question is the owner's alone is passed over with the reason. `--all` lists everyone. |
| `tools/turn.py "<person>" / --resume` | One person's plan run end to end (`docs/RESEARCH-WORKFLOW.md` §8): `plan_person`, every step `run_step.runnable` takes on this person's plan, one commit each, then the person's own pages at holders without a connector printed for the owner's browser session and the turn paused with its state beside the catalog (`<db>.turn-state.json`; a page the list cannot name is passed over with the reason); `--resume` runs `fetches.collect`, `attach_inbox`, `conclude.reconsider` and the plan again, as does a turn with nothing to fetch. Writes nothing of its own; reports held, decided, created and left in words, the sources that did not answer named under left. |
| `tools/turns.py [--turns N] / --resume` | The loop run without a hand on it (`docs/RESEARCH-WORKFLOW.md` §8): `queue.edge` names the next person, `turn.start` runs their turn and prints its report, and the queue is asked again, until it names nobody a turn can act on, a turn pauses on pages to save (the runner stops with the list printed and the turn's state kept; `--resume` runs `turn.resume` and goes on), or N turns are done, the resumed turn counted. A person the queue names again whose last turn held nothing new for them (records found on their steps and accepted on their personas, counted before and after) is passed over for the rest of the run with that reason. Its own state, `<db>.loop-state.json` beside the turn's, holds the turns and the passed-over and is cleared when the run ends; it writes nothing of its own to the catalog. The summary names the turns, the people passed over and why, and what is left for the owner: the queue's own pass-overs and a paused turn's pages. |
| `tools/cite.py "<person>" --row … --holder … --field …` | A record the owner cites on their own word, nothing in the file and nothing archived yet: a fetch step on the person's plan carrying the citation's details as the owner gives them (each field basis `owner`) with the holder as its locator source, asked at the holder's connector like a record the file cites (`attach.cite_on_word`); the planner never drops it. |
| `tools/fetches.py list / collect` | Every planned fetch step whose holder has no connector, once per page (a page is open for a step while the step's own source, the holder or the row's first source, has no run on its current fields; a row source's connector answering the same step does not stand for the holder's page): the holder, the link (the memorial page; the holder's search prefilled from the citation's details; a gravestone photograph's own image), the people waiting on it, and the file name to save under, said to be an image where it is; leads from held records first. `collect` moves the pages and photographs saved by the browser from the download folder into `inbox/` and attaches each by its own identity (a photograph's is in its name), and a page from a holder without a parser by the name the list printed, which ends in the six characters of the person it was listed for: to that person's steps on that page, archived under the holder with its own URL, logged found, unparsed until a parser claims it. |
| `tools/attach.py` `attach_held` | A family-held file from the inbox with no record identity, archived under M05 on the owner's word about whom it concerns, filed under the tree, read afterwards one persona at a time. |
| `tools/cards.py "<person>" / --all` | Read-only. Every Undecided proposal about a person (or everyone) as one decision card in plain text (`--json` for data): highlight, the person and the file's claim, the record with holder, collection, identity and tier, the archived path and the holder's page, each field as agrees / disagrees / absent, the relationships stated and how each persona on the record stands, what accepting closes, anything odd. The person screen's proposal panel shows the same card from the same function. |
| `tools/extract.py <sha256 or path>` | Parse an archived record page (HTML) into one extraction: a Find a Grave memorial by `rule:findagrave-memorial@0.3.0` (verified on a real memorial; the inscription and the biography as facts of their own, as written; every photograph with the type the page gives it in the parsed page), a Find a Grave search results page by `rule:findagrave-search@0.1.0` (one persona per row, the memorial id and URL as its identity; verified on two real pages), a FamilySearch search results page by `rule:familysearch-search@0.1.0` (one persona per row with the record's ark as its identity, the row's events and named relatives; verified on a real page), a FamilySearch record page by `rule:familysearch-record@0.1.0` (verified on real pages; the relatives its fields name become personas), an Ancestry index page by `rule:ancestry-index@0.1.0` (not yet verified on a real page), a 1950 census site response by `rule:nara-1950-schedule@0.1.0`, a loc.gov OCR response by `rule:loc-gov-ocr@0.1.0`, an AAD enlistment results page by `rule:aad-search@0.1.0`, a full enlistment record by `rule:aad-enlistment@0.1.0`, a WikiTree profile with its relatives by `rule:wikitree-profile@0.1.0`, a VA gravesite locator results page by `rule:va-gravesite@0.1.0` (one persona per decedent: name, dates, burial with section and site, rank and war period); a page no parser claims gets a failed extraction by `rule:extract@0.1.0`. A persona per person named, a fact per field as written, a relation per stated relationship, the raw parsed page in `structured_json`. Run on arrival by the person screen's attach; a second run, at any version, supersedes the first, rejects its undecided proposals, carries decided links to the new personas of the same name and role, and matches the rest again. |
| `tools/match.py <extraction id>` | Compare every persona of an extraction with the persons the record was fetched for (the step it came through, every fetch step naming the same record or census page) and their relatives on name, sex, birth and death dates (as dates), burial and death place and stated relationships; write one `persona_match` or `new_person` proposal per persona with a plain-words rationale. Run on every extraction as it is written, followed by the standing rule (`conclude.match_record`); re-running adds nothing. |
| `tools/conclude.py` (module) | The decision on a document and what follows from it: `decide` accepts or rejects a persona match or new person (or, on a `place_resolution` proposal, records the owner's answer on a place string: `decide_place`), writing Accepted assertions for every fact the record states onto the person's events and attributes (created when the tree had none) and for the family links it states with persons already matched on it, regenerating the person's plan (which logs a household record, a census page whichever way it arrived, found on the person's own step for its census year so their row reads held: `log_search.hold_household`; a rejection plans the step again, `release_household`), and on a page anyone can edit an identity: the link accepted, the family memberships it states created where the tree lacks them with an Undecided assertion each, the facts written undecided too; `rule_accepts` says whether the standing rule takes a match and why, judging a record read by hand or by the model exactly as one a rule parsed, by its own kind, tier and agreeing facts, never by who read it (the identity on an editable page when the name and three of birth day, death day, burial place, a stated parent or spouse agree; an obituary or newspaper text once read is such a kind only when a stated relative among its points is that relative in the tree on trusted evidence, dates and places alone never enough); `match_record` runs the matcher then the rule; `reconsider` re-examines every rule decision as the rule stands now and every card still undecided, `withdraw` takes back a decision it would no longer make, the record a card again, and a card it would now take it takes; `link_on_word` and `divorce` write the owner's word on a family link a record stops short of, or a Divorce event; `merge` closes a `duplicate_person` question by moving a duplicate's persona links, assertions, plan steps, search log rows and open questions onto the person it duplicates, sets `person.merged_into`, and writes one `duplicate_person` proposal and one audit row naming what moved; `living "<person>" living|deceased|unknown` writes the owner's word on whether a person is alive (`person.living_override`, one audit row; `unknown` clears it, the tier rule deciding again). A rule decision can be rejected by a person. Used by the person screen, the attach, the runner and the extractor; `reconsider`, `link`, `divorce`, `merge` and `living` are its commands. |
| `tools/check.py` | Green in one command, the runner: every tool compiles; the pure rules on `tests/fixtures/rules.json` and the connectors' offline reading on `tests/fixtures/connectors.json`; then `tests/checks/parsers.py` reads every saved real page under `tests/fixtures/` on a scratch catalog against the `<stem>.expect.json` beside it; then `tests/checks/scenario.py` and `tests/checks/loop.py` ingest `tests/fixtures/harness.ged` (the owner's export cut down by `tests/checks/cut_gedcom.py`) into a scratch per scenario under `tests/fixtures/scenarios/` and run the matcher, the standing rule, the writers and the loop's tools as each scenario says, checking what they write and refuse. Nothing in the harness names a person; `tests/fixtures/README.md` documents the sidecar and scenario vocabulary. `--show` prints what each reading and step did, `--keep` leaves the scratches in place. |
| `tools/backup.py verify / bag <dir> / check <bag>` | Fixity and backup: every object under `archive/objects` hashed against its sha256 and the result on `artifact_copy` (`--sample N` for a random scrub); a BagIt 1.0 bag of the archive with a plain-SQL dump of the catalog inside, the bag's payload manifest the fixity record of that copy, and with `--target <drive>` each object recorded as a verified copy on that storage target so `v_artifact_under_replicated` goes quiet; a bag on its drive hashed against its manifest. A bag holds living-person data and never enters git. |
| `tools/catalog.py` | Read-only access to a tree's people, events, places, citations and families, and `tier_sql`, an artifact's effective trust tier from its own identity; shared by every tool and the screen. |
| `tools/treelib.py` | Shared helpers: ULID, GEDCOM line parser, GEDCOM date grammar, archive paths. |

### How the GEDCOM ingest maps records

| GEDCOM | Catalog |
|---|---|
| file | `artifact` (sha256, manifest sidecar, `artifact_copy` on `local`) + one `extraction` by extractor `rule:gedcom-ingest` + one `tree_import` |
| `SOUR` record | `collection` keyed by Ancestry dbid (dbid learned from citations when the record lacks `_APID`; same dbid or name merges) |
| `INDI` | `persona` (what the tree says) + `person` + primary `person_name` + `person_persona` Accepted with the extractor as decider (definitional: the entry is the person, `docs/DATA-ARCHITECTURE.md` §1a) + `external_id ancestry_gedcom_xref` |
| `INDI` event tags | `persona_fact` + `event` + `event_participant` + one Undecided `assertion` per citation, or one Undecided uncited assertion; `asserted_by` is the extractor |
| `INDI`-level `MARR` etc. | family event on the person's family; each distinct date/place variant is its own event shared by both spouses, so conflicting copies stay visible |
| `FAM` | `family` + `family_member` (each with an Undecided assertion on the artifact: the file states the link, no persona fact) + family events |
| `2 SOUR` / `_APID` | `assertion.citation_text` (Undecided); the unique record citations are kept in the extraction JSON for the footprint engine |
| `OBJE` | media references kept in the extraction JSON (the images are not in the export) |
| `PLAC` | `place_string` rows, status `undecided` |
| header `_TREE NOTE` | `note` on the artifact |
