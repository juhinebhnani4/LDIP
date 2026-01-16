-- =============================================================================
-- Story 14.5: Create Activities Table
-- Activity feed for dashboard showing user's recent activities across matters
-- =============================================================================

-- =============================================================================
-- Task 1.2: Create activity_type enum (AC #6)
-- =============================================================================

CREATE TYPE activity_type AS ENUM (
  'processing_complete',
  'processing_started',
  'processing_failed',
  'contradictions_found',
  'verification_needed',
  'matter_opened'
);

-- =============================================================================
-- Task 1.3: Create activities table (AC #5)
-- =============================================================================

CREATE TABLE public.activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  matter_id UUID REFERENCES public.matters(id) ON DELETE CASCADE, -- nullable for non-matter activities
  type activity_type NOT NULL,
  description TEXT NOT NULL,
  metadata JSONB DEFAULT '{}', -- extra context (doc count, contradiction count, etc.)
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Task 1.5: Create index for efficient feed queries (AC #5)
-- Index on (user_id, created_at DESC) for feed queries
-- =============================================================================

CREATE INDEX idx_activities_user_created ON public.activities(user_id, created_at DESC);

-- =============================================================================
-- Task 1.6: Create partial index for unread count queries (AC #5)
-- =============================================================================

CREATE INDEX idx_activities_user_unread ON public.activities(user_id, is_read) WHERE is_read = FALSE;

-- Additional index for matter filtering
CREATE INDEX idx_activities_matter_id ON public.activities(matter_id) WHERE matter_id IS NOT NULL;

-- =============================================================================
-- Task 1.4: RLS Policy - Users can only access their own activities (AC #5)
-- =============================================================================

ALTER TABLE public.activities ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own activities
-- Note: Activities are per-user, not per-matter. User can see activities
-- from all their matters in a single feed.
CREATE POLICY "Users access own activities only"
ON public.activities FOR SELECT
USING (user_id = auth.uid());

-- Policy: Users can insert activities for themselves
-- (Backend service will use service role key for pipeline activity creation)
CREATE POLICY "Users can insert own activities"
ON public.activities FOR INSERT
WITH CHECK (user_id = auth.uid());

-- Policy: Users can update their own activities (mark as read)
CREATE POLICY "Users can update own activities"
ON public.activities FOR UPDATE
USING (user_id = auth.uid());

-- Policy: Users can delete their own activities
CREATE POLICY "Users can delete own activities"
ON public.activities FOR DELETE
USING (user_id = auth.uid());

-- =============================================================================
-- Comments for documentation
-- =============================================================================

COMMENT ON TABLE public.activities IS 'Story 14.5: User activity feed for dashboard. Per-user activities aggregated across all matters.';
COMMENT ON COLUMN public.activities.id IS 'Unique identifier for the activity';
COMMENT ON COLUMN public.activities.user_id IS 'FK to auth.users - owner of this activity (RLS enforced)';
COMMENT ON COLUMN public.activities.matter_id IS 'FK to matters - optional, NULL for non-matter activities';
COMMENT ON COLUMN public.activities.type IS 'Activity type enum for icon/color coding in UI';
COMMENT ON COLUMN public.activities.description IS 'Human-readable description (no PII, generic)';
COMMENT ON COLUMN public.activities.metadata IS 'Extra context (doc count, contradiction count, etc.)';
COMMENT ON COLUMN public.activities.is_read IS 'Whether user has viewed/dismissed this activity';
COMMENT ON COLUMN public.activities.created_at IS 'Activity timestamp for sorting feed';
