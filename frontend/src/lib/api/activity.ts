'use client';

import { api } from './client';
import type { Activity, DashboardStats } from '@/types/activity';

/**
 * API Response types matching backend models.
 * Story 14.5: Dashboard Real APIs
 */

interface ActivityListMeta {
  total: number;
}

interface ActivityListResponse {
  data: Activity[];
  meta: ActivityListMeta;
}

interface ActivityResponse {
  data: Activity;
}

interface DashboardStatsResponse {
  data: DashboardStats;
}

/**
 * Activity Feed API client functions.
 *
 * Story 14.5: Dashboard Real APIs
 *
 * These functions provide a typed interface to the activity feed and
 * dashboard stats API endpoints.
 */

/**
 * Get activity feed for the current user.
 *
 * @param options.limit - Maximum activities to return (1-50, default 10)
 * @param options.matterId - Optional filter by matter
 * @returns Activities list and total count
 */
export async function getActivities(options?: {
  limit?: number;
  matterId?: string;
}): Promise<{ activities: Activity[]; total: number }> {
  const params = new URLSearchParams();

  if (options?.limit) {
    params.set('limit', String(options.limit));
  }
  if (options?.matterId) {
    params.set('matterId', options.matterId);
  }

  const queryString = params.toString();
  const endpoint = queryString ? `/api/activity-feed?${queryString}` : '/api/activity-feed';

  const response = await api.get<ActivityListResponse>(endpoint);
  return { activities: response.data, total: response.meta.total };
}

/**
 * Mark an activity as read.
 *
 * @param activityId - Activity ID to mark as read
 * @returns Updated activity
 */
export async function markActivityRead(activityId: string): Promise<Activity> {
  const response = await api.patch<ActivityResponse>(
    `/api/activity-feed/${activityId}/read`,
    {}
  );
  return response.data;
}

/**
 * Get dashboard statistics for the current user.
 *
 * @returns Dashboard stats (active matters, verified findings, pending reviews)
 */
export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await api.get<DashboardStatsResponse>('/api/dashboard/stats');
  return response.data;
}

/**
 * Activity API object for convenience.
 *
 * Story 14.5: Dashboard Real APIs
 */
export const activityApi = {
  list: getActivities,
  markRead: markActivityRead,
};

/**
 * Dashboard API object for convenience.
 *
 * Story 14.5: Dashboard Real APIs
 */
export const dashboardApi = {
  getStats: getDashboardStats,
};
