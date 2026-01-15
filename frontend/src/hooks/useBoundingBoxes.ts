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

/**
 * Bounding box data as returned by the API (percentage 0-100 format)
 */
interface ApiBoundingBoxData {
  id: string;
  document_id: string;
  page_number: number;
  x: number; // 0-100 (percentage)
  y: number; // 0-100 (percentage)
  width: number; // 0-100 (percentage)
  height: number; // 0-100 (percentage)
  text: string;
  confidence: number | null;
  reading_order_index: number | null;
}

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
  /** Clear all bounding boxes and cache */
  clearBboxes: () => void;
}

/**
 * Normalize bounding box coordinates from API format (0-100) to canvas format (0-1)
 */
function normalizeBbox(bbox: ApiBoundingBoxData): SplitViewBoundingBox {
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
        const response = await fetch(`/api/chunks/${chunkId}/bounding-boxes`);

        if (!response.ok) {
          if (response.status === 404) {
            // No bboxes found is not an error, just empty result
            setBoundingBoxes([]);
            setBboxPageNumber(null);
            return { bboxes: [], pageNumber: null };
          }
          throw new Error(`Failed to fetch bounding boxes: ${response.statusText}`);
        }

        const result = await response.json();
        const data = result.data as ApiBoundingBoxData[];

        const normalized = data.map(normalizeBbox);

        // Get page number from first bbox (all bboxes from same chunk should be on same page)
        const pageNumber = data.length > 0 && data[0] ? data[0].page_number : null;

        // Cache the result
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });

        setBoundingBoxes(normalized);
        setBboxPageNumber(pageNumber);
        return { bboxes: normalized, pageNumber };
      } catch (err) {
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
        const response = await fetch(
          `/api/documents/${documentId}/pages/${pageNumber}/bounding-boxes`
        );

        if (!response.ok) {
          if (response.status === 404) {
            // No bboxes found is not an error, just empty result
            setBoundingBoxes([]);
            setBboxPageNumber(pageNumber);
            return { bboxes: [], pageNumber };
          }
          throw new Error(`Failed to fetch bounding boxes: ${response.statusText}`);
        }

        const result = await response.json();
        const data = result.data as ApiBoundingBoxData[];

        const normalized = data.map(normalizeBbox);

        // Cache the result
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });

        setBoundingBoxes(normalized);
        setBboxPageNumber(pageNumber);
        return { bboxes: normalized, pageNumber };
      } catch (err) {
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
    clearBboxes,
  };
}
