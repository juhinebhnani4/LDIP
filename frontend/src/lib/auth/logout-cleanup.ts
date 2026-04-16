/**
 * Centralized Logout Cleanup
 *
 * BUG-001 Fix: Prevents cross-user data leakage by clearing ALL frontend
 * state on logout or user switch. Without this, switching users in the same
 * browser leaks the previous user's cached data (Zustand stores, localStorage,
 * SWR cache, API session cache).
 *
 * Called by:
 * 1. LogoutButton.tsx — before redirect
 * 2. UserProfileDropdown.tsx — before redirect
 * 3. useAuth.ts onAuthStateChange — on SIGNED_OUT event
 */

import { STORAGE_KEY_PREFIX as CHAT_STORAGE_PREFIX } from '@/stores/chatStore';
import { clearSessionCache } from '@/lib/api/client';
import { mutate } from 'swr';

/**
 * Clear all app-specific keys from localStorage.
 * This covers all persisted Zustand stores and other app data.
 *
 * Known keys:
 * - ldip-chat-history:* (chat store, per-matter)
 * - ldip-model-preferences (model store)
 * - ldip-qa-panel-preferences (QA panel store)
 * - ldip-inspector-preferences (inspector store)
 * - ldip-feature-tour-completed (feature tour)
 * - ldip-onboarding-in-progress (onboarding wizard)
 * - ldip:bbox:* (bounding box cache)
 * - dashboard_view_preference (matter store view mode)
 * - citations-view-mode, citations-grouping-enabled (citation prefs)
 */
function clearAppLocalStorage(): void {
  if (typeof window === 'undefined') return;

  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && (
      key.startsWith('ldip-') ||
      key.startsWith('ldip:') ||
      key.startsWith(CHAT_STORAGE_PREFIX) ||
      key === 'dashboard_view_preference' ||
      key === 'citations-view-mode' ||
      key === 'citations-grouping-enabled'
    )) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach((key) => localStorage.removeItem(key));
}

/**
 * Clear the global SWR cache.
 * Prevents stale API data from a previous user being shown.
 */
function clearSWRCache(): void {
  try {
    void mutate(
      () => true,
      undefined,
      { revalidate: false }
    );
  } catch {
    // SWR cache clear is best-effort
  }
}

/**
 * Master cleanup function — call on logout or user switch.
 *
 * Clears all frontend caches and persisted state. After calling this,
 * the caller should perform a HARD redirect (window.location.href) to
 * ensure all in-memory Zustand stores are also re-initialized.
 *
 * Order matters:
 * 1. Clear API session cache (prevents stale auth tokens)
 * 2. Clear localStorage (prevents persisted store re-hydration)
 * 3. Clear SWR cache (prevents stale API responses)
 */
export function cleanupOnLogout(): void {
  // 1. Clear API session cache (auth tokens)
  clearSessionCache();

  // 2. Clear persisted localStorage data
  clearAppLocalStorage();

  // 3. Clear SWR cache
  clearSWRCache();
}
