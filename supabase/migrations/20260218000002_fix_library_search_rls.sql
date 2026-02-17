-- Migration: Fix match_library_chunks_for_matter RLS check
-- Problem: auth.uid() returns NULL when called from service role client
-- (backend uses service role for all DB operations). This causes the
-- access check to always fail, silently returning zero library results.
--
-- Fix: Replace auth.uid() check with a simple matter existence check.
-- Layer 4 application auth already validates user access before the
-- query reaches this function. The SECURITY DEFINER + matter_id filter
-- on matter_library_links is sufficient isolation.

CREATE OR REPLACE FUNCTION public.match_library_chunks_for_matter(
  query_embedding vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 10,
  similarity_threshold float DEFAULT 0.5
)
RETURNS TABLE (
  id uuid,
  library_document_id uuid,
  document_title text,
  document_type text,
  chunk_index integer,
  content text,
  page_number integer,
  section_title text,
  chunk_type text,
  similarity float
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Verify matter exists (Layer 4 app auth already validated user access)
  IF NOT EXISTS (
    SELECT 1 FROM public.matters m
    WHERE m.id = filter_matter_id
  ) THEN
    RAISE EXCEPTION 'Matter not found: %', filter_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    lc.id,
    lc.library_document_id,
    ld.title AS document_title,
    ld.document_type,
    lc.chunk_index,
    lc.content,
    lc.page_number,
    lc.section_title,
    lc.chunk_type,
    1 - (lc.embedding <=> query_embedding) AS similarity
  FROM public.library_chunks lc
  JOIN public.library_documents ld ON ld.id = lc.library_document_id
  JOIN public.matter_library_links mll ON mll.library_document_id = ld.id
  WHERE mll.matter_id = filter_matter_id  -- Only linked library documents
    AND lc.embedding IS NOT NULL
    AND 1 - (lc.embedding <=> query_embedding) > similarity_threshold
    AND ld.status = 'completed'  -- Only fully processed documents
  ORDER BY lc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
