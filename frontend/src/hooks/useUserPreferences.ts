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

/**
 * Onboarding wizard stages (Story 6.2)
 */
export type OnboardingStage =
  | 'dashboard'
  | 'upload'
  | 'settings'
  | 'summary'
  | 'timeline'
  | 'entities'
  | 'contradictions'
  | 'citations'
  | 'qa'
  | 'verification';

export interface UserPreferences {
  emailNotificationsProcessing: boolean;
  emailNotificationsVerification: boolean;
  browserNotifications: boolean;
  theme: 'light' | 'dark' | 'system';
  /** Story 6.1: When true, shows advanced features (bulk ops, keyboard shortcuts) */
  powerUserMode: boolean;
  /** Story 6.2: Whether user has completed the onboarding wizard */
  onboardingCompleted: boolean;
  /** Story 6.2: Current onboarding wizard stage */
  onboardingStage: OnboardingStage | null;
  createdAt: string;
  updatedAt: string;
}

export interface UpdatePreferencesRequest {
  emailNotificationsProcessing?: boolean;
  emailNotificationsVerification?: boolean;
  browserNotifications?: boolean;
  theme?: 'light' | 'dark' | 'system';
  /** Story 6.1: Progressive Disclosure toggle */
  powerUserMode?: boolean;
  /** Story 6.2: Mark onboarding as completed */
  onboardingCompleted?: boolean;
  /** Story 6.2: Update current onboarding stage */
  onboardingStage?: OnboardingStage | null;
}

interface ApiPreferencesResponse {
  email_notifications_processing: boolean;
  email_notifications_verification: boolean;
  browser_notifications: boolean;
  theme: 'light' | 'dark' | 'system';
  power_user_mode: boolean;
  onboarding_completed: boolean;
  onboarding_stage: OnboardingStage | null;
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
    powerUserMode: data.power_user_mode,
    onboardingCompleted: data.onboarding_completed,
    onboardingStage: data.onboarding_stage,
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
  if (data.powerUserMode !== undefined) {
    result.power_user_mode = data.powerUserMode;
  }
  if (data.onboardingCompleted !== undefined) {
    result.onboarding_completed = data.onboardingCompleted;
  }
  if (data.onboardingStage !== undefined) {
    result.onboarding_stage = data.onboardingStage;
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
