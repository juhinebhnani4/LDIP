/**
 * useBoundingBoxes Hook Tests
 *
 * Tests for the bbox data fetching hook.
 *
 * Story 11.7: Implement Bounding Box Overlays (AC: #6)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useBoundingBoxes } from './useBoundingBoxes';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('useBoundingBoxes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchByChunkId', () => {
    it('should fetch bounding boxes by chunk ID and normalize coordinates', async () => {
      const mockApiResponse = {
        data: [
          {
            id: 'bbox-1',
            document_id: 'doc-1',
            page_number: 5,
            x: 10, // 10% from API
            y: 20, // 20%
            width: 50, // 50%
            height: 5, // 5%
            text: 'Test text',
            confidence: 0.95,
            reading_order_index: 1,
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockApiResponse),
      });

      const { result } = renderHook(() => useBoundingBoxes());

      let bboxes;
      await act(async () => {
        bboxes = await result.current.fetchByChunkId('chunk-123');
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/chunks/chunk-123/bounding-boxes');
      expect(bboxes).toHaveLength(1);
      expect(bboxes![0]).toEqual({
        bboxId: 'bbox-1',
        x: 0.1, // Normalized from 10%
        y: 0.2, // Normalized from 20%
        width: 0.5, // Normalized from 50%
        height: 0.05, // Normalized from 5%
        text: 'Test text',
      });
      expect(result.current.bboxPageNumber).toBe(5);
    });

    it('should return empty array for 404 response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      const { result } = renderHook(() => useBoundingBoxes());

      let bboxes;
      await act(async () => {
        bboxes = await result.current.fetchByChunkId('chunk-not-found');
      });

      expect(bboxes).toEqual([]);
      expect(result.current.error).toBeNull();
    });

    it('should set error on fetch failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(() => useBoundingBoxes());

      await act(async () => {
        await result.current.fetchByChunkId('chunk-123');
      });

      expect(result.current.error).toBe(
        'Failed to fetch bounding boxes: Internal Server Error'
      );
    });

    it('should use cache for repeated requests', async () => {
      const mockApiResponse = {
        data: [
          {
            id: 'bbox-1',
            document_id: 'doc-1',
            page_number: 1,
            x: 10,
            y: 20,
            width: 50,
            height: 5,
            text: 'Cached text',
            confidence: 0.95,
            reading_order_index: 1,
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockApiResponse),
      });

      const { result } = renderHook(() => useBoundingBoxes());

      // First call
      await act(async () => {
        await result.current.fetchByChunkId('chunk-123');
      });

      // Second call (should use cache)
      await act(async () => {
        await result.current.fetchByChunkId('chunk-123');
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  describe('fetchByPage', () => {
    it('should fetch bounding boxes by document ID and page number', async () => {
      const mockApiResponse = {
        data: [
          {
            id: 'bbox-page-1',
            document_id: 'doc-1',
            page_number: 3,
            x: 25,
            y: 30,
            width: 40,
            height: 10,
            text: 'Page text',
            confidence: 0.9,
            reading_order_index: 0,
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockApiResponse),
      });

      const { result } = renderHook(() => useBoundingBoxes());

      let bboxes;
      await act(async () => {
        bboxes = await result.current.fetchByPage('doc-1', 3);
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/documents/doc-1/pages/3/bounding-boxes'
      );
      expect(bboxes).toHaveLength(1);
      expect(bboxes![0]).toEqual({
        bboxId: 'bbox-page-1',
        x: 0.25,
        y: 0.3,
        width: 0.4,
        height: 0.1,
        text: 'Page text',
      });
    });
  });

  describe('clearBboxes', () => {
    it('should clear all bounding box state', async () => {
      const mockApiResponse = {
        data: [
          {
            id: 'bbox-1',
            document_id: 'doc-1',
            page_number: 1,
            x: 10,
            y: 20,
            width: 50,
            height: 5,
            text: 'Test',
            confidence: 0.95,
            reading_order_index: 1,
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockApiResponse),
      });

      const { result } = renderHook(() => useBoundingBoxes());

      await act(async () => {
        await result.current.fetchByChunkId('chunk-123');
      });

      expect(result.current.boundingBoxes).toHaveLength(1);

      act(() => {
        result.current.clearBboxes();
      });

      expect(result.current.boundingBoxes).toHaveLength(0);
      expect(result.current.bboxPageNumber).toBeNull();
      expect(result.current.error).toBeNull();
    });
  });
});
