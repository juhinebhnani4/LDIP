-- Add reading_order_index column to bounding_boxes table
-- This enables ordered retrieval of bounding boxes for text highlighting
-- Part of Story 2b-4: Bounding Boxes Table Enhancement

-- =============================================================================
-- Add reading_order_index column
-- =============================================================================

ALTER TABLE public.bounding_boxes
ADD COLUMN reading_order_index integer;

-- =============================================================================
-- Add composite index for ordered page retrieval
-- =============================================================================

-- Index for efficient ordered retrieval by document, page, and reading order
CREATE INDEX idx_bboxes_page_order ON public.bounding_boxes(
    document_id, page_number, reading_order_index
);

-- =============================================================================
-- Add CHECK constraint for non-negative reading order
-- =============================================================================

ALTER TABLE public.bounding_boxes
ADD CONSTRAINT bboxes_reading_order_positive
CHECK (reading_order_index IS NULL OR reading_order_index >= 0);

-- =============================================================================
-- Column documentation
-- =============================================================================

COMMENT ON COLUMN public.bounding_boxes.reading_order_index IS
'Reading order within page (0-indexed, top-to-bottom, left-to-right). NULL for legacy boxes without reading order.';
