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
// Gap 9: Quality Metrics Types + API
// =============================================================================

export interface MatterQualityMetrics {
  matterId: string;
  matterTitle: string;
  // Latest batch scores
  latestOverall: number | null;
  latestFaithfulness: number | null;
  latestRelevancy: number | null;
  latestRecall: number | null;
  latestEvalDate: string | null;
  latestJobId: string | null;
  latestEvalCount: number;
  // Baseline comparison
  baselineOverall: number | null;
  baselineDate: string | null;
  baselineItemCount: number;
  // Delta and regression
  overallDelta: number | null;
  hasRegression: boolean;
  // Coverage
  goldenItemCount: number;
  // Frequency
  totalEvals30d: number;
  lastEvalAgeHours: number | null;
}

export interface QualityMetricsSummary {
  totalMatters: number;
  mattersWithRegression: number;
  totalGoldenItems: number;
  mattersWithBaseline: number;
  mattersEvaluatedRecently: number;
}

export interface QualityScheduleConfig {
  enabled: boolean;
  regressionThreshold: number;
  criticalThreshold: number;
  monthlyBudgetUsd: number;
  autoBaseline: boolean;
}

export interface QualityMetricsData {
  matters: MatterQualityMetrics[];
  summary: QualityMetricsSummary;
  schedule: QualityScheduleConfig;
  hasRegressions: boolean;
  lastUpdated: string;
}

// Quality metrics response transformers
function transformMatterQuality(data: Record<string, unknown>): MatterQualityMetrics {
  return {
    matterId: toString(data.matterId ?? data.matter_id),
    matterTitle: toString(data.matterTitle ?? data.matter_title, 'Untitled'),
    latestOverall: data.latestOverall != null ? toNumber(data.latestOverall) : null,
    latestFaithfulness: data.latestFaithfulness != null ? toNumber(data.latestFaithfulness) : null,
    latestRelevancy: data.latestRelevancy != null ? toNumber(data.latestRelevancy) : null,
    latestRecall: data.latestRecall != null ? toNumber(data.latestRecall) : null,
    latestEvalDate: data.latestEvalDate != null ? toString(data.latestEvalDate) : null,
    latestJobId: data.latestJobId != null ? toString(data.latestJobId) : null,
    latestEvalCount: toNumber(data.latestEvalCount ?? data.latest_eval_count),
    baselineOverall: data.baselineOverall != null ? toNumber(data.baselineOverall) : null,
    baselineDate: data.baselineDate != null ? toString(data.baselineDate) : null,
    baselineItemCount: toNumber(data.baselineItemCount ?? data.baseline_item_count),
    overallDelta: data.overallDelta != null ? toNumber(data.overallDelta) : null,
    hasRegression: toBoolean(data.hasRegression ?? data.has_regression),
    goldenItemCount: toNumber(data.goldenItemCount ?? data.golden_item_count),
    totalEvals30d: toNumber(data.totalEvals30d ?? data.total_evals_30d),
    lastEvalAgeHours: data.lastEvalAgeHours != null ? toNumber(data.lastEvalAgeHours) : null,
  };
}

function transformQualityMetricsData(data: Record<string, unknown>): QualityMetricsData {
  const mattersData = (data.matters ?? []) as Array<Record<string, unknown>>;
  const summaryData = (data.summary ?? {}) as Record<string, unknown>;
  const scheduleData = (data.schedule ?? {}) as Record<string, unknown>;

  return {
    matters: mattersData.map(transformMatterQuality),
    summary: {
      totalMatters: toNumber(summaryData.totalMatters ?? summaryData.total_matters),
      mattersWithRegression: toNumber(summaryData.mattersWithRegression ?? summaryData.matters_with_regression),
      totalGoldenItems: toNumber(summaryData.totalGoldenItems ?? summaryData.total_golden_items),
      mattersWithBaseline: toNumber(summaryData.mattersWithBaseline ?? summaryData.matters_with_baseline),
      mattersEvaluatedRecently: toNumber(summaryData.mattersEvaluatedRecently ?? summaryData.matters_evaluated_recently),
    },
    schedule: {
      enabled: toBoolean(scheduleData.enabled),
      regressionThreshold: toNumber(scheduleData.regressionThreshold ?? scheduleData.regression_threshold, 0.10),
      criticalThreshold: toNumber(scheduleData.criticalThreshold ?? scheduleData.critical_threshold, 0.60),
      monthlyBudgetUsd: toNumber(scheduleData.monthlyBudgetUsd ?? scheduleData.monthly_budget_usd, 10),
      autoBaseline: toBoolean(scheduleData.autoBaseline ?? scheduleData.auto_baseline, true),
    },
    hasRegressions: toBoolean(data.hasRegressions ?? data.has_regressions),
    lastUpdated: toString(data.lastUpdated ?? data.last_updated, new Date().toISOString()),
  };
}

/**
 * Get RAG quality metrics for admin monitoring.
 *
 * Gap 9: Automated RAGAS Regression — Quality Monitoring Dashboard
 *
 * @returns Quality metrics with per-matter scores, regression alerts, schedule info
 */
export async function getQualityMetrics(): Promise<QualityMetricsData> {
  const response = await api.get<Record<string, unknown>>(
    '/api/admin/quality-metrics'
  );

  return transformQualityMetricsData(response);
}

// =============================================================================
// Exported API Object
// =============================================================================

export const adminMonitoringApi = {
  getChunkMetrics,
  getQualityMetrics,
};
