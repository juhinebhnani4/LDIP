/**
 * Inspector Hook
 *
 * Hook for interacting with the RAG pipeline inspector API.
 *
 * Story: RAG Production Gaps - Feature 3: Inspector Mode
 */

'use client';

import { useEffect, useCallback } from 'react';
import { useInspectorStore } from '@/stores/inspectorStore';
import type {
  SearchDebugInfo,
  InspectorStatus,
  InspectorStatusAPI,
  SearchDebugInfoAPI,
  transformSearchDebugInfo,
  transformInspectorStatus,
} from '@/types/inspector';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

/**
 * Hook for inspector functionality.
 *
 * @returns Inspector state and actions.
 */
export function useInspector() {
  const debugEnabled = useInspectorStore((state) => state.debugEnabled);
  const inspectorEnabled = useInspectorStore((state) => state.inspectorEnabled);
  const toggleDebug = useInspectorStore((state) => state.toggleDebug);
  const setInspectorStatus = useInspectorStore((state) => state.setInspectorStatus);
  const setLastDebugInfo = useInspectorStore((state) => state.setLastDebugInfo);
  const lastDebugInfo = useInspectorStore((state) => state.lastDebugInfo);

  /**
   * Fetch inspector status from server.
   */
  const fetchInspectorStatus = useCallback(async (accessToken: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/inspector/status`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        console.warn('Failed to fetch inspector status:', response.status);
        return;
      }

      const data: InspectorStatusAPI = await response.json();
      setInspectorStatus({
        inspectorEnabled: data.data.inspector_enabled,
        autoEvaluationEnabled: data.data.auto_evaluation_enabled,
        tableExtractionEnabled: data.data.table_extraction_enabled,
      });
    } catch (error) {
      console.warn('Error fetching inspector status:', error);
    }
  }, [setInspectorStatus]);

  /**
   * Execute search with debug info.
   */
  const searchWithDebug = useCallback(
    async (
      matterId: string,
      query: string,
      accessToken: string,
      options?: {
        limit?: number;
        bm25Weight?: number;
        semanticWeight?: number;
        rerank?: boolean;
        rerankTopN?: number;
        expandAliases?: boolean;
      }
    ): Promise<{
      data: Array<Record<string, unknown>>;
      meta: Record<string, unknown>;
      debug: SearchDebugInfo;
    } | null> => {
      try {
        const response = await fetch(
          `${API_BASE}/api/inspector/matters/${matterId}/search`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${accessToken}`,
            },
            body: JSON.stringify({
              query,
              limit: options?.limit ?? 20,
              bm25_weight: options?.bm25Weight ?? 1.0,
              semantic_weight: options?.semanticWeight ?? 1.0,
              rerank: options?.rerank ?? true,
              rerank_top_n: options?.rerankTopN ?? 5,
              expand_aliases: options?.expandAliases ?? true,
            }),
          }
        );

        if (!response.ok) {
          console.warn('Inspector search failed:', response.status);
          return null;
        }

        const result = await response.json();

        // Transform debug info from API format
        const debugInfo: SearchDebugInfo = {
          timing: {
            embeddingMs: result.debug.timing.embedding_ms,
            bm25SearchMs: result.debug.timing.bm25_search_ms,
            semanticSearchMs: result.debug.timing.semantic_search_ms,
            rrfFusionMs: result.debug.timing.rrf_fusion_ms,
            rerankMs: result.debug.timing.rerank_ms,
            totalMs: result.debug.timing.total_ms,
          },
          query: result.debug.query,
          expandedQuery: result.debug.expanded_query,
          embeddingModel: result.debug.embedding_model,
          bm25Weight: result.debug.bm25_weight,
          semanticWeight: result.debug.semantic_weight,
          topKBm25: result.debug.top_k_bm25,
          topKSemantic: result.debug.top_k_semantic,
          kConstant: result.debug.k_constant,
          rerankRequested: result.debug.rerank_requested,
          rerankUsed: result.debug.rerank_used,
          rerankModel: result.debug.rerank_model,
          rerankTopN: result.debug.rerank_top_n,
          rerankFallbackReason: result.debug.rerank_fallback_reason,
          bm25ResultsCount: result.debug.bm25_results_count,
          semanticResultsCount: result.debug.semantic_results_count,
          fusedResultsCount: result.debug.fused_results_count,
          finalResultsCount: result.debug.final_results_count,
          chunks: result.debug.chunks.map((chunk: Record<string, unknown>) => ({
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

        // Store last debug info
        setLastDebugInfo(debugInfo);

        return {
          data: result.data,
          meta: result.meta,
          debug: debugInfo,
        };
      } catch (error) {
        console.error('Error in inspector search:', error);
        return null;
      }
    },
    [setLastDebugInfo]
  );

  return {
    // State
    debugEnabled,
    inspectorEnabled,
    lastDebugInfo,

    // Actions
    toggleDebug,
    fetchInspectorStatus,
    searchWithDebug,
    setLastDebugInfo,
  };
}
