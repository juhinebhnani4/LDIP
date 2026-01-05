-- Create chunks table for RAG pipeline with vector embeddings
-- This implements Layer 1 (RLS) and Layer 2 (vector namespace) of 4-layer matter isolation (Story 1-7)

-- =============================================================================
-- EXTENSION: pgvector for vector similarity search
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- TABLE: chunks - Document chunks for RAG retrieval
-- =============================================================================

CREATE TABLE public.chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  parent_chunk_id uuid REFERENCES public.chunks(id) ON DELETE CASCADE,
  content text NOT NULL,
  embedding vector(1536), -- OpenAI ada-002 / text-embedding-3-small dimension
  entity_ids uuid[],
  page_number integer,
  bbox_ids uuid[],
  token_count integer,
  chunk_type text NOT NULL CHECK (chunk_type IN ('parent', 'child')),
  created_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for RAG queries with matter isolation
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_chunks_matter_id ON public.chunks(matter_id);
CREATE INDEX idx_chunks_document_id ON public.chunks(document_id);
CREATE INDEX idx_chunks_parent_id ON public.chunks(parent_chunk_id);

-- CRITICAL: Vector similarity search index (HNSW for fast approximate nearest neighbor)
-- Note: All vector queries MUST include matter_id filter for isolation
CREATE INDEX idx_chunks_embedding ON public.chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Entity filtering index for MIG queries
CREATE INDEX idx_chunks_entities ON public.chunks USING GIN (entity_ids);

-- Bounding box filtering index
CREATE INDEX idx_chunks_bboxes ON public.chunks USING GIN (bbox_ids);

-- Composite index for matter-scoped document queries
CREATE INDEX idx_chunks_matter_document ON public.chunks(matter_id, document_id);

-- Chunk type and page filtering
CREATE INDEX idx_chunks_type ON public.chunks(chunk_type);
CREATE INDEX idx_chunks_page ON public.chunks(page_number);

-- Comments
COMMENT ON TABLE public.chunks IS 'Document chunks with embeddings for RAG retrieval - matter isolated';
COMMENT ON COLUMN public.chunks.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.chunks.document_id IS 'FK to documents - source document';
COMMENT ON COLUMN public.chunks.chunk_index IS 'Position within document (0-indexed)';
COMMENT ON COLUMN public.chunks.parent_chunk_id IS 'For hierarchical chunking - child references parent';
COMMENT ON COLUMN public.chunks.content IS 'Chunk text content';
COMMENT ON COLUMN public.chunks.embedding IS 'Vector embedding (1536 dim for OpenAI)';
COMMENT ON COLUMN public.chunks.entity_ids IS 'Array of entity node IDs found in this chunk';
COMMENT ON COLUMN public.chunks.page_number IS 'Source page number for highlighting';
COMMENT ON COLUMN public.chunks.bbox_ids IS 'Array of bounding box IDs for text highlighting';
COMMENT ON COLUMN public.chunks.token_count IS 'Number of tokens in chunk (for context budgeting)';
COMMENT ON COLUMN public.chunks.chunk_type IS 'parent (larger context) or child (precise retrieval)';

-- =============================================================================
-- RLS POLICIES: chunks table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.chunks ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT chunks from matters where they have any role
CREATE POLICY "Users can view chunks from their matters"
ON public.chunks FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT chunks (via ingestion pipeline)
CREATE POLICY "Editors and Owners can insert chunks"
ON public.chunks FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE chunks (embedding updates, entity linking)
CREATE POLICY "Editors and Owners can update chunks"
ON public.chunks FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE chunks
CREATE POLICY "Only Owners can delete chunks"
ON public.chunks FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- FUNCTION: match_chunks - Semantic search with matter isolation
-- CRITICAL: This function enforces Layer 2 isolation (vector namespace)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.match_chunks(
  query_embedding vector(1536),
  match_count integer DEFAULT 10,
  filter_matter_id uuid DEFAULT NULL,
  filter_document_ids uuid[] DEFAULT NULL,
  filter_chunk_type text DEFAULT NULL,
  similarity_threshold float DEFAULT 0.5
)
RETURNS TABLE (
  id uuid,
  matter_id uuid,
  document_id uuid,
  chunk_index integer,
  content text,
  page_number integer,
  chunk_type text,
  token_count integer,
  entity_ids uuid[],
  bbox_ids uuid[],
  similarity float
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- CRITICAL: matter_id filter is REQUIRED for security
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required for security - cannot perform cross-matter search';
  END IF;

  -- Verify user has access to this matter (defense in depth - RLS also enforces this)
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied: user does not have access to matter %', filter_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    c.id,
    c.matter_id,
    c.document_id,
    c.chunk_index,
    c.content,
    c.page_number,
    c.chunk_type,
    c.token_count,
    c.entity_ids,
    c.bbox_ids,
    1 - (c.embedding <=> query_embedding) AS similarity
  FROM public.chunks c
  WHERE c.matter_id = filter_matter_id  -- CRITICAL: Always filter by matter
    AND c.embedding IS NOT NULL
    AND 1 - (c.embedding <=> query_embedding) > similarity_threshold
    AND (filter_document_ids IS NULL OR c.document_id = ANY(filter_document_ids))
    AND (filter_chunk_type IS NULL OR c.chunk_type = filter_chunk_type)
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION public.match_chunks IS 'Semantic search with MANDATORY matter isolation - Layer 2 enforcement';
