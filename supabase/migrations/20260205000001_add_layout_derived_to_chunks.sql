-- Add layout_derived column to chunks table
-- Tracks whether chunk page/bbox info was derived from Docling layout extraction
-- (vs text-based fallback or fuzzy matching)

-- =============================================================================
-- COLUMN: layout_derived - Track Docling layout source
-- =============================================================================

ALTER TABLE public.chunks
ADD COLUMN layout_derived boolean DEFAULT false;

-- Add comment
COMMENT ON COLUMN public.chunks.layout_derived IS 'Whether chunk was derived from Docling layout extraction (true) or text-based fallback (false)';

-- Backfill: Set existing chunks to false (they were created before layout-aware chunking)
-- No action needed as DEFAULT false handles this

-- Index for analytics queries filtering by layout method
CREATE INDEX idx_chunks_layout_derived ON public.chunks(layout_derived)
WHERE layout_derived = true;
