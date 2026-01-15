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

/** Color scheme for highlight statuses */
export const HIGHLIGHT_COLORS = {
  /** Source citation in case document - Yellow */
  source: {
    background: '#FDE047',
    border: '#CA8A04',
  },
  /** Verified section in Act document - Blue */
  verified: {
    background: '#BFDBFE',
    border: '#3B82F6',
  },
  /** Mismatch in Act document - Red */
  mismatch: {
    background: '#FECACA',
    border: '#EF4444',
  },
  /** Section not found - Orange */
  sectionNotFound: {
    background: '#FED7AA',
    border: '#F97316',
  },
  /** Entity mention highlight - Blue (Story 11.7) */
  entity: {
    background: '#BFDBFE',
    border: '#3B82F6',
  },
  /** Contradiction highlight - Red (Story 11.7) */
  contradiction: {
    background: '#FECACA',
    border: '#EF4444',
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
