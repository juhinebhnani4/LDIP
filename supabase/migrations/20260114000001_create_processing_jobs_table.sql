-- Create processing_jobs and job_stage_history tables for background job tracking
-- Story 2c-3: Implement Background Job Status Tracking and Retry
-- This implements Layer 1 of 4-layer matter isolation

-- =============================================================================
-- TABLE: processing_jobs - Track document processing jobs
-- =============================================================================

CREATE TABLE public.processing_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid REFERENCES public.documents(id) ON DELETE CASCADE,

  -- Job identification
  job_type text NOT NULL CHECK (job_type IN (
    'DOCUMENT_PROCESSING', 'OCR', 'VALIDATION', 'CHUNKING',
    'EMBEDDING', 'ENTITY_EXTRACTION', 'ALIAS_RESOLUTION'
  )),
  status text NOT NULL DEFAULT 'QUEUED' CHECK (status IN (
    'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED'
  )),
  celery_task_id text,

  -- Progress tracking
  current_stage text,
  total_stages int DEFAULT 7,
  completed_stages int DEFAULT 0,
  progress_pct int DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100),
  estimated_completion timestamptz,

  -- Error handling
  error_message text,
  error_code text,
  retry_count int DEFAULT 0,
  max_retries int DEFAULT 3,

  -- Metadata for partial progress preservation
  metadata jsonb DEFAULT '{}',

  -- Timestamps
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- =============================================================================
-- TABLE: job_stage_history - Track granular stage progress
-- =============================================================================

CREATE TABLE public.job_stage_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.processing_jobs(id) ON DELETE CASCADE,

  -- Stage information
  stage_name text NOT NULL,
  status text NOT NULL DEFAULT 'PENDING' CHECK (status IN (
    'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'SKIPPED'
  )),

  -- Timestamps
  started_at timestamptz,
  completed_at timestamptz,

  -- Error details
  error_message text,

  -- Additional metadata
  metadata jsonb DEFAULT '{}',

  created_at timestamptz DEFAULT now()
);

-- =============================================================================
-- INDEXES: processing_jobs
-- =============================================================================

-- Primary query patterns: matter jobs, document jobs, celery correlation
CREATE INDEX idx_processing_jobs_matter_status ON public.processing_jobs(matter_id, status);
CREATE INDEX idx_processing_jobs_document_status ON public.processing_jobs(document_id, status);
CREATE INDEX idx_processing_jobs_celery ON public.processing_jobs(celery_task_id);

-- Dashboard queries
CREATE INDEX idx_processing_jobs_matter_created ON public.processing_jobs(matter_id, created_at DESC);

-- Job type filtering
CREATE INDEX idx_processing_jobs_job_type ON public.processing_jobs(job_type);

-- Status-based queries
CREATE INDEX idx_processing_jobs_status ON public.processing_jobs(status);

-- =============================================================================
-- INDEXES: job_stage_history
-- =============================================================================

-- Primary lookup by job
CREATE INDEX idx_job_stage_history_job ON public.job_stage_history(job_id);

-- Stage name lookup
CREATE INDEX idx_job_stage_history_job_stage ON public.job_stage_history(job_id, stage_name);

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE public.processing_jobs IS 'Background document processing jobs with status tracking';
COMMENT ON COLUMN public.processing_jobs.matter_id IS 'FK to matters - CRITICAL for 4-layer isolation';
COMMENT ON COLUMN public.processing_jobs.document_id IS 'FK to documents - nullable for matter-level jobs';
COMMENT ON COLUMN public.processing_jobs.job_type IS 'Type: DOCUMENT_PROCESSING, OCR, VALIDATION, CHUNKING, EMBEDDING, ENTITY_EXTRACTION, ALIAS_RESOLUTION';
COMMENT ON COLUMN public.processing_jobs.status IS 'Status: QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED, SKIPPED';
COMMENT ON COLUMN public.processing_jobs.celery_task_id IS 'Celery task ID for correlation';
COMMENT ON COLUMN public.processing_jobs.current_stage IS 'Current processing stage name';
COMMENT ON COLUMN public.processing_jobs.total_stages IS 'Total number of stages in pipeline';
COMMENT ON COLUMN public.processing_jobs.completed_stages IS 'Number of completed stages';
COMMENT ON COLUMN public.processing_jobs.progress_pct IS 'Overall progress percentage (0-100)';
COMMENT ON COLUMN public.processing_jobs.estimated_completion IS 'Estimated completion timestamp';
COMMENT ON COLUMN public.processing_jobs.error_message IS 'Error message if failed';
COMMENT ON COLUMN public.processing_jobs.error_code IS 'Machine-readable error code';
COMMENT ON COLUMN public.processing_jobs.retry_count IS 'Number of retry attempts';
COMMENT ON COLUMN public.processing_jobs.max_retries IS 'Maximum retry attempts (default 3)';
COMMENT ON COLUMN public.processing_jobs.metadata IS 'JSONB for partial progress: completed_pages, chunks_created, etc.';
COMMENT ON COLUMN public.processing_jobs.started_at IS 'When processing started';
COMMENT ON COLUMN public.processing_jobs.completed_at IS 'When processing completed (success or failure)';

COMMENT ON TABLE public.job_stage_history IS 'Granular stage-level history for job tracking';
COMMENT ON COLUMN public.job_stage_history.job_id IS 'FK to processing_jobs';
COMMENT ON COLUMN public.job_stage_history.stage_name IS 'Stage: ocr, validation, chunking, embedding, entity_extraction, alias_resolution';
COMMENT ON COLUMN public.job_stage_history.status IS 'Stage status: PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED';
COMMENT ON COLUMN public.job_stage_history.error_message IS 'Error message if stage failed';
COMMENT ON COLUMN public.job_stage_history.metadata IS 'Stage-specific metadata';

-- =============================================================================
-- RLS POLICIES: processing_jobs
-- =============================================================================

ALTER TABLE public.processing_jobs ENABLE ROW LEVEL SECURITY;

-- Policy 1: Users can SELECT jobs from matters they have access to
CREATE POLICY "Users can view processing jobs from their matters"
ON public.processing_jobs FOR SELECT
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
  )
);

-- Policy 2: Editors and Owners can INSERT jobs (system usually inserts via service role)
CREATE POLICY "Editors and Owners can insert processing jobs"
ON public.processing_jobs FOR INSERT
WITH CHECK (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 3: Editors and Owners can UPDATE jobs (status changes, retry)
CREATE POLICY "Editors and Owners can update processing jobs"
ON public.processing_jobs FOR UPDATE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role IN ('owner', 'editor')
  )
);

-- Policy 4: Only Owners can DELETE jobs
CREATE POLICY "Only Owners can delete processing jobs"
ON public.processing_jobs FOR DELETE
USING (
  matter_id IN (
    SELECT ma.matter_id FROM public.matter_attorneys ma
    WHERE ma.user_id = auth.uid()
    AND ma.role = 'owner'
  )
);

-- =============================================================================
-- RLS POLICIES: job_stage_history
-- =============================================================================

ALTER TABLE public.job_stage_history ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view stage history for jobs they can view
-- Using a subquery to join through processing_jobs to matter_attorneys
CREATE POLICY "Users can view job stage history from their matters"
ON public.job_stage_history FOR SELECT
USING (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
    )
  )
);

-- Policy: Editors and Owners can INSERT stage history
CREATE POLICY "Editors and Owners can insert job stage history"
ON public.job_stage_history FOR INSERT
WITH CHECK (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
);

-- Policy: Editors and Owners can UPDATE stage history
CREATE POLICY "Editors and Owners can update job stage history"
ON public.job_stage_history FOR UPDATE
USING (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role IN ('owner', 'editor')
    )
  )
);

-- Policy: Only Owners can DELETE stage history
CREATE POLICY "Only Owners can delete job stage history"
ON public.job_stage_history FOR DELETE
USING (
  job_id IN (
    SELECT pj.id FROM public.processing_jobs pj
    WHERE pj.matter_id IN (
      SELECT ma.matter_id FROM public.matter_attorneys ma
      WHERE ma.user_id = auth.uid()
      AND ma.role = 'owner'
    )
  )
);

-- =============================================================================
-- TRIGGERS: Auto-update updated_at
-- =============================================================================

CREATE TRIGGER set_processing_jobs_updated_at
  BEFORE UPDATE ON public.processing_jobs
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to get job queue stats for a matter
CREATE OR REPLACE FUNCTION public.get_job_queue_stats(p_matter_id uuid)
RETURNS TABLE (
  queued bigint,
  processing bigint,
  completed bigint,
  failed bigint,
  cancelled bigint,
  skipped bigint,
  avg_processing_time_ms bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Verify user has access to matter
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = p_matter_id
    AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied: user cannot view jobs for matter %', p_matter_id;
  END IF;

  RETURN QUERY
  SELECT
    COUNT(*) FILTER (WHERE pj.status = 'QUEUED') AS queued,
    COUNT(*) FILTER (WHERE pj.status = 'PROCESSING') AS processing,
    COUNT(*) FILTER (WHERE pj.status = 'COMPLETED') AS completed,
    COUNT(*) FILTER (WHERE pj.status = 'FAILED') AS failed,
    COUNT(*) FILTER (WHERE pj.status = 'CANCELLED') AS cancelled,
    COUNT(*) FILTER (WHERE pj.status = 'SKIPPED') AS skipped,
    COALESCE(
      AVG(
        EXTRACT(EPOCH FROM (pj.completed_at - pj.started_at)) * 1000
      ) FILTER (WHERE pj.status = 'COMPLETED' AND pj.started_at IS NOT NULL AND pj.completed_at IS NOT NULL),
      0
    )::bigint AS avg_processing_time_ms
  FROM public.processing_jobs pj
  WHERE pj.matter_id = p_matter_id;
END;
$$;

COMMENT ON FUNCTION public.get_job_queue_stats IS 'Get job queue statistics for a matter';
