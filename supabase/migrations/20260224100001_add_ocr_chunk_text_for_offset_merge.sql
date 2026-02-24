-- Add ocr_full_text column to document_ocr_chunks for proper text merging
-- Required by BUG-BBOX-0: offset-based bbox linking needs document-relative offsets,
-- which requires knowing per-chunk text lengths during finalization.

ALTER TABLE public.document_ocr_chunks
  ADD COLUMN IF NOT EXISTS ocr_full_text text;

COMMENT ON COLUMN public.document_ocr_chunks.ocr_full_text IS 'Full OCR text for this chunk, stored for proper text merging and bbox offset adjustment during finalization';

-- RPC function: batch-adjust bbox text offsets for a page range
-- Used by finalize_chunked_document to convert per-chunk offsets to document-relative
CREATE OR REPLACE FUNCTION public.adjust_bbox_text_offsets(
  p_document_id uuid,
  p_page_start integer,
  p_page_end integer,
  p_offset_delta integer
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  affected integer;
BEGIN
  UPDATE public.bounding_boxes
  SET text_start_offset = text_start_offset + p_offset_delta,
      text_end_offset = text_end_offset + p_offset_delta
  WHERE document_id = p_document_id
    AND page_number >= p_page_start
    AND page_number <= p_page_end
    AND text_start_offset IS NOT NULL;

  GET DIAGNOSTICS affected = ROW_COUNT;
  RETURN affected;
END;
$$;

COMMENT ON FUNCTION public.adjust_bbox_text_offsets IS 'Batch-adjust bbox text offsets for a page range during finalization (BUG-BBOX-0)';
GRANT EXECUTE ON FUNCTION public.adjust_bbox_text_offsets TO service_role;
