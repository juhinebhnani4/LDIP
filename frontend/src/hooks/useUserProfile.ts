'use client';

/**
 * useUserProfile Hook
 *
 * SWR hook for managing user profile information.
 *
 * Story 14.14: Settings Page Implementation
 * Task 3: Create useUserProfile hook
 */

import useSWR from 'swr';
import useSWRMutation from 'swr/mutation';
import { api } from '@/lib/api/client';

// =============================================================================
// Types
// =============================================================================

export interface UserProfile {
  id: string;
  email: string;
  fullName: string | null;
  avatarUrl: string | null;
}

export interface UpdateProfileRequest {
  fullName?: string;
  avatarUrl?: string;
}

interface ApiProfileResponse {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
}

// =============================================================================
// Transform Functions
// =============================================================================

function transformProfile(data: ApiProfileResponse): UserProfile {
  return {
    id: data.id,
    email: data.email,
    fullName: data.full_name,
    avatarUrl: data.avatar_url,
  };
}

function transformUpdateRequest(data: UpdateProfileRequest): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  if (data.fullName !== undefined) {
    result.full_name = data.fullName;
  }
  if (data.avatarUrl !== undefined) {
    result.avatar_url = data.avatarUrl;
  }

  return result;
}

// =============================================================================
// Fetcher
// =============================================================================

async function fetchProfile(): Promise<UserProfile> {
  const response = await api.get<ApiProfileResponse>('/api/users/me/profile');
  return transformProfile(response);
}

async function updateProfile(
  url: string,
  { arg }: { arg: UpdateProfileRequest }
): Promise<UserProfile> {
  const payload = transformUpdateRequest(arg);
  const response = await api.patch<ApiProfileResponse>(url, payload);
  return transformProfile(response);
}

// =============================================================================
// Hook
// =============================================================================

export interface UseUserProfileReturn {
  profile: UserProfile | undefined;
  isLoading: boolean;
  error: Error | undefined;
  updateProfile: (data: UpdateProfileRequest) => Promise<UserProfile>;
  isUpdating: boolean;
  updateError: Error | undefined;
  refresh: () => void;
}

export function useUserProfile(): UseUserProfileReturn {
  const { data, error, isLoading, mutate } = useSWR<UserProfile, Error>(
    '/api/users/me/profile',
    fetchProfile,
    {
      revalidateOnFocus: false,
    }
  );

  const { trigger, isMutating, error: mutationError } = useSWRMutation(
    '/api/users/me/profile',
    updateProfile,
    {
      onSuccess: (updatedData) => {
        mutate(updatedData, false);
      },
    }
  );

  return {
    profile: data,
    isLoading,
    error,
    updateProfile: trigger,
    isUpdating: isMutating,
    updateError: mutationError,
    refresh: () => mutate(),
  };
}
