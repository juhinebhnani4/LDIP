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
  'archived_session'
));

-- Drop the existing unique constraint to allow multiple archived sessions per matter
ALTER TABLE public.matter_memory
DROP CONSTRAINT IF EXISTS matter_memory_matter_id_memory_type_key;

-- Add a partial unique constraint that only applies to non-archived types
-- (archived_session can have multiple records per matter/user)
DROP INDEX IF EXISTS idx_matter_memory_unique_non_archived;
CREATE UNIQUE INDEX idx_matter_memory_unique_non_archived
ON public.matter_memory(matter_id, memory_type)
WHERE memory_type != 'archived_session';

-- Add index for archived session queries (filter by matter, user, ordered by recency)
CREATE INDEX IF NOT EXISTS idx_matter_memory_archived_sessions
ON public.matter_memory(matter_id, (data->>'user_id'), created_at DESC)
WHERE memory_type = 'archived_session';

-- Update column comment
COMMENT ON COLUMN public.matter_memory.memory_type IS 'Type of memory: query_history, timeline_cache, entity_graph, key_findings, research_notes, archived_session';
