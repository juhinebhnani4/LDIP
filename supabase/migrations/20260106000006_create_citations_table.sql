-- Create citations table for Citation Verification Engine
-- This implements Layer 1 of 4-layer matter isolation (Story 1-7)
-- Schema per ADR-005: Citation Engine Data Model

-- =============================================================================
-- TABLE: citations - Act citations extracted from case documents
-- =============================================================================

CREATE TABLE public.citations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,

  -- Source citation (from case file)
  source_document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  act_name text NOT NULL,
  section text NOT NULL,
  quoted_text text,
  source_page integer NOT NULL,
  source_bbox_ids uuid[],

  -- Verification status
  verification_status text NOT NULL DEFAULT 'pending'
    CHECK (verification_status IN ('verified', 'mismatch', 'not_found', 'act_unavailable', 'pending')),

  -- Target (matching Act document, if found)
  target_act_document_id uuid REFERENCES public.documents(id) ON DELETE SET NULL,
  target_page integer,
  target_bbox_ids uuid[],

  -- Confidence and metadata
  confidence float CHECK (confidence >= 0 AND confidence <= 1),
  mismatch_details jsonb, -- Details about mismatches if any

  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for citation verification workflow
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_citations_matter_id ON public.citations(matter_id);
CREATE INDEX idx_citations_source_doc ON public.citations(source_document_id);
CREATE INDEX idx_citations_target_doc ON public.citations(target_act_document_id);
CREATE INDEX idx_citations_status ON public.citations(verification_status);

-- Act-based queries (for act discovery report)
CREATE INDEX idx_citations_act_name ON public.citations(act_name);
CREATE INDEX idx_citations_matter_act ON public.citations(matter_id, act_name);

-- Composite indexes for common query patterns
CREATE INDEX idx_citations_matter_status ON public.citations(matter_id, verification_status);

-- GIN indexes for array columns
CREATE INDEX idx_citations_source_bboxes ON public.citations USING GIN (source_bbox_ids);
CREATE INDEX idx_citations_target_bboxes ON public.citations USING GIN (target_bbox_ids);

-- Partial index for pending citations
CREATE INDEX idx_citations_pending ON public.citations(matter_id, created_at)
  WHERE verification_status = 'pending';

-- Partial index for mismatches (high priority for review)
CREATE INDEX idx_citations_mismatches ON public.citations(matter_id, created_at)
  WHERE verification_status = 'mismatch';

-- Comments
COMMENT ON TABLE public.citations IS 'Act citations extracted from case documents for verification';
COMMENT ON COLUMN public.citations.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.citations.source_document_id IS 'Case file containing the citation';
COMMENT ON COLUMN public.citations.act_name IS 'Name of Act being cited (e.g., "Indian Evidence Act, 1872")';
COMMENT ON COLUMN public.citations.section IS 'Section being cited (e.g., "Section 65B(4)")';
COMMENT ON COLUMN public.citations.quoted_text IS 'Text quoted from the Act (if any)';
COMMENT ON COLUMN public.citations.source_page IS 'Page in case file where citation appears';
COMMENT ON COLUMN public.citations.source_bbox_ids IS 'Bounding boxes for citation highlighting';
COMMENT ON COLUMN public.citations.verification_status IS 'Status: verified, mismatch, not_found, act_unavailable, pending';
COMMENT ON COLUMN public.citations.target_act_document_id IS 'Matched Act document (if available and verified)';
COMMENT ON COLUMN public.citations.target_page IS 'Page in Act document matching the citation';
COMMENT ON COLUMN public.citations.target_bbox_ids IS 'Bounding boxes in Act document for split-view';
COMMENT ON COLUMN public.citations.confidence IS 'Verification confidence score (0-1)';
COMMENT ON COLUMN public.citations.mismatch_details IS 'Details about text mismatches if verification_status=mismatch';

-- =============================================================================
-- RLS POLICIES: citations table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.citations ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT citations from matters where they have any role
CREATE POLICY "Users can view citations from their matters"
ON public.citations FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT citations (via citation engine)
CREATE POLICY "Editors and Owners can insert citations"
ON public.citations FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE citations (verification workflow)
CREATE POLICY "Editors and Owners can update citations"
ON public.citations FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE citations
CREATE POLICY "Only Owners can delete citations"
ON public.citations FOR DELETE
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

CREATE TRIGGER set_citations_updated_at
  BEFORE UPDATE ON public.citations
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
