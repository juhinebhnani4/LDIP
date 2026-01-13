-- Create anomalies table for Timeline Anomaly Detection
-- Story 4-4: Timeline Anomaly Detection
-- This implements Layer 1 of 4-layer matter isolation

-- =============================================================================
-- TABLE: anomalies - Detected timeline anomalies for attorney review
-- =============================================================================

CREATE TABLE public.anomalies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,

  -- Anomaly classification
  anomaly_type text NOT NULL CHECK (anomaly_type IN ('gap', 'sequence_violation', 'duplicate', 'outlier')),
  severity text NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),

  -- Anomaly details
  title text NOT NULL, -- Short description for UI display
  explanation text NOT NULL, -- Detailed explanation with suggested causes

  -- Related events
  event_ids uuid[] NOT NULL, -- Array of involved event UUIDs

  -- Sequence violation specific
  expected_order text[], -- For sequence violations - expected event type order
  actual_order text[], -- For sequence violations - actual event type order

  -- Gap anomaly specific
  gap_days integer, -- For gap anomalies - number of days in gap

  -- Detection metadata
  confidence float DEFAULT 0.8 CHECK (confidence >= 0 AND confidence <= 1),

  -- Attorney review status
  verified boolean DEFAULT false, -- Attorney confirmed this is a real issue
  dismissed boolean DEFAULT false, -- Attorney dismissed as not an issue
  verified_by uuid REFERENCES auth.users(id),
  verified_at timestamptz,

  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for anomaly queries
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_anomalies_matter_id ON public.anomalies(matter_id);
CREATE INDEX idx_anomalies_severity ON public.anomalies(severity);
CREATE INDEX idx_anomalies_type ON public.anomalies(anomaly_type);

-- For filtering by review status
CREATE INDEX idx_anomalies_verified ON public.anomalies(matter_id, verified);
CREATE INDEX idx_anomalies_dismissed ON public.anomalies(matter_id, dismissed);

-- GIN index for event_ids array
CREATE INDEX idx_anomalies_event_ids ON public.anomalies USING GIN (event_ids);

-- Composite index for common query patterns (severity-ordered listing)
CREATE INDEX idx_anomalies_matter_severity ON public.anomalies(matter_id, severity DESC, created_at DESC);

-- Comments
COMMENT ON TABLE public.anomalies IS 'Detected timeline anomalies for attorney review';
COMMENT ON COLUMN public.anomalies.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.anomalies.anomaly_type IS 'Type: gap, sequence_violation, duplicate, outlier';
COMMENT ON COLUMN public.anomalies.severity IS 'Severity level: low, medium, high, critical';
COMMENT ON COLUMN public.anomalies.title IS 'Short description for UI display';
COMMENT ON COLUMN public.anomalies.explanation IS 'Detailed explanation with suggested causes';
COMMENT ON COLUMN public.anomalies.event_ids IS 'Array of event UUIDs involved in this anomaly';
COMMENT ON COLUMN public.anomalies.expected_order IS 'For sequence violations - expected event type order';
COMMENT ON COLUMN public.anomalies.actual_order IS 'For sequence violations - actual event type order';
COMMENT ON COLUMN public.anomalies.gap_days IS 'For gap anomalies - number of days in gap';
COMMENT ON COLUMN public.anomalies.confidence IS 'Detection confidence (0-1)';
COMMENT ON COLUMN public.anomalies.verified IS 'True if attorney confirmed this is a real issue';
COMMENT ON COLUMN public.anomalies.dismissed IS 'True if attorney dismissed as not an issue';
COMMENT ON COLUMN public.anomalies.verified_by IS 'User who verified/dismissed this anomaly';
COMMENT ON COLUMN public.anomalies.verified_at IS 'Timestamp of verification/dismissal';

-- =============================================================================
-- RLS POLICIES: anomalies table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.anomalies ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT anomalies from matters where they have any role
CREATE POLICY "Users can view anomalies from their matters"
ON public.anomalies FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT anomalies (anomaly detection engine)
CREATE POLICY "Editors and Owners can insert anomalies"
ON public.anomalies FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE anomalies (for verify/dismiss)
CREATE POLICY "Editors and Owners can update anomalies"
ON public.anomalies FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE anomalies (for reprocessing)
CREATE POLICY "Only Owners can delete anomalies"
ON public.anomalies FOR DELETE
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

CREATE TRIGGER set_anomalies_updated_at
  BEFORE UPDATE ON public.anomalies
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
