-- Add 'table' to library_chunks.chunk_type check constraint
-- Matches the same change already applied to chunks table in 20260220300001
-- Required for promote_chunks_to_library to copy table-type chunks

ALTER TABLE public.library_chunks
DROP CONSTRAINT IF EXISTS library_chunks_chunk_type_check;

ALTER TABLE public.library_chunks
ADD CONSTRAINT library_chunks_chunk_type_check
CHECK (chunk_type IN ('parent', 'child', 'table'));
