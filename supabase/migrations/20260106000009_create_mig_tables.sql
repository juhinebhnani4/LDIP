-- Create MIG (Matter Identity Graph) tables for entity extraction and relationships
-- This implements Layer 1 of 4-layer matter isolation (Story 1-7)

-- =============================================================================
-- TABLE: identity_nodes - Canonical entities in the matter
-- =============================================================================

CREATE TABLE public.identity_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,

  -- Identity information
  canonical_name text NOT NULL,
  entity_type text NOT NULL,
  aliases text[] DEFAULT '{}',

  -- Metadata
  metadata jsonb DEFAULT '{}',
  mention_count integer DEFAULT 0, -- Number of times mentioned in documents

  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  -- Unique canonical name per entity type per matter
  UNIQUE(matter_id, entity_type, canonical_name)
);

-- =============================================================================
-- TABLE: identity_edges - Relationships between entities
-- =============================================================================

CREATE TABLE public.identity_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,

  -- Relationship
  source_node_id uuid NOT NULL REFERENCES public.identity_nodes(id) ON DELETE CASCADE,
  target_node_id uuid NOT NULL REFERENCES public.identity_nodes(id) ON DELETE CASCADE,
  relationship_type text NOT NULL,

  -- Metadata
  metadata jsonb DEFAULT '{}',
  confidence float CHECK (confidence >= 0 AND confidence <= 1),

  created_at timestamptz DEFAULT now(),

  -- Prevent duplicate edges
  UNIQUE(matter_id, source_node_id, target_node_id, relationship_type)
);

-- =============================================================================
-- INDEXES: identity_nodes
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_identity_nodes_matter_id ON public.identity_nodes(matter_id);
CREATE INDEX idx_identity_nodes_entity_type ON public.identity_nodes(entity_type);

-- Name search
CREATE INDEX idx_identity_nodes_canonical ON public.identity_nodes(canonical_name);
CREATE INDEX idx_identity_nodes_canonical_lower ON public.identity_nodes(lower(canonical_name));

-- GIN index for aliases array (fast alias lookup)
CREATE INDEX idx_identity_nodes_aliases ON public.identity_nodes USING GIN (aliases);

-- Composite indexes for common query patterns
CREATE INDEX idx_identity_nodes_matter_type ON public.identity_nodes(matter_id, entity_type);

-- Index for listing entities sorted by mention_count (API: list_entities)
-- This prevents slow sorts on large matters when ordering by most-mentioned
CREATE INDEX idx_identity_nodes_matter_mentions ON public.identity_nodes(matter_id, mention_count DESC);

-- Text search on canonical name and aliases
CREATE INDEX idx_identity_nodes_name_search ON public.identity_nodes
  USING GIN (to_tsvector('english', canonical_name));

-- JSONB metadata index
CREATE INDEX idx_identity_nodes_metadata ON public.identity_nodes USING GIN (metadata);

-- =============================================================================
-- INDEXES: identity_edges
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_identity_edges_matter_id ON public.identity_edges(matter_id);
CREATE INDEX idx_identity_edges_source ON public.identity_edges(source_node_id);
CREATE INDEX idx_identity_edges_target ON public.identity_edges(target_node_id);
CREATE INDEX idx_identity_edges_type ON public.identity_edges(relationship_type);

-- Composite indexes for graph traversal
CREATE INDEX idx_identity_edges_matter_source ON public.identity_edges(matter_id, source_node_id);
CREATE INDEX idx_identity_edges_matter_target ON public.identity_edges(matter_id, target_node_id);

-- Comments
COMMENT ON TABLE public.identity_nodes IS 'Canonical entities in the Matter Identity Graph (MIG)';
COMMENT ON COLUMN public.identity_nodes.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.identity_nodes.canonical_name IS 'Primary/canonical name for this entity';
COMMENT ON COLUMN public.identity_nodes.entity_type IS 'Entity type: person, organization, location, date, document, etc.';
COMMENT ON COLUMN public.identity_nodes.aliases IS 'Array of alternate names/spellings that resolve to this entity';
COMMENT ON COLUMN public.identity_nodes.metadata IS 'Additional entity metadata (e.g., role, designation)';
COMMENT ON COLUMN public.identity_nodes.mention_count IS 'Number of times this entity appears in documents';

COMMENT ON TABLE public.identity_edges IS 'Relationships between entities in the MIG';
COMMENT ON COLUMN public.identity_edges.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.identity_edges.source_node_id IS 'Source entity in the relationship';
COMMENT ON COLUMN public.identity_edges.target_node_id IS 'Target entity in the relationship';
COMMENT ON COLUMN public.identity_edges.relationship_type IS 'Type of relationship (e.g., employer_of, represented_by)';
COMMENT ON COLUMN public.identity_edges.metadata IS 'Additional relationship metadata';
COMMENT ON COLUMN public.identity_edges.confidence IS 'Extraction confidence (0-1)';

-- =============================================================================
-- RLS POLICIES: identity_nodes table
-- =============================================================================

ALTER TABLE public.identity_nodes ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT identity nodes from matters where they have any role
CREATE POLICY "Users can view identity nodes from their matters"
ON public.identity_nodes FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT identity nodes
CREATE POLICY "Editors and Owners can insert identity nodes"
ON public.identity_nodes FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE identity nodes (merge, rename)
CREATE POLICY "Editors and Owners can update identity nodes"
ON public.identity_nodes FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE identity nodes
CREATE POLICY "Only Owners can delete identity nodes"
ON public.identity_nodes FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- RLS POLICIES: identity_edges table
-- =============================================================================

ALTER TABLE public.identity_edges ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT identity edges from matters where they have any role
CREATE POLICY "Users can view identity edges from their matters"
ON public.identity_edges FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT identity edges
CREATE POLICY "Editors and Owners can insert identity edges"
ON public.identity_edges FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE identity edges
CREATE POLICY "Editors and Owners can update identity edges"
ON public.identity_edges FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE identity edges
CREATE POLICY "Only Owners can delete identity edges"
ON public.identity_edges FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- TRIGGERS: Auto-update updated_at
-- =============================================================================

CREATE TRIGGER set_identity_nodes_updated_at
  BEFORE UPDATE ON public.identity_nodes
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTIONS: Entity resolution
-- =============================================================================

-- Function to find or create entity by name (with alias matching)
CREATE OR REPLACE FUNCTION public.resolve_or_create_entity(
  p_matter_id uuid,
  p_entity_type text,
  p_name text,
  p_metadata jsonb DEFAULT '{}'
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
  v_normalized_name text;
BEGIN
  -- Verify user has editor or owner access
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  ) THEN
    RAISE EXCEPTION 'Access denied: user cannot modify entities for matter %', p_matter_id;
  END IF;

  -- Normalize name for matching
  v_normalized_name := lower(trim(p_name));

  -- Try to find existing entity by canonical name or alias
  SELECT id INTO v_id
  FROM public.identity_nodes
  WHERE matter_id = p_matter_id
    AND entity_type = p_entity_type
    AND (
      lower(canonical_name) = v_normalized_name
      OR v_normalized_name = ANY(SELECT lower(unnest(aliases)))
    )
  LIMIT 1;

  -- If found, increment mention count and return
  IF v_id IS NOT NULL THEN
    UPDATE public.identity_nodes
    SET mention_count = mention_count + 1,
        updated_at = now()
    WHERE id = v_id;
    RETURN v_id;
  END IF;

  -- Create new entity
  INSERT INTO public.identity_nodes (matter_id, entity_type, canonical_name, metadata, mention_count)
  VALUES (p_matter_id, p_entity_type, p_name, p_metadata, 1)
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.resolve_or_create_entity IS 'Find existing entity or create new one with alias matching';

-- Function to merge entities (combine two entities into one)
CREATE OR REPLACE FUNCTION public.merge_entities(
  p_matter_id uuid,
  p_keep_id uuid,
  p_merge_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_merge_name text;
  v_merge_aliases text[];
BEGIN
  -- Verify user has owner access (merging is destructive)
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
    AND ma.role = 'owner'
  ) THEN
    RAISE EXCEPTION 'Access denied: only owners can merge entities for matter %', p_matter_id;
  END IF;

  -- Verify both entities exist and belong to the same matter
  IF NOT EXISTS (SELECT 1 FROM public.identity_nodes WHERE id = p_keep_id AND matter_id = p_matter_id) THEN
    RAISE EXCEPTION 'Entity to keep not found or not in this matter';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM public.identity_nodes WHERE id = p_merge_id AND matter_id = p_matter_id) THEN
    RAISE EXCEPTION 'Entity to merge not found or not in this matter';
  END IF;

  -- Get name and aliases from entity to merge
  SELECT canonical_name, aliases INTO v_merge_name, v_merge_aliases
  FROM public.identity_nodes WHERE id = p_merge_id;

  -- Add merged entity's name and aliases to kept entity
  UPDATE public.identity_nodes
  SET aliases = array_cat(aliases, array_cat(ARRAY[v_merge_name], v_merge_aliases)),
      mention_count = mention_count + (SELECT mention_count FROM public.identity_nodes WHERE id = p_merge_id),
      updated_at = now()
  WHERE id = p_keep_id;

  -- Update all edges pointing to merged entity
  UPDATE public.identity_edges SET source_node_id = p_keep_id WHERE source_node_id = p_merge_id;
  UPDATE public.identity_edges SET target_node_id = p_keep_id WHERE target_node_id = p_merge_id;

  -- Update all chunks referencing merged entity
  UPDATE public.chunks
  SET entity_ids = array_replace(entity_ids, p_merge_id, p_keep_id)
  WHERE p_merge_id = ANY(entity_ids);

  -- Update all events referencing merged entity
  UPDATE public.events
  SET entities_involved = array_replace(entities_involved, p_merge_id, p_keep_id)
  WHERE p_merge_id = ANY(entities_involved);

  -- CRITICAL: Update entity_mentions to point to kept entity BEFORE deleting merged entity
  -- This prevents cascade delete from destroying mention data (highlighting, bounding boxes)
  UPDATE public.entity_mentions
  SET entity_id = p_keep_id
  WHERE entity_id = p_merge_id;

  -- Delete merged entity
  DELETE FROM public.identity_nodes WHERE id = p_merge_id;
END;
$$;

COMMENT ON FUNCTION public.merge_entities IS 'Merge two entities into one, updating all references';
