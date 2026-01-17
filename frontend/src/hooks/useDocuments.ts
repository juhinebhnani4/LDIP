'use client';

/**
 * Documents Hook
 *
 * SWR-based hook for fetching documents for a matter.
 * Provides loading, error state, and refresh functionality.
 *
 * Story 10D.3: Documents Tab File List
 * Performance Fix: Converted from useState/useEffect to SWR to prevent infinite re-renders
 */

import useSWR from 'swr';
import { fetchDocuments } from '@/lib/api/documents';
import type { DocumentListItem, DocumentFilters, DocumentSort } from '@/types/document';

/**
 * Default polling interval for document list refresh when processing.
 * Set to 10 seconds for responsive updates during processing.
 */
const PROCESSING_POLL_INTERVAL_MS = 10_000;

interface UseDocumentsOptions {
  /** Page number for pagination (default 1) */
  page?: number;
  /** Items per page (default 100 for full list) */
  perPage?: number;
  /** Filter options */
  filters?: DocumentFilters;
  /** Sort options */
  sort?: DocumentSort;
  /** Enable polling when documents are processing (default true) */
  enablePolling?: boolean;
}

interface UseDocumentsReturn {
  /** Document list */
  documents: DocumentListItem[];
  /** Loading state */
  isLoading: boolean;
  /** Error message */
  error: string | null;
  /** Refresh documents manually */
  refresh: () => Promise<void>;
  /** Total document count from pagination */
  totalCount: number;
  /** Whether any documents are currently processing */
  hasProcessing: boolean;
}

/**
 * Build a stable cache key from options.
 * Serializes objects to ensure stable string comparison.
 */
function buildCacheKey(
  matterId: string,
  page: number,
  perPage: number,
  filters?: DocumentFilters,
  sort?: DocumentSort
): string[] {
  return [
    'documents',
    matterId,
    String(page),
    String(perPage),
    filters ? JSON.stringify(filters) : '',
    sort ? `${sort.column}-${sort.order}` : 'uploaded_at-desc',
  ];
}

/**
 * Hook for fetching documents for a matter.
 *
 * Uses SWR for efficient caching and deduplication.
 * Automatically polls when documents are processing.
 *
 * @param matterId - Matter ID
 * @param options - Configuration options
 * @returns Documents state and actions
 *
 * @example
 * ```tsx
 * const { documents, isLoading, error, refresh } = useDocuments(matterId);
 * ```
 */
export function useDocuments(
  matterId: string,
  options: UseDocumentsOptions = {}
): UseDocumentsReturn {
  const {
    page = 1,
    perPage = 100,
    filters,
    sort = { column: 'uploaded_at', order: 'desc' },
    enablePolling = true,
  } = options;

  // Build stable cache key
  const cacheKey = matterId
    ? buildCacheKey(matterId, page, perPage, filters, sort)
    : null;

  const { data, error, isLoading, mutate } = useSWR(
    cacheKey,
    async () => {
      const response = await fetchDocuments(matterId, {
        page,
        perPage,
        filters,
        sort,
      });
      return response;
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000, // 5 seconds deduplication
      // SWR handles polling natively - much more efficient than setInterval
      refreshInterval: (latestData) => {
        if (!enablePolling) return 0;
        // Poll if any documents are processing
        const hasProcessingDocs = latestData?.data?.some(
          (d) => d.status === 'processing' || d.status === 'pending'
        );
        return hasProcessingDocs ? PROCESSING_POLL_INTERVAL_MS : 0;
      },
    }
  );

  // Check if any documents are processing
  const hasProcessing = (data?.data ?? []).some(
    (d) => d.status === 'processing' || d.status === 'pending'
  );

  return {
    documents: data?.data ?? [],
    isLoading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
    refresh: async () => {
      await mutate();
    },
    totalCount: data?.meta?.total ?? 0,
    hasProcessing,
  };
}
