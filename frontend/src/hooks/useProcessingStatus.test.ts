/**
 * useProcessingStatus Hook Tests
 *
 * Tests for the processing status polling hook.
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useProcessingStatus } from './useProcessingStatus';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  api: {
    get: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public code: string,
      message: string,
      public status: number
    ) {
      super(message);
    }
  },
}));

// Mock stage-mapping module
vi.mock('@/lib/utils/stage-mapping', () => ({
  mapBackendStageToUI: vi.fn((stage: string | null) => {
    if (!stage) return 'UPLOADING';
    const map: Record<string, string> = {
      ocr: 'OCR',
      entity_extraction: 'ENTITY_EXTRACTION',
      chunking: 'ANALYSIS',
      indexing: 'INDEXING',
      completed: 'INDEXING',
    };
    return map[stage.toLowerCase()] || 'UPLOADING';
  }),
  determineOverallStage: vi.fn((stages: (string | null)[]) => {
    const filtered = stages.filter((s): s is string => s !== null);
    if (filtered.length === 0) return 'UPLOADING';
    if (filtered.includes('indexing') || filtered.includes('completed')) return 'INDEXING';
    if (filtered.includes('chunking')) return 'ANALYSIS';
    if (filtered.includes('entity_extraction')) return 'ENTITY_EXTRACTION';
    if (filtered.includes('ocr')) return 'OCR';
    return 'UPLOADING';
  }),
  isTerminalStatus: vi.fn((status: string | null) => {
    if (!status) return false;
    return ['COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED'].includes(status.toUpperCase());
  }),
  isActiveStatus: vi.fn((status: string | null) => {
    if (!status) return false;
    return ['QUEUED', 'PROCESSING'].includes(status.toUpperCase());
  }),
}));

import { api } from '@/lib/api/client';

describe('useProcessingStatus', () => {
  const mockJobsResponse = {
    jobs: [
      {
        id: 'job-1',
        matter_id: 'matter-123',
        document_id: 'doc-1',
        status: 'PROCESSING',
        job_type: 'DOCUMENT_PROCESSING',
        current_stage: 'ocr',
        progress_pct: 50,
        error_message: null,
        created_at: '2024-01-01T00:00:00Z',
        started_at: '2024-01-01T00:01:00Z',
        completed_at: null,
      },
    ],
    total: 1,
    limit: 200,
    offset: 0,
  };

  const mockStatsResponse = {
    matter_id: 'matter-123',
    queued: 0,
    processing: 1,
    completed: 0,
    failed: 0,
    cancelled: 0,
    skipped: 0,
    avg_processing_time_ms: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(api.get).mockImplementation((endpoint: string) => {
      if (endpoint.includes('/stats')) {
        return Promise.resolve(mockStatsResponse);
      }
      return Promise.resolve(mockJobsResponse);
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial state when matterId is null', () => {
    const { result } = renderHook(() => useProcessingStatus(null));

    expect(result.current.jobs).toEqual([]);
    expect(result.current.overallProgress).toBe(0);
    expect(result.current.currentStage).toBe('UPLOADING');
    expect(result.current.isComplete).toBe(false);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('fetches jobs and stats when matterId is provided', async () => {
    renderHook(() => useProcessingStatus('matter-123', { enabled: true }));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/jobs/matters/matter-123?limit=200');
      expect(api.get).toHaveBeenCalledWith('/api/jobs/matters/matter-123/stats');
    });
  });

  it('normalizes job data from snake_case to camelCase', async () => {
    const { result } = renderHook(() =>
      useProcessingStatus('matter-123', { enabled: true })
    );

    await waitFor(() => {
      expect(result.current.jobs.length).toBe(1);
    });

    expect(result.current.jobs[0]).toEqual({
      id: 'job-1',
      matterId: 'matter-123',
      documentId: 'doc-1',
      status: 'PROCESSING',
      jobType: 'DOCUMENT_PROCESSING',
      currentStage: 'ocr',
      progressPct: 50,
      errorMessage: null,
      createdAt: '2024-01-01T00:00:00Z',
      startedAt: '2024-01-01T00:01:00Z',
      completedAt: null,
    });
  });

  it('calculates stats correctly', async () => {
    const { result } = renderHook(() =>
      useProcessingStatus('matter-123', { enabled: true })
    );

    await waitFor(() => {
      expect(result.current.stats.total).toBe(1);
    });

    expect(result.current.stats).toEqual({
      queued: 0,
      processing: 1,
      completed: 0,
      failed: 0,
      total: 1,
    });
  });

  it('calculates overall progress from completion counts', async () => {
    vi.mocked(api.get).mockImplementation((endpoint: string) => {
      if (endpoint.includes('/stats')) {
        return Promise.resolve({
          ...mockStatsResponse,
          queued: 0,
          processing: 0,
          completed: 3,
          failed: 1,
        });
      }
      return Promise.resolve({ ...mockJobsResponse, jobs: [] });
    });

    const { result } = renderHook(() =>
      useProcessingStatus('matter-123', { enabled: true })
    );

    await waitFor(() => {
      // 4 total jobs, 4 done (3 completed + 1 failed) = 100%
      expect(result.current.overallProgress).toBe(100);
    });
  });

  it('detects completion when no QUEUED or PROCESSING jobs', async () => {
    vi.mocked(api.get).mockImplementation((endpoint: string) => {
      if (endpoint.includes('/stats')) {
        return Promise.resolve({
          ...mockStatsResponse,
          queued: 0,
          processing: 0,
          completed: 2,
          failed: 0,
        });
      }
      return Promise.resolve({
        ...mockJobsResponse,
        jobs: mockJobsResponse.jobs.map((j) => ({
          ...j,
          status: 'COMPLETED',
          current_stage: 'completed',
        })),
      });
    });

    const { result } = renderHook(() =>
      useProcessingStatus('matter-123', { enabled: true })
    );

    await waitFor(() => {
      expect(result.current.isComplete).toBe(true);
    });
  });

  it('detects failed jobs', async () => {
    vi.mocked(api.get).mockImplementation((endpoint: string) => {
      if (endpoint.includes('/stats')) {
        return Promise.resolve({
          ...mockStatsResponse,
          queued: 0,
          processing: 0,
          completed: 1,
          failed: 1,
        });
      }
      return Promise.resolve({ ...mockJobsResponse, jobs: [] });
    });

    const { result } = renderHook(() =>
      useProcessingStatus('matter-123', { enabled: true })
    );

    await waitFor(() => {
      expect(result.current.hasFailed).toBe(true);
    });
  });

  it('handles API errors gracefully', async () => {
    const errorMessage = 'Network error';
    vi.mocked(api.get).mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() =>
      useProcessingStatus('matter-123', { enabled: true })
    );

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    expect(result.current.error?.message).toBe(errorMessage);
  });

  it('does not poll when disabled', async () => {
    renderHook(() => useProcessingStatus('matter-123', { enabled: false }));

    // Wait a tick to ensure hook is settled
    await new Promise((r) => setTimeout(r, 50));

    expect(api.get).not.toHaveBeenCalled();
  });

  it('provides refresh function to manually fetch data', async () => {
    const { result } = renderHook(() =>
      useProcessingStatus('matter-123', { enabled: true })
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalled();
    });

    const initialCallCount = vi.mocked(api.get).mock.calls.length;

    await act(async () => {
      await result.current.refresh();
    });

    expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThan(initialCallCount);
  });
});
