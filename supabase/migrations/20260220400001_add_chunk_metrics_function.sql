-- Migration: Add chunk metrics monitoring function
-- Date: 2026-02-20
-- Gap 7: Vector Quantization — Monitoring
--
-- PURPOSE: Provide admin-accessible chunk count metrics per matter and globally.
-- Thresholds (50K per-matter, 500K global) are applied in Python (monitoring.py),
-- not in SQL, to maintain a single source of truth.
--
-- Excludes chunks from soft-deleted documents (d.deleted_at IS NULL).
--
-- At current scale (10K-100K chunks), full float32 vectors are optimal for
-- legal domain precision. This function enables proactive monitoring so we
-- know when to revisit quantization.
--
-- USAGE: Called by GET /api/admin/chunk-metrics (admin-only endpoint)

-- =============================================================================
-- STEP 1: Create get_chunk_metrics() RPC function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_chunk_metrics()
RETURNS TABLE (
  matter_id uuid,
  matter_title text,
  total_chunks bigint,
  parent_chunks bigint,
  child_chunks bigint,
  table_chunks bigint,
  has_voyage_embeddings bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  -- Join through documents to exclude chunks from soft-deleted documents.
  -- Threshold comparison is done in Python (single source of truth).
  SELECT
    m.id AS matter_id,
    m.title AS matter_title,
    COUNT(c.id)::bigint AS total_chunks,
    COUNT(c.id) FILTER (WHERE c.chunk_type = 'parent')::bigint AS parent_chunks,
    COUNT(c.id) FILTER (WHERE c.chunk_type = 'child')::bigint AS child_chunks,
    COUNT(c.id) FILTER (WHERE c.chunk_type = 'table')::bigint AS table_chunks,
    COUNT(c.id) FILTER (WHERE c.embedding_voyage IS NOT NULL)::bigint AS has_voyage_embeddings
  FROM public.matters m
  LEFT JOIN (
    public.chunks c
    JOIN public.documents d ON d.id = c.document_id AND d.deleted_at IS NULL
  ) ON c.matter_id = m.id
  WHERE m.deleted_at IS NULL
  GROUP BY m.id, m.title
  ORDER BY COUNT(c.id) DESC;
$$;

-- =============================================================================
-- STEP 2: Create get_global_chunk_count() RPC function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_global_chunk_count()
RETURNS TABLE (
  total_chunks bigint,
  total_with_embedding bigint,
  total_with_voyage bigint,
  total_matters bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  -- Exclude chunks from soft-deleted documents.
  -- Threshold comparison is done in Python (single source of truth).
  SELECT
    COUNT(c.id)::bigint AS total_chunks,
    COUNT(c.id) FILTER (WHERE c.embedding IS NOT NULL)::bigint AS total_with_embedding,
    COUNT(c.id) FILTER (WHERE c.embedding_voyage IS NOT NULL)::bigint AS total_with_voyage,
    (SELECT COUNT(DISTINCT c2.matter_id)
     FROM public.chunks c2
     JOIN public.documents d2 ON d2.id = c2.document_id AND d2.deleted_at IS NULL
    )::bigint AS total_matters
  FROM public.chunks c
  JOIN public.documents d ON d.id = c.document_id
  WHERE d.deleted_at IS NULL;
$$;

-- =============================================================================
-- STEP 3: Grant permissions (admin access enforced at API layer)
-- =============================================================================

GRANT EXECUTE ON FUNCTION public.get_chunk_metrics() TO service_role;
GRANT EXECUTE ON FUNCTION public.get_global_chunk_count() TO service_role;

-- =============================================================================
-- STEP 4: Comments
-- =============================================================================

COMMENT ON FUNCTION public.get_chunk_metrics() IS
  'Gap 7: Per-matter chunk count metrics for vector quantization monitoring. Excludes soft-deleted documents. Thresholds applied in Python.';
COMMENT ON FUNCTION public.get_global_chunk_count() IS
  'Gap 7: Global chunk count metrics for vector quantization monitoring. Excludes soft-deleted documents. Thresholds applied in Python.';
