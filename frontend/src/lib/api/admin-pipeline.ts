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
// Exported API Object
// =============================================================================

export const adminPipelineApi = {
  triggerTask,
  retryDocument,
  resetDocument,
  getStatus,
  reprocessStuckDocuments,
};
