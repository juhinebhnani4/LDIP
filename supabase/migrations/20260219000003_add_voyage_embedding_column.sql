-- Phase 2: Add Voyage AI embedding column for A/B testing
-- Adds embedding_voyage vector(1024) column alongside existing OpenAI embedding vector(1536)
-- Existing embedding column is UNTOUCHED — Voyage column is added alongside

-- =============================================================================
-- STEP 1: Add Voyage embedding column to chunks table
-- =============================================================================

ALTER TABLE public.chunks
ADD COLUMN IF NOT EXISTS embedding_voyage extensions.vector(1024);

COMMENT ON COLUMN public.chunks.embedding_voyage IS
  'Voyage AI voyage-law-2 embedding (1024 dims) for A/B testing. Added alongside OpenAI embedding.';

-- =============================================================================
-- STEP 2: Create HNSW index for Voyage embeddings
-- =============================================================================

-- NOTE: Not using CONCURRENTLY because migrations run inside a transaction.
-- Column is initially all NULL, so index creation is near-instant.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_voyage
  ON public.chunks
  USING hnsw (embedding_voyage extensions.vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- STEP 3: Create Voyage-specific semantic search function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.semantic_search_chunks_voyage(
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
-- STEP 4: Create Voyage-specific hybrid search function
-- =============================================================================

CREATE OR REPLACE FUNCTION public.hybrid_search_chunks_voyage(
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
  bbox_ids uuid[]
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
    COALESCE(bm25.bbox_ids, sem.bbox_ids) AS bbox_ids
  FROM bm25_results bm25
  FULL OUTER JOIN semantic_results sem ON bm25.id = sem.id
  ORDER BY rrf_score DESC
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- STEP 5: Create Voyage-specific library search function
-- =============================================================================

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
-- STEP 6: Add Voyage column to library_chunks too
-- =============================================================================

ALTER TABLE public.library_chunks
ADD COLUMN IF NOT EXISTS embedding_voyage extensions.vector(1024);

CREATE INDEX IF NOT EXISTS idx_library_chunks_embedding_voyage
  ON public.library_chunks
  USING hnsw (embedding_voyage extensions.vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- STEP 7: Grant permissions
-- =============================================================================

GRANT EXECUTE ON FUNCTION public.semantic_search_chunks_voyage(vector(1024), uuid, float, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks_voyage(vector(1024), uuid, float, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.match_library_chunks_for_matter_voyage(vector(1024), uuid, integer, float) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_library_chunks_for_matter_voyage(vector(1024), uuid, integer, float) TO service_role;

COMMENT ON FUNCTION public.semantic_search_chunks_voyage IS
  'Semantic search using Voyage law-2 embeddings (1024 dims) for A/B testing';
COMMENT ON FUNCTION public.hybrid_search_chunks_voyage IS
  'Hybrid BM25+semantic search using Voyage law-2 embeddings for A/B testing';
COMMENT ON FUNCTION public.match_library_chunks_for_matter_voyage IS
  'Library chunk search using Voyage law-2 embeddings for A/B testing';
