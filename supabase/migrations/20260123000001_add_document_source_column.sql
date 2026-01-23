-- Add source column to documents table to distinguish upload sources
-- This enables tracking of auto-fetched Acts from India Code
--
-- This migration is IDEMPOTENT - safe to run multiple times

-- =============================================================================
-- STEP 1: Add source column (if not exists)
-- =============================================================================

DO $$
BEGIN
  -- Check if source column already exists
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'documents'
    AND column_name = 'source'
  ) THEN
    -- Source indicates where the document came from
    ALTER TABLE public.documents
    ADD COLUMN source text NOT NULL DEFAULT 'user_upload'
    CHECK (source IN ('user_upload', 'auto_fetched', 'system'));

    RAISE NOTICE 'Added source column to documents table';
  ELSE
    RAISE NOTICE 'source column already exists, skipping';
  END IF;
END;
$$;

COMMENT ON COLUMN public.documents.source IS 'Document source: user_upload (manual), auto_fetched (India Code), system (internal)';

-- =============================================================================
-- STEP 2: Make uploaded_by nullable for system-sourced documents
-- =============================================================================

-- For auto-fetched documents, there's no user who uploaded them
-- First check if there's a NOT NULL constraint
DO $$
DECLARE
  v_is_nullable text;
BEGIN
  SELECT is_nullable INTO v_is_nullable
  FROM information_schema.columns
  WHERE table_schema = 'public'
  AND table_name = 'documents'
  AND column_name = 'uploaded_by';

  IF v_is_nullable = 'NO' THEN
    ALTER TABLE public.documents
    ALTER COLUMN uploaded_by DROP NOT NULL;
    RAISE NOTICE 'Made uploaded_by nullable';
  ELSE
    RAISE NOTICE 'uploaded_by is already nullable, skipping';
  END IF;
END;
$$;

-- Add check constraint to ensure user_upload documents have uploaded_by
-- But allow NULL for auto_fetched and system sources
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.constraint_column_usage
    WHERE table_schema = 'public'
    AND table_name = 'documents'
    AND constraint_name = 'chk_documents_uploaded_by_required'
  ) THEN
    ALTER TABLE public.documents
    ADD CONSTRAINT chk_documents_uploaded_by_required
    CHECK (
      (source = 'user_upload' AND uploaded_by IS NOT NULL)
      OR source IN ('auto_fetched', 'system')
    );
    RAISE NOTICE 'Added check constraint chk_documents_uploaded_by_required';
  ELSE
    RAISE NOTICE 'chk_documents_uploaded_by_required constraint already exists, skipping';
  END IF;
END;
$$;

-- =============================================================================
-- STEP 3: Add india_code_url for reference (if not exists)
-- =============================================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'documents'
    AND column_name = 'india_code_url'
  ) THEN
    ALTER TABLE public.documents
    ADD COLUMN india_code_url text;
    RAISE NOTICE 'Added india_code_url column';
  ELSE
    RAISE NOTICE 'india_code_url column already exists, skipping';
  END IF;
END;
$$;

COMMENT ON COLUMN public.documents.india_code_url IS 'Original URL from India Code for auto-fetched Acts';

-- =============================================================================
-- STEP 4: Index for efficient source filtering (if not exists)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_documents_source ON public.documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_matter_source ON public.documents(matter_id, source);

-- =============================================================================
-- STEP 5: Update RLS policies for auto-fetched documents
-- =============================================================================

-- Auto-fetched documents should be viewable by anyone with matter access
-- No changes needed - existing SELECT policy covers this

-- Auto-fetched documents should not be deletable by users (system-managed)
-- Add a new policy to restrict deletion of auto-fetched documents
DO $$
BEGIN
  -- Drop existing policy if it exists (to make this idempotent)
  DROP POLICY IF EXISTS "Prevent deletion of auto-fetched documents" ON public.documents;

  CREATE POLICY "Prevent deletion of auto-fetched documents"
  ON public.documents FOR DELETE
  USING (
    source != 'auto_fetched'
    OR matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role = 'owner'
    )
  );
  RAISE NOTICE 'Created/updated RLS policy for auto-fetched documents';
END;
$$;

-- Note: The above policy allows owners to still delete auto-fetched docs if needed

-- =============================================================================
-- STEP 6: Data Migration - Create document records for existing auto-fetched Acts
-- =============================================================================

-- For any act_resolutions that have resolution_status='auto_fetched' but no
-- act_document_id, create document records linking to the cached PDF.
-- This backfills documents for Acts that were auto-fetched before this migration.

DO $$
DECLARE
  r RECORD;
  v_doc_id uuid;
  v_file_size bigint;
  v_filename text;
  v_count integer := 0;
BEGIN
  -- Check if act_validation_cache table exists
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'act_validation_cache'
  ) THEN
    RAISE NOTICE 'act_validation_cache table does not exist, skipping data migration';
    RETURN;
  END IF;

  -- Find all auto_fetched resolutions with cached PDFs but no document record
  FOR r IN (
    SELECT DISTINCT
      ar.matter_id,
      ar.act_name_normalized,
      avc.act_name_canonical,
      avc.cached_storage_path,
      avc.india_code_url
    FROM public.act_resolutions ar
    JOIN public.act_validation_cache avc
      ON ar.validation_cache_id = avc.id
    WHERE ar.resolution_status = 'auto_fetched'
      AND ar.act_document_id IS NULL
      AND avc.cached_storage_path IS NOT NULL
  ) LOOP
    -- Generate filename from canonical name or normalized name
    v_filename := COALESCE(r.act_name_canonical, r.act_name_normalized) || '.pdf';

    -- Try to get file size from storage (default to 0 if not available)
    -- Note: We can't query storage from SQL, so we'll set a placeholder
    v_file_size := 0;

    -- Create document record
    INSERT INTO public.documents (
      id,
      matter_id,
      filename,
      storage_path,
      file_size,
      document_type,
      is_reference_material,
      source,
      uploaded_by,
      india_code_url,
      status,
      created_at,
      updated_at
    )
    VALUES (
      gen_random_uuid(),
      r.matter_id,
      v_filename,
      r.cached_storage_path,
      v_file_size,
      'act',
      true,
      'auto_fetched',
      NULL,  -- No user for auto-fetched
      r.india_code_url,
      'completed',
      now(),
      now()
    )
    RETURNING id INTO v_doc_id;

    -- Update act_resolutions to link to the new document
    UPDATE public.act_resolutions
    SET act_document_id = v_doc_id
    WHERE matter_id = r.matter_id
      AND act_name_normalized = r.act_name_normalized
      AND act_document_id IS NULL;

    v_count := v_count + 1;
    RAISE NOTICE 'Created document % for auto-fetched Act: % in matter %',
      v_doc_id, r.act_name_normalized, r.matter_id;
  END LOOP;

  RAISE NOTICE 'Data migration created % document records for auto-fetched Acts', v_count;
END;
$$;

-- =============================================================================
-- STEP 7: Verify data migration
-- =============================================================================

-- Log counts for verification
DO $$
DECLARE
  v_auto_fetched_docs integer;
  v_orphaned_resolutions integer;
BEGIN
  -- Count auto-fetched documents created
  SELECT COUNT(*) INTO v_auto_fetched_docs
  FROM public.documents
  WHERE source = 'auto_fetched';

  -- Check if act_validation_cache exists before querying
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'act_validation_cache'
  ) THEN
    -- Count any remaining orphaned resolutions (should be 0 after migration)
    SELECT COUNT(*) INTO v_orphaned_resolutions
    FROM public.act_resolutions ar
    JOIN public.act_validation_cache avc ON ar.validation_cache_id = avc.id
    WHERE ar.resolution_status = 'auto_fetched'
      AND ar.act_document_id IS NULL
      AND avc.cached_storage_path IS NOT NULL;
  ELSE
    v_orphaned_resolutions := 0;
  END IF;

  RAISE NOTICE 'Migration complete: % auto-fetched documents total, % orphaned resolutions remaining',
    v_auto_fetched_docs, v_orphaned_resolutions;
END;
$$;
