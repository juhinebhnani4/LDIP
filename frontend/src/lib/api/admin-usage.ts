'use client';

/**
 * Admin Usage Dashboard API Client
 *
 * API functions for the usage dashboard (OpenAI-style cost tracking).
 * Requires admin permissions.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface DailyUsage {
  date: string;
  spendUsd: number;
  spendInr: number;
  requests: number;
  tokens: number;
}

export interface ProviderUsage {
  provider: string;
  spendUsd: number;
  spendInr: number;
  requests: number;
  inputTokens: number;
  outputTokens: number;
}

export interface OperationUsage {
  operation: string;
  spendUsd: number;
  spendInr: number;
  requests: number;
  inputTokens: number;
  outputTokens: number;
}

export interface MatterUsage {
  matterId: string;
  spendUsd: number;
  spendInr: number;
  requests: number;
}

export interface UsageDashboardData {
  month: string;
  totalSpendUsd: number;
  totalSpendInr: number;
  budgetUsd: number;
  totalTokens: number;
  totalRequests: number;
  dailySpend: DailyUsage[];
  byProvider: ProviderUsage[];
  byOperation: OperationUsage[];
  byMatter: MatterUsage[];
}

// =============================================================================
// Transformers
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

function transformDailyUsage(d: Record<string, unknown>): DailyUsage {
  return {
    date: toString(d.date),
    spendUsd: toNumber(d.spendUsd ?? d.spend_usd),
    spendInr: toNumber(d.spendInr ?? d.spend_inr),
    requests: toNumber(d.requests),
    tokens: toNumber(d.tokens),
  };
}

function transformProviderUsage(d: Record<string, unknown>): ProviderUsage {
  return {
    provider: toString(d.provider, 'unknown'),
    spendUsd: toNumber(d.spendUsd ?? d.spend_usd),
    spendInr: toNumber(d.spendInr ?? d.spend_inr),
    requests: toNumber(d.requests),
    inputTokens: toNumber(d.inputTokens ?? d.input_tokens),
    outputTokens: toNumber(d.outputTokens ?? d.output_tokens),
  };
}

function transformOperationUsage(d: Record<string, unknown>): OperationUsage {
  return {
    operation: toString(d.operation, 'unknown'),
    spendUsd: toNumber(d.spendUsd ?? d.spend_usd),
    spendInr: toNumber(d.spendInr ?? d.spend_inr),
    requests: toNumber(d.requests),
    inputTokens: toNumber(d.inputTokens ?? d.input_tokens),
    outputTokens: toNumber(d.outputTokens ?? d.output_tokens),
  };
}

function transformMatterUsage(d: Record<string, unknown>): MatterUsage {
  return {
    matterId: toString(d.matterId ?? d.matter_id),
    spendUsd: toNumber(d.spendUsd ?? d.spend_usd),
    spendInr: toNumber(d.spendInr ?? d.spend_inr),
    requests: toNumber(d.requests),
  };
}

function transformUsageDashboard(data: Record<string, unknown>): UsageDashboardData {
  return {
    month: toString(data.month),
    totalSpendUsd: toNumber(data.totalSpendUsd ?? data.total_spend_usd),
    totalSpendInr: toNumber(data.totalSpendInr ?? data.total_spend_inr),
    budgetUsd: toNumber(data.budgetUsd ?? data.budget_usd),
    totalTokens: toNumber(data.totalTokens ?? data.total_tokens),
    totalRequests: toNumber(data.totalRequests ?? data.total_requests),
    dailySpend: ((data.dailySpend ?? data.daily_spend ?? []) as Array<Record<string, unknown>>).map(transformDailyUsage),
    byProvider: ((data.byProvider ?? data.by_provider ?? []) as Array<Record<string, unknown>>).map(transformProviderUsage),
    byOperation: ((data.byOperation ?? data.by_operation ?? []) as Array<Record<string, unknown>>).map(transformOperationUsage),
    byMatter: ((data.byMatter ?? data.by_matter ?? []) as Array<Record<string, unknown>>).map(transformMatterUsage),
  };
}

// =============================================================================
// API
// =============================================================================

export async function getUsageDashboard(
  year?: number,
  month?: number,
): Promise<UsageDashboardData> {
  const params = new URLSearchParams();
  if (year) params.set('year', String(year));
  if (month) params.set('month', String(month));

  const queryString = params.toString();
  const endpoint = queryString
    ? `/api/admin/usage?${queryString}`
    : '/api/admin/usage';

  const response = await api.get<Record<string, unknown>>(endpoint);
  return transformUsageDashboard(response);
}

export const adminUsageApi = {
  getUsageDashboard,
};
