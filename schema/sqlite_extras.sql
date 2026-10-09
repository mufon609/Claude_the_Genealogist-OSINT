-- SQLite-only objects. Applied after catalog.sql when the engine is SQLite.

-- Insert-only tables (CLAUDE.md hard rule 2; docs/DATA-ARCHITECTURE.md §1): the archive's rows, the evidence, the research
-- log and the audit trail. A correction is a new row; the one UPDATE allowed is a write-once column, superseded_by on
-- extraction, household and search_log, set once from empty to the row that takes the old one's place. Every other UPDATE
-- and every DELETE is refused, and so is an INSERT OR REPLACE over a row: every connection is opened with recursive triggers
-- on (tools/treelib.py open_db), under which the row a replace deletes fires its table's delete trigger. tools/check.py tries
-- each column of each table, and a replace of each.
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
CREATE TRIGGER trg_artifact_locator_no_update BEFORE UPDATE ON artifact_locator BEGIN
  SELECT RAISE(ABORT, 'artifact_locator rows are immutable; insert another locator');
END;
CREATE TRIGGER trg_artifact_locator_no_delete BEFORE DELETE ON artifact_locator BEGIN
  SELECT RAISE(ABORT, 'artifact_locator rows are never deleted');
END;
CREATE TRIGGER trg_tombstone_no_update BEFORE UPDATE ON tombstone BEGIN
  SELECT RAISE(ABORT, 'tombstone rows are immutable');
END;
CREATE TRIGGER trg_tombstone_no_delete BEFORE DELETE ON tombstone BEGIN
  SELECT RAISE(ABORT, 'tombstone rows are never deleted');
END;
CREATE TRIGGER trg_extractor_no_update BEFORE UPDATE ON extractor BEGIN
  SELECT RAISE(ABORT, 'extractor rows are immutable; a changed extractor is a new version');
END;
CREATE TRIGGER trg_extractor_no_delete BEFORE DELETE ON extractor BEGIN
  SELECT RAISE(ABORT, 'extractor rows are never deleted');
END;
CREATE TRIGGER trg_extraction_no_update BEFORE UPDATE OF id, artifact_sha256, extractor_id, ran_at, status, full_text, structured_json, notes ON extraction BEGIN
  SELECT RAISE(ABORT, 'extraction rows are immutable; re-run the extraction');
END;
CREATE TRIGGER trg_extraction_superseded_once BEFORE UPDATE OF superseded_by ON extraction
WHEN OLD.superseded_by IS NOT NULL OR NEW.superseded_by IS NULL BEGIN
  SELECT RAISE(ABORT, 'extraction.superseded_by is written once, from empty');
END;
CREATE TRIGGER trg_extraction_no_delete BEFORE DELETE ON extraction BEGIN
  SELECT RAISE(ABORT, 'extraction rows are never deleted; re-run the extraction');
END;
CREATE TRIGGER trg_persona_relation_no_update BEFORE UPDATE ON persona_relation BEGIN
  SELECT RAISE(ABORT, 'persona_relation rows are immutable; re-run the extraction');
END;
CREATE TRIGGER trg_persona_relation_no_delete BEFORE DELETE ON persona_relation BEGIN
  SELECT RAISE(ABORT, 'persona_relation rows are never deleted; re-run the extraction');
END;
CREATE TRIGGER trg_search_log_no_update BEFORE UPDATE OF id, tree_id, plan_step_id, question_id, executed_at, executed_by, source_id, query_json, outcome, artifacts_json, notes ON search_log BEGIN
  SELECT RAISE(ABORT, 'search_log rows are immutable; a run read again is a new row that supersedes it (log_search.restate)');
END;
CREATE TRIGGER trg_search_log_superseded_once BEFORE UPDATE OF superseded_by ON search_log
WHEN OLD.superseded_by IS NOT NULL OR NEW.superseded_by IS NULL BEGIN
  SELECT RAISE(ABORT, 'search_log.superseded_by is written once, from empty');
END;
CREATE TRIGGER trg_search_log_no_delete BEFORE DELETE ON search_log BEGIN
  SELECT RAISE(ABORT, 'search_log rows are never deleted');
END;
CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log BEGIN
  SELECT RAISE(ABORT, 'audit_log rows are immutable; record a new row');
END;
CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log BEGIN
  SELECT RAISE(ABORT, 'audit_log rows are never deleted');
END;
CREATE TRIGGER trg_same_record_no_update BEFORE UPDATE ON same_record BEGIN
  SELECT RAISE(ABORT, 'same_record rows are immutable; the owner''s later word on a pair stands over an earlier one');
END;
CREATE TRIGGER trg_same_record_no_delete BEFORE DELETE ON same_record BEGIN
  SELECT RAISE(ABORT, 'same_record rows are never deleted; the owner keeps two copies apart with a row of their own');
END;
CREATE TRIGGER trg_household_no_update BEFORE UPDATE OF id, form, page_json, complete, missing_json, ground, grouped_by, grouped_at ON household BEGIN
  SELECT RAISE(ABORT, 'household rows are immutable; the households grouped again are new rows that supersede them');
END;
CREATE TRIGGER trg_household_superseded_once BEFORE UPDATE OF superseded_by ON household
WHEN OLD.superseded_by IS NOT NULL OR NEW.superseded_by IS NULL BEGIN
  SELECT RAISE(ABORT, 'household.superseded_by is written once, from empty');
END;
CREATE TRIGGER trg_household_no_delete BEFORE DELETE ON household BEGIN
  SELECT RAISE(ABORT, 'household rows are never deleted; the households grouped again supersede them');
END;
CREATE TRIGGER trg_household_member_no_update BEFORE UPDATE ON household_member BEGIN
  SELECT RAISE(ABORT, 'household_member rows are immutable; the households grouped again are new rows');
END;
CREATE TRIGGER trg_household_member_no_delete BEFORE DELETE ON household_member BEGIN
  SELECT RAISE(ABORT, 'household_member rows are never deleted');
END;
CREATE TRIGGER trg_task_run_no_update BEFORE UPDATE ON task_run BEGIN
  SELECT RAISE(ABORT, 'task_run rows are immutable; a task run again is a new row');
END;
CREATE TRIGGER trg_task_run_no_delete BEFORE DELETE ON task_run BEGIN
  SELECT RAISE(ABORT, 'task_run rows are never deleted');
END;
