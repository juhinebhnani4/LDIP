-- Migration: Change llm_costs.matter_id from CASCADE to SET NULL
-- Purpose: Preserve historical cost data when matters are deleted
--
-- Problem: ON DELETE CASCADE causes all cost records for a matter to be
-- permanently deleted when the matter is hard-deleted. This destroys
-- historical cost data needed for unit economics and billing analysis.
--
-- Fix: Change to ON DELETE SET NULL (same as document_id already uses).
-- Cost rows survive matter deletion with matter_id = NULL, preserving
-- aggregate totals for monthly reports and unit economics.

-- Step 1: Drop the existing foreign key constraint
ALTER TABLE public.llm_costs
    DROP CONSTRAINT IF EXISTS llm_costs_matter_id_fkey;

-- Step 2: Re-add with ON DELETE SET NULL instead of ON DELETE CASCADE
ALTER TABLE public.llm_costs
    ADD CONSTRAINT llm_costs_matter_id_fkey
    FOREIGN KEY (matter_id)
    REFERENCES public.matters(id)
    ON DELETE SET NULL;
