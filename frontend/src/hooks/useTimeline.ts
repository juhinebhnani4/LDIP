/**
 * Timeline Hook
 *
 * SWR hook for fetching timeline data with entity information.
 * Connected to real backend API at /api/matters/{matterId}/timeline/full
 *
 * Story 10B.3: Timeline Tab Vertical List View
 * Story 10B.5: Timeline Filtering and Manual Event Addition
 */

import { useMemo, useCallback } from 'react';
import useSWR from 'swr';
import type {
  TimelineEvent,
  TimelineResponse,
  UseTimelineOptions,
  TimelineFilterState,
} from '@/types/timeline';

/**
 * Convert API response to camelCase frontend types.
 * Handles both snake_case and camelCase responses for backward compatibility.
 */
function transformEvent(event: Record<string, unknown>): TimelineEvent {
  return {
    id: event.id as string,
    eventDate: (event.eventDate ?? event.event_date) as string,
    eventDatePrecision: (event.eventDatePrecision ?? event.event_date_precision) as TimelineEvent['eventDatePrecision'],
    eventDateText: ((event.eventDateText ?? event.event_date_text) as string | null) ?? null,
    eventType: (event.eventType ?? event.event_type) as TimelineEvent['eventType'],
    description: event.description as string,
    documentId: ((event.documentId ?? event.document_id) as string | null) ?? null,
    documentName: ((event.documentName ?? event.document_name) as string | null) ?? null,
    sourcePage: ((event.sourcePage ?? event.source_page) as number | null) ?? null,
    confidence: event.confidence as number,
    entities: Array.isArray(event.entities)
      ? event.entities.map((e: Record<string, unknown>) => ({
          entityId: (e.entityId ?? e.entity_id) as string,
          canonicalName: (e.canonicalName ?? e.canonical_name) as string,
          entityType: (e.entityType ?? e.entity_type) as string,
          role: ((e.role) as string | null) ?? null,
        }))
      : [],
    isAmbiguous: ((event.isAmbiguous ?? event.is_ambiguous) as boolean) ?? false,
    isVerified: ((event.isVerified ?? event.is_verified) as boolean) ?? false,
    crossReferences: (event.crossReferences ?? event.cross_references) as string[] | undefined,
    hasContradiction: (event.hasContradiction ?? event.has_contradiction) as boolean | undefined,
    contradictionDetails: (event.contradictionDetails ?? event.contradiction_details) as string | undefined,
    isManual: (event.isManual ?? event.is_manual) as boolean | undefined,
    createdBy: (event.createdBy ?? event.created_by) as string | undefined,
  };
}

/**
 * Apply filters to events (client-side filtering for MVP)
 * Server-side filtering will be added in production
 */
function applyFilters(
  events: TimelineEvent[],
  filters: TimelineFilterState
): TimelineEvent[] {
  return events.filter((event) => {
    // Filter by event types
    if (filters.eventTypes.length > 0 && !filters.eventTypes.includes(event.eventType)) {
      return false;
    }

    // Filter by entity IDs
    if (filters.entityIds.length > 0) {
      const eventEntityIds = event.entities.map((e) => e.entityId);
      const hasMatchingEntity = filters.entityIds.some((id) => eventEntityIds.includes(id));
      if (!hasMatchingEntity) {
        return false;
      }
    }

    // Filter by date range
    if (filters.dateRange.start) {
      const eventDate = new Date(event.eventDate);
      const startDate = new Date(filters.dateRange.start);
      if (eventDate < startDate) {
        return false;
      }
    }
    if (filters.dateRange.end) {
      const eventDate = new Date(event.eventDate);
      const endDate = new Date(filters.dateRange.end);
      if (eventDate > endDate) {
        return false;
      }
    }

    // Filter by verification status
    if (filters.verificationStatus === 'verified' && !event.isVerified) {
      return false;
    }
    if (filters.verificationStatus === 'unverified' && event.isVerified) {
      return false;
    }

    return true;
  });
}

/**
 * Real fetcher for production - transforms API response to camelCase.
 * Handles both snake_case and camelCase responses for backward compatibility.
 */
async function fetcher(url: string): Promise<TimelineResponse> {
  const { api } = await import('@/lib/api/client');
  const response = await api.get<{
    data: Record<string, unknown>[];
    meta: Record<string, unknown>;
  }>(url);

  // Transform API response to camelCase (handles both snake_case and camelCase)
  return {
    data: response.data.map(transformEvent),
    meta: {
      total: (response.meta.total ?? 0) as number,
      page: (response.meta.page ?? 1) as number,
      perPage: ((response.meta.perPage ?? response.meta.per_page) ?? 20) as number,
      totalPages: ((response.meta.totalPages ?? response.meta.total_pages) ?? 0) as number,
    },
  };
}

/**
 * Extended options for useTimeline hook with filtering
 */
export interface UseTimelineOptionsWithFilters extends UseTimelineOptions {
  /** Filter state for client-side filtering */
  filters?: TimelineFilterState;
}

/**
 * Hook for fetching timeline data with entity information
 *
 * @param matterId - The matter ID to fetch timeline for
 * @param options - Optional filtering and pagination options
 * @returns Timeline data, loading state, error state, and mutate function
 *
 * @example
 * ```tsx
 * const { events, filteredEvents, meta, isLoading, isError, mutate } = useTimeline(matterId, { filters });
 *
 * if (isLoading) return <TimelineSkeleton />;
 * if (isError) return <TimelineError />;
 *
 * return <TimelineList events={filteredEvents} />;
 * ```
 */
export function useTimeline(matterId: string, options: UseTimelineOptionsWithFilters = {}) {
  // Default to 500 events to load comprehensive timeline data
  // This provides better chronological coverage while maintaining reasonable performance
  const { eventType, entityId, page = 1, perPage = 500, filters } = options;

  // Build URL with query params
  const params = new URLSearchParams();
  if (eventType) params.set('event_type', eventType);
  if (entityId) params.set('entity_id', entityId);
  params.set('page', String(page));
  params.set('per_page', String(perPage));

  const { data, error, isLoading, mutate } = useSWR<TimelineResponse>(
    matterId ? `/api/matters/${matterId}/timeline/full?${params.toString()}` : null,
    fetcher,
    {
      // Keep data fresh but don't refetch too frequently
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 seconds
    }
  );

  // All events from the API
  const events = data?.data ?? [];

  // Apply filters if provided (client-side filtering for MVP)
  const filteredEvents = useMemo(() => {
    if (!filters) return events;
    return applyFilters(events, filters);
  }, [events, filters]);

  // Get unique entities from all events for filter options
  const uniqueEntities = useMemo(() => {
    const entityMap = new Map<string, { id: string; name: string }>();
    events.forEach((event) => {
      event.entities.forEach((entity) => {
        if (!entityMap.has(entity.entityId)) {
          entityMap.set(entity.entityId, {
            id: entity.entityId,
            name: entity.canonicalName,
          });
        }
      });
    });
    return Array.from(entityMap.values());
  }, [events]);

  // Helper to add a manual event optimistically
  const addEvent = useCallback(
    (newEvent: TimelineEvent) => {
      mutate(
        (current) => {
          if (!current) return current;
          return {
            ...current,
            data: [...current.data, newEvent].sort(
              (a, b) => new Date(a.eventDate).getTime() - new Date(b.eventDate).getTime()
            ),
            meta: {
              ...current.meta,
              total: current.meta.total + 1,
            },
          };
        },
        { revalidate: false }
      );
    },
    [mutate]
  );

  // Helper to update an event optimistically
  const updateEvent = useCallback(
    (eventId: string, updates: Partial<TimelineEvent>) => {
      mutate(
        (current) => {
          if (!current) return current;
          return {
            ...current,
            data: current.data.map((event) =>
              event.id === eventId ? { ...event, ...updates } : event
            ),
          };
        },
        { revalidate: false }
      );
    },
    [mutate]
  );

  // Helper to delete an event optimistically
  const deleteEvent = useCallback(
    (eventId: string) => {
      mutate(
        (current) => {
          if (!current) return current;
          return {
            ...current,
            data: current.data.filter((event) => event.id !== eventId),
            meta: {
              ...current.meta,
              total: current.meta.total - 1,
            },
          };
        },
        { revalidate: false }
      );
    },
    [mutate]
  );

  return {
    /** All timeline events (unfiltered) */
    events,
    /** Filtered timeline events based on current filters */
    filteredEvents,
    /** Pagination metadata */
    meta: data?.meta,
    /** Unique entities from events (for filter options) */
    uniqueEntities,
    /** Whether the data is currently loading */
    isLoading,
    /** Whether an error occurred */
    isError: !!error,
    /** Error object if available */
    error,
    /** Function to manually revalidate */
    mutate,
    /** Add an event optimistically */
    addEvent,
    /** Update an event optimistically */
    updateEvent,
    /** Delete an event optimistically */
    deleteEvent,
  };
}
