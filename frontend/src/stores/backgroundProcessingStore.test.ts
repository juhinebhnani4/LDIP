import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from '@testing-library/react';
import {
  useBackgroundProcessingStore,
  selectProcessingMatters,
  selectCompletedMatters,
  selectBackgroundMatterCount,
  selectIsMatterInBackground,
  type BackgroundMatter,
} from './backgroundProcessingStore';
import { useNotificationStore } from './notificationStore';

// Mock browser notifications
vi.mock('@/lib/utils/browser-notifications', () => ({
  showProcessingCompleteNotification: vi.fn(),
  showNotificationFallback: vi.fn(),
  getNotificationPermission: vi.fn().mockReturnValue('granted'),
}));

describe('backgroundProcessingStore', () => {
  beforeEach(() => {
    // Reset stores before each test
    useBackgroundProcessingStore.getState().clearAll();
    useNotificationStore.getState().clearAll();
  });

  describe('initial state', () => {
    it('has empty backgroundMatters map', () => {
      const state = useBackgroundProcessingStore.getState();
      expect(state.backgroundMatters.size).toBe(0);
    });

    it('has isProcessingInBackground as false', () => {
      const state = useBackgroundProcessingStore.getState();
      expect(state.isProcessingInBackground).toBe(false);
    });
  });

  describe('addBackgroundMatter', () => {
    it('adds matter to backgroundMatters map', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
      });

      const state = useBackgroundProcessingStore.getState();
      expect(state.backgroundMatters.has('matter-1')).toBe(true);
      expect(state.backgroundMatters.get('matter-1')).toEqual(matter);
    });

    it('sets isProcessingInBackground to true', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
      });

      expect(useBackgroundProcessingStore.getState().isProcessingInBackground).toBe(true);
    });

    it('can add multiple matters', () => {
      const matter1: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter 1',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };
      const matter2: BackgroundMatter = {
        matterId: 'matter-2',
        matterName: 'Test Matter 2',
        progressPct: 30,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter1);
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter2);
      });

      const state = useBackgroundProcessingStore.getState();
      expect(state.backgroundMatters.size).toBe(2);
    });
  });

  describe('updateBackgroundMatter', () => {
    it('updates existing matter properties', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
        useBackgroundProcessingStore.getState().updateBackgroundMatter('matter-1', {
          progressPct: 75,
        });
      });

      const updated = useBackgroundProcessingStore.getState().backgroundMatters.get('matter-1');
      expect(updated?.progressPct).toBe(75);
      expect(updated?.matterName).toBe('Test Matter'); // Other props unchanged
    });

    it('warns when matter not found', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      act(() => {
        useBackgroundProcessingStore.getState().updateBackgroundMatter('nonexistent', {
          progressPct: 75,
        });
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Background matter nonexistent not found for update'
      );
      consoleSpy.mockRestore();
    });
  });

  describe('removeBackgroundMatter', () => {
    it('removes matter from map', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
        useBackgroundProcessingStore.getState().removeBackgroundMatter('matter-1');
      });

      expect(useBackgroundProcessingStore.getState().backgroundMatters.has('matter-1')).toBe(false);
    });

    it('sets isProcessingInBackground to false when last matter removed', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
      });

      expect(useBackgroundProcessingStore.getState().isProcessingInBackground).toBe(true);

      act(() => {
        useBackgroundProcessingStore.getState().removeBackgroundMatter('matter-1');
      });

      expect(useBackgroundProcessingStore.getState().isProcessingInBackground).toBe(false);
    });

    it('keeps isProcessingInBackground true if other matters remain', () => {
      const matter1: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter 1',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };
      const matter2: BackgroundMatter = {
        matterId: 'matter-2',
        matterName: 'Test Matter 2',
        progressPct: 30,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter1);
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter2);
        useBackgroundProcessingStore.getState().removeBackgroundMatter('matter-1');
      });

      expect(useBackgroundProcessingStore.getState().isProcessingInBackground).toBe(true);
    });
  });

  describe('markComplete', () => {
    it('updates status to ready and progress to 100', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 80,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
        useBackgroundProcessingStore.getState().markComplete('matter-1');
      });

      const updated = useBackgroundProcessingStore.getState().backgroundMatters.get('matter-1');
      expect(updated?.status).toBe('ready');
      expect(updated?.progressPct).toBe(100);
    });

    it('adds in-app notification on completion', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 80,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
        useBackgroundProcessingStore.getState().markComplete('matter-1');
      });

      const notifications = useNotificationStore.getState().notifications;
      expect(notifications.length).toBe(1);
      expect(notifications[0].title).toBe('Processing Complete');
      expect(notifications[0].type).toBe('success');
    });

    it('warns when matter not found', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      act(() => {
        useBackgroundProcessingStore.getState().markComplete('nonexistent');
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Background matter nonexistent not found for completion'
      );
      consoleSpy.mockRestore();
    });
  });

  describe('clearAll', () => {
    it('clears all background matters', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
        useBackgroundProcessingStore.getState().clearAll();
      });

      expect(useBackgroundProcessingStore.getState().backgroundMatters.size).toBe(0);
    });

    it('sets isProcessingInBackground to false', () => {
      const matter: BackgroundMatter = {
        matterId: 'matter-1',
        matterName: 'Test Matter',
        progressPct: 50,
        status: 'processing',
        startedAt: new Date(),
      };

      act(() => {
        useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
        useBackgroundProcessingStore.getState().clearAll();
      });

      expect(useBackgroundProcessingStore.getState().isProcessingInBackground).toBe(false);
    });
  });

  describe('selectors', () => {
    describe('selectProcessingMatters', () => {
      it('returns only processing matters', () => {
        const processing: BackgroundMatter = {
          matterId: 'matter-1',
          matterName: 'Processing Matter',
          progressPct: 50,
          status: 'processing',
          startedAt: new Date(),
        };
        const ready: BackgroundMatter = {
          matterId: 'matter-2',
          matterName: 'Ready Matter',
          progressPct: 100,
          status: 'ready',
          startedAt: new Date(),
        };

        act(() => {
          useBackgroundProcessingStore.getState().addBackgroundMatter(processing);
          useBackgroundProcessingStore.getState().addBackgroundMatter(ready);
        });

        const state = useBackgroundProcessingStore.getState();
        const result = selectProcessingMatters(state);

        expect(result.length).toBe(1);
        expect(result[0].status).toBe('processing');
      });
    });

    describe('selectCompletedMatters', () => {
      it('returns only ready matters', () => {
        const processing: BackgroundMatter = {
          matterId: 'matter-1',
          matterName: 'Processing Matter',
          progressPct: 50,
          status: 'processing',
          startedAt: new Date(),
        };
        const ready: BackgroundMatter = {
          matterId: 'matter-2',
          matterName: 'Ready Matter',
          progressPct: 100,
          status: 'ready',
          startedAt: new Date(),
        };

        act(() => {
          useBackgroundProcessingStore.getState().addBackgroundMatter(processing);
          useBackgroundProcessingStore.getState().addBackgroundMatter(ready);
        });

        const state = useBackgroundProcessingStore.getState();
        const result = selectCompletedMatters(state);

        expect(result.length).toBe(1);
        expect(result[0].status).toBe('ready');
      });
    });

    describe('selectBackgroundMatterCount', () => {
      it('returns correct counts by status', () => {
        const matters: BackgroundMatter[] = [
          { matterId: '1', matterName: 'M1', progressPct: 50, status: 'processing', startedAt: new Date() },
          { matterId: '2', matterName: 'M2', progressPct: 30, status: 'processing', startedAt: new Date() },
          { matterId: '3', matterName: 'M3', progressPct: 100, status: 'ready', startedAt: new Date() },
          { matterId: '4', matterName: 'M4', progressPct: 0, status: 'error', startedAt: new Date() },
        ];

        act(() => {
          matters.forEach((m) => useBackgroundProcessingStore.getState().addBackgroundMatter(m));
        });

        const state = useBackgroundProcessingStore.getState();
        const result = selectBackgroundMatterCount(state);

        expect(result.processing).toBe(2);
        expect(result.ready).toBe(1);
        expect(result.error).toBe(1);
        expect(result.total).toBe(4);
      });
    });

    describe('selectIsMatterInBackground', () => {
      it('returns true for matter in background', () => {
        const matter: BackgroundMatter = {
          matterId: 'matter-1',
          matterName: 'Test Matter',
          progressPct: 50,
          status: 'processing',
          startedAt: new Date(),
        };

        act(() => {
          useBackgroundProcessingStore.getState().addBackgroundMatter(matter);
        });

        const state = useBackgroundProcessingStore.getState();
        expect(selectIsMatterInBackground(state, 'matter-1')).toBe(true);
      });

      it('returns false for matter not in background', () => {
        const state = useBackgroundProcessingStore.getState();
        expect(selectIsMatterInBackground(state, 'nonexistent')).toBe(false);
      });
    });
  });
});
