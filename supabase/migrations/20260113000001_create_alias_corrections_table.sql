-- Migration: Create alias_corrections table for tracking manual corrections
-- Story: 2c-2 Alias Resolution
-- Purpose: Track user corrections to auto-detected aliases for learning and audit

-- =============================================================================
-- Alias Corrections Table
-- =============================================================================
-- Stores manual corrections to alias links, enabling:
-- 1. Audit trail of user corrections
-- 2. Learning from corrections to improve future auto-detection
-- 3. Rollback capability for incorrect corrections

CREATE TABLE IF NOT EXISTS public.alias_corrections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,

    -- The entity that was corrected
    entity_id uuid NOT NULL REFERENCES public.identity_nodes(id) ON DELETE CASCADE,

    -- Correction type: 'add' (added alias), 'remove' (removed alias), 'merge' (merged entities)
    correction_type text NOT NULL CHECK (correction_type IN ('add', 'remove', 'merge')),

    -- The alias name involved (for add/remove)
    alias_name text,

    -- For merges: the source entity that was merged into entity_id
    merged_entity_id uuid REFERENCES public.identity_nodes(id) ON DELETE SET NULL,
    merged_entity_name text, -- Preserved since entity may be deleted

    -- Original auto-detected confidence (if correcting an auto-link)
    original_confidence float,

    -- User who made the correction
    corrected_by uuid NOT NULL REFERENCES public.users(id),

    -- Optional reason for the correction
    reason text,

    -- Metadata for learning (context, similarity scores, etc.)
    metadata jsonb DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_alias_corrections_matter_id
    ON public.alias_corrections(matter_id);

CREATE INDEX IF NOT EXISTS idx_alias_corrections_entity_id
    ON public.alias_corrections(entity_id);

CREATE INDEX IF NOT EXISTS idx_alias_corrections_corrected_by
    ON public.alias_corrections(corrected_by);

CREATE INDEX IF NOT EXISTS idx_alias_corrections_type
    ON public.alias_corrections(correction_type);

CREATE INDEX IF NOT EXISTS idx_alias_corrections_created_at
    ON public.alias_corrections(created_at DESC);

-- =============================================================================
-- RLS Policies
-- =============================================================================
-- Matter-isolated access control

ALTER TABLE public.alias_corrections ENABLE ROW LEVEL SECURITY;

-- View: Matter members can view corrections
CREATE POLICY "Matter members can view alias corrections"
    ON public.alias_corrections
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.matter_attorneys ma
            WHERE ma.matter_id = alias_corrections.matter_id
            AND ma.user_id = auth.uid()
        )
    );

-- Insert: Editors and owners can create corrections
CREATE POLICY "Editors can create alias corrections"
    ON public.alias_corrections
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matter_attorneys ma
            WHERE ma.matter_id = alias_corrections.matter_id
            AND ma.user_id = auth.uid()
            AND ma.role IN ('owner', 'editor')
        )
    );

-- No update/delete - corrections are immutable audit records

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to get correction statistics for a matter
CREATE OR REPLACE FUNCTION get_correction_stats(p_matter_id uuid)
RETURNS TABLE (
    total_corrections bigint,
    add_count bigint,
    remove_count bigint,
    merge_count bigint,
    unique_entities bigint,
    unique_correctors bigint
)
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
    SELECT
        COUNT(*) as total_corrections,
        COUNT(*) FILTER (WHERE correction_type = 'add') as add_count,
        COUNT(*) FILTER (WHERE correction_type = 'remove') as remove_count,
        COUNT(*) FILTER (WHERE correction_type = 'merge') as merge_count,
        COUNT(DISTINCT entity_id) as unique_entities,
        COUNT(DISTINCT corrected_by) as unique_correctors
    FROM public.alias_corrections
    WHERE matter_id = p_matter_id;
$$;

-- Function to get recent corrections for learning
CREATE OR REPLACE FUNCTION get_recent_corrections(
    p_matter_id uuid,
    p_limit int DEFAULT 100
)
RETURNS TABLE (
    id uuid,
    entity_id uuid,
    entity_name text,
    correction_type text,
    alias_name text,
    merged_entity_name text,
    original_confidence float,
    reason text,
    created_at timestamptz
)
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
    SELECT
        ac.id,
        ac.entity_id,
        node.canonical_name as entity_name,
        ac.correction_type,
        ac.alias_name,
        ac.merged_entity_name,
        ac.original_confidence,
        ac.reason,
        ac.created_at
    FROM public.alias_corrections ac
    LEFT JOIN public.identity_nodes node ON node.id = ac.entity_id
    WHERE ac.matter_id = p_matter_id
    ORDER BY ac.created_at DESC
    LIMIT p_limit;
$$;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE public.alias_corrections IS 'Tracks manual corrections to auto-detected entity aliases for audit and learning';

COMMENT ON COLUMN public.alias_corrections.correction_type IS 'Type of correction: add (added alias), remove (removed alias), merge (merged entities)';

COMMENT ON COLUMN public.alias_corrections.original_confidence IS 'Original auto-detection confidence score before correction';

COMMENT ON COLUMN public.alias_corrections.metadata IS 'Additional context for learning: similarity scores, context used, etc.';
