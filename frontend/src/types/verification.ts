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
  /** User UUID who verified (AC #2 - recorded on approval) */
  verifiedBy?: string | null;
  /** When verified (AC #2 - recorded on approval) */
  verifiedAt?: string | null;
  /** Attorney notes for decision */
  notes?: string | null;
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

// =============================================================================
// Story 12-3: Export Eligibility Types (Task 1)
// =============================================================================

/**
 * Finding that blocks export.
 *
 * Story 12-3: AC #1 - Details of finding blocking export.
 */
export interface ExportBlockingFinding {
  verificationId: string;
  findingId: string | null;
  findingType: string;
  findingSummary: string;
  confidence: number;
}

/**
 * Finding that shows warning but doesn't block export.
 *
 * Story 12-3: AC #2 - Findings with 70-90% confidence show warning.
 */
export interface ExportWarningFinding {
  verificationId: string;
  findingId: string | null;
  findingType: string;
  findingSummary: string;
  confidence: number;
}

/**
 * Result of export eligibility check.
 *
 * Story 12-3: AC #1, #2 - Export eligibility with blocking and warning findings.
 */
export interface ExportEligibility {
  eligible: boolean;
  blockingFindings: ExportBlockingFinding[];
  blockingCount: number;
  warningFindings: ExportWarningFinding[];
  warningCount: number;
  message: string;
}

/**
 * Response for export eligibility endpoint.
 */
export interface ExportEligibilityResponse {
  data: ExportEligibility;
}


// =============================================================================
// Verification Priority (Lawyer UX Improvement)
// =============================================================================

/**
 * Priority level for verification items.
 * Used to help lawyers focus on most urgent items first.
 */
export type VerificationPriority = 'urgent' | 'high' | 'normal' | 'low';

/**
 * Priority analysis result for a verification item.
 */
export interface VerificationPriorityAnalysis {
  /** Calculated priority level */
  priority: VerificationPriority;
  /** Priority score (higher = more urgent) */
  score: number;
  /** Reasons for this priority */
  reasons: string[];
  /** Badge color class for display */
  badgeClass: string;
  /** Label for display */
  label: string;
}

/**
 * Calculate priority for a verification item.
 *
 * Factors considered:
 * - Requirement level (REQUIRED > SUGGESTED > OPTIONAL)
 * - Confidence score (lower = higher priority)
 * - Age (older items get slight boost)
 * - Finding type (contradictions often need faster review)
 *
 * @example
 * ```ts
 * const analysis = calculateVerificationPriority(item);
 * // { priority: 'urgent', label: 'For Immediate Review', reasons: [...] }
 * ```
 */
export function calculateVerificationPriority(
  item: VerificationQueueItem
): VerificationPriorityAnalysis {
  let score = 0;
  const reasons: string[] = [];

  // Requirement level weight (most important)
  switch (item.requirement) {
    case VerificationRequirement.REQUIRED:
      score += 50;
      reasons.push('Required verification (blocks export)');
      break;
    case VerificationRequirement.SUGGESTED:
      score += 30;
      reasons.push('Suggested verification');
      break;
    case VerificationRequirement.OPTIONAL:
      score += 10;
      break;
  }

  // Confidence score weight (lower confidence = higher priority)
  if (item.confidence < 50) {
    score += 30;
    reasons.push('Very low confidence (<50%)');
  } else if (item.confidence < 70) {
    score += 20;
    reasons.push('Low confidence (<70%)');
  } else if (item.confidence < 85) {
    score += 10;
  }

  // Finding type weight (some findings need faster review)
  if (item.findingType === 'contradiction' || item.findingType === 'factual_mismatch') {
    score += 15;
    reasons.push('Contradiction finding');
  } else if (item.findingType === 'citation_mismatch') {
    score += 10;
    reasons.push('Citation verification needed');
  }

  // Age weight (items older than 7 days get boost)
  const createdDate = new Date(item.createdAt);
  const daysSinceCreated = Math.floor(
    (Date.now() - createdDate.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (daysSinceCreated > 14) {
    score += 15;
    reasons.push('Pending for over 2 weeks');
  } else if (daysSinceCreated > 7) {
    score += 10;
    reasons.push('Pending for over a week');
  }

  // Determine priority level from score
  let priority: VerificationPriority;
  let label: string;
  let badgeClass: string;

  if (score >= 70) {
    priority = 'urgent';
    label = 'For Immediate Review';
    badgeClass = 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400';
  } else if (score >= 50) {
    priority = 'high';
    label = 'Review Soon';
    badgeClass = 'bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400';
  } else if (score >= 30) {
    priority = 'normal';
    label = 'Standard Review';
    badgeClass = 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400';
  } else {
    priority = 'low';
    label = 'Can Wait';
    badgeClass = 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400';
  }

  return {
    priority,
    score,
    reasons,
    badgeClass,
    label,
  };
}

/**
 * Sort verification items by priority (highest first).
 */
export function sortByPriority(items: VerificationQueueItem[]): VerificationQueueItem[] {
  return [...items].sort((a, b) => {
    const priorityA = calculateVerificationPriority(a);
    const priorityB = calculateVerificationPriority(b);
    return priorityB.score - priorityA.score;
  });
}
