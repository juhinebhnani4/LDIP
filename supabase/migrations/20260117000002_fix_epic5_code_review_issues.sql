-- Migration: Fix Epic 5 Code Review Issues
-- Date: 2026-01-17
-- Fixes issues found during Epic 5 (Contradiction Engine) code review:
--   1. CRITICAL: Add FK constraints for statement_a_id/statement_b_id to chunks
--   2. CRITICAL: Add trigger to enforce same-matter constraint for statement comparisons
--   3. MEDIUM: Add FK constraint for entity_id to identity_nodes
--   4. MEDIUM: Add check constraint for JSONB evidence schema validation
--   5. MEDIUM: Add validation function for anomalies.event_ids array

-- =============================================================================
-- Fix #1: Add FK constraints for statement_a_id and statement_b_id
-- =============================================================================
-- These columns reference chunks.id but had no actual FK constraint.
-- Risk: Orphaned comparisons when chunks are deleted, cross-matter pollution.

-- First, clean up any orphaned records that might exist (defensive)
DELETE FROM public.statement_comparisons sc
WHERE NOT EXISTS (
  SELECT 1 FROM public.chunks c WHERE c.id = sc.statement_a_id
)
OR NOT EXISTS (
  SELECT 1 FROM public.chunks c WHERE c.id = sc.statement_b_id
);

-- Add FK constraint for statement_a_id
ALTER TABLE public.statement_comparisons
  ADD CONSTRAINT fk_statement_comparisons_statement_a
  FOREIGN KEY (statement_a_id) REFERENCES public.chunks(id) ON DELETE CASCADE;

-- Add FK constraint for statement_b_id
ALTER TABLE public.statement_comparisons
  ADD CONSTRAINT fk_statement_comparisons_statement_b
  FOREIGN KEY (statement_b_id) REFERENCES public.chunks(id) ON DELETE CASCADE;

COMMENT ON CONSTRAINT fk_statement_comparisons_statement_a ON public.statement_comparisons IS
  'FK to chunks.id - cascades delete to prevent orphaned comparisons';

COMMENT ON CONSTRAINT fk_statement_comparisons_statement_b ON public.statement_comparisons IS
  'FK to chunks.id - cascades delete to prevent orphaned comparisons';

-- =============================================================================
-- Fix #2: Trigger to enforce same-matter constraint for statement comparisons
-- =============================================================================
-- CRITICAL: Both statement_a and statement_b MUST belong to the same matter_id
-- as the comparison record. This prevents cross-matter data pollution.

CREATE OR REPLACE FUNCTION public.validate_statement_comparison_matter()
RETURNS TRIGGER AS $$
DECLARE
  stmt_a_matter_id uuid;
  stmt_b_matter_id uuid;
BEGIN
  -- Get the matter_id for statement_a
  SELECT matter_id INTO stmt_a_matter_id
  FROM public.chunks
  WHERE id = NEW.statement_a_id;

  -- Get the matter_id for statement_b
  SELECT matter_id INTO stmt_b_matter_id
  FROM public.chunks
  WHERE id = NEW.statement_b_id;

  -- Validate both statements belong to the comparison's matter
  IF stmt_a_matter_id IS NULL OR stmt_a_matter_id != NEW.matter_id THEN
    RAISE EXCEPTION 'statement_a_id % does not belong to matter %',
      NEW.statement_a_id, NEW.matter_id;
  END IF;

  IF stmt_b_matter_id IS NULL OR stmt_b_matter_id != NEW.matter_id THEN
    RAISE EXCEPTION 'statement_b_id % does not belong to matter %',
      NEW.statement_b_id, NEW.matter_id;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for INSERT (main use case)
DROP TRIGGER IF EXISTS trg_validate_statement_comparison_matter ON public.statement_comparisons;
CREATE TRIGGER trg_validate_statement_comparison_matter
  BEFORE INSERT ON public.statement_comparisons
  FOR EACH ROW
  EXECUTE FUNCTION public.validate_statement_comparison_matter();

COMMENT ON FUNCTION public.validate_statement_comparison_matter() IS
  'Validates that statement_a_id and statement_b_id belong to the same matter as the comparison';

-- =============================================================================
-- Fix #3: Add FK constraint for entity_id to identity_nodes
-- =============================================================================
-- entity_id references the entity being compared but had no FK constraint.

-- Clean up any orphaned records first
DELETE FROM public.statement_comparisons sc
WHERE NOT EXISTS (
  SELECT 1 FROM public.identity_nodes n WHERE n.id = sc.entity_id
);

-- Add FK constraint for entity_id
ALTER TABLE public.statement_comparisons
  ADD CONSTRAINT fk_statement_comparisons_entity
  FOREIGN KEY (entity_id) REFERENCES public.identity_nodes(id) ON DELETE CASCADE;

COMMENT ON CONSTRAINT fk_statement_comparisons_entity ON public.statement_comparisons IS
  'FK to identity_nodes.id - cascades delete when entity is removed';

-- =============================================================================
-- Fix #4: Add check constraint for evidence JSONB schema (basic validation)
-- =============================================================================
-- The evidence column should have a recognized structure.
-- We can't enforce full schema, but we can ensure type field is valid.

CREATE OR REPLACE FUNCTION public.validate_contradiction_evidence(evidence jsonb)
RETURNS boolean AS $$
BEGIN
  -- Empty evidence is valid (default)
  IF evidence IS NULL OR evidence = '{}'::jsonb THEN
    RETURN true;
  END IF;

  -- If evidence has a type, it must be one of the recognized types
  IF evidence ? 'type' THEN
    IF NOT (evidence->>'type' IN (
      'none',
      'date_mismatch',
      'amount_mismatch',
      'quantity_mismatch',
      'semantic_conflict',
      'factual_conflict'
    )) THEN
      RETURN false;
    END IF;
  END IF;

  RETURN true;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Add constraint (won't fail existing valid data)
ALTER TABLE public.statement_comparisons
  ADD CONSTRAINT chk_evidence_valid_type
  CHECK (public.validate_contradiction_evidence(evidence));

COMMENT ON FUNCTION public.validate_contradiction_evidence(jsonb) IS
  'Validates evidence JSONB has recognized type field if present';

-- =============================================================================
-- Fix #5: Validation function for anomalies.event_ids array
-- =============================================================================
-- The event_ids array should only contain valid event IDs from the same matter.
-- Adding a trigger to validate this on INSERT/UPDATE.

CREATE OR REPLACE FUNCTION public.validate_anomaly_event_ids()
RETURNS TRIGGER AS $$
DECLARE
  invalid_event_id uuid;
BEGIN
  -- Skip validation if event_ids is empty
  IF NEW.event_ids IS NULL OR array_length(NEW.event_ids, 1) IS NULL THEN
    RETURN NEW;
  END IF;

  -- Find any event_id that doesn't exist or belongs to wrong matter
  SELECT e_id INTO invalid_event_id
  FROM unnest(NEW.event_ids) AS e_id
  WHERE NOT EXISTS (
    SELECT 1 FROM public.events e
    WHERE e.id = e_id AND e.matter_id = NEW.matter_id
  )
  LIMIT 1;

  IF invalid_event_id IS NOT NULL THEN
    RAISE EXCEPTION 'event_id % does not exist or does not belong to matter %',
      invalid_event_id, NEW.matter_id;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for anomalies table
DROP TRIGGER IF EXISTS trg_validate_anomaly_event_ids ON public.anomalies;
CREATE TRIGGER trg_validate_anomaly_event_ids
  BEFORE INSERT OR UPDATE ON public.anomalies
  FOR EACH ROW
  EXECUTE FUNCTION public.validate_anomaly_event_ids();

COMMENT ON FUNCTION public.validate_anomaly_event_ids() IS
  'Validates that all event_ids in anomalies array exist and belong to the same matter';

-- =============================================================================
-- Additional indexes for performance
-- =============================================================================

-- Index for looking up comparisons by statement IDs
CREATE INDEX IF NOT EXISTS idx_statement_comparisons_stmt_a
  ON public.statement_comparisons(statement_a_id);
CREATE INDEX IF NOT EXISTS idx_statement_comparisons_stmt_b
  ON public.statement_comparisons(statement_b_id);

COMMENT ON INDEX idx_statement_comparisons_stmt_a IS
  'Speeds up lookups for all comparisons involving a specific statement';
COMMENT ON INDEX idx_statement_comparisons_stmt_b IS
  'Speeds up lookups for all comparisons involving a specific statement';
