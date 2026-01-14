-- Migration: Create finding_verifications table
-- Story 8-4: Implement Finding Verifications Table
-- Epic 8: Safety Layer (Guardrails, Policing, Verification)
--
-- Creates a dedicated verification record table for findings.
-- Implements FR10 (Attorney Verification Workflow) and NFR23 (Court-defensible trail).
-- Uses ADR-004 tiered verification thresholds (>90% optional, 70-90% suggested, <70% required).

-- =============================================================================
-- TABLE: finding_verifications - Attorney verification records for findings
-- =============================================================================

CREATE TABLE public.finding_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  finding_id uuid REFERENCES public.findings(id) ON DELETE SET NULL,
  -- Note: finding_id can be NULL if finding was deleted but verification kept for audit

  -- Finding snapshot (preserved even if finding deleted)
  finding_type text NOT NULL,
  finding_summary text NOT NULL,
  confidence_before float NOT NULL CHECK (confidence_before >= 0 AND confidence_before <= 100),

  -- Verification decision
  decision text NOT NULL DEFAULT 'pending'
    CHECK (decision IN ('pending', 'approved', 'rejected', 'flagged')),
  verified_by uuid REFERENCES auth.users(id),
  verified_at timestamptz,
  confidence_after float CHECK (confidence_after IS NULL OR (confidence_after >= 0 AND confidence_after <= 100)),
  notes text,

  -- Timestamps
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for verification queue and dashboard queries
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_finding_verifications_matter_id
  ON public.finding_verifications(matter_id);

CREATE INDEX idx_finding_verifications_finding_id
  ON public.finding_verifications(finding_id);

CREATE INDEX idx_finding_verifications_decision
  ON public.finding_verifications(decision);

CREATE INDEX idx_finding_verifications_verified_by
  ON public.finding_verifications(verified_by);

CREATE INDEX idx_finding_verifications_confidence_before
  ON public.finding_verifications(confidence_before);

-- Partial index for pending verifications (Story 8-5 verification queue optimization)
CREATE INDEX idx_finding_verifications_pending
  ON public.finding_verifications(matter_id, created_at)
  WHERE decision = 'pending';

-- Composite index for matter + decision filtering (dashboard queries)
CREATE INDEX idx_finding_verifications_matter_decision
  ON public.finding_verifications(matter_id, decision);

-- Composite index for export eligibility check (finds < 70% pending)
CREATE INDEX idx_finding_verifications_export_blocking
  ON public.finding_verifications(matter_id, confidence_before)
  WHERE decision = 'pending' AND confidence_before < 70;

-- =============================================================================
-- COMMENTS: Document columns per project conventions
-- =============================================================================

COMMENT ON TABLE public.finding_verifications IS
'Story 8-4: Attorney verification records for engine findings. Implements FR10 and NFR23 court-defensible verification trail.';

COMMENT ON COLUMN public.finding_verifications.id IS
'Primary key - verification record UUID';

COMMENT ON COLUMN public.finding_verifications.matter_id IS
'FK to matters - CRITICAL for 4-layer isolation (RLS enforced)';

COMMENT ON COLUMN public.finding_verifications.finding_id IS
'FK to findings - SET NULL on finding deletion to preserve audit trail';

COMMENT ON COLUMN public.finding_verifications.finding_type IS
'Snapshot of finding type at creation (citation_mismatch, date_conflict, contradiction, etc.)';

COMMENT ON COLUMN public.finding_verifications.finding_summary IS
'Snapshot of finding summary for queue display (preserved even if finding deleted)';

COMMENT ON COLUMN public.finding_verifications.confidence_before IS
'Original AI confidence at finding creation (0-100 scale per existing patterns)';

COMMENT ON COLUMN public.finding_verifications.decision IS
'Verification decision: pending (awaiting review), approved (verified correct), rejected (marked incorrect), flagged (needs further review)';

COMMENT ON COLUMN public.finding_verifications.verified_by IS
'FK to auth.users - attorney who made the verification decision';

COMMENT ON COLUMN public.finding_verifications.verified_at IS
'Timestamp when verification decision was recorded';

COMMENT ON COLUMN public.finding_verifications.confidence_after IS
'Attorney-adjusted confidence (optional) - allows manual confidence override';

COMMENT ON COLUMN public.finding_verifications.notes IS
'Attorney notes explaining the verification decision (required for rejections)';

COMMENT ON COLUMN public.finding_verifications.created_at IS
'Record creation timestamp (when finding was generated)';

COMMENT ON COLUMN public.finding_verifications.updated_at IS
'Last modification timestamp';

-- =============================================================================
-- RLS POLICIES: finding_verifications table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.finding_verifications ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT verifications from matters where they have any role
CREATE POLICY "Users can view verifications from their matters"
ON public.finding_verifications FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT verification records (via engine pipeline)
CREATE POLICY "Editors and Owners can insert verifications"
ON public.finding_verifications FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE verifications (record decisions)
CREATE POLICY "Editors and Owners can update verifications"
ON public.finding_verifications FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Only Owners can DELETE verification records (audit trail protection)
CREATE POLICY "Only Owners can delete verifications"
ON public.finding_verifications FOR DELETE
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

CREATE TRIGGER set_finding_verifications_updated_at
  BEFORE UPDATE ON public.finding_verifications
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
