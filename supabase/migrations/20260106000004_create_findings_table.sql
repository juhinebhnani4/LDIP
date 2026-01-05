-- Create findings table for engine outputs (citations, timeline, contradictions)
-- This implements Layer 1 of 4-layer matter isolation (Story 1-7)

-- =============================================================================
-- TABLE: findings - Analysis engine outputs requiring verification
-- =============================================================================

CREATE TABLE public.findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  engine_type text NOT NULL CHECK (engine_type IN ('citation', 'timeline', 'contradiction')),
  finding_type text NOT NULL,
  content jsonb NOT NULL,
  confidence float NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  evidence_refs jsonb, -- References to supporting evidence
  source_document_ids uuid[],
  source_pages integer[],
  source_bbox_ids uuid[],
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'rejected')),
  verified_by uuid REFERENCES auth.users(id),
  verified_at timestamptz,
  verification_notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for findings queries and verification workflow
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_findings_matter_id ON public.findings(matter_id);
CREATE INDEX idx_findings_engine_type ON public.findings(engine_type);
CREATE INDEX idx_findings_status ON public.findings(status);
CREATE INDEX idx_findings_verified_by ON public.findings(verified_by);

-- Composite indexes for common query patterns
CREATE INDEX idx_findings_matter_engine ON public.findings(matter_id, engine_type);
CREATE INDEX idx_findings_matter_status ON public.findings(matter_id, status);
CREATE INDEX idx_findings_matter_engine_status ON public.findings(matter_id, engine_type, status);

-- GIN indexes for array columns
CREATE INDEX idx_findings_source_docs ON public.findings USING GIN (source_document_ids);
CREATE INDEX idx_findings_source_bboxes ON public.findings USING GIN (source_bbox_ids);

-- JSONB index for content queries
CREATE INDEX idx_findings_content ON public.findings USING GIN (content);

-- Confidence-based filtering
CREATE INDEX idx_findings_confidence ON public.findings(confidence);

-- Partial index for pending findings (verification queue)
CREATE INDEX idx_findings_pending ON public.findings(matter_id, created_at)
  WHERE status = 'pending';

-- Comments
COMMENT ON TABLE public.findings IS 'Engine findings requiring attorney verification - matter isolated';
COMMENT ON COLUMN public.findings.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.findings.engine_type IS 'Source engine: citation, timeline, or contradiction';
COMMENT ON COLUMN public.findings.finding_type IS 'Specific finding type within engine (e.g., citation_mismatch, date_conflict)';
COMMENT ON COLUMN public.findings.content IS 'Structured finding content (JSONB for flexibility)';
COMMENT ON COLUMN public.findings.confidence IS 'AI confidence score (0-1) - affects display and export eligibility';
COMMENT ON COLUMN public.findings.evidence_refs IS 'References to supporting chunks, citations, etc.';
COMMENT ON COLUMN public.findings.source_document_ids IS 'Documents where finding was detected';
COMMENT ON COLUMN public.findings.source_pages IS 'Page numbers for source references';
COMMENT ON COLUMN public.findings.source_bbox_ids IS 'Bounding boxes for text highlighting';
COMMENT ON COLUMN public.findings.status IS 'Verification status: pending, verified, rejected';
COMMENT ON COLUMN public.findings.verified_by IS 'Attorney who verified this finding';
COMMENT ON COLUMN public.findings.verified_at IS 'When finding was verified';
COMMENT ON COLUMN public.findings.verification_notes IS 'Attorney notes on verification decision';

-- =============================================================================
-- RLS POLICIES: findings table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.findings ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT findings from matters where they have any role
CREATE POLICY "Users can view findings from their matters"
ON public.findings FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT findings (via engine pipeline)
CREATE POLICY "Editors and Owners can insert findings"
ON public.findings FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE findings (verification workflow)
CREATE POLICY "Editors and Owners can update findings"
ON public.findings FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE findings
CREATE POLICY "Only Owners can delete findings"
ON public.findings FOR DELETE
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

CREATE TRIGGER set_findings_updated_at
  BEFORE UPDATE ON public.findings
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
