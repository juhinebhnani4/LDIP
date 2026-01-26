'use client';

/**
 * useBoundingBoxes Hook
 *
 * Hook for fetching and managing bounding box data from the API.
 * Handles coordinate normalization from API format (0-100) to canvas format (0-1).
 *
 * Story 11.7: Implement Bounding Box Overlays (AC: #1, #3)
 */

import { useState, useCallback, useRef } from 'react';
import type { SplitViewBoundingBox } from '@/types/citation';
import type { BoundingBox } from '@/types/document';
import {
  fetchBoundingBoxesForChunk,
  fetchBoundingBoxesForPage,
  fetchBoundingBoxesByIds,
} from '@/lib/api/bounding-boxes';

/**
 * Result of a bbox fetch operation including page number.
 * Exported for consumers who need to type the return value.
 */
export interface BboxFetchResult {
  bboxes: SplitViewBoundingBox[];
  pageNumber: number | null;
}

interface UseBoundingBoxesReturn {
  /** Normalized bounding boxes (0-1 coordinates) ready for canvas rendering */
  boundingBoxes: SplitViewBoundingBox[];
  /** Whether a fetch is in progress */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Page number the bounding boxes belong to */
  bboxPageNumber: number | null;
  /** Fetch bounding boxes by chunk ID - returns bboxes and page number */
  fetchByChunkId: (chunkId: string) => Promise<BboxFetchResult>;
  /** Fetch bounding boxes by document and page - returns bboxes and page number */
  fetchByPage: (documentId: string, pageNumber: number) => Promise<BboxFetchResult>;
  /** Fetch bounding boxes by their IDs directly - returns bboxes and page number */
  fetchByBboxIds: (bboxIds: string[], matterId: string) => Promise<BboxFetchResult>;
  /** Clear all bounding boxes and cache */
  clearBboxes: () => void;
}

/**
 * Normalize bounding box coordinates from API format (0-100) to canvas format (0-1).
 * The API client already handles snake_case to camelCase conversion.
 */
function normalizeBbox(bbox: BoundingBox): SplitViewBoundingBox {
  return {
    bboxId: bbox.id,
    x: bbox.x / 100,
    y: bbox.y / 100,
    width: bbox.width / 100,
    height: bbox.height / 100,
    text: bbox.text,
  };
}

/**
 * Hook for fetching and managing bounding box data.
 *
 * Story 11.7: Implement Bounding Box Overlays
 * - AC #1: Fetches bbox data and page number from API
 * - AC #3: Supports cross-reference navigation via fetchByPage
 *
 * @returns Object with bbox data, loading state, error state, and fetch functions
 *
 * @example
 * ```tsx
 * const { fetchByChunkId, isLoading, error } = useBoundingBoxes();
 *
 * // Fetch bbox data when source is clicked (returns bboxes AND page number)
 * const handleSourceClick = async (chunkId: string) => {
 *   const { bboxes, pageNumber } = await fetchByChunkId(chunkId);
 *   // Use bboxes for highlighting, pageNumber to navigate to correct page
 *   setBoundingBoxes(bboxes, pageNumber);
 * };
 * ```
 */
export function useBoundingBoxes(): UseBoundingBoxesReturn {
  const [boundingBoxes, setBoundingBoxes] = useState<SplitViewBoundingBox[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bboxPageNumber, setBboxPageNumber] = useState<number | null>(null);

  // Cache to prevent redundant fetches for same chunk/page
  const cacheRef = useRef<Map<string, { bboxes: SplitViewBoundingBox[]; pageNumber: number | null }>>(
    new Map()
  );

  /**
   * Fetch bounding boxes by chunk ID.
   * Uses GET /api/chunks/{chunkId}/bounding-boxes endpoint.
   * Returns both bboxes and page number for immediate use by caller.
   */
  const fetchByChunkId = useCallback(
    async (chunkId: string): Promise<BboxFetchResult> => {
      const cacheKey = `chunk:${chunkId}`;

      // Check cache first
      if (cacheRef.current.has(cacheKey)) {
        const cached = cacheRef.current.get(cacheKey)!;
        setBoundingBoxes(cached.bboxes);
        setBboxPageNumber(cached.pageNumber);
        return { bboxes: cached.bboxes, pageNumber: cached.pageNumber };
      }

      setIsLoading(true);
      setError(null);

      try {
        // Use API client with correct base URL (port 8000)
        const result = await fetchBoundingBoxesForChunk(chunkId);
        const data = result.data;

        const normalized = data.map(normalizeBbox);

        // Get page number from first bbox (all bboxes from same chunk should be on same page)
        const pageNumber = data.length > 0 && data[0] ? data[0].pageNumber ?? null : null;

        // Cache the result
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });

        setBoundingBoxes(normalized);
        setBboxPageNumber(pageNumber);
        return { bboxes: normalized, pageNumber };
      } catch (err) {
        // Handle 404 as empty result, not error
        if (err && typeof err === 'object' && 'status' in err && err.status === 404) {
          setBoundingBoxes([]);
          setBboxPageNumber(null);
          return { bboxes: [], pageNumber: null };
        }
        const errorMessage = err instanceof Error ? err.message : 'Unknown error fetching bounding boxes';
        setError(errorMessage);
        setBoundingBoxes([]);
        setBboxPageNumber(null);
        return { bboxes: [], pageNumber: null };
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  /**
   * Fetch bounding boxes by document ID and page number.
   * Uses GET /api/documents/{documentId}/pages/{pageNumber}/bounding-boxes endpoint.
   * Returns both bboxes and page number for immediate use by caller.
   */
  const fetchByPage = useCallback(
    async (documentId: string, pageNumber: number): Promise<BboxFetchResult> => {
      const cacheKey = `page:${documentId}:${pageNumber}`;

      // Check cache first
      if (cacheRef.current.has(cacheKey)) {
        const cached = cacheRef.current.get(cacheKey)!;
        setBoundingBoxes(cached.bboxes);
        setBboxPageNumber(pageNumber);
        return { bboxes: cached.bboxes, pageNumber };
      }

      setIsLoading(true);
      setError(null);

      try {
        // Use API client with correct base URL (port 8000)
        const result = await fetchBoundingBoxesForPage(documentId, pageNumber);
        const data = result.data;

        const normalized = data.map(normalizeBbox);

        // Cache the result
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });

        setBoundingBoxes(normalized);
        setBboxPageNumber(pageNumber);
        return { bboxes: normalized, pageNumber };
      } catch (err) {
        // Handle 404 as empty result, not error
        if (err && typeof err === 'object' && 'status' in err && err.status === 404) {
          setBoundingBoxes([]);
          setBboxPageNumber(pageNumber);
          return { bboxes: [], pageNumber };
        }
        const errorMessage = err instanceof Error ? err.message : 'Unknown error fetching bounding boxes';
        setError(errorMessage);
        setBoundingBoxes([]);
        setBboxPageNumber(pageNumber);
        return { bboxes: [], pageNumber };
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  /**
   * Fetch bounding boxes by their IDs directly.
   * Uses POST /api/bounding-boxes/by-ids endpoint.
   * Returns both bboxes and page number for immediate use by caller.
   */
  const fetchByBboxIds = useCallback(
    async (bboxIds: string[], matterId: string): Promise<BboxFetchResult> => {
      if (!bboxIds.length) {
        return { bboxes: [], pageNumber: null };
      }

      const cacheKey = `ids:${bboxIds.slice(0, 3).join(',')}`;

      // Check cache first
      if (cacheRef.current.has(cacheKey)) {
        const cached = cacheRef.current.get(cacheKey)!;
        setBoundingBoxes(cached.bboxes);
        setBboxPageNumber(cached.pageNumber);
        return { bboxes: cached.bboxes, pageNumber: cached.pageNumber };
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await fetchBoundingBoxesByIds(bboxIds, matterId);
        const data = result.data;

        const normalized = data.map(normalizeBbox);

        // Get page number from first bbox
        const pageNumber = data.length > 0 && data[0] ? data[0].pageNumber ?? null : null;

        // Cache the result
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });

        setBoundingBoxes(normalized);
        setBboxPageNumber(pageNumber);
        return { bboxes: normalized, pageNumber };
      } catch (err) {
        // Handle 404 as empty result, not error
        if (err && typeof err === 'object' && 'status' in err && err.status === 404) {
          setBoundingBoxes([]);
          setBboxPageNumber(null);
          return { bboxes: [], pageNumber: null };
        }
        const errorMessage = err instanceof Error ? err.message : 'Unknown error fetching bounding boxes';
        setError(errorMessage);
        setBoundingBoxes([]);
        setBboxPageNumber(null);
        return { bboxes: [], pageNumber: null };
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  /**
   * Clear all bounding boxes, reset state, and clear cache.
   * Call this when changing documents to prevent stale data.
   */
  const clearBboxes = useCallback(() => {
    setBoundingBoxes([]);
    setBboxPageNumber(null);
    setError(null);
    // Clear cache to prevent stale data when bboxes are updated on backend
    cacheRef.current.clear();
  }, []);

  return {
    boundingBoxes,
    isLoading,
    error,
    bboxPageNumber,
    fetchByChunkId,
    fetchByPage,
    fetchByBboxIds,
    clearBboxes,
  };
}
