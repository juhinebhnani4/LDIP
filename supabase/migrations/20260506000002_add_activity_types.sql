-- UX-004: Add new activity types for richer activity feed
-- Adds document_uploaded and summary_generated to the activity_type enum.
-- These types are used by create_activity() calls in the upload endpoint
-- and summary generation task.

ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'document_uploaded';
ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'summary_generated';
