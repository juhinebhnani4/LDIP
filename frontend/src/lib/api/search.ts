'use client'

import { api } from './client'
import type {
  BM25SearchRequest,
  RerankedSearchResponse,
  RerankedSearchResult,
  RerankSearchRequest,
  SearchRequest,
  SearchResponse,
  SearchResult,
  SemanticSearchRequest,
  SingleModeSearchResponse,
} from '@/types/search'
import {
  DEFAULT_SEARCH_WEIGHTS,
  RERANK_DEFAULTS,
  SEARCH_LIMITS,
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
    relevanceScore: (data.relevance_score as number | null) ?? null,
  }
}

/** Convert snake_case API response to camelCase for reranked results */
function transformRerankedResult(data: Record<string, unknown>): RerankedSearchResult {
  return {
    ...transformSearchResult(data),
    relevanceScore: (data.relevance_score as number | null) ?? null,
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
      rerankUsed: (data.meta.rerank_used as boolean | null) ?? null,
      fallbackReason: (data.meta.fallback_reason as string | null) ?? null,
    },
  }
}

/** Transform reranked search response */
function transformRerankedResponse(data: {
  data: Record<string, unknown>[]
  meta: Record<string, unknown>
}): RerankedSearchResponse {
  return {
    data: data.data.map(transformRerankedResult),
    meta: {
      query: data.meta.query as string,
      matterId: data.meta.matter_id as string,
      totalCandidates: data.meta.total_candidates as number,
      bm25Weight: data.meta.bm25_weight as number,
      semanticWeight: data.meta.semantic_weight as number,
      rerankUsed: data.meta.rerank_used as boolean,
      fallbackReason: (data.meta.fallback_reason as string | null) ?? null,
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
 * Set `rerank: true` to enable Cohere Rerank v3.5 for improved precision.
 * When enabled, returns top `rerankTopN` results (default 3) with
 * relevance scores from Cohere.
 *
 * @param matterId - Matter UUID to search within
 * @param request - Search parameters (including optional rerank options)
 * @returns Search results with RRF scores (and relevanceScore if rerank=true)
 *
 * @example
 * ```ts
 * // Standard hybrid search
 * const results = await hybridSearch('matter-123', {
 *   query: 'contract termination clause',
 *   limit: 20,
 * })
 *
 * // Hybrid search with Cohere reranking
 * const rerankedResults = await hybridSearch('matter-123', {
 *   query: 'contract termination clause',
 *   limit: 20,
 *   rerank: true,
 *   rerankTopN: 3,
 * })
 * ```
 */
export async function hybridSearch(
  matterId: string,
  request: SearchRequest
): Promise<SearchResponse> {
  const body: Record<string, unknown> = {
    query: request.query,
    limit: request.limit ?? SEARCH_LIMITS.default,
    bm25_weight: request.bm25Weight ?? DEFAULT_SEARCH_WEIGHTS.bm25,
    semantic_weight: request.semanticWeight ?? DEFAULT_SEARCH_WEIGHTS.semantic,
  }

  // Add rerank parameters if requested
  if (request.rerank) {
    body.rerank = true
    body.rerank_top_n = request.rerankTopN ?? RERANK_DEFAULTS.topN
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
    limit: request.limit ?? SEARCH_LIMITS.defaultSingleMode,
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
    limit: request.limit ?? SEARCH_LIMITS.defaultSingleMode,
  }

  const response = await api.post<{
    data: Record<string, unknown>[]
    meta: Record<string, unknown>
  }>(`/api/matters/${matterId}/search/semantic`, body)

  return transformSingleModeResponse(response)
}

/**
 * Execute hybrid search with Cohere Rerank v3.5.
 *
 * This is a dedicated endpoint for reranked search that always applies
 * Cohere reranking to hybrid search results.
 *
 * The pipeline:
 * 1. Hybrid search returns top N candidates (default 20)
 * 2. Cohere Rerank v3.5 scores each candidate by query relevance
 * 3. Returns top K most relevant results (default 3)
 *
 * This approach improves search precision by 40-70% for legal documents.
 *
 * @param matterId - Matter UUID to search within
 * @param request - Search parameters
 * @returns Reranked search results with relevanceScore from Cohere
 *
 * @example
 * ```ts
 * const results = await searchWithRerank('matter-123', {
 *   query: 'contract termination clause',
 *   limit: 20,    // hybrid search candidates
 *   topN: 3,      // results after reranking
 * })
 * ```
 */
export async function searchWithRerank(
  matterId: string,
  request: RerankSearchRequest
): Promise<RerankedSearchResponse> {
  const body = {
    query: request.query,
    limit: request.limit ?? RERANK_DEFAULTS.hybridLimit,
    top_n: request.topN ?? RERANK_DEFAULTS.topN,
    bm25_weight: request.bm25Weight ?? DEFAULT_SEARCH_WEIGHTS.bm25,
    semantic_weight: request.semanticWeight ?? DEFAULT_SEARCH_WEIGHTS.semantic,
  }

  const response = await api.post<{
    data: Record<string, unknown>[]
    meta: Record<string, unknown>
  }>(`/api/matters/${matterId}/search/rerank`, body)

  return transformRerankedResponse(response)
}

/**
 * Search API object for convenient imports.
 */
export const searchApi = {
  hybrid: hybridSearch,
  bm25: bm25Search,
  semantic: semanticSearch,
  rerank: searchWithRerank,
}
