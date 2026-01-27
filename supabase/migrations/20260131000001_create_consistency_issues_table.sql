-- Story 5.4: Cross-Engine Consistency Checking
-- Creates consistency_issues table for tracking cross-engine data inconsistencies
--
-- Tracks issues like:
-- - Date discrepancies between timeline and entity mentions
-- - Entity name variations between MIG and citations
-- - Amount/value discrepancies between extractions

-- =============================================================================
-- Table: consistency_issues
-- =============================================================================

CREATE TABLE IF NOT EXISTS consistency_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,

    -- Issue type and severity
    issue_type TEXT NOT NULL CHECK (issue_type IN (
        'date_mismatch',
        'entity_name_mismatch',
        'amount_discrepancy',
        'citation_conflict',
        'timeline_gap',
        'duplicate_event'
    )),
    severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN (
        'info',
        'warning',
        'error'
    )),

    -- Source references (engine-specific)
    source_engine TEXT NOT NULL CHECK (source_engine IN (
        'timeline',
        'entity',
        'citation',
        'contradiction',
        'rag'
    )),
    source_id UUID, -- Reference to the source record (event_id, entity_id, etc.)
    source_value TEXT, -- The value from the source engine

    -- Conflicting reference
    conflicting_engine TEXT NOT NULL CHECK (conflicting_engine IN (
        'timeline',
        'entity',
        'citation',
        'contradiction',
        'rag'
    )),
    conflicting_id UUID, -- Reference to the conflicting record
    conflicting_value TEXT, -- The conflicting value

    -- Issue details
    description TEXT NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    document_name TEXT, -- Denormalized for display

    -- Resolution tracking
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
        'open',
        'reviewed',
        'resolved',
        'dismissed'
    )),
    resolved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Metadata
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Primary query patterns
CREATE INDEX idx_consistency_issues_matter_id ON consistency_issues(matter_id);
CREATE INDEX idx_consistency_issues_matter_status ON consistency_issues(matter_id, status);
CREATE INDEX idx_consistency_issues_type ON consistency_issues(issue_type);
CREATE INDEX idx_consistency_issues_severity ON consistency_issues(severity);
CREATE INDEX idx_consistency_issues_detected_at ON consistency_issues(detected_at DESC);

-- Source lookups
CREATE INDEX idx_consistency_issues_source ON consistency_issues(source_engine, source_id);
CREATE INDEX idx_consistency_issues_conflicting ON consistency_issues(conflicting_engine, conflicting_id);

-- Document-based lookups
CREATE INDEX idx_consistency_issues_document_id ON consistency_issues(document_id) WHERE document_id IS NOT NULL;

-- =============================================================================
-- Row Level Security
-- =============================================================================

ALTER TABLE consistency_issues ENABLE ROW LEVEL SECURITY;

-- Users can only see issues for matters they have access to
CREATE POLICY "Users can view consistency issues for their matters"
ON consistency_issues
FOR SELECT
USING (
    matter_id IN (
        SELECT matter_id FROM matter_members
        WHERE user_id = auth.uid()
    )
);

-- Users with editor+ role can update issues (resolve/dismiss)
CREATE POLICY "Editors can update consistency issues"
ON consistency_issues
FOR UPDATE
USING (
    matter_id IN (
        SELECT matter_id FROM matter_members
        WHERE user_id = auth.uid()
        AND role IN ('editor', 'owner')
    )
);

-- Service role can insert/delete
CREATE POLICY "Service role can manage consistency issues"
ON consistency_issues
FOR ALL
USING (
    (SELECT current_setting('request.jwt.claims', true)::json->>'role' = 'service_role')
);

-- =============================================================================
-- Trigger for updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_consistency_issues_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER consistency_issues_updated_at
    BEFORE UPDATE ON consistency_issues
    FOR EACH ROW
    EXECUTE FUNCTION update_consistency_issues_updated_at();

-- =============================================================================
-- Helper function: Get consistency issue counts by matter
-- =============================================================================

CREATE OR REPLACE FUNCTION get_consistency_issue_counts(p_matter_id UUID)
RETURNS TABLE (
    total_count BIGINT,
    open_count BIGINT,
    warning_count BIGINT,
    error_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_count,
        COUNT(*) FILTER (WHERE status = 'open')::BIGINT as open_count,
        COUNT(*) FILTER (WHERE severity = 'warning' AND status = 'open')::BIGINT as warning_count,
        COUNT(*) FILTER (WHERE severity = 'error' AND status = 'open')::BIGINT as error_count
    FROM consistency_issues
    WHERE matter_id = p_matter_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION get_consistency_issue_counts(UUID) TO authenticated;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE consistency_issues IS 'Story 5.4: Cross-engine consistency issue tracking';
COMMENT ON COLUMN consistency_issues.issue_type IS 'Type of consistency issue detected';
COMMENT ON COLUMN consistency_issues.source_engine IS 'Engine where the original data was found';
COMMENT ON COLUMN consistency_issues.conflicting_engine IS 'Engine with conflicting data';
COMMENT ON COLUMN consistency_issues.status IS 'Review/resolution status of the issue';

-- =============================================================================
-- Rollback Instructions
-- =============================================================================
-- To rollback this migration, run the following in order:
--
-- REVOKE EXECUTE ON FUNCTION get_consistency_issue_counts(UUID) FROM authenticated;
-- DROP FUNCTION IF EXISTS get_consistency_issue_counts(UUID);
-- DROP TRIGGER IF EXISTS consistency_issues_updated_at ON consistency_issues;
-- DROP FUNCTION IF EXISTS update_consistency_issues_updated_at();
-- DROP POLICY IF EXISTS "Service role can manage consistency issues" ON consistency_issues;
-- DROP POLICY IF EXISTS "Editors can update consistency issues" ON consistency_issues;
-- DROP POLICY IF EXISTS "Users can view consistency issues for their matters" ON consistency_issues;
-- DROP TABLE IF EXISTS consistency_issues;
