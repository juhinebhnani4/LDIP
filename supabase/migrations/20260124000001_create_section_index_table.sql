-- Create section_index table for pre-computed section -> page mappings
-- This optimizes Act section lookups for citation split-view (Story 3-4)

-- =============================================================================
-- TABLE: section_index - Pre-computed section locations in Act documents
-- =============================================================================

CREATE TABLE public.section_index (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  section_number text NOT NULL,
  page_number integer NOT NULL,
  confidence float DEFAULT 1.0,
  is_toc boolean DEFAULT false,
  section_title text,
  bbox_id uuid REFERENCES public.bounding_boxes(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for section lookups
-- =============================================================================

-- Primary lookup pattern: document + section
CREATE UNIQUE INDEX idx_section_index_doc_section
  ON public.section_index(document_id, section_number)
  WHERE NOT is_toc;

-- Matter-scoped queries
CREATE INDEX idx_section_index_matter ON public.section_index(matter_id);

-- Document lookup
CREATE INDEX idx_section_index_document ON public.section_index(document_id);

-- Section number search (for fuzzy matching)
CREATE INDEX idx_section_index_section ON public.section_index(section_number);

-- Filter out TOC entries
CREATE INDEX idx_section_index_non_toc ON public.section_index(document_id, section_number) WHERE NOT is_toc;

-- Comments
COMMENT ON TABLE public.section_index IS 'Pre-computed section locations for Act documents';
COMMENT ON COLUMN public.section_index.document_id IS 'FK to documents - the Act document';
COMMENT ON COLUMN public.section_index.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.section_index.section_number IS 'Section number (e.g., "138", "138(1)", "138A")';
COMMENT ON COLUMN public.section_index.page_number IS 'Page number where section content begins';
COMMENT ON COLUMN public.section_index.confidence IS 'Detection confidence (0-1)';
COMMENT ON COLUMN public.section_index.is_toc IS 'True if this is a TOC entry, not actual content';
COMMENT ON COLUMN public.section_index.section_title IS 'Section title if detected';
COMMENT ON COLUMN public.section_index.bbox_id IS 'Reference to the bounding box containing section header';

-- =============================================================================
-- RLS POLICIES: section_index table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.section_index ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT section index from matters where they have any role
CREATE POLICY "Users can view section index from their matters"
ON public.section_index FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT section index entries
CREATE POLICY "Editors and Owners can insert section index"
ON public.section_index FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE section index
CREATE POLICY "Editors and Owners can update section index"
ON public.section_index FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE section index entries
CREATE POLICY "Only Owners can delete section index"
ON public.section_index FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- FUNCTION: Get section page with fallback
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_section_page(
  p_document_id uuid,
  p_section_number text
)
RETURNS TABLE (
  page_number integer,
  section_title text,
  confidence float,
  source text
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- First try exact match in section_index (non-TOC)
  RETURN QUERY
  SELECT
    si.page_number,
    si.section_title,
    si.confidence,
    'section_index'::text as source
  FROM public.section_index si
  WHERE si.document_id = p_document_id
    AND si.section_number = p_section_number
    AND NOT si.is_toc
  LIMIT 1;

  IF NOT FOUND THEN
    -- Fallback: Search bounding boxes for "section X" pattern
    RETURN QUERY
    SELECT
      bb.page_number,
      NULL::text as section_title,
      0.7::float as confidence,
      'bbox_search'::text as source
    FROM public.bounding_boxes bb
    WHERE bb.document_id = p_document_id
      AND bb.text ILIKE '%section ' || p_section_number || '%'
      AND bb.page_number > 10  -- Skip TOC pages
      AND bb.text NOT ILIKE '%1956%'  -- Skip old Act references
    ORDER BY bb.page_number DESC
    LIMIT 1;
  END IF;
END;
$$;

COMMENT ON FUNCTION public.get_section_page IS 'Get page number for a section with fallback to bbox search';

-- =============================================================================
-- TABLE: toc_pages - Track which pages are Table of Contents
-- =============================================================================

CREATE TABLE public.toc_pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  page_number integer NOT NULL,
  confidence float DEFAULT 1.0,
  detected_via text DEFAULT 'manual',
  created_at timestamptz DEFAULT now(),
  UNIQUE(document_id, page_number)
);

CREATE INDEX idx_toc_pages_document ON public.toc_pages(document_id);

COMMENT ON TABLE public.toc_pages IS 'Tracks Table of Contents pages in documents';
COMMENT ON COLUMN public.toc_pages.detected_via IS 'How TOC was detected: manual, keyword, layout';

-- RLS for toc_pages (same pattern as section_index)
ALTER TABLE public.toc_pages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view toc_pages via document access"
ON public.toc_pages FOR SELECT
USING (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
    )
  )
);

CREATE POLICY "Editors and Owners can manage toc_pages"
ON public.toc_pages FOR ALL
USING (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
);
