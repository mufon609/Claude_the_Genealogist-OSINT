# Data Architecture — below the UI

Goal: every fact in the tree can be traced to a locally held copy of the record
it came from, and the system still works when it holds a million artifacts.

## 1. Four layers, strictly separated

```
┌─────────────────────────────────────────────────────────────┐
│ 4. CONCLUSIONS   persons, families, events, proof arguments  │  mutable, versioned
├─────────────────────────────────────────────────────────────┤
│ 3. EVIDENCE      personas + facts extracted from one artifact│  append-only, versioned per extractor
├─────────────────────────────────────────────────────────────┤
│ 2. ARCHIVE       immutable bytes + provenance manifest       │  write-once, content-addressed
├─────────────────────────────────────────────────────────────┤
│ 1. REFERENCE     gazetteers, name tables, cM tables, source  │  snapshot-versioned
│                  registry (from data-sources.csv)            │
└─────────────────────────────────────────────────────────────┘
```

Rules that keep the layers honest:

- Layer 4 may not contain an assertion without a link to layer 3.
- Layer 3 may not contain a fact without a link to a layer 2 hash and a region
  (page, frame, line, bounding box) inside it.
- Layer 2 is never edited. A correction is a new object plus a note.
- AI output enters layer 3 as an *extraction* and layer 4 as a *proposal*. A
  human accepts a proposal to make it a conclusion. Both carry the model name,
  version, and prompt hash.

This is the GEDCOM X persona/person split and the Genealogical Proof Standard
made mechanical. It is also what lets the AI layer be re-run: a better HTR model
next year produces a new extraction version; nothing above or below it changes
until someone accepts the new reading.

## 1a. Decision model

Wherever a human decides, there are exactly three states and no score:

| State | Meaning |
|---|---|
| **Accepted** | stands; feeds searches, exports and the profile |
| **Rejected** | does not stand; kept with its reason, never deleted |
| **Undecided** | research in progress or needed; the default for anything imported or machine-produced |

This applies to assertions (citations), persona-to-person links, place-string
resolutions, aliases and proposals. There is no numeric confidence anywhere a
person decides. Machine detail (a geocoder's match score, an OCR engine's
certainty) may live inside notes/JSON for debugging and is never shown as an
accuracy figure. Trust tiers (T1-T5) remain: they classify what *kind* of
source a record is, not how confident anyone is in it.

An imported tree arrives entirely Undecided. Nothing becomes Accepted without
a person saying so.

## 2. Archive layer

### Storage: content-addressed, filesystem first

```
archive/
  objects/sha256/ab/cd/abcdef…            # the bytes, exactly as retrieved
  manifests/sha256/ab/cd/abcdef….json     # provenance sidecar
  bags/                                   # BagIt packages for backup/transfer
```

- SHA-256 of the bytes is the identity. Same census page fetched twice stores
  once. A page cited by twelve people stores once and is linked twelve times.
- Two-level hash prefix keeps any directory under a few thousand entries at
  10^6 objects.
- Human-readable organization (by source, collection, person, place) is a
  *view* served from the catalog, never encoded in the path. Paths that carry
  meaning break the first time someone renames a category.
- Package for transfer and off-site backup with BagIt (Library of Congress
  spec): a manifest of hashes plus the payload. Fixity checks are built in.

### Provenance manifest (one JSON per object)

```json
{
  "sha256": "…", "bytes": 1834021, "mime": "image/jpeg",
  "source_id": "D01",                      // key into the source registry (the CSV)
  "collection": "1940 United States Federal Census",
  "locator": {"kind": "apid", "value": "1,2442::12345678"},   // or ark:/61903/…, memorial id, NARA NAID
  "locator_alt": [{"kind": "url", "value": "https://…"}],
  "retrieved_at": "2026-09-05T18:02:11Z",
  "retrieved_by": "user:neural",           // or agent:fetcher@0.3
  "http": {"status": 200, "etag": "…", "last_modified": "…"},
  "rights": {"terms": "ancestry-tos", "redistributable": false, "cost": "paid"},
  "trust_tier": "T1",
  "original_filename": "…", "pages": 1, "page_of_parent": null,
  "derived_from": null,                    // parent sha256 for crops/rotations
  "notes": ""
}
```

`redistributable: false` is what stops a GEDZIP export or a shared page from
leaking a paid Ancestry image. `locator` is what lets a citation survive
outside the vendor.

### What to archive, in priority order

1. Record images (T1) whenever the vendor allows download. Keep the original
   bytes even if the format is poor; derive better views separately.
2. The vendor's index transcription for that record (T2) as a JSON snapshot,
   because the vendor's index is itself evidence of what they read.
3. API responses (WikiTree, loc.gov, Open Archives) as raw JSON with the request
   URL and time. Cheap, and it makes every AI step reproducible.
4. Web pages that cannot be fetched programmatically (Find a Grave): a
   user-initiated save, stored as a single-file HTML plus a PDF print, with the
   memorial ID as locator.
5. Family-held material: scans at 400–600 dpi TIFF as master, JPEG derivative.

### Integrity and backup

- Hash on ingest; nightly scrub over a random sample, full scrub monthly.
- 3-2-1: local disk, external drive (BagIt bags), cloud object storage with
  object lock (Backblaze B2 or S3). Derivatives are excluded from off-site
  backup; they regenerate.
- Deletion is a tombstone row in the catalog. Bytes go to a quarantined bag,
  not to /dev/null, unless a takedown requires otherwise.

## 3. Catalog (the database)

Implemented: see `schema/README.md`, `schema/catalog.sql`, `tools/initdb.py`, and `tools/ingest_gedcom.py`.

One catalog holds layers 1, 3, and 4 and indexes layer 2. Start on SQLite.
Write the schema without SQLite-only features so a move to Postgres is a dump
and restore, not a rewrite. A single-family tree will not outgrow SQLite for
years; a multi-user site will, and the schema should not care which it is on.

Core tables:

| Table | Purpose |
|---|---|
| `source` | Registry, seeded from `data/data-sources.csv`. Its `ID` column becomes the key. |
| `collection` | A named record set within a source (dbid 2442 = 1940 census). Holds the APID/dbid map. |
| `artifact` | One row per archived hash. Mirrors the manifest. |
| `artifact_page` | Page or frame inside a multi-page artifact. |
| `extraction` | One run of one extractor (human, OCR, HTR, LLM) over one artifact page. Versioned. |
| `persona` | What one record says about one individual. Belongs to an extraction. |
| `persona_fact` | Name, date, place, relationship claims on a persona, with region coordinates. |
| `person` | Layer-4 conclusion. |
| `person_persona` | Many-to-many link with a three-state status and who decided it. |
| `event`, `relationship` | Conclusions, each with `evidence_id` links. |
| `proposal` | AI or hint output awaiting review. |
| `external_id` | Any vendor ID for a person or artifact (APID, FamilySearch ARK, WikiTree ID, Find a Grave memorial). Never the primary key. |
| `place`, `place_name` | Normalized place with GeoNames/Wikidata ID and dated name variants. |
| `tombstone` | Deleted or withdrawn artifacts and why. |

Identifiers: ULIDs for everything internal. Sortable, unique across machines,
no coordination needed if the tree is later merged with a cousin's.

Full text: SQLite FTS5 over extraction text now; Meilisearch or OpenSearch when
the catalog leaves SQLite. Embeddings for AI retrieval live beside the
extraction they came from and are regenerable; they are not archived.

## 4. Repository layout

```
tree/
  inbox/         drop zone: put a file here, run an ingest tool, it is moved out
  archive/       layer 2: objects/ manifests/ bags/  (git-ignored; backed up by bag)
  catalog/       tree.db + .active-tree             (git-ignored; dumped to SQL for versioning)
  derivatives/   thumbnails, OCR text, tiles        (regenerable, not backed up)
  trees/<slug>/  one folder per tree: README.md, imports/ (named copies of what
                 was ingested), exports/ (GEDCOM 7 / Gramps XML snapshots)
  data/          source registry CSV and other reference tables
  schema/        DDL, seeds, manifest JSON Schema
  tools/         CLI tools (initdb, tree, ingest_gedcom)
  docs/          this file and its siblings
  app/           code, when it exists
```

The archive is the permanent home of every file's bytes. `trees/<slug>/imports/`
holds a second, human-named copy so a person can find "the GEDCOM I exported on
5 September" without querying the catalog.

## 4a. Trees (profiles)

A **tree** is a workspace of conclusions. The catalog holds any number of them.

- Layers 1-3 (reference, archive, evidence) are shared by all trees. A census
  page archived once can support a person in your tree and in a cousin's tree,
  and cross-tree matching stays possible because personas are tree-independent.
- Layer 4 rows (`person`, `family`, `event`, `assertion`, `proposal`, tree-level
  `note`) carry `tree_id`. `tree_import` records which artifact went into which
  tree and where the named copy was filed.
- Switching: `tools/tree.py use <slug>` writes `catalog/.active-tree`; any tool
  accepts `--tree <slug>` and honours `$TREE`. The app will do the same with a
  session setting.
- Per-tree settings (living-person threshold, home person) live in
  `tree.settings_json` and `tree.home_person_id`.
- Access control per tree is a later addition: a `tree_member` table keyed on
  `tree_id` is all the schema needs.

### Trust boundaries between trees

A fresh tree must be able to distrust everything an earlier tree concluded.
So:

| Shared across trees | Never shared |
|---|---|
| `artifact` bytes and manifests (facts about files) | `person`, `family`, `event` |
| `collection` names and vendor ids | `assertion`, `person_persona` (every act of trust) |
| `place_string` raw text | `proposal`, tree-level `note`, `external_id` for tree entities |
| `event_type`, `source` registry | `tree_import` |

- **Every import gets its own extraction and its own personas.** Importing the
  same file into a second tree does not reuse the first tree's extraction, even
  though the bytes are identical. The duplication is cheap; the coupling is not.
  Reuse of evidence across trees is never automatic. If it is ever wanted it is
  an explicit per-import flag, off by default.
- **Place resolution is the one shared item that carries judgment.** A
  `place_string` resolved to a `place` in one tree is resolved for all. Each
  resolution records who or what resolved it; a fresh tree can re-run
  resolution and overwrite, and `status='artifact'` / `'rejected'` are visible
  to every tree. If this ever proves too leaky, `place_string` gains a
  `tree_id` and becomes per-tree; the schema change is one column.
- **Starting fresh** = `tools/tree.py create <slug>`, then import. Nothing from
  any other tree is linked, proposed, or asserted into it.

## 5. Growth plan

| Scale | Objects | What changes |
|---|---|---|
| One family | 10^3 – 10^4 | Everything above, on one machine. |
| Many families, one site | 10^5 – 10^6 | Catalog to Postgres; objects to S3-compatible store with the same hash paths; search to Meilisearch. Schema unchanged. |
| Shared/public | 10^6+ | Per-user ACLs on `artifact.rights` and `person.living`; dedup already handled by hashing; CDN for derivatives. |

The only thing that must be right on day one is the schema discipline and the
manifest. Storage engines are swappable if paths are hashes and IDs are ULIDs.

## 6. Snapshots and interchange

- Weekly GEDCOM 7 export of layer 4 with a GEDZIP of redistributable media.
  This is the portable backup and the format any other tool can read.
- Catalog dumped to plain SQL on the same schedule and kept in git or a bag.
- Archive bags are the master; GEDZIP is a convenience view.

## 7. Decisions

1. **Layer-4 store: own schema.** Gramps is a neighbor, not a foundation. Borrow
   its taxonomy (event types, place hierarchy with dated names; not its 0-4
   citation confidence scale, see 1a). Ship a Gramps XML exporter alongside GEDCOM 7 so the tree
   opens in Gramps desktop at any time. Persona layer stays native; SQL and
   vector search stay direct; licensing stays open (no AGPL linkage).
2. **Off-site backup: S3.** Design for it from the start; upload nothing until
   the project is finished. Target: bag bucket with Versioning + Object Lock
   (compliance mode), lifecycle to Glacier Deep Archive after 30 days. The
   archive writer targets an S3-compatible interface behind a local-filesystem
   adapter, so switching on S3 later is configuration, not code. Git holds
   code, docs, the CSV registry, and catalog SQL dumps; never the objects.
3. **Living-person policy: two thresholds.** `record_release` follows each
   source's own law (census 72 years under Pub. L. 95-416 / 44 U.S.C. 2108(b);
   PA deaths 50 years and births 105 years under Act 110 of 2011); stored per
   row in the source registry. `presumed_living` = born within 100 years and no
   death evidence, manual override allowed, redacted in every export and
   derivative, retained in the archive under ACL. Both thresholds configurable.

## 8. Wrong source data, variants and aliases

Principle: **correct the profile, never the document, and index the error.**

Three things exist for every value, and they live in different layers:

| What | Where | Mutable? | Example |
|---|---|---|---|
| As written in a record | `persona_fact.value_text`, `place_string.raw` (layer 3) | never | "Worchester, Montgomery, Pennsylvania" |
| Canonical conclusion | `person_name`, `event.place_id` → `place` (layer 4) | yes, with assertions | Worcester Township, Montgomery Co., PA |
| The mapping and why they differ | `alias` / `place_string.variant_kind` (schema 0.4.0) | yes, reviewable | kind = typo, Accepted |

Why the error is kept and indexed rather than fixed:

- Indexers copy each other. A mis-transcribed name or a town filed under the
  wrong state in one Ancestry index usually appears the same way in FamilySearch
  and in later compiled trees. The wrong form is the key that finds the next
  record.
- The same error recurring across independent documents is itself evidence
  that they concern the same person. Erasing it erases a linkage signal.
- A "correction" is a conclusion, and conclusions must be reversible. The only
  reversible correction is one that leaves the original untouched.

### Alias kinds (classification, not a free-text note)

`typo` · `phonetic` (Ahearn/Ahern/Hearn) · `transcription` (indexer/OCR error) ·
`abbreviation` (Hemp.) · `translation` (Allemagne, Sachsen/Saxony) ·
`historical` (Harpersdorf → Twardocice) · `jurisdiction_change` (Norriton →
East/West Norriton 1909; Montgomery Co. formed 1784) · `jurisdiction_error`
(Amwell, Hunterdon, *Pennsylvania*) · `context_glue` (date fused into place) ·
`nickname` · `married_name`.

`historical`, `jurisdiction_change` and `translation` are legitimate names and
belong in `place_name` with dates. Everything else is an error or variant and
is attached to the canonical entity as an alias, never promoted to a name.

### Schema (0.4.0)

```
alias (tree-scoped for persons/families; tree_id NULL for shared entities)
  id, tree_id, entity_kind, entity_id, value, kind, status, source_persona_fact_id,
  source_artifact_sha256, added_by, added_at, notes
  status: undecided | accepted | rejected
place_string.variant_kind   -- same vocabulary; set by tools/backfill_aliases.py
v_person_search_key         -- canonical names + non-rejected aliases, for search expansion
```

`tools/backfill_aliases.py` creates `undecided` aliases from the as-written names on
accepted personas, classifies resolved place strings, and raises a `fact` proposal
when a canonical name itself contains a code (e.g. suffix "CFT19"); it never edits
the canonical value.

- `undecided` = appears in at least one record linked to this entity (created
  automatically when a persona is accepted onto a person).
- `accepted` = a human agreed this variant means this entity.
- `rejected` = a look-alike that has been checked and rejected; search stops
  proposing it. Rejection is recorded, not deleted.

### How the app uses aliases

- **Profile:** shows the canonical value, then "also recorded as" with each
  variant, its kind, and how many documents carry it. Click-through to the
  records.
- **Search / record hunting:** query expansion over canonical + all `undecided`
  and `accepted` aliases, including wrong-jurisdiction forms. The search agent
  must search "Worchester" and "Amwell, Hunterdon, Pennsylvania" as literally
  as the tree owner once typed them.
- **Matching:** two personas sharing a rare alias (same misspelling) get a
  linkage bonus; the AI matcher treats recurring errors as fingerprints.
- **Conflicts are not aliases.** A different birth date is a competing
  assertion, kept with its own three-state status and shown as disputed; it is never
  merged into an alias list.
