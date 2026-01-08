/**
 * Search Types
 *
 * Types for hybrid search API (BM25 + semantic with RRF fusion).
 * Matches backend Pydantic models in app/models/search.py
 */

/** Request model for hybrid search */
export interface SearchRequest {
  /** Search query text (1-1000 chars) */
  query: string
  /** Maximum results to return (1-100, default 20) */
  limit?: number
  /** Weight for BM25 keyword search (0.0-2.0) */
  bm25Weight?: number
  /** Weight for semantic similarity search (0.0-2.0) */
  semanticWeight?: number
  /** Enable Cohere Rerank v3.5 for improved precision (default: false) */
  rerank?: boolean
  /** Number of top results after reranking (1-20, default 3, only used when rerank=true) */
  rerankTopN?: number
}

/** Request model for BM25-only keyword search */
export interface BM25SearchRequest {
  /** Search query text */
  query: string
  /** Maximum results to return (1-100, default 30) */
  limit?: number
}

/** Request model for semantic-only vector search */
export interface SemanticSearchRequest {
  /** Search query text */
  query: string
  /** Maximum results to return (1-100, default 30) */
  limit?: number
}

/** Single search result item */
export interface SearchResult {
  /** Chunk UUID */
  id: string
  /** Source document UUID */
  documentId: string
  /** Chunk text content */
  content: string
  /** Source page number (for highlighting) */
  pageNumber: number | null
  /** Chunk type: 'parent' or 'child' */
  chunkType: 'parent' | 'child'
  /** Number of tokens in chunk */
  tokenCount: number
  /** Rank from BM25 search (null if not in BM25 results) */
  bm25Rank: number | null
  /** Rank from semantic search (null if not in semantic results) */
  semanticRank: number | null
  /** Combined RRF fusion score */
  rrfScore: number
  /** Cohere relevance score (0.0-1.0). Only present when rerank=true. */
  relevanceScore: number | null
}

/** Metadata about hybrid search results */
export interface SearchMeta {
  /** Original search query */
  query: string
  /** Matter UUID searched */
  matterId: string
  /** Total candidates before limit */
  totalCandidates: number
  /** BM25 weight used */
  bm25Weight: number
  /** Semantic weight used */
  semanticWeight: number
  /** True if Cohere reranking was used. Null if rerank was not requested. */
  rerankUsed: boolean | null
  /** Reason for fallback if rerankUsed is false */
  fallbackReason: string | null
}

/** Response model for hybrid search */
export interface SearchResponse {
  /** Search results */
  data: SearchResult[]
  /** Search metadata */
  meta: SearchMeta
}

/** Metadata for single-mode search results */
export interface SingleModeSearchMeta {
  /** Original search query */
  query: string
  /** Matter UUID searched */
  matterId: string
  /** Number of results returned */
  resultCount: number
  /** Search type: 'bm25' or 'semantic' */
  searchType: 'bm25' | 'semantic'
}

/** Response model for BM25 or semantic-only search */
export interface SingleModeSearchResponse {
  /** Search results */
  data: SearchResult[]
  /** Search metadata */
  meta: SingleModeSearchMeta
}

/** Search mode options */
export type SearchMode = 'hybrid' | 'bm25' | 'semantic' | 'rerank'

/** Default search weights */
export const DEFAULT_SEARCH_WEIGHTS = {
  bm25: 1.0,
  semantic: 1.0,
} as const

/** Search limit constraints */
export const SEARCH_LIMITS = {
  min: 1,
  max: 100,
  default: 20,
  defaultSingleMode: 30,
} as const

/** Rerank configuration defaults */
export const RERANK_DEFAULTS = {
  /** Default number of top results after reranking */
  topN: 3,
  /** Maximum top_n value */
  maxTopN: 20,
  /** Default hybrid limit (candidates for reranking) */
  hybridLimit: 20,
} as const

// =============================================================================
// Rerank-specific types for dedicated rerank endpoint
// =============================================================================

/** Request model for dedicated rerank search endpoint */
export interface RerankSearchRequest {
  /** Search query text (1-1000 chars) */
  query: string
  /** Number of hybrid search candidates (1-100, default 20) */
  limit?: number
  /** Number of top results after reranking (1-20, default 3) */
  topN?: number
  /** Weight for BM25 keyword search (0.0-2.0) */
  bm25Weight?: number
  /** Weight for semantic similarity search (0.0-2.0) */
  semanticWeight?: number
}

/** Reranked search result extending SearchResult */
export interface RerankedSearchResult extends SearchResult {
  /** Cohere relevance score (0.0-1.0). Null if fallback to RRF. */
  relevanceScore: number | null
}

/** Metadata for reranked search results */
export interface RerankedSearchMeta {
  /** Original search query */
  query: string
  /** Matter UUID searched */
  matterId: string
  /** Total candidates from hybrid search before reranking */
  totalCandidates: number
  /** BM25 weight used */
  bm25Weight: number
  /** Semantic weight used */
  semanticWeight: number
  /** True if Cohere reranking was successful, false if fallback to RRF */
  rerankUsed: boolean
  /** Reason for fallback if rerankUsed is false */
  fallbackReason: string | null
}

/** Response model for reranked search */
export interface RerankedSearchResponse {
  /** Reranked search results */
  data: RerankedSearchResult[]
  /** Search metadata */
  meta: RerankedSearchMeta
}
