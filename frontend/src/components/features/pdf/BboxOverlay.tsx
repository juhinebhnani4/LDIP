'use client';

/**
 * Bounding Box Overlay Component
 *
 * Renders bounding box highlights on a canvas overlay for PDF pages.
 * Uses canvas (NOT DOM elements) for performance per project-context.md.
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #2)
 */

import { useEffect, useRef, type FC } from 'react';
import type { SplitViewBoundingBox, VerificationStatus } from '@/types/citation';
import {
  renderBboxHighlights,
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
  /** Verification status for color selection */
  verificationStatus: VerificationStatus;
  /** Whether this is the source (left) panel */
  isSource: boolean;
  /** Optional className for the canvas */
  className?: string;
}

/**
 * Canvas overlay for rendering bounding box highlights on PDF pages.
 *
 * @example
 * ```tsx
 * <div className="relative">
 *   <PdfPage ... />
 *   <BboxOverlay
 *     boundingBoxes={[{ bboxId: '1', x: 0.1, y: 0.3, width: 0.4, height: 0.05, text: '...' }]}
 *     pageWidth={612}
 *     pageHeight={792}
 *     scale={1.5}
 *     verificationStatus="verified"
 *     isSource={false}
 *   />
 * </div>
 * ```
 */
export const BboxOverlay: FC<BboxOverlayProps> = ({
  boundingBoxes,
  pageWidth,
  pageHeight,
  scale,
  verificationStatus,
  isSource,
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
  }, [boundingBoxes, pageWidth, pageHeight, scale, verificationStatus, isSource]);

  return (
    <canvas
      ref={canvasRef}
      className={`absolute top-0 left-0 pointer-events-none ${className ?? ''}`}
      aria-hidden="true"
    />
  );
};
