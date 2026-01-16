-- =============================================================================
-- Story 14.4: Summary Verification Tables
-- Creates summary_verifications and summary_notes tables for attorney verification workflow
-- =============================================================================

-- =============================================================================
-- Task 1: Create summary_verifications table (AC #4)
-- =============================================================================

-- Create enum for verification decision
CREATE TYPE summary_verification_decision AS ENUM ('verified', 'flagged');

-- Create enum for summary section types
CREATE TYPE summary_section_type AS ENUM ('parties', 'subject_matter', 'current_status', 'key_issue');

-- Create summary_verifications table
CREATE TABLE IF NOT EXISTS summary_verifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
  section_type summary_section_type NOT NULL,
  section_id TEXT NOT NULL,  -- entityId for parties, "main" for subject_matter/current_status, issue id for key_issue
  decision summary_verification_decision NOT NULL,
  notes TEXT,
  verified_by UUID NOT NULL REFERENCES auth.users(id),
  verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Unique constraint: one verification per (matter_id, section_type, section_id)
  UNIQUE(matter_id, section_type, section_id)
);

-- Index for efficient lookups by matter
CREATE INDEX idx_summary_verifications_matter_id ON summary_verifications(matter_id);

-- Index for efficient lookups by matter and section
CREATE INDEX idx_summary_verifications_matter_section ON summary_verifications(matter_id, section_type, section_id);

-- Enable RLS
ALTER TABLE summary_verifications ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access verifications for matters they have access to
CREATE POLICY "Users access own matter verifications"
ON summary_verifications FOR ALL
USING (
  matter_id IN (
    SELECT ma.matter_id FROM matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- =============================================================================
-- Task 2: Create summary_notes table (AC #5)
-- =============================================================================

-- Create summary_notes table
CREATE TABLE IF NOT EXISTS summary_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
  section_type summary_section_type NOT NULL,
  section_id TEXT NOT NULL,
  text TEXT NOT NULL,
  created_by UUID NOT NULL REFERENCES auth.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- No unique constraint: multiple notes per section allowed
  CONSTRAINT summary_notes_text_not_empty CHECK (LENGTH(TRIM(text)) > 0)
);

-- Index for efficient queries
CREATE INDEX idx_summary_notes_matter_section ON summary_notes(matter_id, section_type, section_id);

-- Index for efficient lookups by matter
CREATE INDEX idx_summary_notes_matter_id ON summary_notes(matter_id);

-- Enable RLS
ALTER TABLE summary_notes ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access notes for matters they have access to
CREATE POLICY "Users access own matter notes"
ON summary_notes FOR ALL
USING (
  matter_id IN (
    SELECT ma.matter_id FROM matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- =============================================================================
-- Comments for documentation
-- =============================================================================

COMMENT ON TABLE summary_verifications IS 'Stores attorney verification decisions for summary sections (Story 14.4)';
COMMENT ON COLUMN summary_verifications.section_type IS 'Type of summary section being verified';
COMMENT ON COLUMN summary_verifications.section_id IS 'Entity ID for parties, "main" for subject_matter/current_status, issue ID for key_issue';
COMMENT ON COLUMN summary_verifications.decision IS 'Verification decision: verified or flagged';
COMMENT ON COLUMN summary_verifications.verified_by IS 'User who made the verification decision';

COMMENT ON TABLE summary_notes IS 'Stores attorney notes on summary sections (Story 14.4)';
COMMENT ON COLUMN summary_notes.section_type IS 'Type of summary section';
COMMENT ON COLUMN summary_notes.section_id IS 'Section identifier';
COMMENT ON COLUMN summary_notes.text IS 'Note text content';
COMMENT ON COLUMN summary_notes.created_by IS 'User who created the note';
