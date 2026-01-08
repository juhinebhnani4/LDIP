/**
 * OCR Quality Assessment Constants
 *
 * Centralized thresholds for OCR quality classification.
 * These values should match the backend thresholds in:
 * - backend/app/services/ocr/confidence_calculator.py
 * - supabase/migrations/20260108000002_add_ocr_quality_columns.sql
 */

/** Threshold for "good" quality - 85% and above */
export const OCR_QUALITY_GOOD_THRESHOLD = 0.85;

/** Threshold for "fair" quality - 70% to 84.99% */
export const OCR_QUALITY_FAIR_THRESHOLD = 0.70;

/** Threshold for highlighting pages needing review - below 60% */
export const OCR_PAGE_REVIEW_THRESHOLD = 0.60;

/**
 * Determine quality status from confidence score
 */
export function getQualityStatus(confidence: number | null): 'good' | 'fair' | 'poor' | null {
  if (confidence === null) return null;
  if (confidence >= OCR_QUALITY_GOOD_THRESHOLD) return 'good';
  if (confidence >= OCR_QUALITY_FAIR_THRESHOLD) return 'fair';
  return 'poor';
}

/**
 * Check if a page needs review based on confidence
 */
export function pageNeedsReview(confidence: number): boolean {
  return confidence < OCR_PAGE_REVIEW_THRESHOLD;
}
