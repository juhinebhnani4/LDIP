-- Create Shared Legal Library tables for public legal documents
-- This implements the Shared Legal Library feature for Acts, Statutes, Judgments, etc.
-- that can be linked to multiple matters

-- =============================================================================
-- EXTENSION: pg_trgm for fuzzy text matching (deduplication)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- TABLE: library_documents - Shared legal documents (Acts, Statutes, Judgments)
-- =============================================================================

CREATE TABLE public.library_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filename text NOT NULL,
  storage_path text NOT NULL UNIQUE,  -- documents/library/{category}/{filename}
  file_size bigint NOT NULL,
  page_count integer,

  -- Document classification
  document_type text NOT NULL CHECK (document_type IN (
    'act', 'statute', 'judgment', 'regulation', 'commentary', 'circular'
  )),

  -- Metadata for searchability
  title text NOT NULL,                 -- "Indian Contract Act, 1872"
  short_title text,                    -- "Contract Act"
  year integer,                        -- 1872
  jurisdiction text,                   -- 'central', 'state:MH', 'state:KA', etc.

  -- Source tracking
  source text NOT NULL DEFAULT 'user_upload' CHECK (source IN (
    'user_upload', 'india_code', 'manual_import'
  )),
  source_url text,                     -- Original URL if fetched

  -- Processing status
  status text NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending', 'processing', 'completed', 'failed'
  )),
  processing_started_at timestamptz,
  processing_completed_at timestamptz,

  -- Quality flags for soft curation
  quality_flags jsonb DEFAULT '[]'::jsonb,  -- ["no_ocr_text", "tiny_file", etc.]

  -- Audit fields
  added_by uuid REFERENCES auth.users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: library_documents
-- =============================================================================

-- Full-text search on title and short_title
CREATE INDEX idx_library_documents_title_trgm ON public.library_documents
  USING gin (lower(title) gin_trgm_ops);
CREATE INDEX idx_library_documents_short_title_trgm ON public.library_documents
  USING gin (lower(short_title) gin_trgm_ops);

-- Filtering indexes
CREATE INDEX idx_library_documents_type ON public.library_documents(document_type);
CREATE INDEX idx_library_documents_year ON public.library_documents(year);
CREATE INDEX idx_library_documents_jurisdiction ON public.library_documents(jurisdiction);
CREATE INDEX idx_library_documents_source ON public.library_documents(source);
CREATE INDEX idx_library_documents_status ON public.library_documents(status);

-- Composite for common query patterns
CREATE INDEX idx_library_documents_type_year ON public.library_documents(document_type, year);

-- Comments
COMMENT ON TABLE public.library_documents IS 'Shared legal documents (Acts, Statutes, Judgments) that can be linked to multiple matters';
COMMENT ON COLUMN public.library_documents.storage_path IS 'Supabase Storage path: documents/library/{document_type}/{filename}';
COMMENT ON COLUMN public.library_documents.jurisdiction IS 'central for Union acts, state:XX for state acts';
COMMENT ON COLUMN public.library_documents.source IS 'Where the document came from: user_upload, india_code auto-fetch, or manual_import';
COMMENT ON COLUMN public.library_documents.quality_flags IS 'Array of quality issues: no_ocr_text, tiny_file, poor_quality, etc.';

-- =============================================================================
-- TABLE: matter_library_links - Junction table linking library docs to matters
-- =============================================================================

CREATE TABLE public.matter_library_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  library_document_id uuid NOT NULL REFERENCES public.library_documents(id) ON DELETE CASCADE,
  linked_by uuid NOT NULL REFERENCES auth.users(id),
  linked_at timestamptz DEFAULT now(),

  -- Ensure no duplicate links
  UNIQUE(matter_id, library_document_id)
);

-- Indexes for matter_library_links
CREATE INDEX idx_matter_library_links_matter ON public.matter_library_links(matter_id);
CREATE INDEX idx_matter_library_links_library_doc ON public.matter_library_links(library_document_id);

COMMENT ON TABLE public.matter_library_links IS 'Links library documents to matters - many-to-many relationship';

-- =============================================================================
-- TABLE: library_chunks - Chunks for library documents
-- =============================================================================

CREATE TABLE public.library_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  library_document_id uuid NOT NULL REFERENCES public.library_documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  parent_chunk_id uuid REFERENCES public.library_chunks(id) ON DELETE CASCADE,
  content text NOT NULL,
  embedding vector(1536),  -- OpenAI ada-002 / text-embedding-3-small dimension
  page_number integer,
  section_title text,      -- For legal documents: "Section 4", "Article III", etc.
  token_count integer,
  chunk_type text NOT NULL CHECK (chunk_type IN ('parent', 'child')),
  created_at timestamptz DEFAULT now()
);

-- Indexes for library_chunks
CREATE INDEX idx_library_chunks_document ON public.library_chunks(library_document_id);
CREATE INDEX idx_library_chunks_parent ON public.library_chunks(parent_chunk_id);
CREATE INDEX idx_library_chunks_type ON public.library_chunks(chunk_type);
CREATE INDEX idx_library_chunks_page ON public.library_chunks(page_number);

-- Vector search index (HNSW for fast approximate nearest neighbor)
CREATE INDEX idx_library_chunks_embedding ON public.library_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Composite for document + chunk queries
CREATE INDEX idx_library_chunks_doc_index ON public.library_chunks(library_document_id, chunk_index);

COMMENT ON TABLE public.library_chunks IS 'Document chunks for library documents with embeddings for RAG';
COMMENT ON COLUMN public.library_chunks.section_title IS 'Legal section identifier: Section 4, Article III, etc.';

-- =============================================================================
-- RLS POLICIES: library_documents - All authenticated users can read/insert
-- =============================================================================

ALTER TABLE public.library_documents ENABLE ROW LEVEL SECURITY;

-- All authenticated users can view library documents
CREATE POLICY "Authenticated users can view library documents"
ON public.library_documents FOR SELECT
TO authenticated
USING (true);

-- All authenticated users can add to the library (Smart Auto-Curation model)
CREATE POLICY "Authenticated users can add library documents"
ON public.library_documents FOR INSERT
TO authenticated
WITH CHECK (added_by = auth.uid());

-- Only the uploader can update their pending documents
CREATE POLICY "Uploaders can update their library documents"
ON public.library_documents FOR UPDATE
TO authenticated
USING (added_by = auth.uid() AND status IN ('pending', 'failed'));

-- No delete for regular users (admin-only operation if needed)
-- Soft delete via status = 'deleted' can be added later if needed

-- =============================================================================
-- RLS POLICIES: matter_library_links - Matter-scoped access
-- =============================================================================

ALTER TABLE public.matter_library_links ENABLE ROW LEVEL SECURITY;

-- Users can view links for their matters
CREATE POLICY "Users can view links for their matters"
ON public.matter_library_links FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Editors and Owners can link documents to their matters
CREATE POLICY "Editors and Owners can link library documents"
ON public.matter_library_links FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
  AND linked_by = auth.uid()
);

-- Editors and Owners can unlink documents from their matters
CREATE POLICY "Editors and Owners can unlink library documents"
ON public.matter_library_links FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- =============================================================================
-- RLS POLICIES: library_chunks - All authenticated users can read
-- =============================================================================

ALTER TABLE public.library_chunks ENABLE ROW LEVEL SECURITY;

-- All authenticated users can view library chunks
CREATE POLICY "Authenticated users can view library chunks"
ON public.library_chunks FOR SELECT
TO authenticated
USING (true);

-- Only service role can insert/update/delete chunks (via processing pipeline)
-- Using SECURITY DEFINER functions for processing

-- =============================================================================
-- FUNCTION: find_library_duplicates - Fuzzy matching for deduplication
-- =============================================================================

CREATE OR REPLACE FUNCTION public.find_library_duplicates(
  search_title text,
  search_year integer DEFAULT NULL,
  similarity_threshold float DEFAULT 0.6
)
RETURNS TABLE (
  id uuid,
  title text,
  year integer,
  document_type text,
  similarity float
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    ld.id,
    ld.title,
    ld.year,
    ld.document_type,
    similarity(lower(ld.title), lower(search_title)) AS similarity
  FROM library_documents ld
  WHERE ld.status != 'failed'
    AND (
      -- Title similarity above threshold
      similarity(lower(ld.title), lower(search_title)) > similarity_threshold
      -- OR year match with lower title threshold
      OR (search_year IS NOT NULL AND ld.year = search_year
          AND similarity(lower(ld.title), lower(search_title)) > 0.4)
    )
  ORDER BY similarity DESC
  LIMIT 5;
$$;

COMMENT ON FUNCTION public.find_library_duplicates IS 'Find potential duplicate library documents by fuzzy title matching';

-- =============================================================================
-- FUNCTION: match_library_chunks_for_matter - Semantic search within linked library
-- =============================================================================

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
SET search_path = public
AS $$
BEGIN
  -- Verify user has access to this matter
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied: user does not have access to matter %', filter_matter_id;
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

COMMENT ON FUNCTION public.match_library_chunks_for_matter IS 'Semantic search over library chunks linked to a specific matter';

-- =============================================================================
-- TRIGGER: Auto-update updated_at on library_documents modification
-- =============================================================================

CREATE TRIGGER set_library_documents_updated_at
  BEFORE UPDATE ON public.library_documents
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
