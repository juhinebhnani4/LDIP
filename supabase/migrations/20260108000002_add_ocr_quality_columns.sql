-- Add OCR quality assessment columns to documents table
-- Story 2b-3: Display OCR Quality Assessment

-- =============================================================================
-- ALTER TABLE: Add OCR quality columns
-- =============================================================================

-- Per-page confidence scores (array of floats)
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS ocr_confidence_per_page jsonb DEFAULT '[]';
COMMENT ON COLUMN public.documents.ocr_confidence_per_page IS 'Array of per-page OCR confidence scores (0-1)';

-- Quality status based on thresholds
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS ocr_quality_status text
CHECK (ocr_quality_status IS NULL OR ocr_quality_status IN ('good', 'fair', 'poor'));
COMMENT ON COLUMN public.documents.ocr_quality_status IS 'OCR quality level: good (>85%), fair (70-85%), poor (<70%)';

-- =============================================================================
-- RENAME: ocr_confidence -> ocr_confidence_avg for clarity
-- =============================================================================

-- Note: The column 'ocr_confidence' already exists from Story 2b-1
-- We keep it as-is since it already represents the average confidence
-- Just add an alias comment for clarity
COMMENT ON COLUMN public.documents.ocr_confidence IS 'Average OCR confidence score (0-1) across all words - same as ocr_confidence_avg';

-- =============================================================================
-- INDEX: For filtering by OCR quality status
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_documents_ocr_quality_status
ON public.documents(ocr_quality_status)
WHERE ocr_quality_status IS NOT NULL;

-- =============================================================================
-- UPDATE existing documents with null quality status based on ocr_confidence
-- =============================================================================

-- Set quality status for documents that already have OCR confidence
UPDATE public.documents
SET ocr_quality_status =
  CASE
    WHEN ocr_confidence >= 0.85 THEN 'good'
    WHEN ocr_confidence >= 0.70 THEN 'fair'
    WHEN ocr_confidence IS NOT NULL THEN 'poor'
    ELSE NULL
  END
WHERE ocr_confidence IS NOT NULL AND ocr_quality_status IS NULL;
