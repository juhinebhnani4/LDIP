-- Fix documents_status_check constraint to include all DocumentStatus enum values
-- BUG-LT-C: The constraint only allowed 6 values but the code uses 12 different statuses.
-- This caused 400 Bad Request when embed_chunks tried to set status to "searchable".

-- Drop the old constraint
ALTER TABLE public.documents DROP CONSTRAINT IF EXISTS documents_status_check;

-- Add new constraint with all DocumentStatus enum values
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
    'failed'
));

COMMENT ON COLUMN public.documents.status IS 'Document processing status: pending → processing → ocr_complete → chunking → embedding → searchable → completed. Can fail at any stage.';
