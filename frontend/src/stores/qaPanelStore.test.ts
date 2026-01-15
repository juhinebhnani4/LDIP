import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { act } from '@testing-library/react';
import {
  useQAPanelStore,
  selectIsPanelVisible,
  selectCurrentDimensions,
  DEFAULT_PANEL_POSITION,
  DEFAULT_RIGHT_WIDTH,
  DEFAULT_BOTTOM_HEIGHT,
  DEFAULT_FLOAT_WIDTH,
  DEFAULT_FLOAT_HEIGHT,
  DEFAULT_FLOAT_X,
  DEFAULT_FLOAT_Y,
  MIN_PANEL_SIZE,
  MAX_PANEL_SIZE,
  MIN_FLOAT_WIDTH,
  MIN_FLOAT_HEIGHT,
} from './qaPanelStore';

describe('qaPanelStore', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Reset store state
    act(() => {
      useQAPanelStore.getState().reset();
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial State', () => {
    it('initializes with right position as default', () => {
      const state = useQAPanelStore.getState();
      expect(state.position).toBe(DEFAULT_PANEL_POSITION);
      expect(state.position).toBe('right');
    });

    it('initializes with default right width', () => {
      const state = useQAPanelStore.getState();
      expect(state.rightWidth).toBe(DEFAULT_RIGHT_WIDTH);
    });

    it('initializes with default bottom height', () => {
      const state = useQAPanelStore.getState();
      expect(state.bottomHeight).toBe(DEFAULT_BOTTOM_HEIGHT);
    });

    it('initializes with default float position', () => {
      const state = useQAPanelStore.getState();
      expect(state.floatX).toBe(DEFAULT_FLOAT_X);
      expect(state.floatY).toBe(DEFAULT_FLOAT_Y);
    });

    it('initializes with default float size', () => {
      const state = useQAPanelStore.getState();
      expect(state.floatWidth).toBe(DEFAULT_FLOAT_WIDTH);
      expect(state.floatHeight).toBe(DEFAULT_FLOAT_HEIGHT);
    });

    it('initializes with zero unread count', () => {
      const state = useQAPanelStore.getState();
      expect(state.unreadCount).toBe(0);
    });

    it('initializes previousPosition to default', () => {
      const state = useQAPanelStore.getState();
      expect(state.previousPosition).toBe(DEFAULT_PANEL_POSITION);
    });
  });

  describe('setPosition', () => {
    it('updates position to right', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
        useQAPanelStore.getState().setPosition('right');
      });

      expect(useQAPanelStore.getState().position).toBe('right');
    });

    it('updates position to bottom', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
      });

      expect(useQAPanelStore.getState().position).toBe('bottom');
    });

    it('updates position to float', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('float');
      });

      expect(useQAPanelStore.getState().position).toBe('float');
    });

    it('updates position to hidden', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('hidden');
      });

      expect(useQAPanelStore.getState().position).toBe('hidden');
    });

    it('stores previousPosition when hiding', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
        useQAPanelStore.getState().setPosition('hidden');
      });

      const state = useQAPanelStore.getState();
      expect(state.position).toBe('hidden');
      expect(state.previousPosition).toBe('bottom');
    });

    it('does not update previousPosition when switching between non-hidden positions', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
        useQAPanelStore.getState().setPosition('float');
      });

      const state = useQAPanelStore.getState();
      expect(state.previousPosition).toBe('right'); // Still default
    });

    it('defaults to right for invalid position', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      act(() => {
        // @ts-expect-error Testing invalid input
        useQAPanelStore.getState().setPosition('invalid');
      });

      expect(useQAPanelStore.getState().position).toBe('right');
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });

  describe('setRightWidth', () => {
    it('updates right width', () => {
      act(() => {
        useQAPanelStore.getState().setRightWidth(45);
      });

      expect(useQAPanelStore.getState().rightWidth).toBe(45);
    });

    it('clamps width to minimum', () => {
      act(() => {
        useQAPanelStore.getState().setRightWidth(10); // Below MIN_PANEL_SIZE
      });

      expect(useQAPanelStore.getState().rightWidth).toBe(MIN_PANEL_SIZE);
    });

    it('clamps width to maximum', () => {
      act(() => {
        useQAPanelStore.getState().setRightWidth(80); // Above MAX_PANEL_SIZE
      });

      expect(useQAPanelStore.getState().rightWidth).toBe(MAX_PANEL_SIZE);
    });

    it('accepts width at boundary values', () => {
      act(() => {
        useQAPanelStore.getState().setRightWidth(MIN_PANEL_SIZE);
      });
      expect(useQAPanelStore.getState().rightWidth).toBe(MIN_PANEL_SIZE);

      act(() => {
        useQAPanelStore.getState().setRightWidth(MAX_PANEL_SIZE);
      });
      expect(useQAPanelStore.getState().rightWidth).toBe(MAX_PANEL_SIZE);
    });
  });

  describe('setBottomHeight', () => {
    it('updates bottom height', () => {
      act(() => {
        useQAPanelStore.getState().setBottomHeight(50);
      });

      expect(useQAPanelStore.getState().bottomHeight).toBe(50);
    });

    it('clamps height to minimum', () => {
      act(() => {
        useQAPanelStore.getState().setBottomHeight(5);
      });

      expect(useQAPanelStore.getState().bottomHeight).toBe(MIN_PANEL_SIZE);
    });

    it('clamps height to maximum', () => {
      act(() => {
        useQAPanelStore.getState().setBottomHeight(90);
      });

      expect(useQAPanelStore.getState().bottomHeight).toBe(MAX_PANEL_SIZE);
    });
  });

  describe('setFloatPosition', () => {
    it('updates float x and y position', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(200, 150);
      });

      const state = useQAPanelStore.getState();
      expect(state.floatX).toBe(200);
      expect(state.floatY).toBe(150);
    });

    it('clamps position to non-negative values', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(-100, -50);
      });

      const state = useQAPanelStore.getState();
      expect(state.floatX).toBe(0);
      expect(state.floatY).toBe(0);
    });

    it('allows zero position', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(0, 0);
      });

      const state = useQAPanelStore.getState();
      expect(state.floatX).toBe(0);
      expect(state.floatY).toBe(0);
    });
  });

  describe('setFloatSize', () => {
    it('updates float width and height', () => {
      act(() => {
        useQAPanelStore.getState().setFloatSize(500, 600);
      });

      const state = useQAPanelStore.getState();
      expect(state.floatWidth).toBe(500);
      expect(state.floatHeight).toBe(600);
    });

    it('clamps size to minimum width', () => {
      act(() => {
        useQAPanelStore.getState().setFloatSize(100, 600);
      });

      expect(useQAPanelStore.getState().floatWidth).toBe(MIN_FLOAT_WIDTH);
    });

    it('clamps size to minimum height', () => {
      act(() => {
        useQAPanelStore.getState().setFloatSize(500, 50);
      });

      expect(useQAPanelStore.getState().floatHeight).toBe(MIN_FLOAT_HEIGHT);
    });

    it('accepts exact minimum size', () => {
      act(() => {
        useQAPanelStore.getState().setFloatSize(MIN_FLOAT_WIDTH, MIN_FLOAT_HEIGHT);
      });

      const state = useQAPanelStore.getState();
      expect(state.floatWidth).toBe(MIN_FLOAT_WIDTH);
      expect(state.floatHeight).toBe(MIN_FLOAT_HEIGHT);
    });
  });

  describe('restoreFromHidden', () => {
    it('restores to previous position from hidden', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
        useQAPanelStore.getState().setPosition('hidden');
        useQAPanelStore.getState().restoreFromHidden();
      });

      expect(useQAPanelStore.getState().position).toBe('bottom');
    });

    it('restores to float if that was previous position', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('float');
        useQAPanelStore.getState().setPosition('hidden');
        useQAPanelStore.getState().restoreFromHidden();
      });

      expect(useQAPanelStore.getState().position).toBe('float');
    });

    it('defaults to right if previousPosition was somehow hidden', () => {
      // Manually set previousPosition to hidden (edge case)
      act(() => {
        useQAPanelStore.setState({ position: 'hidden', previousPosition: 'hidden' });
        useQAPanelStore.getState().restoreFromHidden();
      });

      expect(useQAPanelStore.getState().position).toBe('right');
    });
  });

  describe('setUnreadCount', () => {
    it('sets unread count', () => {
      act(() => {
        useQAPanelStore.getState().setUnreadCount(5);
      });

      expect(useQAPanelStore.getState().unreadCount).toBe(5);
    });

    it('clamps negative counts to zero', () => {
      act(() => {
        useQAPanelStore.getState().setUnreadCount(-3);
      });

      expect(useQAPanelStore.getState().unreadCount).toBe(0);
    });

    it('accepts zero unread count', () => {
      act(() => {
        useQAPanelStore.getState().setUnreadCount(5);
        useQAPanelStore.getState().setUnreadCount(0);
      });

      expect(useQAPanelStore.getState().unreadCount).toBe(0);
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', () => {
      // Set various state values
      act(() => {
        useQAPanelStore.getState().setPosition('float');
        useQAPanelStore.getState().setRightWidth(50);
        useQAPanelStore.getState().setBottomHeight(45);
        useQAPanelStore.getState().setFloatPosition(300, 200);
        useQAPanelStore.getState().setFloatSize(600, 700);
        useQAPanelStore.getState().setUnreadCount(10);
      });

      // Reset
      act(() => {
        useQAPanelStore.getState().reset();
      });

      const state = useQAPanelStore.getState();
      expect(state.position).toBe(DEFAULT_PANEL_POSITION);
      expect(state.rightWidth).toBe(DEFAULT_RIGHT_WIDTH);
      expect(state.bottomHeight).toBe(DEFAULT_BOTTOM_HEIGHT);
      expect(state.floatX).toBe(DEFAULT_FLOAT_X);
      expect(state.floatY).toBe(DEFAULT_FLOAT_Y);
      expect(state.floatWidth).toBe(DEFAULT_FLOAT_WIDTH);
      expect(state.floatHeight).toBe(DEFAULT_FLOAT_HEIGHT);
      expect(state.unreadCount).toBe(0);
    });
  });

  describe('Persistence', () => {
    it('persists state to localStorage', async () => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
        useQAPanelStore.getState().setRightWidth(50);
      });

      // Wait for persistence middleware
      await new Promise((resolve) => setTimeout(resolve, 100));

      const stored = localStorage.getItem('ldip-qa-panel-preferences');
      expect(stored).not.toBeNull();

      const parsed = JSON.parse(stored!);
      expect(parsed.state.position).toBe('bottom');
      expect(parsed.state.rightWidth).toBe(50);
    });

    it('does not persist unreadCount', async () => {
      act(() => {
        useQAPanelStore.getState().setUnreadCount(15);
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      const stored = localStorage.getItem('ldip-qa-panel-preferences');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.unreadCount).toBeUndefined();
      }
    });

    it('loads state from localStorage on initialization', async () => {
      // Pre-populate localStorage with saved state
      const savedState = {
        state: {
          position: 'float',
          previousPosition: 'bottom',
          rightWidth: 45,
          bottomHeight: 40,
          floatX: 200,
          floatY: 150,
          floatWidth: 500,
          floatHeight: 600,
        },
        version: 0,
      };
      localStorage.setItem('ldip-qa-panel-preferences', JSON.stringify(savedState));

      // Trigger store rehydration by calling persist.rehydrate
      await act(async () => {
        await useQAPanelStore.persist.rehydrate();
      });

      const state = useQAPanelStore.getState();
      expect(state.position).toBe('float');
      expect(state.rightWidth).toBe(45);
      expect(state.floatX).toBe(200);
      expect(state.floatY).toBe(150);
      expect(state.floatWidth).toBe(500);
      expect(state.floatHeight).toBe(600);
    });
  });

  describe('Selectors', () => {
    describe('selectIsPanelVisible', () => {
      it('returns true for right position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('right');
        });

        const state = useQAPanelStore.getState();
        expect(selectIsPanelVisible(state)).toBe(true);
      });

      it('returns true for bottom position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('bottom');
        });

        const state = useQAPanelStore.getState();
        expect(selectIsPanelVisible(state)).toBe(true);
      });

      it('returns true for float position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('float');
        });

        const state = useQAPanelStore.getState();
        expect(selectIsPanelVisible(state)).toBe(true);
      });

      it('returns false for hidden position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('hidden');
        });

        const state = useQAPanelStore.getState();
        expect(selectIsPanelVisible(state)).toBe(false);
      });
    });

    describe('selectCurrentDimensions', () => {
      it('returns right width dimensions for right position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('right');
          useQAPanelStore.getState().setRightWidth(40);
        });

        const state = useQAPanelStore.getState();
        const dimensions = selectCurrentDimensions(state);

        expect(dimensions.width).toBe(40);
        expect(dimensions.height).toBe(100);
        expect(dimensions.unit).toBe('percent');
      });

      it('returns bottom height dimensions for bottom position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('bottom');
          useQAPanelStore.getState().setBottomHeight(35);
        });

        const state = useQAPanelStore.getState();
        const dimensions = selectCurrentDimensions(state);

        expect(dimensions.width).toBe(100);
        expect(dimensions.height).toBe(35);
        expect(dimensions.unit).toBe('percent');
      });

      it('returns float dimensions for float position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('float');
          useQAPanelStore.getState().setFloatSize(450, 550);
        });

        const state = useQAPanelStore.getState();
        const dimensions = selectCurrentDimensions(state);

        expect(dimensions.width).toBe(450);
        expect(dimensions.height).toBe(550);
        expect(dimensions.unit).toBe('pixels');
      });

      it('returns zero dimensions for hidden position', () => {
        act(() => {
          useQAPanelStore.getState().setPosition('hidden');
        });

        const state = useQAPanelStore.getState();
        const dimensions = selectCurrentDimensions(state);

        expect(dimensions.width).toBe(0);
        expect(dimensions.height).toBe(0);
        expect(dimensions.unit).toBe('percent');
      });
    });
  });
});
