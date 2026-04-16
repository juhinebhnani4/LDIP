-- Add 'unmerge' to alias_corrections correction_type CHECK constraint
-- Fix: unmerge endpoint sends correction_type='unmerge' but constraint only allowed add/remove/merge

ALTER TABLE public.alias_corrections
  DROP CONSTRAINT alias_corrections_correction_type_check;

ALTER TABLE public.alias_corrections
  ADD CONSTRAINT alias_corrections_correction_type_check
  CHECK (correction_type IN ('add', 'remove', 'merge', 'unmerge'));
