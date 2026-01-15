/**
 * Background Processing Store
 *
 * Zustand store for tracking matters being processed in the background.
 * Used when user clicks "Continue in Background" during processing.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const backgroundMatters = useBackgroundProcessingStore((state) => state.backgroundMatters);
 *   const addBackgroundMatter = useBackgroundProcessingStore((state) => state.addBackgroundMatter);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { backgroundMatters, addBackgroundMatter } = useBackgroundProcessingStore();
 *
 * Story 9-6: Implement Upload Flow Stage 5 and Notifications
 */

import { create } from 'zustand';
import {
  showProcessingCompleteNotification,
  showNotificationFallback,
  getNotificationPermission,
} from '@/lib/utils/browser-notifications';
import { useNotificationStore } from './notificationStore';

/**
 * Background matter tracking state
 */
export interface BackgroundMatter {
  /** Unique matter ID */
  matterId: string;
  /** Human-readable matter name */
  matterName: string;
  /** Current progress percentage (0-100) */
  progressPct: number;
  /** Current processing status */
  status: 'processing' | 'ready' | 'error';
  /** When background processing started */
  startedAt: Date;
  /** Estimated completion time (optional) */
  estimatedCompletion?: Date;
}

interface BackgroundProcessingState {
  /** Map of matters being processed in background */
  backgroundMatters: Map<string, BackgroundMatter>;
  /** Whether any matters are processing in background */
  isProcessingInBackground: boolean;
}

interface BackgroundProcessingActions {
  /** Add a matter to background processing */
  addBackgroundMatter: (matter: BackgroundMatter) => void;
  /** Update a background matter's progress/status */
  updateBackgroundMatter: (matterId: string, updates: Partial<BackgroundMatter>) => void;
  /** Remove a matter from background tracking */
  removeBackgroundMatter: (matterId: string) => void;
  /** Mark a matter as complete and trigger notifications */
  markComplete: (matterId: string) => void;
  /** Clear all background matters */
  clearAll: () => void;
}

type BackgroundProcessingStore = BackgroundProcessingState & BackgroundProcessingActions;

export const useBackgroundProcessingStore = create<BackgroundProcessingStore>()((set, get) => ({
  // Initial state
  backgroundMatters: new Map<string, BackgroundMatter>(),
  isProcessingInBackground: false,

  // Actions
  addBackgroundMatter: (matter: BackgroundMatter) => {
    const currentMatters = get().backgroundMatters;
    const newMatters = new Map(currentMatters);
    newMatters.set(matter.matterId, matter);

    set({
      backgroundMatters: newMatters,
      isProcessingInBackground: true,
    });
  },

  updateBackgroundMatter: (matterId: string, updates: Partial<BackgroundMatter>) => {
    const currentMatters = get().backgroundMatters;
    const existing = currentMatters.get(matterId);

    if (!existing) {
      console.warn(`Background matter ${matterId} not found for update`);
      return;
    }

    const newMatters = new Map(currentMatters);
    newMatters.set(matterId, {
      ...existing,
      ...updates,
    });

    set({ backgroundMatters: newMatters });
  },

  removeBackgroundMatter: (matterId: string) => {
    const currentMatters = get().backgroundMatters;
    const newMatters = new Map(currentMatters);
    newMatters.delete(matterId);

    set({
      backgroundMatters: newMatters,
      isProcessingInBackground: newMatters.size > 0,
    });
  },

  markComplete: (matterId: string) => {
    const currentMatters = get().backgroundMatters;
    const matter = currentMatters.get(matterId);

    if (!matter) {
      console.warn(`Background matter ${matterId} not found for completion`);
      return;
    }

    // Update status to ready
    const newMatters = new Map(currentMatters);
    newMatters.set(matterId, {
      ...matter,
      status: 'ready',
      progressPct: 100,
    });

    set({ backgroundMatters: newMatters });

    // Show browser notification if permission granted
    const permission = getNotificationPermission();
    if (permission === 'granted') {
      showProcessingCompleteNotification(matter.matterName, matter.matterId);
    } else {
      // Use fallback notification (toast, etc.)
      showNotificationFallback(matter.matterName);
    }

    // Add in-app notification
    const addNotification = useNotificationStore.getState().addNotification;
    addNotification({
      type: 'success',
      title: 'Processing Complete',
      message: `Matter "${matter.matterName}" is ready for analysis.`,
      matterId: matter.matterId,
      matterTitle: matter.matterName,
      priority: 'medium',
    });
  },

  clearAll: () => {
    set({
      backgroundMatters: new Map<string, BackgroundMatter>(),
      isProcessingInBackground: false,
    });
  },
}));

// =============================================================================
// Selectors
// =============================================================================

/**
 * Get list of matters currently processing in background
 */
export function selectProcessingMatters(state: BackgroundProcessingStore): BackgroundMatter[] {
  return Array.from(state.backgroundMatters.values()).filter(
    (m) => m.status === 'processing'
  );
}

/**
 * Get list of matters that have completed processing
 */
export function selectCompletedMatters(state: BackgroundProcessingStore): BackgroundMatter[] {
  return Array.from(state.backgroundMatters.values()).filter(
    (m) => m.status === 'ready'
  );
}

/**
 * Get count of background matters by status
 */
export function selectBackgroundMatterCount(state: BackgroundProcessingStore): {
  processing: number;
  ready: number;
  error: number;
  total: number;
} {
  const matters = Array.from(state.backgroundMatters.values());
  return {
    processing: matters.filter((m) => m.status === 'processing').length,
    ready: matters.filter((m) => m.status === 'ready').length,
    error: matters.filter((m) => m.status === 'error').length,
    total: matters.length,
  };
}

/**
 * Check if a specific matter is being processed in background
 */
export function selectIsMatterInBackground(
  state: BackgroundProcessingStore,
  matterId: string
): boolean {
  return state.backgroundMatters.has(matterId);
}
