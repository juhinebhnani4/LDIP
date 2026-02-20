-- Migration: Fix multilingual text search — 'english' → 'simple' everywhere
-- Date: 2026-02-20
-- Gap 3: Hindi/Gujarati BM25 Fix
--
-- ROOT CAUSE: The chunks.fts generated column uses to_tsvector('simple', content)
-- (fixed in migration 20260115), but later migrations recreated search functions
-- by copying old templates that still had 'english' config. This creates a
-- config mismatch: English stemming produces different lexemes ('run' vs 'running')
-- so BM25 silently loses recall on stemmed terms.
--
-- Additionally, three GIN indexes on other tables were never updated to 'simple',
-- meaning Hindi/Gujarati text in events, identity_nodes, and documents is not
-- searchable via full-text search.
--
-- IMPORTANT FOR FUTURE DEVELOPERS:
-- This project uses 'simple' text search config EVERYWHERE because:
--   1. Legal documents contain Hindi, Gujarati, and English text
--   2. 'english' config cannot tokenize Devanagari script
--   3. 'simple' tokenizes on whitespace + lowercases — works for ANY script
--   4. Stemming loss (e.g., 'running' won't match 'run') is acceptable because
--      semantic search covers stemming gaps. BM25 with 'simple' gives exact-match
--      which matters more for legal citations ("Section 138" must match exactly).
--   5. The chunks.fts stored column uses 'simple', so ALL queries against it MUST
--      also use 'simple' to avoid lexeme mismatches.
--
-- DO NOT change any text search config to 'english' without updating ALL of:
--   - chunks.fts generated column
--   - hybrid_search_chunks() function
--   - hybrid_search_chunks_voyage() function
--   - bm25_search_chunks() function
--   - idx_events_description index
--   - idx_identity_nodes_name_search index
--   - idx_documents_extracted_text index
--   - cross_engine_service.py text_search config

-- =============================================================================
-- STEP 1: Drop existing hybrid search functions (return type unchanged,
--         but CREATE OR REPLACE won't work because we need to change the body)
-- =============================================================================

-- hybrid_search_chunks: last created in 20260220000002 (Gap 1) with 'english' (BROKEN)
DROP FUNCTION IF EXISTS public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text);

-- hybrid_search_chunks_voyage: last created in 20260220000002 (Gap 1) with 'english' (BROKEN)
DROP FUNCTION IF EXISTS public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer);

-- =============================================================================
-- STEP 2: Recreate hybrid_search_chunks with 'simple' config
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
        -- IMPORTANT: Must use 'simple' to match chunks.fts generated column config.
        -- Using 'english' here causes lexeme mismatches (stemming vs no stemming).
        ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', query_text)) DESC
      ) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      -- IMPORTANT: 'simple' config for multilingual support (Hindi, Gujarati, English).
      -- Must match the config used in chunks.fts generated column.
      AND c.fts @@ plainto_tsquery('simple', query_text)
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
-- STEP 3: Recreate hybrid_search_chunks_voyage with 'simple' config
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
        -- IMPORTANT: Must use 'simple' to match chunks.fts generated column config.
        ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', query_text)) DESC
      ) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      -- IMPORTANT: 'simple' config for multilingual support (Hindi, Gujarati, English).
      AND c.fts @@ plainto_tsquery('simple', query_text)
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
-- STEP 4: Grant permissions on recreated functions
-- =============================================================================

GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) TO service_role;

-- Comments
COMMENT ON FUNCTION public.hybrid_search_chunks(text, vector(1536), uuid, integer, float, float, integer, text) IS
  'Hybrid BM25+semantic search with parent_chunk_id. Uses simple config for multilingual support (Hindi/Gujarati/English).';
COMMENT ON FUNCTION public.hybrid_search_chunks_voyage(text, vector(1024), uuid, integer, float, float, integer) IS
  'Hybrid BM25+semantic search (Voyage embeddings) with parent_chunk_id. Uses simple config for multilingual support.';

-- =============================================================================
-- STEP 5: Fix GIN indexes on events, identity_nodes, and documents tables
--
-- These indexes must use the same text search config as the queries that hit them.
-- Changing the config requires DROP + CREATE (ALTER INDEX cannot change expressions).
-- =============================================================================

-- 5a. events.description — queried by cross_engine_service.py entity journey fallback
DROP INDEX IF EXISTS idx_events_description;
CREATE INDEX idx_events_description ON public.events
  -- IMPORTANT: 'simple' for multilingual (Hindi/Gujarati) support.
  -- The Python query in cross_engine_service.py must use config='simple' to match.
  USING GIN (to_tsvector('simple', description));

-- 5b. identity_nodes.canonical_name — not queried in Python yet, but index must be
--     consistent for when it is. Entity names can be in any language.
DROP INDEX IF EXISTS idx_identity_nodes_name_search;
CREATE INDEX idx_identity_nodes_name_search ON public.identity_nodes
  USING GIN (to_tsvector('simple', canonical_name));

-- 5c. documents.extracted_text — not queried in Python yet, but the extracted text
--     from OCR'd Hindi/Gujarati documents would be unsearchable with 'english' config.
DROP INDEX IF EXISTS idx_documents_extracted_text;
CREATE INDEX idx_documents_extracted_text ON public.documents
  USING GIN (to_tsvector('simple', COALESCE(extracted_text, '')));
