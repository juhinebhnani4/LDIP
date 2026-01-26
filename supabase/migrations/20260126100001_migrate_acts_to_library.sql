-- Migrate existing Acts from documents table to library_documents
-- This implements the Shared Legal Library architecture where:
-- - Case Files stay in the documents table (matter-specific)
-- - Acts/Statutes go to library_documents (shared, linked to matters)
--
-- This migration is IDEMPOTENT - safe to run multiple times

-- =============================================================================
-- STEP 1: Migrate unique Acts to library_documents
-- =============================================================================

-- First, collect all unique Acts by title (dedup across matters)
-- Then insert them into library_documents

DO $$
DECLARE
  r RECORD;
  v_library_doc_id uuid;
  v_existing_id uuid;
  v_count_migrated integer := 0;
  v_count_linked integer := 0;
BEGIN
  RAISE NOTICE 'Starting migration of Acts to library_documents...';

  -- Iterate over all unique Acts in the documents table
  FOR r IN (
    SELECT DISTINCT ON (COALESCE(NULLIF(trim(d.filename), ''), d.id::text))
      d.id AS document_id,
      d.matter_id,
      d.filename,
      d.storage_path,
      d.file_size,
      d.page_count,
      d.document_type,
      d.source,
      d.india_code_url,
      d.status,
      d.uploaded_by,
      d.created_at,
      -- Extract title from filename (remove .pdf extension)
      regexp_replace(d.filename, '\.pdf$', '', 'i') AS title
    FROM public.documents d
    WHERE d.document_type = 'act'
      AND d.deleted_at IS NULL  -- Only non-deleted documents
    ORDER BY COALESCE(NULLIF(trim(d.filename), ''), d.id::text), d.created_at ASC
  ) LOOP
    -- Check if this Act already exists in library_documents (by title similarity)
    SELECT id INTO v_existing_id
    FROM public.library_documents
    WHERE lower(title) = lower(r.title)
       OR lower(filename) = lower(r.filename)
    LIMIT 1;

    IF v_existing_id IS NOT NULL THEN
      -- Act already in library, just create link
      v_library_doc_id := v_existing_id;
      RAISE NOTICE 'Act "%" already exists in library, creating link only', r.title;
    ELSE
      -- Insert new library document
      INSERT INTO public.library_documents (
        filename,
        storage_path,
        file_size,
        page_count,
        document_type,
        title,
        source,
        source_url,
        status,
        added_by,
        created_at,
        updated_at
      )
      VALUES (
        r.filename,
        r.storage_path,
        COALESCE(r.file_size, 0),
        r.page_count,
        'act',  -- library uses 'act' type
        r.title,
        CASE r.source
          WHEN 'auto_fetched' THEN 'india_code'
          WHEN 'system' THEN 'india_code'
          ELSE 'user_upload'
        END,
        r.india_code_url,
        CASE r.status
          WHEN 'completed' THEN 'completed'
          WHEN 'processing' THEN 'processing'
          WHEN 'failed' THEN 'failed'
          ELSE 'pending'
        END,
        r.uploaded_by,
        r.created_at,
        now()
      )
      RETURNING id INTO v_library_doc_id;

      v_count_migrated := v_count_migrated + 1;
      RAISE NOTICE 'Migrated Act "%" to library: %', r.title, v_library_doc_id;
    END IF;

    -- Now create links for ALL matters that have this Act
    INSERT INTO public.matter_library_links (matter_id, library_document_id, linked_by, linked_at)
    SELECT DISTINCT
      d.matter_id,
      v_library_doc_id,
      COALESCE(d.uploaded_by, (SELECT id FROM auth.users LIMIT 1)),  -- Use any user if null
      d.created_at
    FROM public.documents d
    WHERE (lower(d.filename) = lower(r.filename) OR d.id = r.document_id)
      AND d.document_type = 'act'
      AND d.deleted_at IS NULL
      AND NOT EXISTS (
        SELECT 1 FROM public.matter_library_links mll
        WHERE mll.matter_id = d.matter_id
          AND mll.library_document_id = v_library_doc_id
      );

    GET DIAGNOSTICS v_count_linked = ROW_COUNT;
    IF v_count_linked > 0 THEN
      RAISE NOTICE 'Created % matter links for Act "%"', v_count_linked, r.title;
    END IF;
  END LOOP;

  RAISE NOTICE 'Migration complete: % Acts migrated to library', v_count_migrated;
END;
$$;

-- =============================================================================
-- STEP 2: Migrate chunks from matter chunks to library_chunks
-- =============================================================================

DO $$
DECLARE
  r RECORD;
  v_chunk_count integer := 0;
BEGIN
  RAISE NOTICE 'Starting migration of chunks to library_chunks...';

  -- For each library document that was migrated from documents
  FOR r IN (
    SELECT
      ld.id AS library_document_id,
      ld.storage_path,
      d.id AS original_document_id
    FROM public.library_documents ld
    JOIN public.documents d ON d.storage_path = ld.storage_path
    WHERE d.document_type = 'act'
      AND d.deleted_at IS NULL
  ) LOOP
    -- Check if chunks already migrated for this library document
    IF EXISTS (
      SELECT 1 FROM public.library_chunks lc
      WHERE lc.library_document_id = r.library_document_id
    ) THEN
      CONTINUE;
    END IF;

    -- Copy chunks from the original document to library_chunks
    INSERT INTO public.library_chunks (
      library_document_id,
      chunk_index,
      content,
      embedding,
      page_number,
      token_count,
      chunk_type,
      created_at
    )
    SELECT
      r.library_document_id,
      c.chunk_index,
      c.content,
      c.embedding,
      c.page_number,
      c.token_count,
      c.chunk_type,
      c.created_at
    FROM public.chunks c
    WHERE c.document_id = r.original_document_id
      AND c.parent_chunk_id IS NULL;  -- Only parent chunks for now

    GET DIAGNOSTICS v_chunk_count = ROW_COUNT;
    IF v_chunk_count > 0 THEN
      RAISE NOTICE 'Migrated % chunks for library document %', v_chunk_count, r.library_document_id;
    END IF;
  END LOOP;

  RAISE NOTICE 'Chunk migration complete';
END;
$$;

-- =============================================================================
-- STEP 3: Add migrated_to_library flag to documents table (for filtering)
-- =============================================================================

DO $$
BEGIN
  -- Add column if not exists
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'documents'
    AND column_name = 'migrated_to_library'
  ) THEN
    ALTER TABLE public.documents
    ADD COLUMN migrated_to_library boolean DEFAULT false;

    RAISE NOTICE 'Added migrated_to_library column';
  END IF;
END;
$$;

-- Mark all Acts as migrated
UPDATE public.documents
SET migrated_to_library = true
WHERE document_type = 'act'
  AND deleted_at IS NULL
  AND migrated_to_library IS DISTINCT FROM true;

-- =============================================================================
-- STEP 4: Verification counts
-- =============================================================================

DO $$
DECLARE
  v_library_docs integer;
  v_library_links integer;
  v_library_chunks integer;
  v_migrated_docs integer;
BEGIN
  SELECT COUNT(*) INTO v_library_docs FROM public.library_documents;
  SELECT COUNT(*) INTO v_library_links FROM public.matter_library_links;
  SELECT COUNT(*) INTO v_library_chunks FROM public.library_chunks;
  SELECT COUNT(*) INTO v_migrated_docs FROM public.documents WHERE migrated_to_library = true;

  RAISE NOTICE '=== Migration Summary ===';
  RAISE NOTICE 'Library documents: %', v_library_docs;
  RAISE NOTICE 'Matter-library links: %', v_library_links;
  RAISE NOTICE 'Library chunks: %', v_library_chunks;
  RAISE NOTICE 'Documents marked as migrated: %', v_migrated_docs;
END;
$$;
