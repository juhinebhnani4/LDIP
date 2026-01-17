-- Create exports table for document export tracking
-- Story 12-3: Export Verification Check and Format Generation

-- =============================================================================
-- TABLE: exports - Track export generation and downloads
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    format TEXT NOT NULL CHECK (format IN ('pdf', 'docx', 'pptx')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    sections JSONB,  -- Sections included in the export
    file_name TEXT,
    file_path TEXT,  -- Path in Supabase Storage
    download_url TEXT,  -- Signed download URL (temporary)
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    verification_summary JSONB  -- Summary of verification status at export time
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for listing exports by matter
CREATE INDEX idx_exports_matter_id ON public.exports(matter_id);

-- Index for listing recent exports
CREATE INDEX idx_exports_created_at ON public.exports(created_at DESC);

-- Index for finding exports by status
CREATE INDEX idx_exports_status ON public.exports(status);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE public.exports ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view exports for matters they're members of
CREATE POLICY "Users can view matter exports"
ON public.exports FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM public.matter_attorneys
        WHERE matter_attorneys.matter_id = exports.matter_id
        AND matter_attorneys.user_id = auth.uid()
    )
);

-- Policy: Editors and Owners can create exports
CREATE POLICY "Editors and Owners can create exports"
ON public.exports FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.matter_attorneys
        WHERE matter_attorneys.matter_id = exports.matter_id
        AND matter_attorneys.user_id = auth.uid()
        AND matter_attorneys.role IN ('owner', 'editor')
    )
);

-- Policy: Service role can update exports (for background processing)
-- Note: Service role bypasses RLS, but we add this for completeness
CREATE POLICY "Owners can update exports"
ON public.exports FOR UPDATE
USING (
    EXISTS (
        SELECT 1 FROM public.matter_attorneys
        WHERE matter_attorneys.matter_id = exports.matter_id
        AND matter_attorneys.user_id = auth.uid()
        AND matter_attorneys.role = 'owner'
    )
);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE public.exports IS 'Tracks document export generation and download history';
COMMENT ON COLUMN public.exports.format IS 'Export format: pdf, docx, or pptx';
COMMENT ON COLUMN public.exports.status IS 'Export status: pending, processing, completed, or failed';
COMMENT ON COLUMN public.exports.sections IS 'JSON array of sections included in the export';
COMMENT ON COLUMN public.exports.file_path IS 'Path to exported file in Supabase Storage';
COMMENT ON COLUMN public.exports.verification_summary IS 'Snapshot of verification status at export time';
