# schema/

| File | Purpose |
|---|---|
| `catalog.sql` | Portable DDL (SQLite 3.35+ and PostgreSQL 13+). 37 tables, 6 views. Schema 0.7.4. The live catalog holds the owner's decisions, so a schema change migrates them rather than rebuilding. |
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
  rows too; the Kentucky indexes the death and birth rows, not the marriage row their
  source also sits on), and is asked a search step only on those. A fetch step's `locator_source_id` is the
  free holder of the citation's collection (`data/holders.csv`); with no holder, or with a
  `scanned_index` holder (an archive.org collection of scanned index pages with no
  page-locating step built yet), the mode is `blocked`.
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

One line each; the tool's docstring has the rest. Every tool but `initdb.py` and
`backup.py` opens the catalog through `treelib.connect`, which refuses one whose
`schema_migration` lacks the code's version.

| Tool | Purpose |
|---|---|
| `tools/initdb.py` | Create the catalog and seed reference tables; `--sync-sources` and `--sync-event-types` bring an existing catalog up to the files; `--migrate` applies the schema versions it lacks, never touching decisions. |
| `tools/tree.py create|list|use|show|overview|home` | Manage trees; `overview` prints the tree as confirmed from the home person upward with its edge, `home` sets that person. |
| `tools/ingest_gedcom.py <file.ged>` | Archive a GEDCOM 5.5.1 export as a T4 artifact and load it into the active tree, every claim Undecided; the same tree refuses a repeat. |
| `tools/resolve_places.py` | Resolve place strings through Nominatim with hierarchy verification; a unique full match, or one territory under two names, is accepted; the rest is a `place_resolution` card. |
| `tools/backfill_aliases.py` | Undecided aliases from the names records write, and each place string's variant kind. Re-runnable. |
| `tools/checklist.py "<person>"` | Read-only foundation, questions, Group A/B rows (held / cited / missing / n/a) and the step per gap (`docs/RESEARCH-CHECKLIST.md` §6a). |
| `tools/footprint.py "<person>"` | Read-only Layer 0: duplicates, unlinked same-surname persons, records on relatives ranked by the family members they share. |
| `tools/plan.py "<person>" / --all` | Materialize questions and steps into `research_question` and `search_plan`, idempotently: a fetch step per citation or lead, a search step per missing row. |
| `tools/log_search.py` | A run (found / none / blocked / error) logged on a step, per source; `--dismiss` a question, `--reopen` a step done in error, `--list` a person's plan. |
| `tools/attach_inbox.py [file ...] [--about "<person>"]` | Every inbox file to the steps its own identity fulfils: archived once, logged, extracted and matched; a step is done only when the page is the record it cites. `--about` takes one file on the owner's word: a record no step cites, or a family-held photograph or scan. |
| `tools/attach.py` | The attach path `attach_inbox.py`, `fetches.py collect` and the person screen share. |
| `tools/fetches.py next [K] / list / collect` | The pages waiting to be saved in the owner's browser, with the link and the file name to save under: `next` the next K, one line each, `list` all of them; `collect` brings the saved pages in by their own identity. |
| `tools/run_step.py <step id> / --all` | A step run through the connectors under `tools/connectors/` its sources have, every response archived and logged, then extracted and matched. |
| `tools/cite.py "<person>" --row … --holder … --field …` | A record the owner cites on their own word: a fetch step with the citation's details, asked at the holder like a record the file cites. |
| `tools/queue.py [--all]` | Read-only. The next person at the edge of the confirmed tree a turn can act on, and why each other person is passed over. |
| `tools/turn.py "<person>" / --resume` | One person's plan run end to end; pauses on the pages to save in the browser, and `--resume` collects them and runs the rule again. |
| `tools/turns.py [--turns N] / --resume` | The loop without a hand on it: the queue's next person, their turn, the next, until a turn pauses, nobody is left or N turns are done. |
| `tools/extract.py <sha256 or path>` | Personas, facts and relations from an archived page or a connector's response, one parser per page kind; a page no parser claims is a failed extraction. `--stale` reads again every page an older version of its parser read. |
| `tools/match.py <extraction id>` | Every persona compared with the persons the record was fetched for and their relatives: one `persona_match` or `new_person` proposal each, its rationale in words. |
| `tools/conclude.py` | The decision on a document and what it writes, the standing rule and `reconsider` (which also decides the conflicts the evidence classes settle), and the owner's word: `decide`, `fact`, `assertion`, `place`, `resolve`, `reopen`, `link`, `divorce`, `merge`, `living`. |
| `tools/facts.py` | A person's key facts as the screen and `conclude.py fact` decide them, and a vouch on the owner's own knowledge. |
| `tools/cards.py "<person>" / --all` | Read-only. Every Undecided proposal as a decision card in plain words, the same card the person screen shows. |
| `tools/proof.py "<person>" [--fact …] [--json]` | Read-only. The proof standard's written conclusion per key fact: the value, the evidence grouped by original with its class words (`data/evidence-classes.csv`) and citations, each conflict, the research by checklist row, who decided, and whether it meets the standard or an argument is still owed. |
| `tools/overview.py` | The tree as confirmed from the home person upward, shared by `tree.py overview` and the screen. |
| `tools/check.py` | Green in one command: every tool compiles, the pure rules, every parser on its saved page and every scenario on a scratch catalog (`tests/fixtures/README.md`). |
| `tools/backup.py verify / bag <dir> / check <bag>` | Fixity of every archived object, and a BagIt bag of the archive with the catalog dumped to SQL; a bag never enters git. |
| `tools/catalog.py` | Read-only access to a tree's people, events, places, citations and families, shared by the tools and the screen. |
| `tools/treelib.py` | Shared helpers: ULIDs, GEDCOM parsing, data paths, and `connect`. |

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
