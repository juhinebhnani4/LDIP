-- Create Supabase Storage RLS policies for document files
-- This implements Layer 1 of 4-layer matter isolation for file storage (Story 1-7)
--
-- Storage bucket structure:
--   documents/{matter_id}/uploads/{filename}   - Case files
--   documents/{matter_id}/acts/{filename}      - Act/reference documents
--   documents/{matter_id}/exports/{filename}   - Generated exports (optional)
--
-- NOTE: This migration requires specific Supabase permissions.
-- The helper functions are placed in the PUBLIC schema (not storage schema)
-- because creating functions in the storage schema requires elevated permissions.

-- =============================================================================
-- BUCKET CREATION (done via Supabase dashboard)
-- =============================================================================

-- Note: Bucket creation should be done via the Supabase dashboard or CLI:
--   supabase storage create documents --public false
--
-- Or via dashboard: Storage > New Bucket > "documents" (private)
--
-- Bucket configuration:
--   - Name: documents
--   - Public: false
--   - File size limit: 500MB
--   - Allowed MIME types: application/pdf, application/zip

-- =============================================================================
-- HELPER FUNCTION: Extract matter_id from storage path
-- (Created in PUBLIC schema to avoid permission issues)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_matter_id_from_storage_path(path text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  path_parts text[];
  matter_id_str text;
BEGIN
  -- Path format: {matter_id}/uploads/... or {matter_id}/acts/...
  -- The bucket name is NOT included in the 'name' column of storage.objects
  path_parts := string_to_array(path, '/');

  -- Validate path structure (at least matter_id/subfolder/filename)
  IF array_length(path_parts, 1) < 3 THEN
    RETURN NULL;
  END IF;

  matter_id_str := path_parts[1];

  -- Validate UUID format
  IF matter_id_str !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN NULL;
  END IF;

  RETURN matter_id_str::uuid;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

COMMENT ON FUNCTION public.get_matter_id_from_storage_path IS 'Extracts matter_id from storage path for RLS validation';

-- Grant execute to authenticated users (needed for RLS policies)
GRANT EXECUTE ON FUNCTION public.get_matter_id_from_storage_path TO authenticated;

-- =============================================================================
-- HELPER FUNCTION: Check if user has access to matter for storage
-- =============================================================================

CREATE OR REPLACE FUNCTION public.user_has_storage_access(matter_uuid uuid, required_roles text[] DEFAULT ARRAY['owner', 'editor', 'viewer'])
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- Return false for NULL matter_id (invalid path)
  IF matter_uuid IS NULL THEN
    RETURN false;
  END IF;

  RETURN EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_uuid
    AND ma.user_id = auth.uid()
    AND ma.role = ANY(required_roles)
  );
END;
$$;

COMMENT ON FUNCTION public.user_has_storage_access IS 'Checks if current user has specified role(s) on a matter for storage access';

-- Grant execute to authenticated users (needed for RLS policies)
GRANT EXECUTE ON FUNCTION public.user_has_storage_access TO authenticated;

-- =============================================================================
-- HELPER FUNCTION: Validate storage document path structure
-- =============================================================================

CREATE OR REPLACE FUNCTION public.validate_storage_document_path(path text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  path_parts text[];
BEGIN
  path_parts := string_to_array(path, '/');

  -- Must have at least 3 parts: {matter_id}/{subfolder}/{filename}
  IF array_length(path_parts, 1) < 3 THEN
    RETURN false;
  END IF;

  -- First part (matter_id) must be a valid UUID
  IF path_parts[1] !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    RETURN false;
  END IF;

  -- Second part must be a valid subfolder
  IF path_parts[2] NOT IN ('uploads', 'acts', 'exports') THEN
    RETURN false;
  END IF;

  -- Third part (filename) must exist and not be empty
  IF path_parts[3] IS NULL OR path_parts[3] = '' THEN
    RETURN false;
  END IF;

  RETURN true;
END;
$$;

COMMENT ON FUNCTION public.validate_storage_document_path IS 'Validates document storage path structure';

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION public.validate_storage_document_path TO authenticated;

-- =============================================================================
-- STORAGE POLICIES: documents bucket
-- =============================================================================

-- Note: These policies apply to the 'documents' bucket
-- Supabase Storage uses storage.objects table for RLS
-- The 'name' column contains the path WITHOUT the bucket name

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Users can view documents from their matters" ON storage.objects;
DROP POLICY IF EXISTS "Editors and Owners can upload documents" ON storage.objects;
DROP POLICY IF EXISTS "Editors and Owners can update documents" ON storage.objects;
DROP POLICY IF EXISTS "Owners can delete documents" ON storage.objects;

-- Policy 1: Users can SELECT (download) files from matters they have access to
CREATE POLICY "Users can view documents from their matters"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'documents'
  AND public.user_has_storage_access(
    public.get_matter_id_from_storage_path(name),
    ARRAY['owner', 'editor', 'viewer']
  )
);

-- Policy 2: Editors and Owners can INSERT (upload) files to their matters
-- Also validates path structure to ensure proper folder organization
CREATE POLICY "Editors and Owners can upload documents"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'documents'
  AND public.validate_storage_document_path(name)
  AND public.user_has_storage_access(
    public.get_matter_id_from_storage_path(name),
    ARRAY['owner', 'editor']
  )
);

-- Policy 3: Editors and Owners can UPDATE file metadata
CREATE POLICY "Editors and Owners can update documents"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'documents'
  AND public.user_has_storage_access(
    public.get_matter_id_from_storage_path(name),
    ARRAY['owner', 'editor']
  )
);

-- Policy 4: Only Owners can DELETE files
CREATE POLICY "Owners can delete documents"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'documents'
  AND public.user_has_storage_access(
    public.get_matter_id_from_storage_path(name),
    ARRAY['owner']
  )
);

-- =============================================================================
-- NOTES FOR IMPLEMENTATION
-- =============================================================================

-- Bucket Setup (required before using these policies):
-- 1. Create bucket via Supabase Dashboard: Storage > New Bucket > "documents"
-- 2. Set bucket to private (public = false)
-- 3. Optionally set file size limit and MIME type restrictions
--
-- OR via Supabase CLI:
--   supabase storage create documents

-- File Path Convention:
-- Files must be uploaded to: {matter_id}/{subfolder}/{filename}
-- Where subfolder is one of: uploads, acts, exports
--
-- Example paths:
--   550e8400-e29b-41d4-a716-446655440000/uploads/case_file.pdf
--   550e8400-e29b-41d4-a716-446655440000/acts/indian_contract_act.pdf
--   550e8400-e29b-41d4-a716-446655440000/exports/timeline_export.pdf

-- Signed URL Generation (Python):
--   # User must have appropriate role via matter_attorneys
--   url = supabase.storage.from_('documents').create_signed_url(
--       f'{matter_id}/uploads/{filename}',
--       expires_in=3600  # 1 hour
--   )

-- Upload Example (Python):
--   # User must be editor or owner
--   result = supabase.storage.from_('documents').upload(
--       f'{matter_id}/uploads/{filename}',
--       file_content
--   )
