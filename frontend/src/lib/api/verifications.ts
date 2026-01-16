/**
 * Verification API Client for Attorney Finding Verification Workflow
 *
 * Provides typed API functions for verification operations.
 *
 * Story 8-5: Implement Verification Queue UI
 * Story 12-3: Export Verification Check
 * Epic 8: Safety Layer (Guardrails, Policing, Verification)
 */

import { api } from './client';
import type {
  ApproveVerificationRequest,
  BulkVerificationRequest,
  ExportEligibility,
  FindingBulkVerificationResponse,
  FindingVerification,
  FindingVerificationListResponse,
  FindingVerificationResponse,
  FlagVerificationRequest,
  RejectVerificationRequest,
  VerificationDecision,
  VerificationQueueItem,
  VerificationQueueResponse,
  VerificationStats,
  VerificationStatsResponse,
} from '@/types';

// =============================================================================
// Story 8-5: Statistics API (Task 6.4)
// =============================================================================

/**
 * Get verification statistics for a matter.
 *
 * Returns aggregate counts by decision status and verification tier,
 * plus export eligibility status.
 *
 * @param matterId - Matter UUID.
 * @returns Verification statistics.
 *
 * @example
 * ```ts
 * const stats = await getVerificationStats('matter-123');
 * console.log(`${stats.approvedCount} approved, ${stats.pendingCount} pending`);
 * ```
 */
export async function getVerificationStats(matterId: string): Promise<VerificationStats> {
  const response = await api.get<VerificationStatsResponse>(
    `/api/matters/${matterId}/verifications/stats`
  );
  return response.data;
}

// =============================================================================
// Story 8-5: Queue API (Task 6.3)
// =============================================================================

/**
 * Get pending verification queue for UI.
 *
 * Returns pending verifications sorted by:
 * 1. Requirement tier (REQUIRED first, then SUGGESTED, then OPTIONAL)
 * 2. Creation date (oldest first)
 *
 * @param matterId - Matter UUID.
 * @param limit - Max items to return (default 50, max 100).
 * @returns Pending verification queue items.
 *
 * @example
 * ```ts
 * const queue = await getPendingQueue('matter-123', 20);
 * console.log(`${queue.length} verifications pending`);
 * ```
 */
export async function getPendingQueue(
  matterId: string,
  limit: number = 50
): Promise<VerificationQueueItem[]> {
  const response = await api.get<VerificationQueueResponse>(
    `/api/matters/${matterId}/verifications/pending?limit=${limit}`
  );
  return response.data;
}

// =============================================================================
// Story 8-5: List Verifications (Task 6.2)
// =============================================================================

/**
 * List verification records for a matter with optional filtering.
 *
 * @param matterId - Matter UUID.
 * @param options - Optional filtering options.
 * @returns List of verification records.
 *
 * @example
 * ```ts
 * // Get all verifications
 * const all = await getVerifications('matter-123');
 *
 * // Get only approved
 * const approved = await getVerifications('matter-123', { decision: 'approved' });
 * ```
 */
export async function getVerifications(
  matterId: string,
  options?: {
    decision?: VerificationDecision;
    limit?: number;
    offset?: number;
  }
): Promise<FindingVerification[]> {
  const params = new URLSearchParams();
  if (options?.decision) {
    params.append('decision', options.decision);
  }
  if (options?.limit !== undefined) {
    params.append('limit', String(options.limit));
  }
  if (options?.offset !== undefined) {
    params.append('offset', String(options.offset));
  }

  const queryString = params.toString();
  const url = `/api/matters/${matterId}/verifications${queryString ? `?${queryString}` : ''}`;

  const response = await api.get<FindingVerificationListResponse>(url);
  return response.data;
}

// =============================================================================
// Story 8-5: Approve Verification (Task 6.5)
// =============================================================================

/**
 * Approve a finding verification.
 *
 * @param matterId - Matter UUID.
 * @param verificationId - Verification UUID.
 * @param options - Optional approval options (notes, adjusted confidence).
 * @returns Updated verification record.
 *
 * @example
 * ```ts
 * const verification = await approveVerification('matter-123', 'ver-456');
 * console.log(`Approved at ${verification.verifiedAt}`);
 * ```
 */
export async function approveVerification(
  matterId: string,
  verificationId: string,
  options?: ApproveVerificationRequest
): Promise<FindingVerification> {
  const response = await api.post<FindingVerificationResponse>(
    `/api/matters/${matterId}/verifications/${verificationId}/approve`,
    options ?? {}
  );
  return response.data;
}

// =============================================================================
// Story 8-5: Reject Verification (Task 6.6)
// =============================================================================

/**
 * Reject a finding verification.
 *
 * Notes are required for rejections to provide audit trail.
 *
 * @param matterId - Matter UUID.
 * @param verificationId - Verification UUID.
 * @param notes - Required rejection notes explaining decision.
 * @returns Updated verification record.
 *
 * @example
 * ```ts
 * const verification = await rejectVerification(
 *   'matter-123',
 *   'ver-456',
 *   'Finding is incorrect - source document misread'
 * );
 * ```
 */
export async function rejectVerification(
  matterId: string,
  verificationId: string,
  notes: string
): Promise<FindingVerification> {
  const request: RejectVerificationRequest = { notes };
  const response = await api.post<FindingVerificationResponse>(
    `/api/matters/${matterId}/verifications/${verificationId}/reject`,
    request
  );
  return response.data;
}

// =============================================================================
// Story 8-5: Flag Verification (Task 6.7)
// =============================================================================

/**
 * Flag a finding verification for further review.
 *
 * Used when attorney needs additional review or consultation
 * before making approve/reject decision.
 *
 * @param matterId - Matter UUID.
 * @param verificationId - Verification UUID.
 * @param notes - Required notes explaining why flagged.
 * @returns Updated verification record.
 *
 * @example
 * ```ts
 * const verification = await flagVerification(
 *   'matter-123',
 *   'ver-456',
 *   'Need senior attorney review - complex legal point'
 * );
 * ```
 */
export async function flagVerification(
  matterId: string,
  verificationId: string,
  notes: string
): Promise<FindingVerification> {
  const request: FlagVerificationRequest = { notes };
  const response = await api.post<FindingVerificationResponse>(
    `/api/matters/${matterId}/verifications/${verificationId}/flag`,
    request
  );
  return response.data;
}

// =============================================================================
// Story 8-5: Bulk Verification (Task 6.8)
// =============================================================================

/**
 * Bulk update verification decisions.
 *
 * Limited to 100 verifications per request.
 *
 * @param matterId - Matter UUID.
 * @param verificationIds - Array of verification UUIDs (max 100).
 * @param decision - Decision to apply to all verifications.
 * @param notes - Optional notes for all verifications.
 * @returns Bulk operation results.
 *
 * @example
 * ```ts
 * const result = await bulkUpdateVerifications(
 *   'matter-123',
 *   ['ver-1', 'ver-2', 'ver-3'],
 *   VerificationDecision.APPROVED
 * );
 * console.log(`${result.updatedCount} verifications approved`);
 * ```
 */
export async function bulkUpdateVerifications(
  matterId: string,
  verificationIds: string[],
  decision: VerificationDecision,
  notes?: string
): Promise<FindingBulkVerificationResponse> {
  const request: BulkVerificationRequest = {
    verificationIds,
    decision,
    notes,
  };

  // Convert camelCase to snake_case for API
  const response = await api.post<{ data: FindingBulkVerificationResponse }>(
    `/api/matters/${matterId}/verifications/bulk`,
    {
      verification_ids: request.verificationIds,
      decision: request.decision,
      notes: request.notes,
    }
  );
  return response.data;
}

// =============================================================================
// Story 12-3: Export Eligibility Check (Task 1.2)
// =============================================================================

/**
 * Check export eligibility for a matter.
 *
 * Returns whether export is allowed, along with blocking and warning findings.
 * - Blocking findings (< 70% confidence): Must be verified before export
 * - Warning findings (70-90% confidence): Can proceed with warnings
 *
 * @param matterId - Matter UUID.
 * @returns Export eligibility result with blocking and warning findings.
 *
 * @example
 * ```ts
 * const eligibility = await checkExportEligibility('matter-123');
 * if (!eligibility.eligible) {
 *   console.log(`${eligibility.blockingCount} findings block export`);
 * }
 * ```
 */
export async function checkExportEligibility(matterId: string): Promise<ExportEligibility> {
  // API returns snake_case, convert to camelCase
  const response = await api.get<{
    eligible: boolean;
    blocking_findings: Array<{
      verification_id: string;
      finding_id: string | null;
      finding_type: string;
      finding_summary: string;
      confidence: number;
    }>;
    blocking_count: number;
    warning_findings: Array<{
      verification_id: string;
      finding_id: string | null;
      finding_type: string;
      finding_summary: string;
      confidence: number;
    }>;
    warning_count: number;
    message: string;
  }>(`/api/matters/${matterId}/verifications/export-eligibility`);

  return {
    eligible: response.eligible,
    blockingFindings: response.blocking_findings.map((f) => ({
      verificationId: f.verification_id,
      findingId: f.finding_id,
      findingType: f.finding_type,
      findingSummary: f.finding_summary,
      confidence: f.confidence,
    })),
    blockingCount: response.blocking_count,
    warningFindings: response.warning_findings.map((f) => ({
      verificationId: f.verification_id,
      findingId: f.finding_id,
      findingType: f.finding_type,
      findingSummary: f.finding_summary,
      confidence: f.confidence,
    })),
    warningCount: response.warning_count,
    message: response.message,
  };
}

// =============================================================================
// Story 8-5: Consolidated API Object
// =============================================================================

/**
 * Verification API methods consolidated for convenience.
 */
export const verificationsApi = {
  getStats: getVerificationStats,
  getPendingQueue,
  getVerifications,
  approve: approveVerification,
  reject: rejectVerification,
  flag: flagVerification,
  bulkUpdate: bulkUpdateVerifications,
  checkExportEligibility,
};
