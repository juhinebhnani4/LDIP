-- Migration: Add severity scoring columns
-- Story 5-4: Severity Scoring and Explanation
-- Epic 5: Consistency & Contradiction Engine
--
-- Adds severity level, severity reasoning, and explanation columns
-- to statement_comparisons table for attorney prioritization.

-- =============================================================================
-- Add severity scoring columns to statement_comparisons table
-- =============================================================================

-- Add severity level column with constraint
ALTER TABLE public.statement_comparisons
ADD COLUMN IF NOT EXISTS severity VARCHAR(10) CHECK (
    severity IS NULL OR
    severity IN ('high', 'medium', 'low')
);

-- Add severity reasoning column (brief justification)
ALTER TABLE public.statement_comparisons
ADD COLUMN IF NOT EXISTS severity_reasoning TEXT;

-- Add explanation column (attorney-ready natural language explanation)
ALTER TABLE public.statement_comparisons
ADD COLUMN IF NOT EXISTS explanation TEXT;

-- =============================================================================
-- Index for attorney priority filtering (high severity first)
-- =============================================================================

-- Partial index for severity filtering on contradictions only
-- Enables efficient queries like: "Show HIGH severity contradictions first"
CREATE INDEX IF NOT EXISTS idx_statement_comparisons_severity
ON public.statement_comparisons(matter_id, severity)
WHERE result = 'contradiction';

-- =============================================================================
-- Comments for documentation
-- =============================================================================

COMMENT ON COLUMN public.statement_comparisons.severity IS
'Story 5-4: Severity level for attorney prioritization. Values: high (clear factual conflict), medium (interpretive conflict), low (uncertain conflict). NULL for non-contradictions.';

COMMENT ON COLUMN public.statement_comparisons.severity_reasoning IS
'Story 5-4: Brief explanation of why this severity was assigned. Helps attorneys understand the scoring rationale.';

COMMENT ON COLUMN public.statement_comparisons.explanation IS
'Story 5-4: Attorney-ready natural language explanation of the contradiction with document references. Used for UI display and export.';
