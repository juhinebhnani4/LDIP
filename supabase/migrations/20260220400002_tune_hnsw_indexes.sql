-- Migration: Tune HNSW indexes for improved recall
-- Date: 2026-02-20
-- Gap 8: HNSW Index Tuning
--
-- PURPOSE: Improve vector search recall quality by tuning HNSW parameters.
--
-- CHANGES:
--   1. Recreate all 4 HNSW indexes with ef_construction=128 (was 64)
--      - Better index quality: ~2-5% recall improvement in isolation
--      - Trade-off: ~2x slower index build time (acceptable for legal doc volumes)
--   2. Add SET LOCAL hnsw.ef_search = 80 to ALL 6 vector search functions
--      - Better query-time recall (was implicit default ~40)
--      - Trade-off: ~2x more distance computations per query (~5-10ms added)
--
-- FUNCTIONS UPDATED (6 total):
--   1. hybrid_search_chunks            — BM25+semantic (OpenAI)
--   2. hybrid_search_chunks_voyage     — BM25+semantic (Voyage)
--   3. semantic_search_chunks          — Semantic-only (OpenAI)
--   4. semantic_search_chunks_voyage   — Semantic-only (Voyage)
--   5. match_library_chunks_for_matter — Library search (OpenAI)
--   6. match_library_chunks_for_matter_voyage — Library search (Voyage)
--
-- RATIONALE:
--   While the architecture compensates via hybrid search + reranking,
--   improving the base HNSW quality provides a stronger foundation:
--   - Better ANN candidates -> better reranking input -> better final results
--   - ef_construction=128 is the sweet spot for legal precision at <100K vectors
--   - ef_search=80 closes the gap between HNSW ANN and exact search
--
-- INDEX INVENTORY (4 indexes):
--   1. idx_chunks_embedding          — chunks.embedding (1536-dim OpenAI)
--   2. idx_library_chunks_embedding  — library_chunks.embedding (1536-dim OpenAI)
--   3. idx_chunks_embedding_voyage   — chunks.embedding_voyage (1024-dim Voyage)
--   4. idx_library_chunks_embedding_voyage — library_chunks.embedding_voyage (1024-dim Voyage)
--
-- BACKWARD COMPATIBILITY:
--   - Index recreation is transparent to callers
--   - ef_search is SET LOCAL (transaction-scoped, no session bleed)
--   - Functions maintain same signatures, just better internal recall
--
-- ⚠ DEPLOY WARNING ⚠
-- Index DROP+CREATE runs inside a transaction. During migration:
--   - Each DROP INDEX acquires a brief AccessExclusive lock on the table
--   - Between DROP and CREATE, queries fall back to sequential scan (slower)
--   - CREATE INDEX (non-CONCURRENTLY) holds a ShareLock until complete
-- For tables <100K rows this completes in seconds. For larger tables,
-- consider running during low-traffic window. CREATE INDEX CONCURRENTLY
-- cannot be used inside a transaction block (which Supabase migrations use).

-- =============================================================================
-- STEP 1: Recreate HNSW indexes with ef_construction=128
-- =============================================================================

-- 1a. chunks.embedding (OpenAI 1536-dim)
DROP INDEX IF EXISTS public.idx_chunks_embedding;
CREATE INDEX idx_chunks_embedding ON public.chunks
  USING hnsw (embedding extensions.vector_cosine_ops)
  WITH (m = 16, ef_construction = 128);

-- 1b. library_chunks.embedding (OpenAI 1536-dim)
DROP INDEX IF EXISTS public.idx_library_chunks_embedding;
CREATE INDEX idx_library_chunks_embedding ON public.library_chunks
  USING hnsw (embedding extensions.vector_cosine_ops)
  WITH (m = 16, ef_construction = 128);

-- 1c. chunks.embedding_voyage (Voyage 1024-dim)
DROP INDEX IF EXISTS public.idx_chunks_embedding_voyage;
CREATE INDEX idx_chunks_embedding_voyage ON public.chunks
  USING hnsw (embedding_voyage extensions.vector_cosine_ops)
  WITH (m = 16, ef_construction = 128);

-- 1d. library_chunks.embedding_voyage (Voyage 1024-dim)
DROP INDEX IF EXISTS public.idx_library_chunks_embedding_voyage;
CREATE INDEX idx_library_chunks_embedding_voyage ON public.library_chunks
  USING hnsw (embedding_voyage extensions.vector_cosine_ops)
  WITH (m = 16, ef_construction = 128);

-- =============================================================================
-- STEP 2: Recreate hybrid_search_chunks with ef_search=80
-- =============================================================================

-- Must drop first (signature unchanged, but function body changes)
DROP FUNCTION IF EXISTS public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text, uuid[], text[], integer, integer);

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
  -- Gap 8: Improve HNSW query-time recall (default ~40 -> 80)
  SET LOCAL hnsw.ef_search = 80;

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
-- STEP 3: Recreate hybrid_search_chunks_voyage with ef_search=80
-- =============================================================================

DROP FUNCTION IF EXISTS public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer, uuid[], text[], integer, integer);

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
  -- Gap 8: Improve HNSW query-time recall (default ~40 -> 80)
  SET LOCAL hnsw.ef_search = 80;

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
-- STEP 4: bm25_search_chunks — no HNSW changes needed (no vector search)
-- =============================================================================

-- bm25_search_chunks does NOT need ef_search (no vector search involved)
-- It was already recreated in Gap 4 migration — no changes needed here.

-- =============================================================================
-- STEP 5: Recreate semantic_search_chunks with ef_search=80
-- =============================================================================

-- Drop existing (signature: vector(1536), uuid, integer)
DROP FUNCTION IF EXISTS public.semantic_search_chunks(vector(1536), uuid, integer);

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
  -- Gap 8: Improve HNSW query-time recall (default ~40 -> 80)
  SET LOCAL hnsw.ef_search = 80;

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
-- STEP 6: Recreate semantic_search_chunks_voyage with ef_search=80
-- =============================================================================

DROP FUNCTION IF EXISTS public.semantic_search_chunks_voyage(vector(1024), uuid, float, integer);

CREATE FUNCTION public.semantic_search_chunks_voyage(
    query_embedding extensions.vector(1024),
    filter_matter_id UUID,
    similarity_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    chunk_type TEXT,
    document_id UUID,
    page_number INT,
    bbox_ids UUID[],
    token_count INT,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
    -- Gap 8: Improve HNSW query-time recall (default ~40 -> 80)
    SET LOCAL hnsw.ef_search = 80;

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
    SELECT
        c.id,
        c.content,
        c.chunk_type,
        c.document_id,
        c.page_number,
        c.bbox_ids,
        c.token_count,
        (1 - (c.embedding_voyage <=> query_embedding))::float AS similarity
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.embedding_voyage IS NOT NULL
      AND 1 - (c.embedding_voyage <=> query_embedding) >= similarity_threshold
    ORDER BY c.embedding_voyage <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 7: Recreate match_library_chunks_for_matter with ef_search=80
-- =============================================================================

-- Uses CREATE OR REPLACE (same signature: vector(1536), uuid, integer, float)
CREATE OR REPLACE FUNCTION public.match_library_chunks_for_matter(
  query_embedding vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 10,
  similarity_threshold float DEFAULT 0.5
)
RETURNS TABLE (
  id uuid,
  library_document_id uuid,
  document_title text,
  document_type text,
  chunk_index integer,
  content text,
  page_number integer,
  section_title text,
  chunk_type text,
  similarity float
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
  -- Gap 8: Improve HNSW query-time recall (default ~40 -> 80)
  SET LOCAL hnsw.ef_search = 80;

  -- Verify matter exists (Layer 4 app auth already validated user access)
  IF NOT EXISTS (
    SELECT 1 FROM public.matters m
    WHERE m.id = filter_matter_id
  ) THEN
    RAISE EXCEPTION 'Matter not found: %', filter_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    lc.id,
    lc.library_document_id,
    ld.title AS document_title,
    ld.document_type,
    lc.chunk_index,
    lc.content,
    lc.page_number,
    lc.section_title,
    lc.chunk_type,
    1 - (lc.embedding <=> query_embedding) AS similarity
  FROM public.library_chunks lc
  JOIN public.library_documents ld ON ld.id = lc.library_document_id
  JOIN public.matter_library_links mll ON mll.library_document_id = ld.id
  WHERE mll.matter_id = filter_matter_id  -- Only linked library documents
    AND lc.embedding IS NOT NULL
    AND 1 - (lc.embedding <=> query_embedding) > similarity_threshold
    AND ld.status = 'completed'  -- Only fully processed documents
  ORDER BY lc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 8: Recreate match_library_chunks_for_matter_voyage with ef_search=80
-- =============================================================================

-- Uses CREATE OR REPLACE (same signature: vector(1024), uuid, integer, float)
CREATE OR REPLACE FUNCTION public.match_library_chunks_for_matter_voyage(
  query_embedding extensions.vector(1024),
  filter_matter_id uuid,
  match_count integer DEFAULT 10,
  similarity_threshold float DEFAULT 0.5
)
RETURNS TABLE (
  id uuid,
  content text,
  chunk_type text,
  document_id uuid,
  page_number integer,
  bbox_ids uuid[],
  token_count integer,
  similarity float,
  library_document_id uuid,
  library_document_title text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
BEGIN
  -- Gap 8: Improve HNSW query-time recall (default ~40 -> 80)
  SET LOCAL hnsw.ef_search = 80;

  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required';
  END IF;

  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied to matter %', filter_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    lc.id,
    lc.content,
    lc.chunk_type,
    lc.document_id,
    lc.page_number,
    lc.bbox_ids,
    lc.token_count,
    (1 - (lc.embedding_voyage <=> query_embedding))::float AS similarity,
    ld.id AS library_document_id,
    ld.title AS library_document_title
  FROM public.library_chunks lc
  JOIN public.library_documents ld ON lc.document_id = ld.id
  JOIN public.matter_library_links mll ON ld.id = mll.library_document_id
  WHERE mll.matter_id = filter_matter_id
    AND lc.embedding_voyage IS NOT NULL
    AND 1 - (lc.embedding_voyage <=> query_embedding) >= similarity_threshold
  ORDER BY lc.embedding_voyage <=> query_embedding
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 9: Grant permissions on ALL recreated functions
-- =============================================================================

-- hybrid_search_chunks (Gap 4 signature: 12 params)
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text, uuid[], text[], integer, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text, uuid[], text[], integer, integer) TO service_role;

-- hybrid_search_chunks_voyage (Gap 4 signature: 11 params)
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer, uuid[], text[], integer, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer, uuid[], text[], integer, integer) TO service_role;

-- semantic_search_chunks (3 params)
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks(vector(1536), uuid, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks(vector(1536), uuid, integer) TO service_role;

-- semantic_search_chunks_voyage (4 params)
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks_voyage(vector(1024), uuid, float, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks_voyage(vector(1024), uuid, float, integer) TO service_role;

-- match_library_chunks_for_matter (4 params)
GRANT EXECUTE ON FUNCTION public.match_library_chunks_for_matter(vector(1536), uuid, integer, float) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_library_chunks_for_matter(vector(1536), uuid, integer, float) TO service_role;

-- match_library_chunks_for_matter_voyage (4 params)
GRANT EXECUTE ON FUNCTION public.match_library_chunks_for_matter_voyage(vector(1024), uuid, integer, float) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_library_chunks_for_matter_voyage(vector(1024), uuid, integer, float) TO service_role;

-- =============================================================================
-- STEP 10: Comments
-- =============================================================================

COMMENT ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text, uuid[], text[], integer, integer) IS
  'Hybrid BM25+semantic search with ef_search=80 for improved HNSW recall (Gap 8). Includes parent_chunk_id, metadata filters, simple config.';
COMMENT ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer, uuid[], text[], integer, integer) IS
  'Hybrid BM25+semantic search (Voyage) with ef_search=80 for improved HNSW recall (Gap 8). Includes parent_chunk_id, metadata filters, simple config.';
COMMENT ON FUNCTION public.semantic_search_chunks(vector(1536), uuid, integer) IS
  'Semantic-only search with ef_search=80 for improved HNSW recall (Gap 8). Used for semantic fallback when BM25 has no results.';
COMMENT ON FUNCTION public.semantic_search_chunks_voyage(vector(1024), uuid, float, integer) IS
  'Semantic-only search (Voyage) with ef_search=80 for improved HNSW recall (Gap 8).';
COMMENT ON FUNCTION public.match_library_chunks_for_matter(vector(1536), uuid, integer, float) IS
  'Library chunk search with ef_search=80 for improved HNSW recall (Gap 8). Searches linked library documents for a matter.';
COMMENT ON FUNCTION public.match_library_chunks_for_matter_voyage(vector(1024), uuid, integer, float) IS
  'Library chunk search (Voyage) with ef_search=80 for improved HNSW recall (Gap 8). Searches linked library documents for a matter.';
