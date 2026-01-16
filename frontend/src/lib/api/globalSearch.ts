/**
 * Global Search API client.
 *
 * Provides API methods for searching across all matters the user has access to.
 * Story 14.11: Global Search RAG Wiring
 */

import { api } from './client';

/**
 * Search result item from the global search API.
 * Matches the frontend SearchResult interface in GlobalSearch.tsx.
 */
export interface SearchResult {
  id: string;
  type: 'matter' | 'document';
  title: string;
  matterId: string;
  matterTitle: string;
  matchedContent: string;
}

/**
 * Global search response metadata.
 */
interface GlobalSearchMeta {
  query: string;
  total: number;
}

/**
 * Global search API response.
 */
interface GlobalSearchResponse {
  data: SearchResult[];
  meta: GlobalSearchMeta;
}

/**
 * Search across all matters the user has access to.
 *
 * Uses hybrid search (BM25 + semantic) with cross-matter RRF fusion.
 * Results include both matter title matches and document content matches.
 *
 * @param query - Search query (minimum 2 characters)
 * @param limit - Maximum results to return (default 20, max 50)
 * @returns Array of search results
 *
 * @example
 * const results = await globalSearch('contract breach');
 * // Returns matters and documents matching "contract breach"
 */
export async function globalSearch(
  query: string,
  limit = 20
): Promise<SearchResult[]> {
  const params = new URLSearchParams({
    q: query,
    limit: limit.toString(),
  });

  const response = await api.get<GlobalSearchResponse>(
    `/api/search?${params.toString()}`
  );

  return response.data;
}
