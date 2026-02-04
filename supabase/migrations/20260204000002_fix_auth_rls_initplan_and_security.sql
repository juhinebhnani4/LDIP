-- Migration: Fix auth_rls_initplan, security_definer_view, and function_search_path warnings
-- Purpose: Wrap auth.uid() in (select auth.uid()) for InitPlan optimization,
--          fix security definer views, and set search_path on functions.
--
-- The (select auth.uid()) pattern forces Postgres to evaluate auth.uid() once
-- per query as an InitPlan, rather than re-evaluating it for each row.

-- =============================================================================
-- 1. VIEWS: Fix security_definer_view (ERROR level)
-- =============================================================================

ALTER VIEW public.active_identity_nodes SET (security_invoker = on);
ALTER VIEW public.practice_group_costs SET (security_invoker = on);

-- =============================================================================
-- 2. FUNCTIONS: Fix function_search_path_mutable
-- =============================================================================

-- get_monthly_cost_report - add search_path
CREATE OR REPLACE FUNCTION get_monthly_cost_report(
    p_year INTEGER,
    p_month INTEGER
)
RETURNS TABLE (
    practice_group VARCHAR,
    matter_count BIGINT,
    document_count BIGINT,
    total_cost_inr NUMERIC,
    total_cost_usd NUMERIC,
    total_tokens BIGINT,
    operation_count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_start_date DATE;
    v_end_date DATE;
BEGIN
    v_start_date := make_date(p_year, p_month, 1);
    v_end_date := v_start_date + INTERVAL '1 month';

    RETURN QUERY
    SELECT
        COALESCE(m.practice_group, 'Unassigned')::VARCHAR as practice_group,
        COUNT(DISTINCT m.id) as matter_count,
        COUNT(DISTINCT lc.document_id) as document_count,
        COALESCE(SUM(lc.total_cost_inr), 0)::NUMERIC as total_cost_inr,
        COALESCE(SUM(lc.total_cost_usd), 0)::NUMERIC as total_cost_usd,
        COALESCE(SUM(lc.input_tokens + lc.output_tokens), 0)::BIGINT as total_tokens,
        COUNT(lc.*)::BIGINT as operation_count
    FROM public.matters m
    LEFT JOIN public.llm_costs lc ON m.id = lc.matter_id
        AND lc.created_at >= v_start_date
        AND lc.created_at < v_end_date
    WHERE m.deleted_at IS NULL
    GROUP BY COALESCE(m.practice_group, 'Unassigned')
    ORDER BY total_cost_inr DESC NULLS LAST;
END;
$$;

-- update_llm_quota_limits_updated_at - add search_path
CREATE OR REPLACE FUNCTION public.update_llm_quota_limits_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- =============================================================================
-- 3. RLS POLICIES: Wrap auth.uid() in (select auth.uid())
-- =============================================================================

-- ---- users ----

DROP POLICY IF EXISTS "Users can view own profile" ON public.users;
CREATE POLICY "Users can view own profile"
ON public.users FOR SELECT
USING ((select auth.uid()) = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.users;
CREATE POLICY "Users can update own profile"
ON public.users FOR UPDATE
USING ((select auth.uid()) = id);

-- ---- matter_attorneys ----

DROP POLICY IF EXISTS "Owners can insert members" ON public.matter_attorneys;
CREATE POLICY "Owners can insert members"
ON public.matter_attorneys FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_attorneys.matter_id
    AND ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

DROP POLICY IF EXISTS "Owners can update member roles" ON public.matter_attorneys;
CREATE POLICY "Owners can update member roles"
ON public.matter_attorneys FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_attorneys.matter_id
    AND ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
)
WITH CHECK (
  NOT (user_id = (select auth.uid()) AND role != 'owner')
);

DROP POLICY IF EXISTS "Owners can delete members" ON public.matter_attorneys;
CREATE POLICY "Owners can delete members"
ON public.matter_attorneys FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = matter_attorneys.matter_id
    AND ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
  AND user_id != (select auth.uid())
);

-- ---- matters ----

DROP POLICY IF EXISTS "Users can view own matters" ON public.matters;
CREATE POLICY "Users can view own matters"
ON public.matters FOR SELECT
USING (
  id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
  )
  AND deleted_at IS NULL
);

DROP POLICY IF EXISTS "Authenticated users can create matters" ON public.matters;
CREATE POLICY "Authenticated users can create matters"
ON public.matters FOR INSERT
WITH CHECK ((select auth.uid()) IS NOT NULL);

DROP POLICY IF EXISTS "Editors and Owners can update matters" ON public.matters;
CREATE POLICY "Editors and Owners can update matters"
ON public.matters FOR UPDATE
USING (
  id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
    AND role IN ('owner', 'editor')
  )
  AND deleted_at IS NULL
);

DROP POLICY IF EXISTS "Only Owners can delete matters" ON public.matters;
CREATE POLICY "Only Owners can delete matters"
ON public.matters FOR DELETE
USING (
  id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
    AND role = 'owner'
  )
);

-- ---- documents ----

DROP POLICY IF EXISTS "Users can view documents from their matters" ON public.documents;
CREATE POLICY "Users can view documents from their matters"
ON public.documents FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can upload documents" ON public.documents;
CREATE POLICY "Editors and Owners can upload documents"
ON public.documents FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update documents" ON public.documents;
CREATE POLICY "Editors and Owners can update documents"
ON public.documents FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete documents" ON public.documents;
CREATE POLICY "Only Owners can delete documents"
ON public.documents FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- Also fix the RESTRICTIVE policy from previous migration
DROP POLICY IF EXISTS "Prevent deletion of auto-fetched documents" ON public.documents;
CREATE POLICY "Prevent deletion of auto-fetched documents"
ON public.documents AS RESTRICTIVE FOR DELETE
USING (
  source != 'auto_fetched'
  OR matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- chunks ----

DROP POLICY IF EXISTS "Users can view chunks from their matters" ON public.chunks;
CREATE POLICY "Users can view chunks from their matters"
ON public.chunks FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert chunks" ON public.chunks;
CREATE POLICY "Editors and Owners can insert chunks"
ON public.chunks FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update chunks" ON public.chunks;
CREATE POLICY "Editors and Owners can update chunks"
ON public.chunks FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete chunks" ON public.chunks;
CREATE POLICY "Only Owners can delete chunks"
ON public.chunks FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- bounding_boxes ----

DROP POLICY IF EXISTS "Users can view bounding boxes from their matters" ON public.bounding_boxes;
CREATE POLICY "Users can view bounding boxes from their matters"
ON public.bounding_boxes FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert bounding boxes" ON public.bounding_boxes;
CREATE POLICY "Editors and Owners can insert bounding boxes"
ON public.bounding_boxes FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update bounding boxes" ON public.bounding_boxes;
CREATE POLICY "Editors and Owners can update bounding boxes"
ON public.bounding_boxes FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete bounding boxes" ON public.bounding_boxes;
CREATE POLICY "Only Owners can delete bounding boxes"
ON public.bounding_boxes FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- findings ----

DROP POLICY IF EXISTS "Users can view findings from their matters" ON public.findings;
CREATE POLICY "Users can view findings from their matters"
ON public.findings FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert findings" ON public.findings;
CREATE POLICY "Editors and Owners can insert findings"
ON public.findings FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update findings" ON public.findings;
CREATE POLICY "Editors and Owners can update findings"
ON public.findings FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete findings" ON public.findings;
CREATE POLICY "Only Owners can delete findings"
ON public.findings FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- matter_memory ----

DROP POLICY IF EXISTS "Users can view matter memory from their matters" ON public.matter_memory;
CREATE POLICY "Users can view matter memory from their matters"
ON public.matter_memory FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert matter memory" ON public.matter_memory;
CREATE POLICY "Editors and Owners can insert matter memory"
ON public.matter_memory FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update matter memory" ON public.matter_memory;
CREATE POLICY "Editors and Owners can update matter memory"
ON public.matter_memory FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete matter memory" ON public.matter_memory;
CREATE POLICY "Only Owners can delete matter memory"
ON public.matter_memory FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- citations ----

DROP POLICY IF EXISTS "Users can view citations from their matters" ON public.citations;
CREATE POLICY "Users can view citations from their matters"
ON public.citations FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert citations" ON public.citations;
CREATE POLICY "Editors and Owners can insert citations"
ON public.citations FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
  AND source_document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id = matter_id
  )
  AND (
    target_act_document_id IS NULL
    OR target_act_document_id IN (
      SELECT d.id FROM public.documents d
      WHERE d.matter_id = matter_id
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update citations" ON public.citations;
CREATE POLICY "Editors and Owners can update citations"
ON public.citations FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
)
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
  AND source_document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id = matter_id
  )
  AND (
    target_act_document_id IS NULL
    OR target_act_document_id IN (
      SELECT d.id FROM public.documents d
      WHERE d.matter_id = matter_id
    )
  )
);

DROP POLICY IF EXISTS "Only Owners can delete citations" ON public.citations;
CREATE POLICY "Only Owners can delete citations"
ON public.citations FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- act_resolutions ----

DROP POLICY IF EXISTS "Users can view act resolutions from their matters" ON public.act_resolutions;
CREATE POLICY "Users can view act resolutions from their matters"
ON public.act_resolutions FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert act resolutions" ON public.act_resolutions;
CREATE POLICY "Editors and Owners can insert act resolutions"
ON public.act_resolutions FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update act resolutions" ON public.act_resolutions;
CREATE POLICY "Editors and Owners can update act resolutions"
ON public.act_resolutions FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete act resolutions" ON public.act_resolutions;
CREATE POLICY "Only Owners can delete act resolutions"
ON public.act_resolutions FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- events ----

DROP POLICY IF EXISTS "Users can view events from their matters" ON public.events;
CREATE POLICY "Users can view events from their matters"
ON public.events FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert events" ON public.events;
CREATE POLICY "Editors and Owners can insert events"
ON public.events FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update events" ON public.events;
CREATE POLICY "Editors and Owners can update events"
ON public.events FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete events" ON public.events;
CREATE POLICY "Only Owners can delete events"
ON public.events FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- identity_nodes ----

DROP POLICY IF EXISTS "Users can view identity nodes from their matters" ON public.identity_nodes;
CREATE POLICY "Users can view identity nodes from their matters"
ON public.identity_nodes FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert identity nodes" ON public.identity_nodes;
CREATE POLICY "Editors and Owners can insert identity nodes"
ON public.identity_nodes FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update identity nodes" ON public.identity_nodes;
CREATE POLICY "Editors and Owners can update identity nodes"
ON public.identity_nodes FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete identity nodes" ON public.identity_nodes;
CREATE POLICY "Only Owners can delete identity nodes"
ON public.identity_nodes FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- identity_edges ----

DROP POLICY IF EXISTS "Users can view identity edges from their matters" ON public.identity_edges;
CREATE POLICY "Users can view identity edges from their matters"
ON public.identity_edges FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert identity edges" ON public.identity_edges;
CREATE POLICY "Editors and Owners can insert identity edges"
ON public.identity_edges FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update identity edges" ON public.identity_edges;
CREATE POLICY "Editors and Owners can update identity edges"
ON public.identity_edges FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete identity edges" ON public.identity_edges;
CREATE POLICY "Only Owners can delete identity edges"
ON public.identity_edges FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- entity_mentions ----

DROP POLICY IF EXISTS "Users can view entity mentions from their matters" ON public.entity_mentions;
CREATE POLICY "Users can view entity mentions from their matters"
ON public.entity_mentions FOR SELECT
USING (
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert entity mentions" ON public.entity_mentions;
CREATE POLICY "Editors and Owners can insert entity mentions"
ON public.entity_mentions FOR INSERT
WITH CHECK (
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
  AND document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id = (
      SELECT in_node.matter_id FROM public.identity_nodes in_node
      WHERE in_node.id = entity_id
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update entity mentions" ON public.entity_mentions;
CREATE POLICY "Editors and Owners can update entity mentions"
ON public.entity_mentions FOR UPDATE
USING (
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
);

DROP POLICY IF EXISTS "Only Owners can delete entity mentions" ON public.entity_mentions;
CREATE POLICY "Only Owners can delete entity mentions"
ON public.entity_mentions FOR DELETE
USING (
  entity_id IN (
    SELECT id FROM public.identity_nodes
    WHERE matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role = 'owner'
    )
  )
);

-- ---- alias_corrections ----

DROP POLICY IF EXISTS "Matter members can view alias corrections" ON public.alias_corrections;
CREATE POLICY "Matter members can view alias corrections"
ON public.alias_corrections FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = alias_corrections.matter_id
    AND ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors can create alias corrections" ON public.alias_corrections;
CREATE POLICY "Editors can create alias corrections"
ON public.alias_corrections FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = alias_corrections.matter_id
    AND ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

-- ---- processing_jobs ----

DROP POLICY IF EXISTS "Users can view processing jobs from their matters" ON public.processing_jobs;
CREATE POLICY "Users can view processing jobs from their matters"
ON public.processing_jobs FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert processing jobs" ON public.processing_jobs;
CREATE POLICY "Editors and Owners can insert processing jobs"
ON public.processing_jobs FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update processing jobs" ON public.processing_jobs;
CREATE POLICY "Editors and Owners can update processing jobs"
ON public.processing_jobs FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete processing jobs" ON public.processing_jobs;
CREATE POLICY "Only Owners can delete processing jobs"
ON public.processing_jobs FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- statement_comparisons ----

DROP POLICY IF EXISTS "Users access own matter comparisons only" ON public.statement_comparisons;
CREATE POLICY "Users access own matter comparisons only"
ON public.statement_comparisons FOR ALL
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

-- ---- ocr_validation_log ----

DROP POLICY IF EXISTS "Users can view own matter validation logs" ON public.ocr_validation_log;
CREATE POLICY "Users can view own matter validation logs"
ON public.ocr_validation_log FOR SELECT
USING (
  document_id IN (
    SELECT id FROM public.documents
    WHERE matter_id IN (
      SELECT matter_id FROM public.matter_attorneys
      WHERE user_id = (select auth.uid())
    )
  )
);

-- ---- ocr_human_review ----

DROP POLICY IF EXISTS "Users can view own matter human reviews" ON public.ocr_human_review;
CREATE POLICY "Users can view own matter human reviews"
ON public.ocr_human_review FOR SELECT
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert human reviews" ON public.ocr_human_review;
CREATE POLICY "Editors and Owners can insert human reviews"
ON public.ocr_human_review FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
    AND role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update human reviews" ON public.ocr_human_review;
CREATE POLICY "Editors and Owners can update human reviews"
ON public.ocr_human_review FOR UPDATE
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
    AND role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete human reviews" ON public.ocr_human_review;
CREATE POLICY "Only Owners can delete human reviews"
ON public.ocr_human_review FOR DELETE
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
    AND role = 'owner'
  )
);

-- ---- toc_pages ----

DROP POLICY IF EXISTS "Users can view toc_pages via document access" ON public.toc_pages;
CREATE POLICY "Users can view toc_pages via document access"
ON public.toc_pages FOR SELECT
USING (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert toc_pages" ON public.toc_pages;
CREATE POLICY "Editors and Owners can insert toc_pages"
ON public.toc_pages FOR INSERT
WITH CHECK (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update toc_pages" ON public.toc_pages;
CREATE POLICY "Editors and Owners can update toc_pages"
ON public.toc_pages FOR UPDATE
USING (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
)
WITH CHECK (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can delete toc_pages" ON public.toc_pages;
CREATE POLICY "Editors and Owners can delete toc_pages"
ON public.toc_pages FOR DELETE
USING (
  document_id IN (
    SELECT d.id FROM public.documents d
    WHERE d.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
);
