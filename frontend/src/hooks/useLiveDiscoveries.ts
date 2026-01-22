/**
 * useLiveDiscoveries Hook
 *
 * Polls backend APIs to fetch live discovery data during document processing.
 * Aggregates entities, dates/timeline stats, and citations to populate
 * the LiveDiscoveriesPanel.
 *
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 *
 * Backend APIs used:
 * - GET /api/matters/{matter_id}/entities - Entity list
 * - GET /api/matters/{matter_id}/timeline/stats - Timeline statistics
 * - GET /api/matters/{matter_id}/citations/acts/discovery - Act citations
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/lib/api/client';
import type {
  LiveDiscovery,
  DiscoveredEntity,
  DiscoveredDate,
  DiscoveredCitation,
} from '@/types/upload';

// =============================================================================
// Types
// =============================================================================

/** Entity from backend */
interface BackendEntity {
  id: string;
  canonicalName: string;
  entityType: string;
  mentionCount: number;
  metadata?: Record<string, unknown>;
}

/** Entity list response */
interface EntitiesResponse {
  data: BackendEntity[];
  meta: {
    total: number;
    page: number;
    perPage: number;
    totalPages: number;
  };
}

/** Timeline statistics response */
interface TimelineStatsResponse {
  data: {
    totalEvents: number;
    eventsByType: Record<string, number>;
    entitiesInvolved: number;
    dateRangeStart: string | null;
    dateRangeEnd: string | null;
    eventsWithEntities: number;
    eventsWithoutEntities: number;
    verifiedEvents: number;
  };
}

/** Act discovery summary from backend */
interface ActDiscoverySummary {
  actName: string;
  actNameNormalized: string;
  citationCount: number;
  resolutionStatus: string;
  userAction: string;
  actDocumentId: string | null;
}

/** Act discovery response */
interface ActDiscoveryResponse {
  acts: ActDiscoverySummary[];
  totalActs: number;
  missingCount: number;
  availableCount: number;
  skippedCount: number;
}

/** Hook options */
export interface UseLiveDiscoveriesOptions {
  /** Polling interval in ms (default: 3000ms - less frequent than job status) */
  pollingInterval?: number;
  /** Whether to enable polling (default: true) */
  enabled?: boolean;
  /** Stop polling when processing is complete */
  stopOnComplete?: boolean;
}

/** Hook return value */
export interface LiveDiscoveriesResult {
  /** All discoveries found so far */
  discoveries: LiveDiscovery[];
  /** Whether currently fetching */
  isLoading: boolean;
  /** Error from API calls */
  error: Error | null;
  /** Force refresh data */
  refresh: () => Promise<void>;
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_POLLING_INTERVAL = 3000;

// =============================================================================
// Helper Functions
// =============================================================================

let discoveryIdCounter = 0;

function generateDiscoveryId(): string {
  discoveryIdCounter += 1;
  return `discovery-${Date.now()}-${discoveryIdCounter}`;
}

/**
 * Map entity type to a role description
 */
function getEntityRole(entityType: string): string {
  const roleMap: Record<string, string> = {
    PERSON: 'Individual',
    ORG: 'Organization',
    INSTITUTION: 'Institution',
    ASSET: 'Asset',
  };
  return roleMap[entityType] || entityType;
}

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook to poll for live discoveries during processing.
 *
 * @param matterId - Matter ID to fetch discoveries for, null to disable
 * @param options - Polling configuration options
 * @returns Discovery data, loading state, and error
 *
 * @example
 * const { discoveries, isLoading, error } = useLiveDiscoveries(matterId, {
 *   pollingInterval: 3000,
 *   enabled: !USE_MOCK_PROCESSING && uploadPhaseComplete,
 * });
 */
export function useLiveDiscoveries(
  matterId: string | null,
  options: UseLiveDiscoveriesOptions = {}
): LiveDiscoveriesResult {
  const {
    pollingInterval = DEFAULT_POLLING_INTERVAL,
    enabled = true,
    stopOnComplete = false,
  } = options;

  const [discoveries, setDiscoveries] = useState<LiveDiscovery[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Refs for tracking state
  const isMountedRef = useRef(true);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isCompleteRef = useRef(false);

  // Track what we've already discovered to avoid duplicates
  const hasEntitiesRef = useRef(false);
  const hasDateRef = useRef(false);
  const hasCitationsRef = useRef(false);
  const lastEntityCountRef = useRef(0);
  const lastDateCountRef = useRef(0);
  const lastCitationCountRef = useRef(0);

  /**
   * Fetch discovery data from all endpoints
   */
  const fetchDiscoveries = useCallback(async () => {
    if (!matterId) return;

    setIsLoading(true);
    setError(null);

    const newDiscoveries: LiveDiscovery[] = [];

    try {
      // Fetch all discovery data in parallel
      const [entitiesResult, timelineResult, citationsResult] = await Promise.allSettled([
        api.get<EntitiesResponse>(`/api/matters/${matterId}/entities?per_page=10`),
        api.get<TimelineStatsResponse>(`/api/matters/${matterId}/timeline/stats`),
        api.get<ActDiscoveryResponse>(`/api/matters/${matterId}/citations/acts/discovery`),
      ]);

      if (!isMountedRef.current) return;

      // Process entities
      if (entitiesResult.status === 'fulfilled' && entitiesResult.value.data.length > 0) {
        const entities = entitiesResult.value.data;
        const totalEntities = entitiesResult.value.meta.total;

        // Only add/update if we have new entities
        if (totalEntities > 0 && totalEntities !== lastEntityCountRef.current) {
          lastEntityCountRef.current = totalEntities;

          const entityDetails: DiscoveredEntity[] = entities.map((e) => ({
            name: e.canonicalName,
            role: getEntityRole(e.entityType),
          }));

          // Replace existing entity discovery or add new one
          if (hasEntitiesRef.current) {
            setDiscoveries((prev) => {
              const filtered = prev.filter((d) => d.type !== 'entity');
              return [
                ...filtered,
                {
                  id: generateDiscoveryId(),
                  type: 'entity' as const,
                  count: totalEntities,
                  details: entityDetails,
                  timestamp: new Date(),
                },
              ];
            });
          } else {
            hasEntitiesRef.current = true;
            newDiscoveries.push({
              id: generateDiscoveryId(),
              type: 'entity',
              count: totalEntities,
              details: entityDetails,
              timestamp: new Date(),
            });
          }
        }
      }

      // Process timeline stats (dates)
      if (timelineResult.status === 'fulfilled' && timelineResult.value.data) {
        const stats = timelineResult.value.data;

        if (stats.totalEvents > 0 && stats.dateRangeStart && stats.dateRangeEnd) {
          const dateCount = stats.totalEvents;

          // Only add/update if count changed
          if (dateCount !== lastDateCountRef.current) {
            lastDateCountRef.current = dateCount;

            const dateDetails: DiscoveredDate = {
              earliest: new Date(stats.dateRangeStart),
              latest: new Date(stats.dateRangeEnd),
              count: dateCount,
            };

            // Replace existing date discovery or add new one
            if (hasDateRef.current) {
              setDiscoveries((prev) => {
                const filtered = prev.filter((d) => d.type !== 'date');
                return [
                  ...filtered,
                  {
                    id: generateDiscoveryId(),
                    type: 'date' as const,
                    count: dateCount,
                    details: dateDetails,
                    timestamp: new Date(),
                  },
                ];
              });
            } else {
              hasDateRef.current = true;
              newDiscoveries.push({
                id: generateDiscoveryId(),
                type: 'date',
                count: dateCount,
                details: dateDetails,
                timestamp: new Date(),
              });
            }
          }
        }
      }

      // Process citations
      if (citationsResult.status === 'fulfilled' && citationsResult.value.acts) {
        const acts = citationsResult.value.acts;
        const totalCitations = acts.reduce((sum, act) => sum + act.citationCount, 0);

        if (acts.length > 0 && totalCitations > 0) {
          // Only add/update if count changed
          if (totalCitations !== lastCitationCountRef.current) {
            lastCitationCountRef.current = totalCitations;

            const citationDetails: DiscoveredCitation[] = acts
              .filter((act) => act.citationCount > 0)
              .slice(0, 5) // Show top 5 acts
              .map((act) => ({
                actName: act.actName,
                count: act.citationCount,
              }));

            // Replace existing citation discovery or add new one
            if (hasCitationsRef.current) {
              setDiscoveries((prev) => {
                const filtered = prev.filter((d) => d.type !== 'citation');
                return [
                  ...filtered,
                  {
                    id: generateDiscoveryId(),
                    type: 'citation' as const,
                    count: totalCitations,
                    details: citationDetails,
                    timestamp: new Date(),
                  },
                ];
              });
            } else {
              hasCitationsRef.current = true;
              newDiscoveries.push({
                id: generateDiscoveryId(),
                type: 'citation',
                count: totalCitations,
                details: citationDetails,
                timestamp: new Date(),
              });
            }
          }
        }
      }

      // Add all new discoveries at once
      if (newDiscoveries.length > 0) {
        setDiscoveries((prev) => [...prev, ...newDiscoveries]);
      }

    } catch (err) {
      if (!isMountedRef.current) return;

      // Don't fail hard on discovery errors - these are progressive enhancements
      console.warn('Failed to fetch some discovery data:', err);

      if (err instanceof Error) {
        setError(err);
      } else {
        setError(new Error('Failed to fetch discovery data'));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [matterId]);

  /**
   * Manual refresh function
   */
  const refresh = useCallback(async () => {
    await fetchDiscoveries();
  }, [fetchDiscoveries]);

  // Set up polling
  useEffect(() => {
    isMountedRef.current = true;
    isCompleteRef.current = false;

    // Reset tracking refs when matterId changes
    hasEntitiesRef.current = false;
    hasDateRef.current = false;
    hasCitationsRef.current = false;
    lastEntityCountRef.current = 0;
    lastDateCountRef.current = 0;
    lastCitationCountRef.current = 0;
    setDiscoveries([]);

    // Don't poll if disabled or no matterId
    if (!enabled || !matterId) {
      return;
    }

    // Initial fetch
    void fetchDiscoveries();

    // Set up polling interval
    const poll = () => {
      if (stopOnComplete && isCompleteRef.current) {
        return;
      }

      pollingRef.current = setTimeout(async () => {
        if (!isMountedRef.current) return;

        await fetchDiscoveries();

        // Continue polling
        if (!stopOnComplete || !isCompleteRef.current) {
          poll();
        }
      }, pollingInterval);
    };

    poll();

    // Cleanup
    return () => {
      isMountedRef.current = false;
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [matterId, enabled, pollingInterval, stopOnComplete, fetchDiscoveries]);

  return {
    discoveries,
    isLoading,
    error,
    refresh,
  };
}

export default useLiveDiscoveries;
