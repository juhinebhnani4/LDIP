-- Create act_resolutions table for tracking Act document availability
-- This implements Layer 1 of 4-layer matter isolation (Story 1-7)
-- Schema per ADR-005: Citation Engine Data Model

-- =============================================================================
-- TABLE: act_resolutions - Tracks Act document availability per matter
-- =============================================================================

CREATE TABLE public.act_resolutions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,

  -- Act identification (normalized name for matching)
  act_name_normalized text NOT NULL,

  -- Linked Act document (if uploaded)
  act_document_id uuid REFERENCES public.documents(id) ON DELETE SET NULL,

  -- Resolution status
  resolution_status text NOT NULL DEFAULT 'missing'
    CHECK (resolution_status IN ('available', 'missing', 'skipped')),

  -- User action
  user_action text NOT NULL DEFAULT 'pending'
    CHECK (user_action IN ('uploaded', 'skipped', 'pending')),

  -- Metadata
  citation_count integer DEFAULT 0, -- Number of citations referencing this Act
  first_seen_at timestamptz DEFAULT now(),

  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  -- One entry per act per matter
  UNIQUE(matter_id, act_name_normalized)
);

-- =============================================================================
-- INDEXES: Optimized for Act discovery and resolution workflow
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_act_resolutions_matter_id ON public.act_resolutions(matter_id);
CREATE INDEX idx_act_resolutions_status ON public.act_resolutions(resolution_status);
CREATE INDEX idx_act_resolutions_user_action ON public.act_resolutions(user_action);
CREATE INDEX idx_act_resolutions_act_doc ON public.act_resolutions(act_document_id);

-- Normalized act name for matching
CREATE INDEX idx_act_resolutions_act_name ON public.act_resolutions(act_name_normalized);

-- Composite indexes for common query patterns
CREATE INDEX idx_act_resolutions_matter_status ON public.act_resolutions(matter_id, resolution_status);
CREATE INDEX idx_act_resolutions_matter_action ON public.act_resolutions(matter_id, user_action);

-- Partial index for missing acts (prompt user to upload)
CREATE INDEX idx_act_resolutions_missing ON public.act_resolutions(matter_id, citation_count DESC)
  WHERE resolution_status = 'missing';

-- Partial index for pending user action
CREATE INDEX idx_act_resolutions_pending ON public.act_resolutions(matter_id, first_seen_at)
  WHERE user_action = 'pending';

-- Comments
COMMENT ON TABLE public.act_resolutions IS 'Tracks Act document availability per matter for citation verification';
COMMENT ON COLUMN public.act_resolutions.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.act_resolutions.act_name_normalized IS 'Normalized Act name for matching (lowercase, no punctuation)';
COMMENT ON COLUMN public.act_resolutions.act_document_id IS 'FK to uploaded Act document (if available)';
COMMENT ON COLUMN public.act_resolutions.resolution_status IS 'available (has doc), missing (need upload), skipped (user chose to skip)';
COMMENT ON COLUMN public.act_resolutions.user_action IS 'uploaded (user uploaded doc), skipped (user skipped), pending (awaiting action)';
COMMENT ON COLUMN public.act_resolutions.citation_count IS 'Number of citations referencing this Act (for prioritization)';
COMMENT ON COLUMN public.act_resolutions.first_seen_at IS 'When this Act was first referenced in the matter';

-- =============================================================================
-- RLS POLICIES: act_resolutions table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.act_resolutions ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT act resolutions from matters where they have any role
CREATE POLICY "Users can view act resolutions from their matters"
ON public.act_resolutions FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT act resolutions (via citation engine)
CREATE POLICY "Editors and Owners can insert act resolutions"
ON public.act_resolutions FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE act resolutions (upload/skip workflow)
CREATE POLICY "Editors and Owners can update act resolutions"
ON public.act_resolutions FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE act resolutions
CREATE POLICY "Only Owners can delete act resolutions"
ON public.act_resolutions FOR DELETE
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

CREATE TRIGGER set_act_resolutions_updated_at
  BEFORE UPDATE ON public.act_resolutions
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTION: Upsert act resolution (increment citation count)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.upsert_act_resolution(
  p_matter_id uuid,
  p_act_name_normalized text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  -- Verify user has editor or owner access
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  ) THEN
    RAISE EXCEPTION 'Access denied: user cannot modify act resolutions for matter %', p_matter_id;
  END IF;

  INSERT INTO public.act_resolutions (matter_id, act_name_normalized, citation_count)
  VALUES (p_matter_id, p_act_name_normalized, 1)
  ON CONFLICT (matter_id, act_name_normalized)
  DO UPDATE SET
    citation_count = act_resolutions.citation_count + 1,
    updated_at = now()
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.upsert_act_resolution IS 'Upsert act resolution with citation count increment';
