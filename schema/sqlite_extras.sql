-- SQLite-only objects. Applied after catalog.sql when the engine is SQLite.
-- Postgres gets tsvector equivalents in a separate file when we get there.

CREATE VIRTUAL TABLE fts_extraction USING fts5(
  extraction_id UNINDEXED,
  full_text,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER trg_extraction_ai AFTER INSERT ON extraction
WHEN NEW.full_text IS NOT NULL BEGIN
  INSERT INTO fts_extraction (extraction_id, full_text) VALUES (NEW.id, NEW.full_text);
END;

CREATE VIRTUAL TABLE fts_persona USING fts5(
  persona_id UNINDEXED,
  name_text,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER trg_persona_ai AFTER INSERT ON persona
WHEN NEW.name_text IS NOT NULL BEGIN
  INSERT INTO fts_persona (persona_id, name_text) VALUES (NEW.id, NEW.name_text);
END;

CREATE VIRTUAL TABLE fts_note USING fts5(
  note_id UNINDEXED,
  body,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER trg_note_ai AFTER INSERT ON note BEGIN
  INSERT INTO fts_note (note_id, body) VALUES (NEW.id, NEW.body);
END;

-- Archive rows are write-once.
CREATE TRIGGER trg_artifact_no_update BEFORE UPDATE ON artifact BEGIN
  SELECT RAISE(ABORT, 'artifact rows are immutable; insert a derived artifact or a tombstone');
END;
CREATE TRIGGER trg_artifact_no_delete BEFORE DELETE ON artifact BEGIN
  SELECT RAISE(ABORT, 'artifact rows are never deleted; insert a tombstone');
END;
CREATE TRIGGER trg_persona_no_update BEFORE UPDATE ON persona BEGIN
  SELECT RAISE(ABORT, 'persona rows are immutable; re-run the extraction');
END;
CREATE TRIGGER trg_persona_no_delete BEFORE DELETE ON persona BEGIN
  SELECT RAISE(ABORT, 'persona rows are never deleted; re-run the extraction');
END;
CREATE TRIGGER trg_persona_fact_no_update BEFORE UPDATE ON persona_fact BEGIN
  SELECT RAISE(ABORT, 'persona_fact rows are immutable; re-run the extraction');
END;
CREATE TRIGGER trg_persona_fact_no_delete BEFORE DELETE ON persona_fact BEGIN
  SELECT RAISE(ABORT, 'persona_fact rows are never deleted; re-run the extraction');
END;
CREATE TRIGGER trg_same_record_no_update BEFORE UPDATE ON same_record BEGIN
  SELECT RAISE(ABORT, 'same_record rows are immutable; the owner''s later word on a pair stands over an earlier one');
END;
CREATE TRIGGER trg_same_record_no_delete BEFORE DELETE ON same_record BEGIN
  SELECT RAISE(ABORT, 'same_record rows are never deleted; the owner keeps two copies apart with a row of their own');
END;
