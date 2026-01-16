-- Epic 7 Code Review Fix: JSONB Append-Only Scalability Issue
--
-- Problem: append_to_matter_memory function grows JSONB arrays indefinitely,
-- causing performance degradation and potential OOM when reading large blobs.
--
-- Solution: Add configurable limit parameter with default of 500 entries.
-- When limit is exceeded, oldest entries are removed (FIFO).

-- =============================================================================
-- REPLACE append_to_matter_memory with bounded version
-- =============================================================================

CREATE OR REPLACE FUNCTION public.append_to_matter_memory(
  p_matter_id uuid,
  p_memory_type text,
  p_key text,
  p_item jsonb,
  p_max_entries int DEFAULT 500  -- Configurable limit, default 500
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
  v_current_array jsonb;
  v_new_array jsonb;
  v_array_length int;
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

  -- Get current array or empty array
  SELECT COALESCE(data->p_key, '[]'::jsonb)
  INTO v_current_array
  FROM public.matter_memory
  WHERE matter_id = p_matter_id AND memory_type = p_memory_type;

  -- If no row exists, start with empty array
  IF v_current_array IS NULL THEN
    v_current_array := '[]'::jsonb;
  END IF;

  -- Append new item
  v_new_array := v_current_array || p_item;
  v_array_length := jsonb_array_length(v_new_array);

  -- If over limit, trim oldest entries (FIFO)
  IF v_array_length > p_max_entries THEN
    -- Keep only the most recent p_max_entries items
    -- jsonb_path_query_array with slice: $[last - N + 1 to last]
    v_new_array := (
      SELECT jsonb_agg(elem)
      FROM (
        SELECT elem
        FROM jsonb_array_elements(v_new_array) WITH ORDINALITY AS t(elem, idx)
        ORDER BY idx DESC
        LIMIT p_max_entries
      ) sub
      ORDER BY (SELECT NULL)  -- Preserve order after reversing
    );

    -- Re-reverse to maintain chronological order (oldest first, newest last)
    v_new_array := (
      SELECT jsonb_agg(elem)
      FROM (
        SELECT elem
        FROM jsonb_array_elements(v_new_array) WITH ORDINALITY AS t(elem, idx)
        ORDER BY idx DESC
      ) sub
    );
  END IF;

  -- Upsert with the bounded array
  INSERT INTO public.matter_memory (matter_id, memory_type, data)
  VALUES (p_matter_id, p_memory_type, jsonb_build_object(p_key, v_new_array))
  ON CONFLICT (matter_id, memory_type)
  DO UPDATE SET
    data = jsonb_set(
      matter_memory.data,
      ARRAY[p_key],
      v_new_array
    ),
    updated_at = now()
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.append_to_matter_memory IS
'Append item to JSONB array in matter memory with bounded size (default 500 entries).
Oldest entries are removed when limit is exceeded (FIFO).
Epic 7 Code Review Fix: Prevents unbounded array growth.';


-- =============================================================================
-- Add helper function to get last N entries efficiently (DB-side slicing)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_matter_memory_entries(
  p_matter_id uuid,
  p_memory_type text,
  p_key text,
  p_limit int DEFAULT 100
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_result jsonb;
  v_array jsonb;
  v_array_length int;
BEGIN
  -- Verify user has access to this matter
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied: user cannot read memory for matter %', p_matter_id;
  END IF;

  -- Get the array from matter_memory
  SELECT data->p_key
  INTO v_array
  FROM public.matter_memory
  WHERE matter_id = p_matter_id AND memory_type = p_memory_type;

  -- Return empty array if not found
  IF v_array IS NULL THEN
    RETURN '[]'::jsonb;
  END IF;

  v_array_length := jsonb_array_length(v_array);

  -- If array is smaller than limit, return all
  IF v_array_length <= p_limit THEN
    RETURN v_array;
  END IF;

  -- Otherwise, return only the last p_limit entries (most recent)
  SELECT jsonb_agg(elem)
  INTO v_result
  FROM (
    SELECT elem
    FROM jsonb_array_elements(v_array) WITH ORDINALITY AS t(elem, idx)
    WHERE idx > (v_array_length - p_limit)
    ORDER BY idx
  ) sub;

  RETURN COALESCE(v_result, '[]'::jsonb);
END;
$$;

COMMENT ON FUNCTION public.get_matter_memory_entries IS
'Get last N entries from a JSONB array in matter memory efficiently (DB-side slicing).
Epic 7 Code Review Fix: Avoids loading entire blob into application memory.';
