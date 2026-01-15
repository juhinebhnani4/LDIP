/**
 * PDF Split View Store Tests
 *
 * Story 11.5: Implement PDF Viewer Split-View Mode
 * Story 11.6: Implement PDF Viewer Full Modal Mode
 */

import { describe, test, expect, beforeEach } from 'vitest';
import { act } from '@testing-library/react';
import {
  usePdfSplitViewStore,
  selectPdfSplitViewIsOpen,
  selectIsFullScreenOpen,
  selectPdfDocumentUrl,
  selectPdfCurrentPage,
  selectPdfTotalPages,
  selectPdfBboxPageNumber,
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

    test('has isFullScreenOpen false by default (Story 11.6)', () => {
      const state = usePdfSplitViewStore.getState();
      expect(state.isFullScreenOpen).toBe(false);
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

    test('has null bboxPageNumber (Story 11.7)', () => {
      const state = usePdfSplitViewStore.getState();
      expect(state.bboxPageNumber).toBeNull();
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

    test('also closes full screen modal (Story 11.6)', () => {
      // Open split view first
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
      });

      // Open full screen modal
      act(() => {
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      // Close split view
      act(() => {
        usePdfSplitViewStore.getState().closePdfSplitView();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isFullScreenOpen).toBe(false);
    });
  });

  describe('openFullScreenModal (Story 11.6)', () => {
    const mockSource: SourceReference = {
      documentId: 'doc-123',
      documentName: 'Test.pdf',
      page: 5,
    };

    test('sets isFullScreenOpen to true when split view is open', () => {
      // Open split view first
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
      });

      act(() => {
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isFullScreenOpen).toBe(true);
    });

    test('does not open if split view is not open', () => {
      act(() => {
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isFullScreenOpen).toBe(false);
    });

    test('does not open if document URL is null', () => {
      // Manually set state to simulate edge case
      act(() => {
        usePdfSplitViewStore.setState({ isOpen: true, documentUrl: null });
      });

      act(() => {
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isFullScreenOpen).toBe(false);
    });

    test('preserves all other state when opening full screen', () => {
      // Set up split view with modified state
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
        usePdfSplitViewStore.getState().setCurrentPage(10);
        usePdfSplitViewStore.getState().setTotalPages(50);
        usePdfSplitViewStore.getState().setScale(1.5);
      });

      act(() => {
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.currentPage).toBe(10);
      expect(state.totalPages).toBe(50);
      expect(state.scale).toBe(1.5);
      expect(state.documentUrl).toBe('https://example.com/doc.pdf');
      expect(state.documentName).toBe('Test.pdf');
    });
  });

  describe('closeFullScreenModal (Story 11.6)', () => {
    const mockSource: SourceReference = {
      documentId: 'doc-123',
      documentName: 'Test.pdf',
      page: 5,
    };

    test('sets isFullScreenOpen to false', () => {
      // Open both split view and full screen
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      act(() => {
        usePdfSplitViewStore.getState().closeFullScreenModal();
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.isFullScreenOpen).toBe(false);
    });

    test('preserves split view state (returns to split view)', () => {
      // Open both split view and full screen
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
        usePdfSplitViewStore.getState().setCurrentPage(15);
        usePdfSplitViewStore.getState().setScale(2.0);
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      // Close full screen modal
      act(() => {
        usePdfSplitViewStore.getState().closeFullScreenModal();
      });

      const state = usePdfSplitViewStore.getState();
      // Split view should still be open
      expect(state.isOpen).toBe(true);
      expect(state.documentUrl).toBe('https://example.com/doc.pdf');
      expect(state.documentName).toBe('Test.pdf');
      expect(state.currentPage).toBe(15);
      expect(state.scale).toBe(2.0);
    });

    test('state changes in full screen mode are preserved after closing', () => {
      // Open both split view and full screen
      act(() => {
        usePdfSplitViewStore
          .getState()
          .openPdfSplitView(mockSource, 'matter-1', 'https://example.com/doc.pdf');
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      // Make changes while in full screen
      act(() => {
        usePdfSplitViewStore.getState().setCurrentPage(25);
        usePdfSplitViewStore.getState().setScale(1.75);
      });

      // Close full screen
      act(() => {
        usePdfSplitViewStore.getState().closeFullScreenModal();
      });

      const state = usePdfSplitViewStore.getState();
      // Changes should persist
      expect(state.currentPage).toBe(25);
      expect(state.scale).toBe(1.75);
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

    test('sets bboxPageNumber when provided (Story 11.7)', () => {
      const boxes = [{ x: 10, y: 20, width: 100, height: 50 }];

      act(() => {
        usePdfSplitViewStore.getState().setBoundingBoxes(boxes, 5);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.bboxPageNumber).toBe(5);
    });

    test('sets bboxPageNumber to null when not provided (Story 11.7)', () => {
      // First set with page number
      act(() => {
        usePdfSplitViewStore
          .getState()
          .setBoundingBoxes([{ x: 10, y: 20, width: 100, height: 50 }], 3);
      });

      // Then set without page number
      act(() => {
        usePdfSplitViewStore
          .getState()
          .setBoundingBoxes([{ x: 20, y: 30, width: 50, height: 25 }]);
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.bboxPageNumber).toBeNull();
    });
  });

  describe('navigateToDocument (Story 11.7)', () => {
    test('navigates to a different document', () => {
      // First open split view with one document
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'First.pdf', page: 1 },
          'matter-1',
          'https://example.com/first.pdf'
        );
      });

      // Navigate to another document
      act(() => {
        usePdfSplitViewStore.getState().navigateToDocument(
          'doc-2',
          'https://example.com/second.pdf',
          'Second.pdf',
          10
        );
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.documentId).toBe('doc-2');
      expect(state.documentUrl).toBe('https://example.com/second.pdf');
      expect(state.documentName).toBe('Second.pdf');
      expect(state.currentPage).toBe(10);
      expect(state.initialPage).toBe(10);
    });

    test('defaults to page 1 when page not provided', () => {
      act(() => {
        usePdfSplitViewStore.getState().navigateToDocument(
          'doc-1',
          'https://example.com/doc.pdf',
          'Document.pdf'
        );
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.currentPage).toBe(1);
      expect(state.initialPage).toBe(1);
    });

    test('sets bounding boxes and page number when provided', () => {
      const boxes = [{ x: 0.1, y: 0.2, width: 0.5, height: 0.1 }];

      act(() => {
        usePdfSplitViewStore.getState().navigateToDocument(
          'doc-1',
          'https://example.com/doc.pdf',
          'Document.pdf',
          5,
          boxes,
          5
        );
      });

      const state = usePdfSplitViewStore.getState();
      expect(state.boundingBoxes).toEqual(boxes);
      expect(state.bboxPageNumber).toBe(5);
    });

    test('clears chunkId when navigating to new document', () => {
      // First open with chunkId
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'First.pdf', chunkId: 'chunk-123' },
          'matter-1',
          'https://example.com/first.pdf'
        );
      });

      expect(usePdfSplitViewStore.getState().chunkId).toBe('chunk-123');

      // Navigate to new document
      act(() => {
        usePdfSplitViewStore.getState().navigateToDocument(
          'doc-2',
          'https://example.com/second.pdf',
          'Second.pdf'
        );
      });

      expect(usePdfSplitViewStore.getState().chunkId).toBeNull();
    });

    test('resets totalPages when navigating (needs PDF reload)', () => {
      // First open and set total pages
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'First.pdf' },
          'matter-1',
          'https://example.com/first.pdf'
        );
        usePdfSplitViewStore.getState().setTotalPages(50);
      });

      expect(usePdfSplitViewStore.getState().totalPages).toBe(50);

      // Navigate to new document
      act(() => {
        usePdfSplitViewStore.getState().navigateToDocument(
          'doc-2',
          'https://example.com/second.pdf',
          'Second.pdf'
        );
      });

      expect(usePdfSplitViewStore.getState().totalPages).toBe(0);
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

    test('selectIsFullScreenOpen returns isFullScreenOpen state (Story 11.6)', () => {
      expect(selectIsFullScreenOpen(usePdfSplitViewStore.getState())).toBe(false);

      // Open split view first
      act(() => {
        usePdfSplitViewStore.getState().openPdfSplitView(
          { documentId: 'doc-1', documentName: 'Test.pdf' },
          'matter-1',
          'https://example.com/doc.pdf'
        );
      });

      expect(selectIsFullScreenOpen(usePdfSplitViewStore.getState())).toBe(false);

      // Open full screen
      act(() => {
        usePdfSplitViewStore.getState().openFullScreenModal();
      });

      expect(selectIsFullScreenOpen(usePdfSplitViewStore.getState())).toBe(true);
    });

    test('selectPdfBboxPageNumber returns bboxPageNumber state (Story 11.7)', () => {
      expect(selectPdfBboxPageNumber(usePdfSplitViewStore.getState())).toBeNull();

      act(() => {
        usePdfSplitViewStore
          .getState()
          .setBoundingBoxes([{ x: 10, y: 20, width: 100, height: 50 }], 7);
      });

      expect(selectPdfBboxPageNumber(usePdfSplitViewStore.getState())).toBe(7);
    });
  });
});
