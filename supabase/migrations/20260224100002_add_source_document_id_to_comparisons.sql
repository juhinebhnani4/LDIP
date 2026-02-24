-- Stage 2.3: Incremental Contradiction Detection
-- Adds source_document_id to statement_comparisons so we can track which document
-- triggered each comparison. This enables incremental detection: when doc B is uploaded,
-- only pairs involving doc B's chunks are compared (not the entire matter).

ALTER TABLE public.statement_comparisons
    ADD COLUMN IF NOT EXISTS source_document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL;

-- Index for efficient lookups by source document
CREATE INDEX IF NOT EXISTS idx_sc_source_doc
    ON public.statement_comparisons(source_document_id);

COMMENT ON COLUMN public.statement_comparisons.source_document_id IS
    'Document that triggered this comparison (for incremental contradiction detection)';
