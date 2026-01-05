-- Create audit_logs table for compliance and security auditing
-- This table stores all security-related events for auditing purposes
-- NOTE: This table intentionally does NOT have RLS - it's accessed via service role only

-- =============================================================================
-- TABLE: audit_logs - Security audit trail
-- =============================================================================

CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  matter_id uuid REFERENCES public.matters(id) ON DELETE SET NULL,
  action text NOT NULL,
  result text NOT NULL CHECK (result IN ('success', 'denied', 'error', 'blocked')),
  ip_address inet,
  user_agent text,
  path text,
  method text,
  details jsonb,
  created_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: Optimized for security analysis and compliance queries
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_audit_logs_event_type ON public.audit_logs(event_type);
CREATE INDEX idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX idx_audit_logs_matter_id ON public.audit_logs(matter_id);
CREATE INDEX idx_audit_logs_created_at ON public.audit_logs(created_at);
CREATE INDEX idx_audit_logs_result ON public.audit_logs(result);
CREATE INDEX idx_audit_logs_ip ON public.audit_logs(ip_address);

-- Composite index for time-based queries
CREATE INDEX idx_audit_logs_user_time ON public.audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_matter_time ON public.audit_logs(matter_id, created_at DESC);

-- Security analysis index (denied/blocked events)
CREATE INDEX idx_audit_logs_security_events ON public.audit_logs(event_type, result, created_at)
  WHERE result IN ('denied', 'blocked', 'error');

-- Failed access attempts (for intrusion detection)
CREATE INDEX idx_audit_logs_failed_access ON public.audit_logs(ip_address, created_at)
  WHERE result = 'denied';

-- JSONB index for details queries
CREATE INDEX idx_audit_logs_details ON public.audit_logs USING GIN (details);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE public.audit_logs IS 'Security audit trail - NOT RLS protected, service role access only';
COMMENT ON COLUMN public.audit_logs.event_type IS 'Type of security event (e.g., matter_access_granted, rls_violation)';
COMMENT ON COLUMN public.audit_logs.user_id IS 'User who triggered the event (may be NULL for anonymous)';
COMMENT ON COLUMN public.audit_logs.matter_id IS 'Matter involved in the event (may be NULL)';
COMMENT ON COLUMN public.audit_logs.action IS 'Human-readable action description';
COMMENT ON COLUMN public.audit_logs.result IS 'Result: success, denied, error, or blocked';
COMMENT ON COLUMN public.audit_logs.ip_address IS 'Client IP address';
COMMENT ON COLUMN public.audit_logs.user_agent IS 'Client user agent string';
COMMENT ON COLUMN public.audit_logs.path IS 'Request path';
COMMENT ON COLUMN public.audit_logs.method IS 'HTTP method';
COMMENT ON COLUMN public.audit_logs.details IS 'Additional event-specific details as JSONB';

-- =============================================================================
-- SECURITY NOTE: No RLS on this table
-- =============================================================================
-- This table intentionally does NOT have Row Level Security enabled.
-- Access is restricted to:
-- 1. Service role (for writing audit logs from backend)
-- 2. Admin users via explicit permission checks in application code
--
-- This is because:
-- - Audit logs contain sensitive security information
-- - Users should not be able to see or modify their own audit trails
-- - Security analysis requires full access to all events
--
-- The backend service writes to this table using the service role key.

-- =============================================================================
-- RETENTION POLICY (Optional - uncomment if needed)
-- =============================================================================

-- Create a function to clean up old audit logs
-- CREATE OR REPLACE FUNCTION public.cleanup_old_audit_logs()
-- RETURNS void
-- LANGUAGE plpgsql
-- SECURITY DEFINER
-- AS $$
-- BEGIN
--   -- Delete audit logs older than 1 year
--   DELETE FROM public.audit_logs
--   WHERE created_at < now() - INTERVAL '1 year';
-- END;
-- $$;

-- Schedule cleanup (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-audit-logs', '0 0 * * *', 'SELECT cleanup_old_audit_logs()');
