/**
 * Anomalies Hook
 *
 * SWR hooks for fetching timeline anomaly data.
 * Connected to backend API at /api/matters/{matterId}/anomalies
 *
 * Story 14.16: Anomalies UI Integration
 */

import { useMemo, useCallback } from 'react';
import useSWR from 'swr';
import useSWRMutation from 'swr/mutation';

// =============================================================================
// TypeScript Interfaces
// =============================================================================

export type AnomalyType = 'gap' | 'sequence_violation' | 'duplicate' | 'outlier';
export type AnomalySeverity = 'low' | 'medium' | 'high' | 'critical';

export interface AnomalyListItem {
  id: string;
  anomalyType: AnomalyType;
  severity: AnomalySeverity;
  title: string;
  explanation: string;
  eventIds: string[];
  gapDays: number | null;
  confidence: number;
  verified: boolean;
  dismissed: boolean;
  createdAt: string;
}

export interface Anomaly extends AnomalyListItem {
  matterId: string;
  expectedOrder: string[] | null;
  actualOrder: string[] | null;
  verifiedBy: string | null;
  verifiedAt: string | null;
  updatedAt: string;
}

export interface AnomalySummary {
  total: number;
  bySeverity: Record<string, number>;
  byType: Record<string, number>;
  unreviewed: number;
  verified: number;
  dismissed: number;
}

export interface PaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

export interface AnomaliesListResponse {
  data: AnomalyListItem[];
  meta: PaginationMeta;
}

export interface AnomalySummaryResponse {
  data: AnomalySummary;
}

export interface AnomalyDetailResponse {
  data: Anomaly;
}

// =============================================================================
// API Response Transformers
// =============================================================================

/**
 * Transform snake_case API response to camelCase
 */
function transformAnomalyListItem(item: Record<string, unknown>): AnomalyListItem {
  return {
    id: item.id as string,
    anomalyType: (item.anomaly_type ?? item.anomalyType) as AnomalyType,
    severity: item.severity as AnomalySeverity,
    title: item.title as string,
    explanation: item.explanation as string,
    eventIds: (item.event_ids ?? item.eventIds) as string[],
    gapDays: (item.gap_days ?? item.gapDays) as number | null,
    confidence: item.confidence as number,
    verified: item.verified as boolean,
    dismissed: item.dismissed as boolean,
    createdAt: (item.created_at ?? item.createdAt) as string,
  };
}

function transformAnomaly(item: Record<string, unknown>): Anomaly {
  return {
    ...transformAnomalyListItem(item),
    matterId: (item.matter_id ?? item.matterId) as string,
    expectedOrder: (item.expected_order ?? item.expectedOrder) as string[] | null,
    actualOrder: (item.actual_order ?? item.actualOrder) as string[] | null,
    verifiedBy: (item.verified_by ?? item.verifiedBy) as string | null,
    verifiedAt: (item.verified_at ?? item.verifiedAt) as string | null,
    updatedAt: (item.updated_at ?? item.updatedAt) as string,
  };
}

function transformSummary(data: Record<string, unknown>): AnomalySummary {
  return {
    total: data.total as number,
    bySeverity: (data.by_severity ?? data.bySeverity) as Record<string, number>,
    byType: (data.by_type ?? data.byType) as Record<string, number>,
    unreviewed: data.unreviewed as number,
    verified: data.verified as number,
    dismissed: data.dismissed as number,
  };
}

// =============================================================================
// Fetchers
// =============================================================================

async function anomaliesListFetcher(url: string): Promise<AnomaliesListResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.get<{
    data: Record<string, unknown>[];
    meta: Record<string, unknown>;
  }>(url);

  return {
    data: response.data.map(transformAnomalyListItem),
    meta: {
      total: (response.meta.total ?? 0) as number,
      page: (response.meta.page ?? 1) as number,
      perPage: ((response.meta.per_page ?? response.meta.perPage) ?? 20) as number,
      totalPages: ((response.meta.total_pages ?? response.meta.totalPages) ?? 0) as number,
    },
  };
}

async function anomalySummaryFetcher(url: string): Promise<AnomalySummaryResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.get<{ data: Record<string, unknown> }>(url);

  return {
    data: transformSummary(response.data),
  };
}

async function anomalyDetailFetcher(url: string): Promise<AnomalyDetailResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.get<{ data: Record<string, unknown> }>(url);

  return {
    data: transformAnomaly(response.data),
  };
}

// =============================================================================
// Mutation Fetchers
// =============================================================================

async function dismissAnomalyFetcher(
  url: string,
): Promise<AnomalyDetailResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.patch<{ data: Record<string, unknown> }>(url, {});
  return {
    data: transformAnomaly(response.data),
  };
}

async function verifyAnomalyFetcher(
  url: string,
): Promise<AnomalyDetailResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.patch<{ data: Record<string, unknown> }>(url, {});
  return {
    data: transformAnomaly(response.data),
  };
}

// =============================================================================
// Hooks
// =============================================================================

export interface UseAnomaliesOptions {
  severity?: AnomalySeverity;
  anomalyType?: AnomalyType;
  dismissed?: boolean;
  page?: number;
  perPage?: number;
}

/**
 * Hook for fetching list of anomalies for a matter
 */
export function useAnomalies(matterId: string, options: UseAnomaliesOptions = {}) {
  const { severity, anomalyType, dismissed, page = 1, perPage = 20 } = options;

  // Build URL with query params
  const params = new URLSearchParams();
  if (severity) params.set('severity', severity);
  if (anomalyType) params.set('anomaly_type', anomalyType);
  if (dismissed !== undefined) params.set('dismissed', String(dismissed));
  params.set('page', String(page));
  params.set('per_page', String(perPage));

  const url = matterId
    ? `/api/matters/${matterId}/anomalies?${params.toString()}`
    : null;

  const { data, error, isLoading, mutate } = useSWR<AnomaliesListResponse>(
    url,
    anomaliesListFetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    anomalies: data?.data ?? [],
    meta: data?.meta,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}

/**
 * Hook for fetching anomaly summary counts
 */
export function useAnomalySummary(matterId: string) {
  const url = matterId ? `/api/matters/${matterId}/anomalies/summary` : null;

  const { data, error, isLoading, mutate } = useSWR<AnomalySummaryResponse>(
    url,
    anomalySummaryFetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    summary: data?.data ?? null,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}

/**
 * Hook for fetching a single anomaly's details
 */
export function useAnomalyDetail(matterId: string, anomalyId: string | null) {
  const url =
    matterId && anomalyId
      ? `/api/matters/${matterId}/anomalies/${anomalyId}`
      : null;

  const { data, error, isLoading, mutate } = useSWR<AnomalyDetailResponse>(
    url,
    anomalyDetailFetcher,
    {
      revalidateOnFocus: false,
    }
  );

  return {
    anomaly: data?.data ?? null,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}

/**
 * Hook for anomaly mutations (dismiss/verify)
 */
export function useAnomalyMutations(matterId: string) {
  const { trigger: dismissTrigger, isMutating: isDismissing } = useSWRMutation(
    matterId ? `/api/matters/${matterId}/anomalies` : null,
    async (baseUrl: string, { arg }: { arg: { anomalyId: string } }) => {
      return dismissAnomalyFetcher(`${baseUrl}/${arg.anomalyId}/dismiss`);
    }
  );

  const { trigger: verifyTrigger, isMutating: isVerifying } = useSWRMutation(
    matterId ? `/api/matters/${matterId}/anomalies` : null,
    async (baseUrl: string, { arg }: { arg: { anomalyId: string } }) => {
      return verifyAnomalyFetcher(`${baseUrl}/${arg.anomalyId}/verify`);
    }
  );

  const dismiss = useCallback(
    async (anomalyId: string) => {
      return dismissTrigger({ anomalyId });
    },
    [dismissTrigger]
  );

  const verify = useCallback(
    async (anomalyId: string) => {
      return verifyTrigger({ anomalyId });
    },
    [verifyTrigger]
  );

  return {
    dismiss,
    verify,
    isDismissing,
    isVerifying,
    isLoading: isDismissing || isVerifying,
  };
}

/**
 * Hook to get anomalies mapped by event ID for easy lookup
 */
export function useAnomaliesByEvent(matterId: string) {
  const { anomalies, isLoading, error } = useAnomalies(matterId, {
    perPage: 100, // Fetch all for mapping
    dismissed: false, // Only show active anomalies
  });

  const anomaliesByEventId = useMemo(() => {
    const map = new Map<string, AnomalyListItem[]>();

    anomalies.forEach((anomaly) => {
      anomaly.eventIds.forEach((eventId) => {
        const existing = map.get(eventId) ?? [];
        existing.push(anomaly);
        map.set(eventId, existing);
      });
    });

    return map;
  }, [anomalies]);

  const getAnomaliesForEvent = useCallback(
    (eventId: string) => anomaliesByEventId.get(eventId) ?? [],
    [anomaliesByEventId]
  );

  const hasAnomaly = useCallback(
    (eventId: string) => anomaliesByEventId.has(eventId),
    [anomaliesByEventId]
  );

  return {
    anomaliesByEventId,
    getAnomaliesForEvent,
    hasAnomaly,
    isLoading,
    error,
  };
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get severity color classes for UI
 */
export function getAnomalySeverityColor(severity: AnomalySeverity): string {
  switch (severity) {
    case 'critical':
      return 'text-red-700 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-950 dark:border-red-800';
    case 'high':
      return 'text-red-600 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-950 dark:border-red-800';
    case 'medium':
      return 'text-orange-600 bg-orange-50 border-orange-200 dark:text-orange-400 dark:bg-orange-950 dark:border-orange-800';
    case 'low':
      return 'text-yellow-600 bg-yellow-50 border-yellow-200 dark:text-yellow-400 dark:bg-yellow-950 dark:border-yellow-800';
    default:
      return 'text-gray-600 bg-gray-50 border-gray-200 dark:text-gray-400 dark:bg-gray-950 dark:border-gray-800';
  }
}

/**
 * Get anomaly type label for display
 */
export function getAnomalyTypeLabel(type: AnomalyType): string {
  switch (type) {
    case 'gap':
      return 'Unusual Gap';
    case 'sequence_violation':
      return 'Sequence Violation';
    case 'duplicate':
      return 'Potential Duplicate';
    case 'outlier':
      return 'Date Outlier';
    default:
      return 'Unknown';
  }
}

/**
 * Get severity label for display
 */
export function getAnomalySeverityLabel(severity: AnomalySeverity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1);
}
