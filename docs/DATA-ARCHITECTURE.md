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

- Layer 4 may not contain an assertion without a link to layer 3, or to the
  artifact itself when the claim is a family link or family event that a tree
  file states on the family rather than on a persona.
- Layer 3 may not contain a fact without a link to a layer 2 hash and a region
  (page, frame, line, bounding box) inside it.
- Layer 2 is never edited. A correction is a new object plus a note.
- AI output enters layer 3 as an *extraction* and layer 4 as a *proposal*. A
  human accepts a proposal to make it a conclusion, or the human's standing
  rule does so on their behalf when the record agrees with what they already
  accepted, recorded as the rule. Both carry the model name, version, and
  prompt hash.

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
a person saying so, and what a person says yes to is a document: a record
accepted as theirs brings every fact it states, a value that differs from the
tree's becomes a conflict question, and a standing rule may say yes for them
to a record that agrees with facts they already accepted, recorded as acting
on their word and reversible, and taken back by the rule itself when it would
no longer make it (`docs/RESEARCH-WORKFLOW.md` §5–7). A person may accept a fact on their own knowledge: the
acceptance is recorded as their own Accepted assertion on the tree file's
persona (the archived claim), marked vouched, and the fact's citations stay
Undecided until their records are fetched. One link is definitional rather than decided: the persona an
import creates for each tree entry is linked to the person it creates with
status Accepted, because that persona *is* the entry. The extractor is recorded
as the decider, and the link alone never counts as support
(`v_unsupported_person`).

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
  "schema_version": "0.1.0",
  "sha256": "…", "bytes": 1834021, "mime": "image/jpeg",
  "source_id": "D01",                      // key into the source registry (the CSV)
  "collection": "1940 United States Federal Census",
  "locator": {"kind": "apid", "value": "1,2442::12345678"},   // or ark:/61903/…, memorial id, NARA NAID; other identities go to artifact_locator
  "retrieved_at": "2026-09-05T18:02:11Z",
  "retrieved_by": "user:neural",           // or agent:fetcher@0.3
  "http": {"status": 200, "etag": "…", "last_modified": "…"},
  "rights": {"terms": "ancestry-tos", "redistributable": false, "cost": "paid"},
  "trust_tier": "T1",
  "original_filename": "…", "pages": 1,
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
4. Web pages that cannot be fetched programmatically (Find a Grave): one
   page at a time in the owner's own browser, the page saving its own markup
   as a file that goes to `inbox/` (`docs/RESEARCH-WORKFLOW.md` §4), with the
   citation's locator and the memorial URL in the manifest.
5. Family-held material: scans at 400–600 dpi TIFF as master, JPEG derivative.

### Integrity and backup

- Hash on ingest; a scrub over a random sample often, the whole archive
  monthly (`tools/backup.py verify`, the result on `artifact_copy`).
- 3-2-1: local disk, external drive (BagIt bags written by
  `tools/backup.py bag`, checked on the drive by `check`), S3 with Object Lock
  (see §7; disabled until the project is finished). Derivatives are excluded
  from off-site backup; they regenerate.
- Deletion is a tombstone row in the catalog. Bytes go to a quarantined bag,
  not to /dev/null, unless a takedown requires otherwise.

## 3. Catalog (the database)

Implemented: see `schema/README.md`, `schema/catalog.sql`, `tools/initdb.py`, and `tools/ingest_gedcom.py`.

One catalog holds layers 1, 3, and 4 and indexes layer 2. Start on SQLite.
Write the schema without SQLite-only features so a move to Postgres is a dump
and restore, not a rewrite. A single-family tree will not outgrow SQLite for
years; a multi-user site will, and the schema should not care which it is on.

Core tables (the full map by layer is in `schema/README.md`):

| Table | Purpose |
|---|---|
| `source`, `collection` | Registry seeded from `data/data-sources.csv`; a collection is a named record set inside a source and holds the vendor id (Ancestry dbid). |
| `artifact`, `artifact_page`, `tombstone` | One row per archived hash, mirroring the manifest; pages inside it; withdrawn artifacts and why. |
| `extraction`, `persona`, `persona_fact` | One run of one extractor over an artifact; what one record says about one individual; the claims on that persona with region coordinates. |
| `tree`, `tree_import` | A workspace of conclusions; which artifact was imported into which tree. |
| `person`, `person_name`, `family`, `family_member`, `event`, `event_participant` | Layer-4 conclusions. |
| `assertion` | The evidence link from a conclusion to a persona fact, persona or artifact, with the three-state status. |
| `person_persona` | Person-to-persona link with the three-state status and who decided it. |
| `proposal` | AI output awaiting a decision; answers a question about a person. |
| `alias` | Variant and erroneous forms kept as search keys (§8). |
| `research_question`, `search_plan`, `search_log` | A fact-level question about a person; an executable step on a checklist row of a person (a fetch with its locator, or a typed search with per-field basis); every run of a step including negatives (`docs/RESEARCH-WORKFLOW.md`). |
| `external_id` | Any vendor ID for any entity (APID, FamilySearch ARK, WikiTree ID, Find a Grave memorial). Never the primary key. |
| `place`, `place_name`, `place_string` | Normalized place hierarchy with dated names; every raw string ever seen and what it resolved to. |

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
  catalog/       tree.db + .active-tree             (git-ignored; dumped to SQL into a bag)
  derivatives/   thumbnails, OCR text, tiles        (regenerable, not backed up)
  trees/<slug>/  one folder per tree: README.md, imports/ (named copies of what
                 was ingested), exports/ (GEDCOM 7 / Gramps XML snapshots)
  data/          source registry CSV and other reference tables
  schema/        DDL, seeds, manifest JSON Schema
  tools/         CLI tools and shared modules (`README.md` lists them; `schema/README.md`
                 says what each does)
  docs/          this file and its siblings
  app/person/    the person screen: stdlib server + one page
```

The archive is the permanent home of every file's bytes. `trees/<slug>/imports/`
holds a second, human-named copy so a person can find "the GEDCOM I exported on
5 September" without querying the catalog.

## 4a. Trees (profiles)

A **tree** is a workspace of conclusions. The catalog holds any number of them.

- Layers 1-3 (reference, archive, evidence) are shared by all trees. A census
  page archived once can support a person in your tree and in a cousin's tree.
  Personas are tree-independent in the schema, so cross-tree matching is
  possible as an explicit, opt-in operation; it never happens on its own (see
  trust boundaries below).
- Layer 4 rows (`person`, `family`, `event`, `assertion`, `proposal`, tree-level
  `note`) carry `tree_id`. `tree_import` records which artifact went into which
  tree and where the named copy was filed.
- Switching: `tools/tree.py use <slug>` writes `catalog/.active-tree`; any tool
  accepts `--tree <slug>` and honours `$TREE`; the screen takes `?tree=<slug>`.
- The home person, the one the overview lays the tree out from and the
  living default counts tiers from (§7 decision 3), lives in
  `tree.home_person_id`; `tree.settings_json` is for per-tree settings, and
  none is defined today.
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
  resolution and overwrite, and a `rejected` string (with its reason) is
  visible to every tree. If this ever proves too leaky, `place_string` gains a
  `tree_id` and becomes per-tree; the schema change is one column.
- **Starting fresh** = `tools/tree.py create <slug>`, then import. Nothing from
  any other tree is linked, proposed, or asserted into it.

## 5. Growth plan

| Scale | Objects | What changes |
|---|---|---|
| One family | 10^3 – 10^4 | Everything above, on one machine. |
| Many families, one site | 10^5 – 10^6 | Catalog to Postgres; objects to S3-compatible store with the same hash paths; search to Meilisearch. Schema unchanged. |
| Shared/public | 10^6+ | Per-user ACLs on `artifact.rights` and the living-person redaction; dedup already handled by hashing; CDN for derivatives. |

The only thing that must be right on day one is the schema discipline and the
manifest. Storage engines are swappable if paths are hashes and IDs are ULIDs.

## 6. Snapshots and interchange

- Weekly GEDCOM 7 export of layer 4 with a GEDZIP of redistributable media.
  This is the portable backup and the format any other tool can read.
- Catalog dumped to plain SQL on the same schedule and kept in a bag beside the
  archive bags, never in git: a dump holds living-person data.
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
   code, docs and the CSV registry; never the objects, never a catalog dump.
3. **Living-person policy: a release threshold and a tier rule.**
   `record_release` follows each source's own law (census 72 years under
   Pub. L. 95-416 / 44 U.S.C. 2108(b); PA deaths 50 years and births 105
   years under Act 110 of 2011); stored per row in the source registry and
   configurable there. `presumed_living` is decided by tier. A person's tier
   is their generation relative to the tree's home person, counted along the
   family links the tree holds, accepted or claimed (a `family_member` row
   whose assertion is not rejected): a parent is one generation up, a child
   one down, a partner shares the tier, and a person reached by more than one
   path takes the nearest. The home person's generation and their parents'
   (tiers 0 and 1) are living. The grandparents' generation (tier 2) is
   unknown until the owner confirms the person (`tools/conclude.py living`),
   and while unknown is treated as living wherever the default is read. Tier
   3 and beyond, and a person no chain of links reaches from the home person,
   are deceased. Death evidence the tree holds
   (`v_person_vitals.has_death_evidence`) makes a person deceased at any
   tier; `person.living_override`, `living` or `deceased`, stands above
   everything. The same structure holds for every tree; there is no per-tree
   threshold. A living person is redacted in every export and derivative and
   retained in the archive under ACL. The one thing the default decides today
   is the search mode: a search step on a living or unknown person is
   assisted, never auto.

## 8. Wrong source data, variants and aliases

Principle: **correct the profile, never the document, and index the error.**

Three things exist for every value, and they live in different layers:

| What | Where | Mutable? | Example |
|---|---|---|---|
| As written in a record | `persona_fact.value_text`, `place_string.raw` (layer 3) | never | "Worchester, Montgomery, Pennsylvania" |
| Canonical conclusion | `person_name`, `event.place_id` → `place` (layer 4) | yes, with assertions | Worcester Township, Montgomery Co., PA |
| The mapping and why they differ | `alias` / `place_string.variant_kind` | yes, reviewable | kind = typo, Accepted |

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
`nickname` · `married_name` · `detail` (a fuller form of the same name) ·
`unclassified` (not yet sorted).

`historical`, `jurisdiction_change` and `translation` are legitimate names and
belong in `place_name` with dates. Everything else is an error or variant and
is attached to the canonical entity as an alias, never promoted to a name.

A place's dated names are proposed the way a place itself is: the resolver
reads them off the gazetteer's own merger and rename records, and the owner
accepts one once on a fact row, the same click that accepts a place now.
Matching reads `place_name` too, so a record's place agrees with the tree's
when both resolve to one place or one is a dated name of the other.

### Schema

```
alias (tree-scoped for persons/families; tree_id NULL for shared entities)
  id, tree_id, entity_kind, entity_id, value, kind, status, source_persona_fact_id,
  source_artifact_sha256, added_by, added_at, notes
  status: undecided | accepted | rejected
place_string.variant_kind   -- same vocabulary; set by tools/backfill_aliases.py
v_person_search_key         -- canonical names + non-rejected aliases, for search expansion
```

`tools/backfill_aliases.py` creates `undecided` aliases from the as-written names on
accepted personas, classifies resolved place strings, and writes a note on the
person when a canonical name itself contains a code (e.g. suffix "CFT19"); it never
edits the canonical value.

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
- **Matching:** two personas sharing a rare alias (the same misspelling) are
  evidence for the same person; the matcher treats recurring errors as
  fingerprints when it proposes a match.
- **Conflicts are not aliases.** A different birth date is a competing
  assertion, kept with its own three-state status and shown as disputed; it is never
  merged into an alias list.

An accepted variant of a name — a transposition, an indexer's slip, a married
name — is not written as a competing name: it is an alias of its own kind,
carrying the record's words exactly as written. The card that decides it is
the record's words, then the canonical value, then the kind and the reason
(`docs/RESEARCH-CHECKLIST.md` §6b); deciding it never edits the record.
