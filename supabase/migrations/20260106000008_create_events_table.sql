-- Create events table for Timeline Construction Engine
-- This implements Layer 1 of 4-layer matter isolation (Story 1-7)

-- =============================================================================
-- TABLE: events - Timeline events extracted from documents
-- =============================================================================

CREATE TABLE public.events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid REFERENCES public.documents(id) ON DELETE SET NULL,

  -- Event timing
  event_date date NOT NULL,
  event_date_precision text NOT NULL DEFAULT 'day'
    CHECK (event_date_precision IN ('day', 'month', 'year', 'approximate')),
  event_date_text text, -- Original date text from document (e.g., "on or about March 2023")

  -- Event details
  event_type text NOT NULL,
  description text NOT NULL,
  entities_involved uuid[], -- References to identity_nodes

  -- Source references
  source_page integer,
  source_bbox_ids uuid[],

  -- Confidence and metadata
  confidence float CHECK (confidence >= 0 AND confidence <= 1),
  is_manual boolean DEFAULT false, -- True if manually added by attorney
  created_by uuid REFERENCES auth.users(id),

  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for timeline queries
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_events_matter_id ON public.events(matter_id);
CREATE INDEX idx_events_document_id ON public.events(document_id);
CREATE INDEX idx_events_event_type ON public.events(event_type);
CREATE INDEX idx_events_created_by ON public.events(created_by);

-- Timeline ordering (most important index)
CREATE INDEX idx_events_matter_date ON public.events(matter_id, event_date);

-- Precision-based filtering
CREATE INDEX idx_events_precision ON public.events(event_date_precision);

-- Manual vs extracted filtering
CREATE INDEX idx_events_manual ON public.events(matter_id, is_manual);

-- GIN indexes for array columns
CREATE INDEX idx_events_entities ON public.events USING GIN (entities_involved);
CREATE INDEX idx_events_source_bboxes ON public.events USING GIN (source_bbox_ids);

-- Composite index for common query patterns
CREATE INDEX idx_events_matter_type_date ON public.events(matter_id, event_type, event_date);

-- Text search on description
CREATE INDEX idx_events_description ON public.events USING GIN (to_tsvector('english', description));

-- Comments
COMMENT ON TABLE public.events IS 'Timeline events extracted from documents for chronological analysis';
COMMENT ON COLUMN public.events.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.events.document_id IS 'Source document (null for manually added events)';
COMMENT ON COLUMN public.events.event_date IS 'Event date (use precision field to interpret)';
COMMENT ON COLUMN public.events.event_date_precision IS 'day (exact), month, year, or approximate';
COMMENT ON COLUMN public.events.event_date_text IS 'Original date text from document for verification';
COMMENT ON COLUMN public.events.event_type IS 'Category of event (filing, hearing, contract, communication, etc.)';
COMMENT ON COLUMN public.events.description IS 'Human-readable event description';
COMMENT ON COLUMN public.events.entities_involved IS 'Array of identity_node IDs involved in this event';
COMMENT ON COLUMN public.events.source_page IS 'Page number in source document';
COMMENT ON COLUMN public.events.source_bbox_ids IS 'Bounding boxes for highlighting source text';
COMMENT ON COLUMN public.events.confidence IS 'Extraction confidence (0-1) for AI-extracted events';
COMMENT ON COLUMN public.events.is_manual IS 'True if attorney manually added this event';
COMMENT ON COLUMN public.events.created_by IS 'User who created/extracted this event';

-- =============================================================================
-- RLS POLICIES: events table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT events from matters where they have any role
CREATE POLICY "Users can view events from their matters"
ON public.events FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT events (timeline engine or manual)
CREATE POLICY "Editors and Owners can insert events"
ON public.events FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE events
CREATE POLICY "Editors and Owners can update events"
ON public.events FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE events
CREATE POLICY "Only Owners can delete events"
ON public.events FOR DELETE
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

CREATE TRIGGER set_events_updated_at
  BEFORE UPDATE ON public.events
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();
