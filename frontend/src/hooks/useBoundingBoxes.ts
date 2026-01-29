'use client';

/**
 * useBoundingBoxes Hook
 *
 * Hook for fetching and managing bounding box data from the API.
 * Handles coordinate normalization from API format (0-100) to canvas format (0-1).
 *
 * EGRESS OPTIMIZATION: Uses two-tier caching:
 * 1. In-memory cache (fast, lost on refresh)
 * 2. localStorage cache (persists across sessions, reduces repeat fetches)
 *
 * Story 11.7: Implement Bounding Box Overlays (AC: #1, #3)
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type { SplitViewBoundingBox } from '@/types/citation';
import type { BoundingBox } from '@/types/document';
import {
  fetchBoundingBoxesForChunk,
  fetchBoundingBoxesForPage,
  fetchBoundingBoxesByIds,
  fetchBoundingBoxCoordsForChunk,
  fetchBoundingBoxCoordsForPage,
  fetchBoundingBoxCoordsByIds,
} from '@/lib/api/bounding-boxes';

// =============================================================================
// EGRESS OPTIMIZATION: localStorage cache for bounding boxes
// =============================================================================

const BBOX_CACHE_PREFIX = 'ldip:bbox:';
const BBOX_CACHE_VERSION = 'v1';
const BBOX_CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours
const BBOX_CACHE_MAX_ENTRIES = 100; // Limit localStorage usage

interface CachedBboxData {
  bboxes: SplitViewBoundingBox[];
  pageNumber: number | null;
  timestamp: number;
  version: string;
}

/**
 * Load bbox data from localStorage cache.
 * Returns null if not found, expired, or invalid.
 */
function loadFromLocalStorage(key: string): CachedBboxData | null {
  if (typeof window === 'undefined') return null;

  try {
    const stored = localStorage.getItem(`${BBOX_CACHE_PREFIX}${key}`);
    if (!stored) return null;

    const data = JSON.parse(stored) as CachedBboxData;

    // Validate version
    if (data.version !== BBOX_CACHE_VERSION) return null;

    // Check expiry
    if (Date.now() - data.timestamp > BBOX_CACHE_MAX_AGE_MS) {
      localStorage.removeItem(`${BBOX_CACHE_PREFIX}${key}`);
      return null;
    }

    return data;
  } catch {
    return null;
  }
}

/**
 * Save bbox data to localStorage cache.
 * Automatically prunes old entries if cache is full.
 */
function saveToLocalStorage(key: string, bboxes: SplitViewBoundingBox[], pageNumber: number | null): void {
  if (typeof window === 'undefined') return;

  try {
    // Prune old entries if approaching limit
    pruneLocalStorageCache();

    const data: CachedBboxData = {
      bboxes,
      pageNumber,
      timestamp: Date.now(),
      version: BBOX_CACHE_VERSION,
    };

    localStorage.setItem(`${BBOX_CACHE_PREFIX}${key}`, JSON.stringify(data));
  } catch {
    // localStorage might be full or disabled - ignore silently
  }
}

/**
 * Prune old/expired entries from localStorage to stay under limit.
 */
function pruneLocalStorageCache(): void {
  if (typeof window === 'undefined') return;

  try {
    const entries: Array<{ key: string; timestamp: number }> = [];

    // Collect all bbox cache entries
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(BBOX_CACHE_PREFIX)) {
        try {
          const data = JSON.parse(localStorage.getItem(key) || '{}');
          entries.push({ key, timestamp: data.timestamp || 0 });
        } catch {
          // Invalid entry - mark for removal
          entries.push({ key, timestamp: 0 });
        }
      }
    }

    // Remove expired or excess entries (oldest first)
    if (entries.length > BBOX_CACHE_MAX_ENTRIES * 0.8) {
      entries.sort((a, b) => a.timestamp - b.timestamp);
      const toRemove = entries.slice(0, Math.floor(entries.length * 0.3));
      toRemove.forEach(({ key }) => localStorage.removeItem(key));
    }
  } catch {
    // Ignore pruning errors
  }
}

/**
 * Result of a bbox fetch operation including page number.
 * Exported for consumers who need to type the return value.
 */
export interface BboxFetchResult {
  bboxes: SplitViewBoundingBox[];
  pageNumber: number | null;
}

interface FetchOptions {
  /** Include text content. Set false to reduce egress ~80%. Default: false for highlighting. */
  includeText?: boolean;
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
  fetchByChunkId: (chunkId: string, options?: FetchOptions) => Promise<BboxFetchResult>;
  /** Fetch bounding boxes by document and page - returns bboxes and page number */
  fetchByPage: (documentId: string, pageNumber: number, options?: FetchOptions) => Promise<BboxFetchResult>;
  /** Fetch bounding boxes by their IDs directly - returns bboxes and page number */
  fetchByBboxIds: (bboxIds: string[], matterId: string, options?: FetchOptions) => Promise<BboxFetchResult>;
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
   *
   * EGRESS OPTIMIZATION:
   * 1. By default, excludes text content to reduce egress ~80%.
   * 2. Uses two-tier cache: in-memory (fast) + localStorage (persists).
   * Pass { includeText: true } when text is needed (e.g., for diff comparison).
   */
  const fetchByChunkId = useCallback(
    async (chunkId: string, options?: FetchOptions): Promise<BboxFetchResult> => {
      const includeText = options?.includeText ?? false; // EGRESS OPTIMIZATION: Default to no text
      const cacheKey = `chunk:${chunkId}:${includeText}`;

      // Check in-memory cache first (fastest)
      if (cacheRef.current.has(cacheKey)) {
        const cached = cacheRef.current.get(cacheKey)!;
        setBoundingBoxes(cached.bboxes);
        setBboxPageNumber(cached.pageNumber);
        return { bboxes: cached.bboxes, pageNumber: cached.pageNumber };
      }

      // Check localStorage cache (persists across sessions)
      const localCached = loadFromLocalStorage(cacheKey);
      if (localCached) {
        // Populate in-memory cache for faster subsequent access
        cacheRef.current.set(cacheKey, { bboxes: localCached.bboxes, pageNumber: localCached.pageNumber });
        setBoundingBoxes(localCached.bboxes);
        setBboxPageNumber(localCached.pageNumber);
        return { bboxes: localCached.bboxes, pageNumber: localCached.pageNumber };
      }

      setIsLoading(true);
      setError(null);

      try {
        // EGRESS OPTIMIZATION: Use coordinates-only fetch when text not needed
        const result = includeText
          ? await fetchBoundingBoxesForChunk(chunkId)
          : await fetchBoundingBoxCoordsForChunk(chunkId);
        const data = result.data;

        const normalized = data.map(normalizeBbox);

        // Get page number from first bbox (all bboxes from same chunk should be on same page)
        const pageNumber = data.length > 0 && data[0] ? data[0].pageNumber ?? null : null;

        // Save to both caches
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });
        saveToLocalStorage(cacheKey, normalized, pageNumber);

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
   *
   * EGRESS OPTIMIZATION:
   * 1. By default, excludes text content to reduce egress ~80%.
   * 2. Uses two-tier cache: in-memory (fast) + localStorage (persists).
   * Pass { includeText: true } when text is needed (e.g., for diff comparison).
   */
  const fetchByPage = useCallback(
    async (documentId: string, pageNumber: number, options?: FetchOptions): Promise<BboxFetchResult> => {
      const includeText = options?.includeText ?? false; // EGRESS OPTIMIZATION: Default to no text
      const cacheKey = `page:${documentId}:${pageNumber}:${includeText}`;

      // Check in-memory cache first (fastest)
      if (cacheRef.current.has(cacheKey)) {
        const cached = cacheRef.current.get(cacheKey)!;
        setBoundingBoxes(cached.bboxes);
        setBboxPageNumber(pageNumber);
        return { bboxes: cached.bboxes, pageNumber };
      }

      // Check localStorage cache (persists across sessions)
      const localCached = loadFromLocalStorage(cacheKey);
      if (localCached) {
        // Populate in-memory cache for faster subsequent access
        cacheRef.current.set(cacheKey, { bboxes: localCached.bboxes, pageNumber });
        setBoundingBoxes(localCached.bboxes);
        setBboxPageNumber(pageNumber);
        return { bboxes: localCached.bboxes, pageNumber };
      }

      setIsLoading(true);
      setError(null);

      try {
        // EGRESS OPTIMIZATION: Use coordinates-only fetch when text not needed
        const result = includeText
          ? await fetchBoundingBoxesForPage(documentId, pageNumber)
          : await fetchBoundingBoxCoordsForPage(documentId, pageNumber);
        const data = result.data;

        const normalized = data.map(normalizeBbox);

        // Save to both caches
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });
        saveToLocalStorage(cacheKey, normalized, pageNumber);

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
   *
   * EGRESS OPTIMIZATION:
   * 1. By default, excludes text content to reduce egress ~80%.
   * 2. Uses two-tier cache: in-memory (fast) + localStorage (persists).
   * Pass { includeText: true } when text is needed (e.g., for diff comparison).
   */
  const fetchByBboxIds = useCallback(
    async (bboxIds: string[], matterId: string, options?: FetchOptions): Promise<BboxFetchResult> => {
      if (!bboxIds.length) {
        return { bboxes: [], pageNumber: null };
      }

      const includeText = options?.includeText ?? false; // EGRESS OPTIMIZATION: Default to no text
      // Use hash of IDs for cache key (handles large lists)
      const cacheKey = `ids:${bboxIds.length}:${bboxIds.slice(0, 3).join(',')}:${includeText}`;

      // Check in-memory cache first (fastest)
      if (cacheRef.current.has(cacheKey)) {
        const cached = cacheRef.current.get(cacheKey)!;
        setBoundingBoxes(cached.bboxes);
        setBboxPageNumber(cached.pageNumber);
        return { bboxes: cached.bboxes, pageNumber: cached.pageNumber };
      }

      // Check localStorage cache (persists across sessions)
      const localCached = loadFromLocalStorage(cacheKey);
      if (localCached) {
        // Populate in-memory cache for faster subsequent access
        cacheRef.current.set(cacheKey, { bboxes: localCached.bboxes, pageNumber: localCached.pageNumber });
        setBoundingBoxes(localCached.bboxes);
        setBboxPageNumber(localCached.pageNumber);
        return { bboxes: localCached.bboxes, pageNumber: localCached.pageNumber };
      }

      setIsLoading(true);
      setError(null);

      try {
        // EGRESS OPTIMIZATION: Use coordinates-only fetch when text not needed
        const result = includeText
          ? await fetchBoundingBoxesByIds(bboxIds, matterId)
          : await fetchBoundingBoxCoordsByIds(bboxIds, matterId);
        const data = result.data;

        const normalized = data.map(normalizeBbox);

        // Get page number from first bbox
        const pageNumber = data.length > 0 && data[0] ? data[0].pageNumber ?? null : null;

        // Save to both caches
        cacheRef.current.set(cacheKey, { bboxes: normalized, pageNumber });
        saveToLocalStorage(cacheKey, normalized, pageNumber);

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
