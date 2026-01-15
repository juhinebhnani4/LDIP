/**
 * PDF Highlight Utilities
 *
 * Functions for rendering bounding box highlights on PDF canvas.
 * Uses canvas overlays (NOT DOM elements) for performance per project-context.md.
 *
 * Story 3-4: Split-View Citation Highlighting
 */

import type { BoundingBox, CanvasRect, HighlightColors, HighlightType } from '@/types/pdf';
import type { VerificationStatus, DiffDetail, SplitViewBoundingBox } from '@/types/citation';
import { HIGHLIGHT_COLORS } from '@/types/pdf';

// =============================================================================
// Position Calculation
// =============================================================================

/**
 * Calculate absolute canvas position from normalized bbox coordinates.
 *
 * Bounding box coordinates from Google Document AI are normalized (0-1 range).
 * This function converts them to actual pixel positions based on page dimensions
 * and current scale.
 *
 * @param bbox - Bounding box with normalized coordinates
 * @param pageWidth - Actual page width in pixels
 * @param pageHeight - Actual page height in pixels
 * @param scale - Current zoom scale factor
 * @returns Canvas-ready rectangle with pixel coordinates
 *
 * @example
 * ```ts
 * const rect = calculateBboxPosition(
 *   { id: '1', x: 0.1, y: 0.3, width: 0.4, height: 0.05 },
 *   612, // Letter width in points
 *   792, // Letter height in points
 *   1.5  // 150% zoom
 * );
 * // rect = { x: 91.8, y: 356.4, width: 367.2, height: 59.4 }
 * ```
 */
export function calculateBboxPosition(
  bbox: BoundingBox | SplitViewBoundingBox,
  pageWidth: number,
  pageHeight: number,
  scale: number
): CanvasRect {
  return {
    x: bbox.x * pageWidth * scale,
    y: bbox.y * pageHeight * scale,
    width: bbox.width * pageWidth * scale,
    height: bbox.height * pageHeight * scale,
  };
}

// =============================================================================
// Color Utilities
// =============================================================================

/**
 * Get highlight colors based on verification status and panel type.
 *
 * @param status - Verification status of the citation
 * @param isSource - Whether this is the source (left) panel
 * @returns Highlight colors for background and border
 *
 * @example
 * ```ts
 * // Source citation is always yellow
 * const sourceColor = getBboxColor('verified', true);
 * // sourceColor = { background: '#FDE047', border: '#CA8A04' }
 *
 * // Target with verified status is blue
 * const targetColor = getBboxColor('verified', false);
 * // targetColor = { background: '#BFDBFE', border: '#3B82F6' }
 *
 * // Target with mismatch is red
 * const mismatchColor = getBboxColor('mismatch', false);
 * // mismatchColor = { background: '#FECACA', border: '#EF4444' }
 * ```
 */
export function getBboxColor(
  status: VerificationStatus,
  isSource: boolean
): HighlightColors {
  // Source citation is always yellow
  if (isSource) {
    return HIGHLIGHT_COLORS.source;
  }

  // Target panel colors depend on verification status
  switch (status) {
    case 'verified':
      return HIGHLIGHT_COLORS.verified;
    case 'mismatch':
      return HIGHLIGHT_COLORS.mismatch;
    case 'section_not_found':
      return HIGHLIGHT_COLORS.sectionNotFound;
    case 'pending':
    case 'act_unavailable':
    default:
      return HIGHLIGHT_COLORS.verified; // Default to blue for target
  }
}

/**
 * Get highlight colors based on highlight type (Story 11.7).
 *
 * Maps semantic highlight types to colors:
 * - citation: Yellow (source citations)
 * - entity: Blue (entity mentions in MIG)
 * - contradiction: Red (contradiction highlights)
 *
 * @param highlightType - The type of highlight
 * @returns Highlight colors for background and border
 *
 * @example
 * ```ts
 * const citationColor = getHighlightTypeColor('citation');
 * // citationColor = { background: '#FDE047', border: '#CA8A04' }
 *
 * const entityColor = getHighlightTypeColor('entity');
 * // entityColor = { background: '#BFDBFE', border: '#3B82F6' }
 *
 * const contradictionColor = getHighlightTypeColor('contradiction');
 * // contradictionColor = { background: '#FECACA', border: '#EF4444' }
 * ```
 */
export function getHighlightTypeColor(highlightType: HighlightType): HighlightColors {
  switch (highlightType) {
    case 'citation':
      return HIGHLIGHT_COLORS.source;
    case 'entity':
      return HIGHLIGHT_COLORS.entity;
    case 'contradiction':
      return HIGHLIGHT_COLORS.contradiction;
    default:
      return HIGHLIGHT_COLORS.source;
  }
}

// =============================================================================
// Canvas Rendering
// =============================================================================

/**
 * Render a bounding box highlight on a canvas context.
 *
 * Uses semi-transparent fill with solid border for visibility.
 *
 * @param ctx - Canvas 2D rendering context
 * @param rect - Rectangle with pixel coordinates
 * @param colors - Background and border colors
 * @param opacity - Fill opacity (0-1), default 0.3
 *
 * @example
 * ```ts
 * const ctx = canvas.getContext('2d');
 * renderBboxHighlight(
 *   ctx,
 *   { x: 91.8, y: 356.4, width: 367.2, height: 59.4 },
 *   { background: '#FDE047', border: '#CA8A04' },
 *   0.3
 * );
 * ```
 */
export function renderBboxHighlight(
  ctx: CanvasRenderingContext2D,
  rect: CanvasRect,
  colors: HighlightColors,
  opacity: number = 0.3
): void {
  // Save current context state
  ctx.save();

  // Draw filled rectangle with transparency
  ctx.fillStyle = hexToRgba(colors.background, opacity);
  ctx.fillRect(rect.x, rect.y, rect.width, rect.height);

  // Draw border
  ctx.strokeStyle = colors.border;
  ctx.lineWidth = 2;
  ctx.strokeRect(rect.x, rect.y, rect.width, rect.height);

  // Restore context state
  ctx.restore();
}

/**
 * Render multiple bounding boxes on a canvas.
 *
 * @param ctx - Canvas 2D rendering context
 * @param bboxes - Array of bounding boxes with normalized coordinates
 * @param pageWidth - Page width in pixels
 * @param pageHeight - Page height in pixels
 * @param scale - Current zoom scale
 * @param status - Verification status for color selection
 * @param isSource - Whether this is the source panel
 */
export function renderBboxHighlights(
  ctx: CanvasRenderingContext2D,
  bboxes: Array<BoundingBox | SplitViewBoundingBox>,
  pageWidth: number,
  pageHeight: number,
  scale: number,
  status: VerificationStatus,
  isSource: boolean
): void {
  const colors = getBboxColor(status, isSource);

  for (const bbox of bboxes) {
    const rect = calculateBboxPosition(bbox, pageWidth, pageHeight, scale);
    renderBboxHighlight(ctx, rect, colors);
  }
}

/**
 * Render multiple bounding boxes on a canvas using highlight type for colors (Story 11.7).
 *
 * @param ctx - Canvas 2D rendering context
 * @param bboxes - Array of bounding boxes with normalized coordinates
 * @param pageWidth - Page width in pixels
 * @param pageHeight - Page height in pixels
 * @param scale - Current zoom scale
 * @param highlightType - Type of highlight for color selection
 */
export function renderBboxHighlightsByType(
  ctx: CanvasRenderingContext2D,
  bboxes: Array<BoundingBox | SplitViewBoundingBox>,
  pageWidth: number,
  pageHeight: number,
  scale: number,
  highlightType: HighlightType
): void {
  const colors = getHighlightTypeColor(highlightType);

  for (const bbox of bboxes) {
    const rect = calculateBboxPosition(bbox, pageWidth, pageHeight, scale);
    renderBboxHighlight(ctx, rect, colors);
  }
}

/**
 * Clear all highlights from a canvas.
 *
 * @param ctx - Canvas 2D rendering context
 * @param width - Canvas width
 * @param height - Canvas height
 */
export function clearHighlights(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number
): void {
  ctx.clearRect(0, 0, width, height);
}

// =============================================================================
// Diff Highlighting (Task 7)
// =============================================================================

/**
 * Get rectangles for highlighting text differences.
 *
 * When there's a mismatch, this identifies specific bbox regions
 * that contain the differing text.
 *
 * @param diffDetails - Diff details from verification result
 * @param bboxes - All bounding boxes in the target section
 * @returns Rectangles that should be highlighted in red
 */
export function getDiffHighlightRects(
  diffDetails: DiffDetail,
  bboxes: Array<BoundingBox | SplitViewBoundingBox>,
  pageWidth: number,
  pageHeight: number,
  scale: number
): CanvasRect[] {
  // For now, highlight all bboxes in mismatch areas
  // A more sophisticated implementation would use text matching
  // to identify specific character-level differences
  const rects: CanvasRect[] = [];

  // If we have differences listed, try to find matching bboxes
  // This is a simplified approach - real implementation would need
  // more sophisticated text alignment
  if (diffDetails.differences.length > 0) {
    for (const bbox of bboxes) {
      // Check if this bbox contains any of the different text
      const bboxText = 'text' in bbox ? (bbox as SplitViewBoundingBox).text : '';
      const hasDifference = diffDetails.differences.some((diff) =>
        bboxText.toLowerCase().includes(diff.toLowerCase())
      );

      if (hasDifference) {
        rects.push(calculateBboxPosition(bbox, pageWidth, pageHeight, scale));
      }
    }
  }

  // If no specific differences found, return all bbox rects
  if (rects.length === 0) {
    return bboxes.map((bbox) =>
      calculateBboxPosition(bbox, pageWidth, pageHeight, scale)
    );
  }

  return rects;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Convert hex color to rgba string with specified opacity.
 *
 * @param hex - Hex color string (with or without #)
 * @param opacity - Opacity value (0-1)
 * @returns RGBA color string
 */
function hexToRgba(hex: string, opacity: number): string {
  const cleanHex = hex.replace('#', '');
  const r = parseInt(cleanHex.substring(0, 2), 16);
  const g = parseInt(cleanHex.substring(2, 4), 16);
  const b = parseInt(cleanHex.substring(4, 6), 16);

  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

/**
 * Check if a point is inside a rectangle.
 *
 * Useful for hit testing when user clicks on highlights.
 *
 * @param x - Point x coordinate
 * @param y - Point y coordinate
 * @param rect - Rectangle to test against
 * @returns Whether the point is inside the rectangle
 */
export function isPointInRect(x: number, y: number, rect: CanvasRect): boolean {
  return (
    x >= rect.x &&
    x <= rect.x + rect.width &&
    y >= rect.y &&
    y <= rect.y + rect.height
  );
}

/**
 * Get the bounding rectangle that contains all provided rectangles.
 *
 * Useful for calculating viewport to show all highlights.
 *
 * @param rects - Array of rectangles
 * @returns Bounding rectangle containing all input rectangles
 */
export function getBoundingRect(rects: CanvasRect[]): CanvasRect | null {
  if (rects.length === 0) {
    return null;
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const rect of rects) {
    minX = Math.min(minX, rect.x);
    minY = Math.min(minY, rect.y);
    maxX = Math.max(maxX, rect.x + rect.width);
    maxY = Math.max(maxY, rect.y + rect.height);
  }

  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  };
}
