/**
 * PDF Viewer Types for Split-View Citation Highlighting
 *
 * Types for PDF rendering, bounding box overlays, and viewer state management.
 *
 * Story 3-4: Split-View Citation Highlighting
 */

// =============================================================================
// Bounding Box Types (for PDF overlay rendering)
// =============================================================================

/** Normalized bounding box from backend (0-1 range coordinates) */
export interface BoundingBox {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Canvas-ready rectangle with pixel coordinates */
export interface CanvasRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Bounding box with associated text and metadata */
export interface BoundingBoxData {
  bboxId: string;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
}

// =============================================================================
// PDF Viewer State Types
// =============================================================================

/** State for a PDF viewer panel */
export interface PdfViewerState {
  currentPage: number;
  scale: number;
  scrollPosition: { x: number; y: number };
}

/** Zoom level presets */
export type ZoomLevel = 'fit-width' | 'fit-page' | 'custom';

/** Navigation direction */
export type NavigationDirection = 'prev' | 'next';

// =============================================================================
// Highlight Color Types
// =============================================================================

/** Highlight colors for different verification statuses */
export interface HighlightColors {
  background: string;
  border: string;
}

/** Color scheme for highlight statuses - jaanch.ai brand palette */
export const HIGHLIGHT_COLORS = {
  /** Source citation in case document - Warm Cream / Muted Gold */
  source: {
    background: '#f5f0d8',
    border: '#b8973b',
  },
  /** Verified section in Act document - Light Indigo */
  verified: {
    background: '#e8eef8',
    border: '#0d1b5e',
  },
  /** Mismatch in Act document - Soft Pink / Burgundy */
  mismatch: {
    background: '#f2d4d7',
    border: '#8b2635',
  },
  /** Section not found - Warm Peach / Aged Gold */
  sectionNotFound: {
    background: '#f5e8d8',
    border: '#c4a35a',
  },
  /** Entity mention highlight - Light Indigo (Story 11.7) */
  entity: {
    background: '#e8eef8',
    border: '#0d1b5e',
  },
  /** Contradiction highlight - Soft Pink / Burgundy (Story 11.7) */
  contradiction: {
    background: '#f2d4d7',
    border: '#8b2635',
  },
} as const;

/** Highlight status type derived from color keys */
export type HighlightStatus = keyof typeof HIGHLIGHT_COLORS;

/**
 * Highlight type for semantic categorization (Story 11.7)
 *
 * Used by BboxOverlay to determine highlight colors based on purpose:
 * - citation: Source citations in documents (yellow)
 * - entity: Entity mentions in MIG (blue)
 * - contradiction: Contradiction highlights (red)
 */
export type HighlightType = 'citation' | 'entity' | 'contradiction';

// =============================================================================
// PDF Document Types
// =============================================================================

/** Document view data for split view panel */
export interface DocumentViewData {
  documentId: string;
  documentUrl: string;
  pageNumber: number;
  boundingBoxes: BoundingBoxData[];
}

/** Error states for PDF viewer */
export interface PdfViewerError {
  code: 'LOAD_FAILED' | 'RENDER_FAILED' | 'BBOX_NOT_FOUND' | 'NETWORK_ERROR';
  message: string;
  retryable: boolean;
}

// =============================================================================
// Keyboard Shortcuts
// =============================================================================

/** Keyboard shortcut mapping */
export const PDF_KEYBOARD_SHORTCUTS = {
  close: 'Escape',
  toggleFullscreen: 'f',
  prevCitation: 'ArrowLeft',
  nextCitation: 'ArrowRight',
  zoomIn: '+',
  zoomInAlt: '=',
  zoomOut: '-',
} as const;
