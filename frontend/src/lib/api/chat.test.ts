import { describe, test, expect, vi, beforeEach } from 'vitest';
import { getConversationHistory, getArchivedMessages, restoreSession } from './chat';
import { api } from './client';

// Mock the API client
vi.mock('./client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockApiGet = vi.mocked(api.get);
const mockApiPost = vi.mocked(api.post);

describe('chat API', () => {
  const matterId = 'matter-123';
  const userId = 'user-456';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getConversationHistory', () => {
    const mockBackendResponse = {
      data: {
        session_id: 'session-1',
        matter_id: matterId,
        user_id: userId,
        messages: [
          {
            id: 'msg-1',
            role: 'user' as const,
            content: 'What is this case about?',
            timestamp: '2026-01-15T10:00:00Z',
          },
          {
            id: 'msg-2',
            role: 'assistant' as const,
            content: 'This case involves...',
            timestamp: '2026-01-15T10:00:05Z',
            source_refs: [
              {
                document_id: 'doc-1',
                document_name: 'petition.pdf',
                page: 5,
                bbox_ids: ['bbox-1', 'bbox-2'],
              },
            ],
          },
        ],
        entities: ['Entity 1', 'Entity 2'],
        has_archived: true,
      },
    };

    test('calls correct API endpoint', async () => {
      mockApiGet.mockResolvedValue(mockBackendResponse);

      await getConversationHistory(matterId, userId);

      expect(mockApiGet).toHaveBeenCalledWith(`/api/v1/session/${matterId}/${userId}`);
    });

    test('transforms session_id to sessionId', async () => {
      mockApiGet.mockResolvedValue(mockBackendResponse);

      const result = await getConversationHistory(matterId, userId);

      expect(result.sessionId).toBe('session-1');
    });

    test('transforms matter_id to matterId', async () => {
      mockApiGet.mockResolvedValue(mockBackendResponse);

      const result = await getConversationHistory(matterId, userId);

      expect(result.matterId).toBe(matterId);
    });

    test('transforms user_id to userId', async () => {
      mockApiGet.mockResolvedValue(mockBackendResponse);

      const result = await getConversationHistory(matterId, userId);

      expect(result.userId).toBe(userId);
    });

    test('transforms has_archived to hasArchived', async () => {
      mockApiGet.mockResolvedValue(mockBackendResponse);

      const result = await getConversationHistory(matterId, userId);

      expect(result.hasArchived).toBe(true);
    });

    test('transforms messages array', async () => {
      mockApiGet.mockResolvedValue(mockBackendResponse);

      const result = await getConversationHistory(matterId, userId);

      expect(result.messages).toHaveLength(2);
      const firstMessage = result.messages[0]!;
      expect(firstMessage.id).toBe('msg-1');
      expect(firstMessage.role).toBe('user');
      expect(firstMessage.content).toBe('What is this case about?');
    });

    test('transforms source_refs to sources', async () => {
      mockApiGet.mockResolvedValue(mockBackendResponse);

      const result = await getConversationHistory(matterId, userId);

      const assistantMessage = result.messages[1]!;
      expect(assistantMessage.sources).toBeDefined();
      expect(assistantMessage.sources).toHaveLength(1);
      expect(assistantMessage.sources![0]).toEqual({
        documentId: 'doc-1',
        documentName: 'petition.pdf',
        page: 5,
        bboxIds: ['bbox-1', 'bbox-2'],
      });
    });

    test('generates id if not provided by backend', async () => {
      const responseWithoutId = {
        data: {
          ...mockBackendResponse.data,
          messages: [
            {
              role: 'user' as const,
              content: 'Test',
              timestamp: '2026-01-15T10:00:00Z',
            },
          ],
        },
      };
      mockApiGet.mockResolvedValue(responseWithoutId);

      const result = await getConversationHistory(matterId, userId);

      const firstMessage = result.messages[0]!;
      expect(firstMessage.id).toBeDefined();
      expect(typeof firstMessage.id).toBe('string');
    });

    test('handles message without sources', async () => {
      const responseWithoutSources = {
        data: {
          ...mockBackendResponse.data,
          messages: [
            {
              id: 'msg-1',
              role: 'user' as const,
              content: 'Test',
              timestamp: '2026-01-15T10:00:00Z',
            },
          ],
        },
      };
      mockApiGet.mockResolvedValue(responseWithoutSources);

      const result = await getConversationHistory(matterId, userId);

      expect(result.messages[0]!.sources).toBeUndefined();
    });
  });

  describe('getArchivedMessages', () => {
    const mockArchivedResponse = {
      data: {
        messages: [
          {
            id: 'old-msg-1',
            role: 'user' as const,
            content: 'Old question',
            timestamp: '2026-01-14T10:00:00Z',
          },
          {
            id: 'old-msg-2',
            role: 'assistant' as const,
            content: 'Old answer',
            timestamp: '2026-01-14T10:00:05Z',
          },
        ],
        has_more: false,
      },
    };

    test('calls correct API endpoint', async () => {
      mockApiGet.mockResolvedValue(mockArchivedResponse);

      await getArchivedMessages(matterId, userId);

      expect(mockApiGet).toHaveBeenCalledWith(`/api/v1/session/${matterId}/${userId}/archived`);
    });

    test('transforms messages array', async () => {
      mockApiGet.mockResolvedValue(mockArchivedResponse);

      const result = await getArchivedMessages(matterId, userId);

      expect(result.messages).toHaveLength(2);
      expect(result.messages[0]!.id).toBe('old-msg-1');
      expect(result.messages[1]!.content).toBe('Old answer');
    });

    test('transforms has_more to hasMore', async () => {
      mockApiGet.mockResolvedValue(mockArchivedResponse);

      const result = await getArchivedMessages(matterId, userId);

      expect(result.hasMore).toBe(false);
    });

    test('returns hasMore true when more archived exist', async () => {
      mockApiGet.mockResolvedValue({
        data: {
          ...mockArchivedResponse.data,
          has_more: true,
        },
      });

      const result = await getArchivedMessages(matterId, userId);

      expect(result.hasMore).toBe(true);
    });
  });

  describe('restoreSession', () => {
    const mockRestoreResponse = {
      data: {
        session_id: 'restored-session-1',
        matter_id: matterId,
        user_id: userId,
        messages: [
          {
            id: 'restored-1',
            role: 'user' as const,
            content: 'Restored question',
            timestamp: '2026-01-14T10:00:00Z',
          },
        ],
        entities: [],
        has_archived: false,
      },
    };

    test('calls correct API endpoint with POST', async () => {
      mockApiPost.mockResolvedValue(mockRestoreResponse);

      await restoreSession(matterId, userId);

      expect(mockApiPost).toHaveBeenCalledWith(
        `/api/v1/session/${matterId}/${userId}/restore`,
        {}
      );
    });

    test('transforms response to SessionContext', async () => {
      mockApiPost.mockResolvedValue(mockRestoreResponse);

      const result = await restoreSession(matterId, userId);

      expect(result.sessionId).toBe('restored-session-1');
      expect(result.messages).toHaveLength(1);
      expect(result.hasArchived).toBe(false);
    });
  });
});
