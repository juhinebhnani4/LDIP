ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS cause_title text;
COMMENT ON COLUMN public.matters.cause_title IS 'Extracted party listing (cause title) from the application document. Injected as permanent context for RAG generation.';
