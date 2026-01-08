-- Create OCR validation tables for Gemini-based validation
-- Story 2b-2: Gemini OCR Validation

-- Add validation_status column to documents table
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS validation_status text DEFAULT 'pending'
CHECK (validation_status IN ('pending', 'validated', 'requires_human_review'));

-- Create index for validation status queries
CREATE INDEX IF NOT EXISTS idx_documents_validation_status
ON public.documents(validation_status);

-- Create ocr_validation_log table for audit trail
CREATE TABLE IF NOT EXISTS public.ocr_validation_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  bbox_id uuid REFERENCES public.bounding_boxes(id) ON DELETE SET NULL,
  original_text text NOT NULL,
  corrected_text text NOT NULL,
  old_confidence float CHECK (old_confidence >= 0 AND old_confidence <= 1),
  new_confidence float CHECK (new_confidence >= 0 AND new_confidence <= 1),
  validation_type text NOT NULL CHECK (validation_type IN ('pattern', 'gemini', 'human')),
  reasoning text,
  created_at timestamptz DEFAULT now()
);

-- Index for document lookups on validation log
CREATE INDEX IF NOT EXISTS idx_validation_log_document
ON public.ocr_validation_log(document_id);

-- Index for bbox lookups
CREATE INDEX IF NOT EXISTS idx_validation_log_bbox
ON public.ocr_validation_log(bbox_id);

-- Enable RLS on validation log
ALTER TABLE public.ocr_validation_log ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can access validation logs for documents in their matters
CREATE POLICY "Users access own matter validation logs"
ON public.ocr_validation_log FOR ALL
USING (
  document_id IN (
    SELECT id FROM public.documents
    WHERE matter_id IN (
      SELECT matter_id FROM public.matter_attorneys
      WHERE user_id = auth.uid()
    )
  )
);

-- Create ocr_human_review table for human review queue
CREATE TABLE IF NOT EXISTS public.ocr_human_review (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  bbox_id uuid REFERENCES public.bounding_boxes(id) ON DELETE SET NULL,
  original_text text NOT NULL,
  context_before text,
  context_after text,
  page_number int NOT NULL CHECK (page_number >= 1),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'skipped')),
  corrected_text text,
  reviewed_by uuid REFERENCES auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz DEFAULT now()
);

-- Indexes for human review queries
CREATE INDEX IF NOT EXISTS idx_human_review_matter_status
ON public.ocr_human_review(matter_id, status);

CREATE INDEX IF NOT EXISTS idx_human_review_document
ON public.ocr_human_review(document_id);

CREATE INDEX IF NOT EXISTS idx_human_review_status
ON public.ocr_human_review(status);

-- Enable RLS on human review
ALTER TABLE public.ocr_human_review ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can access human reviews for their matters
CREATE POLICY "Users access own matter human reviews"
ON public.ocr_human_review FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
  )
);

-- Grant permissions for service role (backend uses service key)
GRANT ALL ON public.ocr_validation_log TO service_role;
GRANT ALL ON public.ocr_human_review TO service_role;

-- Comments for documentation
COMMENT ON TABLE public.ocr_validation_log IS 'Audit trail for all OCR corrections (pattern, Gemini, and human)';
COMMENT ON TABLE public.ocr_human_review IS 'Queue for words requiring human review due to very low OCR confidence';
COMMENT ON COLUMN public.documents.validation_status IS 'OCR validation status: pending, validated, or requires_human_review';
COMMENT ON COLUMN public.ocr_validation_log.validation_type IS 'Type of validation: pattern (regex), gemini (LLM), or human';
COMMENT ON COLUMN public.ocr_human_review.status IS 'Review status: pending, completed, or skipped';
