-- Reasoning Archive Storage Bucket (Story 4.2)
-- Epic 4: Legal Defensibility (Gap Remediation)
-- This migration creates the Supabase Storage bucket for cold storage of reasoning traces

-- =============================================================================
-- BUCKET: reasoning-archive - Cold storage for old reasoning traces
-- =============================================================================

-- Create the bucket (this is done via Supabase Storage API, not SQL)
-- The bucket should be created with the following settings:
-- - Name: reasoning-archive
-- - Public: false (private bucket)
-- - File size limit: 10MB (gzipped JSON files are small)
-- - Allowed MIME types: application/gzip, application/json

-- Note: Bucket creation is typically done via:
-- 1. Supabase Dashboard -> Storage -> Create new bucket
-- 2. Or via Supabase JS client: supabase.storage.createBucket('reasoning-archive', {...})

-- This SQL file documents the expected bucket policies for RLS enforcement

-- =============================================================================
-- RLS POLICIES: reasoning-archive bucket
-- =============================================================================

-- Policy 1: Service role can upload (archival task)
-- Applied automatically as service role bypasses RLS

-- Policy 2: Authenticated users can download from their matters
-- This requires matter ownership validation at application layer
-- since Storage policies cannot reference custom tables directly

-- For reference, the bucket policies should be:
-- INSERT: Only service role (background archival task)
-- SELECT: Authenticated users (validated via matter ownership in app layer)
-- DELETE: Only service role (cleanup tasks)

-- =============================================================================
-- DOCUMENTATION: Bucket Setup Instructions
-- =============================================================================

-- To complete this migration, create the bucket via Supabase Dashboard:
--
-- 1. Go to Storage in Supabase Dashboard
-- 2. Click "Create new bucket"
-- 3. Settings:
--    - Name: reasoning-archive
--    - Public: OFF (private)
--    - File size limit: 10485760 (10MB)
--    - Allowed MIME types: application/gzip
--
-- 4. Bucket policies (via Dashboard -> Storage -> Policies):
--    - No public access
--    - Service role has full access (automatic)
--    - Application validates matter ownership before generating signed URLs

-- =============================================================================
-- TABLE UPDATE: Track archive metadata
-- =============================================================================

-- Add comment to reasoning_traces table about archive path format
COMMENT ON COLUMN public.reasoning_traces.archive_path IS
  'Supabase Storage path: {matter_id}/{trace_id}.json.gz in reasoning-archive bucket';

-- Create index for finding traces by archive path (for cleanup/restore operations)
CREATE INDEX IF NOT EXISTS idx_reasoning_traces_archive_path
ON public.reasoning_traces(archive_path)
WHERE archive_path IS NOT NULL;
