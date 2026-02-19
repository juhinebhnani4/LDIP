-- =============================================================================
-- Migration: Fix get_job_queue_stats RPC for service role access
-- =============================================================================
-- BUG-007: The get_job_queue_stats function uses auth.uid() for authorization,
-- but the backend calls it with the service role key where auth.uid() is NULL.
-- This causes "Access denied" errors on every poll (~2s), filling logs with
-- warnings and preventing the queue stats feature from working.
--
-- Fix: Skip the auth.uid() check when it's NULL (service role calls).
-- The backend already handles authorization via validate_matter_access()
-- middleware before calling this RPC. This matches the pattern used in
-- search RPCs (see 20260117140001_fix_search_rpc_service_role.sql).
-- =============================================================================

-- Recreate with service role bypass
CREATE OR REPLACE FUNCTION public.get_job_queue_stats(p_matter_id uuid)
RETURNS TABLE (
  queued bigint,
  processing bigint,
  completed bigint,
  failed bigint,
  cancelled bigint,
  skipped bigint,
  avg_processing_time_ms bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Verify user has access to matter (defense in depth)
  -- Skip check if auth.uid() is NULL (service role - backend handles auth)
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied: user cannot view jobs for matter %', p_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    COUNT(*) FILTER (WHERE pj.status = 'QUEUED') AS queued,
    COUNT(*) FILTER (WHERE pj.status = 'PROCESSING') AS processing,
    COUNT(*) FILTER (WHERE pj.status = 'COMPLETED') AS completed,
    COUNT(*) FILTER (WHERE pj.status = 'FAILED') AS failed,
    COUNT(*) FILTER (WHERE pj.status = 'CANCELLED') AS cancelled,
    COUNT(*) FILTER (WHERE pj.status = 'SKIPPED') AS skipped,
    COALESCE(
      AVG(
        EXTRACT(EPOCH FROM (pj.completed_at - pj.started_at)) * 1000
      ) FILTER (WHERE pj.status = 'COMPLETED' AND pj.started_at IS NOT NULL AND pj.completed_at IS NOT NULL),
      0
    )::bigint AS avg_processing_time_ms
  FROM public.processing_jobs pj
  WHERE pj.matter_id = p_matter_id;
END;
$$;

COMMENT ON FUNCTION public.get_job_queue_stats IS 'Get job queue statistics for a matter (service role compatible)';
