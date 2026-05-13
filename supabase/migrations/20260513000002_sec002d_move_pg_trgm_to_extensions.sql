-- SEC-002 D: Move pg_trgm from public to extensions schema
-- Supabase linter recommends extensions not live in public schema.
-- Verified on live DB (2026-05-13): pg_trgm is in public, extensions schema exists.
--
-- Impact: find_library_duplicates uses similarity() — must update its search_path.
-- GIN indexes (idx_library_documents_title_trgm, idx_library_documents_short_title_trgm)
-- survive the move — operator class OIDs are resolved at index creation time.

-- 1. Move pg_trgm to extensions schema
ALTER EXTENSION pg_trgm SET SCHEMA extensions;

-- 2. Recreate find_library_duplicates with extensions in search_path
--    (CREATE OR REPLACE resets privileges, so we must re-apply REVOKE after)
CREATE OR REPLACE FUNCTION public.find_library_duplicates(
  search_title text,
  search_year integer DEFAULT NULL,
  similarity_threshold float DEFAULT 0.6
)
RETURNS TABLE (
  id uuid,
  title text,
  year integer,
  document_type text,
  similarity float
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
  SELECT
    ld.id,
    ld.title,
    ld.year,
    ld.document_type,
    similarity(lower(ld.title), lower(search_title)) AS similarity
  FROM library_documents ld
  WHERE ld.status != 'failed'
    AND (
      -- Title similarity above threshold
      similarity(lower(ld.title), lower(search_title)) > similarity_threshold
      -- OR year match with lower title threshold
      OR (search_year IS NOT NULL AND ld.year = search_year
          AND similarity(lower(ld.title), lower(search_title)) > 0.4)
    )
  ORDER BY similarity DESC
  LIMIT 5;
$$;

-- 3. Re-apply SEC-002 A hardening (CREATE OR REPLACE resets privileges)
REVOKE EXECUTE ON FUNCTION public.find_library_duplicates(text, integer, double precision) FROM PUBLIC, anon;
