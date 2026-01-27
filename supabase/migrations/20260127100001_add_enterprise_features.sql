-- Migration: Add Enterprise Features Columns
--
-- Story 7.2: Monthly Cost Report by Practice Group
-- Story 7.3: Data Residency Controls
--
-- Adds:
-- 1. practice_group column to matters for cost reporting
-- 2. data_residency column to matters for regional API routing

-- =============================================================================
-- Add practice_group column to matters
-- Story 7.2: Monthly Cost Report by Practice Group
-- =============================================================================

ALTER TABLE public.matters
ADD COLUMN IF NOT EXISTS practice_group VARCHAR(100);

COMMENT ON COLUMN public.matters.practice_group
IS 'Practice group for cost reporting (e.g., Litigation, Corporate, IP). Optional field for enterprise cost analysis.';

-- Create index for practice group aggregation queries
CREATE INDEX IF NOT EXISTS idx_matters_practice_group
ON public.matters(practice_group) WHERE practice_group IS NOT NULL;

-- =============================================================================
-- Add data_residency column to matters
-- Story 7.3: Data Residency Controls
-- =============================================================================

-- Create enum type for data residency regions
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'data_residency_region') THEN
        CREATE TYPE data_residency_region AS ENUM ('default', 'us', 'eu', 'asia');
    END IF;
END
$$;

ALTER TABLE public.matters
ADD COLUMN IF NOT EXISTS data_residency data_residency_region DEFAULT 'default';

COMMENT ON COLUMN public.matters.data_residency
IS 'Data residency region for API routing. Options: default (auto), us (US region), eu (EU region), asia (Asia region). Immutable after documents are uploaded.';

-- =============================================================================
-- Create view for cost reporting by practice group
-- Story 7.2: Admin cost aggregation
-- =============================================================================

CREATE OR REPLACE VIEW public.practice_group_costs AS
SELECT
    m.practice_group,
    DATE_TRUNC('month', lc.created_at)::DATE as report_month,
    COUNT(DISTINCT m.id) as matter_count,
    COUNT(DISTINCT lc.document_id) as document_count,
    SUM(lc.total_cost_inr) as total_cost_inr,
    SUM(lc.total_cost_usd) as total_cost_usd,
    SUM(lc.input_tokens + lc.output_tokens) as total_tokens,
    COUNT(*) as operation_count
FROM public.llm_costs lc
JOIN public.matters m ON lc.matter_id = m.id
WHERE m.practice_group IS NOT NULL
  AND m.deleted_at IS NULL
GROUP BY m.practice_group, DATE_TRUNC('month', lc.created_at);

COMMENT ON VIEW public.practice_group_costs
IS 'Monthly cost aggregation by practice group for admin reporting (Story 7.2)';

-- =============================================================================
-- RPC function for monthly cost report
-- Story 7.2: Admin endpoint support
-- =============================================================================

CREATE OR REPLACE FUNCTION get_monthly_cost_report(
    p_year INTEGER,
    p_month INTEGER
)
RETURNS TABLE (
    practice_group VARCHAR,
    matter_count BIGINT,
    document_count BIGINT,
    total_cost_inr NUMERIC,
    total_cost_usd NUMERIC,
    total_tokens BIGINT,
    operation_count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_start_date DATE;
    v_end_date DATE;
BEGIN
    -- Calculate date range for the specified month
    v_start_date := make_date(p_year, p_month, 1);
    v_end_date := v_start_date + INTERVAL '1 month';

    RETURN QUERY
    SELECT
        COALESCE(m.practice_group, 'Unassigned')::VARCHAR as practice_group,
        COUNT(DISTINCT m.id) as matter_count,
        COUNT(DISTINCT lc.document_id) as document_count,
        COALESCE(SUM(lc.total_cost_inr), 0)::NUMERIC as total_cost_inr,
        COALESCE(SUM(lc.total_cost_usd), 0)::NUMERIC as total_cost_usd,
        COALESCE(SUM(lc.input_tokens + lc.output_tokens), 0)::BIGINT as total_tokens,
        COUNT(lc.*)::BIGINT as operation_count
    FROM public.matters m
    LEFT JOIN public.llm_costs lc ON m.id = lc.matter_id
        AND lc.created_at >= v_start_date
        AND lc.created_at < v_end_date
    WHERE m.deleted_at IS NULL
    GROUP BY COALESCE(m.practice_group, 'Unassigned')
    ORDER BY total_cost_inr DESC NULLS LAST;
END;
$$;

COMMENT ON FUNCTION get_monthly_cost_report
IS 'Returns monthly cost report grouped by practice group. Used by admin dashboard (Story 7.2).';
