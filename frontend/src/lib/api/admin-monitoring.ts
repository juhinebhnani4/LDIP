'use client';

/**
 * Admin Chunk Metrics & Monitoring API Client
 *
 * Gap 7: Vector Quantization — Chunk Count Monitoring
 *
 * API functions for admin-only chunk metrics monitoring.
 * Provides endpoints for:
 * - Getting per-matter and global chunk count metrics
 * - Alert status for vector quantization planning
 * - HNSW index configuration info
 *
 * Note: These operations require admin permissions.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface MatterChunkMetrics {
  matterId: string;
  matterTitle: string;
  totalChunks: number;
  parentChunks: number;
  childChunks: number;
  tableChunks: number;
  hasVoyageEmbeddings: number;
  exceedsThreshold: boolean;
}

export interface GlobalChunkMetrics {
  totalChunks: number;
  totalWithEmbedding: number;
  totalWithVoyage: number;
  totalMatters: number;
  exceedsGlobalThreshold: boolean;
  globalThreshold: number;
}

export interface IndexConfig {
  m: number;
  efConstruction: number;
  efSearch: number;
  vectorDimensions: {
    openai: number;
    voyage: number;
  };
  quantization: string;
  recommendation: string;
}

export interface ChunkMetricsData {
  global: GlobalChunkMetrics;
  matters: MatterChunkMetrics[];
  thresholds: {
    perMatter: number;
    global: number;
  };
  indexConfig: IndexConfig;
  alertsTriggered: boolean;
  lastUpdated: string;
}

// =============================================================================
// Response Transformers (Runtime type validation)
// =============================================================================

function toNumber(value: unknown, fallback: number = 0): number {
  if (typeof value === 'number' && !Number.isNaN(value)) return value;
  if (typeof value === 'string') {
    const parsed = parseFloat(value);
    return Number.isNaN(parsed) ? fallback : parsed;
  }
  return fallback;
}

function toString(value: unknown, fallback: string = ''): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return fallback;
  return String(value);
}

function toBoolean(value: unknown, fallback: boolean = false): boolean {
  if (typeof value === 'boolean') return value;
  if (value === 'true') return true;
  if (value === 'false') return false;
  return fallback;
}

function transformMatterMetrics(data: Record<string, unknown>): MatterChunkMetrics {
  return {
    matterId: toString(data.matterId ?? data.matter_id),
    matterTitle: toString(data.matterTitle ?? data.matter_title, 'Untitled'),
    totalChunks: toNumber(data.totalChunks ?? data.total_chunks),
    parentChunks: toNumber(data.parentChunks ?? data.parent_chunks),
    childChunks: toNumber(data.childChunks ?? data.child_chunks),
    tableChunks: toNumber(data.tableChunks ?? data.table_chunks),
    hasVoyageEmbeddings: toNumber(data.hasVoyageEmbeddings ?? data.has_voyage_embeddings),
    exceedsThreshold: toBoolean(data.exceedsThreshold ?? data.exceeds_threshold),
  };
}

function transformGlobalMetrics(data: Record<string, unknown>): GlobalChunkMetrics {
  return {
    totalChunks: toNumber(data.totalChunks ?? data.total_chunks),
    totalWithEmbedding: toNumber(data.totalWithEmbedding ?? data.total_with_embedding),
    totalWithVoyage: toNumber(data.totalWithVoyage ?? data.total_with_voyage),
    totalMatters: toNumber(data.totalMatters ?? data.total_matters),
    exceedsGlobalThreshold: toBoolean(data.exceedsGlobalThreshold ?? data.exceeds_global_threshold),
    globalThreshold: toNumber(data.globalThreshold ?? data.global_threshold, 500000),
  };
}

function transformIndexConfig(data: Record<string, unknown>): IndexConfig {
  const dims = (data.vectorDimensions ?? data.vector_dimensions ?? {}) as Record<string, unknown>;
  return {
    m: toNumber(data.m, 16),
    efConstruction: toNumber(data.efConstruction ?? data.ef_construction, 128),
    efSearch: toNumber(data.efSearch ?? data.ef_search, 80),
    vectorDimensions: {
      openai: toNumber(dims.openai, 1536),
      voyage: toNumber(dims.voyage, 1024),
    },
    quantization: toString(data.quantization, 'float32'),
    recommendation: toString(data.recommendation, 'No data'),
  };
}

function transformChunkMetricsData(data: Record<string, unknown>): ChunkMetricsData {
  const globalData = (data.global ?? {}) as Record<string, unknown>;
  const mattersData = (data.matters ?? []) as Array<Record<string, unknown>>;
  const thresholdsData = (data.thresholds ?? {}) as Record<string, unknown>;
  const indexData = (data.indexConfig ?? data.index_config ?? {}) as Record<string, unknown>;

  return {
    global: transformGlobalMetrics(globalData),
    matters: mattersData.map(transformMatterMetrics),
    thresholds: {
      perMatter: toNumber(thresholdsData.perMatter ?? thresholdsData.per_matter, 50000),
      global: toNumber(thresholdsData.global, 500000),
    },
    indexConfig: transformIndexConfig(indexData),
    alertsTriggered: toBoolean(data.alertsTriggered ?? data.alerts_triggered),
    lastUpdated: toString(data.lastUpdated ?? data.last_updated, new Date().toISOString()),
  };
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get chunk count metrics for all matters and global totals.
 *
 * Gap 7: Vector Quantization — Monitoring Dashboard
 *
 * @returns Chunk metrics data with per-matter and global breakdowns
 */
export async function getChunkMetrics(): Promise<ChunkMetricsData> {
  const response = await api.get<Record<string, unknown>>(
    '/api/admin/chunk-metrics'
  );

  return transformChunkMetricsData(response);
}

// =============================================================================
// Exported API Object
// =============================================================================

export const adminMonitoringApi = {
  getChunkMetrics,
};
