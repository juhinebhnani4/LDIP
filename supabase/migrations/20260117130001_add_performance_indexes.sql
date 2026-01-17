-- Performance indexes for slow endpoints
-- Story: API Performance Optimization
-- Fixes timeout issues on dashboard/stats, notifications, exports, contradictions, anomalies

-- =============================================================================
-- NOTIFICATIONS INDEXES
-- Improves: GET /api/notifications
-- =============================================================================

-- Composite index for efficient notification listing by user
CREATE INDEX IF NOT EXISTS idx_notifications_user_created
ON public.notifications(user_id, created_at DESC);

-- Index for unread count queries
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
ON public.notifications(user_id, is_read)
WHERE is_read = false;

-- =============================================================================
-- EXPORTS INDEXES
-- Improves: GET /api/matters/{matter_id}/exports
-- =============================================================================

-- Composite index for listing exports by matter (ordered by recency)
CREATE INDEX IF NOT EXISTS idx_exports_matter_created
ON public.exports(matter_id, created_at DESC);

-- =============================================================================
-- STATEMENT COMPARISONS (CONTRADICTIONS) INDEXES
-- Improves: GET /api/matters/{matter_id}/contradictions
-- =============================================================================

-- Composite index for contradiction queries with result filtering
CREATE INDEX IF NOT EXISTS idx_statement_comparisons_matter_result
ON public.statement_comparisons(matter_id, result, severity DESC, created_at DESC);

-- Indexes for statement lookups in batch operations
CREATE INDEX IF NOT EXISTS idx_statement_comparisons_statement_a
ON public.statement_comparisons(statement_a_id);

CREATE INDEX IF NOT EXISTS idx_statement_comparisons_statement_b
ON public.statement_comparisons(statement_b_id);

-- =============================================================================
-- FINDING VERIFICATIONS INDEXES
-- Improves: GET /api/dashboard/stats (verified findings count)
-- =============================================================================

-- Composite index for counting verified findings by matter
CREATE INDEX IF NOT EXISTS idx_finding_verifications_matter_decision
ON public.finding_verifications(matter_id, decision);

-- =============================================================================
-- FINDINGS INDEXES
-- Improves: GET /api/dashboard/stats (pending reviews count)
-- =============================================================================

-- Composite index for counting findings by matter and status
CREATE INDEX IF NOT EXISTS idx_findings_matter_status
ON public.findings(matter_id, status);

-- =============================================================================
-- ANOMALIES INDEXES (verify existing index is optimal)
-- Improves: GET /api/matters/{matter_id}/anomalies
-- =============================================================================

-- Composite index for anomaly listing (if not exists from previous migration)
CREATE INDEX IF NOT EXISTS idx_anomalies_matter_created
ON public.anomalies(matter_id, created_at DESC);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON INDEX idx_notifications_user_created IS 'Optimizes notification listing for user';
COMMENT ON INDEX idx_exports_matter_created IS 'Optimizes export listing by matter';
COMMENT ON INDEX idx_statement_comparisons_matter_result IS 'Optimizes contradiction queries';
COMMENT ON INDEX idx_finding_verifications_matter_decision IS 'Optimizes dashboard stats - verified count';
COMMENT ON INDEX idx_findings_matter_status IS 'Optimizes dashboard stats - pending count';
