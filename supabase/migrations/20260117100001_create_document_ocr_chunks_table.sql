-- Create document_ocr_chunks table for tracking OCR chunk processing state
-- This implements Story 15.1: Document OCR Chunks Database Table
-- Enables large PDF processing via parallel chunked OCR (Epic 15)

-- =============================================================================
-- TABLE: document_ocr_chunks - OCR chunk processing state tracking
-- =============================================================================

CREATE TABLE public.document_ocr_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  page_start integer NOT NULL,
  page_end integer NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  error_message text,
  result_storage_path text,
  result_checksum text,
  processing_started_at timestamptz,
  processing_completed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  -- Constraints
  CONSTRAINT document_ocr_chunks_unique_doc_chunk UNIQUE (document_id, chunk_index),
  CONSTRAINT document_ocr_chunks_check_page_order CHECK (page_start <= page_end),
  CONSTRAINT document_ocr_chunks_check_page_start CHECK (page_start >= 1),
  CONSTRAINT document_ocr_chunks_check_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

-- =============================================================================
-- INDEXES: Optimized for chunk queries and status monitoring
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_doc_ocr_chunks_document_id ON public.document_ocr_chunks(document_id);
CREATE INDEX idx_doc_ocr_chunks_matter_id ON public.document_ocr_chunks(matter_id);

-- Composite index for status-based queries (finding pending/failed chunks)
CREATE INDEX idx_doc_ocr_chunks_document_status ON public.document_ocr_chunks(document_id, status);

-- =============================================================================
-- COMMENTS: Table and column documentation
-- =============================================================================

COMMENT ON TABLE public.document_ocr_chunks IS 'Tracks OCR chunk processing state for large document parallel processing';
COMMENT ON COLUMN public.document_ocr_chunks.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.document_ocr_chunks.document_id IS 'FK to documents - source document being chunked';
COMMENT ON COLUMN public.document_ocr_chunks.chunk_index IS 'Zero-indexed position of chunk within document';
COMMENT ON COLUMN public.document_ocr_chunks.page_start IS 'First page of chunk (1-indexed)';
COMMENT ON COLUMN public.document_ocr_chunks.page_end IS 'Last page of chunk (1-indexed)';
COMMENT ON COLUMN public.document_ocr_chunks.status IS 'Processing status: pending, processing, completed, failed';
COMMENT ON COLUMN public.document_ocr_chunks.error_message IS 'Error details if status is failed';
COMMENT ON COLUMN public.document_ocr_chunks.result_storage_path IS 'Supabase Storage path for cached OCR results';
COMMENT ON COLUMN public.document_ocr_chunks.result_checksum IS 'SHA256 checksum for result validation';
COMMENT ON COLUMN public.document_ocr_chunks.processing_started_at IS 'Timestamp when OCR processing began (for heartbeat detection)';
COMMENT ON COLUMN public.document_ocr_chunks.processing_completed_at IS 'Timestamp when OCR processing finished';

-- =============================================================================
-- RLS POLICIES: document_ocr_chunks table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.document_ocr_chunks ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT chunks from matters where they have any role
CREATE POLICY "Users can view chunks from their matters"
ON public.document_ocr_chunks FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT chunks (via processing pipeline)
CREATE POLICY "Editors and Owners can insert chunks"
ON public.document_ocr_chunks FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE chunk status
CREATE POLICY "Editors and Owners can update chunks"
ON public.document_ocr_chunks FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Only Owners can DELETE chunks
CREATE POLICY "Only Owners can delete chunks"
ON public.document_ocr_chunks FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- TRIGGER: Auto-update updated_at on modification
-- =============================================================================

CREATE TRIGGER set_document_ocr_chunks_updated_at
  BEFORE UPDATE ON public.document_ocr_chunks
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- STORAGE POLICIES: ocr-chunks bucket
-- =============================================================================
--
-- BUCKET SETUP REQUIRED (via dashboard or script):
--   1. Create bucket: Storage > New Bucket > "ocr-chunks" (private)
--   2. File size limit: 10MB
--   3. Allowed MIME types: application/json
--
-- Path structure: {matter_id}/{document_id}/{chunk_index}.json
-- =============================================================================

-- Helper function: Extract matter_id from OCR chunk storage path
CREATE OR REPLACE FUNCTION public.get_matter_id_from_chunk_path(path text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  path_parts text[];
  matter_id_str text;
BEGIN
  -- Path format: {matter_id}/{document_id}/{chunk_index}.json
  path_parts := string_to_array(path, '/');

  -- Validate path structure (must have 3 parts)
  IF array_length(path_parts, 1) < 3 THEN
    RETURN NULL;
  END IF;

  matter_id_str := path_parts[1];

  -- Validate UUID format
  IF matter_id_str !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN NULL;
  END IF;

  RETURN matter_id_str::uuid;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

COMMENT ON FUNCTION public.get_matter_id_from_chunk_path IS 'Extracts matter_id from OCR chunk storage path for RLS validation';

-- Grant execute to authenticated users (needed for RLS policies)
GRANT EXECUTE ON FUNCTION public.get_matter_id_from_chunk_path TO authenticated;

-- Helper function: Validate OCR chunk storage path structure
CREATE OR REPLACE FUNCTION public.validate_ocr_chunk_path(path text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  path_parts text[];
  filename text;
BEGIN
  path_parts := string_to_array(path, '/');

  -- Must have exactly 3 parts: {matter_id}/{document_id}/{chunk_index}.json
  IF array_length(path_parts, 1) != 3 THEN
    RETURN false;
  END IF;

  -- First part (matter_id) must be a valid UUID
  IF path_parts[1] !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN false;
  END IF;

  -- Second part (document_id) must be a valid UUID
  IF path_parts[2] !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN false;
  END IF;

  -- Third part must be a valid chunk filename (number.json)
  filename := path_parts[3];
  IF filename !~ '^[0-9]+\.json$' THEN
    RETURN false;
  END IF;

  RETURN true;
END;
$$;

COMMENT ON FUNCTION public.validate_ocr_chunk_path IS 'Validates OCR chunk storage path structure';

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.validate_ocr_chunk_path TO authenticated;

-- =============================================================================
-- STORAGE POLICIES: ocr-chunks bucket
-- =============================================================================

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can view ocr chunks from their matters" ON storage.objects;
DROP POLICY IF EXISTS "Editors and Owners can upload ocr chunks" ON storage.objects;
DROP POLICY IF EXISTS "Editors and Owners can update ocr chunks" ON storage.objects;
DROP POLICY IF EXISTS "Owners can delete ocr chunks" ON storage.objects;

-- Policy 1: Users can SELECT (download) OCR chunk files from matters they have access to
CREATE POLICY "Users can view ocr chunks from their matters"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'ocr-chunks'
  AND public.user_has_storage_access(
    public.get_matter_id_from_chunk_path(name),
    ARRAY['owner', 'editor', 'viewer']
  )
);

-- Policy 2: Editors and Owners can INSERT (upload) OCR chunk files to their matters
CREATE POLICY "Editors and Owners can upload ocr chunks"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'ocr-chunks'
  AND public.validate_ocr_chunk_path(name)
  AND public.user_has_storage_access(
    public.get_matter_id_from_chunk_path(name),
    ARRAY['owner', 'editor']
  )
);

-- Policy 3: Editors and Owners can UPDATE OCR chunk file metadata
CREATE POLICY "Editors and Owners can update ocr chunks"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'ocr-chunks'
  AND public.user_has_storage_access(
    public.get_matter_id_from_chunk_path(name),
    ARRAY['owner', 'editor']
  )
);

-- Policy 4: Only Owners can DELETE OCR chunk files
CREATE POLICY "Owners can delete ocr chunks"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'ocr-chunks'
  AND public.user_has_storage_access(
    public.get_matter_id_from_chunk_path(name),
    ARRAY['owner']
  )
);
