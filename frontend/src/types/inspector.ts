/**
 * Inspector/Debug Types
 *
 * Type definitions for the RAG pipeline inspector/debug functionality.
 *
 * Story: RAG Production Gaps - Feature 3: Inspector Mode
 */

/**
 * Timing breakdown for search operations.
 */
export interface TimingBreakdown {
  /** Time to generate query embedding */
  embeddingMs: number | null;
  /** BM25 search time */
  bm25SearchMs: number | null;
  /** Semantic/vector search time */
  semanticSearchMs: number | null;
  /** RRF score fusion time */
  rrfFusionMs: number | null;
  /** Cohere reranking time */
  rerankMs: number | null;
  /** Total search time */
  totalMs: number;
}

/**
 * Debug information for a single chunk result.
 */
export interface ChunkDebugInfo {
  /** Chunk UUID */
  chunkId: string;
  /** Document UUID */
  documentId: string;
  /** Document filename */
  documentName: string | null;
  /** Page number */
  pageNumber: number | null;
  /** parent or child */
  chunkType: string;
  /** Position in BM25 results (1-indexed) */
  bm25Rank: number | null;
  /** Raw BM25 score */
  bm25Score: number | null;
  /** Position in semantic results (1-indexed) */
  semanticRank: number | null;
  /** Cosine similarity score (0-1) */
  semanticScore: number | null;
  /** Combined RRF score */
  rrfScore: number;
  /** Position after RRF fusion (1-indexed) */
  rrfRank: number;
  /** Cohere relevance score (0-1) */
  rerankScore: number | null;
  /** Position after reranking (1-indexed) */
  rerankRank: number | null;
  /** First 200 chars of content */
  contentPreview: string;
  /** Number of tokens */
  tokenCount: number;
}

/**
 * Full debug information for a search operation.
 */
export interface SearchDebugInfo {
  /** Timing breakdown */
  timing: TimingBreakdown;
  /** Original query */
  query: string;
  /** Query after alias expansion */
  expandedQuery: string | null;
  /** Embedding model used */
  embeddingModel: string;
  /** BM25 weight */
  bm25Weight: number;
  /** Semantic weight */
  semanticWeight: number;
  /** Top K for BM25 */
  topKBm25: number;
  /** Top K for semantic */
  topKSemantic: number;
  /** RRF k constant */
  kConstant: number;
  /** Was reranking requested */
  rerankRequested: boolean;
  /** Was reranking actually used */
  rerankUsed: boolean;
  /** Reranking model */
  rerankModel: string | null;
  /** Top N after reranking */
  rerankTopN: number | null;
  /** Why reranking failed/skipped */
  rerankFallbackReason: string | null;
  /** Results from BM25 */
  bm25ResultsCount: number;
  /** Results from semantic */
  semanticResultsCount: number;
  /** Results after fusion */
  fusedResultsCount: number;
  /** Final results returned */
  finalResultsCount: number;
  /** Debug info per chunk */
  chunks: ChunkDebugInfo[];
}

/**
 * API response format for search debug info (snake_case).
 */
export interface SearchDebugInfoAPI {
  timing: {
    embedding_ms: number | null;
    bm25_search_ms: number | null;
    semantic_search_ms: number | null;
    rrf_fusion_ms: number | null;
    rerank_ms: number | null;
    total_ms: number;
  };
  query: string;
  expanded_query: string | null;
  embedding_model: string;
  bm25_weight: number;
  semantic_weight: number;
  top_k_bm25: number;
  top_k_semantic: number;
  k_constant: number;
  rerank_requested: boolean;
  rerank_used: boolean;
  rerank_model: string | null;
  rerank_top_n: number | null;
  rerank_fallback_reason: string | null;
  bm25_results_count: number;
  semantic_results_count: number;
  fused_results_count: number;
  final_results_count: number;
  chunks: Array<{
    chunk_id: string;
    document_id: string;
    document_name: string | null;
    page_number: number | null;
    chunk_type: string;
    bm25_rank: number | null;
    bm25_score: number | null;
    semantic_rank: number | null;
    semantic_score: number | null;
    rrf_score: number;
    rrf_rank: number;
    rerank_score: number | null;
    rerank_rank: number | null;
    content_preview: string;
    token_count: number;
  }>;
}

/**
 * Transform API response to frontend format.
 */
export function transformSearchDebugInfo(api: SearchDebugInfoAPI): SearchDebugInfo {
  return {
    timing: {
      embeddingMs: api.timing.embedding_ms,
      bm25SearchMs: api.timing.bm25_search_ms,
      semanticSearchMs: api.timing.semantic_search_ms,
      rrfFusionMs: api.timing.rrf_fusion_ms,
      rerankMs: api.timing.rerank_ms,
      totalMs: api.timing.total_ms,
    },
    query: api.query,
    expandedQuery: api.expanded_query,
    embeddingModel: api.embedding_model,
    bm25Weight: api.bm25_weight,
    semanticWeight: api.semantic_weight,
    topKBm25: api.top_k_bm25,
    topKSemantic: api.top_k_semantic,
    kConstant: api.k_constant,
    rerankRequested: api.rerank_requested,
    rerankUsed: api.rerank_used,
    rerankModel: api.rerank_model,
    rerankTopN: api.rerank_top_n,
    rerankFallbackReason: api.rerank_fallback_reason,
    bm25ResultsCount: api.bm25_results_count,
    semanticResultsCount: api.semantic_results_count,
    fusedResultsCount: api.fused_results_count,
    finalResultsCount: api.final_results_count,
    chunks: api.chunks.map((chunk) => ({
      chunkId: chunk.chunk_id,
      documentId: chunk.document_id,
      documentName: chunk.document_name,
      pageNumber: chunk.page_number,
      chunkType: chunk.chunk_type,
      bm25Rank: chunk.bm25_rank,
      bm25Score: chunk.bm25_score,
      semanticRank: chunk.semantic_rank,
      semanticScore: chunk.semantic_score,
      rrfScore: chunk.rrf_score,
      rrfRank: chunk.rrf_rank,
      rerankScore: chunk.rerank_score,
      rerankRank: chunk.rerank_rank,
      contentPreview: chunk.content_preview,
      tokenCount: chunk.token_count,
    })),
  };
}

/**
 * Inspector status response.
 */
export interface InspectorStatus {
  inspectorEnabled: boolean;
  autoEvaluationEnabled: boolean;
  tableExtractionEnabled: boolean;
}

/**
 * Inspector status API response (snake_case).
 */
export interface InspectorStatusAPI {
  data: {
    inspector_enabled: boolean;
    auto_evaluation_enabled: boolean;
    table_extraction_enabled: boolean;
  };
}

/**
 * Transform inspector status response.
 */
export function transformInspectorStatus(api: InspectorStatusAPI): InspectorStatus {
  return {
    inspectorEnabled: api.data.inspector_enabled,
    autoEvaluationEnabled: api.data.auto_evaluation_enabled,
    tableExtractionEnabled: api.data.table_extraction_enabled,
  };
}
