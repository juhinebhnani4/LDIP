-- Add soft delete support to documents table
-- Story 10D.4: Implement Documents Tab File Actions

-- =============================================================================
-- Add deleted_at column for soft delete (30-day retention)
-- =============================================================================

ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

-- Index for efficient soft-delete filtering
CREATE INDEX IF NOT EXISTS idx_documents_deleted_at ON public.documents(deleted_at);

-- Composite index for common query pattern (matter_id + not deleted)
CREATE INDEX IF NOT EXISTS idx_documents_matter_not_deleted
ON public.documents(matter_id)
WHERE deleted_at IS NULL;

-- Comment
COMMENT ON COLUMN public.documents.deleted_at IS 'Timestamp of soft deletion. Documents are permanently deleted after 30 days.';

-- =============================================================================
-- Update RLS policies to exclude soft-deleted documents
-- =============================================================================

-- Drop and recreate the SELECT policy to filter out soft-deleted documents
DROP POLICY IF EXISTS "Users can view documents from their matters" ON public.documents;

CREATE POLICY "Users can view documents from their matters"
ON public.documents FOR SELECT
USING (
  deleted_at IS NULL
  AND matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Drop and recreate the UPDATE policy to prevent updates on soft-deleted documents
DROP POLICY IF EXISTS "Editors and Owners can update documents" ON public.documents;

CREATE POLICY "Editors and Owners can update documents"
ON public.documents FOR UPDATE
USING (
  deleted_at IS NULL
  AND matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);
