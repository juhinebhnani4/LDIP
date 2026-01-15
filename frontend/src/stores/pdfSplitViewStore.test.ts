/**
 * PDF Split View Store Tests
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode
 */

import { describe, test, expect, beforeEach } from 'vitest';
import { act } from '@testing-library/react';
import {
  usePdfSplitViewStore,
  selectPdfSplitViewIsOpen,
  selectPdfDocumentUrl,
  selectPdfCurrentPage,
  selectPdfTotalPages,
} from './pdfSplitViewStore';
import type { SourceReference } from '@/types/chat';

// Reset store state before each test
beforeEach(() => {
  act(() => {
    usePdfSplitViewStore.getState().reset();
  });
});

describe('pdfSplitViewStore', () => {
  describe('initial state', () => {
    test('has isOpen false by default', () => {
      const state = usePdfSplitViewStore.getState();
      expect(state.isOpen).toBe(false);
    });

    test('has null document values by default', () => {
      const state = usePdfSplitViewStore.getState();
      expect(state.documentUrl).toBeNull();
      expect(state.documentName).toBeNull();
      expect(state.documentId).toBeNull();
      expect(state.matterId).toBeNull();
    });

    test('has default page and scale values', () => {
      const state = usePdfSplitViewStore.getState();
      expect(state.initialPage).toBe(1);
      expect(state.currentPage).toBe(1);
      expect(state.totalPages).toBe(0);
      expect(state.scale).toBe(1.0);
    });

    test('has empty bounding boxes array', () => {
      const state = usePdfSplitViewStore.getState();
      expect(state.boundingBoxes).toEqual([]);
    });
  });

  describe('openPdfSplitView', () => {
    const mockSource: SourceReference = {
      documentId: 'doc-123',
      documentName: 'Test Document.pdf',
      page: 5,
      chunkId: 'chunk-456',
      confidence: 85,
    };
    const mockMatterId = 'matter-789';
    const mockDocumentUrl = 'https://example.com/documents/doc-123.pdf';

    test('sets isOpen to true', () => {
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isOpen).toBe(true);
    });

    test('sets document URL correctly', () => {
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.documentUrl).toBe(mockDocumentUrl);
    });

    test('sets document name from source', () => {
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.documentName).toBe('Test Document.pdf');
    });

    test('sets document ID from source', () => {
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.documentId).toBe('doc-123');
    });

    test('sets matter ID', () => {
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.matterId).toBe('matter-789');
    });

    test('sets initial page from source', () => {
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.initialPage).toBe(5);
      expect(state.currentPage).toBe(5);
    });

    test('sets chunk ID from source', () => {
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.chunkId).toBe('chunk-456');
    });

    test('defaults to page 1 when source has no page', () => {
      const sourceWithoutPage: SourceReference = {
        documentId: 'doc-123',
        documentName: 'Test.pdf',
      };

      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(sourceWithoutPage, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.initialPage).toBe(1);
      expect(state.currentPage).toBe(1);
    });

    test('sets chunkId to null when source has no chunkId', () => {
      const sourceWithoutChunk: SourceReference = {
        documentId: 'doc-123',
        documentName: 'Test.pdf',
      };

      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(sourceWithoutChunk, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.chunkId).toBeNull();
    });

    test('resets bounding boxes when opening', () => {
      // First set some bounding boxes
      act(() => {
        usePdfSplitViewStore
          .getState()
          .setBoundingBoxes([{ x: 10, y: 20, width: 100, height: 50 }]);
      });

      // Then open with new source
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.boundingBoxes).toEqual([]);
    });

    test('resets scale to 1.0 when opening', () => {
      // First change scale
      act(() => {
        usePdfSplitViewStore.getState().setScale(1.5);
      });

      // Then open with new source
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, mockMatterId, mockDocumentUrl);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.scale).toBe(1.0);
    });
  });

  describe('closePdfSplitView', () => {
    const mockSource: SourceReference = {
      documentId: 'doc-123',
      documentName: 'Test.pdf',
      page: 5,
    };

    beforeEach(() => {
      // Open split view first
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
      });
    });

    test('sets isOpen to false', () => {
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isOpen).toBe(false);
    });

    test('resets document URL to null', () => {
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.documentUrl).toBeNull();
    });

    test('resets document name to null', () => {
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.documentName).toBeNull();
    });

    test('resets document ID to null', () => {
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.documentId).toBeNull();
    });

    test('resets matter ID to null', () => {
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.matterId).toBeNull();
    });

    test('resets pages to 1', () => {
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.initialPage).toBe(1);
      expect(state.currentPage).toBe(1);
    });

    test('resets scale to 1.0', () => {
      // Change scale first
      act(() => {
        usePdfSplitViewStore.getState().setScale(2.0);
      });

      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.scale).toBe(1.0);
    });

    test('clears bounding boxes', () => {
      // Set bounding boxes first
      act(() => {
        usePdfSplitViewStore
          .getState()
          .setBoundingBoxes([{ x: 10, y: 20, width: 100, height: 50 }]);
      });

      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.boundingBoxes).toEqual([]);
    });
  });

  describe('setCurrentPage', () => {
    test('updates current page', () => {
      act(() => {
        usePdfSplitViewStore.getState().setCurrentPage(10);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.currentPage).toBe(10);
    });

    test('does not affect initial page', () => {
      const mockSource: SourceReference = {
        documentId: 'doc-1',
        documentName: 'Test.pdf',
        page: 5,
      };

      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
      });

      act(() => {
        usePdfSplitViewStore.getState().setCurrentPage(10);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.initialPage).toBe(5);
      expect(state.currentPage).toBe(10);
    });
  });

  describe('setTotalPages', () => {
    test('updates totalPages value', () => {
      act(() => {
        usePdfSplitViewStore.getState().setTotalPages(25);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.totalPages).toBe(25);
    });
  });

  describe('setScale', () => {
    test('updates scale value', () => {
      act(() => {
        usePdfSplitViewStore.getState().setScale(1.5);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.scale).toBe(1.5);
    });
  });

  describe('setBoundingBoxes', () => {
    test('sets bounding boxes array', () => {
      const boxes = [
        { x: 10, y: 20, width: 100, height: 50 },
        { x: 200, y: 300, width: 150, height: 75 },
      ];

      act(() => {
        usePdfSplitViewStore.getState().setBoundingBoxes(boxes);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.boundingBoxes).toEqual(boxes);
    });

    test('can set empty array', () => {
      // First set some boxes
      act(() => {
        usePdfSplitViewStore
          .getState()
          .setBoundingBoxes([{ x: 10, y: 20, width: 100, height: 50 }]);
      });

      // Then clear them
      act(() => {
        usePdfSplitViewStore.getState().setBoundingBoxes([]);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.boundingBoxes).toEqual([]);
    });
  });

  describe('reset', () => {
    test('resets all state to initial values', () => {
      const mockSource: SourceReference = {
        documentId: 'doc-123',
        documentName: 'Test.pdf',
        page: 5,
        chunkId: 'chunk-1',
      };

      // Set various state values
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
        usePdfSplitViewStore.getState().setCurrentPage(10);
        usePdfSplitViewStore.getState().setScale(2.0);
        usePdfSplitViewStore
          .getState()
          .setBoundingBoxes([{ x: 10, y: 20, width: 100, height: 50 }]);
      });

      // Reset
      act(() => {
        usePdfSplitViewStore.getState().reset();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isOpen).toBe(false);
      expect(state.documentUrl).toBeNull();
      expect(state.documentName).toBeNull();
      expect(state.documentId).toBeNull();
      expect(state.matterId).toBeNull();
      expect(state.initialPage).toBe(1);
      expect(state.currentPage).toBe(1);
      expect(state.scale).toBe(1.0);
      expect(state.boundingBoxes).toEqual([]);
      expect(state.chunkId).toBeNull();
    });
  });

  describe('selectors', () => {
    test('selectPdfSplitViewIsOpen returns isOpen state', () => {
      expect(selectPdfSplitViewIsOpen(usePdfSplitViewStore.getState())).toBe(false);

      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf' },
          'matter-1',
          'https://example.com/doc.pdf'
        );
      });

      expect(selectPdfSplitViewIsOpen(usePdfSplitViewStore.getState())).toBe(true);
    });

    test('selectPdfDocumentUrl returns documentUrl state', () => {
      expect(selectPdfDocumentUrl(usePdfSplitViewStore.getState())).toBeNull();

      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf' },
          'matter-1',
          'https://example.com/doc.pdf'
        );
      });

      expect(selectPdfDocumentUrl(usePdfSplitViewStore.getState())).toBe(
        'https://example.com/doc.pdf'
      );
    });

    test('selectPdfCurrentPage returns currentPage state', () => {
      expect(selectPdfCurrentPage(usePdfSplitViewStore.getState())).toBe(1);

      act(() => {
        usePdfSplitViewStore.getState().setCurrentPage(7);
      });

      expect(selectPdfCurrentPage(usePdfSplitViewStore.getState())).toBe(7);
    });

    test('selectPdfTotalPages returns totalPages state', () => {
      expect(selectPdfTotalPages(usePdfSplitViewStore.getState())).toBe(0);

      act(() => {
        usePdfSplitViewStore.getState().setTotalPages(15);
      });

      expect(selectPdfTotalPages(usePdfSplitViewStore.getState())).toBe(15);
    });
  });
});
