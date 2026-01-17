'use client';

/**
 * useUserPreferences Hook
 *
 * SWR hook for managing user notification and appearance preferences.
 *
 * Story 14.14: Settings Page Implementation
 * Task 2: Create useUserPreferences hook
 */

import useSWR from 'swr';
import useSWRMutation from 'swr/mutation';
import { api } from '@/lib/api/client';

// =============================================================================
// Types
// =============================================================================

export interface UserPreferences {
  emailNotificationsProcessing: boolean;
  emailNotificationsVerification: boolean;
  browserNotifications: boolean;
  theme: 'light' | 'dark' | 'system';
  createdAt: string;
  updatedAt: string;
}

export interface UpdatePreferencesRequest {
  emailNotificationsProcessing?: boolean;
  emailNotificationsVerification?: boolean;
  browserNotifications?: boolean;
  theme?: 'light' | 'dark' | 'system';
}

interface ApiPreferencesResponse {
  email_notifications_processing: boolean;
  email_notifications_verification: boolean;
  browser_notifications: boolean;
  theme: 'light' | 'dark' | 'system';
  created_at: string;
  updated_at: string;
}

// =============================================================================
// Transform Functions
// =============================================================================

function transformPreferences(data: ApiPreferencesResponse): UserPreferences {
  return {
    emailNotificationsProcessing: data.email_notifications_processing,
    emailNotificationsVerification: data.email_notifications_verification,
    browserNotifications: data.browser_notifications,
    theme: data.theme,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  };
}

function transformUpdateRequest(data: UpdatePreferencesRequest): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  if (data.emailNotificationsProcessing !== undefined) {
    result.email_notifications_processing = data.emailNotificationsProcessing;
  }
  if (data.emailNotificationsVerification !== undefined) {
    result.email_notifications_verification = data.emailNotificationsVerification;
  }
  if (data.browserNotifications !== undefined) {
    result.browser_notifications = data.browserNotifications;
  }
  if (data.theme !== undefined) {
    result.theme = data.theme;
  }

  return result;
}

// =============================================================================
// Fetcher
// =============================================================================

async function fetchPreferences(): Promise<UserPreferences> {
  const response = await api.get<ApiPreferencesResponse>('/api/users/me/preferences');
  return transformPreferences(response);
}

async function updatePreferences(
  url: string,
  { arg }: { arg: UpdatePreferencesRequest }
): Promise<UserPreferences> {
  const payload = transformUpdateRequest(arg);
  const response = await api.patch<ApiPreferencesResponse>(url, payload);
  return transformPreferences(response);
}

// =============================================================================
// Hook
// =============================================================================

export interface UseUserPreferencesReturn {
  preferences: UserPreferences | undefined;
  isLoading: boolean;
  error: Error | undefined;
  updatePreferences: (data: UpdatePreferencesRequest) => Promise<UserPreferences>;
  isUpdating: boolean;
  updateError: Error | undefined;
  refresh: () => void;
}

export function useUserPreferences(): UseUserPreferencesReturn {
  const { data, error, isLoading, mutate } = useSWR<UserPreferences, Error>(
    '/api/users/me/preferences',
    fetchPreferences,
    {
      revalidateOnFocus: false,
    }
  );

  const { trigger, isMutating, error: mutationError } = useSWRMutation(
    '/api/users/me/preferences',
    updatePreferences,
    {
      onSuccess: (updatedData) => {
        mutate(updatedData, false);
      },
    }
  );

  return {
    preferences: data,
    isLoading,
    error,
    updatePreferences: trigger,
    isUpdating: isMutating,
    updateError: mutationError,
    refresh: () => mutate(),
  };
}
