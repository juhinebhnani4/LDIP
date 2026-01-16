/**
 * Tab Stats API Client
 *
 * Story 14.12: Tab Stats API (Task 4.1)
 *
 * Provides API functions for fetching tab statistics for the workspace tab bar.
 */

import { api } from './client'

import type { TabStats, TabProcessingStatus, TabId } from '@/stores/workspaceStore'

/**
 * Tab counts response structure from API.
 * Uses camelCase as API is configured with aliases.
 */
interface TabCountsData {
  summary: TabStats
  timeline: TabStats
  entities: TabStats
  citations: TabStats
  contradictions: TabStats
  verification: TabStats
  documents: TabStats
}

/**
 * Tab processing status response structure from API.
 */
interface TabProcessingStatusData {
  summary: TabProcessingStatus
  timeline: TabProcessingStatus
  entities: TabProcessingStatus
  citations: TabProcessingStatus
  contradictions: TabProcessingStatus
  verification: TabProcessingStatus
  documents: TabProcessingStatus
}

/**
 * Tab stats data structure from API.
 */
interface TabStatsData {
  tabCounts: TabCountsData
  tabProcessingStatus: TabProcessingStatusData
}

/**
 * API response wrapper for tab stats.
 */
export interface TabStatsResponse {
  data: TabStatsData
}

/**
 * Fetch tab statistics for a matter.
 *
 * Story 14.12: AC #4 - Wire frontend to real API.
 *
 * @param matterId - Matter ID to fetch stats for.
 * @returns TabStatsResponse with counts and processing status.
 * @throws ApiError if the request fails.
 */
export async function fetchTabStats(matterId: string): Promise<TabStatsResponse> {
  return api.get<TabStatsResponse>(`/api/matters/${matterId}/tab-stats`)
}

/**
 * Convert API response to store-compatible format.
 *
 * @param response - API response data.
 * @returns Object with tabCounts and tabProcessingStatus in store format.
 */
export function transformTabStatsResponse(response: TabStatsResponse): {
  tabCounts: Partial<Record<TabId, TabStats>>
  tabProcessingStatus: Partial<Record<TabId, TabProcessingStatus>>
} {
  const { tabCounts, tabProcessingStatus } = response.data

  return {
    tabCounts: {
      summary: tabCounts.summary,
      timeline: tabCounts.timeline,
      entities: tabCounts.entities,
      citations: tabCounts.citations,
      contradictions: tabCounts.contradictions,
      verification: tabCounts.verification,
      documents: tabCounts.documents,
    },
    tabProcessingStatus: {
      summary: tabProcessingStatus.summary,
      timeline: tabProcessingStatus.timeline,
      entities: tabProcessingStatus.entities,
      citations: tabProcessingStatus.citations,
      contradictions: tabProcessingStatus.contradictions,
      verification: tabProcessingStatus.verification,
      documents: tabProcessingStatus.documents,
    },
  }
}
