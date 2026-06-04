-- Fix enum/constraint drift on citations.verification_status.
--
-- The CHECK constraint allowed the legacy value 'not_found', but the
-- application enum (app.models.citation.VerificationStatus) emits
-- 'section_not_found'. They diverged and the constraint was never updated, so
-- EVERY verification that resolved to "section not found" was rejected by the
-- DB (SQLSTATE 23514) and silently lost — the result was masked because the
-- verification batch loop counted the verification result, not the DB-write
-- outcome. This is why citations.verification_status only ever held
-- pending/verified/act_unavailable in production, and why section-not-found
-- citations stayed stuck in 'pending' forever.
--
-- No existing rows use 'not_found' (0 rows outside the 5 enum values at apply
-- time), so this is a safe widening that aligns the DB to the source-of-truth
-- enum. Discovered while shipping RISK-1 (derived-state citation verification);
-- the drift was the real blocker to verification convergence.

ALTER TABLE public.citations
  DROP CONSTRAINT IF EXISTS citations_verification_status_check;

ALTER TABLE public.citations
  ADD CONSTRAINT citations_verification_status_check
  CHECK (verification_status = ANY (ARRAY[
    'pending'::text,
    'verified'::text,
    'mismatch'::text,
    'section_not_found'::text,
    'act_unavailable'::text
  ]));
