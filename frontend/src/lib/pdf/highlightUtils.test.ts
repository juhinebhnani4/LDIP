/**
 * Highlight Utilities Unit Tests
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #2)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  calculateBboxPosition,
  getBboxColor,
  isPointInRect,
  getBoundingRect,
} from './highlightUtils';
import { HIGHLIGHT_COLORS } from '@/types/pdf';
import type { VerificationStatus } from '@/types/citation';

describe('calculateBboxPosition', () => {
  it('converts normalized coordinates to pixel coordinates', () => {
    const bbox = { id: '1', x: 0.1, y: 0.2, width: 0.3, height: 0.05 };
    const pageWidth = 612; // Letter size
    const pageHeight = 792;
    const scale = 1.0;

    const rect = calculateBboxPosition(bbox, pageWidth, pageHeight, scale);

    expect(rect.x).toBeCloseTo(61.2);
    expect(rect.y).toBeCloseTo(158.4);
    expect(rect.width).toBeCloseTo(183.6);
    expect(rect.height).toBeCloseTo(39.6);
  });

  it('applies scale factor correctly', () => {
    const bbox = { id: '1', x: 0.1, y: 0.2, width: 0.3, height: 0.05 };
    const pageWidth = 612;
    const pageHeight = 792;
    const scale = 1.5; // 150% zoom

    const rect = calculateBboxPosition(bbox, pageWidth, pageHeight, scale);

    // Values should be 1.5x the base calculation
    expect(rect.x).toBeCloseTo(91.8);
    expect(rect.y).toBeCloseTo(237.6);
    expect(rect.width).toBeCloseTo(275.4);
    expect(rect.height).toBeCloseTo(59.4);
  });

  it('handles zero dimensions', () => {
    const bbox = { id: '1', x: 0, y: 0, width: 0, height: 0 };
    const pageWidth = 612;
    const pageHeight = 792;
    const scale = 1.0;

    const rect = calculateBboxPosition(bbox, pageWidth, pageHeight, scale);

    expect(rect.x).toBe(0);
    expect(rect.y).toBe(0);
    expect(rect.width).toBe(0);
    expect(rect.height).toBe(0);
  });

  it('handles full page bbox', () => {
    const bbox = { id: '1', x: 0, y: 0, width: 1, height: 1 };
    const pageWidth = 612;
    const pageHeight = 792;
    const scale = 1.0;

    const rect = calculateBboxPosition(bbox, pageWidth, pageHeight, scale);

    expect(rect.x).toBe(0);
    expect(rect.y).toBe(0);
    expect(rect.width).toBe(612);
    expect(rect.height).toBe(792);
  });
});

describe('getBboxColor', () => {
  it('returns yellow for source panel', () => {
    const statuses: VerificationStatus[] = [
      'pending',
      'verified',
      'mismatch',
      'section_not_found',
      'act_unavailable',
    ];

    for (const status of statuses) {
      const colors = getBboxColor(status, true);
      expect(colors).toEqual(HIGHLIGHT_COLORS.source);
    }
  });

  it('returns blue for verified target', () => {
    const colors = getBboxColor('verified', false);
    expect(colors).toEqual(HIGHLIGHT_COLORS.verified);
  });

  it('returns red for mismatch target (AC: #3)', () => {
    const colors = getBboxColor('mismatch', false);
    expect(colors).toEqual(HIGHLIGHT_COLORS.mismatch);
  });

  it('returns orange for section_not_found target', () => {
    const colors = getBboxColor('section_not_found', false);
    expect(colors).toEqual(HIGHLIGHT_COLORS.sectionNotFound);
  });

  it('returns blue for pending target', () => {
    const colors = getBboxColor('pending', false);
    expect(colors).toEqual(HIGHLIGHT_COLORS.verified);
  });

  it('returns blue for act_unavailable target', () => {
    const colors = getBboxColor('act_unavailable', false);
    expect(colors).toEqual(HIGHLIGHT_COLORS.verified);
  });
});

describe('isPointInRect', () => {
  const rect = { x: 100, y: 100, width: 200, height: 50 };

  it('returns true for point inside rectangle', () => {
    expect(isPointInRect(150, 125, rect)).toBe(true);
  });

  it('returns true for point on rectangle edge', () => {
    expect(isPointInRect(100, 100, rect)).toBe(true); // Top-left corner
    expect(isPointInRect(300, 150, rect)).toBe(true); // Bottom-right corner
  });

  it('returns false for point outside rectangle', () => {
    expect(isPointInRect(50, 125, rect)).toBe(false); // Left of rect
    expect(isPointInRect(350, 125, rect)).toBe(false); // Right of rect
    expect(isPointInRect(150, 50, rect)).toBe(false); // Above rect
    expect(isPointInRect(150, 200, rect)).toBe(false); // Below rect
  });
});

describe('getBoundingRect', () => {
  it('returns null for empty array', () => {
    expect(getBoundingRect([])).toBeNull();
  });

  it('returns same rect for single rectangle', () => {
    const rects = [{ x: 100, y: 100, width: 200, height: 50 }];
    const result = getBoundingRect(rects);

    expect(result).toEqual({ x: 100, y: 100, width: 200, height: 50 });
  });

  it('returns bounding rect for multiple rectangles', () => {
    const rects = [
      { x: 100, y: 100, width: 50, height: 25 },
      { x: 200, y: 150, width: 100, height: 50 },
    ];
    const result = getBoundingRect(rects);

    // Should span from (100, 100) to (300, 200)
    expect(result).toEqual({ x: 100, y: 100, width: 200, height: 100 });
  });

  it('handles overlapping rectangles', () => {
    const rects = [
      { x: 100, y: 100, width: 100, height: 100 },
      { x: 150, y: 150, width: 100, height: 100 },
    ];
    const result = getBoundingRect(rects);

    // Should span from (100, 100) to (250, 250)
    expect(result).toEqual({ x: 100, y: 100, width: 150, height: 150 });
  });
});
