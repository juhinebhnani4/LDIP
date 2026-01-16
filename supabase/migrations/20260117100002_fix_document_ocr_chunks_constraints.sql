-- Fix document_ocr_chunks table constraints identified in code review
-- Story 15.1 Code Review Fixes
-- Issues addressed:
--   #2 (HIGH): created_at/updated_at missing NOT NULL constraint
--   #3 (HIGH): UPDATE policy missing WITH CHECK clause (security)
--   #6 (MEDIUM): chunk_index missing >= 0 CHECK constraint

-- =============================================================================
-- FIX #2: Add NOT NULL constraints to timestamp columns
-- =============================================================================

-- First, ensure no NULL values exist (set to now() if any)
UPDATE public.document_ocr_chunks
SET created_at = now()
WHERE created_at IS NULL;

UPDATE public.document_ocr_chunks
SET updated_at = now()
WHERE updated_at IS NULL;

-- Now add NOT NULL constraints
ALTER TABLE public.document_ocr_chunks
ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE public.document_ocr_chunks
ALTER COLUMN updated_at SET NOT NULL;

-- =============================================================================
-- FIX #6: Add CHECK constraint for chunk_index >= 0
-- =============================================================================

ALTER TABLE public.document_ocr_chunks
ADD CONSTRAINT document_ocr_chunks_check_chunk_index CHECK (chunk_index >= 0);

-- =============================================================================
-- FIX #3: Replace UPDATE policy with one that includes WITH CHECK
-- This prevents users from changing matter_id to move chunks between matters
-- =============================================================================

-- Drop existing policy
DROP POLICY IF EXISTS "Editors and Owners can update chunks" ON public.document_ocr_chunks;

-- Recreate with WITH CHECK clause to prevent matter_id changes
CREATE POLICY "Editors and Owners can update chunks"
ON public.document_ocr_chunks FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
)
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- =============================================================================
-- FIX #8 (LOW): Add index comments for documentation
-- =============================================================================

COMMENT ON INDEX public.idx_doc_ocr_chunks_document_id IS 'Optimizes chunk lookup by document_id';
COMMENT ON INDEX public.idx_doc_ocr_chunks_matter_id IS 'Optimizes RLS policy checks and matter-scoped queries';
COMMENT ON INDEX public.idx_doc_ocr_chunks_document_status IS 'Optimizes queries finding pending/failed chunks for a document';
