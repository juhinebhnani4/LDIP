'use client';

/**
 * Bounding Box Overlay Component
 *
 * Renders bounding box highlights on a canvas overlay for PDF pages.
 * Uses canvas (NOT DOM elements) for performance per project-context.md.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #2)
 * Story 11.7: Bounding Box Overlays with highlight types (AC: #1, #2)
 */

import { useEffect, useRef, type FC } from 'react';
import type { SplitViewBoundingBox, VerificationStatus } from '@/types/citation';
import type { HighlightType } from '@/types/pdf';
import {
  renderBboxHighlights,
  renderBboxHighlightsByType,
  clearHighlights,
} from '@/lib/pdf/highlightUtils';

export interface BboxOverlayProps {
  /** Bounding boxes to highlight (normalized 0-1 coordinates) */
  boundingBoxes: SplitViewBoundingBox[];
  /** Page width in pixels (at scale 1.0) */
  pageWidth: number;
  /** Page height in pixels (at scale 1.0) */
  pageHeight: number;
  /** Current zoom scale */
  scale: number;
  /**
   * Highlight type for semantic categorization (Story 11.7).
   * When provided, takes precedence over verificationStatus/isSource.
   */
  highlightType?: HighlightType;
  /** Verification status for color selection (legacy, used when highlightType not provided) */
  verificationStatus?: VerificationStatus;
  /** Whether this is the source (left) panel (legacy, used when highlightType not provided) */
  isSource?: boolean;
  /** Optional className for the canvas */
  className?: string;
}

/**
 * Canvas overlay for rendering bounding box highlights on PDF pages.
 *
 * @example
 * ```tsx
 * // Using highlightType (Story 11.7 - preferred)
 * <BboxOverlay
 *   boundingBoxes={bboxes}
 *   pageWidth={612}
 *   pageHeight={792}
 *   scale={1.5}
 *   highlightType="citation"
 * />
 *
 * // Using legacy verificationStatus/isSource
 * <BboxOverlay
 *   boundingBoxes={bboxes}
 *   pageWidth={612}
 *   pageHeight={792}
 *   scale={1.5}
 *   verificationStatus="verified"
 *   isSource={false}
 * />
 * ```
 */
export const BboxOverlay: FC<BboxOverlayProps> = ({
  boundingBoxes,
  pageWidth,
  pageHeight,
  scale,
  highlightType,
  verificationStatus = 'pending',
  isSource = true,
  className,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Re-render highlights when props change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size to match scaled page dimensions
    const scaledWidth = pageWidth * scale;
    const scaledHeight = pageHeight * scale;

    // Handle high DPI displays
    const dpr = window.devicePixelRatio || 1;
    canvas.width = scaledWidth * dpr;
    canvas.height = scaledHeight * dpr;
    canvas.style.width = `${scaledWidth}px`;
    canvas.style.height = `${scaledHeight}px`;

    // Scale context for high DPI
    ctx.scale(dpr, dpr);

    // Clear previous highlights
    clearHighlights(ctx, scaledWidth, scaledHeight);

    // Render new highlights
    if (boundingBoxes.length > 0) {
      // Story 11.7: Use highlightType if provided, otherwise fall back to legacy approach
      if (highlightType) {
        renderBboxHighlightsByType(
          ctx,
          boundingBoxes,
          pageWidth,
          pageHeight,
          scale,
          highlightType
        );
      } else {
        renderBboxHighlights(
          ctx,
          boundingBoxes,
          pageWidth,
          pageHeight,
          scale,
          verificationStatus,
          isSource
        );
      }
    }
  }, [boundingBoxes, pageWidth, pageHeight, scale, highlightType, verificationStatus, isSource]);

  return (
    <canvas
      ref={canvasRef}
      className={`absolute top-0 left-0 pointer-events-none ${className ?? ''}`}
      aria-hidden="true"
    />
  );
};
