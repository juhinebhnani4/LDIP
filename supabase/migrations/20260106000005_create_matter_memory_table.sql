-- Create matter_memory table for persistent matter-level storage
-- This implements Layer 1 of 4-layer matter isolation (Story 1-7)
-- Part of the Three-Layer Memory System (FR5, FR6)

-- =============================================================================
-- TABLE: matter_memory - PostgreSQL JSONB storage for matter context
-- =============================================================================

CREATE TABLE public.matter_memory (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  memory_type text NOT NULL CHECK (memory_type IN ('query_history', 'timeline_cache', 'entity_graph', 'key_findings', 'research_notes')),
  data jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  -- One entry per memory type per matter
  UNIQUE(matter_id, memory_type)
);

-- =============================================================================
-- INDEXES: Optimized for matter memory access
-- =============================================================================

-- Basic lookup
CREATE INDEX idx_matter_memory_matter_id ON public.matter_memory(matter_id);
CREATE INDEX idx_matter_memory_type ON public.matter_memory(memory_type);

-- JSONB data access
CREATE INDEX idx_matter_memory_data ON public.matter_memory USING GIN (data);

-- Comments
COMMENT ON TABLE public.matter_memory IS 'Persistent matter-level memory storage (Layer 2 of Three-Layer Memory)';
COMMENT ON COLUMN public.matter_memory.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.matter_memory.memory_type IS 'Type of memory: query_history, timeline_cache, entity_graph, key_findings, research_notes';
COMMENT ON COLUMN public.matter_memory.data IS 'JSONB storage for flexible memory structures';

-- Memory type descriptions:
-- query_history: Past queries and their responses for context continuity
-- timeline_cache: Cached timeline data for fast rendering
-- entity_graph: Cached entity relationships from MIG
-- key_findings: Verified findings saved by attorney
-- research_notes: Attorney notes and annotations

-- =============================================================================
-- RLS POLICIES: matter_memory table - Layer 1 of 4-layer matter isolation
-- =============================================================================

ALTER TABLE public.matter_memory ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT memory from matters where they have any role
CREATE POLICY "Users can view matter memory from their matters"
ON public.matter_memory FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT memory entries
CREATE POLICY "Editors and Owners can insert matter memory"
ON public.matter_memory FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE memory entries
CREATE POLICY "Editors and Owners can update matter memory"
ON public.matter_memory FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Owners can DELETE memory entries
CREATE POLICY "Only Owners can delete matter memory"
ON public.matter_memory FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- TRIGGER: Auto-update updated_at on modification
-- =============================================================================

CREATE TRIGGER set_matter_memory_updated_at
  BEFORE UPDATE ON public.matter_memory
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTIONS: Upsert matter memory
-- =============================================================================

CREATE OR REPLACE FUNCTION public.upsert_matter_memory(
  p_matter_id uuid,
  p_memory_type text,
  p_data jsonb
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  -- Verify user has editor or owner access
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  ) THEN
    RAISE EXCEPTION 'Access denied: user cannot modify memory for matter %', p_matter_id;
  END IF;

  INSERT INTO public.matter_memory (matter_id, memory_type, data)
  VALUES (p_matter_id, p_memory_type, p_data)
  ON CONFLICT (matter_id, memory_type)
  DO UPDATE SET
    data = p_data,
    updated_at = now()
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.upsert_matter_memory IS 'Upsert matter memory with access control';

-- Function to append to JSONB array in matter memory (useful for query_history)
CREATE OR REPLACE FUNCTION public.append_to_matter_memory(
  p_matter_id uuid,
  p_memory_type text,
  p_key text,
  p_item jsonb
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  -- Verify user has editor or owner access
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  ) THEN
    RAISE EXCEPTION 'Access denied: user cannot modify memory for matter %', p_matter_id;
  END IF;

  INSERT INTO public.matter_memory (matter_id, memory_type, data)
  VALUES (p_matter_id, p_memory_type, jsonb_build_object(p_key, jsonb_build_array(p_item)))
  ON CONFLICT (matter_id, memory_type)
  DO UPDATE SET
    data = jsonb_set(
      matter_memory.data,
      ARRAY[p_key],
      COALESCE(matter_memory.data->p_key, '[]'::jsonb) || p_item
    ),
    updated_at = now()
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.append_to_matter_memory IS 'Append item to JSONB array in matter memory';
