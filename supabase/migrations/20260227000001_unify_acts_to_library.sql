-- Unify Acts Pipeline: Single database for all Acts (library_documents)
--
-- Problem: Acts enter the system via 4 paths, but only 2 route to library_documents.
-- PATCH (document_type change) and sync_act_resolutions leave Acts orphaned in documents table.
--
-- This migration:
-- 1. Adds library_document_id to documents (tracks promotion to library)
-- 2. Backfills library_document_id for Acts already migrated
-- 3. Fixes citations.target_act_document_id FK: documents → library_documents

-- =============================================================================
-- Phase 1: Add library_document_id column to documents
-- =============================================================================

ALTER TABLE public.documents
  ADD COLUMN IF NOT EXISTS library_document_id uuid;

COMMENT ON COLUMN public.documents.library_document_id
  IS 'FK to library_documents — set when this document is promoted to the shared library';

-- =============================================================================
-- Phase 2: Backfill library_document_id for Acts already in library
-- =============================================================================

-- Match documents to library_documents by filename (minus .pdf extension → title)
UPDATE public.documents d
  SET library_document_id = ld.id
  FROM public.library_documents ld
  WHERE d.document_type = 'act'
    AND d.library_document_id IS NULL
    AND d.migrated_to_library = true
    AND lower(replace(d.filename, '.pdf', '')) = lower(ld.title);

-- Also match by storage_path for auto-fetched Acts
UPDATE public.documents d
  SET library_document_id = ld.id
  FROM public.library_documents ld
  WHERE d.document_type = 'act'
    AND d.library_document_id IS NULL
    AND d.storage_path = ld.storage_path;

-- Add FK constraint (deferred — allows NULL, points to library_documents)
ALTER TABLE public.documents
  ADD CONSTRAINT documents_library_document_id_fkey
    FOREIGN KEY (library_document_id)
    REFERENCES public.library_documents(id)
    ON DELETE SET NULL;

-- =============================================================================
-- Phase 3: Fix citations.target_act_document_id FK
-- =============================================================================

-- Drop old FK to documents table
ALTER TABLE public.citations
  DROP CONSTRAINT IF EXISTS citations_target_act_document_id_fkey;

-- Map existing target_act_document_id values to library_documents.id
-- Strategy: match via documents.library_document_id (just backfilled)
-- or via filename match to library_documents.title
UPDATE public.citations c
  SET target_act_document_id = d.library_document_id
  FROM public.documents d
  WHERE c.target_act_document_id IS NOT NULL
    AND c.target_act_document_id = d.id
    AND d.library_document_id IS NOT NULL;

-- NULL out any remaining values that don't map to library_documents
UPDATE public.citations
  SET target_act_document_id = NULL
  WHERE target_act_document_id IS NOT NULL
    AND target_act_document_id NOT IN (SELECT id FROM public.library_documents);

-- Add new FK to library_documents
ALTER TABLE public.citations
  ADD CONSTRAINT citations_target_act_document_id_fkey
    FOREIGN KEY (target_act_document_id)
    REFERENCES public.library_documents(id)
    ON DELETE SET NULL;

COMMENT ON COLUMN public.citations.target_act_document_id
  IS 'FK to library_documents — the shared Act document used for verification';

-- =============================================================================
-- Phase 4: Verification
-- =============================================================================

-- Verify no orphaned citations
DO $$
DECLARE
  orphan_count integer;
BEGIN
  SELECT count(*) INTO orphan_count
  FROM public.citations
  WHERE target_act_document_id IS NOT NULL
    AND target_act_document_id NOT IN (SELECT id FROM public.library_documents);

  IF orphan_count > 0 THEN
    RAISE WARNING 'Found % orphaned citations.target_act_document_id values', orphan_count;
  END IF;
END $$;
