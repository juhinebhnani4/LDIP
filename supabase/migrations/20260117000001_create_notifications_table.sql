-- =============================================================================
-- Story 14.10: Create Notifications Table
-- Real-time notifications for important events in matters
-- =============================================================================

-- =============================================================================
-- Task 1.2: Create notifications table (AC #1)
-- Table schema matching frontend Notification interface
-- =============================================================================

CREATE TABLE public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  matter_id UUID REFERENCES public.matters(id) ON DELETE CASCADE, -- nullable for non-matter notifications
  type TEXT NOT NULL CHECK (type IN ('success', 'info', 'warning', 'error', 'in_progress')),
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Task 1.3: Create index for efficient badge count and listing queries (AC #1)
-- Index on (user_id, is_read, created_at DESC)
-- =============================================================================

CREATE INDEX idx_notifications_user_unread_created ON public.notifications(user_id, is_read, created_at DESC);

-- Additional partial index for unread count performance
CREATE INDEX idx_notifications_user_unread_only ON public.notifications(user_id) WHERE is_read = FALSE;

-- =============================================================================
-- Task 1.4: RLS Policy - Users can only access their own notifications (AC #1)
-- =============================================================================

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own notifications
CREATE POLICY "Users can view own notifications"
ON public.notifications FOR SELECT
USING (user_id = auth.uid());

-- Policy: Users can update their own notifications (mark as read)
CREATE POLICY "Users can update own notifications"
ON public.notifications FOR UPDATE
USING (user_id = auth.uid());

-- Policy: Service role can insert notifications (for background job notifications)
-- Using permissive policy with true - service role bypasses RLS anyway
-- This allows backend to insert notifications for any user
CREATE POLICY "Service can insert notifications"
ON public.notifications FOR INSERT
WITH CHECK (true);

-- Policy: Users can delete their own notifications (optional cleanup)
CREATE POLICY "Users can delete own notifications"
ON public.notifications FOR DELETE
USING (user_id = auth.uid());

-- =============================================================================
-- Comments for documentation
-- =============================================================================

COMMENT ON TABLE public.notifications IS 'Story 14.10: User notifications for important events (processing complete, errors, verifications needed)';
COMMENT ON COLUMN public.notifications.id IS 'Unique identifier for the notification';
COMMENT ON COLUMN public.notifications.user_id IS 'FK to auth.users - owner of this notification (RLS enforced)';
COMMENT ON COLUMN public.notifications.matter_id IS 'FK to matters - optional, NULL for non-matter notifications';
COMMENT ON COLUMN public.notifications.type IS 'Notification type: success, info, warning, error, in_progress';
COMMENT ON COLUMN public.notifications.title IS 'Short title for the notification';
COMMENT ON COLUMN public.notifications.message IS 'Detailed message text';
COMMENT ON COLUMN public.notifications.priority IS 'Priority level: high, medium, low';
COMMENT ON COLUMN public.notifications.is_read IS 'Whether user has read this notification';
COMMENT ON COLUMN public.notifications.created_at IS 'Notification timestamp for sorting';
