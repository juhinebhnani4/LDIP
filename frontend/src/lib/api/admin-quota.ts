'use client';

/**
 * Admin LLM Quota API Client
 *
 * Story gap-5.2: LLM Quota Monitoring Dashboard
 *
 * API functions for admin-only LLM quota monitoring.
 * Provides endpoints for:
 * - Getting current LLM quota status and usage
 *
 * Note: These operations require admin permissions.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export type QuotaTrend = 'increasing' | 'decreasing' | 'stable';

export interface ProviderQuota {
  provider: string;
  currentRpm: number;
  rpmLimit: number;
  rpmUsagePct: number;
  dailyTokensUsed: number;
  dailyTokenLimit: number | null;
  dailyCostInr: number;
  dailyCostLimitInr: number | null;
  rateLimitedCount: number;
  projectedExhaustion: string | null;
  trend: QuotaTrend;
  alertTriggered: boolean;
}

export interface LLMQuotaData {
  providers: ProviderQuota[];
  lastUpdated: string;
  alertThresholdPct: number;
  usdToInrRate: number;
}

export interface LLMQuotaResponse {
  data: LLMQuotaData;
}

// =============================================================================
// Response Transformers (F14 fix: Runtime type validation)
// =============================================================================

/** F14 fix: Safely parse a number with fallback */
function toNumber(value: unknown, fallback: number = 0): number {
  if (typeof value === 'number' && !Number.isNaN(value)) return value;
  if (typeof value === 'string') {
    const parsed = parseFloat(value);
    return Number.isNaN(parsed) ? fallback : parsed;
  }
  return fallback;
}

/** F14 fix: Safely parse a nullable number */
function toNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const num = toNumber(value, NaN);
  return Number.isNaN(num) ? null : num;
}

/** F14 fix: Safely parse a string with fallback */
function toString(value: unknown, fallback: string = ''): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return fallback;
  return String(value);
}

/** F14 fix: Safely parse a boolean with fallback */
function toBoolean(value: unknown, fallback: boolean = false): boolean {
  if (typeof value === 'boolean') return value;
  if (value === 'true') return true;
  if (value === 'false') return false;
  return fallback;
}

/** F14 fix: Safely parse trend enum */
function toTrend(value: unknown): QuotaTrend {
  if (value === 'increasing' || value === 'decreasing' || value === 'stable') {
    return value;
  }
  return 'stable';
}

function transformProviderQuota(data: Record<string, unknown>): ProviderQuota {
  return {
    provider: toString(data.provider, 'unknown'),
    currentRpm: toNumber(data.currentRpm ?? data.current_rpm),
    rpmLimit: toNumber(data.rpmLimit ?? data.rpm_limit),
    rpmUsagePct: toNumber(data.rpmUsagePct ?? data.rpm_usage_pct),
    dailyTokensUsed: toNumber(data.dailyTokensUsed ?? data.daily_tokens_used),
    dailyTokenLimit: toNullableNumber(data.dailyTokenLimit ?? data.daily_token_limit),
    dailyCostInr: toNumber(data.dailyCostInr ?? data.daily_cost_inr),
    dailyCostLimitInr: toNullableNumber(data.dailyCostLimitInr ?? data.daily_cost_limit_inr),
    rateLimitedCount: toNumber(data.rateLimitedCount ?? data.rate_limited_count),
    projectedExhaustion: (data.projectedExhaustion ?? data.projected_exhaustion)
      ? toString(data.projectedExhaustion ?? data.projected_exhaustion)
      : null,
    trend: toTrend(data.trend),
    alertTriggered: toBoolean(data.alertTriggered ?? data.alert_triggered),
  };
}

function transformLLMQuotaData(data: Record<string, unknown>): LLMQuotaData {
  const providers = (data.providers as Array<Record<string, unknown>> ?? []).map(transformProviderQuota);

  return {
    providers,
    lastUpdated: (data.lastUpdated ?? data.last_updated ?? new Date().toISOString()) as string,
    alertThresholdPct: (data.alertThresholdPct ?? data.alert_threshold_pct ?? 80) as number,
    usdToInrRate: (data.usdToInrRate ?? data.usd_to_inr_rate ?? 83.5) as number,
  };
}

// =============================================================================
// Admin Quota API
// =============================================================================

/**
 * Get current LLM quota status for all providers.
 *
 * @returns LLM quota data with usage, limits, and projections
 */
export async function getLLMQuota(): Promise<LLMQuotaData> {
  const response = await api.get<{ data: Record<string, unknown> }>(
    '/api/admin/llm-quota'
  );

  return transformLLMQuotaData(response.data);
}

// =============================================================================
// Admin Status Check (F1, F2, F3 fix)
// =============================================================================

export interface AdminStatusData {
  isAdmin: boolean;
  email: string | null;
}

/**
 * Check if current user has admin privileges.
 *
 * This replaces build-time env var checks with runtime API validation.
 *
 * @returns Admin status data
 */
export async function checkAdminStatus(): Promise<AdminStatusData> {
  const response = await api.get<{ data: AdminStatusData }>(
    '/api/admin/status'
  );
  return response.data;
}

// =============================================================================
// Exported API Object
// =============================================================================

export const adminQuotaApi = {
  getLLMQuota,
  checkAdminStatus,
};
