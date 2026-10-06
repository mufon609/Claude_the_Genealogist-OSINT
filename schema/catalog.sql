-- =============================================================================
-- tree catalog schema  v0.8.7
-- Portable SQL: runs on SQLite 3.35+ and PostgreSQL 13+ without edits.
-- Conventions
--   * ids are ULIDs stored as 26-char TEXT; artifacts are keyed by sha256 hex.
--   * timestamps are ISO-8601 UTC TEXT ("2026-09-05T18:02:11Z").
--   * dates in records use the date_* column group (see persona_fact / event).
--   * JSON is stored as TEXT (json_* functions exist on both engines).
--   * booleans are BOOLEAN (SQLite stores 0/1).
--   * SQLite-only objects live in sqlite_extras.sql: the insert-only triggers on artifact,
--     artifact_locator, tombstone, extractor, extraction, persona, persona_fact, persona_relation, same_record, household,
--     household_member, search_log, task_run and audit_log take no UPDATE but a write-once superseded_by, and no DELETE.
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
  place_type    TEXT,                    -- country | state (a country's first-level unit: a US state, a province, a prefecture; the country says whether it is American) | county | city | town | township | parish | cemetery | address | region | unknown
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
  prompt_sha256 TEXT,                   -- hash of the prompt template used; a reading of a record image: the sha256 of app/person/read_record.md as it stood
  config_json   TEXT,
  created_at    TEXT NOT NULL,
  UNIQUE (kind, name, version, prompt_sha256)
);

-- One run of one extractor over one artifact. Never updated in place;
-- a re-run inserts a new row and sets superseded_by on the old one, written once from empty.
CREATE TABLE extraction (
  id              TEXT PRIMARY KEY,
  artifact_sha256 TEXT NOT NULL REFERENCES artifact(sha256),
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

-- Two archived copies of one record (docs/DATA-ARCHITECTURE.md §7 decision 15): the document made at an event, held as
-- FamilySearch's index page of it, its image, a state index's line. A copy is a whole file (entry '') or one row of a listing
-- holding many records each under its own number (entry: that row's catalog.persona_key as JSON); a record is every copy
-- these rows join, directly or through another copy (catalog.record_copies). Code joins two copies on what they share of
-- the record itself, for every tree (tree_id NULL; basis citation: archived under one record id; entry: one FamilySearch
-- entry id on both readings; number: one certificate number of one year), where an entry of both readings agrees by name;
-- the owner's word joins two copies or keeps two apart in one tree (basis owner), standing above code's on that pair, the
-- latest word last. Insert-only.
CREATE TABLE same_record (
  id          TEXT PRIMARY KEY,
  tree_id     TEXT REFERENCES tree(id),
  a_sha256    TEXT NOT NULL REFERENCES artifact(sha256),
  a_entry     TEXT NOT NULL DEFAULT '',
  b_sha256    TEXT NOT NULL REFERENCES artifact(sha256),
  b_entry     TEXT NOT NULL DEFAULT '',
  same        BOOLEAN NOT NULL,
  basis       TEXT NOT NULL CHECK (basis IN ('citation','entry','number','owner')),
  shared      TEXT,                 -- what the two share, in words: "apid 1,3077::604036", "number 14205 of 1946"
  decided_by  TEXT NOT NULL,
  decided_at  TEXT NOT NULL,
  notes       TEXT
);
CREATE INDEX ix_same_record_a ON same_record(a_sha256, a_entry);
CREATE INDEX ix_same_record_b ON same_record(b_sha256, b_entry);

-- A household read off a census form (docs/DATA-ARCHITECTURE.md §7 decision 21): the entries the form's own rule bounds as one
-- household (data/record-forms.csv's page, household and lines columns), across every copy and index page that carries them,
-- grouped by tools/households.py at the version grouped_by names. Evidence shared by every tree, like code's same_record joins:
-- no tree's decision goes into it. Insert-only: the households grouped again differently (a page newly held, a reading read
-- again, the script at another version) are new rows, and each row they replace names one holding one of its entries in
-- superseded_by, written once from empty; a household whose entries no current reading holds is replaced by a row of no members.
CREATE TABLE household (
  id            TEXT PRIMARY KEY,
  form          TEXT NOT NULL,        -- data/record-forms.csv's id: us-1900, ny-1925
  page_json     TEXT NOT NULL,        -- the form's page locators its entries hold: {"county": "Nassau", "assembly_district": "01", "election_district": "06", "page": "19"}
  complete      BOOLEAN NOT NULL,     -- nothing the form's rule shows missing: the head held and, where every member's line is read, no line between missing
  missing_json  TEXT NOT NULL,        -- what the form's rule shows missing, the head first: ["the head", "line 24"]
  ground        TEXT NOT NULL,        -- what groups the entries, in words: "lines 23 and 25 of one page; across line 24 not held, by one surname (Peters)"
  grouped_by    TEXT NOT NULL,        -- the script and its version: rule:households@0.1.0
  grouped_at    TEXT NOT NULL,
  superseded_by TEXT REFERENCES household(id)
);
CREATE INDEX ix_household_superseded ON household(superseded_by);

-- One persona of a household. A member is one entry, however many copies carry it (entry); each copy's persona of it is a row
-- with what that copy states: the relationship to the head as the form states it, as written, and no other tie. Insert-only.
CREATE TABLE household_member (
  household_id  TEXT NOT NULL REFERENCES household(id),
  persona_id    TEXT NOT NULL REFERENCES persona(id),
  entry         TEXT NOT NULL,        -- the member, one for every copy of it, as JSON: a record id (["ark", "ark:/61903/1:1:KS4R-RTQ"]), else its line on a reading's image
  relationship  TEXT,                 -- as the copy states it ("Daughter"): the Relationship to Head of Household field, a stated relation, a reading's role word; NULL where it states none
  head          BOOLEAN NOT NULL,     -- the copy states this member the head (on a form that names the head alone, its one entry)
  line          INTEGER,              -- the line the form's lines column reads for the member, NULL where none is read
  PRIMARY KEY (household_id, persona_id)
);
CREATE INDEX ix_household_member_persona ON household_member(persona_id);

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
  given       TEXT,
  surname     TEXT,
  suffix      TEXT,
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
  citation_text   TEXT,                 -- the record's short name (its collection); the full Evidence Explained citation is rendered from the archived record (tools/proof.py)
  status          TEXT NOT NULL DEFAULT 'undecided' CHECK (status IN ('undecided','accepted','rejected')),
  asserted_by     TEXT NOT NULL,        -- who set the status it now has: user:<name>, agent:<session> for user:<name>, rule:<name> for <whoever ran it>, or the import's extractor
  asserted_at     TEXT NOT NULL,        -- when that status was set
  person_decided  BOOLEAN NOT NULL DEFAULT FALSE,   -- the status is a person's own decision on this statement (a key fact or this statement decided, a vouch, a card's rejection: docs/RESEARCH-WORKFLOW.md §5–7); a record's acceptance, a re-read, a carry, a withdrawal or the import never sets it, and none of them changes a statement that carries it
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
-- open until answered, dismissed or, a conflict, resolved by the owner with a written reason naming the
-- value kept (tools/conclude.py resolve; the resolution is in detail_json); a dismissal keeps its reason, who
-- gave it and when in detail_json's dismissal, and a conflict is dismissed only with one; the decision that
-- answers it is a proposal. A missing checklist row is not a question: it is a unit of work, a search_plan row.
-- An identity question names a link or a statement beyond the limits of one life (data/life-limits.csv).
CREATE TABLE research_question (
  id                      TEXT PRIMARY KEY,
  tree_id                 TEXT NOT NULL REFERENCES tree(id),
  subject_person_id       TEXT NOT NULL REFERENCES person(id),
  kind                    TEXT NOT NULL CHECK (kind IN ('missing_parents','identity_incomplete','missing_spouse','missing_fact',
                                                        'unverified_claim','conflict','duplicate_person','unlinked_relative','identity')),
  q_key                   TEXT NOT NULL,                -- stable key for idempotent regeneration: kind + detail
  detail_json             TEXT,
  status                  TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
  closed_reason           TEXT CHECK (closed_reason IN ('answered','dismissed','gap_gone','resolved') OR closed_reason IS NULL),
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
  mode              TEXT NOT NULL CHECK (mode IN ('fetch','blocked','auto','assisted','awaiting_approval')),   -- blocked: a cited record with no free holder; assisted fetch: a cited record whose holder's link takes nothing from the citation
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

-- Every execution of a step, including the ones that found nothing. found: a page or record was archived and read, and
-- marks the step done when it is the record the step cites; none: the source answered with nothing; blocked; error: the
-- source did not answer; unread: a record was archived and no parser reads it, a web page or a connector's JSON or text response
-- alike (tools/attach.py, tools/run_step.py), held on the step's log, the step stays planned. Insert-only: a run read again (a
-- found run whose records fit no one, or that no parser reads) or carried onto the kept person's step by a merge is a new row
-- restating it (log_search.restate), and the old row's superseded_by, written once from empty, names that row; every reader
-- reads the rows whose superseded_by is empty.
CREATE TABLE search_log (
  id              TEXT PRIMARY KEY,
  tree_id         TEXT NOT NULL REFERENCES tree(id),
  plan_step_id    TEXT REFERENCES search_plan(id),
  question_id     TEXT REFERENCES research_question(id),
  executed_at     TEXT NOT NULL,
  executed_by     TEXT NOT NULL,                        -- user:<name> | agent:<name>
  source_id       TEXT REFERENCES source(id),
  query_json      TEXT NOT NULL,                        -- exactly the fields used, after include/revise
  outcome         TEXT NOT NULL CHECK (outcome IN ('found','none','blocked','error','unread')),
  artifacts_json  TEXT,                                 -- sha256s archived by this run
  notes           TEXT,
  superseded_by   TEXT REFERENCES search_log(id)        -- the row restating this run; NULL on every row a reader reads
);
CREATE INDEX ix_search_log_step ON search_log(plan_step_id);
CREATE INDEX ix_search_log_question ON search_log(question_id);

-- A model launched on a step no connector can take (tools/run_task.py; docs/DATA-ARCHITECTURE.md decisions 16 and 19), one row per
-- launch, insert-only, whichever launcher started it. The measures are the launcher's own report; the outcome is what code found, never what the model
-- reported. These numbers say what a task costs at a model and never reach a card.
CREATE TABLE task_run (
  id                 TEXT PRIMARY KEY,
  tree_id            TEXT NOT NULL REFERENCES tree(id),
  task_kind          TEXT NOT NULL CHECK (task_kind IN ('fetch')),
  holder_id          TEXT REFERENCES source(id),           -- where the task was run: the fetch list entry's holder
  plan_step_ids_json TEXT NOT NULL,                        -- the steps the task was rendered from: the entry's key
  task_json          TEXT NOT NULL,                        -- the task as rendered: link, file, call, the save script's sha256
  task_text_sha256   TEXT NOT NULL,                        -- the kind's one text (tools/tasks/<kind>.md) as it stood
  model              TEXT NOT NULL,                        -- as asked of the launcher
  effort             TEXT NOT NULL,
  started_at         TEXT NOT NULL,
  launched_by        TEXT NOT NULL,                        -- agent:run_task | agent:<session> for user:<name>
  input_tokens       INTEGER,                              -- every model's input, cache reads and writes included; NULL when the launcher gave no result, and from a session, which is given one total
  output_tokens      INTEGER,
  cost_usd           REAL,
  turns              INTEGER,
  duration_ms        INTEGER NOT NULL,                     -- the launcher's own, or the clock's when it reported none
  usage_json         TEXT,                                 -- the launcher's usage per model, as reported
  ended              TEXT NOT NULL,                        -- the launcher's terminal reason | timeout | exit <n> | no result
  denials            INTEGER,                              -- the tool calls the launcher refused the model
  answer_json        TEXT,                                 -- the model's answer as given; a report, never the outcome
  outcome            TEXT NOT NULL CHECK (outcome IN ('no_answer','invalid','nothing','mismatch','unread','none','read','card','taken')),
  differs            BOOLEAN NOT NULL,                     -- the model's report and code's finding differ; note says how
  note               TEXT,
  search_log_id      TEXT REFERENCES search_log(id),       -- the run the page's attach logged on a step of the task
  launcher           TEXT NOT NULL DEFAULT 'headless' CHECK (launcher IN ('headless','session')),   -- what started the task and returned its measures: a headless prompt, or a session's subagent
  total_tokens       INTEGER,                              -- every token the launcher reported, in and out: the one number both launchers give
  tool_uses          INTEGER                               -- the tool calls the session counted for its subagent; NULL from the headless launcher, which reports turns
);
CREATE INDEX ix_task_run_kind ON task_run(task_kind, holder_id, model, effort);

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
  created_at  TEXT NOT NULL
);
CREATE INDEX ix_note_entity ON note(entity_kind, entity_id);

-- =============================================================================
-- OPS
-- =============================================================================

-- Who did what, one row per change. Insert-only: a reset or a correction is a row of its own, never a row removed.
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

-- The inputs of the living default (docs/DATA-ARCHITECTURE.md §7 decision 3): the owner's word and held death evidence,
-- an event of a death's kind that has a statement not rejected (the file's undecided claim is held by the tree; a claim
-- the owner rejected, or an event nothing states, is not); the tier from the home person is walked by the app
-- (Catalog.living), which decides.
CREATE VIEW v_person_vitals AS
SELECT
  p.tree_id,
  p.id AS person_id,
  p.display_name,
  p.living_override,
  EXISTS (SELECT 1 FROM event e JOIN event_participant ep ON ep.event_id = e.id
           WHERE ep.person_id = p.id AND e.event_type IN ('Death','Burial','Cremation','Probate','Will')
             AND EXISTS (SELECT 1 FROM assertion a WHERE a.subject_kind = 'event' AND a.subject_id = e.id AND a.status <> 'rejected')) AS has_death_evidence
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
