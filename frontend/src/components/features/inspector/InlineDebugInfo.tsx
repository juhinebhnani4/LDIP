'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Clock, Zap, Search, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { SearchDebugInfo, ChunkDebugInfo } from '@/types/inspector';

interface InlineDebugInfoProps {
  /** Debug information to display */
  debugInfo: SearchDebugInfo;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Inline Debug Info Display
 *
 * Compact, collapsible display of search debug information
 * that can be shown inline with chat messages.
 *
 * Story: RAG Production Gaps - Feature 3: Inspector Mode
 */
export function InlineDebugInfo({ debugInfo, className }: InlineDebugInfoProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        'mt-2 rounded-md border border-amber-200 bg-amber-50 text-xs',
        className
      )}
    >
      {/* Compact header - always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-left"
      >
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1 font-medium text-amber-800">
            <Clock className="h-3 w-3" />
            {debugInfo.timing.totalMs.toFixed(0)}ms
          </span>
          <span className="text-amber-600">
            BM25: {debugInfo.bm25ResultsCount} | Semantic: {debugInfo.semanticResultsCount}
          </span>
          {debugInfo.rerankUsed && (
            <span className="flex items-center gap-1 text-amber-600">
              <Sparkles className="h-3 w-3" />
              Reranked
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-amber-600" />
        ) : (
          <ChevronDown className="h-4 w-4 text-amber-600" />
        )}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-amber-200 px-3 py-2">
          {/* Timing breakdown */}
          <div className="mb-3">
            <h4 className="mb-1 font-medium text-amber-800">Timing Breakdown</h4>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-amber-700">
              {debugInfo.timing.embeddingMs !== null && (
                <div>Embedding: {debugInfo.timing.embeddingMs.toFixed(1)}ms</div>
              )}
              {debugInfo.timing.bm25SearchMs !== null && (
                <div>BM25: {debugInfo.timing.bm25SearchMs.toFixed(1)}ms</div>
              )}
              {debugInfo.timing.semanticSearchMs !== null && (
                <div>Semantic: {debugInfo.timing.semanticSearchMs.toFixed(1)}ms</div>
              )}
              {debugInfo.timing.rrfFusionMs !== null && (
                <div>RRF Fusion: {debugInfo.timing.rrfFusionMs.toFixed(1)}ms</div>
              )}
              {debugInfo.timing.rerankMs !== null && (
                <div>Rerank: {debugInfo.timing.rerankMs.toFixed(1)}ms</div>
              )}
            </div>
          </div>

          {/* Search config */}
          <div className="mb-3">
            <h4 className="mb-1 font-medium text-amber-800">Configuration</h4>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-amber-700">
              <div>BM25 Weight: {debugInfo.bm25Weight}</div>
              <div>Semantic Weight: {debugInfo.semanticWeight}</div>
              <div>Model: {debugInfo.embeddingModel}</div>
              <div>K Constant: {debugInfo.kConstant}</div>
              {debugInfo.rerankModel && <div>Rerank: {debugInfo.rerankModel}</div>}
              {debugInfo.rerankFallbackReason && (
                <div className="col-span-2 text-amber-600">
                  Rerank fallback: {debugInfo.rerankFallbackReason}
                </div>
              )}
            </div>
          </div>

          {/* Per-chunk details */}
          {debugInfo.chunks.length > 0 && (
            <div>
              <h4 className="mb-1 font-medium text-amber-800">
                Top Chunks ({debugInfo.chunks.length})
              </h4>
              <div className="max-h-48 overflow-y-auto">
                <table className="w-full text-amber-700">
                  <thead>
                    <tr className="border-b border-amber-200">
                      <th className="px-1 py-1 text-left">#</th>
                      <th className="px-1 py-1 text-left">BM25</th>
                      <th className="px-1 py-1 text-left">Semantic</th>
                      <th className="px-1 py-1 text-left">RRF</th>
                      {debugInfo.rerankUsed && (
                        <th className="px-1 py-1 text-left">Rerank</th>
                      )}
                      <th className="px-1 py-1 text-left">Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {debugInfo.chunks.map((chunk, idx) => (
                      <ChunkRow
                        key={chunk.chunkId}
                        chunk={chunk}
                        index={idx}
                        showRerank={debugInfo.rerankUsed}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ChunkRowProps {
  chunk: ChunkDebugInfo;
  index: number;
  showRerank: boolean;
}

function ChunkRow({ chunk, index, showRerank }: ChunkRowProps) {
  return (
    <tr className="border-b border-amber-100 last:border-0">
      <td className="px-1 py-1">{index + 1}</td>
      <td className="px-1 py-1">
        {chunk.bm25Rank !== null ? (
          <span className="font-mono">#{chunk.bm25Rank}</span>
        ) : (
          <span className="text-amber-400">—</span>
        )}
      </td>
      <td className="px-1 py-1">
        {chunk.semanticRank !== null ? (
          <span className="font-mono">
            #{chunk.semanticRank}
            {chunk.semanticScore !== null && (
              <span className="ml-1 text-amber-500">
                ({(chunk.semanticScore * 100).toFixed(0)}%)
              </span>
            )}
          </span>
        ) : (
          <span className="text-amber-400">—</span>
        )}
      </td>
      <td className="px-1 py-1">
        <span className="font-mono">{chunk.rrfScore.toFixed(4)}</span>
      </td>
      {showRerank && (
        <td className="px-1 py-1">
          {chunk.rerankScore !== null ? (
            <span className="font-mono">
              {(chunk.rerankScore * 100).toFixed(0)}%
            </span>
          ) : (
            <span className="text-amber-400">—</span>
          )}
        </td>
      )}
      <td className="max-w-xs truncate px-1 py-1" title={chunk.contentPreview}>
        {chunk.contentPreview.slice(0, 50)}...
      </td>
    </tr>
  );
}
