-- Migration: Add Full-Text Search and Hybrid Search for RAG Pipeline
-- Story 2b-6: Implement Hybrid Search with RRF Fusion
--
-- This migration adds:
-- 1. tsvector column with GIN index for BM25-style keyword search
-- 2. BM25 search function for keyword matching
-- 3. Hybrid search function combining BM25 + pgvector with RRF fusion
--
-- CRITICAL: All search functions enforce 4-layer matter isolation

-- =============================================================================
-- STEP 1: Add tsvector column to chunks table
-- =============================================================================

-- Add generated tsvector column for full-text search
ALTER TABLE public.chunks
ADD COLUMN IF NOT EXISTS fts tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Create GIN index for efficient full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON public.chunks USING GIN (fts);

COMMENT ON COLUMN public.chunks.fts IS 'Full-text search vector - auto-generated from content';

-- =============================================================================
-- STEP 2: Create BM25 Search Function (Keyword Search)
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
  IF NOT EXISTS (
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
    ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text))::float AS rank,
    ROW_NUMBER() OVER (
      ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC
    )::integer AS row_num
  FROM public.chunks c
  WHERE c.matter_id = filter_matter_id
    AND c.fts @@ websearch_to_tsquery('english', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION public.bm25_search_chunks IS
  'BM25-style keyword search with MANDATORY matter isolation - uses ts_rank_cd for cover density ranking';

-- =============================================================================
-- STEP 3: Create Semantic Search Function (Enhanced version)
-- =============================================================================

-- This enhances the existing match_chunks function with row numbering for RRF
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
  IF NOT EXISTS (
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

COMMENT ON FUNCTION public.semantic_search_chunks IS
  'Semantic similarity search with MANDATORY matter isolation - returns cosine similarity with row numbers';

-- =============================================================================
-- STEP 4: Create Hybrid Search Function with RRF Fusion
-- =============================================================================

CREATE OR REPLACE FUNCTION public.hybrid_search_chunks(
  query_text text,
  query_embedding vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 20,
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
  -- CRITICAL: matter_id is REQUIRED
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  -- Verify user access (defense in depth)
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id AND ma.user_id = auth.uid()
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
        ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC
      ) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.fts @@ websearch_to_tsquery('english', query_text)
    LIMIT LEAST(match_count, 30) * 2
  ),
  semantic_results AS (
    SELECT
      c.id,
      c.matter_id,
      c.document_id,
      c.content,
      c.page_number,
      c.chunk_type,
      c.token_count,
      ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT LEAST(match_count, 30) * 2
  )
  SELECT
    COALESCE(bm25.id, sem.id) AS id,
    COALESCE(bm25.matter_id, sem.matter_id) AS matter_id,
    COALESCE(bm25.document_id, sem.document_id) AS document_id,
    COALESCE(bm25.content, sem.content) AS content,
    COALESCE(bm25.page_number, sem.page_number) AS page_number,
    COALESCE(bm25.chunk_type, sem.chunk_type) AS chunk_type,
    COALESCE(bm25.token_count, sem.token_count) AS token_count,
    bm25.rn::integer AS bm25_rank,
    sem.rn::integer AS semantic_rank,
    (
      COALESCE(1.0 / (rrf_k + bm25.rn), 0.0) * full_text_weight +
      COALESCE(1.0 / (rrf_k + sem.rn), 0.0) * semantic_weight
    )::float AS rrf_score
  FROM bm25_results bm25
  FULL OUTER JOIN semantic_results sem ON bm25.id = sem.id
  ORDER BY rrf_score DESC
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION public.hybrid_search_chunks IS
  'Hybrid BM25+semantic search with RRF fusion - MANDATORY matter isolation. Returns top N candidates for reranking.';

-- =============================================================================
-- STEP 5: Grant execute permissions
-- =============================================================================

GRANT EXECUTE ON FUNCTION public.bm25_search_chunks TO authenticated;
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks TO authenticated;
