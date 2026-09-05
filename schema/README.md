# schema/

| File | Purpose |
|---|---|
| `catalog.sql` | Portable DDL (SQLite 3.35+ and PostgreSQL 13+). 34 tables, 6 views. Schema 0.4.0; no deployed catalogs exist yet, so changes rebuild rather than migrate. |
| `seed_event_type.sql` | Event/attribute taxonomy borrowed from Gramps with GEDCOM 7 tags. |
| `sqlite_extras.sql` | SQLite-only: FTS5 tables on extraction text, persona names, notes; immutability triggers on archive and evidence rows. |
| `manifest.schema.json` | JSON Schema for the provenance sidecar written next to every archived object. |

Build a fresh catalog with `tools/initdb.py` (add `--force` to overwrite). It seeds
`source` from `data/data-sources.csv`, so the CSV stays the registry of record.

## Table map by layer

```
1 REFERENCE    source, collection, event_type, place, place_name, place_string
2 ARCHIVE      artifact, artifact_locator, artifact_page, derivative, tombstone
3 EVIDENCE     extractor, extraction, persona, persona_fact, persona_relation
4 CONCLUSIONS  tree, tree_import, person, person_name, family, family_member, event,
               event_participant, person_persona, assertion, proposal, external_id, alias, note
               (tree-scoped: person, family, event, assertion, proposal, note, tree_import)
OPS            schema_migration, audit_log, storage_target, artifact_copy
VIEWS          v_person_vitals, v_unsupported_person, v_unsupported_event,
               v_artifact_under_replicated, v_external_id_collision, v_person_search_key
```

## Invariants (enforced by DB where possible, otherwise by the app)

- `artifact`, `persona`, `persona_fact` are insert-only. Triggers abort UPDATE/DELETE.
  Corrections are new rows; removals are `tombstone` rows.
- Decisions are three-state: `undecided` | `accepted` | `rejected` on `assertion`,
  `person_persona`, `place_string`, `alias`, `proposal`. No numeric confidence columns.
- Every `persona_fact.fact_type` and `event.event_type` must exist in `event_type`.
- A `person` is supported only by an Accepted `assertion` (on the person or an
  event of theirs). `v_unsupported_person` lists the rest; after an import that
  is everyone, by design.
- Layer-4 rows belong to exactly one `tree`. Layers 1-3 are shared across trees,
  but every import creates its own `extraction` + personas: evidence is never
  auto-reused between trees (see DATA-ARCHITECTURE.md, trust boundaries).
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
then add tsvector indexes. The DDL uses no engine-specific types or clauses.

## Tools

| Tool | Purpose |
|---|---|
| `tools/initdb.py` | Create the catalog and seed reference tables (`--force` to rebuild). |
| `tools/tree.py create|list|use|show` | Manage trees (profiles). `use` sets the active tree in `catalog/.active-tree`; every tool also accepts `--tree` and `$TREE`. |
| `tools/ingest_gedcom.py <file.ged>` | Archive a GEDCOM 5.5.1 export as a T4 artifact and load it into the active tree. Files from `inbox/` are moved to `trees/<slug>/imports/<date>_<name>` (`--keep` copies instead). The same bytes may be imported into different trees; the same tree refuses a repeat. |
| `tools/resolve_places.py` | Resolve `place_string` rows via Nominatim: parse + normalize, verify every given component against the candidate's hierarchy, auto-accept only unique full matches (or safe nested/coterminous choices), everything else stays Undecided with a tree-scoped `place_resolution` proposal. Then fills `event.place_id` only where every supporting fact resolved to the same place (audit-logged per event). `--reset` undoes AI-made resolutions and keeps human ones. Overrides in `data/place-overrides.json`. Responses cached under `derivatives/geocode/`. |
| `tools/backfill_aliases.py` | Create `undecided` aliases from as-written persona names; set `place_string.variant_kind`; propose fixes for canonical names containing codes. Re-runnable. |
| `tools/checklist.py "<person>"` | Read-only per-person checklist and gap generator (`docs/RESEARCH-CHECKLIST.md` §6a): foundation, questions, Group A/B rows with held / cited / missing / n/a, pre-built search step per gap. `--json`, `--all`. |
| `tools/treelib.py` | Shared helpers: ULID, GEDCOM line parser, GEDCOM date grammar, archive paths. |

### How the GEDCOM ingest maps records

| GEDCOM | Catalog |
|---|---|
| file | `artifact` (sha256, manifest sidecar, `artifact_copy` on `local`) + one `extraction` by extractor `rule:gedcom-ingest` + one `tree_import` |
| `SOUR` record | `collection` keyed by Ancestry dbid (dbid learned from citations when the record lacks `_APID`; same dbid or name merges) |
| `INDI` | `persona` (what the tree says) + `person` + primary `person_name` + accepted `person_persona` + `external_id ancestry_gedcom_xref` |
| `INDI` event tags | `persona_fact` + `event` + `event_participant` + one Undecided `assertion` per citation, or one Undecided uncited assertion |
| `INDI`-level `MARR` etc. | family event on the person's family; each distinct date/place variant is its own event shared by both spouses, so conflicting copies stay visible |
| `FAM` | `family` + `family_member` (each with an assertion) + family events |
| `2 SOUR` / `_APID` | `assertion.citation_text` (Undecided); the unique record citations are kept in the extraction JSON for the footprint engine |
| `OBJE` | media references kept in the extraction JSON (the images are not in the export) |
| `PLAC` | `place_string` rows, status `undecided` |
| header `_TREE NOTE` | `note` on the artifact |
