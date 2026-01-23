/**
 * useLiveDiscoveries Hook
 *
 * WebSocket-based live discovery data during document processing.
 * Falls back to polling if WebSocket is unavailable.
 * Aggregates entities, dates/timeline stats, and citations to populate
 * the LiveDiscoveriesPanel.
 *
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 *
 * Backend APIs used:
 * - GET /api/matters/{matter_id}/entities - Entity list
 * - GET /api/matters/{matter_id}/timeline/stats - Timeline statistics
 * - GET /api/matters/{matter_id}/citations/acts/discovery - Act citations
 *
 * WebSocket channels:
 * - discoveries:{matter_id} - Entity/timeline discovery updates
 * - citations:{matter_id} - Citation extraction updates
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/lib/api/client';
import { useWebSocket } from './useWebSocket';
import type { WSMessage, WSDiscoveryUpdate, WSEntityStream } from '@/lib/ws/client';
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
  /** Polling interval in ms (default: 5000ms - fallback only) */
  pollingInterval?: number;
  /** Whether to enable the hook (default: true) */
  enabled?: boolean;
  /** Stop updates when processing is complete */
  stopOnComplete?: boolean;
  /** Prefer WebSocket over polling (default: true) */
  preferWebSocket?: boolean;
}

/** Hook return value */
export interface LiveDiscoveriesResult {
  /** All discoveries found so far */
  discoveries: LiveDiscovery[];
  /** Whether currently fetching */
  isLoading: boolean;
  /** Error from API calls */
  error: Error | null;
  /** Whether using WebSocket (true) or polling fallback (false) */
  isRealTime: boolean;
  /** Force refresh data */
  refresh: () => Promise<void>;
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_POLLING_INTERVAL = 5000; // Slower fallback since we have WebSocket

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
 * Hook to receive live discoveries during processing via WebSocket.
 * Falls back to polling if WebSocket is unavailable.
 *
 * @param matterId - Matter ID to fetch discoveries for, null to disable
 * @param options - Configuration options
 * @returns Discovery data, loading state, and error
 *
 * @example
 * const { discoveries, isLoading, isRealTime } = useLiveDiscoveries(matterId, {
 *   enabled: !USE_MOCK_PROCESSING && uploadPhaseComplete,
 *   preferWebSocket: true,
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
    preferWebSocket = true,
  } = options;

  const [discoveries, setDiscoveries] = useState<LiveDiscovery[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Refs for tracking state
  const isMountedRef = useRef(true);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isCompleteRef = useRef(false);

  // Track counts to detect changes
  const lastEntityCountRef = useRef(0);
  const lastDateCountRef = useRef(0);
  const lastCitationCountRef = useRef(0);

  // WebSocket connection
  const { isConnected, subscribe } = useWebSocket(
    preferWebSocket ? matterId : null,
    { enabled: enabled && preferWebSocket }
  );

  // Track if we're using real-time updates
  const isRealTime = preferWebSocket && isConnected;

  /**
   * Update entity discovery from WebSocket message
   */
  const handleEntityDiscovery = useCallback((data: WSDiscoveryUpdate) => {
    if (data.event !== 'entity_discovery') return;

    const totalEntities = data.total_entities;
    if (totalEntities <= 0 || totalEntities === lastEntityCountRef.current) return;

    lastEntityCountRef.current = totalEntities;

    // Build entity details from the message or use placeholder
    const entityDetails: DiscoveredEntity[] = data.new_entities
      ? data.new_entities.slice(0, 5).map((e) => ({
          name: e.canonical_name,
          role: getEntityRole(e.entity_type),
        }))
      : [];

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
  }, []);

  /**
   * Handle individual entity streaming for progressive rendering
   * Entities appear one-by-one as they're discovered
   */
  const handleEntityStream = useCallback((data: WSEntityStream) => {
    if (data.event !== 'entity_stream') return;

    const newEntity: DiscoveredEntity = {
      name: data.entity.name,
      role: getEntityRole(data.entity.type),
    };

    setDiscoveries((prev) => {
      const existing = prev.find((d) => d.type === 'entity');

      if (existing) {
        // Add new entity to existing list (keep max 5 recent)
        const currentDetails = existing.details as DiscoveredEntity[];
        const updatedDetails = [...currentDetails];

        // Only add if not already in list
        const alreadyExists = updatedDetails.some(
          (e) => e.name.toLowerCase() === newEntity.name.toLowerCase()
        );

        if (!alreadyExists) {
          // Add new entity at the end, keep max 5
          updatedDetails.push(newEntity);
          if (updatedDetails.length > 5) {
            updatedDetails.shift(); // Remove oldest
          }
        }

        return prev.map((d) =>
          d.type === 'entity'
            ? {
                ...d,
                count: data.current_count,
                details: updatedDetails,
                timestamp: new Date(),
              }
            : d
        );
      }

      // First entity - create new discovery
      return [
        ...prev,
        {
          id: generateDiscoveryId(),
          type: 'entity' as const,
          count: data.current_count,
          details: [newEntity],
          timestamp: new Date(),
        },
      ];
    });

    // Update ref
    lastEntityCountRef.current = data.current_count;
  }, []);

  /**
   * Update timeline discovery from WebSocket message
   */
  const handleTimelineDiscovery = useCallback((data: WSDiscoveryUpdate) => {
    if (data.event !== 'timeline_discovery') return;

    const totalEvents = data.total_events;
    if (totalEvents <= 0 || totalEvents === lastDateCountRef.current) return;
    if (!data.date_range_start || !data.date_range_end) return;

    lastDateCountRef.current = totalEvents;

    const dateDetails: DiscoveredDate = {
      earliest: new Date(data.date_range_start),
      latest: new Date(data.date_range_end),
      count: totalEvents,
    };

    setDiscoveries((prev) => {
      const filtered = prev.filter((d) => d.type !== 'date');
      return [
        ...filtered,
        {
          id: generateDiscoveryId(),
          type: 'date' as const,
          count: totalEvents,
          details: dateDetails,
          timestamp: new Date(),
        },
      ];
    });
  }, []);

  /**
   * Handle WebSocket discovery messages
   */
  const handleDiscoveryMessage = useCallback(
    (msg: WSMessage<WSDiscoveryUpdate | WSEntityStream>) => {
      if (!msg.data) return;

      const data = msg.data;
      if (data.event === 'entity_discovery') {
        handleEntityDiscovery(data as WSDiscoveryUpdate);
      } else if (data.event === 'entity_stream') {
        handleEntityStream(data as WSEntityStream);
      } else if (data.event === 'timeline_discovery') {
        handleTimelineDiscovery(data as WSDiscoveryUpdate);
      }
    },
    [handleEntityDiscovery, handleEntityStream, handleTimelineDiscovery]
  );

  /**
   * Handle WebSocket citation messages
   */
  const handleCitationMessage = useCallback(
    (msg: WSMessage<{ event?: string; total_acts?: number; citations_found?: number }>) => {
      if (!msg.data) return;

      const data = msg.data;
      // Handle act_discovery_update or citation_extraction_progress events
      if (data.event === 'act_discovery_update' || data.event === 'citation_extraction_progress') {
        const totalCitations = data.citations_found ?? data.total_acts ?? 0;
        if (totalCitations <= 0 || totalCitations === lastCitationCountRef.current) return;

        lastCitationCountRef.current = totalCitations;

        // We don't have detailed act names from WS, so just update the count
        // The full refresh will populate details
        setDiscoveries((prev) => {
          const existing = prev.find((d) => d.type === 'citation');
          if (existing) {
            // Update count in place
            return prev.map((d) =>
              d.type === 'citation'
                ? { ...d, count: totalCitations, timestamp: new Date() }
                : d
            );
          }
          // Add new citation discovery (details will be populated by refresh)
          return [
            ...prev,
            {
              id: generateDiscoveryId(),
              type: 'citation' as const,
              count: totalCitations,
              details: [] as DiscoveredCitation[],
              timestamp: new Date(),
            },
          ];
        });
      }
    },
    []
  );

  /**
   * Subscribe to WebSocket messages
   */
  useEffect(() => {
    if (!isConnected || !enabled) return;

    const unsubDiscovery = subscribe<WSDiscoveryUpdate>(
      'discovery_update',
      handleDiscoveryMessage
    );
    const unsubCitation = subscribe<{ event?: string; total_acts?: number; citations_found?: number }>(
      'citation_update',
      handleCitationMessage
    );

    return () => {
      unsubDiscovery();
      unsubCitation();
    };
  }, [isConnected, enabled, subscribe, handleDiscoveryMessage, handleCitationMessage]);

  /**
   * Fetch discovery data from all endpoints (initial load + polling fallback)
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

        if (totalEntities > 0 && totalEntities !== lastEntityCountRef.current) {
          lastEntityCountRef.current = totalEntities;

          const entityDetails: DiscoveredEntity[] = entities.map((e) => ({
            name: e.canonicalName,
            role: getEntityRole(e.entityType),
          }));

          newDiscoveries.push({
            id: generateDiscoveryId(),
            type: 'entity',
            count: totalEntities,
            details: entityDetails,
            timestamp: new Date(),
          });
        }
      }

      // Process timeline stats (dates)
      if (timelineResult.status === 'fulfilled' && timelineResult.value.data) {
        const stats = timelineResult.value.data;

        if (stats.totalEvents > 0 && stats.dateRangeStart && stats.dateRangeEnd) {
          const dateCount = stats.totalEvents;

          if (dateCount !== lastDateCountRef.current) {
            lastDateCountRef.current = dateCount;

            const dateDetails: DiscoveredDate = {
              earliest: new Date(stats.dateRangeStart),
              latest: new Date(stats.dateRangeEnd),
              count: dateCount,
            };

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

      // Process citations
      if (citationsResult.status === 'fulfilled' && citationsResult.value.acts) {
        const acts = citationsResult.value.acts;
        const totalCitations = acts.reduce((sum, act) => sum + act.citationCount, 0);

        if (acts.length > 0 && totalCitations > 0) {
          if (totalCitations !== lastCitationCountRef.current) {
            lastCitationCountRef.current = totalCitations;

            const citationDetails: DiscoveredCitation[] = acts
              .filter((act) => act.citationCount > 0)
              .slice(0, 5)
              .map((act) => ({
                actName: act.actName,
                count: act.citationCount,
              }));

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

      // Update discoveries - merge with existing or add new
      if (newDiscoveries.length > 0) {
        setDiscoveries((prev) => {
          const result = [...prev];
          for (const newDisc of newDiscoveries) {
            const existingIdx = result.findIndex((d) => d.type === newDisc.type);
            if (existingIdx >= 0) {
              result[existingIdx] = newDisc;
            } else {
              result.push(newDisc);
            }
          }
          return result;
        });
      }
    } catch (err) {
      if (!isMountedRef.current) return;

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

  /**
   * Initial fetch and polling fallback setup
   */
  useEffect(() => {
    isMountedRef.current = true;
    isCompleteRef.current = false;

    // Reset tracking refs when matterId changes
    lastEntityCountRef.current = 0;
    lastDateCountRef.current = 0;
    lastCitationCountRef.current = 0;
    setDiscoveries([]);

    // Don't poll if disabled or no matterId
    if (!enabled || !matterId) {
      return;
    }

    // Always do initial fetch
    void fetchDiscoveries();

    // Only poll if WebSocket is not connected
    if (!isRealTime) {
      const poll = () => {
        if (stopOnComplete && isCompleteRef.current) {
          return;
        }

        pollingRef.current = setTimeout(async () => {
          if (!isMountedRef.current) return;

          await fetchDiscoveries();

          if (!stopOnComplete || !isCompleteRef.current) {
            poll();
          }
        }, pollingInterval);
      };

      poll();
    }

    // Cleanup
    return () => {
      isMountedRef.current = false;
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [matterId, enabled, pollingInterval, stopOnComplete, isRealTime, fetchDiscoveries]);

  return {
    discoveries,
    isLoading,
    error,
    isRealTime,
    refresh,
  };
}

export default useLiveDiscoveries;
