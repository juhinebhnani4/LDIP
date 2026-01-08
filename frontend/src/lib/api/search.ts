'use client'

import { api } from './client'
import type {
  BM25SearchRequest,
  SearchRequest,
  SearchResponse,
  SearchResult,
  SemanticSearchRequest,
  SingleModeSearchResponse,
} from '@/types/search'

/**
 * Search API client for hybrid search operations.
 *
 * All search operations are matter-isolated. The matter_id is
 * validated server-side against the user's access permissions.
 */

/** Convert snake_case API response to camelCase */
function transformSearchResult(data: Record<string, unknown>): SearchResult {
  return {
    id: data.id as string,
    documentId: data.document_id as string,
    content: data.content as string,
    pageNumber: data.page_number as number | null,
    chunkType: data.chunk_type as 'parent' | 'child',
    tokenCount: data.token_count as number,
    bm25Rank: data.bm25_rank as number | null,
    semanticRank: data.semantic_rank as number | null,
    rrfScore: data.rrf_score as number,
  }
}

/** Transform hybrid search response */
function transformSearchResponse(data: {
  data: Record<string, unknown>[]
  meta: Record<string, unknown>
}): SearchResponse {
  return {
    data: data.data.map(transformSearchResult),
    meta: {
      query: data.meta.query as string,
      matterId: data.meta.matter_id as string,
      totalCandidates: data.meta.total_candidates as number,
      bm25Weight: data.meta.bm25_weight as number,
      semanticWeight: data.meta.semantic_weight as number,
    },
  }
}

/** Transform single-mode search response */
function transformSingleModeResponse(data: {
  data: Record<string, unknown>[]
  meta: Record<string, unknown>
}): SingleModeSearchResponse {
  return {
    data: data.data.map(transformSearchResult),
    meta: {
      query: data.meta.query as string,
      matterId: data.meta.matter_id as string,
      resultCount: data.meta.result_count as number,
      searchType: data.meta.search_type as 'bm25' | 'semantic',
    },
  }
}

/**
 * Execute hybrid search combining BM25 and semantic search with RRF fusion.
 *
 * Best for general-purpose retrieval where both exact terms and
 * conceptual similarity matter.
 *
 * @param matterId - Matter UUID to search within
 * @param request - Search parameters
 * @returns Search results with RRF scores
 *
 * @example
 * ```ts
 * const results = await hybridSearch('matter-123', {
 *   query: 'contract termination clause',
 *   limit: 20,
 *   bm25Weight: 1.0,
 *   semanticWeight: 1.5,
 * })
 * ```
 */
export async function hybridSearch(
  matterId: string,
  request: SearchRequest
): Promise<SearchResponse> {
  const body = {
    query: request.query,
    limit: request.limit ?? 20,
    bm25_weight: request.bm25Weight ?? 1.0,
    semantic_weight: request.semanticWeight ?? 1.0,
  }

  const response = await api.post<{
    data: Record<string, unknown>[]
    meta: Record<string, unknown>
  }>(`/api/matters/${matterId}/search`, body)

  return transformSearchResponse(response)
}

/**
 * Execute BM25-only keyword search.
 *
 * Uses PostgreSQL full-text search. Best for finding specific terms,
 * legal citations, or exact phrases.
 *
 * @param matterId - Matter UUID to search within
 * @param request - Search parameters
 * @returns Search results ranked by BM25 score
 *
 * @example
 * ```ts
 * const results = await bm25Search('matter-123', {
 *   query: 'Section 138 Negotiable Instruments Act',
 *   limit: 30,
 * })
 * ```
 */
export async function bm25Search(
  matterId: string,
  request: BM25SearchRequest
): Promise<SingleModeSearchResponse> {
  const body = {
    query: request.query,
    limit: request.limit ?? 30,
  }

  const response = await api.post<{
    data: Record<string, unknown>[]
    meta: Record<string, unknown>
  }>(`/api/matters/${matterId}/search/bm25`, body)

  return transformSingleModeResponse(response)
}

/**
 * Execute semantic-only vector search.
 *
 * Uses OpenAI embeddings with pgvector. Best for conceptual similarity,
 * paraphrased queries, and abstract concepts.
 *
 * @param matterId - Matter UUID to search within
 * @param request - Search parameters
 * @returns Search results ranked by cosine similarity
 *
 * @example
 * ```ts
 * const results = await semanticSearch('matter-123', {
 *   query: 'remedies for breach of contract',
 *   limit: 30,
 * })
 * ```
 */
export async function semanticSearch(
  matterId: string,
  request: SemanticSearchRequest
): Promise<SingleModeSearchResponse> {
  const body = {
    query: request.query,
    limit: request.limit ?? 30,
  }

  const response = await api.post<{
    data: Record<string, unknown>[]
    meta: Record<string, unknown>
  }>(`/api/matters/${matterId}/search/semantic`, body)

  return transformSingleModeResponse(response)
}

/**
 * Search API object for convenient imports.
 */
export const searchApi = {
  hybrid: hybridSearch,
  bm25: bm25Search,
  semantic: semanticSearch,
}
