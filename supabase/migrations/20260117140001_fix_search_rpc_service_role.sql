-- Fix search RPC functions to work with service role key
--
-- Problem: The search functions check auth.uid() for access control, but when
-- the backend uses service role key, auth.uid() returns NULL, causing access denied.
--
-- Solution: The backend already validates matter access via require_matter_role
-- dependency BEFORE calling these RPCs. We can trust the caller when service role
-- is used (auth.uid() IS NULL means service role, which bypasses RLS anyway).
--
-- Security: This is safe because:
-- 1. Service role is only used by the backend
-- 2. Backend validates access via FastAPI dependencies before calling RPCs
-- 3. The matter_id filter is still REQUIRED and enforced

-- =============================================================================
-- Update BM25 search function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.bm25_search_chunks(
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
  rank float,
  row_num integer
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
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
-- Update semantic search function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.semantic_search_chunks(
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
  similarity float,
  row_num integer
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
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
-- Update hybrid search function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.hybrid_search_chunks(
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
  bm25_rank integer,
  semantic_rank integer,
  rrf_score float
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
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
-- Grant execute permissions
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
  'BM25 keyword search with matter isolation. Service role bypasses auth check (backend validates access).';
COMMENT ON FUNCTION public.semantic_search_chunks IS
  'Semantic vector search with matter isolation. Service role bypasses auth check (backend validates access).';
COMMENT ON FUNCTION public.hybrid_search_chunks IS
  'Hybrid RRF search combining BM25 and semantic. Service role bypasses auth check (backend validates access).';
