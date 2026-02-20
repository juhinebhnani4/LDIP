-- Migration: Add metadata filtering parameters to all search RPC functions
-- Date: 2026-02-20
-- Gap 4: Metadata Filtering at Search Time
--
-- PURPOSE: Allow users to scope search by document IDs, document types,
-- and page ranges. Needed for matters with 50+ documents where users want
-- to search within specific documents or page ranges.
--
-- DESIGN:
--   - All filter parameters use DEFAULT NULL for full backward compatibility
--   - Existing callers that don't pass filters get the exact same behavior
--   - Filters are applied in BOTH CTEs (BM25 and semantic) for consistency
--   - IS NULL OR pattern lets the query planner skip filters when not set
--   - Document type filter joins to documents table via primary key (fast)
--   - Page range filter uses indexed chunks.page_number column
--
-- AFFECTED FUNCTIONS (all 3):
--   1. hybrid_search_chunks       (OpenAI embeddings, 1536-dim)
--   2. hybrid_search_chunks_voyage (Voyage embeddings, 1024-dim)
--   3. bm25_search_chunks         (keyword-only fallback)
--
-- BACKWARD COMPATIBILITY:
--   - Function signatures change (new params appended with defaults)
--   - Must DROP old signatures first, then CREATE new ones
--   - All existing callers continue working unchanged (defaults = no filter)

-- =============================================================================
-- STEP 1: Drop existing functions (signature change requires DROP + CREATE)
-- =============================================================================

-- hybrid_search_chunks: last created in 20260220100001 (Gap 3)
DROP FUNCTION IF EXISTS public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text);

-- hybrid_search_chunks_voyage: last created in 20260220100001 (Gap 3)
DROP FUNCTION IF EXISTS public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer);

-- bm25_search_chunks: last created in 20260220000002 (Gap 1)
DROP FUNCTION IF EXISTS public.bm25_search_chunks(text, uuid, integer);

-- =============================================================================
-- STEP 2: Recreate hybrid_search_chunks with metadata filter params
-- =============================================================================

CREATE FUNCTION public.hybrid_search_chunks(
  query_text text,
  query_embedding extensions.vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 20,
  full_text_weight float DEFAULT 1.0,
  semantic_weight float DEFAULT 1.0,
  rrf_k integer DEFAULT 60,
  filter_model_version TEXT DEFAULT 'text-embedding-3-small',
  -- Gap 4: Metadata filter params (all NULL = no filter)
  filter_document_ids uuid[] DEFAULT NULL,
  filter_document_types text[] DEFAULT NULL,
  filter_page_min integer DEFAULT NULL,
  filter_page_max integer DEFAULT NULL
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
        -- IMPORTANT: Must use 'simple' to match chunks.fts generated column config.
        ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', query_text)) DESC
      ) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      -- IMPORTANT: 'simple' config for multilingual support (Hindi, Gujarati, English).
      AND c.fts @@ plainto_tsquery('simple', query_text)
      -- Gap 4: Metadata filters (IS NULL = skip filter)
      AND (filter_document_ids IS NULL OR c.document_id = ANY(filter_document_ids))
      AND (filter_document_types IS NULL OR c.document_id IN (
        SELECT d.id FROM public.documents d
        WHERE d.id = c.document_id AND d.document_type = ANY(filter_document_types)
      ))
      AND (filter_page_min IS NULL OR c.page_number >= filter_page_min)
      AND (filter_page_max IS NULL OR c.page_number <= filter_page_max)
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
      -- Gap 4: Same metadata filters applied to semantic results
      AND (filter_document_ids IS NULL OR c.document_id = ANY(filter_document_ids))
      AND (filter_document_types IS NULL OR c.document_id IN (
        SELECT d.id FROM public.documents d
        WHERE d.id = c.document_id AND d.document_type = ANY(filter_document_types)
      ))
      AND (filter_page_min IS NULL OR c.page_number >= filter_page_min)
      AND (filter_page_max IS NULL OR c.page_number <= filter_page_max)
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
-- STEP 3: Recreate hybrid_search_chunks_voyage with metadata filter params
-- =============================================================================

CREATE FUNCTION public.hybrid_search_chunks_voyage(
  query_text text,
  query_embedding extensions.vector(1024),
  filter_matter_id uuid,
  match_count integer DEFAULT 20,
  full_text_weight float DEFAULT 1.0,
  semantic_weight float DEFAULT 1.0,
  rrf_k integer DEFAULT 60,
  -- Gap 4: Metadata filter params (all NULL = no filter)
  filter_document_ids uuid[] DEFAULT NULL,
  filter_document_types text[] DEFAULT NULL,
  filter_page_min integer DEFAULT NULL,
  filter_page_max integer DEFAULT NULL
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
        -- IMPORTANT: Must use 'simple' to match chunks.fts generated column config.
        ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', query_text)) DESC
      ) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      -- IMPORTANT: 'simple' config for multilingual support (Hindi, Gujarati, English).
      AND c.fts @@ plainto_tsquery('simple', query_text)
      -- Gap 4: Metadata filters
      AND (filter_document_ids IS NULL OR c.document_id = ANY(filter_document_ids))
      AND (filter_document_types IS NULL OR c.document_id IN (
        SELECT d.id FROM public.documents d
        WHERE d.id = c.document_id AND d.document_type = ANY(filter_document_types)
      ))
      AND (filter_page_min IS NULL OR c.page_number >= filter_page_min)
      AND (filter_page_max IS NULL OR c.page_number <= filter_page_max)
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
      -- Gap 4: Same metadata filters
      AND (filter_document_ids IS NULL OR c.document_id = ANY(filter_document_ids))
      AND (filter_document_types IS NULL OR c.document_id IN (
        SELECT d.id FROM public.documents d
        WHERE d.id = c.document_id AND d.document_type = ANY(filter_document_types)
      ))
      AND (filter_page_min IS NULL OR c.page_number >= filter_page_min)
      AND (filter_page_max IS NULL OR c.page_number <= filter_page_max)
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
-- STEP 4: Recreate bm25_search_chunks with metadata filter params
-- =============================================================================

CREATE FUNCTION public.bm25_search_chunks(
  query_text text,
  filter_matter_id uuid,
  match_count integer DEFAULT 30,
  -- Gap 4: Metadata filter params (all NULL = no filter)
  filter_document_ids uuid[] DEFAULT NULL,
  filter_document_types text[] DEFAULT NULL,
  filter_page_min integer DEFAULT NULL,
  filter_page_max integer DEFAULT NULL
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
    -- IMPORTANT: Must use 'simple' to match chunks.fts generated column config.
    ts_rank_cd(c.fts, plainto_tsquery('simple', query_text))::float AS rank,
    ROW_NUMBER() OVER (
      ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', query_text)) DESC
    )::integer AS row_num
  FROM public.chunks c
  WHERE c.matter_id = filter_matter_id
    AND c.fts @@ plainto_tsquery('simple', query_text)
    -- Gap 4: Metadata filters
    AND (filter_document_ids IS NULL OR c.document_id = ANY(filter_document_ids))
    AND (filter_document_types IS NULL OR c.document_id IN (
      SELECT d.id FROM public.documents d
      WHERE d.id = c.document_id AND d.document_type = ANY(filter_document_types)
    ))
    AND (filter_page_min IS NULL OR c.page_number >= filter_page_min)
    AND (filter_page_max IS NULL OR c.page_number <= filter_page_max)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 5: Grant permissions on all recreated functions
-- =============================================================================

-- hybrid_search_chunks (new signature with 12 params)
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text, uuid[], text[], integer, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text, uuid[], text[], integer, integer) TO service_role;

-- hybrid_search_chunks_voyage (new signature with 11 params)
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer, uuid[], text[], integer, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer, uuid[], text[], integer, integer) TO service_role;

-- bm25_search_chunks (new signature with 7 params)
GRANT EXECUTE ON FUNCTION public.bm25_search_chunks(text, uuid, integer, uuid[], text[], integer, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.bm25_search_chunks(text, uuid, integer, uuid[], text[], integer, integer) TO service_role;

-- =============================================================================
-- STEP 6: Comments
-- =============================================================================

COMMENT ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text, uuid[], text[], integer, integer) IS
  'Hybrid BM25+semantic search with parent_chunk_id and metadata filters (Gap 4). Uses simple config for multilingual support.';
COMMENT ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer, uuid[], text[], integer, integer) IS
  'Hybrid BM25+semantic search (Voyage embeddings) with parent_chunk_id and metadata filters (Gap 4). Uses simple config for multilingual support.';
COMMENT ON FUNCTION public.bm25_search_chunks(text, uuid, integer, uuid[], text[], integer, integer) IS
  'BM25-only keyword search with parent_chunk_id and metadata filters (Gap 4). Uses simple config for multilingual support.';
