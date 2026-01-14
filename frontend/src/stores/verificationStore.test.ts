/**
 * Verification Store Tests
 *
 * Story 8-5: Implement Verification Queue UI (Task 10)
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  useVerificationStore,
  getConfidenceTier,
  getConfidenceColorClass,
  getConfidenceLabel,
  formatFindingType,
  getFindingTypeIcon,
} from './verificationStore';
import { VerificationDecision, VerificationRequirement } from '@/types';
import type { VerificationQueueItem, VerificationStats } from '@/types';

describe('verificationStore', () => {
  // Reset store before each test
  beforeEach(() => {
    const { result } = renderHook(() => useVerificationStore());
    act(() => {
      result.current.reset();
    });
  });

  describe('initial state', () => {
    it('should have empty queue initially', () => {
      const { result } = renderHook(() => useVerificationStore());
      expect(result.current.queue).toEqual([]);
    });

    it('should have null stats initially', () => {
      const { result } = renderHook(() => useVerificationStore());
      expect(result.current.stats).toBeNull();
    });

    it('should have empty selection initially', () => {
      const { result } = renderHook(() => useVerificationStore());
      expect(result.current.selectedIds).toEqual([]);
    });

    it('should have default filters', () => {
      const { result } = renderHook(() => useVerificationStore());
      expect(result.current.filters).toEqual({
        findingType: null,
        confidenceTier: null,
        status: null,
        view: 'queue',
      });
    });
  });

  describe('setMatterId', () => {
    it('should set matter ID', () => {
      const { result } = renderHook(() => useVerificationStore());

      act(() => {
        result.current.setMatterId('matter-123');
      });

      expect(result.current.matterId).toBe('matter-123');
    });

    it('should reset state when matter ID changes', () => {
      const { result } = renderHook(() => useVerificationStore());

      // Set initial state
      act(() => {
        result.current.setMatterId('matter-123');
        result.current.setQueue([mockQueueItem('1')]);
        result.current.selectAll(['1']);
      });

      expect(result.current.queue.length).toBe(1);
      expect(result.current.selectedIds.length).toBe(1);

      // Change matter ID - should reset
      act(() => {
        result.current.setMatterId('matter-456');
      });

      expect(result.current.queue).toEqual([]);
      expect(result.current.selectedIds).toEqual([]);
    });
  });

  describe('setQueue', () => {
    it('should set queue items', () => {
      const { result } = renderHook(() => useVerificationStore());
      const items = [mockQueueItem('1'), mockQueueItem('2')];

      act(() => {
        result.current.setQueue(items);
      });

      expect(result.current.queue).toEqual(items);
    });

    it('should clear error when queue is set', () => {
      const { result } = renderHook(() => useVerificationStore());

      act(() => {
        result.current.setError('Some error');
        result.current.setQueue([]);
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('selection', () => {
    it('should toggle selection', () => {
      const { result } = renderHook(() => useVerificationStore());
      const items = [mockQueueItem('1'), mockQueueItem('2')];

      act(() => {
        result.current.setQueue(items);
      });

      // Select first item
      act(() => {
        result.current.toggleSelected('1');
      });
      expect(result.current.selectedIds).toEqual(['1']);

      // Select second item
      act(() => {
        result.current.toggleSelected('2');
      });
      expect(result.current.selectedIds).toEqual(['1', '2']);

      // Deselect first item
      act(() => {
        result.current.toggleSelected('1');
      });
      expect(result.current.selectedIds).toEqual(['2']);
    });

    it('should select all items', () => {
      const { result } = renderHook(() => useVerificationStore());

      act(() => {
        result.current.selectAll(['1', '2', '3']);
      });

      expect(result.current.selectedIds).toEqual(['1', '2', '3']);
    });

    it('should clear selection', () => {
      const { result } = renderHook(() => useVerificationStore());

      act(() => {
        result.current.selectAll(['1', '2']);
        result.current.clearSelection();
      });

      expect(result.current.selectedIds).toEqual([]);
    });
  });

  describe('removeFromQueue', () => {
    it('should remove item from queue', () => {
      const { result } = renderHook(() => useVerificationStore());
      const items = [mockQueueItem('1'), mockQueueItem('2')];

      act(() => {
        result.current.setQueue(items);
        result.current.removeFromQueue('1');
      });

      expect(result.current.queue.length).toBe(1);
      expect(result.current.queue[0]?.id).toBe('2');
    });

    it('should remove item from selection when removed from queue', () => {
      const { result } = renderHook(() => useVerificationStore());
      const items = [mockQueueItem('1'), mockQueueItem('2')];

      act(() => {
        result.current.setQueue(items);
        result.current.selectAll(['1', '2']);
        result.current.removeFromQueue('1');
      });

      expect(result.current.selectedIds).toEqual(['2']);
    });
  });

  describe('removeMultipleFromQueue', () => {
    it('should remove multiple items from queue', () => {
      const { result } = renderHook(() => useVerificationStore());
      const items = [mockQueueItem('1'), mockQueueItem('2'), mockQueueItem('3')];

      act(() => {
        result.current.setQueue(items);
        result.current.removeMultipleFromQueue(['1', '3']);
      });

      expect(result.current.queue.length).toBe(1);
      expect(result.current.queue[0]?.id).toBe('2');
    });
  });

  describe('filters', () => {
    it('should update filters', () => {
      const { result } = renderHook(() => useVerificationStore());

      act(() => {
        result.current.setFilters({ findingType: 'citation_mismatch' });
      });

      expect(result.current.filters.findingType).toBe('citation_mismatch');
      expect(result.current.filters.confidenceTier).toBeNull(); // Unchanged
    });

    it('should clear selection when filters change', () => {
      const { result } = renderHook(() => useVerificationStore());

      act(() => {
        result.current.selectAll(['1', '2']);
        result.current.setFilters({ findingType: 'test' });
      });

      expect(result.current.selectedIds).toEqual([]);
    });

    it('should reset filters', () => {
      const { result } = renderHook(() => useVerificationStore());

      act(() => {
        result.current.setFilters({
          findingType: 'test',
          confidenceTier: 'low',
        });
        result.current.resetFilters();
      });

      expect(result.current.filters).toEqual({
        findingType: null,
        confidenceTier: null,
        status: null,
        view: 'queue',
      });
    });
  });

  describe('updateQueueItem', () => {
    it('should update a single queue item', () => {
      const { result } = renderHook(() => useVerificationStore());
      const items = [mockQueueItem('1')];

      act(() => {
        result.current.setQueue(items);
        result.current.updateQueueItem('1', {
          decision: VerificationDecision.FLAGGED,
        });
      });

      expect(result.current.queue[0]?.decision).toBe(VerificationDecision.FLAGGED);
    });
  });
});

describe('helper functions', () => {
  describe('getConfidenceTier', () => {
    it('should return high for > 90', () => {
      expect(getConfidenceTier(91)).toBe('high');
      expect(getConfidenceTier(100)).toBe('high');
    });

    it('should return medium for 70-90', () => {
      expect(getConfidenceTier(70.1)).toBe('medium');
      expect(getConfidenceTier(90)).toBe('medium');
    });

    it('should return low for <= 70', () => {
      expect(getConfidenceTier(70)).toBe('low');
      expect(getConfidenceTier(50)).toBe('low');
      expect(getConfidenceTier(0)).toBe('low');
    });
  });

  describe('getConfidenceColorClass', () => {
    it('should return green for high confidence', () => {
      expect(getConfidenceColorClass(91)).toBe('bg-green-500');
    });

    it('should return yellow for medium confidence', () => {
      expect(getConfidenceColorClass(80)).toBe('bg-yellow-500');
    });

    it('should return red for low confidence', () => {
      expect(getConfidenceColorClass(60)).toBe('bg-red-500');
    });
  });

  describe('getConfidenceLabel', () => {
    it('should return correct labels', () => {
      expect(getConfidenceLabel('high')).toBe('High (>90%)');
      expect(getConfidenceLabel('medium')).toBe('Medium (70-90%)');
      expect(getConfidenceLabel('low')).toBe('Low (<70%)');
    });
  });

  describe('formatFindingType', () => {
    it('should format finding types correctly', () => {
      expect(formatFindingType('citation_mismatch')).toBe('Citation Mismatch');
      expect(formatFindingType('timeline_anomaly')).toBe('Timeline Anomaly');
      expect(formatFindingType('contradiction')).toBe('Contradiction');
    });
  });

  describe('getFindingTypeIcon', () => {
    it('should return correct icons', () => {
      expect(getFindingTypeIcon('contradiction')).toBe('⚡');
      expect(getFindingTypeIcon('citation_mismatch')).toBe('⚖️');
      expect(getFindingTypeIcon('timeline_anomaly')).toBe('📅');
      expect(getFindingTypeIcon('unknown_type')).toBe('📄');
    });
  });
});

// Helper function to create mock queue items
function mockQueueItem(
  id: string,
  overrides: Partial<VerificationQueueItem> = {}
): VerificationQueueItem {
  return {
    id,
    findingId: `finding-${id}`,
    findingType: 'citation_mismatch',
    findingSummary: `Test finding summary ${id}`,
    confidence: 75,
    requirement: VerificationRequirement.SUGGESTED,
    decision: VerificationDecision.PENDING,
    createdAt: new Date().toISOString(),
    sourceDocument: 'test-doc.pdf',
    engine: 'citation',
    ...overrides,
  };
}
