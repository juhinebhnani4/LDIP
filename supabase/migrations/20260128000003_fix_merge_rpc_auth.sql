-- Story 3.3: Fix merge/unmerge RPC functions for service client auth
-- The merge_entities and unmerge_entity functions use auth.uid() which returns NULL
-- when called via service client. This migration adds a p_user_id parameter.

-- =============================================================================
-- UPDATE merge_entities FUNCTION to accept user_id parameter
-- =============================================================================

-- Drop existing function first (must specify exact signature)
DROP FUNCTION IF EXISTS public.merge_entities(uuid, uuid, uuid);

-- Recreate with user_id parameter
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

COMMENT ON FUNCTION public.merge_entities IS 'Soft merge two entities - marks source as merged, preserving for undo (Story 3.3). Accepts optional p_user_id for service client calls.';


-- =============================================================================
-- UPDATE unmerge_entity FUNCTION to accept user_id parameter
-- =============================================================================

-- Drop existing function first (must specify exact signature)
DROP FUNCTION IF EXISTS public.unmerge_entity(uuid, uuid);

-- Recreate with user_id parameter
CREATE OR REPLACE FUNCTION public.unmerge_entity(
  p_matter_id uuid,
  p_merged_id uuid,
  p_user_id uuid DEFAULT NULL
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
  v_effective_user_id uuid;
BEGIN
  -- Use passed user_id, or fall back to auth.uid()
  v_effective_user_id := COALESCE(p_user_id, auth.uid());

  -- Verify user has owner access (skip if no user context)
  IF v_effective_user_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.matter_attorneys ma
      WHERE ma.matter_id = p_matter_id
      AND ma.user_id = v_effective_user_id
      AND ma.role = 'owner'
    ) THEN
      RAISE EXCEPTION 'Access denied: only owners can unmerge entities for matter %', p_matter_id;
    END IF;
  END IF;

  -- Verify entity exists, is in this matter, and is actually merged
  SELECT merged_into_id, canonical_name, COALESCE(pre_merge_mention_count, 0)
  INTO v_keep_id, v_merged_name, v_pre_merge_mention_count
  FROM public.identity_nodes
  WHERE id = p_merged_id AND matter_id = p_matter_id AND merged_into_id IS NOT NULL;

  IF v_keep_id IS NULL THEN
    RAISE EXCEPTION 'Entity not found, not in this matter, or not merged';
  END IF;

  -- Remove merged entity's name from kept entity's aliases
  UPDATE public.identity_nodes
  SET aliases = array_remove(aliases, v_merged_name),
      mention_count = GREATEST(0, mention_count - v_pre_merge_mention_count),
      updated_at = now()
  WHERE id = v_keep_id;

  -- Clear merge tracking fields to restore entity
  UPDATE public.identity_nodes
  SET merged_into_id = NULL,
      merged_at = NULL,
      merged_by = NULL,
      mention_count = v_pre_merge_mention_count,
      pre_merge_mention_count = NULL,
      updated_at = now()
  WHERE id = p_merged_id;
END;
$$;

COMMENT ON FUNCTION public.unmerge_entity IS 'Reverse a soft merge, restoring the merged entity (Story 3.3). Accepts optional p_user_id for service client calls.';
