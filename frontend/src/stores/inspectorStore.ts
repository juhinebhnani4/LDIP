/**
 * Inspector Store
 *
 * Zustand store for RAG pipeline inspector/debug state.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const debugEnabled = useInspectorStore((state) => state.debugEnabled);
 *   const toggleDebug = useInspectorStore((state) => state.toggleDebug);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { debugEnabled, toggleDebug } = useInspectorStore();
 *
 * Story: RAG Production Gaps - Feature 3: Inspector Mode
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SearchDebugInfo } from '@/types/inspector';

// ============================================================================
// Constants
// ============================================================================

export const STORAGE_KEY = 'ldip-inspector-preferences';

// ============================================================================
// Types
// ============================================================================

interface InspectorState {
  /** Whether inspector/debug mode is enabled on the server */
  inspectorEnabled: boolean;

  /** Whether debug info should be shown in chat UI */
  debugEnabled: boolean;

  /** Last search debug info (for inline display) */
  lastDebugInfo: SearchDebugInfo | null;

  /** Whether auto-evaluation is enabled */
  autoEvaluationEnabled: boolean;

  /** Whether table extraction is enabled */
  tableExtractionEnabled: boolean;
}

interface InspectorActions {
  /** Set server-side inspector status */
  setInspectorStatus: (status: {
    inspectorEnabled: boolean;
    autoEvaluationEnabled: boolean;
    tableExtractionEnabled: boolean;
  }) => void;

  /** Toggle debug display in chat UI */
  toggleDebug: () => void;

  /** Set debug display state */
  setDebugEnabled: (enabled: boolean) => void;

  /** Store last search debug info */
  setLastDebugInfo: (info: SearchDebugInfo | null) => void;

  /** Reset to default state */
  reset: () => void;
}

type InspectorStore = InspectorState & InspectorActions;

// ============================================================================
// Initial State
// ============================================================================

const initialState: InspectorState = {
  inspectorEnabled: false, // Will be set from server
  debugEnabled: false,
  lastDebugInfo: null,
  autoEvaluationEnabled: false,
  tableExtractionEnabled: false,
};

// ============================================================================
// Store
// ============================================================================

export const useInspectorStore = create<InspectorStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      setInspectorStatus: (status) => {
        set({
          inspectorEnabled: status.inspectorEnabled,
          autoEvaluationEnabled: status.autoEvaluationEnabled,
          tableExtractionEnabled: status.tableExtractionEnabled,
        });
      },

      toggleDebug: () => {
        const { inspectorEnabled, debugEnabled } = get();
        // Only toggle if inspector is enabled on server
        if (inspectorEnabled) {
          set({ debugEnabled: !debugEnabled });
        }
      },

      setDebugEnabled: (enabled) => {
        const { inspectorEnabled } = get();
        // Only enable if inspector is enabled on server
        if (enabled && !inspectorEnabled) {
          return;
        }
        set({ debugEnabled: enabled });
      },

      setLastDebugInfo: (info) => {
        set({ lastDebugInfo: info });
      },

      reset: () => {
        set(initialState);
      },
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        // Only persist debug preference
        debugEnabled: state.debugEnabled,
        // Don't persist server-side status or debug info
      }),
    }
  )
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for checking if debug mode is active
 * (inspector enabled on server AND user has enabled debug)
 */
export const selectIsDebugActive = (state: InspectorStore): boolean => {
  return state.inspectorEnabled && state.debugEnabled;
};
