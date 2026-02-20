-- Migration: Add parent_chunk_id to search function results
-- Date: 2026-02-20
-- Purpose: Gap 1 - Parent-Child Context Expansion
--
-- Enables "retrieve child, generate from parent" pattern:
-- Child chunks are retrieval-optimized (narrow match for BM25/semantic)
-- Parent chunks are generation-optimized (1500-2000 tokens of context)
--
-- After reranking picks the best child chunks, the adapter fetches
-- parent content and sends it to the LLM for richer, more accurate answers.
--
-- All three search functions (hybrid, hybrid_voyage, bm25) are updated
-- to return parent_chunk_id so the Python layer can batch-fetch parents.
--
-- BACKWARD COMPATIBLE: parent_chunk_id is appended to RETURNS TABLE.
-- Existing Python code that doesn't use it simply ignores the extra column.

-- =============================================================================
-- STEP 1: Drop existing functions (return type is changing)
-- =============================================================================

-- hybrid_search_chunks: last created in 20260127000002 with model_version param
DROP FUNCTION IF EXISTS public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text);

-- hybrid_search_chunks_voyage: last created in 20260219000003
DROP FUNCTION IF EXISTS public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer);

-- bm25_search_chunks: last created in 20260125000005
DROP FUNCTION IF EXISTS public.bm25_search_chunks(text, uuid, integer);

-- =============================================================================
-- STEP 2: Recreate hybrid_search_chunks with parent_chunk_id
-- =============================================================================

CREATE FUNCTION public.hybrid_search_chunks(
  query_text text,
  query_embedding extensions.vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 20,
  full_text_weight float DEFAULT 1.0,
  semantic_weight float DEFAULT 1.0,
  rrf_k integer DEFAULT 60,
  filter_model_version TEXT DEFAULT 'text-embedding-3-small'
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
  rrf_score float,
  bbox_ids uuid[],
  parent_chunk_id uuid
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
  -- CRITICAL: matter_id is REQUIRED
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  -- Verify user access (defense in depth)
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
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
      c.bbox_ids,
      c.parent_chunk_id,
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
      c.bbox_ids,
      c.parent_chunk_id,
      ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.embedding IS NOT NULL
      AND c.embedding_model_version = filter_model_version
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
    )::float AS rrf_score,
    COALESCE(bm25.bbox_ids, sem.bbox_ids) AS bbox_ids,
    COALESCE(bm25.parent_chunk_id, sem.parent_chunk_id) AS parent_chunk_id
  FROM bm25_results bm25
  FULL OUTER JOIN semantic_results sem ON bm25.id = sem.id
  ORDER BY rrf_score DESC
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 3: Recreate hybrid_search_chunks_voyage with parent_chunk_id
-- =============================================================================

CREATE FUNCTION public.hybrid_search_chunks_voyage(
  query_text text,
  query_embedding extensions.vector(1024),
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
  rrf_score float,
  bbox_ids uuid[],
  parent_chunk_id uuid
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  IF auth.uid() IS NOT NULL AND NOT EXISTS (
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
      c.bbox_ids,
      c.parent_chunk_id,
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
      c.bbox_ids,
      c.parent_chunk_id,
      ROW_NUMBER() OVER (ORDER BY c.embedding_voyage <=> query_embedding) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.embedding_voyage IS NOT NULL
    ORDER BY c.embedding_voyage <=> query_embedding
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
    )::float AS rrf_score,
    COALESCE(bm25.bbox_ids, sem.bbox_ids) AS bbox_ids,
    COALESCE(bm25.parent_chunk_id, sem.parent_chunk_id) AS parent_chunk_id
  FROM bm25_results bm25
  FULL OUTER JOIN semantic_results sem ON bm25.id = sem.id
  ORDER BY rrf_score DESC
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 4: Recreate bm25_search_chunks with parent_chunk_id
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
  parent_chunk_id uuid,
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
    c.parent_chunk_id,
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
-- STEP 5: Grant permissions
-- =============================================================================

GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.bm25_search_chunks(text, uuid, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.bm25_search_chunks(text, uuid, integer) TO service_role;

-- =============================================================================
-- STEP 6: Comments
-- =============================================================================

COMMENT ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) IS
  'Hybrid BM25+semantic search with parent_chunk_id for context expansion (Gap 1). Returns bbox_ids for source highlighting.';
COMMENT ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) IS
  'Hybrid BM25+semantic search using Voyage embeddings with parent_chunk_id for context expansion (Gap 1).';
COMMENT ON FUNCTION public.bm25_search_chunks(text, uuid, integer) IS
  'BM25 keyword search with parent_chunk_id for context expansion (Gap 1). Returns bbox_ids for source highlighting.';
