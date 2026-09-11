# schema/

| File | Purpose |
|---|---|
| `catalog.sql` | Portable DDL (SQLite 3.35+ and PostgreSQL 13+). 37 tables, 6 views. Schema 0.7.1. The live catalog holds the owner's decisions, so a schema change now migrates them rather than rebuilding. |
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
- `search_plan.mode` is `auto` only when `source.connector` names a built connector;
  the registry's free text never decides it. A fetch step's `locator_source_id` is the
  free holder of the citation's collection (`data/holders.csv`); with no holder the
  mode is `blocked`.
- Every `persona_fact.fact_type` and `event.event_type` must exist in `event_type`.
- A `person` is supported only by an Accepted `assertion` (on the person or an
  event of theirs). `v_unsupported_person` lists the rest; after an import that
  is everyone, by design.
- An `assertion` links to layer 3 (`persona_fact` or `persona`); it links only to the
  artifact when the claim is a family link or family event that a tree file states on
  the family rather than on a persona.
- Layer-4 rows belong to exactly one `tree`. Layers 1-3 are shared across trees,
  but every import creates its own `extraction` + personas: evidence is never
  auto-reused between trees (see DATA-ARCHITECTURE.md, trust boundaries).
- A `persona_relation` row runs from the persona whose role it is to the persona it is
  toward, as the record states it: a household member to the head (`child`, "Son"), a
  named relative to the record's subject (`parent`, "Father's name").
- Errors in records are never corrected in evidence and never deleted: they become
  `alias` rows (persons) or `place_string.variant_kind` (places) and stay searchable.
- Vendor IDs go in `external_id`, never in a primary key.
- Raw place strings go in `place_string` first; `place_id` is filled by a resolver,
  and a string that is not a real place is `rejected` with its reason in notes.
- Living status is computed by the app from `v_person_vitals` with the 100-year
  default and `person.living_override`; it is never stored as a bare flag.

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
| `tools/initdb.py` | Create the catalog and seed reference tables (`--force` to rebuild); `--sync-sources` and `--sync-event-types` bring an existing catalog's registry rows and event types up to the files. |
| `tools/tree.py create|list|use|show|overview|home` | Manage trees (profiles). `overview` prints the tree as confirmed from the home person upward with its edge (`tools/overview.py`, shared with the screen); `use` sets the active tree in `catalog/.active-tree`; `home "<person>"` sets the person the overview lays the family out from; every tree-scoped tool also accepts `--tree` and `$TREE`. |
| `tools/ingest_gedcom.py <file.ged>` | Archive a GEDCOM 5.5.1 export as a T4 artifact and load it into the active tree. Files from `inbox/` are moved to `trees/<slug>/imports/<date>_<name>` (`--keep` copies instead). The same bytes may be imported into different trees; the same tree refuses a repeat. |
| `tools/resolve_places.py` | Resolve `place_string` rows via Nominatim: parse + normalize, verify every given component against the candidate's hierarchy, auto-accept only unique full matches (or safe nested/coterminous choices), everything else stays Undecided with a tree-scoped `place_resolution` proposal. Then fills `event.place_id` only where every supporting fact resolved to the same place (audit-logged per event). `--reset` undoes AI-made resolutions and keeps human ones. One audit row per string accepted, rejected or reset, under `--by`. Overrides in `data/place-overrides.json`. Responses cached under `derivatives/geocode/`. |
| `tools/backfill_aliases.py` | Create `undecided` aliases from as-written persona names; set `place_string.variant_kind`; write a note on a person whose canonical name carries a code. Re-runnable. |
| `tools/checklist.py "<person>"` | Read-only per-person checklist and gap generator (`docs/RESEARCH-CHECKLIST.md` §6a): foundation, questions, Group A/B rows with held / cited / missing / n/a, pre-built step per gap with `{value, basis}` fields. Before review: fetch steps only. `--json`, `--all`. |
| `tools/footprint.py "<person>"` | Read-only Layer 0: duplicate check, unlinked same-surname persons as hints, records on relatives ranked by shared family members and by what they settle, collections to search next. Used by `checklist.py`; shown only once the baseline is reviewed. |
| `tools/plan.py "<person>" / --all` | Materialize fact-level questions and executable steps into `research_question` / `search_plan` from the checklist and footprint: one fetch step per citation with its locator, the citation's own details as fields (basis `citation`) and the free holder of its collection as locator source (`blocked` when there is none), one search step per missing row with `{value, basis}` fields and a registry-driven mode; idempotent; drops steps no longer generated (done ones stay; one run but not done is kept for its log as `skipped`, planned again if generated again); marks a fetch step done when an archived record holds its citation for the person (its own record id, a sheet image of the page, or a record page naming the person); closes questions whose gap has gone; leaves dismissed ones closed. |
| `tools/log_search.py --step <id> --outcome …` | Record a run (found / none / blocked / error) with the step's fields as rendered after include/revise; `--dismiss <question id>` closes a question for good; `--list "<person>"` shows the plan with outcomes. |
| `tools/attach_inbox.py [file ...]` | Attach every inbox file (or the named ones) to the fetch steps its own identity fulfils: the memorial id or ark read from the file (kept as an `artifact_locator` too; the identity also names the holder the page came from and, for a FamilySearch record, its own collection), the file archived once, a found run logged on each step (a record of no census page reaches the person's checklist row of its kind: an obituary collection the obituary row, a death index the death record row), then the extractor and matcher once. A file matching no step stays in the inbox. `tools/attach.py` is the shared path the person screen's attach uses too. |
| `tools/run_step.py <step id> / --all` | Run a step through every connector its sources have (`loc_gov`, `nara_1950`, `ia_newspapers`, `ia_directories`, `ia_books`, `wikitree`), one log row per source: an auto search step, or a fetch step whose holder has one (the 1950 site by surname within the citation's enumeration district). A fetched response may name more to fetch (an Archive item's metadata, the search inside it, its page images). Every request at the source's rate, a search paging on while the connector says the total stays small and the note saying what to add to the step when it does not, every response archived with the request URL as locator, one log row with the query and outcome, the household's other steps logged found for the same page, then the extractor and `conclude.match_record` on each hit's record. `--dry-run` prints the requests. |
| `tools/fetches.py list / collect` | Every planned fetch step whose holder has no connector, once per page: the holder, the link (the memorial page; the holder's search prefilled from the citation's details), the people waiting on it, and the file name to save under; leads from held records first. `collect` moves the pages saved by the browser from the download folder into `inbox/` and attaches each by its own identity. |
| `tools/attach.py` `attach_held` | A family-held file from the inbox with no record identity, archived under M05 on the owner's word about whom it concerns, filed under the tree, read afterwards one persona at a time. |
| `tools/cards.py "<person>" / --all` | Read-only. Every Undecided proposal about a person (or everyone) as one decision card in plain text (`--json` for data): highlight, the person and the file's claim, the record with holder, collection, identity and tier, the archived path and the holder's page, each field as agrees / disagrees / absent, the relationships stated and how each persona on the record stands, what accepting closes, anything odd. The person screen's proposal panel shows the same card from the same function. |
| `tools/extract.py <sha256 or path>` | Parse an archived record page (HTML) into one extraction: a Find a Grave memorial by `rule:findagrave-memorial@0.2.0` (verified on a real memorial; the inscription and the biography as facts of their own, as written), a Find a Grave search results page by `rule:findagrave-search@0.1.0` (one persona per row, the memorial id and URL as its identity; verified on two real pages), a FamilySearch search results page by `rule:familysearch-search@0.1.0` (one persona per row with the record's ark as its identity, the row's events and named relatives; verified on a real page), a FamilySearch record page by `rule:familysearch-record@0.1.0` (verified on real pages; the relatives its fields name become personas), an Ancestry index page by `rule:ancestry-index@0.1.0` (not yet verified on a real page), a 1950 census site response by `rule:nara-1950-schedule@0.1.0`, a loc.gov OCR response by `rule:loc-gov-ocr@0.1.0`, an AAD enlistment results page by `rule:aad-search@0.1.0`, a full enlistment record by `rule:aad-enlistment@0.1.0`, a WikiTree profile with its relatives by `rule:wikitree-profile@0.1.0`; a page no parser claims gets a failed extraction by `rule:extract@0.1.0`. A persona per person named, a fact per field as written, a relation per stated relationship, the raw parsed page in `structured_json`. Run on arrival by the person screen's attach; a second run, at any version, supersedes the first, rejects its undecided proposals, carries decided links to the new personas of the same name and role, and matches the rest again. |
| `tools/match.py <extraction id>` | Compare every persona of an extraction with the persons the record was fetched for (the step it came through, every fetch step naming the same record or census page) and their relatives on name, sex, birth and death dates (as dates), burial and death place and stated relationships; write one `persona_match` or `new_person` proposal per persona with a plain-words rationale. Run on every extraction as it is written, followed by the standing rule (`conclude.match_record`); re-running adds nothing. |
| `tools/conclude.py` (module) | The decision on a document and what follows from it: `decide` accepts or rejects a persona match or new person, writing Accepted assertions for every fact the record states onto the person's events and attributes (created when the tree had none) and for the family links it states with persons already matched on it; `rule_accepts` says whether the standing rule takes a match and why; `match_record` runs the matcher then the rule; `reconsider` re-examines every rule decision as the rule stands now and `withdraw` takes back one it would no longer make, the record a card again; `link_on_word` and `divorce` write the owner's word on a family link a record stops short of, or a Divorce event. A rule decision can be rejected by a person. Used by the person screen, the attach, the runner and the extractor; `reconsider`, `link` and `divorce` are its commands. |
| `tools/check.py` | Green in one command: every tool compiles; every parser read against its saved real page under `tests/fixtures/` on a scratch catalog under a temporary data root, the personas, facts and relations checked against the page; then `tests/fixtures/harness.ged` ingested into a second scratch catalog and the matcher, the standing rule and the decision writers run on the pages against it, what each writes and refuses checked; `--show` prints what each wrote, `--keep` leaves the scratches in place. |
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
