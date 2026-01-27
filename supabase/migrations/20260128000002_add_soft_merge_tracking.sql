-- Story 3.3: Add Soft Merge Tracking to Entity Nodes
-- Epic 3: Compliance & UX
-- Gap #6: Track entity merges for potential undo/audit trail

-- =============================================================================
-- Add soft merge tracking columns to identity_nodes
-- =============================================================================

-- merged_into_id: If this entity was merged into another, this references that entity
-- A NULL value means this entity is active (not merged)
-- A non-NULL value means this entity's data has been merged into the referenced entity
ALTER TABLE public.identity_nodes
ADD COLUMN IF NOT EXISTS merged_into_id uuid REFERENCES public.identity_nodes(id) ON DELETE SET NULL;

-- merged_at: When the merge occurred
ALTER TABLE public.identity_nodes
ADD COLUMN IF NOT EXISTS merged_at timestamptz DEFAULT NULL;

-- merged_by: User who performed the merge (for audit trail)
ALTER TABLE public.identity_nodes
ADD COLUMN IF NOT EXISTS merged_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

-- Code Review Fix: Store pre-merge mention_count for accurate unmerge
ALTER TABLE public.identity_nodes
ADD COLUMN IF NOT EXISTS pre_merge_mention_count integer DEFAULT NULL;

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for finding merged entities (for unmerge operations and auditing)
CREATE INDEX IF NOT EXISTS idx_identity_nodes_merged_into
ON public.identity_nodes (merged_into_id)
WHERE merged_into_id IS NOT NULL;

-- Index for listing active (non-merged) entities
CREATE INDEX IF NOT EXISTS idx_identity_nodes_active
ON public.identity_nodes (matter_id, entity_type)
WHERE merged_into_id IS NULL;

-- Composite index for finding entities merged by a user
CREATE INDEX IF NOT EXISTS idx_identity_nodes_merged_by
ON public.identity_nodes (merged_by, merged_at DESC)
WHERE merged_into_id IS NOT NULL;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN public.identity_nodes.merged_into_id IS 'If merged, references the target entity. NULL = active entity. (Story 3.3)';
COMMENT ON COLUMN public.identity_nodes.merged_at IS 'Timestamp when entity was merged. NULL = active. (Story 3.3)';
COMMENT ON COLUMN public.identity_nodes.merged_by IS 'User who performed the merge. (Story 3.3)';
COMMENT ON COLUMN public.identity_nodes.pre_merge_mention_count IS 'Mention count before merge, for accurate unmerge. (Code Review Fix)';

-- =============================================================================
-- UPDATE merge_entities FUNCTION for soft merge
-- =============================================================================

-- Drop existing function first
DROP FUNCTION IF EXISTS public.merge_entities(uuid, uuid, uuid);

-- Recreate with soft merge tracking
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
  v_merge_mention_count integer;
  v_user_id uuid;
BEGIN
  -- Get current user ID (may be NULL for service account calls)
  v_user_id := auth.uid();

  -- Verify user has owner access (merging is destructive)
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = v_user_id
    AND ma.role = 'owner'
  ) THEN
    RAISE EXCEPTION 'Access denied: only owners can merge entities for matter %', p_matter_id;
  END IF;

  -- Verify both entities exist, belong to the same matter, and are active (not already merged)
  IF NOT EXISTS (
    SELECT 1 FROM public.identity_nodes
    WHERE id = p_keep_id AND matter_id = p_matter_id AND merged_into_id IS NULL
  ) THEN
    RAISE EXCEPTION 'Entity to keep not found, not in this matter, or already merged';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.identity_nodes
    WHERE id = p_merge_id AND matter_id = p_matter_id AND merged_into_id IS NULL
  ) THEN
    RAISE EXCEPTION 'Entity to merge not found, not in this matter, or already merged';
  END IF;

  -- Get name, aliases, and mention_count from entity to merge
  -- Code Review Fix: Store mention_count for accurate unmerge
  SELECT canonical_name, aliases, mention_count INTO v_merge_name, v_merge_aliases, v_merge_mention_count
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

  -- Update entity_mentions to point to kept entity
  UPDATE public.entity_mentions
  SET entity_id = p_keep_id
  WHERE entity_id = p_merge_id;

  -- Story 3.3: SOFT MERGE - Mark entity as merged instead of deleting
  -- This preserves the entity for potential undo operations
  -- Code Review Fix: Store pre_merge_mention_count for accurate unmerge
  UPDATE public.identity_nodes
  SET merged_into_id = p_keep_id,
      merged_at = now(),
      merged_by = v_user_id,
      pre_merge_mention_count = v_merge_mention_count,
      updated_at = now()
  WHERE id = p_merge_id;
END;
$$;

COMMENT ON FUNCTION public.merge_entities IS 'Soft merge two entities - marks source as merged, preserving for undo (Story 3.3)';

-- =============================================================================
-- NEW FUNCTION: Unmerge entity (reverse a soft merge)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.unmerge_entity(
  p_matter_id uuid,
  p_merged_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_keep_id uuid;
  v_merged_name text;
  v_pre_merge_mention_count integer;
  v_user_id uuid;
BEGIN
  v_user_id := auth.uid();

  -- Verify user has owner access
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = v_user_id
    AND ma.role = 'owner'
  ) THEN
    RAISE EXCEPTION 'Access denied: only owners can unmerge entities for matter %', p_matter_id;
  END IF;

  -- Verify entity exists, is in this matter, and is actually merged
  -- Code Review Fix: Also get pre_merge_mention_count for accurate restoration
  SELECT merged_into_id, canonical_name, COALESCE(pre_merge_mention_count, 0)
  INTO v_keep_id, v_merged_name, v_pre_merge_mention_count
  FROM public.identity_nodes
  WHERE id = p_merged_id AND matter_id = p_matter_id AND merged_into_id IS NOT NULL;

  IF v_keep_id IS NULL THEN
    RAISE EXCEPTION 'Entity not found, not in this matter, or not merged';
  END IF;

  -- Remove merged entity's name from kept entity's aliases
  -- Code Review Fix: Subtract the pre_merge_mention_count from kept entity
  UPDATE public.identity_nodes
  SET aliases = array_remove(aliases, v_merged_name),
      mention_count = GREATEST(0, mention_count - v_pre_merge_mention_count),
      updated_at = now()
  WHERE id = v_keep_id;

  -- Clear merge tracking fields to restore entity
  -- Code Review Fix: Restore original mention_count and clear pre_merge_mention_count
  UPDATE public.identity_nodes
  SET merged_into_id = NULL,
      merged_at = NULL,
      merged_by = NULL,
      mention_count = v_pre_merge_mention_count,
      pre_merge_mention_count = NULL,
      updated_at = now()
  WHERE id = p_merged_id;

  -- Note: Entity mentions, chunks, and events references remain pointing to keep_id
  -- The unmerged entity's mention_count is restored but actual mentions stay with kept entity
  -- This is a known limitation - full mention reassignment would be expensive
END;
$$;

COMMENT ON FUNCTION public.unmerge_entity IS 'Reverse a soft merge, restoring the merged entity (Story 3.3). Note: Entity type validation is done at API level before merge, so unmerge assumes types were validated. If DB was manually modified, types may mismatch.';

-- =============================================================================
-- VIEW: Active entities only (excludes merged)
-- =============================================================================

CREATE OR REPLACE VIEW public.active_identity_nodes AS
SELECT *
FROM public.identity_nodes
WHERE merged_into_id IS NULL;

COMMENT ON VIEW public.active_identity_nodes IS 'View of active (non-merged) entities for most queries (Story 3.3)';
