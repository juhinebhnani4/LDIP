/**
 * useContradictions Hook Tests
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 10: Write tests for useContradictions hook
 */

import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useContradictions } from './useContradictions';
import useSWR from 'swr';

// Mock SWR
vi.mock('swr');

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}));

describe('useContradictions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns empty data when matterId is null', () => {
    (useSWR as Mock).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useContradictions(null));

    expect(result.current.data).toEqual([]);
    expect(result.current.meta).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('returns loading state when fetching', () => {
    (useSWR as Mock).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
      isValidating: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useContradictions('matter-123'));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toEqual([]);
  });

  it('returns error state when fetch fails', () => {
    const mockError = new Error('Failed to fetch');
    (useSWR as Mock).mockReturnValue({
      data: undefined,
      error: mockError,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useContradictions('matter-123'));

    expect(result.current.error).toBe(mockError);
    expect(result.current.data).toEqual([]);
  });

  it('returns data when fetch succeeds', () => {
    const mockData = {
      data: [
        {
          entityId: 'entity-1',
          entityName: 'John Smith',
          contradictions: [
            {
              id: 'contradiction-1',
              contradictionType: 'semantic_contradiction',
              severity: 'high',
              entityId: 'entity-1',
              entityName: 'John Smith',
              statementA: {
                documentId: 'doc-1',
                documentName: 'Doc A.pdf',
                page: 5,
                excerpt: 'Statement A text',
                date: '2024-01-15',
              },
              statementB: {
                documentId: 'doc-2',
                documentName: 'Doc B.pdf',
                page: 10,
                excerpt: 'Statement B text',
                date: '2024-02-20',
              },
              explanation: 'These contradict each other',
              evidenceLinks: [],
              confidence: 0.85,
              createdAt: '2024-03-01T10:00:00Z',
            },
          ],
          count: 1,
        },
      ],
      meta: {
        total: 1,
        page: 1,
        perPage: 20,
        totalPages: 1,
      },
    };

    (useSWR as Mock).mockReturnValue({
      data: mockData,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useContradictions('matter-123'));

    expect(result.current.data).toEqual(mockData.data);
    expect(result.current.meta).toEqual(mockData.meta);
    expect(result.current.totalCount).toBe(1);
  });

  it('builds correct URL with filter parameters', () => {
    (useSWR as Mock).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    renderHook(() =>
      useContradictions('matter-123', {
        severity: 'high',
        contradictionType: 'semantic_contradiction',
        entityId: 'entity-1',
        page: 2,
        perPage: 10,
      })
    );

    // Check that useSWR was called with the correct URL
    const swrCall = (useSWR as Mock).mock.calls[0];
    const url = swrCall[0] as string;

    expect(url).toContain('/api/matters/matter-123/contradictions');
    expect(url).toContain('severity=high');
    expect(url).toContain('contradiction_type=semantic_contradiction');
    expect(url).toContain('entity_id=entity-1');
    expect(url).toContain('page=2');
    expect(url).toContain('per_page=10');
  });

  it('returns null key when disabled', () => {
    (useSWR as Mock).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    renderHook(() =>
      useContradictions('matter-123', {
        enabled: false,
      })
    );

    const swrCall = (useSWR as Mock).mock.calls[0];
    expect(swrCall[0]).toBeNull();
  });

  it('extracts unique entities from data', () => {
    const mockData = {
      data: [
        { entityId: 'entity-1', entityName: 'John Smith', contradictions: [], count: 2 },
        { entityId: 'entity-2', entityName: 'Acme Corp', contradictions: [], count: 1 },
      ],
      meta: { total: 3, page: 1, perPage: 20, totalPages: 1 },
    };

    (useSWR as Mock).mockReturnValue({
      data: mockData,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useContradictions('matter-123'));

    expect(result.current.uniqueEntities).toEqual([
      { id: 'entity-1', name: 'John Smith' },
      { id: 'entity-2', name: 'Acme Corp' },
    ]);
  });

  it('calculates totalCount from groups', () => {
    const mockData = {
      data: [
        { entityId: 'entity-1', entityName: 'John Smith', contradictions: [], count: 5 },
        { entityId: 'entity-2', entityName: 'Acme Corp', contradictions: [], count: 3 },
      ],
      meta: { total: 8, page: 1, perPage: 20, totalPages: 1 },
    };

    (useSWR as Mock).mockReturnValue({
      data: mockData,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useContradictions('matter-123'));

    expect(result.current.totalCount).toBe(8);
  });

  it('provides mutate function for revalidation', () => {
    const mockMutate = vi.fn();
    (useSWR as Mock).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: mockMutate,
    });

    const { result } = renderHook(() => useContradictions('matter-123'));

    expect(result.current.mutate).toBe(mockMutate);
  });

  it('uses correct SWR options', () => {
    (useSWR as Mock).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: vi.fn(),
    });

    renderHook(() => useContradictions('matter-123'));

    const swrCall = (useSWR as Mock).mock.calls[0];
    const options = swrCall[2];

    expect(options.revalidateOnFocus).toBe(false);
    expect(options.dedupingInterval).toBe(30000);
  });
});
