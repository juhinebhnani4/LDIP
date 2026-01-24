-- Migration: Move pgvector extension to extensions schema
-- Date: 2026-01-25
-- Fixes: extension_in_public (Supabase security linter warning)
--
-- This migration moves the pgvector extension from public schema to a dedicated
-- extensions schema, following Supabase best practices for extension management.
--
-- The search_path is updated to include 'extensions' so existing code continues
-- to work without modification.

-- =============================================================================
-- Step 1: Create extensions schema
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS extensions;

COMMENT ON SCHEMA extensions IS 'Schema for PostgreSQL extensions (pgvector, etc.)';

-- =============================================================================
-- Step 2: Grant usage to all roles
-- =============================================================================
-- All roles need USAGE on the schema to access extension types and operators

GRANT USAGE ON SCHEMA extensions TO postgres;
GRANT USAGE ON SCHEMA extensions TO anon;
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO service_role;

-- =============================================================================
-- Step 3: Move the vector extension to extensions schema
-- =============================================================================
-- This preserves all existing data, indexes, and operator classes.
-- The extension objects (types, operators, functions) are moved to the new schema.

ALTER EXTENSION vector SET SCHEMA extensions;

-- =============================================================================
-- Step 4: Update database search_path to include extensions
-- =============================================================================
-- This ensures that unqualified references to 'vector' type still resolve correctly.
-- The search_path order: public first (for user tables), then extensions.
--
-- Note: This sets the default for new connections. Existing connections may need
-- to reconnect or run SET search_path manually.

ALTER DATABASE postgres SET search_path TO "$user", public, extensions;

-- Also set for current session
SET search_path TO "$user", public, extensions;

-- =============================================================================
-- Step 5: Verify the migration
-- =============================================================================
-- These queries can be run manually to verify the migration succeeded:
--
-- Check extension location:
--   SELECT extname, nspname
--   FROM pg_extension e
--   JOIN pg_namespace n ON e.extnamespace = n.oid
--   WHERE extname = 'vector';
--
-- Check that vector type is accessible:
--   SELECT 'test'::vector(3);
--
-- Check existing chunks table still works:
--   SELECT id, embedding IS NOT NULL as has_embedding
--   FROM chunks LIMIT 1;

-- =============================================================================
-- Rollback instructions (if needed)
-- =============================================================================
-- To rollback this migration:
--
-- ALTER EXTENSION vector SET SCHEMA public;
-- ALTER DATABASE postgres SET search_path TO "$user", public;
-- DROP SCHEMA IF EXISTS extensions;
