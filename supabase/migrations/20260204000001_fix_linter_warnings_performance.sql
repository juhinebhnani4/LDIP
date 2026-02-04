-- Migration: Fix Supabase database linter warnings
-- Purpose: Resolve duplicate indexes and multiple permissive RLS policy warnings
-- Issues fixed:
--   1. Duplicate indexes on llm_quota_limits, statement_comparisons
--   2. Multiple permissive DELETE policies on documents (also fixes security issue)
--   3. Multiple permissive SELECT policies on matter_attorneys
--   4. Multiple permissive SELECT policies on toc_pages

-- =============================================================================
-- 1. DROP DUPLICATE INDEXES
-- =============================================================================

-- llm_quota_limits: UNIQUE constraint on provider already creates
-- llm_quota_limits_provider_key; the explicit idx is redundant
DROP INDEX IF EXISTS public.idx_llm_quota_limits_provider;

-- statement_comparisons: two migrations created indexes on the same columns
-- Keep the longer, more descriptive names; drop the shorter duplicates
DROP INDEX IF EXISTS public.idx_statement_comparisons_stmt_a;
DROP INDEX IF EXISTS public.idx_statement_comparisons_stmt_b;

-- =============================================================================
-- 2. FIX documents DELETE POLICIES
-- =============================================================================
-- Problem: Two permissive DELETE policies combine with OR logic, which means
-- non-owners can delete non-auto-fetched documents (unintended).
-- Fix: Make "Prevent deletion of auto-fetched documents" RESTRICTIVE so it
-- uses AND logic with the permissive "Only Owners can delete" policy.
-- Result: Only owners can delete, AND auto-fetched docs are protected unless
-- the user is an owner.

DROP POLICY IF EXISTS "Prevent deletion of auto-fetched documents" ON public.documents;

CREATE POLICY "Prevent deletion of auto-fetched documents"
ON public.documents AS RESTRICTIVE FOR DELETE
USING (
  source != 'auto_fetched'
  OR matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- 3. FIX matter_attorneys SELECT POLICIES
-- =============================================================================
-- Problem: Two permissive SELECT policies:
--   "Users can view own memberships" (user_id = auth.uid())
--   "Users can view co-members via function" (user_has_matter_access(matter_id))
-- The function check already covers own membership (if you're a member, the
-- function returns true for that matter, letting you see all co-members).
-- Fix: Drop the redundant "own memberships" policy.

DROP POLICY IF EXISTS "Users can view own memberships" ON public.matter_attorneys;

-- =============================================================================
-- 4. FIX toc_pages SELECT POLICIES
-- =============================================================================
-- Problem: "Editors and Owners can manage toc_pages" uses FOR ALL, which
-- includes SELECT, overlapping with the dedicated SELECT policy.
-- Fix: Replace FOR ALL with separate INSERT, UPDATE, DELETE policies so
-- there is only one permissive SELECT policy.

DROP POLICY IF EXISTS "Editors and Owners can manage toc_pages" ON public.toc_pages;

CREATE POLICY "Editors and Owners can insert toc_pages"
ON public.toc_pages FOR INSERT
WITH CHECK (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
);

CREATE POLICY "Editors and Owners can update toc_pages"
ON public.toc_pages FOR UPDATE
USING (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
)
WITH CHECK (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
);

CREATE POLICY "Editors and Owners can delete toc_pages"
ON public.toc_pages FOR DELETE
USING (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
);
