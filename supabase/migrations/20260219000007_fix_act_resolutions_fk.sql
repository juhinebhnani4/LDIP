-- Fix act_resolutions.act_document_id FK to reference library_documents instead of documents
--
-- BUG-LT3-E: act_resolutions_act_document_id_fkey FK violation
--
-- Root cause: The act_resolutions table was created (20260106000007) before the library
-- system (20260126000001). When acts were migrated to library_documents, the FK on
-- act_document_id was never updated. The backend now stores library_document IDs in
-- act_document_id, but the FK still references the documents table, causing violations.

-- Drop the old FK constraint (references documents table)
ALTER TABLE public.act_resolutions
  DROP CONSTRAINT IF EXISTS act_resolutions_act_document_id_fkey;

-- Clean up orphaned references: NULL out any act_document_id values that point to
-- the old documents table and don't exist in library_documents
UPDATE public.act_resolutions
  SET act_document_id = NULL
  WHERE act_document_id IS NOT NULL
    AND act_document_id NOT IN (SELECT id FROM public.library_documents);

-- Add the corrected FK constraint (references library_documents table)
ALTER TABLE public.act_resolutions
  ADD CONSTRAINT act_resolutions_act_document_id_fkey
    FOREIGN KEY (act_document_id)
    REFERENCES public.library_documents(id)
    ON DELETE SET NULL;

-- Update the column comment to reflect the change
COMMENT ON COLUMN public.act_resolutions.act_document_id
  IS 'FK to library_documents — the shared Act document (if uploaded or fetched from India Code)';
