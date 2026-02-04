-- Migration: Fix remaining auth_rls_initplan warnings
-- Purpose: Wrap auth.uid() in (select auth.uid()) for all remaining policies
-- that were missed in 20260204000002 (tables from later migrations)

-- ---- activities ----

DROP POLICY IF EXISTS "Users access own activities only" ON public.activities;
CREATE POLICY "Users access own activities only"
ON public.activities FOR SELECT
USING (user_id = (select auth.uid()));

DROP POLICY IF EXISTS "Users can insert own activities" ON public.activities;
CREATE POLICY "Users can insert own activities"
ON public.activities FOR INSERT
WITH CHECK (user_id = (select auth.uid()));

DROP POLICY IF EXISTS "Users can update own activities" ON public.activities;
CREATE POLICY "Users can update own activities"
ON public.activities FOR UPDATE
USING (user_id = (select auth.uid()));

DROP POLICY IF EXISTS "Users can delete own activities" ON public.activities;
CREATE POLICY "Users can delete own activities"
ON public.activities FOR DELETE
USING (user_id = (select auth.uid()));

-- ---- anomalies ----

DROP POLICY IF EXISTS "Users can view anomalies from their matters" ON public.anomalies;
CREATE POLICY "Users can view anomalies from their matters"
ON public.anomalies FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert anomalies" ON public.anomalies;
CREATE POLICY "Editors and Owners can insert anomalies"
ON public.anomalies FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update anomalies" ON public.anomalies;
CREATE POLICY "Editors and Owners can update anomalies"
ON public.anomalies FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete anomalies" ON public.anomalies;
CREATE POLICY "Only Owners can delete anomalies"
ON public.anomalies FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- document_ocr_chunks ----

DROP POLICY IF EXISTS "Users can view chunks from their matters" ON public.document_ocr_chunks;
CREATE POLICY "Users can view chunks from their matters"
ON public.document_ocr_chunks FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert chunks" ON public.document_ocr_chunks;
CREATE POLICY "Editors and Owners can insert chunks"
ON public.document_ocr_chunks FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update chunks" ON public.document_ocr_chunks;
CREATE POLICY "Editors and Owners can update chunks"
ON public.document_ocr_chunks FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete chunks" ON public.document_ocr_chunks;
CREATE POLICY "Only Owners can delete chunks"
ON public.document_ocr_chunks FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- document_tables ----

DROP POLICY IF EXISTS "Users access own matter tables" ON public.document_tables;
CREATE POLICY "Users access own matter tables"
ON public.document_tables FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
  )
);

-- ---- evaluation_results ----

DROP POLICY IF EXISTS "Users access own matter evaluation results" ON public.evaluation_results;
CREATE POLICY "Users access own matter evaluation results"
ON public.evaluation_results FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
  )
);

-- ---- exports ----

DROP POLICY IF EXISTS "Users can view matter exports" ON public.exports;
CREATE POLICY "Users can view matter exports"
ON public.exports FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys
    WHERE matter_attorneys.matter_id = exports.matter_id
    AND matter_attorneys.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can create exports" ON public.exports;
CREATE POLICY "Editors and Owners can create exports"
ON public.exports FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys
    WHERE matter_attorneys.matter_id = exports.matter_id
    AND matter_attorneys.user_id = (select auth.uid())
    AND matter_attorneys.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Owners can update exports" ON public.exports;
CREATE POLICY "Owners can update exports"
ON public.exports FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM public.matter_attorneys
    WHERE matter_attorneys.matter_id = exports.matter_id
    AND matter_attorneys.user_id = (select auth.uid())
    AND matter_attorneys.role = 'owner'
  )
);

-- ---- finding_verifications ----

DROP POLICY IF EXISTS "Users can view verifications from their matters" ON public.finding_verifications;
CREATE POLICY "Users can view verifications from their matters"
ON public.finding_verifications FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert verifications" ON public.finding_verifications;
CREATE POLICY "Editors and Owners can insert verifications"
ON public.finding_verifications FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update verifications" ON public.finding_verifications;
CREATE POLICY "Editors and Owners can update verifications"
ON public.finding_verifications FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete verifications" ON public.finding_verifications;
CREATE POLICY "Only Owners can delete verifications"
ON public.finding_verifications FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- golden_dataset ----

DROP POLICY IF EXISTS "Users access own matter golden dataset" ON public.golden_dataset;
CREATE POLICY "Users access own matter golden dataset"
ON public.golden_dataset FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
  )
);

-- ---- job_stage_history ----

DROP POLICY IF EXISTS "Users can view job stage history from their matters" ON public.job_stage_history;
CREATE POLICY "Users can view job stage history from their matters"
ON public.job_stage_history FOR SELECT
USING (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert job stage history" ON public.job_stage_history;
CREATE POLICY "Editors and Owners can insert job stage history"
ON public.job_stage_history FOR INSERT
WITH CHECK (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update job stage history" ON public.job_stage_history;
CREATE POLICY "Editors and Owners can update job stage history"
ON public.job_stage_history FOR UPDATE
USING (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role IN ('owner', 'editor')
    )
  )
);

DROP POLICY IF EXISTS "Only Owners can delete job stage history" ON public.job_stage_history;
CREATE POLICY "Only Owners can delete job stage history"
ON public.job_stage_history FOR DELETE
USING (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = (select auth.uid())
      AND ma.role = 'owner'
    )
  )
);

-- ---- library_documents ----

DROP POLICY IF EXISTS "Authenticated users can add library documents" ON public.library_documents;
CREATE POLICY "Authenticated users can add library documents"
ON public.library_documents FOR INSERT
TO authenticated
WITH CHECK (added_by = (select auth.uid()));

DROP POLICY IF EXISTS "Uploaders can update their library documents" ON public.library_documents;
CREATE POLICY "Uploaders can update their library documents"
ON public.library_documents FOR UPDATE
TO authenticated
USING (added_by = (select auth.uid()) AND status IN ('pending', 'failed'));

-- ---- llm_costs ----

DROP POLICY IF EXISTS "Users access own matter costs only" ON public.llm_costs;
CREATE POLICY "Users access own matter costs only"
ON public.llm_costs FOR ALL
USING (
  matter_id IS NULL OR
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

-- ---- matter_library_links ----

DROP POLICY IF EXISTS "Users can view links for their matters" ON public.matter_library_links;
CREATE POLICY "Users can view links for their matters"
ON public.matter_library_links FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can link library documents" ON public.matter_library_links;
CREATE POLICY "Editors and Owners can link library documents"
ON public.matter_library_links FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
  AND linked_by = (select auth.uid())
);

DROP POLICY IF EXISTS "Editors and Owners can unlink library documents" ON public.matter_library_links;
CREATE POLICY "Editors and Owners can unlink library documents"
ON public.matter_library_links FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

-- ---- matter_query_history ----

DROP POLICY IF EXISTS "Users can view their matter query history" ON public.matter_query_history;
CREATE POLICY "Users can view their matter query history"
ON public.matter_query_history FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Users can insert query history for their matters" ON public.matter_query_history;
CREATE POLICY "Users can insert query history for their matters"
ON public.matter_query_history FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

-- ---- notifications ----

DROP POLICY IF EXISTS "Users can view own notifications" ON public.notifications;
CREATE POLICY "Users can view own notifications"
ON public.notifications FOR SELECT
USING (user_id = (select auth.uid()));

DROP POLICY IF EXISTS "Users can update own notifications" ON public.notifications;
CREATE POLICY "Users can update own notifications"
ON public.notifications FOR UPDATE
USING (user_id = (select auth.uid()));

DROP POLICY IF EXISTS "Users can delete own notifications" ON public.notifications;
CREATE POLICY "Users can delete own notifications"
ON public.notifications FOR DELETE
USING (user_id = (select auth.uid()));

-- ---- ocr_validation_log (INSERT only) ----

DROP POLICY IF EXISTS "Service role can insert validation logs" ON public.ocr_validation_log;
CREATE POLICY "Service role can insert validation logs"
ON public.ocr_validation_log FOR INSERT
WITH CHECK (
  document_id IN (
    SELECT id FROM public.documents
    WHERE matter_id IN (
      SELECT matter_id FROM public.matter_attorneys
      WHERE user_id = (select auth.uid())
    )
  )
);

-- ---- reasoning_traces ----

DROP POLICY IF EXISTS "Users can view reasoning from their matters" ON public.reasoning_traces;
CREATE POLICY "Users can view reasoning from their matters"
ON public.reasoning_traces FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

-- ---- section_index ----

DROP POLICY IF EXISTS "Users can view section index from their matters" ON public.section_index;
CREATE POLICY "Users can view section index from their matters"
ON public.section_index FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

DROP POLICY IF EXISTS "Editors and Owners can insert section index" ON public.section_index;
CREATE POLICY "Editors and Owners can insert section index"
ON public.section_index FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Editors and Owners can update section index" ON public.section_index;
CREATE POLICY "Editors and Owners can update section index"
ON public.section_index FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role IN ('owner', 'editor')
  )
);

DROP POLICY IF EXISTS "Only Owners can delete section index" ON public.section_index;
CREATE POLICY "Only Owners can delete section index"
ON public.section_index FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
    AND ma.role = 'owner'
  )
);

-- ---- summary_edits ----

DROP POLICY IF EXISTS "Users access own matter edits" ON public.summary_edits;
CREATE POLICY "Users access own matter edits"
ON public.summary_edits FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_attorneys
    WHERE user_id = (select auth.uid())
  )
);

-- ---- summary_notes ----

DROP POLICY IF EXISTS "Users access own matter notes" ON public.summary_notes;
CREATE POLICY "Users access own matter notes"
ON public.summary_notes FOR ALL
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

-- ---- summary_verifications ----

DROP POLICY IF EXISTS "Users access own matter verifications" ON public.summary_verifications;
CREATE POLICY "Users access own matter verifications"
ON public.summary_verifications FOR ALL
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = (select auth.uid())
  )
);

-- ---- user_preferences ----

DROP POLICY IF EXISTS "Users can view own preferences" ON public.user_preferences;
CREATE POLICY "Users can view own preferences"
ON public.user_preferences FOR SELECT
USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert own preferences" ON public.user_preferences;
CREATE POLICY "Users can insert own preferences"
ON public.user_preferences FOR INSERT
WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update own preferences" ON public.user_preferences;
CREATE POLICY "Users can update own preferences"
ON public.user_preferences FOR UPDATE
USING ((select auth.uid()) = user_id)
WITH CHECK ((select auth.uid()) = user_id);
