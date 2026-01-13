/**
 * Job Types
 *
 * Types for background job tracking and processing status.
 * Story 2c-3: Background Job Status Tracking and Retry
 */

/** Job type enum matching backend */
export type JobType =
  | 'DOCUMENT_PROCESSING'
  | 'OCR'
  | 'VALIDATION'
  | 'CHUNKING'
  | 'EMBEDDING'
  | 'ENTITY_EXTRACTION'
  | 'ALIAS_RESOLUTION';

/** Job status enum matching backend */
export type JobStatus =
  | 'QUEUED'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'SKIPPED';

/** Stage status for individual processing stages */
export type StageStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'FAILED'
  | 'SKIPPED';

/** Human-readable stage names */
export const STAGE_LABELS: Record<string, string> = {
  ocr: 'OCR Processing',
  validation: 'OCR Validation',
  confidence: 'Confidence Scoring',
  chunking: 'Document Chunking',
  embedding: 'Vector Embedding',
  entity_extraction: 'Entity Extraction',
  alias_resolution: 'Alias Resolution',
};

/** Stage history record */
export interface JobStageHistory {
  id: string;
  job_id: string;
  stage_name: string;
  status: StageStatus;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

/** Processing job record */
export interface ProcessingJob {
  id: string;
  matter_id: string;
  document_id: string | null;
  job_type: JobType;
  status: JobStatus;
  celery_task_id: string | null;

  // Progress tracking
  current_stage: string | null;
  total_stages: number;
  completed_stages: number;
  progress_pct: number;
  estimated_completion: string | null;

  // Error handling
  error_message: string | null;
  error_code: string | null;
  retry_count: number;
  max_retries: number;

  // Metadata for partial progress
  metadata: Record<string, unknown>;

  // Timestamps
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Job with stage history */
export interface ProcessingJobWithHistory extends ProcessingJob {
  stage_history: JobStageHistory[];
}

/** Queue statistics for a matter */
export interface JobQueueStats {
  matter_id: string;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
  cancelled: number;
  skipped: number;
  avg_processing_time_ms: number | null;
}

// =============================================================================
// API Request/Response Types
// =============================================================================

/** Response for list of jobs */
export interface JobListResponse {
  jobs: ProcessingJob[];
  total: number;
  limit: number;
  offset: number;
}

/** Response for single job with history */
export interface JobDetailResponse {
  job: ProcessingJob;
  stages: JobStageHistory[];
}

/** Request for job retry */
export interface JobRetryRequest {
  reset_retry_count?: boolean;
}

/** Response for job retry */
export interface JobRetryResponse {
  success: boolean;
  message: string;
  job_id: string;
  new_status: string;
}

/** Response for job skip */
export interface JobSkipResponse {
  success: boolean;
  message: string;
  job_id: string;
  new_status: string;
}

/** Response for job cancel */
export interface JobCancelResponse {
  success: boolean;
  message: string;
  job_id: string;
  new_status: string;
}

// =============================================================================
// Real-time Event Types (for WebSocket/PubSub)
// =============================================================================

/** Job progress event */
export interface JobProgressEvent {
  event: 'job_progress';
  job_id: string;
  matter_id: string;
  stage: string;
  progress_pct: number;
  estimated_completion?: string;
}

/** Job status change event */
export interface JobStatusChangeEvent {
  event: 'job_status_change';
  job_id: string;
  matter_id: string;
  old_status: JobStatus;
  new_status: JobStatus;
}

/** Processing summary event */
export interface ProcessingSummaryEvent {
  event: 'processing_summary';
  matter_id: string;
  stats: {
    queued: number;
    processing: number;
    completed: number;
    failed: number;
  };
}

/** Union type for all job events */
export type JobEvent =
  | JobProgressEvent
  | JobStatusChangeEvent
  | ProcessingSummaryEvent;

// =============================================================================
// UI State Types
// =============================================================================

/** Processing status for a document (simplified for UI) */
export interface DocumentProcessingStatus {
  documentId: string;
  status: JobStatus;
  currentStage: string | null;
  progressPct: number;
  estimatedCompletion: string | null;
  errorMessage: string | null;
  retryCount: number;
  canRetry: boolean;
  canSkip: boolean;
  canCancel: boolean;
}

/** Helper to determine if a job can be retried */
export function canRetryJob(job: ProcessingJob): boolean {
  return job.status === 'FAILED' && job.retry_count < job.max_retries;
}

/** Helper to determine if a job can be skipped */
export function canSkipJob(job: ProcessingJob): boolean {
  return job.status === 'FAILED';
}

/** Helper to determine if a job can be cancelled */
export function canCancelJob(job: ProcessingJob): boolean {
  return job.status === 'QUEUED' || job.status === 'PROCESSING';
}

/** Helper to check if a job is active (in progress) */
export function isJobActive(job: ProcessingJob): boolean {
  return job.status === 'QUEUED' || job.status === 'PROCESSING';
}

/** Helper to check if a job is terminal (completed, failed, etc.) */
export function isJobTerminal(job: ProcessingJob): boolean {
  return ['COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED'].includes(job.status);
}

/** Helper to get human-readable status */
export function getJobStatusLabel(status: JobStatus): string {
  const labels: Record<JobStatus, string> = {
    QUEUED: 'Queued',
    PROCESSING: 'Processing',
    COMPLETED: 'Completed',
    FAILED: 'Failed',
    CANCELLED: 'Cancelled',
    SKIPPED: 'Skipped',
  };
  return labels[status] || status;
}

/** Helper to get status color for UI */
export function getJobStatusColor(status: JobStatus): string {
  const colors: Record<JobStatus, string> = {
    QUEUED: 'text-muted-foreground',
    PROCESSING: 'text-blue-600',
    COMPLETED: 'text-green-600',
    FAILED: 'text-destructive',
    CANCELLED: 'text-yellow-600',
    SKIPPED: 'text-muted-foreground',
  };
  return colors[status] || 'text-muted-foreground';
}
