-- Story 5.4: Cross-Engine Consistency Checking
-- Creates consistency_issues table for tracking cross-engine data inconsistencies
-- (Replaces 20260131000001 which had wrong table name in RLS policies)

-- =============================================================================
-- Table: consistency_issues
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.consistency_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,

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
    source_id UUID,
    source_value TEXT,

    -- Conflicting reference
    conflicting_engine TEXT NOT NULL CHECK (conflicting_engine IN (
        'timeline',
        'entity',
        'citation',
        'contradiction',
        'rag'
    )),
    conflicting_id UUID,
    conflicting_value TEXT,

    -- Issue details
    description TEXT NOT NULL,
    document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
    document_name TEXT,

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

CREATE INDEX IF NOT EXISTS idx_consistency_issues_matter_id ON public.consistency_issues(matter_id);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_matter_status ON public.consistency_issues(matter_id, status);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_type ON public.consistency_issues(issue_type);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_severity ON public.consistency_issues(severity);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_detected_at ON public.consistency_issues(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_source ON public.consistency_issues(source_engine, source_id);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_conflicting ON public.consistency_issues(conflicting_engine, conflicting_id);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_document_id ON public.consistency_issues(document_id) WHERE document_id IS NOT NULL;

-- =============================================================================
-- Row Level Security
-- =============================================================================

ALTER TABLE public.consistency_issues ENABLE ROW LEVEL SECURITY;

-- Users can only see issues for matters they have access to
CREATE POLICY "Users can view consistency issues for their matters"
ON public.consistency_issues
FOR SELECT
USING (
    matter_id IN (
        SELECT ma.matter_id FROM public.matter_attorneys ma
        WHERE ma.user_id = (select auth.uid())
    )
);

-- Users with editor+ role can update issues (resolve/dismiss)
CREATE POLICY "Editors can update consistency issues"
ON public.consistency_issues
FOR UPDATE
USING (
    matter_id IN (
        SELECT ma.matter_id FROM public.matter_attorneys ma
        WHERE ma.user_id = (select auth.uid())
        AND ma.role IN ('editor', 'owner')
    )
);

-- Service role can insert/delete
CREATE POLICY "Service role can manage consistency issues"
ON public.consistency_issues
FOR ALL
USING (
    (SELECT current_setting('request.jwt.claims', true)::json->>'role' = 'service_role')
);

-- =============================================================================
-- Trigger for updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION public.update_consistency_issues_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER consistency_issues_updated_at
    BEFORE UPDATE ON public.consistency_issues
    FOR EACH ROW
    EXECUTE FUNCTION public.update_consistency_issues_updated_at();

-- =============================================================================
-- Helper function: Get consistency issue counts by matter
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_consistency_issue_counts(p_matter_id UUID)
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
        COUNT(*) FILTER (WHERE ci.status = 'open')::BIGINT as open_count,
        COUNT(*) FILTER (WHERE ci.severity = 'warning' AND ci.status = 'open')::BIGINT as warning_count,
        COUNT(*) FILTER (WHERE ci.severity = 'error' AND ci.status = 'open')::BIGINT as error_count
    FROM public.consistency_issues ci
    WHERE ci.matter_id = p_matter_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION public.get_consistency_issue_counts(UUID) TO authenticated;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE public.consistency_issues IS 'Story 5.4: Cross-engine consistency issue tracking';
COMMENT ON COLUMN public.consistency_issues.issue_type IS 'Type of consistency issue detected';
COMMENT ON COLUMN public.consistency_issues.source_engine IS 'Engine where the original data was found';
COMMENT ON COLUMN public.consistency_issues.conflicting_engine IS 'Engine with conflicting data';
COMMENT ON COLUMN public.consistency_issues.status IS 'Review/resolution status of the issue';
