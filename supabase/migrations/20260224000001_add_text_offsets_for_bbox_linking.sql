-- BUG-BBOX-0: Add text offset columns for deterministic bbox-to-chunk linking
-- Instead of fuzzy text matching, use exact character offset intervals from OCR.

ALTER TABLE public.bounding_boxes
  ADD COLUMN text_start_offset integer,
  ADD COLUMN text_end_offset integer;

ALTER TABLE public.chunks
  ADD COLUMN text_start_offset integer,
  ADD COLUMN text_end_offset integer;

-- Partial indexes for offset-based interval queries
CREATE INDEX idx_bboxes_text_offsets
  ON public.bounding_boxes(document_id, text_start_offset, text_end_offset)
  WHERE text_start_offset IS NOT NULL;

CREATE INDEX idx_chunks_text_offsets
  ON public.chunks(document_id, text_start_offset, text_end_offset)
  WHERE text_start_offset IS NOT NULL;
