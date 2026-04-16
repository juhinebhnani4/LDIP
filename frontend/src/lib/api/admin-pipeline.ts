'use client';

/**
 * Admin Pipeline API Client
 *
 * API functions for admin-only pipeline management operations.
 * Provides endpoints for:
 * - Triggering specific pipeline tasks manually
 * - Retrying failed documents
 * - Resetting stuck documents
 * - Getting pipeline status
 *
 * Note: These operations require admin permissions.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export type PipelineTaskName =
  | 'process_document'
  | 'validate_ocr'
  | 'calculate_confidence'
  | 'chunk_document'
  | 'embed_chunks'
  | 'extract_entities'
  | 'resolve_aliases'
  | 'extract_citations'
  | 'link_bboxes'
  | 'extract_dates'
  | 'classify_events'
  | 'link_entities'
  | 'process_chunked_document'
  | 'finalize_chunked_document';

export interface PipelineStatus {
  documentId: string;
  currentStage: string;
  status: string;
  progressPct: number;
  lastUpdated: string;
  retryCount: number;
  errorMessage: string | null;
}

export interface TriggerTaskResponse {
  success: boolean;
  taskId: string;
  message: string;
}

export interface RetryDocumentResponse {
  success: boolean;
  documentId: string;
  message: string;
}

export interface ResetDocumentResponse {
  success: boolean;
  documentId: string;
  previousStatus: string;
  newStatus: string;
  message: string;
}

export interface ReprocessStuckResponse {
  success: boolean;
  processedCount: number;
  errors: Array<{ documentId: string; error: string }>;
  message: string;
}

// =============================================================================
// Response Transformers
// =============================================================================

function transformPipelineStatus(data: Record<string, unknown>): PipelineStatus {
  return {
    documentId: (data.document_id ?? data.documentId) as string,
    currentStage: (data.current_stage ?? data.currentStage) as string,
    status: data.status as string,
    progressPct: (data.progress_pct ?? data.progressPct ?? 0) as number,
    lastUpdated: (data.last_updated ?? data.lastUpdated ?? data.updated_at ?? data.updatedAt) as string,
    retryCount: (data.retry_count ?? data.retryCount ?? 0) as number,
    errorMessage: (data.error_message ?? data.errorMessage ?? null) as string | null,
  };
}

// =============================================================================
// Pipeline Admin API
// =============================================================================

/**
 * Trigger a specific pipeline task for a document.
 *
 * @param documentId - Document UUID
 * @param taskName - Name of the pipeline task to trigger
 * @param options - Optional force flag to bypass checks
 * @returns Task trigger result
 */
export async function triggerTask(
  documentId: string,
  taskName: PipelineTaskName,
  options?: { force?: boolean }
): Promise<TriggerTaskResponse> {
  const response = await api.post<{ data: Record<string, unknown> }>(
    `/api/admin/pipeline/documents/${documentId}/trigger/${taskName}`,
    { force: options?.force ?? false }
  );

  return {
    success: response.data.success as boolean,
    taskId: (response.data.task_id ?? response.data.taskId) as string,
    message: response.data.message as string,
  };
}

/**
 * Retry a failed document's processing.
 *
 * @param documentId - Document UUID
 * @param options - Retry options
 * @returns Retry result
 */
export async function retryDocument(
  documentId: string,
  options?: {
    resetRetryCount?: boolean;
    fromStage?: string;
  }
): Promise<RetryDocumentResponse> {
  const response = await api.post<{ data: Record<string, unknown> }>(
    `/api/admin/pipeline/documents/${documentId}/retry`,
    {
      reset_retry_count: options?.resetRetryCount ?? true,
      from_stage: options?.fromStage,
    }
  );

  return {
    success: response.data.success as boolean,
    documentId: (response.data.document_id ?? response.data.documentId) as string,
    message: response.data.message as string,
  };
}

/**
 * Reset a stuck document's status.
 *
 * @param documentId - Document UUID
 * @param options - Reset options
 * @returns Reset result
 */
export async function resetDocument(
  documentId: string,
  options?: {
    targetStatus?: 'pending' | 'queued';
  }
): Promise<ResetDocumentResponse> {
  const response = await api.post<{ data: Record<string, unknown> }>(
    `/api/admin/pipeline/documents/${documentId}/reset`,
    { target_status: options?.targetStatus ?? 'queued' }
  );

  return {
    success: response.data.success as boolean,
    documentId: (response.data.document_id ?? response.data.documentId) as string,
    previousStatus: (response.data.previous_status ?? response.data.previousStatus) as string,
    newStatus: (response.data.new_status ?? response.data.newStatus) as string,
    message: response.data.message as string,
  };
}

/**
 * Get pipeline status for a document.
 *
 * @param documentId - Document UUID
 * @returns Pipeline status details
 */
export async function getStatus(documentId: string): Promise<PipelineStatus> {
  const response = await api.get<{ data: Record<string, unknown> }>(
    `/api/admin/pipeline/documents/${documentId}/status`
  );

  return transformPipelineStatus(response.data);
}

/**
 * Reprocess all stuck documents in the system.
 *
 * @param options - Reprocess options
 * @returns Reprocess results
 */
export async function reprocessStuckDocuments(
  options?: {
    thresholdMinutes?: number;
    matterId?: string;
    limit?: number;
  }
): Promise<ReprocessStuckResponse> {
  const body: Record<string, unknown> = {};
  if (options?.thresholdMinutes) body.threshold_minutes = options.thresholdMinutes;
  if (options?.matterId) body.matter_id = options.matterId;
  if (options?.limit) body.limit = options.limit;

  const response = await api.post<{ data: Record<string, unknown> }>(
    '/api/admin/pipeline/documents/reprocess-stuck',
    body
  );

  return {
    success: response.data.success as boolean,
    processedCount: (response.data.processed_count ?? response.data.processedCount ?? 0) as number,
    errors: ((response.data.errors ?? []) as Array<Record<string, unknown>>).map((e) => ({
      documentId: (e.document_id ?? e.documentId) as string,
      error: e.error as string,
    })),
    message: response.data.message as string,
  };
}

// =============================================================================
// Worker Diagnostics Types
// =============================================================================

export interface ActiveTaskDetail {
  taskName: string;
  taskId: string;
  workerName: string;
  runtimeSeconds: number;
}

export interface WorkerInfo {
  workerCount: number;
  activeTasks: ActiveTaskDetail[];
}

export interface JobOverviewItem {
  jobId: string;
  matterId: string;
  documentId: string | null;
  jobType: string;
  status: string;
  currentStage: string | null;
  progressPct: number;
  retryCount: number;
  errorMessage: string | null;
  queueWaitSeconds: number | null;
  createdAt: string;
  startedAt: string | null;
  updatedAt: string;
}

export interface JobsOverview {
  jobs: JobOverviewItem[];
  totalCount: number;
  queuedCount: number;
  processingCount: number;
}

export interface BottleneckStage {
  stageName: string;
  avgDurationSeconds: number;
  maxDurationSeconds: number;
  totalRuns: number;
  failedRuns: number;
}

export interface BottleneckStats {
  stages: BottleneckStage[];
}

export interface ErrorPatternItem {
  errorMessage: string;
  count: number;
  stageName: string;
  lastOccurred: string;
}

export interface ErrorPatterns {
  patterns: ErrorPatternItem[];
  totalErrors: number;
}

// =============================================================================
// Worker Diagnostics API
// =============================================================================

export async function getWorkerInfo(): Promise<WorkerInfo> {
  const response = await api.get<Record<string, unknown>>(
    '/api/admin/pipeline/worker-info'
  );

  const data = response as Record<string, unknown>;
  const tasks = ((data.active_tasks ?? data.activeTasks ?? []) as Record<string, unknown>[]).map(
    (t) => ({
      taskName: (t.task_name ?? t.taskName) as string,
      taskId: (t.task_id ?? t.taskId) as string,
      workerName: (t.worker_name ?? t.workerName) as string,
      runtimeSeconds: (t.runtime_seconds ?? t.runtimeSeconds ?? 0) as number,
    })
  );

  return {
    workerCount: (data.worker_count ?? data.workerCount ?? 0) as number,
    activeTasks: tasks,
  };
}

export async function getJobsOverview(
  options?: { statusFilter?: string; limit?: number }
): Promise<JobsOverview> {
  const params = new URLSearchParams();
  if (options?.statusFilter) params.set('status_filter', options.statusFilter);
  if (options?.limit) params.set('limit', String(options.limit));

  const qs = params.toString();
  const url = `/api/admin/pipeline/jobs-overview${qs ? `?${qs}` : ''}`;
  const response = await api.get<Record<string, unknown>>(url);

  const data = response as Record<string, unknown>;
  const jobs = ((data.jobs ?? []) as Record<string, unknown>[]).map((j) => ({
    jobId: (j.job_id ?? j.jobId) as string,
    matterId: (j.matter_id ?? j.matterId) as string,
    documentId: (j.document_id ?? j.documentId ?? null) as string | null,
    jobType: (j.job_type ?? j.jobType) as string,
    status: j.status as string,
    currentStage: (j.current_stage ?? j.currentStage ?? null) as string | null,
    progressPct: (j.progress_pct ?? j.progressPct ?? 0) as number,
    retryCount: (j.retry_count ?? j.retryCount ?? 0) as number,
    errorMessage: (j.error_message ?? j.errorMessage ?? null) as string | null,
    queueWaitSeconds: (j.queue_wait_seconds ?? j.queueWaitSeconds ?? null) as number | null,
    createdAt: (j.created_at ?? j.createdAt) as string,
    startedAt: (j.started_at ?? j.startedAt ?? null) as string | null,
    updatedAt: (j.updated_at ?? j.updatedAt) as string,
  }));

  return {
    jobs,
    totalCount: (data.total_count ?? data.totalCount ?? 0) as number,
    queuedCount: (data.queued_count ?? data.queuedCount ?? 0) as number,
    processingCount: (data.processing_count ?? data.processingCount ?? 0) as number,
  };
}

export async function getBottleneckStats(
  options?: { hours?: number }
): Promise<BottleneckStats> {
  const params = new URLSearchParams();
  if (options?.hours) params.set('hours', String(options.hours));

  const qs = params.toString();
  const url = `/api/admin/pipeline/bottleneck-stats${qs ? `?${qs}` : ''}`;
  const response = await api.get<Record<string, unknown>>(url);

  const data = response as Record<string, unknown>;
  const stages = ((data.stages ?? []) as Record<string, unknown>[]).map((s) => ({
    stageName: (s.stage_name ?? s.stageName) as string,
    avgDurationSeconds: (s.avg_duration_seconds ?? s.avgDurationSeconds ?? 0) as number,
    maxDurationSeconds: (s.max_duration_seconds ?? s.maxDurationSeconds ?? 0) as number,
    totalRuns: (s.total_runs ?? s.totalRuns ?? 0) as number,
    failedRuns: (s.failed_runs ?? s.failedRuns ?? 0) as number,
  }));

  return { stages };
}

export async function getErrorPatterns(
  options?: { hours?: number; limit?: number }
): Promise<ErrorPatterns> {
  const params = new URLSearchParams();
  if (options?.hours) params.set('hours', String(options.hours));
  if (options?.limit) params.set('limit', String(options.limit));

  const qs = params.toString();
  const url = `/api/admin/pipeline/error-patterns${qs ? `?${qs}` : ''}`;
  const response = await api.get<Record<string, unknown>>(url);

  const data = response as Record<string, unknown>;
  const patterns = ((data.patterns ?? []) as Record<string, unknown>[]).map((p) => ({
    errorMessage: (p.error_message ?? p.errorMessage) as string,
    count: (p.count ?? 0) as number,
    stageName: (p.stage_name ?? p.stageName) as string,
    lastOccurred: (p.last_occurred ?? p.lastOccurred) as string,
  }));

  return {
    patterns,
    totalErrors: (data.total_errors ?? data.totalErrors ?? 0) as number,
  };
}

// =============================================================================
// Exported API Object
// =============================================================================

export const adminPipelineApi = {
  triggerTask,
  retryDocument,
  resetDocument,
  getStatus,
  reprocessStuckDocuments,
  getWorkerInfo,
  getJobsOverview,
  getBottleneckStats,
  getErrorPatterns,
};
