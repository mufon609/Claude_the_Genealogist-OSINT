-- =============================================================================
-- tree catalog schema  v0.7.3
-- Portable SQL: runs on SQLite 3.35+ and PostgreSQL 13+ without edits.
-- Conventions
--   * ids are ULIDs stored as 26-char TEXT; artifacts are keyed by sha256 hex.
--   * timestamps are ISO-8601 UTC TEXT ("2026-09-05T18:02:11Z").
--   * dates in records use the date_* column group (see persona_fact / event).
--   * JSON is stored as TEXT (json_* functions exist on both engines).
--   * booleans are BOOLEAN (SQLite stores 0/1).
--   * SQLite-only objects (FTS, triggers) live in sqlite_extras.sql.
--   * DECISIONS: wherever a human decides, the column is `status` with exactly
--     three values: 'undecided' | 'accepted' | 'rejected'. No numeric confidence.
--     Machine details (match scores, OCR certainty) stay inside notes/JSON.
-- Layers: 1 reference  2 archive  3 evidence  4 conclusions  + ops
-- =============================================================================

CREATE TABLE schema_migration (
  version     TEXT PRIMARY KEY,
  applied_at  TEXT NOT NULL,
  notes       TEXT
);

-- =============================================================================
-- LAYER 1 - REFERENCE
-- =============================================================================

-- Source registry. Seeded from data/data-sources.csv; `id` is the CSV ID (D01).
CREATE TABLE source (
  id                    TEXT PRIMARY KEY,
  category              TEXT NOT NULL,
  data_type             TEXT NOT NULL,
  name                  TEXT NOT NULL,
  provider              TEXT,
  cost                  TEXT,
  access                TEXT,
  url                   TEXT,
  coverage              TEXT,
  terms                 TEXT,
  trust_tier            TEXT,          -- T1..T5, ref, n/a
  priority              TEXT,          -- P0..P3
  status                TEXT,
  connector             TEXT,          -- name of the built connector that runs searches against this source; NULL = none, so never 'auto'
  record_release_rule   TEXT,          -- human-readable law/rule, e.g. "72y after census date"
  notes                 TEXT,
  updated_at            TEXT NOT NULL
);

-- A named record set inside a source (Ancestry dbid 2442 = 1940 census).
CREATE TABLE collection (
  id                    TEXT PRIMARY KEY,
  source_id             TEXT NOT NULL REFERENCES source(id),
  name                  TEXT NOT NULL,
  external_key_kind     TEXT,          -- ancestry_dbid | fs_collection | nara_naid | loc_collection | other
  external_key          TEXT,
  record_release_years  INTEGER,       -- machine-usable form of the release rule, if one applies
  date_start            TEXT,          -- ISO date or year
  date_end              TEXT,
  trust_tier            TEXT,
  notes                 TEXT,
  UNIQUE (external_key_kind, external_key)
);

-- Event / fact taxonomy. Borrowed from Gramps; gedcom_tag maps to GEDCOM 7.
CREATE TABLE event_type (
  name        TEXT PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('event','attribute','family_event')),
  gedcom_tag  TEXT,
  gramps_name TEXT
);

-- Normalized place with hierarchy.
CREATE TABLE place (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,           -- canonical modern name
  place_type    TEXT,                    -- country | state | county | city | town | township | parish | cemetery | address | region | unknown
  parent_id     TEXT REFERENCES place(id),
  latitude      REAL,
  longitude     REAL,
  geonames_id   INTEGER,
  wikidata_id   TEXT,                    -- Q-number
  gov_id        TEXT,                    -- gov.genealogy.net id
  notes         TEXT,
  updated_at    TEXT NOT NULL
);
CREATE INDEX ix_place_parent ON place(parent_id);
CREATE INDEX ix_place_name   ON place(name);

-- Dated name variants for a place (Harpersdorf 1700-1945, Twardocice 1945-).
CREATE TABLE place_name (
  id          TEXT PRIMARY KEY,
  place_id    TEXT NOT NULL REFERENCES place(id),
  name        TEXT NOT NULL,
  lang        TEXT,
  valid_from  TEXT,
  valid_to    TEXT,
  is_primary  BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX ix_place_name_place ON place_name(place_id);

-- Every raw place string ever seen, and what it resolved to. accepted = place_id
-- stands; rejected = not a real place (reason in notes); undecided = still open.
CREATE TABLE place_string (
  id          TEXT PRIMARY KEY,
  raw         TEXT NOT NULL UNIQUE,
  place_id    TEXT REFERENCES place(id),
  status      TEXT NOT NULL DEFAULT 'undecided' CHECK (status IN ('undecided','accepted','rejected')),
  resolver    TEXT,                      -- user:<name> | ai:<extractor>   (who last set place_id / status)
  resolved_at TEXT,
  variant_kind TEXT CHECK (variant_kind IN ('typo','phonetic','transcription','abbreviation','translation','historical',
                            'jurisdiction_change','jurisdiction_error','context_glue','detail','unclassified') OR variant_kind IS NULL),
  notes       TEXT
);

-- =============================================================================
-- LAYER 2 - ARCHIVE  (bytes live under archive/objects/sha256/aa/bb/<hash>)
-- =============================================================================

CREATE TABLE artifact (
  sha256              TEXT PRIMARY KEY CHECK (length(sha256) = 64),
  byte_size           INTEGER NOT NULL,
  mime                TEXT NOT NULL,
  source_id           TEXT REFERENCES source(id),
  collection_id       TEXT REFERENCES collection(id),
  locator_kind        TEXT,             -- apid | ark | naid | memorial_id | url | file | other
  locator_value       TEXT,
  retrieved_at        TEXT NOT NULL,
  retrieved_by        TEXT NOT NULL,    -- user:<name> | agent:<name>@<version>
  http_status         INTEGER,
  http_etag           TEXT,
  http_last_modified  TEXT,
  terms               TEXT,             -- public-domain | cc-by | ancestry-tos | familysearch-tos | ...
  redistributable     BOOLEAN NOT NULL DEFAULT FALSE,
  cost                TEXT CHECK (cost IN ('free','paid','member','unknown')),
  trust_tier          TEXT,
  original_filename   TEXT,
  page_count          INTEGER NOT NULL DEFAULT 1,
  derived_from        TEXT REFERENCES artifact(sha256),
  manifest_json       TEXT NOT NULL,    -- verbatim copy of the sidecar manifest
  created_at          TEXT NOT NULL,
  notes               TEXT
);
CREATE INDEX ix_artifact_source     ON artifact(source_id);
CREATE INDEX ix_artifact_collection ON artifact(collection_id);
CREATE INDEX ix_artifact_locator    ON artifact(locator_kind, locator_value);

-- Additional locators for the same bytes (a URL and an APID and a NARA id).
CREATE TABLE artifact_locator (
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
  kind            TEXT NOT NULL,
  value           TEXT NOT NULL,
  PRIMARY KEY (artifact_sha256, kind, value)
);
CREATE INDEX ix_artifact_locator_value ON artifact_locator(kind, value);

CREATE TABLE artifact_page (
  id              TEXT PRIMARY KEY,
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
  page_no         INTEGER NOT NULL,
  width_px        INTEGER,
  height_px       INTEGER,
  label           TEXT,                 -- "sheet 4B", "frame 217"
  UNIQUE (artifact_sha256, page_no)
);

-- Regenerable outputs (thumbnails, tiles, OCR text files). Not backed up.
CREATE TABLE derivative (
  id              TEXT PRIMARY KEY,
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
  page_id         TEXT REFERENCES artifact_page(id),
  kind            TEXT NOT NULL,        -- thumb | web | tiles | ocr_text | hocr
  path            TEXT NOT NULL,
  generator       TEXT,
  generated_at    TEXT NOT NULL
);
CREATE INDEX ix_derivative_artifact ON derivative(artifact_sha256);

-- Deletion is a record, not an absence.
CREATE TABLE tombstone (
  artifact_sha256 TEXT PRIMARY KEY REFERENCES artifact(sha256),
  reason          TEXT NOT NULL,
  disposition     TEXT NOT NULL CHECK (disposition IN ('quarantined','destroyed')),
  tombstoned_at   TEXT NOT NULL,
  tombstoned_by   TEXT NOT NULL
);

-- =============================================================================
-- LAYER 3 - EVIDENCE
-- =============================================================================

-- Who or what produced an extraction. Humans are extractors too.
CREATE TABLE extractor (
  id            TEXT PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('human','vendor_index','ocr','htr','llm','rule')),
  name          TEXT NOT NULL,
  version       TEXT,
  model_id      TEXT,                   -- e.g. claude-fable-5-1
  prompt_sha256 TEXT,                   -- hash of the prompt template used
  config_json   TEXT,
  created_at    TEXT NOT NULL,
  UNIQUE (kind, name, version, prompt_sha256)
);

-- One run of one extractor over one artifact (or page). Never updated in place;
-- a re-run inserts a new row and sets superseded_by on the old one.
CREATE TABLE extraction (
  id              TEXT PRIMARY KEY,
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
  page_id         TEXT REFERENCES artifact_page(id),
  extractor_id    TEXT NOT NULL REFERENCES extractor(id),
  ran_at          TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'complete'
                  CHECK (status IN ('complete','partial','failed')),
  full_text       TEXT,                 -- OCR/HTR/transcription output
  structured_json TEXT,                 -- raw structured output, if any
  superseded_by   TEXT REFERENCES extraction(id),
  notes           TEXT
);
CREATE INDEX ix_extraction_artifact ON extraction(artifact_sha256);

-- What ONE record says about ONE individual. Never merged, never edited.
CREATE TABLE persona (
  id              TEXT PRIMARY KEY,
  extraction_id   TEXT NOT NULL REFERENCES extraction(id),
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
  page_id         TEXT REFERENCES artifact_page(id),
  name_text       TEXT,                 -- exactly as written
  sex             TEXT CHECK (sex IN ('M','F','X','U') OR sex IS NULL),
  role_in_record  TEXT,                 -- head | wife | child | deceased | informant | bride | groom | witness | passenger | registrant | ...
  sequence        INTEGER,              -- order within the record (household line)
  region_json     TEXT,                 -- {"page":1,"bbox":[x,y,w,h]} or {"line":17}
  notes           TEXT
);
CREATE INDEX ix_persona_extraction ON persona(extraction_id);
CREATE INDEX ix_persona_artifact   ON persona(artifact_sha256);
CREATE INDEX ix_persona_name       ON persona(name_text);

-- A single claim on a persona. Dates keep the written form plus a sortable form.
CREATE TABLE persona_fact (
  id              TEXT PRIMARY KEY,
  persona_id      TEXT NOT NULL REFERENCES persona(id),
  fact_type       TEXT NOT NULL REFERENCES event_type(name),
  value_text      TEXT,                 -- as written: "farmer", "abt 34", "Norristown"
  date_text       TEXT,                 -- as written
  date_start      TEXT,                 -- ISO, may be partial: 1852 | 1852-03 | 1852-03-14
  date_end        TEXT,
  date_qualifier  TEXT CHECK (date_qualifier IN ('exact','about','before','after','between','calculated','estimated') OR date_qualifier IS NULL),
  calendar        TEXT NOT NULL DEFAULT 'gregorian' CHECK (calendar IN ('gregorian','julian','dual','unknown')),
  place_string_id TEXT REFERENCES place_string(id),
  region_json     TEXT,
  notes           TEXT
);
CREATE INDEX ix_persona_fact_persona ON persona_fact(persona_id);
CREATE INDEX ix_persona_fact_type    ON persona_fact(fact_type);

-- Relationship stated by the record itself, from the persona whose role it is to the
-- persona it is toward: (son, head, child, "Son"); (father, deceased, parent, "Father").
CREATE TABLE persona_relation (
  id                  TEXT PRIMARY KEY,
  persona_id          TEXT NOT NULL REFERENCES persona(id),
  related_persona_id  TEXT NOT NULL REFERENCES persona(id),
  kind                TEXT NOT NULL,    -- spouse | parent | child | sibling | head | boarder | witness | informant | employer | other
  value_text          TEXT,             -- as written: "Wife", "Son-in-law"
  region_json         TEXT
);
CREATE INDEX ix_persona_relation_persona ON persona_relation(persona_id);

-- =============================================================================
-- LAYER 4 - CONCLUSIONS  (scoped to a tree; layers 1-3 are shared by all trees)
-- =============================================================================

-- A tree is a workspace of conclusions: one family's research, one profile.
-- Artifacts, extractions and personas are NOT tree-scoped, so the same record
-- can support persons in several trees and cross-tree matching stays possible.
CREATE TABLE tree (
  id              TEXT PRIMARY KEY,
  slug            TEXT NOT NULL UNIQUE,   -- "ahearn"; used in paths and CLI
  name            TEXT NOT NULL,
  description     TEXT,
  home_person_id  TEXT,                   -- REFERENCES person(id), declared below
  settings_json   TEXT,                   -- per-tree settings as JSON; none is defined today (the living default is the tier rule, the same for every tree)
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

-- One import of one artifact into one tree.
CREATE TABLE tree_import (
  id              TEXT PRIMARY KEY,
  tree_id         TEXT NOT NULL REFERENCES tree(id),
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
  extraction_id   TEXT REFERENCES extraction(id),
  imported_at     TEXT NOT NULL,
  imported_by     TEXT NOT NULL,
  original_path   TEXT,                   -- where the named copy was filed (trees/<slug>/imports/...)
  summary_json    TEXT,
  UNIQUE (tree_id, artifact_sha256)
);

CREATE TABLE person (
  id              TEXT PRIMARY KEY,
  tree_id         TEXT NOT NULL REFERENCES tree(id),
  sex             TEXT CHECK (sex IN ('M','F','X','U') OR sex IS NULL),
  display_name    TEXT,                 -- cached from primary person_name
  living_override TEXT CHECK (living_override IN ('living','deceased') OR living_override IS NULL),
  private         BOOLEAN NOT NULL DEFAULT FALSE,
  merged_into     TEXT REFERENCES person(id),   -- set by tools/conclude.py merge; the row stays for the audit trail, out of every listing, overview, plan and matcher run
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  notes           TEXT
);
CREATE INDEX ix_person_merged_into ON person(merged_into) WHERE merged_into IS NOT NULL;

CREATE TABLE person_name (
  id          TEXT PRIMARY KEY,
  person_id   TEXT NOT NULL REFERENCES person(id),
  name_type   TEXT NOT NULL DEFAULT 'birth' CHECK (name_type IN ('birth','married','aka','religious','immigrant','anglicized','other')),
  prefix      TEXT,
  given       TEXT,
  surname     TEXT,
  surname_prefix TEXT,                  -- "van", "von"
  suffix      TEXT,
  nick        TEXT,
  is_primary  BOOLEAN NOT NULL DEFAULT FALSE,
  sort_key    TEXT                      -- "cassel, abraham b"
);
CREATE INDEX ix_person_tree ON person(tree_id);
CREATE INDEX ix_person_name_person  ON person_name(person_id);
CREATE INDEX ix_person_name_surname ON person_name(surname);

-- A couple/parent unit. Members carry roles; parent-child is derived.
CREATE TABLE family (
  id          TEXT PRIMARY KEY,
  tree_id     TEXT NOT NULL REFERENCES tree(id),
  rel_type    TEXT NOT NULL DEFAULT 'unknown' CHECK (rel_type IN ('married','unmarried','civil_union','unknown')),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  notes       TEXT
);

CREATE TABLE family_member (
  family_id   TEXT NOT NULL REFERENCES family(id),
  person_id   TEXT NOT NULL REFERENCES person(id),
  role        TEXT NOT NULL CHECK (role IN ('partner','child')),
  child_rel   TEXT CHECK (child_rel IN ('birth','adopted','step','foster','unknown') OR child_rel IS NULL),
  seq         INTEGER,
  PRIMARY KEY (family_id, person_id, role)
);
CREATE INDEX ix_family_tree ON family(tree_id);
CREATE INDEX ix_family_member_person ON family_member(person_id);

CREATE TABLE event (
  id              TEXT PRIMARY KEY,
  tree_id         TEXT NOT NULL REFERENCES tree(id),
  event_type      TEXT NOT NULL REFERENCES event_type(name),
  date_text       TEXT,
  date_start      TEXT,
  date_end        TEXT,
  date_qualifier  TEXT CHECK (date_qualifier IN ('exact','about','before','after','between','calculated','estimated') OR date_qualifier IS NULL),
  calendar        TEXT NOT NULL DEFAULT 'gregorian' CHECK (calendar IN ('gregorian','julian','dual','unknown')),
  place_id        TEXT REFERENCES place(id),
  description     TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX ix_event_tree  ON event(tree_id);
CREATE INDEX ix_event_type  ON event(event_type);
CREATE INDEX ix_event_place ON event(place_id);
CREATE INDEX ix_event_date  ON event(date_start);

CREATE TABLE event_participant (
  id          TEXT PRIMARY KEY,
  event_id    TEXT NOT NULL REFERENCES event(id),
  person_id   TEXT REFERENCES person(id),
  family_id   TEXT REFERENCES family(id),
  role        TEXT NOT NULL DEFAULT 'primary',   -- primary | spouse | child | witness | informant | officiant | other
  UNIQUE (event_id, role, person_id, family_id),
  CHECK ((person_id IS NULL) <> (family_id IS NULL))
);
CREATE INDEX ix_event_participant_person ON event_participant(person_id);
CREATE INDEX ix_event_participant_family ON event_participant(family_id);

-- Conclusion <-> persona link. The core of the persona/person split.
CREATE TABLE person_persona (
  person_id   TEXT NOT NULL REFERENCES person(id),
  persona_id  TEXT NOT NULL REFERENCES persona(id),
  status      TEXT NOT NULL DEFAULT 'undecided' CHECK (status IN ('undecided','accepted','rejected')),
  proposal_id TEXT,                     -- REFERENCES proposal(id), declared below
  decided_by  TEXT,
  decided_at  TEXT,
  PRIMARY KEY (person_id, persona_id)
);
CREATE INDEX ix_person_persona_persona ON person_persona(persona_id);

-- The evidence link for any conclusion. Imported citations start 'undecided';
-- a human review makes them 'accepted' or 'rejected'. Every layer-4 row should
-- end up with >= 1 accepted assertion (v_unsupported_* lists the rest).
CREATE TABLE assertion (
  id              TEXT PRIMARY KEY,
  tree_id         TEXT NOT NULL REFERENCES tree(id),
  subject_kind    TEXT NOT NULL CHECK (subject_kind IN ('person','person_name','event','event_participant','family','family_member','place')),
  subject_id      TEXT NOT NULL,        -- id of the subject row (composite keys: json-encoded)
  persona_fact_id TEXT REFERENCES persona_fact(id),
  persona_id      TEXT REFERENCES persona(id),
  artifact_sha256 TEXT REFERENCES artifact(sha256),
  citation_text   TEXT,                 -- Evidence Explained style rendered citation
  status          TEXT NOT NULL DEFAULT 'undecided' CHECK (status IN ('undecided','accepted','rejected')),
  asserted_by     TEXT NOT NULL,        -- user:<name> | ai:<extractor_id>
  asserted_at     TEXT NOT NULL,
  notes           TEXT,
  CHECK (persona_fact_id IS NOT NULL OR persona_id IS NOT NULL OR artifact_sha256 IS NOT NULL)
);
CREATE INDEX ix_assertion_tree     ON assertion(tree_id);
CREATE INDEX ix_assertion_subject  ON assertion(subject_kind, subject_id);
CREATE INDEX ix_assertion_artifact ON assertion(artifact_sha256);

-- AI output waiting for a decision; each proposal answers a question about a person.
CREATE TABLE proposal (
  id            TEXT PRIMARY KEY,
  tree_id       TEXT NOT NULL REFERENCES tree(id),
  kind          TEXT NOT NULL CHECK (kind IN ('persona_match','new_person','fact','relation','place_resolution','duplicate_person')),
  question_id   TEXT,                                   -- the research_question this proposal answers, when it answers one
  payload_json  TEXT NOT NULL,
  rationale     TEXT,
  generated_by  TEXT NOT NULL REFERENCES extractor(id),
  created_at    TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'undecided' CHECK (status IN ('undecided','accepted','rejected')),
  decided_by    TEXT,
  decided_at    TEXT,
  decision_note TEXT
);
CREATE INDEX ix_proposal_status ON proposal(tree_id, status, kind);

-- A fact-level question about a person, generated from gaps in the baseline (RESEARCH-WORKFLOW §2).
-- open until answered or dismissed; the decision that answers it is a proposal. A missing
-- checklist row is not a question: it is a unit of work, a search_plan row.
CREATE TABLE research_question (
  id                      TEXT PRIMARY KEY,
  tree_id                 TEXT NOT NULL REFERENCES tree(id),
  subject_person_id       TEXT NOT NULL REFERENCES person(id),
  kind                    TEXT NOT NULL CHECK (kind IN ('missing_parents','identity_incomplete','missing_spouse','missing_fact',
                                                        'unverified_claim','conflict','duplicate_person','unlinked_relative')),
  q_key                   TEXT NOT NULL,                -- stable key for idempotent regeneration: kind + detail
  detail_json             TEXT,
  status                  TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
  closed_reason           TEXT CHECK (closed_reason IN ('answered','dismissed','gap_gone') OR closed_reason IS NULL),
  answered_by_proposal_id TEXT,
  created_at              TEXT NOT NULL,
  closed_at               TEXT,
  UNIQUE (subject_person_id, q_key)
);
CREATE INDEX ix_question_person ON research_question(subject_person_id, status);

-- One executable step for a person: a fetch of a record the tree already cites, or a typed search
-- for a missing checklist row (RESEARCH-WORKFLOW §3). It belongs to the person and a checklist row;
-- it carries a question only when it answers a fact-level question (a footprint record for missing parents).
CREATE TABLE search_plan (
  id                TEXT PRIMARY KEY,
  person_id         TEXT NOT NULL REFERENCES person(id),
  row_key           TEXT NOT NULL,                      -- "<record>:<instance>" of the checklist row, or "footprint:<locator>" for a record on a relative
  question_id       TEXT REFERENCES research_question(id),
  seq               INTEGER NOT NULL,
  step_key          TEXT NOT NULL,                      -- stable key for idempotent regeneration
  kind              TEXT NOT NULL CHECK (kind IN ('fetch','search')),
  query_type        TEXT NOT NULL CHECK (query_type IN ('footprint_record','subject_record','household','couple','name','surname_locality','obituary','probate')),
  query_json        TEXT NOT NULL,                      -- search: {field: {"value": ..., "basis": accepted|claim|row|record|run}}; fetch: the citation's own details, basis citation
  locator_source_id TEXT REFERENCES source(id),         -- fetch: the registry row the record is fetched from: the free holder of the citation's collection (data/holders.csv), or B02 when none is known
  locator_kind      TEXT,                               -- apid | ark | naid | memorial_id | url: the citation's identity for the record
  locator_value     TEXT,
  collection_id     TEXT REFERENCES collection(id),
  on_json           TEXT,                               -- [[relative name, relation]] the citation sits on; [] when it is on the person
  sources_json      TEXT NOT NULL,                      -- registry ids for the record's kind
  mode              TEXT NOT NULL CHECK (mode IN ('fetch','blocked','auto','assisted','awaiting_approval')),   -- blocked: a cited record with no free holder
  expected          TEXT,
  status            TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','done','skipped')),
  rationale         TEXT,
  revisions_json    TEXT,                               -- {field: {"include": false} | {"value": "..."}}: the person's include/revise for this step
  created_at        TEXT NOT NULL,
  UNIQUE (person_id, step_key)
);
CREATE INDEX ix_search_plan_person   ON search_plan(person_id, seq);
CREATE INDEX ix_search_plan_question ON search_plan(question_id);
CREATE INDEX ix_search_plan_locator  ON search_plan(locator_kind, locator_value);

-- Every execution of a step, including the ones that found nothing.
CREATE TABLE search_log (
  id              TEXT PRIMARY KEY,
  tree_id         TEXT NOT NULL REFERENCES tree(id),
  plan_step_id    TEXT REFERENCES search_plan(id),
  question_id     TEXT REFERENCES research_question(id),
  executed_at     TEXT NOT NULL,
  executed_by     TEXT NOT NULL,                        -- user:<name> | agent:<name>
  source_id       TEXT REFERENCES source(id),
  query_json      TEXT NOT NULL,                        -- exactly the fields used, after include/revise
  outcome         TEXT NOT NULL CHECK (outcome IN ('found','none','blocked','error')),
  artifacts_json  TEXT,                                 -- sha256s archived by this run
  notes           TEXT
);
CREATE INDEX ix_search_log_step ON search_log(plan_step_id);
CREATE INDEX ix_search_log_question ON search_log(question_id);

-- Any vendor identifier for any entity. Never a primary key.
CREATE TABLE external_id (
  id          TEXT PRIMARY KEY,
  tree_id     TEXT REFERENCES tree(id), -- NULL for shared entities (artifact, collection, place, source)
  entity_kind TEXT NOT NULL CHECK (entity_kind IN ('person','family','event','place','artifact','collection','source')),
  entity_id   TEXT NOT NULL,
  system      TEXT NOT NULL,            -- ancestry_pid | ancestry_apid | ancestry_oid | familysearch_ark | wikitree | findagrave | geni | myheritage | gramps_handle | geonames | wikidata
  value       TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  UNIQUE (entity_kind, entity_id, system, value)
);
CREATE INDEX ix_external_id_entity ON external_id(entity_kind, entity_id);
CREATE INDEX ix_external_id_value  ON external_id(system, value);

-- Same vendor id on two entities of the same kind in one tree = probable duplicate.
CREATE VIEW v_external_id_collision AS
SELECT tree_id, entity_kind, system, value, COUNT(*) AS n
FROM external_id WHERE tree_id IS NOT NULL
GROUP BY tree_id, entity_kind, system, value HAVING COUNT(*) > 1;

-- Variant forms of an entity's name as they appear in records. Errors are kept and
-- classified, never corrected away: they are search keys and linkage signals.
CREATE TABLE alias (
  id                      TEXT PRIMARY KEY,
  tree_id                 TEXT REFERENCES tree(id),      -- NULL for shared entities
  entity_kind             TEXT NOT NULL CHECK (entity_kind IN ('person','family','place')),
  entity_id               TEXT NOT NULL,
  value                   TEXT NOT NULL,                 -- exactly as it appears somewhere
  kind                    TEXT NOT NULL CHECK (kind IN ('typo','phonetic','transcription','abbreviation','translation',
                                                        'historical','jurisdiction_change','jurisdiction_error','context_glue',
                                                        'nickname','married_name','detail','unclassified')),
  status                  TEXT NOT NULL DEFAULT 'undecided' CHECK (status IN ('undecided','accepted','rejected')),
  source_persona_fact_id  TEXT REFERENCES persona_fact(id),
  source_artifact_sha256  TEXT REFERENCES artifact(sha256),
  added_by                TEXT NOT NULL,
  added_at                TEXT NOT NULL,
  notes                   TEXT,
  UNIQUE (entity_kind, entity_id, value)
);
CREATE INDEX ix_alias_entity ON alias(entity_kind, entity_id);
CREATE INDEX ix_alias_value  ON alias(tree_id, value);

CREATE TABLE note (
  id          TEXT PRIMARY KEY,
  tree_id     TEXT REFERENCES tree(id),   -- NULL for notes on shared entities (artifacts)
  entity_kind TEXT NOT NULL,
  entity_id   TEXT NOT NULL,
  body        TEXT NOT NULL,
  author      TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  private     BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX ix_note_entity ON note(entity_kind, entity_id);

-- =============================================================================
-- OPS
-- =============================================================================

CREATE TABLE audit_log (
  id          TEXT PRIMARY KEY,
  tree_id     TEXT REFERENCES tree(id),
  at          TEXT NOT NULL,
  actor       TEXT NOT NULL,
  action      TEXT NOT NULL,            -- insert | update | delete | accept | reject | import | export
  entity_kind TEXT NOT NULL,
  entity_id   TEXT NOT NULL,
  diff_json   TEXT
);
CREATE INDEX ix_audit_entity ON audit_log(entity_kind, entity_id);

-- Storage backends for the archive (local now, s3 later). Config, not code.
CREATE TABLE storage_target (
  name        TEXT PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('local','s3')),
  uri         TEXT NOT NULL,            -- file:///.../archive  |  s3://bucket/prefix
  is_master   BOOLEAN NOT NULL DEFAULT FALSE,
  object_lock BOOLEAN NOT NULL DEFAULT FALSE,
  enabled     BOOLEAN NOT NULL DEFAULT TRUE,
  notes       TEXT
);

-- Which targets hold which object, and when fixity was last verified.
CREATE TABLE artifact_copy (
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
  target_name     TEXT NOT NULL REFERENCES storage_target(name),
  stored_at       TEXT NOT NULL,
  last_verified   TEXT,
  verify_ok       BOOLEAN,
  PRIMARY KEY (artifact_sha256, target_name)
);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- The inputs of the living default (docs/DATA-ARCHITECTURE.md §7 decision 3): the owner's word and held death evidence;
-- the tier from the home person is walked by the app (Catalog.living), which decides.
CREATE VIEW v_person_vitals AS
SELECT
  p.tree_id,
  p.id AS person_id,
  p.display_name,
  p.living_override,
  (SELECT MIN(e.date_start) FROM event e
     JOIN event_participant ep ON ep.event_id = e.id
    WHERE ep.person_id = p.id AND e.event_type = 'Birth')                         AS birth_date,
  (SELECT MIN(e.date_start) FROM event e
     JOIN event_participant ep ON ep.event_id = e.id
    WHERE ep.person_id = p.id AND e.event_type IN ('Death','Burial','Cremation','Probate','Will')) AS death_date,
  EXISTS (SELECT 1 FROM event e JOIN event_participant ep ON ep.event_id = e.id
           WHERE ep.person_id = p.id AND e.event_type IN ('Death','Burial','Cremation','Probate','Will')) AS has_death_evidence
FROM person p;

-- Conclusions with no accepted assertion: the "untrusted data" report.
CREATE VIEW v_unsupported_event AS
SELECT e.* FROM event e
WHERE NOT EXISTS (SELECT 1 FROM assertion a
                   WHERE a.subject_kind = 'event' AND a.subject_id = e.id AND a.status = 'accepted');

-- A person is supported only by an ACCEPTED assertion on the person or on one of
-- their events. The persona link alone is not support (it is definitional).
CREATE VIEW v_unsupported_person AS
SELECT p.* FROM person p
WHERE NOT EXISTS (SELECT 1 FROM assertion a
                   WHERE a.subject_kind = 'person' AND a.subject_id = p.id AND a.status = 'accepted')
  AND NOT EXISTS (SELECT 1 FROM assertion a
                   JOIN event_participant ep ON ep.event_id = a.subject_id AND ep.person_id = p.id
                   WHERE a.subject_kind = 'event' AND a.status = 'accepted');

-- Artifacts with fewer than two verified copies.
CREATE VIEW v_artifact_under_replicated AS
SELECT a.sha256, a.byte_size, a.source_id,
       (SELECT COUNT(*) FROM artifact_copy c WHERE c.artifact_sha256 = a.sha256 AND c.verify_ok) AS verified_copies
FROM artifact a
WHERE NOT EXISTS (SELECT 1 FROM tombstone t WHERE t.artifact_sha256 = a.sha256)
  AND (SELECT COUNT(*) FROM artifact_copy c WHERE c.artifact_sha256 = a.sha256 AND c.verify_ok) < 2;

-- Search keys per person: canonical names plus every alias not rejected.
CREATE VIEW v_person_search_key AS
SELECT pn.person_id, p.tree_id, TRIM(COALESCE(pn.given,'') || ' ' || COALESCE(pn.surname,'')) AS value, 'name:' || pn.name_type AS kind, 'canonical' AS status
FROM person_name pn JOIN person p ON p.id = pn.person_id
UNION ALL
SELECT a.entity_id, a.tree_id, a.value, a.kind, a.status
FROM alias a WHERE a.entity_kind = 'person' AND a.status <> 'rejected';
