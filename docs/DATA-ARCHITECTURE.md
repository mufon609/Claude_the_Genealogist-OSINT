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
                 was ingested), exports/ (GEDCOM 7 / Gramps XML snapshots, once
                 the exporters in `BACKLOG.md` are built)
  data/          source registry CSV and other reference tables
  schema/        DDL, seeds, manifest JSON Schema
  tools/         CLI tools and shared modules (`README.md` lists them; `schema/README.md`
                 says what each does)
  docs/          this file and its siblings
  app/person/    the person screen: stdlib server + one page, and read_record.md (what a reader of a record image writes)
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
  none is defined today. An import sets no home person: the ingest says so and
  names `tools/tree.py home`, and the queue and the runner refuse until it is set.
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

- A GEDCOM 7 export of layer 4 with a GEDZIP of redistributable media, the
  portable backup and the format any other tool can read, is deferred work in
  `BACKLOG.md` with the Gramps XML exporter (decision 1): no exporter is built.
- Catalog dumped to plain SQL and kept in a bag beside the archive bags
  (`tools/backup.py bag`), never in git: a dump holds living-person data.
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
4. **FamilySearch: the owner's browser, never its API.** Its record and search
   pages are saved one at a time by the page-saves-itself method and every
   decision on them is automated from the saved page
   (`docs/RESEARCH-WORKFLOW.md` §4, §5–7).
5. **The Genealogical Proof Standard, in code.** Conclusions meet the GPS and
   the standing rule's linkage rests on the same analysis: source,
   information and evidence classified in words from a data table, a proof
   summary per key fact written by code, and every conflict kept, cited,
   pointed out and decided with a written reason: by the rule when the
   classes favour one side without doubt, by the owner otherwise
   (`docs/RESEARCH-WORKFLOW.md` §5–7, "The proof standard"). No class becomes
   a number.
6. **Tokens are a cost the design answers to.** A session pays for every byte
   a tool prints and every browser round trip: a tool prints what the next
   action needs and the whole on request, the browser saves pages with a
   script that verifies itself, and the files every session loads hold the
   rules, not the catalogue.
7. **Any family, not this one.** The tool serves whatever tree is imported:
   no code names a family's people, places or denominations. What records
   exist where and who holds them is reference data (`data/jurisdictions.csv`,
   `data/countries.csv`, `data/data-sources.csv`, `data/holders.csv`,
   `data/evidence-classes.csv`),
   grown as a family's places need it; a place the data does not know yet gets
   its rows with no source, saying what is missing, never another family's
   holders. Settings that belong to one tree (its home person, its living
   overrides) live with that tree. The harness runs on the owner's own
   export by the owner's ruling (no invented people or records), and the
   walker names nobody, so another family's export and pages can stand in.
8. **Test data is real; only a holder's silence is simulated.** The owner's
   ruling, no invented people or records, reads at its own width: every page,
   response body, row and record the harness reads is a real one, archived or
   captured from the holder with its URL and the date it was fetched. A
   holder's failure to answer (a timeout, a refusal, a challenge) carries no
   record of anyone and may be simulated, named as the harness's stand-in.
9. **Contested evidence classes read toward the owner.** Where genealogists
   differ on how a record kind's field is classed, `data/evidence-classes.csv`
   reads the class that leaves the decision to a person: secondary rather than
   primary, indeterminable rather than primary, computed rather than stated. A
   class matters only where the rule would decide a conflict on it, so the
   cautious reading never lets the rule decide what a genealogist could
   contest. A reading of an image, by the model or a person, has the source
   class of what the image shows: an image of an index or an abstract is
   derivative, the image of the record made at the event original.
10. **A saved page names the steps it was saved for.** The page-saving script,
   run from the fetch list, writes the list entry's own key beside its
   saved-from line; collecting the page reaches those steps first, and the
   inference from the page's own identity stays for a file dropped into the
   inbox by hand. The owner's hand does not change: the same script, the same
   save.
11. **A year-filed index is asked with the year of the person's accepted
   event.** When a citation gives no year, the connector for an index filed
   by year looks in the year of the person's accepted event of that type. The
   year narrows where to look and decides nothing: a row found there is
   matched and judged by the rule like any other.
12. **Is this the right person: identity is tested, not assumed.** Before the
   rule takes a record, no other person of the tree fits the persona as well
   (compared across the whole tree, spelling variants included), the person
   holds no other persona on that reading, and nothing the record would add
   falls outside the person's life as accepted. Every plan regeneration tests
   each person's accepted links and statements against the limits of one
   life: a statement dated after the death or before the birth, a parent too
   young or too old at a child's birth, a child born after the mother's death
   or more than ten months after the father's, one person in two places in
   one census. The limits are data. A hit is a question about the person that
   names both records, for the owner; nothing is changed silently.
13. **A session writes the catalog only through a tool.** A correction no
   tool makes becomes a tool command first, so every write carries the tool's
   checks, its `--by` and its audit row; no session edits catalog rows by hand
   or by ad hoc SQL.

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

A place written at another granularity is the same place, not a conflict
(`catalog.place_verdict`): an abbreviated word is the word (Mt. is Mount,
St. is Saint, Ft. is Fort), and two US places that differ only in the unit's own word
(Township, Town, Village of, Borough, City, Ward N) or in a county one side
leaves out agree when the rest of the name and the state agree, so
"Northampton" and "Northampton Ward 1", "Hempstead" and "Hempstead Town",
"Lindenhurst" and "Village of Lindenhurst", "Mt. Holly" and "Mount Holly
Township" raise no conflict question. A name that differs in a letter or a
word ("North Hampton" and "Northampton", "Norriton" and "Norristown") still
differs: whether it is a variant is the owner's question. This governs
comparing only; resolving a string to a place keeps its own rule, under
which a village nested in its same-named town stays undecided.

### Resolving a place string

`tools/resolve_places.py` reads a raw string into its parts and asks OpenStreetMap's Nominatim, cached under
`derivatives/geocode/` and asked at one request a second. The last part of a string that is no country is the state when
it is a state's name or an abbreviation of it, from the one table in `catalog.py` that `place_verdict` reads too (the fifty
states and the District of Columbia, with the postal codes and the period abbreviations records write: NJ, N.J., Penna,
Mass., Tenn.), so a string that is a state alone ("NJ", "Penna") is asked as the state; earlier in a string an abbreviation
is left as written (Penn, in Penn, Cumberland, Pennsylvania, is a township). A part verifies against a candidate when it is
the name, in full, of the candidate or of a unit in its hierarchy, or one of the old or alternative names OpenStreetMap
records for them: the same name once case, accents, punctuation and spacing are set aside, an abbreviated word is written out
(Mt. is Mount, St. is Saint, Ft. is Fort, Twp is Township) and the unit's own word is dropped from either side (Township,
Town, Village of, Borough, City, County, Ward N), so "Mt. Holly" is Mount Holly Township and "Hempstead Town" the Town of
Hempstead (`catalog.place_name_key`, which `place_verdict` shares its words with). A part that is only the start of a name
("Cadillac Memorial Gardens West" for a cemetery named "Cadillac Memorial Gardens West Cemetery"), a truncation ("Hemp." for
Hempstead) or a spelling close to one ("Worchester" for Worcester, "North Hampton" for Northampton) verifies nothing: the
candidate is still offered on the card, that part marked near in its checks. A string is accepted when exactly one candidate
verifies on every part the string gives, or when the verified candidates are one territory under two names (a city and the
county coterminous with it, tested on the geocoder's boxes); a place nested in a larger unit of the same name stays
undecided with both offered. The words a record writes for the place of another of its lines ("Same House", "Same
Place", "Same County", listed in `data/place-overrides.json`) are rejected as no place, the reason in the string's notes.

What is not accepted is a `place_resolution` card on the fact row of the person it concerns. Cards that offer the same set
of places, the same of them verified on every part of their strings, are one question put in different spellings
("Worcester, Montgomery County, Pennsylvania, USA" and "Worcester, Montgomery, Pennsylvania, United States"): the screen shows
them as one card naming every spelling it covers, and the owner's answer (`conclude.decide_place`) is every string's, each
with its own audit row; `conclude.py decide --alone` answers one string only. A geocoder that does not answer leaves its
strings as they were, with no card, and the run says how many.

A turn (`tools/turn.py`) runs the resolver in its tail, after the records are collected and attached and before the rule
goes over the conflicts, on the strings no resolver has read that the records the turn brought carry or that lie behind
the person's own events: a new record's places are resolved or carded in the turn that brought it, and an event whose
strings are all resolved takes its place before the rule compares it. A geocoder that did not answer is named once in the
turn's report.

### Gazetteers for the places the geocoder does not know

`tools/resolve_places.py` asks OpenStreetMap's Nominatim first. When it
leaves a string open (no unique full match, a bare name, or a review the
overrides force), a gazetteer that knows the string's places is asked next:

| Strings naming | Gazetteer | Asked | Licence |
|---|---|---|---|
| Germany, Poland, Silesia | GOV, genealogy.net's historical gazetteer (SOAP, no key) | `searchByName` under the string's own name and under the current name of every geocoder candidate that keeps the string's name as its own (Dłużec, whose old name OpenStreetMap records as Langneundorf); `searchRelatedByName` for each other part | CC BY-SA |
| Ireland | Wikidata, its own API | `wbsearchentities` under the string's name; `wbgetentities` for the candidates; their containing units followed up P131 (`wbgetclaims`) to the country (P17) | CC0 |

A gazetteer candidate is checked as a geocoder candidate is: every part the
string gives (a Kreis, a town, a county, a land, the region, the country)
must be a unit the candidate lies within, in any period of its history, so
"Freiberg" verifies the Berthelsdorf that lay in the Amtshauptmannschaft
Freiberg and no other. GOV offers only its populated places; its parishes,
churches, registry offices and administrative units of the same name are
the settlement's offices and containers. The acceptance rule is the same
one: the string is accepted only when exactly one gazetteer candidate
verifies on every part, the string gives more than its name, and the
candidate has exactly one geocoder twin, the same place by an identifier
both keep (Wikidata's item id; GOV's id through Wikidata's P2503 or the
Polish SIMC register), with no other geocoder candidate verifying fully. The
twin places it in today's hierarchy; the gazetteer's id goes onto the place
(`gov_id`, `wikidata_id`) and GOV's names of it become `place_name` rows
with their language and dates (Lang Neundorf until 1945, Dłużec from 1945).
Anything else is the card: every gazetteer candidate offered with its
checks, on its twin's entry where it has one, after the geocoder's own. A
twin the owner chooses there carries the gazetteer's answer onto the place
on the next run; a gazetteer's own candidate the owner chooses (a place the
geocoder does not know) becomes a place of its own name and position under
the string's country, with the gazetteer's id and dated names. Every answer is cached under `derivatives/geocode/` at one
request a second, as Nominatim's are.

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
