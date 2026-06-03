-- GAP-11: Add library_document_id to llm_costs for library document cost tracking
-- library doc UUIDs can't go in document_id (FK to documents table)

ALTER TABLE public.llm_costs
    ADD COLUMN IF NOT EXISTS library_document_id UUID
    REFERENCES public.library_documents(id) ON DELETE SET NULL;

-- Partial index: only non-NULL rows (most rows will be NULL)
CREATE INDEX IF NOT EXISTS idx_llm_costs_library_document
ON public.llm_costs(library_document_id, created_at DESC)
WHERE library_document_id IS NOT NULL;

COMMENT ON COLUMN public.llm_costs.library_document_id IS
    'Library document UUID for cost attribution. Mutually exclusive with document_id.';
