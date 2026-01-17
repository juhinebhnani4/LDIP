/**
 * useAnomalies Hook Tests
 *
 * Tests for the anomalies data fetching and mutation hooks.
 *
 * Story 14.16: Anomalies UI Integration
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import {
  getAnomalySeverityColor,
  getAnomalyTypeLabel,
  getAnomalySeverityLabel,
} from './useAnomalies';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

describe('useAnomalies', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getAnomalySeverityColor', () => {
    it('returns correct color classes for critical severity', () => {
      const result = getAnomalySeverityColor('critical');
      expect(result).toContain('text-red-700');
      expect(result).toContain('bg-red-50');
    });

    it('returns correct color classes for high severity', () => {
      const result = getAnomalySeverityColor('high');
      expect(result).toContain('text-red-600');
      expect(result).toContain('bg-red-50');
    });

    it('returns correct color classes for medium severity', () => {
      const result = getAnomalySeverityColor('medium');
      expect(result).toContain('text-orange-600');
      expect(result).toContain('bg-orange-50');
    });

    it('returns correct color classes for low severity', () => {
      const result = getAnomalySeverityColor('low');
      expect(result).toContain('text-yellow-600');
      expect(result).toContain('bg-yellow-50');
    });
  });

  describe('getAnomalyTypeLabel', () => {
    it('returns correct label for gap anomaly', () => {
      expect(getAnomalyTypeLabel('gap')).toBe('Unusual Gap');
    });

    it('returns correct label for sequence violation', () => {
      expect(getAnomalyTypeLabel('sequence_violation')).toBe('Sequence Violation');
    });

    it('returns correct label for duplicate', () => {
      expect(getAnomalyTypeLabel('duplicate')).toBe('Potential Duplicate');
    });

    it('returns correct label for outlier', () => {
      expect(getAnomalyTypeLabel('outlier')).toBe('Date Outlier');
    });

    it('returns Unknown for unrecognized type', () => {
      // @ts-expect-error Testing invalid input
      expect(getAnomalyTypeLabel('invalid')).toBe('Unknown');
    });
  });

  describe('getAnomalySeverityLabel', () => {
    it('capitalizes severity labels correctly', () => {
      expect(getAnomalySeverityLabel('low')).toBe('Low');
      expect(getAnomalySeverityLabel('medium')).toBe('Medium');
      expect(getAnomalySeverityLabel('high')).toBe('High');
      expect(getAnomalySeverityLabel('critical')).toBe('Critical');
    });
  });
});
