-- Fix: Enable RLS on matter_summaries table
-- The original migration (20260428000001) omitted RLS, leaving the table
-- publicly accessible via PostgREST (Supabase security advisory).
--
-- Access pattern: backend reads/writes via service_role (bypasses RLS).
-- Frontend/anon access scoped via matter_attorneys membership, same as
-- matters, documents, chunks, etc.

ALTER TABLE public.matter_summaries ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT summaries for matters they belong to
CREATE POLICY "Users can view summaries for own matters"
ON public.matter_summaries FOR SELECT
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = auth.uid()
  )
);

-- Policy 2: Only service_role inserts/updates summaries (backend pipeline).
-- No INSERT/UPDATE/DELETE policies for anon/authenticated — the backend
-- uses service_role which bypasses RLS entirely.
-- If a future frontend feature needs direct writes, add policies then.
