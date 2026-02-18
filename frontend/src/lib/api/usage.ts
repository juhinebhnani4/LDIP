'use client';

/**
 * User-facing Usage API Client
 *
 * Fetches usage metrics (documents, pages, queries) — no cost data.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface MatterUsageStats {
  matterId: string;
  matterTitle: string;
  documents: number;
  pages: number;
  queries: number;
}

export interface UsageSummaryData {
  totalDocuments: number;
  totalPages: number;
  totalQueries: number;
  totalMatters: number;
  matters: MatterUsageStats[];
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

function transformMatterUsage(d: Record<string, unknown>): MatterUsageStats {
  return {
    matterId: toString(d.matterId ?? d.matter_id),
    matterTitle: toString(d.matterTitle ?? d.matter_title, 'Untitled'),
    documents: toNumber(d.documents),
    pages: toNumber(d.pages),
    queries: toNumber(d.queries),
  };
}

function transformUsageSummary(raw: Record<string, unknown>): UsageSummaryData {
  const data = (raw.data ?? raw) as Record<string, unknown>;
  return {
    totalDocuments: toNumber(data.totalDocuments ?? data.total_documents),
    totalPages: toNumber(data.totalPages ?? data.total_pages),
    totalQueries: toNumber(data.totalQueries ?? data.total_queries),
    totalMatters: toNumber(data.totalMatters ?? data.total_matters),
    matters: (
      (data.matters ?? []) as Array<Record<string, unknown>>
    ).map(transformMatterUsage),
  };
}

// =============================================================================
// API
// =============================================================================

export async function getUsageSummary(): Promise<UsageSummaryData> {
  const response = await api.get<Record<string, unknown>>('/api/usage/summary');
  return transformUsageSummary(response);
}

export const usageApi = {
  getUsageSummary,
};
