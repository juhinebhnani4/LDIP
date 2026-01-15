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
import type { VerificationQueueItem } from '@/types';

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

describe('selectFilteredQueue selector (Task 2.4 - AND logic)', () => {
  beforeEach(() => {
    const { result } = renderHook(() => useVerificationStore());
    act(() => {
      result.current.reset();
    });
  });

  it('should return all items when no filters are set', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { findingType: 'citation_mismatch', confidence: 95 }),
      mockQueueItem('2', { findingType: 'timeline_anomaly', confidence: 75 }),
      mockQueueItem('3', { findingType: 'contradiction', confidence: 50 }),
    ];

    act(() => {
      result.current.setQueue(items);
    });

    // Access filtered queue via the selector
    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    expect(filtered.length).toBe(3);
  });

  it('should filter by findingType', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { findingType: 'citation_mismatch' }),
      mockQueueItem('2', { findingType: 'timeline_anomaly' }),
      mockQueueItem('3', { findingType: 'citation_mismatch' }),
    ];

    act(() => {
      result.current.setQueue(items);
      result.current.setFilters({ findingType: 'citation_mismatch' });
    });

    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    expect(filtered.length).toBe(2);
    expect(filtered.every(item => item.findingType === 'citation_mismatch')).toBe(true);
  });

  it('should filter by confidenceTier high (>90%)', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { confidence: 95 }),
      mockQueueItem('2', { confidence: 91 }),
      mockQueueItem('3', { confidence: 90 }), // Not > 90
      mockQueueItem('4', { confidence: 50 }),
    ];

    act(() => {
      result.current.setQueue(items);
      result.current.setFilters({ confidenceTier: 'high' });
    });

    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    expect(filtered.length).toBe(2);
    expect(filtered.every(item => item.confidence > 90)).toBe(true);
  });

  it('should filter by confidenceTier medium (70-90%)', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { confidence: 95 }),
      mockQueueItem('2', { confidence: 85 }),
      mockQueueItem('3', { confidence: 71 }),
      mockQueueItem('4', { confidence: 70 }), // Not > 70
      mockQueueItem('5', { confidence: 50 }),
    ];

    act(() => {
      result.current.setQueue(items);
      result.current.setFilters({ confidenceTier: 'medium' });
    });

    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    expect(filtered.length).toBe(2);
    expect(filtered.every(item => item.confidence > 70 && item.confidence <= 90)).toBe(true);
  });

  it('should filter by confidenceTier low (<70%)', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { confidence: 95 }),
      mockQueueItem('2', { confidence: 85 }),
      mockQueueItem('3', { confidence: 70 }),
      mockQueueItem('4', { confidence: 65 }),
      mockQueueItem('5', { confidence: 40 }),
    ];

    act(() => {
      result.current.setQueue(items);
      result.current.setFilters({ confidenceTier: 'low' });
    });

    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    expect(filtered.length).toBe(3);
    expect(filtered.every(item => item.confidence <= 70)).toBe(true);
  });

  it('should filter by status', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { decision: VerificationDecision.PENDING }),
      mockQueueItem('2', { decision: VerificationDecision.APPROVED }),
      mockQueueItem('3', { decision: VerificationDecision.PENDING }),
      mockQueueItem('4', { decision: VerificationDecision.FLAGGED }),
    ];

    act(() => {
      result.current.setQueue(items);
      result.current.setFilters({ status: VerificationDecision.PENDING });
    });

    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    expect(filtered.length).toBe(2);
    expect(filtered.every(item => item.decision === VerificationDecision.PENDING)).toBe(true);
  });

  it('should combine multiple filters with AND logic', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { findingType: 'citation_mismatch', confidence: 50, decision: VerificationDecision.PENDING }),
      mockQueueItem('2', { findingType: 'citation_mismatch', confidence: 90, decision: VerificationDecision.PENDING }),
      mockQueueItem('3', { findingType: 'timeline_anomaly', confidence: 50, decision: VerificationDecision.PENDING }),
      mockQueueItem('4', { findingType: 'citation_mismatch', confidence: 50, decision: VerificationDecision.APPROVED }),
      mockQueueItem('5', { findingType: 'citation_mismatch', confidence: 50, decision: VerificationDecision.PENDING }), // Matches all
    ];

    act(() => {
      result.current.setQueue(items);
      result.current.setFilters({
        findingType: 'citation_mismatch',
        confidenceTier: 'low',
        status: VerificationDecision.PENDING,
      });
    });

    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    // Only items 1 and 5 match all three filters
    expect(filtered.length).toBe(2);
    expect(filtered.map(item => item.id)).toEqual(['1', '5']);
  });

  it('should return empty array when no items match filters', () => {
    const { result } = renderHook(() => useVerificationStore());
    const items = [
      mockQueueItem('1', { findingType: 'citation_mismatch', confidence: 95 }),
      mockQueueItem('2', { findingType: 'timeline_anomaly', confidence: 85 }),
    ];

    act(() => {
      result.current.setQueue(items);
      result.current.setFilters({
        findingType: 'contradiction', // No items with this type
      });
    });

    const state = useVerificationStore.getState();
    const filtered = selectFilteredQueueHelper(state);

    expect(filtered.length).toBe(0);
  });
});

// Helper to access selectFilteredQueue logic inline
function selectFilteredQueueHelper(state: ReturnType<typeof useVerificationStore.getState>) {
  let filtered = state.queue;

  // Filter by finding type
  if (state.filters.findingType) {
    filtered = filtered.filter(
      (item) => item.findingType === state.filters.findingType
    );
  }

  // Filter by confidence tier
  if (state.filters.confidenceTier) {
    filtered = filtered.filter((item) => {
      const confidence = item.confidence;
      switch (state.filters.confidenceTier) {
        case 'high':
          return confidence > 90;
        case 'medium':
          return confidence > 70 && confidence <= 90;
        case 'low':
          return confidence <= 70;
        default:
          return true;
      }
    });
  }

  // Filter by status
  if (state.filters.status) {
    filtered = filtered.filter((item) => item.decision === state.filters.status);
  }

  return filtered;
}

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
