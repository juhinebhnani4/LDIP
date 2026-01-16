-- Migration: Create summary_edits table
-- Story 14.6: Summary Frontend Integration (Task 1.3)
-- Creates table for tracking edited summary sections with audit trail

-- Create enum type for summary section types (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'summary_section_type') THEN
        CREATE TYPE summary_section_type AS ENUM (
            'parties',
            'subject_matter',
            'current_status',
            'key_issue'
        );
    END IF;
END $$;

-- Create summary_edits table
CREATE TABLE IF NOT EXISTS summary_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    section_type summary_section_type NOT NULL,
    section_id TEXT NOT NULL,  -- "main" for subject_matter/current_status, entity_id for parties
    original_content TEXT NOT NULL,
    edited_content TEXT NOT NULL,
    edited_by UUID NOT NULL REFERENCES auth.users(id),
    edited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: one edit record per section per matter (upsert pattern)
    CONSTRAINT summary_edits_matter_section_unique UNIQUE(matter_id, section_type, section_id)
);

-- Enable RLS
ALTER TABLE summary_edits ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access edits for matters they have access to
CREATE POLICY "Users access own matter edits"
ON summary_edits FOR ALL
USING (
    matter_id IN (
        SELECT matter_id FROM matter_attorneys
        WHERE user_id = auth.uid()
    )
);

-- Index for efficient queries by matter and section
CREATE INDEX IF NOT EXISTS idx_summary_edits_matter_section
ON summary_edits(matter_id, section_type, section_id);

-- Index for querying by editor
CREATE INDEX IF NOT EXISTS idx_summary_edits_edited_by
ON summary_edits(edited_by);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_summary_edits_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER summary_edits_updated_at_trigger
    BEFORE UPDATE ON summary_edits
    FOR EACH ROW
    EXECUTE FUNCTION update_summary_edits_updated_at();

COMMENT ON TABLE summary_edits IS 'Stores user edits to AI-generated summary sections (Story 14.6)';
COMMENT ON COLUMN summary_edits.section_type IS 'Type of summary section: parties, subject_matter, current_status, key_issue';
COMMENT ON COLUMN summary_edits.section_id IS 'Section identifier: "main" for single sections, entity_id for parties';
COMMENT ON COLUMN summary_edits.original_content IS 'Original AI-generated content (never lost)';
COMMENT ON COLUMN summary_edits.edited_content IS 'User-edited content';
