-- Story 1.3: Store Embedding Model Version with Vectors
-- Adds embedding_model_version column to chunks table for version tracking

-- Add embedding_model_version column to chunks table
ALTER TABLE chunks
ADD COLUMN IF NOT EXISTS embedding_model_version TEXT DEFAULT 'text-embedding-3-small';

-- Add index for filtering by embedding model version
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_model_version
ON chunks (embedding_model_version)
WHERE embedding IS NOT NULL;

-- Add composite index for searching within a model version
CREATE INDEX IF NOT EXISTS idx_chunks_matter_model_version
ON chunks (matter_id, embedding_model_version)
WHERE embedding IS NOT NULL;

-- Comment on column for documentation
COMMENT ON COLUMN chunks.embedding_model_version IS 'OpenAI embedding model version used (Story 1.3). Default: text-embedding-3-small';

-- =============================================================================
-- Drop existing functions (signatures are changing)
-- =============================================================================
DROP FUNCTION IF EXISTS public.semantic_search_chunks(vector(1536), uuid, integer);
DROP FUNCTION IF EXISTS public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer);

-- =============================================================================
-- Recreate semantic_search_chunks with model version filter
-- =============================================================================
CREATE FUNCTION public.semantic_search_chunks(
    query_embedding extensions.vector(1536),
    filter_matter_id UUID,
    similarity_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10,
    filter_model_version TEXT DEFAULT 'text-embedding-3-small'
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
    -- CRITICAL: matter_id is REQUIRED for security
    IF filter_matter_id IS NULL THEN
        RAISE EXCEPTION 'filter_matter_id is required - security violation';
    END IF;

    -- Verify user access (defense in depth)
    -- Skip check if auth.uid() is NULL (service role - backend handles auth)
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
        (1 - (c.embedding <=> query_embedding))::float AS similarity
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.embedding IS NOT NULL
      AND c.embedding_model_version = filter_model_version
      AND 1 - (c.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- Recreate hybrid_search_chunks with model version filter
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
  bbox_ids uuid[]
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
  -- Skip check if auth.uid() is NULL (service role - backend handles auth)
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
    COALESCE(bm25.bbox_ids, sem.bbox_ids) AS bbox_ids
  FROM bm25_results bm25
  FULL OUTER JOIN semantic_results sem ON bm25.id = sem.id
  ORDER BY rrf_score DESC
  LIMIT match_count;
END;
$$;

-- =============================================================================
-- Grant permissions
-- =============================================================================
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks(vector(1536), uuid, float, integer, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.semantic_search_chunks(vector(1536), uuid, float, integer, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) TO service_role;

-- =============================================================================
-- Comments (with full signatures to avoid ambiguity)
-- =============================================================================
COMMENT ON FUNCTION public.semantic_search_chunks(vector(1536), uuid, float, integer, text) IS
  'Semantic search with embedding model version filtering (Story 1.3). Returns bbox_ids for source highlighting.';
COMMENT ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) IS
  'Hybrid BM25+semantic search with embedding model version filtering (Story 1.3). Returns bbox_ids for source highlighting.';
