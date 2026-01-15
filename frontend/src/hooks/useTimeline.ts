/**
 * Timeline Hook
 *
 * SWR hook for fetching timeline data with entity information.
 * Uses mock data for MVP - actual API integration exists.
 *
 * Story 10B.3: Timeline Tab Vertical List View
 */

import useSWR from 'swr';
import type {
  TimelineEvent,
  TimelineResponse,
  UseTimelineOptions,
} from '@/types/timeline';

/** Mock data for MVP - demonstrates UI functionality */
const MOCK_EVENTS: TimelineEvent[] = [
  {
    id: 'evt-1',
    eventDate: '2016-05-15',
    eventDatePrecision: 'day',
    eventDateText: '15th May 2016',
    eventType: 'filing',
    description:
      'RTI Application filed by Nirav D. Jobalia requesting disclosure of infrastructure development contracts.',
    documentId: 'doc-1',
    sourcePage: 1,
    confidence: 0.95,
    entities: [
      {
        entityId: 'ent-1',
        canonicalName: 'Nirav D. Jobalia',
        entityType: 'PERSON',
        role: 'petitioner',
      },
    ],
    isAmbiguous: false,
    isVerified: true,
  },
  {
    id: 'evt-2',
    eventDate: '2016-06-10',
    eventDatePrecision: 'day',
    eventDateText: '10th June 2016',
    eventType: 'notice',
    description:
      'Notice issued to Custodian of Records requesting response within 30 days.',
    documentId: 'doc-2',
    sourcePage: 1,
    confidence: 0.92,
    entities: [
      {
        entityId: 'ent-2',
        canonicalName: 'Custodian of Records',
        entityType: 'ORG',
        role: 'respondent',
      },
    ],
    isAmbiguous: false,
    isVerified: false,
  },
  {
    id: 'evt-3',
    eventDate: '2018-02-20',
    eventDatePrecision: 'day',
    eventDateText: '20th February 2018',
    eventType: 'order',
    description:
      'Court order directing respondent to provide detailed response on exemption claims.',
    documentId: 'doc-3',
    sourcePage: 2,
    confidence: 0.98,
    entities: [
      {
        entityId: 'ent-3',
        canonicalName: 'Special Court, Ahmedabad',
        entityType: 'INSTITUTION',
        role: null,
      },
    ],
    isAmbiguous: false,
    isVerified: true,
  },
  {
    id: 'evt-4',
    eventDate: '2018-03-15',
    eventDatePrecision: 'day',
    eventDateText: '15th March 2018',
    eventType: 'hearing',
    description:
      'Hearing held for arguments on Section 8 exemption applicability.',
    documentId: 'doc-4',
    sourcePage: 1,
    confidence: 0.88,
    entities: [
      {
        entityId: 'ent-1',
        canonicalName: 'Nirav D. Jobalia',
        entityType: 'PERSON',
        role: 'petitioner',
      },
      {
        entityId: 'ent-2',
        canonicalName: 'Custodian of Records',
        entityType: 'ORG',
        role: 'respondent',
      },
    ],
    isAmbiguous: false,
    isVerified: false,
    hasContradiction: true,
    contradictionDetails:
      'Respondent claims documents were provided, petitioner disputes this.',
  },
  {
    id: 'evt-5',
    eventDate: '2020-08-01',
    eventDatePrecision: 'month',
    eventDateText: 'August 2020',
    eventType: 'transaction',
    description:
      'Infrastructure contract #IC-2020-045 executed for highway development project.',
    documentId: 'doc-5',
    sourcePage: 12,
    confidence: 0.75,
    entities: [
      {
        entityId: 'ent-4',
        canonicalName: 'Gujarat State Road Corp',
        entityType: 'ORG',
        role: null,
      },
    ],
    isAmbiguous: false,
    isVerified: false,
  },
  {
    id: 'evt-6',
    eventDate: '2023-01-10',
    eventDatePrecision: 'day',
    eventDateText: '10th January 2023',
    eventType: 'deadline',
    description:
      'Statutory deadline for filing response to RTI appeal under Section 19.',
    documentId: 'doc-6',
    sourcePage: 1,
    confidence: 0.93,
    entities: [],
    isAmbiguous: false,
    isVerified: true,
  },
  {
    id: 'evt-7',
    eventDate: '2024-01-15',
    eventDatePrecision: 'day',
    eventDateText: '15th January 2024',
    eventType: 'order',
    description:
      'Final order issued directing partial disclosure of non-exempt documents within 30 days.',
    documentId: 'doc-7',
    sourcePage: 5,
    confidence: 0.97,
    entities: [
      {
        entityId: 'ent-3',
        canonicalName: 'Special Court, Ahmedabad',
        entityType: 'INSTITUTION',
        role: null,
      },
    ],
    isAmbiguous: false,
    isVerified: true,
  },
];

/**
 * Convert snake_case API response to camelCase frontend types
 */
function transformEvent(event: Record<string, unknown>): TimelineEvent {
  return {
    id: event.id as string,
    eventDate: event.event_date as string,
    eventDatePrecision: event.event_date_precision as TimelineEvent['eventDatePrecision'],
    eventDateText: (event.event_date_text as string | null) ?? null,
    eventType: event.event_type as TimelineEvent['eventType'],
    description: event.description as string,
    documentId: (event.document_id as string | null) ?? null,
    sourcePage: (event.source_page as number | null) ?? null,
    confidence: event.confidence as number,
    entities: Array.isArray(event.entities)
      ? event.entities.map((e: Record<string, unknown>) => ({
          entityId: e.entity_id as string,
          canonicalName: e.canonical_name as string,
          entityType: e.entity_type as string,
          role: (e.role as string | null) ?? null,
        }))
      : [],
    isAmbiguous: (event.is_ambiguous as boolean) ?? false,
    isVerified: (event.is_verified as boolean) ?? false,
    crossReferences: event.cross_references as string[] | undefined,
    hasContradiction: event.has_contradiction as boolean | undefined,
    contradictionDetails: event.contradiction_details as string | undefined,
  };
}

/**
 * Mock fetcher for MVP - simulates API call
 * TODO: Replace with actual API call when ready
 */
async function mockFetcher(url: string): Promise<TimelineResponse> {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 600));

  // Parse URL to get page and perPage
  const urlObj = new URL(url, 'http://localhost');
  const page = parseInt(urlObj.searchParams.get('page') ?? '1', 10);
  const perPage = parseInt(urlObj.searchParams.get('per_page') ?? '50', 10);

  // Apply pagination to mock data
  const total = MOCK_EVENTS.length;
  const totalPages = Math.ceil(total / perPage);
  const start = (page - 1) * perPage;
  const end = start + perPage;
  const paginatedEvents = MOCK_EVENTS.slice(start, end);

  return {
    data: paginatedEvents,
    meta: {
      total,
      page,
      perPage,
      totalPages,
    },
  };
}

/**
 * Real fetcher for production - transforms snake_case to camelCase
 * TODO(Story-10B.5): Enable this when backend API is verified and working
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
async function realFetcher(url: string): Promise<TimelineResponse> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error('Failed to fetch timeline');
  }
  const json = await res.json();

  // Transform snake_case API response to camelCase
  return {
    data: json.data.map(transformEvent),
    meta: {
      total: json.meta.total,
      page: json.meta.page,
      perPage: json.meta.per_page,
      totalPages: json.meta.total_pages,
    },
  };
}

// TODO(Story-10B.5): Switch to realFetcher when backend API is verified
const fetcher = mockFetcher;

/**
 * Hook for fetching timeline data with entity information
 *
 * @param matterId - The matter ID to fetch timeline for
 * @param options - Optional filtering and pagination options
 * @returns Timeline data, loading state, error state, and mutate function
 *
 * @example
 * ```tsx
 * const { events, meta, isLoading, isError, mutate } = useTimeline(matterId);
 *
 * if (isLoading) return <TimelineSkeleton />;
 * if (isError) return <TimelineError />;
 *
 * return <TimelineList events={events} />;
 * ```
 */
export function useTimeline(matterId: string, options: UseTimelineOptions = {}) {
  const { eventType, entityId, page = 1, perPage = 50 } = options;

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

  return {
    /** The timeline events */
    events: data?.data ?? [],
    /** Pagination metadata */
    meta: data?.meta,
    /** Whether the data is currently loading */
    isLoading,
    /** Whether an error occurred */
    isError: !!error,
    /** Error object if available */
    error,
    /** Function to manually revalidate */
    mutate,
  };
}
