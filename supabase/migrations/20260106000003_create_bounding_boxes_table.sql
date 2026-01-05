-- Create bounding_boxes table for OCR text positioning
-- This implements Layer 1 of 4-layer matter isolation (Story 1-7)

-- =============================================================================
-- TABLE: bounding_boxes - OCR text position data for highlighting
-- =============================================================================

CREATE TABLE public.bounding_boxes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  page_number integer NOT NULL,
  x float NOT NULL,
  y float NOT NULL,
  width float NOT NULL,
  height float NOT NULL,
  text text NOT NULL,
  confidence float,
  created_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for page rendering and text lookup
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_bboxes_matter_id ON public.bounding_boxes(matter_id);
CREATE INDEX idx_bboxes_document_id ON public.bounding_boxes(document_id);

-- Composite index for page-based queries (most common access pattern)
CREATE INDEX idx_bboxes_document_page ON public.bounding_boxes(document_id, page_number);

-- Full composite for matter-scoped page rendering
CREATE INDEX idx_bboxes_matter_doc_page ON public.bounding_boxes(matter_id, document_id, page_number);

-- Text search for finding specific text locations
CREATE INDEX idx_bboxes_text ON public.bounding_boxes USING GIN (to_tsvector('english', text));

-- Comments
COMMENT ON TABLE public.bounding_boxes IS 'OCR bounding boxes for text positioning and highlighting';
COMMENT ON COLUMN public.bounding_boxes.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.bounding_boxes.document_id IS 'FK to documents - source document';
COMMENT ON COLUMN public.bounding_boxes.page_number IS 'Page number (1-indexed) within document';
COMMENT ON COLUMN public.bounding_boxes.x IS 'X coordinate (percentage of page width, 0-100)';
COMMENT ON COLUMN public.bounding_boxes.y IS 'Y coordinate (percentage of page height, 0-100)';
COMMENT ON COLUMN public.bounding_boxes.width IS 'Width (percentage of page width)';
COMMENT ON COLUMN public.bounding_boxes.height IS 'Height (percentage of page height)';
COMMENT ON COLUMN public.bounding_boxes.text IS 'OCR-extracted text content';
COMMENT ON COLUMN public.bounding_boxes.confidence IS 'OCR confidence score (0-1)';

-- =============================================================================
-- RLS POLICIES: bounding_boxes table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.bounding_boxes ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT bounding boxes from matters where they have any role
CREATE POLICY "Users can view bounding boxes from their matters"
ON public.bounding_boxes FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT bounding boxes (via OCR pipeline)
CREATE POLICY "Editors and Owners can insert bounding boxes"
ON public.bounding_boxes FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE bounding boxes (corrections)
CREATE POLICY "Editors and Owners can update bounding boxes"
ON public.bounding_boxes FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE bounding boxes
CREATE POLICY "Only Owners can delete bounding boxes"
ON public.bounding_boxes FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);
