-- Story 6-3: Matter Query History for Audit Trail
-- This table stores forensic audit records of all queries processed
-- Implements append-only semantics for legal compliance (NFR24)

-- =============================================================================
-- TABLE: matter_query_history - Query audit trail per matter
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.matter_query_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  query_id uuid NOT NULL,
  audit_data jsonb NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,

  -- Ensure unique query_id per matter
  CONSTRAINT unique_query_per_matter UNIQUE (matter_id, query_id)
);

-- =============================================================================
-- INDEXES: Efficient querying for audit analysis
-- =============================================================================

-- Basic lookup indexes
CREATE INDEX idx_query_history_matter_id ON public.matter_query_history(matter_id);
CREATE INDEX idx_query_history_created_at ON public.matter_query_history(created_at DESC);
CREATE INDEX idx_query_history_query_id ON public.matter_query_history(query_id);

-- Composite index for matter + time queries (most common pattern)
CREATE INDEX idx_query_history_matter_time ON public.matter_query_history(matter_id, created_at DESC);

-- GIN index for JSONB queries (e.g., searching by user_id in audit_data)
CREATE INDEX idx_query_history_audit_data ON public.matter_query_history USING gin(audit_data);

-- =============================================================================
-- ROW LEVEL SECURITY: Matter Isolation (CRITICAL)
-- =============================================================================

ALTER TABLE public.matter_query_history ENABLE ROW LEVEL SECURITY;

-- Users can only view query history for matters they belong to
CREATE POLICY "Users can view their matter query history"
ON public.matter_query_history FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Users can insert query history for matters they belong to
CREATE POLICY "Users can insert query history for their matters"
ON public.matter_query_history FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- =============================================================================
-- APPEND-ONLY ENFORCEMENT: Forensic Integrity
-- =============================================================================

-- Prevent updates - audit records are immutable
CREATE POLICY "Query history is append-only - no updates"
ON public.matter_query_history FOR UPDATE
USING (false);

-- Prevent deletes by regular users - only via service role for admin
CREATE POLICY "Query history cannot be deleted by users"
ON public.matter_query_history FOR DELETE
USING (false);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE public.matter_query_history IS
  'Forensic audit trail of all queries processed per matter. APPEND-ONLY - no updates or deletes allowed by users.';

COMMENT ON COLUMN public.matter_query_history.id IS 'Unique record identifier (UUID)';
COMMENT ON COLUMN public.matter_query_history.matter_id IS 'Matter this query belongs to (RLS enforced)';
COMMENT ON COLUMN public.matter_query_history.query_id IS 'Unique query identifier for deduplication';
COMMENT ON COLUMN public.matter_query_history.audit_data IS 'Complete audit entry as JSONB (QueryAuditEntry model)';
COMMENT ON COLUMN public.matter_query_history.created_at IS 'Timestamp when record was created';

-- =============================================================================
-- SAMPLE AUDIT_DATA STRUCTURE (for reference)
-- =============================================================================
-- {
--   "query_id": "uuid",
--   "matter_id": "uuid",
--   "query_text": "What citations are in this case?",
--   "query_intent": "citation",
--   "intent_confidence": 0.95,
--   "asked_by": "user-uuid",
--   "asked_at": "2026-01-14T10:30:00Z",
--   "engines_invoked": ["citation", "rag"],
--   "successful_engines": ["citation", "rag"],
--   "failed_engines": [],
--   "execution_time_ms": 250,
--   "wall_clock_time_ms": 180,
--   "findings_count": 5,
--   "response_summary": "Found 5 citations...",
--   "overall_confidence": 0.9,
--   "llm_costs": [
--     {"model_name": "gpt-3.5-turbo", "purpose": "intent_analysis", "input_tokens": 50, "output_tokens": 20, "cost_usd": 0.0001}
--   ],
--   "total_cost_usd": 0.0001,
--   "findings": [...]
-- }
