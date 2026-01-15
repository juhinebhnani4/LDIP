/**
 * Q&A Panel Store
 *
 * Zustand store for Q&A panel position and sizing state.
 *
 * USAGE PATTERN (MANDATORY - from project-context.md):
 * CORRECT - Selector pattern:
 *   const position = useQAPanelStore((state) => state.position);
 *   const setPosition = useQAPanelStore((state) => state.setPosition);
 *
 * WRONG - Full store subscription (causes re-renders):
 *   const { position, setPosition, rightWidth } = useQAPanelStore();
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ============================================================================
// Constants
// ============================================================================

export const QA_PANEL_POSITIONS = ['right', 'bottom', 'float', 'hidden'] as const;
export type QAPanelPosition = (typeof QA_PANEL_POSITIONS)[number];

export const DEFAULT_PANEL_POSITION: QAPanelPosition = 'right';
export const DEFAULT_RIGHT_WIDTH = 35; // percentage
export const DEFAULT_BOTTOM_HEIGHT = 40; // percentage
export const MIN_PANEL_SIZE = 20; // percentage
export const MAX_PANEL_SIZE = 60; // percentage

export const DEFAULT_FLOAT_WIDTH = 400; // pixels
export const DEFAULT_FLOAT_HEIGHT = 500; // pixels
export const MIN_FLOAT_WIDTH = 300; // pixels
export const MIN_FLOAT_HEIGHT = 200; // pixels
export const DEFAULT_FLOAT_X = 100; // pixels from left
export const DEFAULT_FLOAT_Y = 100; // pixels from top

export const STORAGE_KEY = 'ldip-qa-panel-preferences';

// ============================================================================
// Types
// ============================================================================

interface QAPanelState {
  /** Current panel position */
  position: QAPanelPosition;

  /** Width for right sidebar position (percentage 20-60) */
  rightWidth: number;

  /** Height for bottom panel position (percentage 20-60) */
  bottomHeight: number;

  /** X position for floating panel (pixels from left) */
  floatX: number;

  /** Y position for floating panel (pixels from top) */
  floatY: number;

  /** Width for floating panel (pixels) */
  floatWidth: number;

  /** Height for floating panel (pixels) */
  floatHeight: number;

  /** Previous position before hiding (for restore) */
  previousPosition: QAPanelPosition;

  /** Mock unread count for MVP */
  unreadCount: number;
}

interface QAPanelActions {
  /** Set panel position */
  setPosition: (position: QAPanelPosition) => void;

  /** Set right sidebar width (percentage) */
  setRightWidth: (width: number) => void;

  /** Set bottom panel height (percentage) */
  setBottomHeight: (height: number) => void;

  /** Set floating panel position (pixels) */
  setFloatPosition: (x: number, y: number) => void;

  /** Set floating panel size (pixels) */
  setFloatSize: (width: number, height: number) => void;

  /** Restore from hidden to previous position */
  restoreFromHidden: () => void;

  /** Set unread count (mock for MVP) */
  setUnreadCount: (count: number) => void;

  /** Reset to default state */
  reset: () => void;
}

type QAPanelStore = QAPanelState & QAPanelActions;

// ============================================================================
// Initial State
// ============================================================================

const initialState: QAPanelState = {
  position: DEFAULT_PANEL_POSITION,
  rightWidth: DEFAULT_RIGHT_WIDTH,
  bottomHeight: DEFAULT_BOTTOM_HEIGHT,
  floatX: DEFAULT_FLOAT_X,
  floatY: DEFAULT_FLOAT_Y,
  floatWidth: DEFAULT_FLOAT_WIDTH,
  floatHeight: DEFAULT_FLOAT_HEIGHT,
  previousPosition: DEFAULT_PANEL_POSITION,
  unreadCount: 0,
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Clamp a value to a min/max range
 */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Validate panel position
 */
function isValidPosition(position: unknown): position is QAPanelPosition {
  return (
    typeof position === 'string' &&
    QA_PANEL_POSITIONS.includes(position as QAPanelPosition)
  );
}

// ============================================================================
// Store
// ============================================================================

export const useQAPanelStore = create<QAPanelStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      setPosition: (position) => {
        if (!isValidPosition(position)) {
          console.warn(`Invalid Q&A panel position: ${position}, defaulting to 'right'`);
          position = 'right';
        }

        const currentPosition = get().position;

        // Store previous position when hiding (unless already hidden)
        if (position === 'hidden' && currentPosition !== 'hidden') {
          set({ position, previousPosition: currentPosition });
        } else {
          set({ position });
        }
      },

      setRightWidth: (width) => {
        const clampedWidth = clamp(width, MIN_PANEL_SIZE, MAX_PANEL_SIZE);
        set({ rightWidth: clampedWidth });
      },

      setBottomHeight: (height) => {
        const clampedHeight = clamp(height, MIN_PANEL_SIZE, MAX_PANEL_SIZE);
        set({ bottomHeight: clampedHeight });
      },

      setFloatPosition: (x, y) => {
        // Ensure position is within reasonable bounds
        const clampedX = Math.max(0, x);
        const clampedY = Math.max(0, y);
        set({ floatX: clampedX, floatY: clampedY });
      },

      setFloatSize: (width, height) => {
        // Clamp to minimum size, no maximum (viewport will constrain)
        const clampedWidth = Math.max(MIN_FLOAT_WIDTH, width);
        const clampedHeight = Math.max(MIN_FLOAT_HEIGHT, height);
        set({ floatWidth: clampedWidth, floatHeight: clampedHeight });
      },

      restoreFromHidden: () => {
        const { previousPosition } = get();
        // If previous was also hidden (edge case), default to right
        const targetPosition = previousPosition === 'hidden' ? 'right' : previousPosition;
        set({ position: targetPosition });
      },

      setUnreadCount: (count) => {
        set({ unreadCount: Math.max(0, count) });
      },

      reset: () => {
        set(initialState);
      },
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        // Only persist position and sizing preferences
        position: state.position,
        rightWidth: state.rightWidth,
        bottomHeight: state.bottomHeight,
        floatX: state.floatX,
        floatY: state.floatY,
        floatWidth: state.floatWidth,
        floatHeight: state.floatHeight,
        previousPosition: state.previousPosition,
        // Don't persist unreadCount
      }),
    }
  )
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for checking if panel is visible
 */
export const selectIsPanelVisible = (state: QAPanelStore): boolean => {
  return state.position !== 'hidden';
};

/**
 * Selector for getting current panel dimensions
 * Returns the appropriate width/height based on position
 */
export const selectCurrentDimensions = (
  state: QAPanelStore
): { width: number; height: number; unit: 'percent' | 'pixels' } => {
  switch (state.position) {
    case 'right':
      return { width: state.rightWidth, height: 100, unit: 'percent' };
    case 'bottom':
      return { width: 100, height: state.bottomHeight, unit: 'percent' };
    case 'float':
      return { width: state.floatWidth, height: state.floatHeight, unit: 'pixels' };
    case 'hidden':
      return { width: 0, height: 0, unit: 'percent' };
  }
};
