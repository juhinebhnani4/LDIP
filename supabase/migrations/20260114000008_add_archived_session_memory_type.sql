-- Add 'archived_session' to matter_memory.memory_type constraint
-- Story 7-2: Session TTL and Context Restoration

-- Drop existing constraint
ALTER TABLE public.matter_memory
DROP CONSTRAINT IF EXISTS matter_memory_memory_type_check;

-- Add new constraint with archived_session type
ALTER TABLE public.matter_memory
ADD CONSTRAINT matter_memory_memory_type_check
CHECK (memory_type IN (
  'query_history',
  'timeline_cache',
  'entity_graph',
  'key_findings',
  'research_notes',
  'archived_session'  -- Story 7-2: Session archival
));

-- Update the UNIQUE constraint to allow multiple archived sessions per matter/user
-- We need a different approach: use a composite key with user_id for archived sessions
-- Actually, we want to store multiple archived sessions, so we need to change the approach

-- Drop the existing unique constraint
ALTER TABLE public.matter_memory
DROP CONSTRAINT IF EXISTS matter_memory_matter_id_memory_type_key;

-- Add a partial unique constraint that only applies to non-archived types
CREATE UNIQUE INDEX idx_matter_memory_unique_non_archived
ON public.matter_memory(matter_id, memory_type)
WHERE memory_type != 'archived_session';

-- Add index for archived session queries (filter by matter and user)
CREATE INDEX IF NOT EXISTS idx_matter_memory_archived_sessions
ON public.matter_memory(matter_id, (data->>'user_id'), created_at DESC)
WHERE memory_type = 'archived_session';

-- Comment for archived_session type
COMMENT ON COLUMN public.matter_memory.memory_type IS 'Type of memory: query_history, timeline_cache, entity_graph, key_findings, research_notes, archived_session (Story 7-2)';
