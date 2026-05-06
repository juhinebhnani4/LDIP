-- Migration: Add schema parity columns to library_chunks (GAP-7 + GAP-8)
--
-- Closes two gaps between chunks and library_chunks:
-- GAP-7: No BM25/full-text search for library chunks
-- GAP-8: Schema divergence (missing fts, embedding_model_version, layout_derived, text offsets)
--
-- The fts column is GENERATED STORED, so existing rows are auto-backfilled.

-- =============================================================================
-- STEP 1: Add missing columns to library_chunks
-- =============================================================================

-- GAP-7: Full-text search vector (matches chunks.fts definition)
ALTER TABLE public.library_chunks
ADD COLUMN IF NOT EXISTS fts tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- GAP-8: Embedding model version tracking
ALTER TABLE public.library_chunks
ADD COLUMN IF NOT EXISTS embedding_model_version text DEFAULT 'text-embedding-3-small';

-- GAP-8: Layout quality signal
ALTER TABLE public.library_chunks
ADD COLUMN IF NOT EXISTS layout_derived boolean DEFAULT false;

-- GAP-8: Character offset columns for bbox linking
ALTER TABLE public.library_chunks
ADD COLUMN IF NOT EXISTS text_start_offset integer;

ALTER TABLE public.library_chunks
ADD COLUMN IF NOT EXISTS text_end_offset integer;

-- =============================================================================
-- STEP 2: Create indexes
-- =============================================================================

-- GIN index for full-text search (matches chunks index)
CREATE INDEX IF NOT EXISTS idx_library_chunks_fts
ON public.library_chunks USING GIN (fts);

-- Embedding model version for queries filtering by model
CREATE INDEX IF NOT EXISTS idx_library_chunks_embedding_model_version
ON public.library_chunks(embedding_model_version)
WHERE embedding IS NOT NULL;

-- =============================================================================
-- STEP 3: BM25 search function for library chunks (GAP-7)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.bm25_search_library_chunks(
  query_text text,
  filter_matter_id uuid,
  match_count integer DEFAULT 10
)
RETURNS TABLE (
  id uuid,
  library_document_id uuid,
  content text,
  page_number integer,
  section_title text,
  chunk_type text,
  token_count integer,
  rank float,
  document_title text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- matter_id is required for security (only search linked library docs)
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  RETURN QUERY
  SELECT
    lc.id,
    lc.library_document_id,
    lc.content,
    lc.page_number,
    lc.section_title,
    lc.chunk_type,
    lc.token_count,
    ts_rank_cd(lc.fts, websearch_to_tsquery('english', query_text))::float AS rank,
    ld.title AS document_title
  FROM public.library_chunks lc
  JOIN public.library_documents ld ON ld.id = lc.library_document_id
  JOIN public.matter_library_links mll ON mll.library_document_id = ld.id
  WHERE mll.matter_id = filter_matter_id
    AND lc.fts @@ websearch_to_tsquery('english', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION public.bm25_search_library_chunks IS
  'BM25 keyword search over library chunks linked to a matter - for hybrid search fallback';

-- Grant access
GRANT EXECUTE ON FUNCTION public.bm25_search_library_chunks(text, uuid, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.bm25_search_library_chunks(text, uuid, integer) TO service_role;

-- =============================================================================
-- STEP 4: Add comments
-- =============================================================================

COMMENT ON COLUMN public.library_chunks.fts IS 'Full-text search vector - auto-generated from content (GAP-7 fix)';
COMMENT ON COLUMN public.library_chunks.embedding_model_version IS 'Embedding model used - tracks model for migration (GAP-8 fix)';
COMMENT ON COLUMN public.library_chunks.layout_derived IS 'Whether chunk was derived from layout analysis vs text-based fallback (GAP-8 fix)';
COMMENT ON COLUMN public.library_chunks.text_start_offset IS 'Character start offset for bbox linking (GAP-8 fix)';
COMMENT ON COLUMN public.library_chunks.text_end_offset IS 'Character end offset for bbox linking (GAP-8 fix)';
