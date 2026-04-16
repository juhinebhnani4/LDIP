-- INF-009 fix: backfill status='deleted' for all soft-deleted documents.
-- Prior to this fix, soft_delete_document() only set deleted_at but left status
-- unchanged, causing recovery tasks to treat deleted docs as stuck.
-- The code now sets status='deleted' atomically with deleted_at; this migration
-- brings existing data in line.

UPDATE documents
SET status = 'deleted', updated_at = now()
WHERE deleted_at IS NOT NULL
  AND status != 'deleted';
