/**
 * Matter Cost API Client
 *
 * Story 7.1: Per-Matter Cost Tracking Widget
 *
 * API functions for retrieving per-matter cost data.
 * Note: This is a utility module, not a React component - no 'use client' needed.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface CostByOperation {
  operation: string;
  costInr: number;
  costUsd: number;
  inputTokens: number;
  outputTokens: number;
  operationCount: number;
}

export interface CostByProvider {
  provider: string;
  costInr: number;
  costUsd: number;
  inputTokens: number;
  outputTokens: number;
  operationCount: number;
}

export interface DailyCost {
  date: string;
  costInr: number;
  costUsd: number;
}

export interface MatterCostSummary {
  matterId: string;
  periodDays: number;
  totalCostInr: number;
  totalCostUsd: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  operationCount: number;
  byOperation: CostByOperation[];
  byProvider: CostByProvider[];
  dailyCosts: DailyCost[];
  weeklyCostInr: number;
  weeklyCostUsd: number;
}

export interface MatterCostResponse {
  data: MatterCostSummary;
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

function transformCostByOperation(data: Record<string, unknown>): CostByOperation {
  return {
    operation: toString(data.operation ?? data.operation_type, 'Unknown'),
    costInr: toNumber(data.costInr ?? data.cost_inr),
    costUsd: toNumber(data.costUsd ?? data.cost_usd),
    inputTokens: toNumber(data.inputTokens ?? data.input_tokens),
    outputTokens: toNumber(data.outputTokens ?? data.output_tokens),
    operationCount: toNumber(data.operationCount ?? data.operation_count),
  };
}

function transformCostByProvider(data: Record<string, unknown>): CostByProvider {
  return {
    provider: toString(data.provider, 'Unknown'),
    costInr: toNumber(data.costInr ?? data.cost_inr),
    costUsd: toNumber(data.costUsd ?? data.cost_usd),
    inputTokens: toNumber(data.inputTokens ?? data.input_tokens),
    outputTokens: toNumber(data.outputTokens ?? data.output_tokens),
    operationCount: toNumber(data.operationCount ?? data.operation_count),
  };
}

function transformDailyCost(data: Record<string, unknown>): DailyCost {
  return {
    date: toString(data.date),
    costInr: toNumber(data.costInr ?? data.cost_inr),
    costUsd: toNumber(data.costUsd ?? data.cost_usd),
  };
}

function transformMatterCostSummary(data: Record<string, unknown>): MatterCostSummary {
  const byOperation = (data.byOperation ?? data.by_operation ?? []) as Array<Record<string, unknown>>;
  const byProvider = (data.byProvider ?? data.by_provider ?? []) as Array<Record<string, unknown>>;
  const dailyCosts = (data.dailyCosts ?? data.daily_costs ?? []) as Array<Record<string, unknown>>;

  return {
    matterId: toString(data.matterId ?? data.matter_id),
    periodDays: toNumber(data.periodDays ?? data.period_days, 30),
    totalCostInr: toNumber(data.totalCostInr ?? data.total_cost_inr),
    totalCostUsd: toNumber(data.totalCostUsd ?? data.total_cost_usd),
    totalInputTokens: toNumber(data.totalInputTokens ?? data.total_input_tokens),
    totalOutputTokens: toNumber(data.totalOutputTokens ?? data.total_output_tokens),
    operationCount: toNumber(data.operationCount ?? data.operation_count),
    byOperation: byOperation.map(transformCostByOperation),
    byProvider: byProvider.map(transformCostByProvider),
    dailyCosts: dailyCosts.map(transformDailyCost),
    weeklyCostInr: toNumber(data.weeklyCostInr ?? data.weekly_cost_inr),
    weeklyCostUsd: toNumber(data.weeklyCostUsd ?? data.weekly_cost_usd),
  };
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get cost summary for a matter.
 *
 * Story 7.1: Per-Matter Cost Tracking Widget
 *
 * @param matterId - Matter UUID
 * @param days - Number of days to include (default 30)
 * @returns Cost summary data
 */
export async function getMatterCosts(
  matterId: string,
  days: number = 30
): Promise<MatterCostSummary> {
  const response = await api.get<{ data: Record<string, unknown> }>(
    `/api/matters/${matterId}/costs?days=${days}`
  );

  return transformMatterCostSummary(response.data);
}

// =============================================================================
// Exported API Object
// =============================================================================

export const costsApi = {
  getMatterCosts,
};
