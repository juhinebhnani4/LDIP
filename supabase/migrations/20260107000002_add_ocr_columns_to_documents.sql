-- Add OCR-specific columns to documents table
-- Story 2b-1: Google Document AI OCR Integration

-- =============================================================================
-- ALTER TABLE: Add OCR result columns
-- =============================================================================

-- Extracted text from OCR processing
ALTER TABLE public.documents ADD COLUMN extracted_text TEXT;
COMMENT ON COLUMN public.documents.extracted_text IS 'Full OCR-extracted text content';

-- OCR confidence score (0-1 average across all pages)
ALTER TABLE public.documents ADD COLUMN ocr_confidence FLOAT;
COMMENT ON COLUMN public.documents.ocr_confidence IS 'Average OCR confidence score (0-1)';

-- Image quality score from Document AI
ALTER TABLE public.documents ADD COLUMN ocr_quality_score FLOAT;
COMMENT ON COLUMN public.documents.ocr_quality_score IS 'Document AI image quality score (0-1)';

-- Error details when OCR fails
ALTER TABLE public.documents ADD COLUMN ocr_error TEXT;
COMMENT ON COLUMN public.documents.ocr_error IS 'Error details if OCR processing failed';

-- Retry count for failed OCR attempts
ALTER TABLE public.documents ADD COLUMN ocr_retry_count INTEGER DEFAULT 0;
COMMENT ON COLUMN public.documents.ocr_retry_count IS 'Number of OCR retry attempts';

-- =============================================================================
-- INDEX: Full-text search on extracted text
-- =============================================================================

-- GIN index for full-text search on extracted content
CREATE INDEX idx_documents_extracted_text
ON public.documents USING GIN (to_tsvector('english', COALESCE(extracted_text, '')));

-- Index for filtering by OCR confidence (e.g., finding low-confidence documents)
CREATE INDEX idx_documents_ocr_confidence ON public.documents(ocr_confidence)
WHERE ocr_confidence IS NOT NULL;

-- =============================================================================
-- UPDATE STATUS CHECK: Add ocr_complete and ocr_failed states
-- =============================================================================

-- Drop the existing check constraint
ALTER TABLE public.documents DROP CONSTRAINT IF EXISTS documents_status_check;

-- Add new check constraint with expanded status values
ALTER TABLE public.documents ADD CONSTRAINT documents_status_check
CHECK (status IN ('pending', 'processing', 'ocr_complete', 'ocr_failed', 'completed', 'failed'));

-- Update comment to reflect new states
COMMENT ON COLUMN public.documents.status IS 'Processing status: pending, processing, ocr_complete, ocr_failed, completed, failed';
