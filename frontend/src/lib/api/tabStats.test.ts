/**
 * Tab Stats API Client Tests
 *
 * Story 14.12: Tab Stats API (Task 6)
 *
 * Tests for the tab stats API client functions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchTabStats, transformTabStatsResponse } from './tabStats';
import type { TabStatsResponse } from './tabStats';

// Mock the api client
vi.mock('./client', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from './client';
const mockApiGet = vi.mocked(api.get);

describe('tabStats API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchTabStats', () => {
    it('calls correct endpoint with matter ID', async () => {
      const mockResponse: TabStatsResponse = {
        data: {
          tabCounts: {
            summary: { count: 1, issueCount: 0 },
            timeline: { count: 24, issueCount: 0 },
            entities: { count: 18, issueCount: 2 },
            citations: { count: 45, issueCount: 3 },
            contradictions: { count: 7, issueCount: 7 },
            verification: { count: 12, issueCount: 5 },
            documents: { count: 8, issueCount: 0 },
          },
          tabProcessingStatus: {
            summary: 'ready',
            timeline: 'ready',
            entities: 'processing',
            citations: 'ready',
            contradictions: 'ready',
            verification: 'ready',
            documents: 'ready',
          },
        },
      };

      mockApiGet.mockResolvedValue(mockResponse);

      const result = await fetchTabStats('matter-123');

      expect(mockApiGet).toHaveBeenCalledWith('/api/matters/matter-123/tab-stats');
      expect(result).toEqual(mockResponse);
    });

    it('propagates API errors', async () => {
      const error = new Error('API Error');
      mockApiGet.mockRejectedValue(error);

      await expect(fetchTabStats('matter-123')).rejects.toThrow('API Error');
    });
  });

  describe('transformTabStatsResponse', () => {
    it('transforms API response to store format', () => {
      const apiResponse: TabStatsResponse = {
        data: {
          tabCounts: {
            summary: { count: 1, issueCount: 0 },
            timeline: { count: 24, issueCount: 0 },
            entities: { count: 18, issueCount: 2 },
            citations: { count: 45, issueCount: 3 },
            contradictions: { count: 7, issueCount: 7 },
            verification: { count: 12, issueCount: 5 },
            documents: { count: 8, issueCount: 0 },
          },
          tabProcessingStatus: {
            summary: 'ready',
            timeline: 'processing',
            entities: 'ready',
            citations: 'ready',
            contradictions: 'ready',
            verification: 'ready',
            documents: 'processing',
          },
        },
      };

      const result = transformTabStatsResponse(apiResponse);

      // Verify tabCounts are transformed correctly
      expect(result.tabCounts.summary).toEqual({ count: 1, issueCount: 0 });
      expect(result.tabCounts.timeline).toEqual({ count: 24, issueCount: 0 });
      expect(result.tabCounts.entities).toEqual({ count: 18, issueCount: 2 });
      expect(result.tabCounts.citations).toEqual({ count: 45, issueCount: 3 });
      expect(result.tabCounts.contradictions).toEqual({ count: 7, issueCount: 7 });
      expect(result.tabCounts.verification).toEqual({ count: 12, issueCount: 5 });
      expect(result.tabCounts.documents).toEqual({ count: 8, issueCount: 0 });

      // Verify tabProcessingStatus are transformed correctly
      expect(result.tabProcessingStatus.summary).toBe('ready');
      expect(result.tabProcessingStatus.timeline).toBe('processing');
      expect(result.tabProcessingStatus.entities).toBe('ready');
      expect(result.tabProcessingStatus.documents).toBe('processing');
    });

    it('preserves all tab data', () => {
      const apiResponse: TabStatsResponse = {
        data: {
          tabCounts: {
            summary: { count: 1, issueCount: 0 },
            timeline: { count: 0, issueCount: 0 },
            entities: { count: 0, issueCount: 0 },
            citations: { count: 0, issueCount: 0 },
            contradictions: { count: 0, issueCount: 0 },
            verification: { count: 0, issueCount: 0 },
            documents: { count: 0, issueCount: 0 },
          },
          tabProcessingStatus: {
            summary: 'ready',
            timeline: 'ready',
            entities: 'ready',
            citations: 'ready',
            contradictions: 'ready',
            verification: 'ready',
            documents: 'ready',
          },
        },
      };

      const result = transformTabStatsResponse(apiResponse);

      // All 7 tabs should be present
      const tabIds = Object.keys(result.tabCounts);
      expect(tabIds).toHaveLength(7);
      expect(tabIds).toContain('summary');
      expect(tabIds).toContain('timeline');
      expect(tabIds).toContain('entities');
      expect(tabIds).toContain('citations');
      expect(tabIds).toContain('contradictions');
      expect(tabIds).toContain('verification');
      expect(tabIds).toContain('documents');
    });

    it('handles processing status values correctly', () => {
      const apiResponse: TabStatsResponse = {
        data: {
          tabCounts: {
            summary: { count: 1, issueCount: 0 },
            timeline: { count: 10, issueCount: 0 },
            entities: { count: 5, issueCount: 1 },
            citations: { count: 20, issueCount: 2 },
            contradictions: { count: 3, issueCount: 3 },
            verification: { count: 8, issueCount: 0 },
            documents: { count: 4, issueCount: 0 },
          },
          tabProcessingStatus: {
            summary: 'ready',
            timeline: 'processing',
            entities: 'processing',
            citations: 'ready',
            contradictions: 'ready',
            verification: 'processing',
            documents: 'processing',
          },
        },
      };

      const result = transformTabStatsResponse(apiResponse);

      // Count tabs with each status
      const statuses = Object.values(result.tabProcessingStatus);
      const readyCount = statuses.filter(s => s === 'ready').length;
      const processingCount = statuses.filter(s => s === 'processing').length;

      expect(readyCount).toBe(3);
      expect(processingCount).toBe(4);
    });
  });
});
