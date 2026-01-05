-- Create documents table for legal document storage
-- This implements FR11: Document Upload & Storage for the 4-layer matter isolation (Story 1-7)

-- =============================================================================
-- TABLE: documents - Legal documents uploaded to matters
-- =============================================================================

CREATE TABLE public.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  filename text NOT NULL,
  storage_path text NOT NULL,
  file_size bigint NOT NULL,
  page_count integer,
  document_type text NOT NULL CHECK (document_type IN ('case_file', 'act', 'annexure', 'other')),
  is_reference_material boolean DEFAULT false,
  uploaded_by uuid NOT NULL REFERENCES auth.users(id),
  uploaded_at timestamptz DEFAULT now(),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  processing_started_at timestamptz,
  processing_completed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Performance indexes
CREATE INDEX idx_documents_matter_id ON public.documents(matter_id);
CREATE INDEX idx_documents_type ON public.documents(document_type);
CREATE INDEX idx_documents_status ON public.documents(status);
CREATE INDEX idx_documents_uploaded_by ON public.documents(uploaded_by);

-- Composite index for common query patterns
CREATE INDEX idx_documents_matter_status ON public.documents(matter_id, status);

-- Comments
COMMENT ON TABLE public.documents IS 'Legal documents uploaded to matters for analysis';
COMMENT ON COLUMN public.documents.matter_id IS 'FK to matters table - document belongs to this matter';
COMMENT ON COLUMN public.documents.filename IS 'Original filename as uploaded';
COMMENT ON COLUMN public.documents.storage_path IS 'Supabase Storage path: documents/{matter_id}/uploads/{filename}';
COMMENT ON COLUMN public.documents.file_size IS 'File size in bytes';
COMMENT ON COLUMN public.documents.page_count IS 'Number of pages (null until OCR complete)';
COMMENT ON COLUMN public.documents.document_type IS 'Type: case_file, act, annexure, other';
COMMENT ON COLUMN public.documents.is_reference_material IS 'True for Acts and reference docs, false for case files';
COMMENT ON COLUMN public.documents.uploaded_by IS 'User who uploaded this document';
COMMENT ON COLUMN public.documents.status IS 'Processing status: pending, processing, completed, failed';

-- =============================================================================
-- RLS POLICIES: documents table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT documents from matters where they have any role
CREATE POLICY "Users can view documents from their matters"
ON public.documents FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Users with editor or owner role can INSERT documents
CREATE POLICY "Editors and Owners can upload documents"
ON public.documents FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Users with editor or owner role can UPDATE documents
CREATE POLICY "Editors and Owners can update documents"
ON public.documents FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Only owners can DELETE documents
CREATE POLICY "Only Owners can delete documents"
ON public.documents FOR DELETE
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

CREATE TRIGGER set_documents_updated_at
  BEFORE UPDATE ON public.documents
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
