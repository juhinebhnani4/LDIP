-- Story 3.4: Fix merge_entities function to handle duplicate edge constraints
-- The previous version would fail when updating edges that would create duplicates
-- (e.g., both entities have an edge to the same third entity)

-- =============================================================================
-- UPDATE merge_entities FUNCTION to handle edge duplicates
-- =============================================================================

-- Drop existing function first (must specify exact signature with 4 params)
DROP FUNCTION IF EXISTS public.merge_entities(uuid, uuid, uuid, uuid);

-- Recreate with proper edge duplicate handling
CREATE OR REPLACE FUNCTION public.merge_entities(
  p_matter_id uuid,
  p_keep_id uuid,
  p_merge_id uuid,
  p_user_id uuid DEFAULT NULL
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
  v_effective_user_id uuid;
BEGIN
  -- Use passed user_id, or fall back to auth.uid()
  v_effective_user_id := COALESCE(p_user_id, auth.uid());

  -- Verify user has owner access (merging is destructive)
  -- Skip check if no user context (service-level call with prior API auth)
  IF v_effective_user_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.matter_attorneys ma
      WHERE ma.matter_id = p_matter_id
      AND ma.user_id = v_effective_user_id
      AND ma.role = 'owner'
    ) THEN
      RAISE EXCEPTION 'Access denied: only owners can merge entities for matter %', p_matter_id;
    END IF;
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
  SELECT canonical_name, aliases, mention_count INTO v_merge_name, v_merge_aliases, v_merge_mention_count
  FROM public.identity_nodes WHERE id = p_merge_id;

  -- Add merged entity's name and aliases to kept entity
  UPDATE public.identity_nodes
  SET aliases = array_cat(aliases, array_cat(ARRAY[v_merge_name], v_merge_aliases)),
      mention_count = mention_count + (SELECT mention_count FROM public.identity_nodes WHERE id = p_merge_id),
      updated_at = now()
  WHERE id = p_keep_id;

  -- Delete edges from merged entity that would create duplicates when updated
  -- (i.e., kept entity already has an edge to the same target with same relationship type)
  DELETE FROM public.identity_edges e1
  WHERE e1.source_node_id = p_merge_id
  AND EXISTS (
    SELECT 1 FROM public.identity_edges e2
    WHERE e2.source_node_id = p_keep_id
    AND e2.target_node_id = e1.target_node_id
    AND e2.relationship_type = e1.relationship_type
    AND e2.matter_id = e1.matter_id
  );

  -- Delete edges to merged entity that would create duplicates when updated
  DELETE FROM public.identity_edges e1
  WHERE e1.target_node_id = p_merge_id
  AND EXISTS (
    SELECT 1 FROM public.identity_edges e2
    WHERE e2.target_node_id = p_keep_id
    AND e2.source_node_id = e1.source_node_id
    AND e2.relationship_type = e1.relationship_type
    AND e2.matter_id = e1.matter_id
  );

  -- Delete self-referential edges that would be created (edge from kept to kept)
  DELETE FROM public.identity_edges
  WHERE (source_node_id = p_merge_id AND target_node_id = p_keep_id)
     OR (source_node_id = p_keep_id AND target_node_id = p_merge_id);

  -- Now update remaining edges pointing to/from merged entity
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

  -- SOFT MERGE - Mark entity as merged instead of deleting
  UPDATE public.identity_nodes
  SET merged_into_id = p_keep_id,
      merged_at = now(),
      merged_by = v_effective_user_id,
      pre_merge_mention_count = v_merge_mention_count,
      updated_at = now()
  WHERE id = p_merge_id;
END;
$$;

COMMENT ON FUNCTION public.merge_entities IS 'Soft merge two entities - handles duplicate edges gracefully (Story 3.4). Accepts optional p_user_id for service client calls.';
