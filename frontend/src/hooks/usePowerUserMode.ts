'use client';

/**
 * usePowerUserMode Hook
 *
 * Convenience hook for checking and toggling Power User Mode.
 * Use this throughout the app to gate advanced features.
 *
 * Story 6.1: Progressive Disclosure UI
 * Task 6.1.7: Create usePowerUserMode() convenience hook
 *
 * @example
 * ```tsx
 * const { isPowerUser, isLoading } = usePowerUserMode();
 *
 * // Gate a feature
 * if (isPowerUser) {
 *   return <BulkOperationsToolbar />;
 * }
 * ```
 */

import { useUserPreferences } from './useUserPreferences';

export interface UsePowerUserModeReturn {
  /** Whether Power User Mode is enabled */
  isPowerUser: boolean;
  /** Whether preferences are still loading */
  isLoading: boolean;
  /** Toggle Power User Mode */
  togglePowerUserMode: () => Promise<void>;
  /** Set Power User Mode explicitly */
  setPowerUserMode: (enabled: boolean) => Promise<void>;
}

export function usePowerUserMode(): UsePowerUserModeReturn {
  const { preferences, isLoading, updatePreferences } = useUserPreferences();

  const isPowerUser = preferences?.powerUserMode ?? false;

  const togglePowerUserMode = async () => {
    await updatePreferences({ powerUserMode: !isPowerUser });
  };

  const setPowerUserMode = async (enabled: boolean) => {
    await updatePreferences({ powerUserMode: enabled });
  };

  return {
    isPowerUser,
    isLoading,
    togglePowerUserMode,
    setPowerUserMode,
  };
}
