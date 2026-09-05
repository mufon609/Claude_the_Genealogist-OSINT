-- 0.3.0: aliases for persons/families; variant classification for place strings.
CREATE TABLE alias (
  id                      TEXT PRIMARY KEY,
  tree_id                 TEXT REFERENCES tree(id),      -- NULL for shared entities
  entity_kind             TEXT NOT NULL CHECK (entity_kind IN ('person','family','place')),
  entity_id               TEXT NOT NULL,
  value                   TEXT NOT NULL,                 -- exactly as it appears somewhere
  kind                    TEXT NOT NULL CHECK (kind IN ('typo','phonetic','transcription','abbreviation','translation',
                                                        'historical','jurisdiction_change','jurisdiction_error','context_glue',
                                                        'nickname','married_name','detail','unclassified')),
  status                  TEXT NOT NULL DEFAULT 'observed' CHECK (status IN ('observed','confirmed','not_this_entity')),
  source_persona_fact_id  TEXT REFERENCES persona_fact(id),
  source_artifact_sha256  TEXT REFERENCES artifact(sha256),
  added_by                TEXT NOT NULL,
  added_at                TEXT NOT NULL,
  notes                   TEXT,
  UNIQUE (entity_kind, entity_id, value)
);
CREATE INDEX ix_alias_entity ON alias(entity_kind, entity_id);
CREATE INDEX ix_alias_value  ON alias(tree_id, value);

ALTER TABLE place_string ADD COLUMN variant_kind TEXT
  CHECK (variant_kind IN ('typo','phonetic','transcription','abbreviation','translation','historical','jurisdiction_change',
                          'jurisdiction_error','context_glue','detail','unclassified') OR variant_kind IS NULL);

-- Search keys per person: canonical names plus every alias not rejected.
CREATE VIEW v_person_search_key AS
SELECT pn.person_id, p.tree_id, TRIM(COALESCE(pn.given,'') || ' ' || COALESCE(pn.surname,'')) AS value, 'name:' || pn.name_type AS kind, 'canonical' AS status
FROM person_name pn JOIN person p ON p.id = pn.person_id
UNION ALL
SELECT a.entity_id, a.tree_id, a.value, a.kind, a.status
FROM alias a WHERE a.entity_kind = 'person' AND a.status <> 'not_this_entity';

INSERT INTO schema_migration (version, applied_at, notes) VALUES ('0.3.0', strftime('%Y-%m-%dT%H:%M:%SZ','now'), 'alias table, place_string.variant_kind, v_person_search_key');
