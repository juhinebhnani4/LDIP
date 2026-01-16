-- Create entity_mentions table for MIG (Matter Identity Graph)
-- Tracks where entities are mentioned in documents for source location highlighting
-- Story: 2c-1-mig-entity-extraction

-- =============================================================================
-- TABLE: entity_mentions - Links entities to their source locations
-- =============================================================================

CREATE TABLE public.entity_mentions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id uuid NOT NULL REFERENCES public.identity_nodes(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  chunk_id uuid REFERENCES public.chunks(id) ON DELETE SET NULL,

  -- Location information
  page_number integer,
  bbox_ids uuid[] DEFAULT '{}',

  -- Mention details
  mention_text text NOT NULL,
  context text,  -- Surrounding text for context (±50 chars)
  confidence float CHECK (confidence >= 0 AND confidence <= 1),

  created_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: entity_mentions
-- =============================================================================

-- Primary lookup indexes
CREATE INDEX idx_entity_mentions_entity_id ON public.entity_mentions(entity_id);
CREATE INDEX idx_entity_mentions_document_id ON public.entity_mentions(document_id);
CREATE INDEX idx_entity_mentions_chunk_id ON public.entity_mentions(chunk_id);

-- Composite index for entity+document queries
CREATE INDEX idx_entity_mentions_entity_document ON public.entity_mentions(entity_id, document_id);

-- Page-based lookups for highlighting
CREATE INDEX idx_entity_mentions_document_page ON public.entity_mentions(document_id, page_number);

-- Comments
COMMENT ON TABLE public.entity_mentions IS 'Tracks entity mentions with source document locations for highlighting';
COMMENT ON COLUMN public.entity_mentions.entity_id IS 'FK to identity_nodes - the extracted entity';
COMMENT ON COLUMN public.entity_mentions.document_id IS 'FK to documents - source document';
COMMENT ON COLUMN public.entity_mentions.chunk_id IS 'FK to chunks - source chunk (nullable)';
COMMENT ON COLUMN public.entity_mentions.page_number IS 'Page number where mention appears';
COMMENT ON COLUMN public.entity_mentions.bbox_ids IS 'Array of bounding box UUIDs for highlighting';
COMMENT ON COLUMN public.entity_mentions.mention_text IS 'Exact text of the mention';
COMMENT ON COLUMN public.entity_mentions.context IS 'Surrounding text for context (±50 chars)';
COMMENT ON COLUMN public.entity_mentions.confidence IS 'Extraction confidence (0-1)';

-- =============================================================================
-- RLS POLICIES: entity_mentions table
-- =============================================================================

ALTER TABLE public.entity_mentions ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT entity mentions from their matters
-- (join through identity_nodes to get matter_id)
CREATE POLICY "Users can view entity mentions from their matters"
ON public.entity_mentions FOR SELECT
USING (
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
    )
  )
);

-- Policy 2: Editors and Owners can INSERT entity mentions
-- CRITICAL: Validates both entity_id AND document_id belong to the SAME matter
-- This prevents cross-matter reference injection attacks
CREATE POLICY "Editors and Owners can insert entity mentions"
ON public.entity_mentions FOR INSERT
WITH CHECK (
  -- Entity must belong to a matter the user can edit
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
  AND
  -- Document must belong to the SAME matter as the entity (cross-matter protection)
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id = (
      SELECT in_node.matter_id FROM public.identity_nodes in_node
      WHERE in_node.id = entity_id
    )
  )
);

-- Policy 3: Editors and Owners can UPDATE entity mentions
CREATE POLICY "Editors and Owners can update entity mentions"
ON public.entity_mentions FOR UPDATE
USING (
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
);

-- Policy 4: Owners can DELETE entity mentions
CREATE POLICY "Only Owners can delete entity mentions"
ON public.entity_mentions FOR DELETE
USING (
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role = 'owner'
    )
  )
);
