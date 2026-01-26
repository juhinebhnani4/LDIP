/**
 * useContradictions Hook
 *
 * SWR hook for fetching contradictions data with filtering and pagination.
 * Connected to real backend API at /api/matters/{matterId}/contradictions
 *
 * Story 14.13: Contradictions Tab UI Completion
 */

import { useMemo } from 'react';
import useSWR from 'swr';

// =============================================================================
// Types
// =============================================================================

export type ContradictionType =
  | 'semantic_contradiction'
  | 'factual_contradiction'
  | 'date_mismatch'
  | 'amount_mismatch';

export type ContradictionSeverity = 'high' | 'medium' | 'low';

export interface StatementInfo {
  documentId: string;
  documentName: string;
  page: number | null;
  excerpt: string;
  date: string | null;
}

export interface EvidenceLink {
  statementId: string;
  documentId: string;
  documentName: string;
  page: number | null;
  bboxIds: string[];
}

export interface ContradictionItem {
  id: string;
  contradictionType: ContradictionType;
  severity: ContradictionSeverity;
  entityId: string;
  entityName: string;
  statementA: StatementInfo;
  statementB: StatementInfo;
  explanation: string;
  evidenceLinks: EvidenceLink[];
  confidence: number;
  createdAt: string;
}

export interface EntityContradictions {
  entityId: string;
  entityName: string;
  contradictions: ContradictionItem[];
  count: number;
}

export interface ContradictionsListResponse {
  data: EntityContradictions[];
  meta: {
    total: number;
    page: number;
    perPage: number;
    totalPages: number;
  };
}

export interface ContradictionsFilterOptions {
  severity?: ContradictionSeverity;
  contradictionType?: ContradictionType;
  entityId?: string;
  documentId?: string;
  page?: number;
  perPage?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface UseContradictionsOptions extends ContradictionsFilterOptions {
  enabled?: boolean;
}

export interface UseContradictionsReturn {
  /** Grouped contradictions data */
  data: EntityContradictions[];
  /** Pagination metadata */
  meta: ContradictionsListResponse['meta'] | null;
  /** Whether data is loading */
  isLoading: boolean;
  /** Whether data is revalidating */
  isValidating: boolean;
  /** Error if request failed */
  error: Error | null;
  /** Total count of contradictions */
  totalCount: number;
  /** Unique entities from current data (for filter dropdown) */
  uniqueEntities: { id: string; name: string }[];
  /** Refetch data */
  mutate: () => void;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Safely get a string value from an object, with fallback.
 */
function getString(obj: Record<string, unknown>, key: string, altKey?: string): string {
  const val = obj[key] ?? (altKey ? obj[altKey] : undefined);
  return typeof val === 'string' ? val : '';
}

/**
 * Safely get a number value from an object, with fallback.
 */
function getNumber(obj: Record<string, unknown>, key: string, altKey?: string): number {
  const val = obj[key] ?? (altKey ? obj[altKey] : undefined);
  return typeof val === 'number' ? val : 0;
}

/**
 * Safely get a nullable number value from an object, with fallback.
 */
function getNumberOrNull(obj: Record<string, unknown>, key: string, altKey?: string): number | null {
  const val = obj[key] ?? (altKey ? obj[altKey] : undefined);
  return typeof val === 'number' ? val : null;
}

/**
 * Safely get a nullable string value from an object, with fallback.
 */
function getStringOrNull(obj: Record<string, unknown>, key: string, altKey?: string): string | null {
  const val = obj[key] ?? (altKey ? obj[altKey] : undefined);
  return typeof val === 'string' ? val : null;
}

/**
 * Transform snake_case API response to camelCase frontend types.
 * Handles both snake_case and camelCase for backward compatibility.
 * Uses safe accessors to prevent crashes on malformed data.
 */
function transformStatement(stmt: Record<string, unknown>): StatementInfo {
  return {
    documentId: getString(stmt, 'documentId', 'document_id'),
    documentName: getString(stmt, 'documentName', 'document_name'),
    page: getNumberOrNull(stmt, 'page'),
    excerpt: getString(stmt, 'excerpt'),
    date: getStringOrNull(stmt, 'date'),
  };
}

function transformEvidenceLink(link: Record<string, unknown>): EvidenceLink {
  const bboxIds = link.bboxIds ?? link.bbox_ids;
  return {
    statementId: getString(link, 'statementId', 'statement_id'),
    documentId: getString(link, 'documentId', 'document_id'),
    documentName: getString(link, 'documentName', 'document_name'),
    page: getNumberOrNull(link, 'page'),
    bboxIds: Array.isArray(bboxIds) ? (bboxIds as string[]) : [],
  };
}

function transformContradiction(item: Record<string, unknown>): ContradictionItem {
  const evidenceLinks = item.evidenceLinks ?? item.evidence_links;
  const stmtA = (item.statementA ?? item.statement_a) as Record<string, unknown> | undefined;
  const stmtB = (item.statementB ?? item.statement_b) as Record<string, unknown> | undefined;

  return {
    id: getString(item, 'id'),
    contradictionType: getString(item, 'contradictionType', 'contradiction_type') as ContradictionType,
    severity: getString(item, 'severity') as ContradictionSeverity,
    entityId: getString(item, 'entityId', 'entity_id'),
    entityName: getString(item, 'entityName', 'entity_name'),
    statementA: stmtA ? transformStatement(stmtA) : { documentId: '', documentName: '', page: null, excerpt: '', date: null },
    statementB: stmtB ? transformStatement(stmtB) : { documentId: '', documentName: '', page: null, excerpt: '', date: null },
    explanation: getString(item, 'explanation'),
    evidenceLinks: Array.isArray(evidenceLinks)
      ? (evidenceLinks as Record<string, unknown>[]).map(transformEvidenceLink)
      : [],
    confidence: getNumber(item, 'confidence'),
    createdAt: getString(item, 'createdAt', 'created_at'),
  };
}

function transformEntityGroup(group: Record<string, unknown>): EntityContradictions {
  return {
    entityId: getString(group, 'entityId', 'entity_id'),
    entityName: getString(group, 'entityName', 'entity_name'),
    contradictions: Array.isArray(group.contradictions)
      ? (group.contradictions as Record<string, unknown>[]).map(transformContradiction)
      : [],
    count: getNumber(group, 'count'),
  };
}

function transformResponse(response: {
  data: Record<string, unknown>[];
  meta: Record<string, unknown>;
}): ContradictionsListResponse {
  return {
    data: response.data.map(transformEntityGroup),
    meta: {
      total: (response.meta.total ?? 0) as number,
      page: (response.meta.page ?? 1) as number,
      perPage: ((response.meta.perPage ?? response.meta.per_page) ?? 20) as number,
      totalPages: ((response.meta.totalPages ?? response.meta.total_pages) ?? 0) as number,
    },
  };
}

/**
 * Fetcher for contradictions API.
 */
async function fetcher(url: string): Promise<ContradictionsListResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.get<{
    data: Record<string, unknown>[];
    meta: Record<string, unknown>;
  }>(url);

  return transformResponse(response);
}

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook for fetching contradictions data with filtering and pagination.
 *
 * @param matterId - The matter ID to fetch contradictions for
 * @param options - Optional filtering and pagination options
 * @returns Contradictions data, loading state, error state, and mutate function
 *
 * @example
 * ```tsx
 * const { data, meta, isLoading, isError, mutate } = useContradictions(matterId, {
 *   severity: 'high',
 *   page: 1,
 *   perPage: 20,
 * });
 *
 * if (isLoading) return <ContradictionsSkeleton />;
 * if (isError) return <ContradictionsError />;
 *
 * return <ContradictionsList data={data} />;
 * ```
 */
export function useContradictions(
  matterId: string | null,
  options: UseContradictionsOptions = {}
): UseContradictionsReturn {
  // Default to 100 items for comprehensive contradiction view
  const {
    enabled = true,
    severity,
    contradictionType,
    entityId,
    documentId,
    page = 1,
    perPage = 100,
    sortBy,
    sortOrder,
  } = options;

  // Build URL with query params
  const params = new URLSearchParams();
  if (severity) params.set('severity', severity);
  if (contradictionType) params.set('contradiction_type', contradictionType);
  if (entityId) params.set('entity_id', entityId);
  if (documentId) params.set('document_id', documentId);
  params.set('page', String(page));
  params.set('per_page', String(perPage));
  if (sortBy) params.set('sort_by', sortBy);
  if (sortOrder) params.set('sort_order', sortOrder);

  const { data, error, isLoading, isValidating, mutate } = useSWR<ContradictionsListResponse>(
    enabled && matterId
      ? `/api/matters/${matterId}/contradictions?${params.toString()}`
      : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 seconds
    }
  );

  // Stable reference to the data array
  const dataArray = useMemo(() => data?.data ?? [], [data?.data]);

  // Extract unique entities from current data for filter dropdown
  const uniqueEntities = useMemo(() => {
    return dataArray.map((group) => ({
      id: group.entityId,
      name: group.entityName,
    }));
  }, [dataArray]);

  // Calculate total count across all groups
  const totalCount = useMemo(() => {
    return dataArray.reduce((sum, group) => sum + group.count, 0);
  }, [dataArray]);

  return {
    data: data?.data ?? [],
    meta: data?.meta ?? null,
    isLoading,
    isValidating,
    error: error ?? null,
    totalCount,
    uniqueEntities,
    mutate,
  };
}
