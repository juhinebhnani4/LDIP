import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useActDiscovery } from './useActDiscovery';
import * as citationsApi from '@/lib/api/citations';
import type { ActDiscoveryResponse, ActDiscoverySummary, ActResolutionResponse } from '@/types';

// Mock the citations API
vi.mock('@/lib/api/citations', () => ({
  getActDiscoveryReport: vi.fn(),
  markActUploaded: vi.fn(),
  markActSkipped: vi.fn(),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('useActDiscovery', () => {
  const mockMatterId = 'test-matter-123';

  const mockAvailableAct: ActDiscoverySummary = {
    actName: 'Securities Act, 1992',
    actNameNormalized: 'securities_act_1992',
    citationCount: 5,
    resolutionStatus: 'available',
    userAction: 'uploaded',
    actDocumentId: 'doc-123',
  };

  const mockMissingAct: ActDiscoverySummary = {
    actName: 'Negotiable Instruments Act, 1881',
    actNameNormalized: 'negotiable_instruments_act_1881',
    citationCount: 12,
    resolutionStatus: 'missing',
    userAction: 'pending',
    actDocumentId: null,
  };

  const mockSkippedAct: ActDiscoverySummary = {
    actName: 'Companies Act, 2013',
    actNameNormalized: 'companies_act_2013',
    citationCount: 3,
    resolutionStatus: 'skipped',
    userAction: 'skipped',
    actDocumentId: null,
  };

  const mockReport: ActDiscoveryResponse = {
    data: [mockAvailableAct, mockMissingAct, mockSkippedAct],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(citationsApi.getActDiscoveryReport).mockResolvedValue(mockReport);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Fetching', () => {
    it('fetches discovery report on mount when enabled', async () => {
      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(citationsApi.getActDiscoveryReport).toHaveBeenCalledWith(mockMatterId);
      expect(result.current.actReport).toHaveLength(3);
    });

    it('does not fetch when disabled', async () => {
      renderHook(() => useActDiscovery(mockMatterId, false));

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(citationsApi.getActDiscoveryReport).not.toHaveBeenCalled();
    });

    it('sets loading state while fetching', async () => {
      vi.mocked(citationsApi.getActDiscoveryReport).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockReport), 100))
      );

      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error state on fetch failure', async () => {
      vi.mocked(citationsApi.getActDiscoveryReport).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.error).toBeTruthy();
      });

      expect(result.current.error?.message).toBe('Network error');
    });
  });

  describe('Computed Values', () => {
    it('calculates availableCount correctly', async () => {
      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.availableCount).toBe(1);
    });

    it('calculates missingCount correctly', async () => {
      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.missingCount).toBe(1);
    });

    it('calculates skippedCount correctly', async () => {
      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.skippedCount).toBe(1);
    });

    it('calculates totalCitations correctly', async () => {
      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 5 + 12 + 3 = 20
      expect(result.current.totalCitations).toBe(20);
    });
  });

  describe('markUploaded Mutation', () => {
    it('calls API and updates local state optimistically', async () => {
      const mockResponse: ActResolutionResponse = {
        success: true,
        actName: mockMissingAct.actName,
        resolutionStatus: 'available',
      };
      vi.mocked(citationsApi.markActUploaded).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.markUploaded(mockMissingAct.actName, 'new-doc-id');
      });

      expect(citationsApi.markActUploaded).toHaveBeenCalledWith(mockMatterId, {
        actName: mockMissingAct.actName,
        actDocumentId: 'new-doc-id',
      });

      // Check optimistic update
      const updatedAct = result.current.actReport.find(
        (a) => a.actName === mockMissingAct.actName
      );
      expect(updatedAct?.resolutionStatus).toBe('available');
      expect(updatedAct?.userAction).toBe('uploaded');
    });

    it('sets isMutating during mutation', async () => {
      vi.mocked(citationsApi.markActUploaded).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  success: true,
                  actName: mockMissingAct.actName,
                  resolutionStatus: 'available',
                }),
              100
            )
          )
      );

      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let mutationPromise: Promise<unknown>;
      act(() => {
        mutationPromise = result.current.markUploaded(mockMissingAct.actName, 'new-doc-id');
      });

      expect(result.current.isMutating).toBe(true);

      await act(async () => {
        await mutationPromise;
      });

      expect(result.current.isMutating).toBe(false);
    });
  });

  describe('markSkipped Mutation', () => {
    it('calls API and updates local state optimistically', async () => {
      const mockResponse: ActResolutionResponse = {
        success: true,
        actName: mockMissingAct.actName,
        resolutionStatus: 'skipped',
      };
      vi.mocked(citationsApi.markActSkipped).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.markSkipped(mockMissingAct.actName);
      });

      expect(citationsApi.markActSkipped).toHaveBeenCalledWith(mockMatterId, {
        actName: mockMissingAct.actName,
      });

      // Check optimistic update
      const updatedAct = result.current.actReport.find(
        (a) => a.actName === mockMissingAct.actName
      );
      expect(updatedAct?.resolutionStatus).toBe('skipped');
      expect(updatedAct?.userAction).toBe('skipped');
    });
  });

  describe('Refetch', () => {
    it('refetches data when refetch is called', async () => {
      const { result } = renderHook(() => useActDiscovery(mockMatterId, true));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(citationsApi.getActDiscoveryReport).toHaveBeenCalledTimes(1);

      await act(async () => {
        await result.current.refetch();
      });

      expect(citationsApi.getActDiscoveryReport).toHaveBeenCalledTimes(2);
    });
  });
});
