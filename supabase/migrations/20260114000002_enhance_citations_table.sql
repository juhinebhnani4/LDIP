-- Enhance citations table for Story 3-1: Act Citation Extraction
-- Adds missing columns needed for comprehensive citation extraction

-- =============================================================================
-- ADD MISSING COLUMNS: citations table
-- =============================================================================

-- Add act_name_original to preserve original extracted form
ALTER TABLE public.citations
ADD COLUMN IF NOT EXISTS act_name_original text;

-- Add subsection and clause for granular section parsing
ALTER TABLE public.citations
ADD COLUMN IF NOT EXISTS subsection text;

ALTER TABLE public.citations
ADD COLUMN IF NOT EXISTS clause text;

-- Add raw_citation_text for exact text from document
ALTER TABLE public.citations
ADD COLUMN IF NOT EXISTS raw_citation_text text;

-- Add extraction_metadata for LLM extraction details
ALTER TABLE public.citations
ADD COLUMN IF NOT EXISTS extraction_metadata jsonb;

-- =============================================================================
-- COLUMN COMMENTS
-- =============================================================================

COMMENT ON COLUMN public.citations.act_name_original IS 'Original Act name as extracted (before normalization)';
COMMENT ON COLUMN public.citations.subsection IS 'Subsection part of citation (e.g., "(1)" from "Section 138(1)")';
COMMENT ON COLUMN public.citations.clause IS 'Clause part of citation (e.g., "(a)" from "Section 138(1)(a)")';
COMMENT ON COLUMN public.citations.raw_citation_text IS 'Exact citation text extracted from document';
COMMENT ON COLUMN public.citations.extraction_metadata IS 'Extraction metadata: model, confidence, patterns matched, etc.';

-- =============================================================================
-- ADD MISSING COLUMNS: act_resolutions table
-- =============================================================================

-- Add act_name_display for user-friendly display name
ALTER TABLE public.act_resolutions
ADD COLUMN IF NOT EXISTS act_name_display text;

-- =============================================================================
-- COLUMN COMMENTS
-- =============================================================================

COMMENT ON COLUMN public.act_resolutions.act_name_display IS 'Display name for Act (e.g., "Negotiable Instruments Act, 1881")';

-- =============================================================================
-- INDEX: Add index for raw_citation_text full-text search (optional)
-- =============================================================================

-- GIN index for JSONB metadata queries
CREATE INDEX IF NOT EXISTS idx_citations_extraction_metadata
ON public.citations USING GIN (extraction_metadata);

-- Index for section_number + subsection compound queries
-- Note: Using existing 'section' column name from original migration
CREATE INDEX IF NOT EXISTS idx_citations_section_subsection
ON public.citations (section, subsection) WHERE subsection IS NOT NULL;
