/**
 * PDF Split View Store
 *
 * Zustand store for managing PDF split-view state when viewing source documents
 * from Q&A responses, citations, or other source references.
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode
 * Story 11.6: Implement PDF Viewer Full Modal Mode
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const isOpen = usePdfSplitViewStore(selectPdfSplitViewIsOpen);
 *   const openPdfSplitView = usePdfSplitViewStore((state) => state.openPdfSplitView);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { isOpen, openPdfSplitView } = usePdfSplitViewStore();
 */

import { create } from 'zustand';
import type { SourceReference } from '@/types/chat';

// =============================================================================
// Store Types
// =============================================================================

interface PdfSplitViewState {
  /** Whether the split view panel is open */
  isOpen: boolean;

  /** Whether the full screen modal is open (Story 11.6) */
  isFullScreenOpen: boolean;

  /** URL of the document to display */
  documentUrl: string | null;

  /** Display name of the document */
  documentName: string | null;

  /** Matter ID for context */
  matterId: string | null;

  /** Document ID for reference */
  documentId: string | null;

  /** Initial page to navigate to when opening */
  initialPage: number;

  /** Current page being viewed */
  currentPage: number;

  /** Total number of pages in the document */
  totalPages: number;

  /** Current zoom scale */
  scale: number;

  /** Bounding boxes for highlighting (if available) */
  boundingBoxes: Array<{ x: number; y: number; width: number; height: number }>;

  /** Page number the bounding boxes belong to (Story 11.7) */
  bboxPageNumber: number | null;

  /** Chunk ID for potential bbox lookup */
  chunkId: string | null;
}

interface PdfSplitViewActions {
  /** Open the PDF split view with a source reference */
  openPdfSplitView: (
    source: SourceReference,
    matterId: string,
    documentUrl: string
  ) => void;

  /** Close the PDF split view */
  closePdfSplitView: () => void;

  /** Open the full screen modal (Story 11.6) */
  openFullScreenModal: () => void;

  /** Close the full screen modal, preserving split view state (Story 11.6) */
  closeFullScreenModal: () => void;

  /** Set the current page */
  setCurrentPage: (page: number) => void;

  /** Set the total number of pages */
  setTotalPages: (totalPages: number) => void;

  /** Set the zoom scale */
  setScale: (scale: number) => void;

  /** Set bounding boxes for highlighting */
  setBoundingBoxes: (
    boxes: Array<{ x: number; y: number; width: number; height: number }>,
    pageNumber?: number | null
  ) => void;

  /**
   * Navigate to a different document with optional page and bboxes (Story 11.7).
   * Used for cross-reference navigation (AC: #3).
   */
  navigateToDocument: (
    documentId: string,
    documentUrl: string,
    documentName: string,
    page?: number,
    boundingBoxes?: Array<{ x: number; y: number; width: number; height: number }>,
    bboxPageNumber?: number | null
  ) => void;

  /** Reset all state */
  reset: () => void;
}

type PdfSplitViewStore = PdfSplitViewState & PdfSplitViewActions;

// =============================================================================
// Initial State
// =============================================================================

const initialState: PdfSplitViewState = {
  isOpen: false,
  isFullScreenOpen: false,
  documentUrl: null,
  documentName: null,
  matterId: null,
  documentId: null,
  initialPage: 1,
  currentPage: 1,
  totalPages: 0,
  scale: 1.0,
  boundingBoxes: [],
  bboxPageNumber: null,
  chunkId: null,
};

// =============================================================================
// Store Implementation
// =============================================================================

export const usePdfSplitViewStore = create<PdfSplitViewStore>()((set) => ({
  // Initial state
  ...initialState,

  // Actions
  openPdfSplitView: (
    source: SourceReference,
    matterId: string,
    documentUrl: string
  ) => {
    const page = source.page ?? 1;
    set({
      isOpen: true,
      documentUrl,
      documentName: source.documentName,
      matterId,
      documentId: source.documentId,
      initialPage: page,
      currentPage: page,
      totalPages: 0, // Will be set when PDF loads
      chunkId: source.chunkId ?? null,
      // NOTE: Bounding boxes are populated via setBoundingBoxes() after opening.
      // Story 11.7 wires the bbox fetching in WorkspaceContentArea.handleSourceClick().
      boundingBoxes: [],
      bboxPageNumber: null,
      scale: 1.0,
    });
  },

  closePdfSplitView: () => {
    set({
      isOpen: false,
      isFullScreenOpen: false,
      documentUrl: null,
      documentName: null,
      matterId: null,
      documentId: null,
      initialPage: 1,
      currentPage: 1,
      totalPages: 0,
      boundingBoxes: [],
      bboxPageNumber: null,
      chunkId: null,
      scale: 1.0,
    });
  },

  openFullScreenModal: () => {
    // Only open full screen if split view is already open with a document
    set((state) => ({
      isFullScreenOpen: state.isOpen && state.documentUrl !== null,
    }));
  },

  closeFullScreenModal: () => {
    // Close full screen but preserve split view state (returns to split view)
    set({ isFullScreenOpen: false });
  },

  setCurrentPage: (page: number) => {
    set({ currentPage: page });
  },

  setTotalPages: (totalPages: number) => {
    set({ totalPages });
  },

  setScale: (scale: number) => {
    set({ scale });
  },

  setBoundingBoxes: (
    boxes: Array<{ x: number; y: number; width: number; height: number }>,
    pageNumber?: number | null
  ) => {
    set({ boundingBoxes: boxes, bboxPageNumber: pageNumber ?? null });
  },

  navigateToDocument: (
    documentId: string,
    documentUrl: string,
    documentName: string,
    page?: number,
    boundingBoxes?: Array<{ x: number; y: number; width: number; height: number }>,
    bboxPageNumber?: number | null
  ) => {
    const targetPage = page ?? 1;
    set({
      documentId,
      documentUrl,
      documentName,
      initialPage: targetPage,
      currentPage: targetPage,
      totalPages: 0, // Will be set when new PDF loads
      boundingBoxes: boundingBoxes ?? [],
      bboxPageNumber: bboxPageNumber ?? null,
      chunkId: null, // Clear chunkId when navigating to different doc
    });
  },

  reset: () => {
    set(initialState);
  },
}));

// =============================================================================
// Selectors (for optimized re-renders)
// =============================================================================

/** Select whether PDF split view is open */
export const selectPdfSplitViewIsOpen = (state: PdfSplitViewStore) =>
  state.isOpen;

/** Select whether full screen modal is open (Story 11.6) */
export const selectIsFullScreenOpen = (state: PdfSplitViewStore) =>
  state.isFullScreenOpen;

/** Select document URL */
export const selectPdfDocumentUrl = (state: PdfSplitViewStore) =>
  state.documentUrl;

/** Select document name */
export const selectPdfDocumentName = (state: PdfSplitViewStore) =>
  state.documentName;

/** Select current page */
export const selectPdfCurrentPage = (state: PdfSplitViewStore) =>
  state.currentPage;

/** Select total pages */
export const selectPdfTotalPages = (state: PdfSplitViewStore) =>
  state.totalPages;

/** Select initial page */
export const selectPdfInitialPage = (state: PdfSplitViewStore) =>
  state.initialPage;

/** Select scale */
export const selectPdfScale = (state: PdfSplitViewStore) => state.scale;

/** Select bounding boxes */
export const selectPdfBoundingBoxes = (state: PdfSplitViewStore) =>
  state.boundingBoxes;

/** Select matter ID */
export const selectPdfMatterId = (state: PdfSplitViewStore) => state.matterId;

/** Select document ID */
export const selectPdfDocumentId = (state: PdfSplitViewStore) =>
  state.documentId;

/** Select chunk ID for bbox lookup */
export const selectPdfChunkId = (state: PdfSplitViewStore) => state.chunkId;

/** Select bounding box page number (Story 11.7) */
export const selectPdfBboxPageNumber = (state: PdfSplitViewStore) =>
  state.bboxPageNumber;
