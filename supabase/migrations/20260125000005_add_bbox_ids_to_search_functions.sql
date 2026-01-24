-- Migration: Add bbox_ids to search functions for source highlighting
-- Date: 2026-01-25
-- Purpose: Enable RAG/Search to return bbox_ids so UI can highlight exact source location
-- Note: Must DROP functions first because return type is changing

-- =============================================================================
-- Drop existing functions (return type is changing)
-- =============================================================================

DROP FUNCTION IF EXISTS public.semantic_search_chunks(vector(1536), uuid, integer);
DROP FUNCTION IF EXISTS public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer);
DROP FUNCTION IF EXISTS public.bm25_search_chunks(text, uuid, integer);

-- =============================================================================
-- Recreate semantic search function with bbox_ids
-- =============================================================================

CREATE FUNCTION public.semantic_search_chunks(
  query_embedding vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 30
)
RETURNS TABLE (
  id uuid,
  matter_id uuid,
  document_id uuid,
  content text,
  page_number integer,
  chunk_type text,
  token_count integer,
  bbox_ids uuid[],
  similarity float,
  row_num integer
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
  -- CRITICAL: matter_id filter is REQUIRED for security
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  -- Verify user has access to this matter (defense in depth)
  -- Skip check if auth.uid() is NULL (service role - backend handles auth)
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied to matter %', filter_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    c.id,
    c.matter_id,
    c.document_id,
    c.content,
    c.page_number,
    c.chunk_type,
    c.token_count,
    c.bbox_ids,
    (1 - (c.embedding <=> query_embedding))::float AS similarity,
    ROW_NUMBER() OVER (
      ORDER BY c.embedding <=> query_embedding
    )::integer AS row_num
  FROM public.chunks c
  WHERE c.matter_id = filter_matter_id
    AND c.embedding IS NOT NULL
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- Recreate hybrid search function with bbox_ids
-- =============================================================================

CREATE FUNCTION public.hybrid_search_chunks(
  query_text text,
  query_embedding vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 30,
  full_text_weight float DEFAULT 1.0,
  semantic_weight float DEFAULT 1.0,
  rrf_k integer DEFAULT 60
)
RETURNS TABLE (
  id uuid,
  matter_id uuid,
  document_id uuid,
  content text,
  page_number integer,
  chunk_type text,
  token_count integer,
  bbox_ids uuid[],
  bm25_rank integer,
  semantic_rank integer,
  rrf_score float
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
  -- CRITICAL: matter_id filter is REQUIRED for security
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  -- Verify user has access to this matter (defense in depth)
  -- Skip check if auth.uid() is NULL (service role - backend handles auth)
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied to matter %', filter_matter_id;
  END IF;

  RETURN QUERY
  WITH bm25_results AS (
    SELECT
      c.id,
      c.matter_id,
      c.document_id,
      c.content,
      c.page_number,
      c.chunk_type,
      c.token_count,
      c.bbox_ids,
      ROW_NUMBER() OVER (
        ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', query_text)) DESC
      )::integer AS bm25_rank
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.fts @@ plainto_tsquery('simple', query_text)
    LIMIT match_count * 2
  ),
  semantic_results AS (
    SELECT
      c.id,
      c.bbox_ids AS sem_bbox_ids,
      ROW_NUMBER() OVER (
        ORDER BY c.embedding <=> query_embedding
      )::integer AS semantic_rank
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.embedding IS NOT NULL
    LIMIT match_count * 2
  ),
  combined AS (
    SELECT
      COALESCE(b.id, s_chunk.id) AS id,
      COALESCE(b.matter_id, s_chunk.matter_id) AS matter_id,
      COALESCE(b.document_id, s_chunk.document_id) AS document_id,
      COALESCE(b.content, s_chunk.content) AS content,
      COALESCE(b.page_number, s_chunk.page_number) AS page_number,
      COALESCE(b.chunk_type, s_chunk.chunk_type) AS chunk_type,
      COALESCE(b.token_count, s_chunk.token_count) AS token_count,
      COALESCE(b.bbox_ids, s.sem_bbox_ids) AS bbox_ids,
      b.bm25_rank,
      s.semantic_rank,
      (
        COALESCE(full_text_weight / (rrf_k + b.bm25_rank), 0.0) +
        COALESCE(semantic_weight / (rrf_k + s.semantic_rank), 0.0)
      )::float AS rrf_score
    FROM bm25_results b
    FULL OUTER JOIN semantic_results s ON b.id = s.id
    LEFT JOIN public.chunks s_chunk ON s.id = s_chunk.id
  )
  SELECT
    combined.id,
    combined.matter_id,
    combined.document_id,
    combined.content,
    combined.page_number,
    combined.chunk_type,
    combined.token_count,
    combined.bbox_ids,
    combined.bm25_rank,
    combined.semantic_rank,
    combined.rrf_score
  FROM combined
  WHERE combined.id IS NOT NULL
  ORDER BY combined.rrf_score DESC
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- Recreate BM25 search function with bbox_ids
-- =============================================================================

CREATE FUNCTION public.bm25_search_chunks(
  query_text text,
  filter_matter_id uuid,
  match_count integer DEFAULT 30
)
RETURNS TABLE (
  id uuid,
  matter_id uuid,
  document_id uuid,
  content text,
  page_number integer,
  chunk_type text,
  token_count integer,
  bbox_ids uuid[],
  rank float,
  row_num integer
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
  -- CRITICAL: matter_id filter is REQUIRED for security
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  -- Verify user has access to this matter (defense in depth)
  -- Skip check if auth.uid() is NULL (service role - backend handles auth)
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied to matter %', filter_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    c.id,
    c.matter_id,
    c.document_id,
    c.content,
    c.page_number,
    c.chunk_type,
    c.token_count,
    c.bbox_ids,
    ts_rank_cd(c.fts, plainto_tsquery('simple', query_text))::float AS rank,
    ROW_NUMBER() OVER (
      ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', query_text)) DESC
    )::integer AS row_num
  FROM public.chunks c
  WHERE c.matter_id = filter_matter_id
    AND c.fts @@ plainto_tsquery('simple', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- Re-grant execute permissions
-- =============================================================================

GRANT EXECUTE ON FUNCTION public.bm25_search_chunks TO authenticated;
GRANT EXECUTE ON FUNCTION public.bm25_search_chunks TO service_role;
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks TO authenticated;
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks TO service_role;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks TO service_role;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON FUNCTION public.bm25_search_chunks IS
  'BM25 keyword search with matter isolation. Returns bbox_ids for source highlighting.';
COMMENT ON FUNCTION public.semantic_search_chunks IS
  'Semantic vector search with matter isolation. Returns bbox_ids for source highlighting.';
COMMENT ON FUNCTION public.hybrid_search_chunks IS
  'Hybrid RRF search combining BM25 and semantic. Returns bbox_ids for source highlighting.';
