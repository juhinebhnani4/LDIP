-- =============================================================================
-- Migration: Add 'table' chunk_type to chunks table
-- Gap 5: Table-Aware Embedding — connect table extraction to search pipeline
--
-- Tables extracted by Docling are stored in document_tables but were never
-- chunked, embedded, or included in search. This migration allows table
-- content to be stored as chunks with chunk_type='table', enabling them to
-- participate in hybrid search (BM25 + semantic) automatically.
--
-- Table chunks are self-contained (parent_chunk_id = NULL) and skip parent
-- context expansion in the RAG adapter.
-- =============================================================================

-- Drop the old CHECK constraint and add the new one with 'table' included
ALTER TABLE public.chunks
DROP CONSTRAINT IF EXISTS chunks_chunk_type_check;

ALTER TABLE public.chunks
ADD CONSTRAINT chunks_chunk_type_check
CHECK (chunk_type IN ('parent', 'child', 'table'));

-- Update column comment
COMMENT ON COLUMN public.chunks.chunk_type IS 'parent (larger context), child (precise retrieval), or table (extracted table content)';
