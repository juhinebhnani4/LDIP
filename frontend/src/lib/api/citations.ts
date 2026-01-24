/**
 * Citation API Client for Act Citation Extraction and Verification
 *
 * Provides typed API functions for citation operations.
 *
 * Story 3-1: Act Citation Extraction
 * Story 3-3: Citation Verification
 */

import { api } from './client';
import type {
  ActDiscoveryResponse,
  ActResolutionResponse,
  BatchVerificationResponse,
  CitationListOptions,
  CitationResponse,
  CitationsListResponse,
  CitationStats,
  CitationSummaryResponse,
  MarkActSkippedRequest,
  MarkActUploadedRequest,
  SplitViewResponse,
  VerificationResultResponse,
  VerificationStatus,
  VerifyActRequest,
  VerifyCitationRequest,
} from '@/types';

/**
 * Build query string from options object.
 */
function buildQueryString(options: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(options)) {
    if (value !== undefined) {
      // Convert camelCase to snake_case for API
      const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase();
      params.append(snakeKey, String(value));
    }
  }
  const queryString = params.toString();
  return queryString ? `?${queryString}` : '';
}

// =============================================================================
// Citation Operations
// =============================================================================

/**
 * Get paginated list of citations in a matter.
 *
 * @param matterId - Matter UUID
 * @param options - Query options (actName, verificationStatus, documentId, page, perPage)
 * @returns Paginated list of citations
 *
 * @example
 * ```ts
 * const citations = await getCitations('matter-123', {
 *   actName: 'Negotiable Instruments Act',
 *   verificationStatus: 'pending',
 *   page: 1,
 *   perPage: 20,
 * });
 * console.log(citations.data); // CitationListItem[]
 * console.log(citations.meta.total); // Total count
 * ```
 */
export async function getCitations(
  matterId: string,
  options: CitationListOptions = {}
): Promise<CitationsListResponse> {
  const queryString = buildQueryString({
    actName: options.actName,
    verificationStatus: options.verificationStatus,
    documentId: options.documentId,
    page: options.page,
    perPage: options.perPage,
  });

  return api.get<CitationsListResponse>(`/api/matters/${matterId}/citations${queryString}`);
}

/**
 * Get a single citation by ID.
 *
 * @param matterId - Matter UUID
 * @param citationId - Citation UUID
 * @returns Citation details
 *
 * @example
 * ```ts
 * const citation = await getCitation('matter-123', 'citation-456');
 * console.log(citation.data.actName); // "Negotiable Instruments Act, 1881"
 * console.log(citation.data.sectionNumber); // "138"
 * console.log(citation.data.verificationStatus); // "pending"
 * ```
 */
export async function getCitation(
  matterId: string,
  citationId: string
): Promise<CitationResponse> {
  return api.get<CitationResponse>(`/api/matters/${matterId}/citations/${citationId}`);
}

/**
 * Get citation counts grouped by Act.
 *
 * Useful for showing which Acts are most frequently cited.
 *
 * @param matterId - Matter UUID
 * @returns Citation summary grouped by Act
 *
 * @example
 * ```ts
 * const summary = await getCitationSummary('matter-123');
 * for (const item of summary.data) {
 *   console.log(`${item.actName}: ${item.citationCount} citations`);
 * }
 * ```
 */
export async function getCitationSummary(
  matterId: string
): Promise<CitationSummaryResponse> {
  return api.get<CitationSummaryResponse>(`/api/matters/${matterId}/citations/summary/by-act`);
}

/**
 * Get citation statistics for a matter.
 *
 * Returns summary statistics including total citations,
 * unique Acts, and verification status breakdown.
 *
 * @param matterId - Matter UUID
 * @returns Citation statistics
 *
 * @example
 * ```ts
 * const stats = await getCitationStats('matter-123');
 * console.log(`Total: ${stats.totalCitations}`);
 * console.log(`Missing Acts: ${stats.missingActsCount}`);
 * ```
 */
export async function getCitationStats(
  matterId: string
): Promise<CitationStats> {
  return api.get<CitationStats>(`/api/matters/${matterId}/citations/stats`);
}

/**
 * Update citation verification status (manual override).
 *
 * Allows lawyers to mark a citation as verified after manual review,
 * or change status when automated verification is incorrect.
 *
 * @param matterId - Matter UUID
 * @param citationId - Citation UUID
 * @param verificationStatus - New verification status
 * @returns Update confirmation with new status
 *
 * @example
 * ```ts
 * // Mark citation as manually verified
 * const result = await updateCitationStatus('matter-123', 'citation-456', 'verified');
 * console.log(result.success); // true
 * console.log(result.verificationStatus); // "verified"
 * ```
 */
export async function updateCitationStatus(
  matterId: string,
  citationId: string,
  verificationStatus: VerificationStatus
): Promise<{ success: boolean; citationId: string; verificationStatus: VerificationStatus }> {
  return api.patch<{ success: boolean; citationId: string; verificationStatus: VerificationStatus }>(
    `/api/matters/${matterId}/citations/${citationId}/status`,
    { verificationStatus }
  );
}

// =============================================================================
// Act Discovery Operations
// =============================================================================

/**
 * Get Act Discovery Report.
 *
 * Returns list of all Acts referenced in the matter with their resolution status.
 * Shows which Acts are uploaded, missing, or skipped.
 *
 * This is the primary function for the "Missing Acts" UI.
 *
 * @param matterId - Matter UUID
 * @param includeAvailable - Whether to include Acts that are already available (default true)
 * @returns Act Discovery Report
 *
 * @example
 * ```ts
 * // Get all acts
 * const report = await getActDiscoveryReport('matter-123');
 *
 * // Get only missing acts
 * const missing = await getActDiscoveryReport('matter-123', false);
 * for (const act of missing.data) {
 *   if (act.resolutionStatus === 'missing') {
 *     console.log(`Missing: ${act.actName} (${act.citationCount} citations)`);
 *   }
 * }
 * ```
 */
export async function getActDiscoveryReport(
  matterId: string,
  includeAvailable: boolean = true
): Promise<ActDiscoveryResponse> {
  const queryString = buildQueryString({ includeAvailable: includeAvailable ? 1 : 0 });
  return api.get<ActDiscoveryResponse>(`/api/matters/${matterId}/citations/acts/discovery${queryString}`);
}

/**
 * Get only missing Acts that need user action.
 *
 * Convenience wrapper around getActDiscoveryReport that filters for missing Acts.
 *
 * @param matterId - Matter UUID
 * @returns List of missing Acts
 */
export async function getMissingActs(matterId: string): Promise<ActDiscoveryResponse> {
  const report = await getActDiscoveryReport(matterId, false);
  return {
    data: report.data.filter(
      (act) => act.resolutionStatus === 'missing' && act.userAction === 'pending'
    ),
  };
}

// =============================================================================
// Act Resolution Operations
// =============================================================================

/**
 * Mark an Act as uploaded.
 *
 * Call this after uploading an Act document to update the resolution status.
 *
 * @param matterId - Matter UUID
 * @param request - Act upload details
 * @returns Updated resolution status
 *
 * @example
 * ```ts
 * // After uploading the NI Act document
 * const result = await markActUploaded('matter-123', {
 *   actName: 'Negotiable Instruments Act, 1881',
 *   actDocumentId: 'doc-789',
 * });
 * console.log(result.success); // true
 * ```
 */
export async function markActUploaded(
  matterId: string,
  request: MarkActUploadedRequest
): Promise<ActResolutionResponse> {
  return api.post<ActResolutionResponse>(
    `/api/matters/${matterId}/citations/acts/mark-uploaded`,
    request
  );
}

/**
 * Mark an Act as skipped.
 *
 * User chooses not to upload this Act (maybe they don't have it).
 * The Act will no longer appear in the "missing" list.
 *
 * @param matterId - Matter UUID
 * @param request - Act to skip
 * @returns Updated resolution status
 *
 * @example
 * ```ts
 * // User doesn't have the Arbitration Act
 * const result = await markActSkipped('matter-123', {
 *   actName: 'Arbitration and Conciliation Act, 1996',
 * });
 * console.log(result.success); // true
 * ```
 */
export async function markActSkipped(
  matterId: string,
  request: MarkActSkippedRequest
): Promise<ActResolutionResponse> {
  return api.post<ActResolutionResponse>(
    `/api/matters/${matterId}/citations/acts/mark-skipped`,
    request
  );
}

// =============================================================================
// Citation Verification Operations (Story 3-3)
// =============================================================================

/**
 * Start batch verification of citations for an Act.
 *
 * Triggers an async task to verify all citations referencing
 * the specified Act against the uploaded Act document.
 *
 * @param matterId - Matter UUID
 * @param request - Verification request with Act name and document ID
 * @returns Batch verification response with task ID
 *
 * @example
 * ```ts
 * // Start verification for NI Act
 * const result = await verifyCitationsBatch('matter-123', {
 *   actName: 'Negotiable Instruments Act, 1881',
 *   actDocumentId: 'doc-456',
 * });
 * console.log(result.taskId); // "task-789"
 * console.log(result.totalCitations); // 25
 * ```
 */
export async function verifyCitationsBatch(
  matterId: string,
  request: VerifyActRequest
): Promise<BatchVerificationResponse> {
  return api.post<BatchVerificationResponse>(
    `/api/matters/${matterId}/citations/verify`,
    request
  );
}

/**
 * Verify a single citation against an Act document.
 *
 * Triggers an async task to verify the specific citation.
 * Useful for re-verification or on-demand verification.
 *
 * @param matterId - Matter UUID
 * @param citationId - Citation UUID to verify
 * @param request - Verification request with Act document ID
 * @returns Batch verification response with task ID
 *
 * @example
 * ```ts
 * const result = await verifySingleCitation('matter-123', 'citation-456', {
 *   actDocumentId: 'doc-789',
 *   actName: 'Negotiable Instruments Act, 1881',
 * });
 * console.log(result.taskId); // "task-xyz"
 * ```
 */
export async function verifySingleCitation(
  matterId: string,
  citationId: string,
  request: VerifyCitationRequest
): Promise<BatchVerificationResponse> {
  return api.post<BatchVerificationResponse>(
    `/api/matters/${matterId}/citations/${citationId}/verify`,
    request
  );
}

/**
 * Mark an Act as uploaded and automatically trigger verification.
 *
 * Combines marking the Act as uploaded with triggering verification
 * of all citations referencing this Act.
 *
 * @param matterId - Matter UUID
 * @param request - Act upload details
 * @returns Updated resolution status
 *
 * @example
 * ```ts
 * // Mark NI Act as uploaded and start verification
 * const result = await markActUploadedAndVerify('matter-123', {
 *   actName: 'Negotiable Instruments Act, 1881',
 *   actDocumentId: 'doc-456',
 * });
 * // Verification runs automatically in the background
 * console.log(result.success); // true
 * ```
 */
export async function markActUploadedAndVerify(
  matterId: string,
  request: MarkActUploadedRequest
): Promise<ActResolutionResponse> {
  return api.post<ActResolutionResponse>(
    `/api/matters/${matterId}/citations/acts/mark-uploaded-verify`,
    request
  );
}

/**
 * Get verification details for a citation.
 *
 * Returns the current verification status and any stored verification
 * metadata for the specified citation.
 *
 * @param matterId - Matter UUID
 * @param citationId - Citation UUID
 * @returns Verification details
 *
 * @example
 * ```ts
 * const details = await getVerificationDetails('matter-123', 'citation-456');
 * console.log(details.data.status); // "verified"
 * console.log(details.data.similarityScore); // 95.0
 * ```
 */
export async function getVerificationDetails(
  matterId: string,
  citationId: string
): Promise<VerificationResultResponse> {
  return api.get<VerificationResultResponse>(
    `/api/matters/${matterId}/citations/${citationId}/verification`
  );
}

/**
 * Get citations filtered for verification purposes.
 *
 * Convenience wrapper around getCitations for fetching citations
 * that need verification or have specific verification statuses.
 *
 * @param matterId - Matter UUID
 * @param options - Optional filters for verification status
 * @returns Paginated list of citations
 *
 * @example
 * ```ts
 * // Get all pending citations
 * const pending = await getCitationsForVerification('matter-123', {
 *   status: 'pending',
 * });
 *
 * // Get all verified citations
 * const verified = await getCitationsForVerification('matter-123', {
 *   status: 'verified',
 * });
 * ```
 */
export async function getCitationsForVerification(
  matterId: string,
  options?: { status?: VerificationStatus }
): Promise<CitationsListResponse> {
  return getCitations(matterId, {
    verificationStatus: options?.status,
  });
}

// =============================================================================
// Split-View Operations (Story 3-4)
// =============================================================================

/**
 * Get split-view data for a citation.
 *
 * Returns all data needed to render the split-view panel including:
 * - Source document URL, page, and bounding boxes
 * - Target Act document URL, page, and bounding boxes (if available)
 * - Verification result with explanation
 *
 * @param matterId - Matter UUID
 * @param citationId - Citation UUID
 * @returns Split view data for rendering
 *
 * @example
 * ```ts
 * const splitView = await getCitationSplitViewData('matter-123', 'citation-456');
 * console.log(splitView.data.sourceDocument.pageNumber); // 45
 * console.log(splitView.data.targetDocument?.pageNumber); // 89
 * ```
 */
export async function getCitationSplitViewData(
  matterId: string,
  citationId: string
): Promise<SplitViewResponse> {
  return api.get<SplitViewResponse>(
    `/api/matters/${matterId}/citations/${citationId}/split-view`
  );
}
