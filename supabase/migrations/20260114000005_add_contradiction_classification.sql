-- Migration: Add contradiction classification columns
-- Story 5-3: Contradiction Type Classification
-- Epic 5: Consistency & Contradiction Engine
--
-- Adds contradiction type and extracted values for attorney prioritization.
-- Attorneys can filter by type (factual vs semantic) to focus on high-priority issues.

-- =============================================================================
-- Add classification columns to statement_comparisons table
-- =============================================================================

-- Add contradiction type column with constraint
ALTER TABLE public.statement_comparisons
ADD COLUMN IF NOT EXISTS contradiction_type VARCHAR(30) CHECK (
    contradiction_type IS NULL OR
    contradiction_type IN (
        'semantic_contradiction',
        'factual_contradiction',
        'date_mismatch',
        'amount_mismatch'
    )
);

-- Add extracted values for attorney display
-- Format: {"value_a": {"original": "15/01/2024", "normalized": "2024-01-15"}, "value_b": {...}}
ALTER TABLE public.statement_comparisons
ADD COLUMN IF NOT EXISTS extracted_values JSONB DEFAULT '{}'::jsonb;

-- =============================================================================
-- Index for filtering by contradiction type (attorney prioritization use case)
-- =============================================================================

-- Index for filtering contradictions by type
-- Partial index only on contradiction results for efficiency
CREATE INDEX IF NOT EXISTS idx_statement_comparisons_type
ON public.statement_comparisons(matter_id, contradiction_type)
WHERE result = 'contradiction';

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON COLUMN public.statement_comparisons.contradiction_type IS
'Story 5-3: Classification of contradiction type for attorney prioritization. Values: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch. NULL for non-contradictions.';

COMMENT ON COLUMN public.statement_comparisons.extracted_values IS
'Story 5-3: Structured values for attorney display. Format: {"value_a": {"original": "15/01/2024", "normalized": "2024-01-15"}, "value_b": {...}}. Used for date_mismatch and amount_mismatch types.';
