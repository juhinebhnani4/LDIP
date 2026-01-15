import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useDocuments } from './useDocuments';
import type { DocumentListItem, DocumentListResponse } from '@/types/document';

// Mock the API module
vi.mock('@/lib/api/documents', () => ({
  fetchDocuments: vi.fn(),
}));

// Import mocked function for manipulation
import { fetchDocuments } from '@/lib/api/documents';

const mockDocuments: DocumentListItem[] = [
  {
    id: 'doc-1',
    matterId: 'matter-123',
    filename: 'petition.pdf',
    fileSize: 102400,
    pageCount: 25,
    documentType: 'case_file',
    isReferenceMaterial: false,
    status: 'completed',
    uploadedAt: '2024-01-15T10:00:00Z',
    uploadedBy: 'user-1',
    ocrConfidence: 0.92,
    ocrQualityStatus: 'good',
  },
  {
    id: 'doc-2',
    matterId: 'matter-123',
    filename: 'contract_act.pdf',
    fileSize: 204800,
    pageCount: 120,
    documentType: 'act',
    isReferenceMaterial: true,
    status: 'processing',
    uploadedAt: '2024-01-14T10:00:00Z',
    uploadedBy: 'user-1',
    ocrConfidence: null,
    ocrQualityStatus: null,
  },
];

const mockResponse: DocumentListResponse = {
  data: mockDocuments,
  meta: {
    total: 2,
    page: 1,
    perPage: 100,
    totalPages: 1,
  },
};

describe('useDocuments', () => {
  const matterId = 'matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
    (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);
  });

  describe('Initial Loading', () => {
    it('starts in loading state', () => {
      // Make fetch hang
      (fetchDocuments as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDocuments(matterId));

      expect(result.current.isLoading).toBe(true);
      expect(result.current.documents).toEqual([]);
    });

    it('fetches documents on mount', async () => {
      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(fetchDocuments).toHaveBeenCalledWith(matterId, expect.any(Object));
      expect(result.current.documents).toEqual(mockDocuments);
    });
  });

  describe('Successful Load', () => {
    it('returns documents after successful fetch', async () => {
      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.documents).toEqual(mockDocuments);
      expect(result.current.totalCount).toBe(2);
      expect(result.current.error).toBeNull();
    });

    it('detects processing documents', async () => {
      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // One document has status 'processing'
      expect(result.current.hasProcessing).toBe(true);
    });

    it('returns hasProcessing false when no processing documents', async () => {
      const completedDocs = mockDocuments.map((d) => ({
        ...d,
        status: 'completed' as const,
      }));
      (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: completedDocs,
        meta: mockResponse.meta,
      });

      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasProcessing).toBe(false);
    });
  });

  describe('Error Handling', () => {
    it('handles fetch error', async () => {
      (fetchDocuments as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Network error');
      expect(result.current.documents).toEqual([]);
    });

    it('handles non-Error exceptions', async () => {
      (fetchDocuments as ReturnType<typeof vi.fn>).mockRejectedValue('Unknown error');

      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Failed to load documents');
    });
  });

  describe('Refresh', () => {
    it('provides refresh function', async () => {
      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refresh).toBe('function');
    });

    it('refresh refetches documents', async () => {
      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Clear calls
      vi.clearAllMocks();

      // Call refresh
      await act(async () => {
        await result.current.refresh();
      });

      expect(fetchDocuments).toHaveBeenCalled();
    });
  });

  describe('Options', () => {
    it('uses default options', async () => {
      const { result } = renderHook(() => useDocuments(matterId));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(fetchDocuments).toHaveBeenCalledWith(matterId, {
        page: 1,
        perPage: 100,
        filters: {},
        sort: { column: 'uploaded_at', order: 'desc' },
      });
    });

    it('accepts custom options', async () => {
      const { result } = renderHook(() =>
        useDocuments(matterId, {
          page: 2,
          perPage: 50,
          filters: { documentType: 'act' },
          sort: { column: 'filename', order: 'asc' },
        })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(fetchDocuments).toHaveBeenCalledWith(matterId, {
        page: 2,
        perPage: 50,
        filters: { documentType: 'act' },
        sort: { column: 'filename', order: 'asc' },
      });
    });
  });

  describe('Polling', () => {
    it('detects processing documents', async () => {
      const { result } = renderHook(() => useDocuments(matterId));

      // Wait for initial load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should detect processing documents (one doc has status 'processing')
      expect(result.current.hasProcessing).toBe(true);
    });

    it('has no processing documents when all are completed', async () => {
      const completedDocs = mockDocuments.map((d) => ({
        ...d,
        status: 'completed' as const,
      }));
      (fetchDocuments as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: completedDocs,
        meta: mockResponse.meta,
      });

      const { result } = renderHook(() => useDocuments(matterId));

      // Wait for initial load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should NOT detect processing documents
      expect(result.current.hasProcessing).toBe(false);
    });

    it('respects enablePolling option', async () => {
      // Verify the option is accepted without error
      const { result } = renderHook(() =>
        useDocuments(matterId, { enablePolling: false })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Hook should work with polling disabled
      expect(result.current.documents).toEqual(mockDocuments);
    });
  });
});
