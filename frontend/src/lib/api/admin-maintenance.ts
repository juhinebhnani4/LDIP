'use client';

/**
 * Admin Maintenance API Client
 *
 * API functions for admin-only maintenance operations.
 * Provides endpoints for:
 * - Triggering cleanup of soft-deleted matters
 * - Triggering cleanup of soft-deleted documents
 *
 * Note: These operations require admin permissions.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface CleanupResponse {
  success: boolean;
  taskId: string | null;
  message: string;
}

export interface CleanupRequest {
  retentionDays?: number;
}

// =============================================================================
// Maintenance Admin API
// =============================================================================

/**
 * Trigger hard deletion of soft-deleted matters.
 *
 * This permanently removes matters (and all related data via CASCADE delete):
 * - documents, chunks, bounding_boxes
 * - entities, entity_mentions, citations
 * - events, processing_jobs, act_resolutions
 * - Storage files in Supabase Storage
 *
 * @param options - Cleanup options
 * @returns Cleanup result with task ID
 */
export async function cleanupDeletedMatters(
  options?: CleanupRequest
): Promise<CleanupResponse> {
  const response = await api.post<{ success: boolean; task_id: string | null; message: string }>(
    '/api/admin/maintenance/cleanup-deleted-matters',
    { retention_days: options?.retentionDays ?? 0 }
  );

  return {
    success: response.success,
    taskId: response.task_id,
    message: response.message,
  };
}

/**
 * Trigger hard deletion of soft-deleted documents.
 *
 * This permanently removes documents and their storage files.
 *
 * @param options - Cleanup options
 * @returns Cleanup result with task ID
 */
export async function cleanupDeletedDocuments(
  options?: CleanupRequest
): Promise<CleanupResponse> {
  const response = await api.post<{ success: boolean; task_id: string | null; message: string }>(
    '/api/admin/maintenance/cleanup-deleted-documents',
    { retention_days: options?.retentionDays ?? 0 }
  );

  return {
    success: response.success,
    taskId: response.task_id,
    message: response.message,
  };
}

// =============================================================================
// Exported API Object
// =============================================================================

export const adminMaintenanceApi = {
  cleanupDeletedMatters,
  cleanupDeletedDocuments,
};
