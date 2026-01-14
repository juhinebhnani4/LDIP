/**
 * Verification Types for Attorney Finding Verification Workflow
 *
 * Types for the verification queue UI and finding verification.
 * Matches backend Pydantic models in app/models/verification.py
 *
 * Story 8-5: Implement Verification Queue UI
 * Epic 8: Safety Layer (Guardrails, Policing, Verification)
 */

// =============================================================================
// Story 8-5: Verification Enums (Task 8.2, 8.3)
// =============================================================================

/**
 * Attorney verification decision.
 *
 * Matches backend VerificationDecision enum.
 */
export enum VerificationDecision {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  FLAGGED = 'flagged',
}

/**
 * Verification requirement tier based on confidence.
 *
 * Implements ADR-004 tiered verification:
 * - OPTIONAL: Confidence > 90% (export allowed)
 * - SUGGESTED: Confidence 70-90% (export warning shown)
 * - REQUIRED: Confidence < 70% (export blocked until verified)
 */
export enum VerificationRequirement {
  OPTIONAL = 'optional',
  SUGGESTED = 'suggested',
  REQUIRED = 'required',
}

// =============================================================================
// Story 8-5: Queue Item Types (Task 8.4)
// =============================================================================

/**
 * Item in verification queue for UI display.
 *
 * Matches backend VerificationQueueItem model.
 */
export interface VerificationQueueItem {
  /** Verification UUID */
  id: string;
  /** Finding UUID (nullable if finding was deleted) */
  findingId: string | null;
  /** Finding type for filtering (citation_mismatch, timeline_anomaly, etc.) */
  findingType: string;
  /** Summary for queue display */
  findingSummary: string;
  /** Confidence percentage (0-100) */
  confidence: number;
  /** Verification requirement tier */
  requirement: VerificationRequirement;
  /** Current decision status */
  decision: VerificationDecision;
  /** When finding was created */
  createdAt: string;
  /** Primary source document name */
  sourceDocument: string | null;
  /** Source engine (citation, timeline, contradiction) */
  engine: string;
}

// =============================================================================
// Story 8-5: Statistics Types (Task 8.5)
// =============================================================================

/**
 * Verification statistics for dashboard.
 *
 * Matches backend VerificationStats model.
 */
export interface VerificationStats {
  /** Total verification records */
  totalVerifications: number;
  /** Awaiting review */
  pendingCount: number;
  /** Approved by attorney */
  approvedCount: number;
  /** Rejected by attorney */
  rejectedCount: number;
  /** Flagged for further review */
  flaggedCount: number;
  /** < 70% confidence, pending (blocks export) */
  requiredPending: number;
  /** 70-90% confidence, pending */
  suggestedPending: number;
  /** > 90% confidence, pending */
  optionalPending: number;
  /** True if has unverified findings < 70% confidence */
  exportBlocked: boolean;
  /** Count of findings blocking export */
  blockingCount: number;
}

// =============================================================================
// Story 8-5: Filter Types (Task 8.6)
// =============================================================================

/**
 * Confidence tier for filtering.
 */
export type ConfidenceTier = 'high' | 'medium' | 'low';

/**
 * View mode for verification queue.
 */
export type VerificationView = 'queue' | 'by-type' | 'history';

/**
 * Filter state for verification queue.
 */
export interface VerificationFilters {
  /** Filter by finding type */
  findingType: string | null;
  /** Filter by confidence tier (high >90%, medium 70-90%, low <70%) */
  confidenceTier: ConfidenceTier | null;
  /** Filter by verification status */
  status: VerificationDecision | null;
  /** Current view mode */
  view: VerificationView;
}

// =============================================================================
// Story 8-5: API Response Types
// =============================================================================

/**
 * Response for verification queue endpoint.
 */
export interface VerificationQueueResponse {
  data: VerificationQueueItem[];
  meta: {
    limit: number;
    count: number;
  };
}

/**
 * Response for verification stats endpoint.
 */
export interface VerificationStatsResponse {
  data: VerificationStats;
}

/**
 * Complete verification record from database.
 */
export interface FindingVerification {
  id: string;
  matterId: string;
  findingId: string | null;
  findingType: string;
  findingSummary: string;
  confidenceBefore: number;
  decision: VerificationDecision;
  verifiedBy: string | null;
  verifiedAt: string | null;
  confidenceAfter: number | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  verificationRequirement: VerificationRequirement;
}

/**
 * Response for single verification record.
 */
export interface VerificationResponse {
  data: FindingVerification;
}

/**
 * Response for verification list endpoint.
 */
export interface VerificationListResponse {
  data: FindingVerification[];
}

/**
 * Response for bulk verification operations.
 */
export interface BulkVerificationResponse {
  data: Record<string, unknown>;
  updatedCount: number;
  failedIds: string[];
}

// =============================================================================
// Story 8-5: Request Types
// =============================================================================

/**
 * Request body for approving a verification.
 */
export interface ApproveVerificationRequest {
  notes?: string;
  confidenceAfter?: number;
}

/**
 * Request body for rejecting a verification.
 */
export interface RejectVerificationRequest {
  notes: string;
}

/**
 * Request body for flagging a verification.
 */
export interface FlagVerificationRequest {
  notes: string;
}

/**
 * Request for bulk verification operations.
 */
export interface BulkVerificationRequest {
  verificationIds: string[];
  decision: VerificationDecision;
  notes?: string;
}
