/**
 * Confidence Display Utilities
 *
 * Transforms technical confidence percentages into lawyer-friendly
 * verification status labels.
 *
 * Part of the Lawyer UX Improvements initiative.
 */

export type VerificationStatusLevel = 'verified' | 'likely_correct' | 'needs_review';

export interface VerificationStatus {
  /** Display label for the status */
  label: string;
  /** Short label for compact displays */
  shortLabel: string;
  /** CSS classes for badge styling */
  badgeClass: string;
  /** CSS classes for text color */
  textClass: string;
  /** CSS classes for background color */
  bgClass: string;
  /** Status level identifier */
  level: VerificationStatusLevel;
  /** Original confidence value (0-1) */
  confidence: number;
  /** Confidence as percentage (0-100) */
  confidencePercent: number;
}

/**
 * Convert a confidence score (0-1 or 0-100) to a lawyer-friendly verification status.
 *
 * Thresholds:
 * - >= 90%: "Verified" (green) - High confidence, reliable finding
 * - 70-89%: "Likely Correct" (yellow) - Review recommended
 * - < 70%: "Needs Review" (red) - Requires attorney verification
 *
 * @param confidence - Confidence score (0-1 or 0-100)
 * @returns VerificationStatus object with label and styling
 *
 * @example
 * ```tsx
 * const status = getVerificationStatus(0.94);
 * // status.label = "Verified"
 * // status.badgeClass = "bg-green-100 text-green-800 border-green-200"
 *
 * <Badge className={status.badgeClass}>{status.label}</Badge>
 * ```
 */
export function getVerificationStatus(confidence: number): VerificationStatus {
  // Normalize to 0-1 range if passed as percentage
  const normalizedConfidence = confidence > 1 ? confidence / 100 : confidence;
  const percent = Math.round(normalizedConfidence * 100);

  if (normalizedConfidence >= 0.9) {
    return {
      label: 'Verified',
      shortLabel: 'Verified',
      badgeClass: 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800',
      textClass: 'text-green-700 dark:text-green-400',
      bgClass: 'bg-green-100 dark:bg-green-900/30',
      level: 'verified',
      confidence: normalizedConfidence,
      confidencePercent: percent,
    };
  }

  if (normalizedConfidence >= 0.7) {
    return {
      label: 'Likely Correct',
      shortLabel: 'Likely',
      badgeClass: 'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800',
      textClass: 'text-yellow-700 dark:text-yellow-400',
      bgClass: 'bg-yellow-100 dark:bg-yellow-900/30',
      level: 'likely_correct',
      confidence: normalizedConfidence,
      confidencePercent: percent,
    };
  }

  return {
    label: 'Needs Review',
    shortLabel: 'Review',
    badgeClass: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
    textClass: 'text-red-700 dark:text-red-400',
    bgClass: 'bg-red-100 dark:bg-red-900/30',
    level: 'needs_review',
    confidence: normalizedConfidence,
    confidencePercent: percent,
  };
}

/**
 * Get icon name suggestion based on verification status.
 * Returns lucide-react icon names.
 */
export function getVerificationStatusIcon(status: VerificationStatus): string {
  switch (status.level) {
    case 'verified':
      return 'CheckCircle2';
    case 'likely_correct':
      return 'AlertCircle';
    case 'needs_review':
      return 'XCircle';
    default:
      return 'HelpCircle';
  }
}

/**
 * Format confidence for tooltip display.
 * Shows the raw percentage for power users.
 */
export function formatConfidenceTooltip(confidence: number): string {
  const percent = confidence > 1 ? confidence : Math.round(confidence * 100);
  return `AI Confidence: ${percent}%`;
}
