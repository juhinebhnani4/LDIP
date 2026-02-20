'use client';

/**
 * A/B Testing API Client
 *
 * Gap 10: Automated Voyage A/B Testing
 *
 * API functions for managing provider comparison experiments.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface ABTestScores {
  context_recall: number | null;
  faithfulness: number | null;
  answer_relevancy: number | null;
  overall: number | null;
  count: number;
}

export interface StatisticalTest {
  t_statistic: number;
  p_value_approx: number;
  degrees_of_freedom: number;
  effect_size_cohens_d: number;
  mean_a: number;
  mean_b: number;
  std_a: number;
  std_b: number;
}

export interface ABTestRun {
  id: string;
  matterId: string;
  status: string;
  controlEmbedding: string;
  controlReranker: string;
  treatmentEmbedding: string;
  treatmentReranker: string;
  controlJobId: string | null;
  treatmentJobId: string | null;
  controlScores: ABTestScores | null;
  treatmentScores: ABTestScores | null;
  controlLatencyP50: number | null;
  controlLatencyP95: number | null;
  treatmentLatencyP50: number | null;
  treatmentLatencyP95: number | null;
  controlCostUsd: number;
  treatmentCostUsd: number;
  decision: string | null;
  decisionConfidence: number | null;
  decisionReasoning: string | null;
  statisticalTest: StatisticalTest | null;
  goldenItemCount: number | null;
  createdAt: string;
  completedAt: string | null;
}

export interface ABTestStatus {
  enabled: boolean;
  trafficPercentage: number;
  autoPromoteEnabled: boolean;
  minSamples: number;
  latestRun: ABTestRun | null;
  running: { id: string; status: string; createdAt: string; matterId: string } | null;
  totalCompletedRuns: number;
}

// =============================================================================
// Transformers (snake_case → camelCase with null safety)
// =============================================================================

function toNum(v: unknown, fallback = 0): number {
  if (typeof v === 'number' && !Number.isNaN(v)) return v;
  if (typeof v === 'string') {
    const p = parseFloat(v);
    return Number.isNaN(p) ? fallback : p;
  }
  return fallback;
}

function toStr(v: unknown, fallback = ''): string {
  return typeof v === 'string' ? v : (v == null ? fallback : String(v));
}

function toBool(v: unknown, fallback = false): boolean {
  return typeof v === 'boolean' ? v : fallback;
}

function transformScores(data: Record<string, unknown> | null): ABTestScores | null {
  if (!data) return null;
  return {
    context_recall: data.context_recall != null ? toNum(data.context_recall) : null,
    faithfulness: data.faithfulness != null ? toNum(data.faithfulness) : null,
    answer_relevancy: data.answer_relevancy != null ? toNum(data.answer_relevancy) : null,
    overall: data.overall != null ? toNum(data.overall) : null,
    count: toNum(data.count),
  };
}

function transformStatisticalTest(data: Record<string, unknown> | null): StatisticalTest | null {
  if (!data) return null;
  return {
    t_statistic: toNum(data.t_statistic),
    p_value_approx: toNum(data.p_value_approx),
    degrees_of_freedom: toNum(data.degrees_of_freedom),
    effect_size_cohens_d: toNum(data.effect_size_cohens_d),
    mean_a: toNum(data.mean_a),
    mean_b: toNum(data.mean_b),
    std_a: toNum(data.std_a),
    std_b: toNum(data.std_b),
  };
}

function transformRun(data: Record<string, unknown>): ABTestRun {
  return {
    id: toStr(data.id),
    matterId: toStr(data.matter_id),
    status: toStr(data.status),
    controlEmbedding: toStr(data.control_embedding, 'openai'),
    controlReranker: toStr(data.control_reranker, 'cohere'),
    treatmentEmbedding: toStr(data.treatment_embedding, 'voyage'),
    treatmentReranker: toStr(data.treatment_reranker, 'voyage'),
    controlJobId: data.control_job_id ? toStr(data.control_job_id) : null,
    treatmentJobId: data.treatment_job_id ? toStr(data.treatment_job_id) : null,
    controlScores: transformScores(data.control_scores as Record<string, unknown> | null),
    treatmentScores: transformScores(data.treatment_scores as Record<string, unknown> | null),
    controlLatencyP50: data.control_latency_p50_ms != null ? toNum(data.control_latency_p50_ms) : null,
    controlLatencyP95: data.control_latency_p95_ms != null ? toNum(data.control_latency_p95_ms) : null,
    treatmentLatencyP50: data.treatment_latency_p50_ms != null ? toNum(data.treatment_latency_p50_ms) : null,
    treatmentLatencyP95: data.treatment_latency_p95_ms != null ? toNum(data.treatment_latency_p95_ms) : null,
    controlCostUsd: toNum(data.control_cost_usd),
    treatmentCostUsd: toNum(data.treatment_cost_usd),
    decision: data.decision ? toStr(data.decision) : null,
    decisionConfidence: data.decision_confidence != null ? toNum(data.decision_confidence) : null,
    decisionReasoning: data.decision_reasoning ? toStr(data.decision_reasoning) : null,
    statisticalTest: transformStatisticalTest(data.statistical_test as Record<string, unknown> | null),
    goldenItemCount: data.golden_item_count != null ? toNum(data.golden_item_count) : null,
    createdAt: toStr(data.created_at),
    completedAt: data.completed_at ? toStr(data.completed_at) : null,
  };
}

function transformStatus(data: Record<string, unknown>): ABTestStatus {
  const latestRaw = data.latest_run as Record<string, unknown> | null;
  const runningRaw = data.running as Record<string, unknown> | null;

  return {
    enabled: toBool(data.enabled),
    trafficPercentage: toNum(data.traffic_percentage),
    autoPromoteEnabled: toBool(data.auto_promote_enabled),
    minSamples: toNum(data.min_samples, 20),
    latestRun: latestRaw ? transformRun(latestRaw) : null,
    running: runningRaw ? {
      id: toStr(runningRaw.id),
      status: toStr(runningRaw.status),
      createdAt: toStr(runningRaw.created_at),
      matterId: toStr(runningRaw.matter_id),
    } : null,
    totalCompletedRuns: toNum(data.total_completed_runs),
  };
}

// =============================================================================
// API Functions
// =============================================================================

export async function getABTestStatus(): Promise<ABTestStatus> {
  const response = await api.get<{ data: Record<string, unknown> }>('/api/ab-testing/status');
  return transformStatus(response.data);
}

export async function getABTestRuns(matterId?: string): Promise<ABTestRun[]> {
  const params = matterId ? `?matter_id=${matterId}` : '';
  const response = await api.get<{ data: Array<Record<string, unknown>> }>(`/api/ab-testing/runs${params}`);
  return (response.data || []).map(transformRun);
}

export async function getABTestRun(runId: string): Promise<ABTestRun> {
  const response = await api.get<{ data: Record<string, unknown> }>(`/api/ab-testing/runs/${runId}`);
  return transformRun(response.data);
}

export async function triggerABComparison(
  matterId: string,
  tags?: string[],
): Promise<{ runId: string; taskId: string }> {
  const response = await api.post<{ data: Record<string, unknown> }>('/api/ab-testing/compare', {
    matter_id: matterId,
    tags: tags || null,
  });
  return {
    runId: toStr(response.data.run_id),
    taskId: toStr(response.data.task_id),
  };
}

export const abTestingApi = {
  getStatus: getABTestStatus,
  getRuns: getABTestRuns,
  getRun: getABTestRun,
  triggerComparison: triggerABComparison,
};
