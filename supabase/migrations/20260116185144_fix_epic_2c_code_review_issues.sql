-- Migration: Fix Epic 2c Code Review Issues
-- Date: 2026-01-16
-- Fixes:
--   1. CRITICAL: Data loss on entity merge (entity_mentions cascade delete)
--   2. CRITICAL: Cross-matter reference injection (RLS gap in entity_mentions INSERT)
--   3. MEDIUM: Missing performance index for listing entities by mention_count

-- =============================================================================
-- Fix #1: Update merge_entities function to migrate entity_mentions before delete
-- =============================================================================
-- The original function deleted the merged entity without first updating
-- entity_mentions, causing cascade delete to destroy mention data.

CREATE OR REPLACE FUNCTION public.merge_entities(
  p_matter_id UUID,
  p_keep_id UUID,
  p_merge_id UUID
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- Validate both entities exist and belong to the same matter
  IF NOT EXISTS (
    SELECT 1 FROM public.identity_nodes
    WHERE id = p_keep_id AND matter_id = p_matter_id
  ) THEN
    RAISE EXCEPTION 'Keep entity not found or does not belong to matter';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.identity_nodes
    WHERE id = p_merge_id AND matter_id = p_matter_id
  ) THEN
    RAISE EXCEPTION 'Merge entity not found or does not belong to matter';
  END IF;

  -- Add merged entity's canonical name as an alias to kept entity
  UPDATE public.identity_nodes
  SET aliases = COALESCE(aliases, '{}') || ARRAY[(
    SELECT canonical_name FROM public.identity_nodes WHERE id = p_merge_id
  )]
  WHERE id = p_keep_id;

  -- Merge aliases from merged entity to kept entity
  UPDATE public.identity_nodes
  SET aliases = (
    SELECT ARRAY(
      SELECT DISTINCT unnest(
        COALESCE(k.aliases, '{}') || COALESCE(m.aliases, '{}')
      )
    )
    FROM public.identity_nodes k, public.identity_nodes m
    WHERE k.id = p_keep_id AND m.id = p_merge_id
  )
  WHERE id = p_keep_id;

  -- Update all edges pointing to merged entity
  UPDATE public.identity_edges
  SET source_node_id = p_keep_id
  WHERE source_node_id = p_merge_id;

  UPDATE public.identity_edges
  SET target_node_id = p_keep_id
  WHERE target_node_id = p_merge_id;

  -- Update all chunks referencing merged entity
  UPDATE public.chunks
  SET entity_ids = array_replace(entity_ids, p_merge_id, p_keep_id)
  WHERE p_merge_id = ANY(entity_ids);

  -- Update all events referencing merged entity
  UPDATE public.events
  SET entities_involved = array_replace(entities_involved, p_merge_id, p_keep_id)
  WHERE p_merge_id = ANY(entities_involved);

  -- CRITICAL FIX: Update entity_mentions to point to kept entity BEFORE deleting merged entity
  -- This prevents cascade delete from destroying mention data (highlighting, bounding boxes)
  UPDATE public.entity_mentions
  SET entity_id = p_keep_id
  WHERE entity_id = p_merge_id;

  -- Delete merged entity
  DELETE FROM public.identity_nodes WHERE id = p_merge_id;
END;
$$;

COMMENT ON FUNCTION public.merge_entities IS 'Merge two entities into one, updating all references including entity_mentions';

-- =============================================================================
-- Fix #2: Update entity_mentions INSERT RLS policy to validate document_id
-- =============================================================================
-- The original policy only validated entity_id belonged to user's matter,
-- allowing cross-matter reference injection via document_id.

-- Drop the old policy
DROP POLICY IF EXISTS "Editors and Owners can insert entity mentions" ON public.entity_mentions;

-- Create the fixed policy with document_id validation
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

-- =============================================================================
-- Fix #3: Add composite index for listing entities by mention_count
-- =============================================================================
-- This index speeds up the common API query: list entities sorted by mention_count DESC

CREATE INDEX IF NOT EXISTS idx_identity_nodes_matter_mentions
ON public.identity_nodes(matter_id, mention_count DESC);

COMMENT ON INDEX idx_identity_nodes_matter_mentions IS 'Speeds up list_entities API sorted by most-mentioned';
