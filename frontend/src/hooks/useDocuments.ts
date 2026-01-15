'use client';

/**
 * Documents Hook
 *
 * Custom hook for fetching documents for a matter.
 * Provides loading, error state, and refresh functionality.
 *
 * Story 10D.3: Documents Tab File List
 */

import { useCallback, useEffect, useRef, useState } from 'react';
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
 * Hook for fetching documents for a matter.
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
    filters = {},
    sort = { column: 'uploaded_at', order: 'desc' },
    enablePolling = true,
  } = options;

  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);

  // Track mounted state to prevent state updates after unmount
  const isMountedRef = useRef(true);

  // Check if any documents are processing
  const hasProcessing = documents.some(
    (d) => d.status === 'processing' || d.status === 'pending'
  );

  // Fetch documents from API
  const fetchDocs = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetchDocuments(matterId, {
        page,
        perPage,
        filters,
        sort,
      });

      // Only update state if component is still mounted
      if (isMountedRef.current) {
        setDocuments(response.data);
        setTotalCount(response.meta.total);
      }
    } catch (err) {
      // Only update state if component is still mounted
      if (isMountedRef.current) {
        const message =
          err instanceof Error ? err.message : 'Failed to load documents';
        setError(message);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [matterId, page, perPage, filters, sort]);

  // Initialize and fetch on mount/matterId change
  useEffect(() => {
    isMountedRef.current = true;
    fetchDocs();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchDocs]);

  // Set up polling when documents are processing
  useEffect(() => {
    if (!enablePolling || !hasProcessing) {
      return;
    }

    const intervalId = setInterval(() => {
      // Don't poll if currently loading
      if (!isLoading && isMountedRef.current) {
        fetchDocs();
      }
    }, PROCESSING_POLL_INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
    };
  }, [enablePolling, hasProcessing, isLoading, fetchDocs]);

  return {
    documents,
    isLoading,
    error,
    refresh: fetchDocs,
    totalCount,
    hasProcessing,
  };
}
