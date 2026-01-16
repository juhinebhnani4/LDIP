/**
 * Timeline Event API Tests
 *
 * Verifies that timelineEventApi uses the correct URL prefix (/api/matters/)
 * and properly handles requests.
 *
 * Story 14.8: Timeline Real API Integration (AC #2)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { timelineEventApi } from './client';

// Track captured requests
let capturedRequests: { method: string; url: string; body?: unknown }[] = [];

// Mock Supabase client
vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            access_token: 'test-token',
          },
        },
      }),
      refreshSession: vi.fn().mockResolvedValue({
        data: { session: null },
      }),
    },
  }),
}));

// Mock API response for manual event
const mockManualEventResponse = {
  id: 'evt-123',
  event_date: '2024-01-15',
  event_date_precision: 'day',
  event_date_text: '15th January 2024',
  event_type: 'filing',
  description: 'Test filing event',
  document_id: null,
  source_page: null,
  confidence: 1.0,
  entities: [],
  is_ambiguous: false,
  is_verified: false,
  is_manual: true,
  created_by: 'user-123',
  created_at: '2024-01-15T10:00:00Z',
};

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  capturedRequests = [];
  mockFetch.mockReset();

  // Default mock implementation that captures requests and returns success
  mockFetch.mockImplementation(async (url: string, options: RequestInit) => {
    const method = options.method || 'GET';
    const body = options.body ? JSON.parse(options.body as string) : undefined;
    const urlPath = new URL(url).pathname;

    capturedRequests.push({ method, url: urlPath, body });

    // Return appropriate response based on method
    if (method === 'DELETE') {
      return {
        ok: true,
        status: 204,
        json: async () => undefined,
      };
    }

    const response = method === 'PATCH' && urlPath.includes('/verify')
      ? { ...mockManualEventResponse, is_verified: true }
      : mockManualEventResponse;

    return {
      ok: true,
      status: 200,
      json: async () => response,
    };
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('timelineEventApi', () => {
  describe('URL prefix', () => {
    it('create uses /api/matters/ prefix (not /api/v1/matters/)', async () => {
      const matterId = 'test-matter-123';

      await timelineEventApi.create(matterId, {
        eventDate: '2024-01-15',
        eventType: 'filing',
        title: 'Test filing',
        description: 'Test description',
        entityIds: [],
      });

      // Verify the request was made to the correct URL
      expect(capturedRequests).toHaveLength(1);
      expect(capturedRequests[0].method).toBe('POST');
      expect(capturedRequests[0].url).toBe(`/api/matters/${matterId}/timeline/events`);
      // Should NOT contain /api/v1/
      expect(capturedRequests[0].url).not.toContain('/api/v1/');
    });

    it('update uses /api/matters/ prefix (not /api/v1/matters/)', async () => {
      const matterId = 'test-matter-123';
      const eventId = 'evt-456';

      await timelineEventApi.update(matterId, eventId, {
        eventType: 'hearing',
      });

      expect(capturedRequests).toHaveLength(1);
      expect(capturedRequests[0].method).toBe('PATCH');
      expect(capturedRequests[0].url).toBe(`/api/matters/${matterId}/timeline/events/${eventId}`);
      expect(capturedRequests[0].url).not.toContain('/api/v1/');
    });

    it('delete uses /api/matters/ prefix (not /api/v1/matters/)', async () => {
      const matterId = 'test-matter-123';
      const eventId = 'evt-789';

      await timelineEventApi.delete(matterId, eventId);

      expect(capturedRequests).toHaveLength(1);
      expect(capturedRequests[0].method).toBe('DELETE');
      expect(capturedRequests[0].url).toBe(`/api/matters/${matterId}/timeline/events/${eventId}`);
      expect(capturedRequests[0].url).not.toContain('/api/v1/');
    });

    it('setVerified uses /api/matters/ prefix (not /api/v1/matters/)', async () => {
      const matterId = 'test-matter-123';
      const eventId = 'evt-101';

      await timelineEventApi.setVerified(matterId, eventId, true);

      expect(capturedRequests).toHaveLength(1);
      expect(capturedRequests[0].method).toBe('PATCH');
      expect(capturedRequests[0].url).toBe(`/api/matters/${matterId}/timeline/events/${eventId}/verify`);
      expect(capturedRequests[0].url).not.toContain('/api/v1/');
    });
  });

  describe('request payload transformation', () => {
    it('create transforms camelCase to snake_case', async () => {
      await timelineEventApi.create('matter-1', {
        eventDate: '2024-01-15',
        eventType: 'filing',
        title: 'Test event',
        description: 'Test description',
        entityIds: ['entity-1', 'entity-2'],
        sourceDocumentId: 'doc-1',
        sourcePage: 5,
      });

      expect(capturedRequests[0].body).toEqual({
        event_date: '2024-01-15',
        event_type: 'filing',
        title: 'Test event',
        description: 'Test description',
        entity_ids: ['entity-1', 'entity-2'],
        source_document_id: 'doc-1',
        source_page: 5,
      });
    });

    it('update transforms camelCase to snake_case', async () => {
      await timelineEventApi.update('matter-1', 'evt-1', {
        eventDate: '2024-02-20',
        eventType: 'hearing',
        description: 'Updated description',
        entityIds: ['entity-3'],
      });

      expect(capturedRequests[0].body).toEqual({
        event_date: '2024-02-20',
        event_type: 'hearing',
        description: 'Updated description',
        entity_ids: ['entity-3'],
      });
    });

    it('setVerified sends is_verified in snake_case', async () => {
      await timelineEventApi.setVerified('matter-1', 'evt-1', true);

      expect(capturedRequests[0].body).toEqual({
        is_verified: true,
      });
    });
  });

  describe('response transformation', () => {
    it('create transforms snake_case response to camelCase', async () => {
      const result = await timelineEventApi.create('matter-1', {
        eventDate: '2024-01-15',
        eventType: 'filing',
        title: 'Test',
        description: 'Test desc',
        entityIds: [],
      });

      // Should have camelCase properties
      expect(result.id).toBe('evt-123');
      expect(result.eventDate).toBe('2024-01-15');
      expect(result.eventDatePrecision).toBe('day');
      expect(result.eventDateText).toBe('15th January 2024');
      expect(result.eventType).toBe('filing');
      expect(result.isVerified).toBe(false);
      expect(result.isManual).toBe(true);
      expect(result.createdBy).toBe('user-123');
    });
  });

  describe('error handling', () => {
    it('handles 500 error from API with correct error type and message', async () => {
      mockFetch.mockImplementationOnce(async () => ({
        ok: false,
        status: 500,
        json: async () => ({ error: { code: 'SERVER_ERROR', message: 'Internal server error' } }),
      }));

      await expect(
        timelineEventApi.create('matter-1', {
          eventDate: '2024-01-15',
          eventType: 'filing',
          title: 'Test',
          description: 'Test desc',
          entityIds: [],
        })
      ).rejects.toMatchObject({
        name: 'ApiError',
        code: 'SERVER_ERROR',
        message: 'Internal server error',
        status: 500,
      });
    });

    it('handles 404 error for non-existent event', async () => {
      mockFetch.mockImplementationOnce(async () => ({
        ok: false,
        status: 404,
        json: async () => ({ error: { code: 'NOT_FOUND', message: 'Event not found' } }),
      }));

      await expect(
        timelineEventApi.update('matter-1', 'non-existent-event', { eventType: 'hearing' })
      ).rejects.toMatchObject({
        name: 'ApiError',
        code: 'NOT_FOUND',
        message: 'Event not found',
        status: 404,
      });
    });

    it('handles 401 error and attempts token refresh', async () => {
      // First call returns 401, simulating expired token
      mockFetch
        .mockImplementationOnce(async () => ({
          ok: false,
          status: 401,
          json: async () => ({ error: { code: 'UNAUTHORIZED', message: 'Token expired' } }),
        }))
        // After refresh fails (mock returns null session), should throw SESSION_EXPIRED
        .mockImplementationOnce(async () => ({
          ok: false,
          status: 401,
          json: async () => ({ error: { code: 'SESSION_EXPIRED', message: 'Session expired' } }),
        }));

      await expect(
        timelineEventApi.delete('matter-1', 'evt-1')
      ).rejects.toMatchObject({
        name: 'ApiError',
        code: 'SESSION_EXPIRED',
        message: 'Session expired',
        status: 401,
      });
    });
  });
});
