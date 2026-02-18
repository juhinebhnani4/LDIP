-- =============================================================================
-- Migration: Usage Stats Helpers
-- Date: 2026-02-19
-- Purpose: Add RPC for per-matter query counting (user-facing usage page)
-- =============================================================================

-- RPC: Count queries per matter (for usage summary page)
-- Returns matter_id + query_count for a list of matter IDs
CREATE OR REPLACE FUNCTION public.count_queries_per_matter(p_matter_ids UUID[])
RETURNS TABLE(matter_id UUID, query_count BIGINT)
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT
        mqh.matter_id,
        COUNT(*)::BIGINT AS query_count
    FROM public.matter_query_history mqh
    WHERE mqh.matter_id = ANY(p_matter_ids)
    GROUP BY mqh.matter_id;
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.count_queries_per_matter(UUID[]) TO authenticated;
GRANT EXECUTE ON FUNCTION public.count_queries_per_matter(UUID[]) TO service_role;
