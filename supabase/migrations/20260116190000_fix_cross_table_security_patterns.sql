-- Migration: Fix Cross-Table Security Patterns
-- Date: 2026-01-16
-- Fixes similar patterns found during Epic 2c code review:
--   1. HIGH: Citations RLS INSERT - validate source_document_id belongs to same matter
--   2. HIGH: Citations RLS UPDATE - validate target_act_document_id on update
--   3. MEDIUM: Missing composite index for ocr_validation_log
--   4. MEDIUM: Missing composite index for statement_comparisons severity sort
--   5. MEDIUM: Split ocr_human_review RLS into role-based policies

-- =============================================================================
-- Fix #1 & #2: Citations RLS policies - Cross-matter FK validation
-- =============================================================================
-- The original policies only validated matter_id but not the document foreign keys.
-- An attacker could insert/update citations with document IDs from other matters.

-- Drop existing policies
DROP POLICY IF EXISTS "Editors and Owners can insert citations" ON public.citations;
DROP POLICY IF EXISTS "Editors and Owners can update citations" ON public.citations;

-- Recreate INSERT policy with document FK validation
CREATE POLICY "Editors and Owners can insert citations"
ON public.citations FOR INSERT
WITH CHECK (
  -- User must be editor/owner of the matter
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
  AND
  -- source_document_id MUST belong to the SAME matter (required field)
  source_document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id = matter_id
  )
  AND
  -- target_act_document_id must also belong to same matter IF provided
  (
    target_act_document_id IS NULL
    OR target_act_document_id IN (
      SELECT d.id FROM public.documents d
      WHERE d.matter_id = matter_id
    )
  )
);

-- Recreate UPDATE policy with FK validation
-- Note: WITH CHECK validates the NEW values after update
CREATE POLICY "Editors and Owners can update citations"
ON public.citations FOR UPDATE
USING (
  -- User must be editor/owner of the matter (for reading current row)
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
)
WITH CHECK (
  -- After update, all FKs must still belong to the same matter
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
  AND
  source_document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id = matter_id
  )
  AND
  (
    target_act_document_id IS NULL
    OR target_act_document_id IN (
      SELECT d.id FROM public.documents d
      WHERE d.matter_id = matter_id
    )
  )
);

-- =============================================================================
-- Fix #3: Missing composite index for ocr_validation_log
-- =============================================================================
-- Query pattern: SELECT * FROM ocr_validation_log WHERE document_id = ? ORDER BY created_at DESC
-- Current index only covers document_id, forcing a separate sort operation

CREATE INDEX IF NOT EXISTS idx_validation_log_document_created
ON public.ocr_validation_log(document_id, created_at DESC);

COMMENT ON INDEX idx_validation_log_document_created IS 'Speeds up validation log queries sorted by most recent first';

-- =============================================================================
-- Fix #4: Missing composite index for statement_comparisons severity sort
-- =============================================================================
-- Query pattern: SELECT * FROM statement_comparisons WHERE matter_id = ? ORDER BY result, created_at DESC
-- The contradiction list UI sorts by severity (result type) then date

CREATE INDEX IF NOT EXISTS idx_statement_comparisons_matter_result_created
ON public.statement_comparisons(matter_id, result, created_at DESC);

COMMENT ON INDEX idx_statement_comparisons_matter_result_created IS 'Speeds up contradiction list sorted by severity (result type) and date';

-- =============================================================================
-- Fix #5: Split ocr_human_review RLS into role-based policies
-- =============================================================================
-- The original "FOR ALL" policy allows any matter member to DELETE reviews.
-- Should follow the pattern: viewers SELECT, editors INSERT/UPDATE, owners DELETE

-- Drop the overly permissive "FOR ALL" policy
DROP POLICY IF EXISTS "Users access own matter human reviews" ON public.ocr_human_review;

-- Policy 1: Any matter member can VIEW human review queue
CREATE POLICY "Users can view own matter human reviews"
ON public.ocr_human_review FOR SELECT
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT reviews (system creates these)
CREATE POLICY "Editors and Owners can insert human reviews"
ON public.ocr_human_review FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
    AND role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE reviews (complete/skip)
CREATE POLICY "Editors and Owners can update human reviews"
ON public.ocr_human_review FOR UPDATE
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
    AND role IN ('owner', 'editor')
  )
);

-- Policy 4: Only Owners can DELETE reviews
CREATE POLICY "Only Owners can delete human reviews"
ON public.ocr_human_review FOR DELETE
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
    AND role = 'owner'
  )
);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON POLICY "Editors and Owners can insert citations" ON public.citations IS
  'INSERT with cross-matter FK validation - documents must belong to same matter';

COMMENT ON POLICY "Editors and Owners can update citations" ON public.citations IS
  'UPDATE with cross-matter FK validation - prevents changing document IDs to other matters';
