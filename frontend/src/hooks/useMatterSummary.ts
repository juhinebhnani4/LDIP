/**
 * Matter Summary Hook
 *
 * SWR hook for fetching matter summary data.
 * Uses mock data for MVP - actual API integration in later story.
 *
 * Story 10B.1: Summary Tab Content
 */

import useSWR from 'swr';
import type { MatterSummary, MatterSummaryResponse } from '@/types/summary';

/** Mock data for MVP - API does not exist yet */
const MOCK_SUMMARY: MatterSummary = {
  matterId: '',
  attentionItems: [
    {
      type: 'contradiction',
      count: 3,
      label: 'contradictions detected',
      targetTab: 'verification',
    },
    {
      type: 'citation_issue',
      count: 2,
      label: 'citations need verification',
      targetTab: 'citations',
    },
    {
      type: 'timeline_gap',
      count: 1,
      label: 'timeline gap identified',
      targetTab: 'timeline',
    },
  ],
  parties: [
    {
      entityId: 'mock-petitioner-1',
      entityName: 'Nirav D. Jobalia',
      role: 'petitioner',
      sourceDocument: 'Petition.pdf',
      sourcePage: 1,
      isVerified: false,
    },
    {
      entityId: 'mock-respondent-1',
      entityName: 'The Custodian of Records',
      role: 'respondent',
      sourceDocument: 'Petition.pdf',
      sourcePage: 2,
      isVerified: false,
    },
  ],
  subjectMatter: {
    description:
      'This matter concerns a Right to Information (RTI) application seeking disclosure of records related to infrastructure development contracts awarded between 2020-2023.',
    sources: [
      { documentName: 'Petition.pdf', pageRange: '1-3' },
      { documentName: 'Application.pdf', pageRange: '1-2' },
    ],
    isVerified: false,
  },
  currentStatus: {
    lastOrderDate: new Date().toISOString(),
    description:
      'Matter adjourned for hearing on next available date. Respondent directed to file reply within 15 days.',
    sourceDocument: 'Order_2024_01.pdf',
    sourcePage: 1,
    isVerified: false,
  },
  keyIssues: [
    {
      id: 'issue-1',
      number: 1,
      title: 'Whether the requested documents fall under exempted categories under Section 8?',
      verificationStatus: 'pending',
    },
    {
      id: 'issue-2',
      number: 2,
      title: 'Whether partial disclosure is warranted under Section 10?',
      verificationStatus: 'verified',
    },
    {
      id: 'issue-3',
      number: 3,
      title: 'Whether there was unreasonable delay in responding to the RTI application?',
      verificationStatus: 'flagged',
    },
  ],
  stats: {
    totalPages: 156,
    entitiesFound: 24,
    eventsExtracted: 18,
    citationsFound: 42,
    verificationPercent: 67,
  },
  generatedAt: new Date().toISOString(),
};

/**
 * Mock fetcher for MVP
 * TODO: Replace with actual API call to GET /api/matters/{matterId}/summary
 */
async function mockFetcher(url: string): Promise<MatterSummaryResponse> {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Extract matterId from URL format: /api/matters/{matterId}/summary
  // at(-2) gets the second-to-last segment which is the matterId
  const matterId = url.split('/').at(-2) ?? '';

  return {
    data: {
      ...MOCK_SUMMARY,
      matterId,
    },
  };
}

/**
 * Hook for fetching matter summary data
 *
 * @param matterId - The matter ID to fetch summary for
 * @returns Summary data, loading state, error state, and mutate function
 *
 * @example
 * ```tsx
 * const { summary, isLoading, isError, mutate } = useMatterSummary(matterId);
 *
 * if (isLoading) return <SummarySkeleton />;
 * if (isError) return <SummaryError />;
 *
 * return <SummaryContent summary={summary} />;
 * ```
 */
export function useMatterSummary(matterId: string) {
  const { data, error, isLoading, mutate } = useSWR<MatterSummaryResponse>(
    matterId ? `/api/matters/${matterId}/summary` : null,
    mockFetcher,
    {
      // Keep data fresh but don't refetch too frequently
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 seconds
    }
  );

  return {
    /** The matter summary data */
    summary: data?.data,
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
