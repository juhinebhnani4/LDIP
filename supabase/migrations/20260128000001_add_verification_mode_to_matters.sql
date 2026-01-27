-- Story 3.1: Add Verification Mode Setting to Matters
-- Epic 3: Compliance & UX
-- Gap #1: Configurable verification gates per matter

-- =============================================================================
-- Add verification_mode column to matters table
-- =============================================================================

-- Add verification_mode column with 'advisory' as default (existing behavior)
ALTER TABLE public.matters
ADD COLUMN IF NOT EXISTS verification_mode TEXT DEFAULT 'advisory'
    CHECK (verification_mode IN ('advisory', 'required'));

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for filtering matters by verification mode
CREATE INDEX IF NOT EXISTS idx_matters_verification_mode
ON public.matters (verification_mode)
WHERE deleted_at IS NULL;

-- Composite index for queries filtering by both status and verification mode
CREATE INDEX IF NOT EXISTS idx_matters_status_verification_mode
ON public.matters (status, verification_mode)
WHERE deleted_at IS NULL;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN public.matters.verification_mode IS 'Verification requirement mode: advisory (acknowledgment only) or required (100% verification for export) - Story 3.1';

-- =============================================================================
-- BACKWARD COMPATIBILITY
-- =============================================================================

-- All existing matters default to 'advisory' mode, preserving current behavior.
-- Only matters explicitly set to 'required' will enforce 100% verification before export.
