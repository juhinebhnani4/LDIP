-- PROD-005: add 'deleted' to documents_status_check.
--
-- The codebase has assumed 'deleted' is a valid documents.status since INF-009
-- (DocumentStatus.DELETED enum, soft_delete_document writing status='deleted',
-- maintenance_tasks._TERMINAL_STATUSES, and the 20260416 backfill migration).
-- But the CHECK constraint was never updated to allow it — so every
-- soft_delete_document() write was rejected with SQLSTATE 23514 and the
-- single-document delete endpoint 500'd. The 20260416 backfill matched 0 rows
-- (no doc ever reached deleted_at), so the gap stayed invisible.
--
-- This makes the existing convention legal. Additive + reversible: re-adding
-- the prior 12-value constraint reverts it (safe only while no 'deleted' rows
-- exist, which holds today).

ALTER TABLE public.documents DROP CONSTRAINT IF EXISTS documents_status_check;

ALTER TABLE public.documents ADD CONSTRAINT documents_status_check
CHECK (status IN (
    'pending',
    'processing',
    'ocr_complete',
    'ocr_failed',
    'pending_review',
    'chunking',
    'chunking_failed',
    'embedding',
    'embedding_failed',
    'searchable',
    'completed',
    'failed',
    'deleted'
));

COMMENT ON COLUMN public.documents.status IS 'Document processing status: pending → processing → ocr_complete → chunking → embedding → searchable → completed. Can fail at any stage. Terminal sink: deleted (soft-delete, INF-009/PROD-005) — paired with deleted_at.';
