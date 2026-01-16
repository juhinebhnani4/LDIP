/**
 * Chat API Client
 *
 * API functions for fetching conversation history from the backend session memory service.
 * The backend (Story 7-1, 7-2) already implements SessionMemoryService with sliding window.
 *
 * Story 11.2: Implement Q&A Conversation History (AC: #3)
 */

import { api } from './client';
import type { ChatMessage, SessionContext } from '@/types/chat';

// ============================================================================
// Response Types (Backend API format)
// ============================================================================

interface BackendSessionMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  entity_refs?: string[];
  source_refs?: Array<{
    document_id: string;
    document_name: string;
    page?: number;
    bbox_ids?: string[];
  }>;
}

interface BackendSessionContext {
  session_id: string;
  matter_id: string;
  user_id: string;
  messages: BackendSessionMessage[];
  entities: string[];
  has_archived: boolean;
}

interface BackendArchivedResponse {
  messages: BackendSessionMessage[];
  has_more: boolean;
}

// ============================================================================
// Transform Functions
// ============================================================================

/**
 * Transform backend message format to frontend format.
 * Handles both snake_case and camelCase for backward compatibility.
 */
function transformMessage(backendMessage: BackendSessionMessage): ChatMessage {
  let messageId = backendMessage.id;
  if (!messageId) {
    messageId = crypto.randomUUID();
    if (process.env.NODE_ENV === 'development') {
      console.warn('[chat.ts] Backend message missing ID, generated fallback:', messageId);
    }
  }

  // Handle both snake_case and camelCase source refs
  const msg = backendMessage as unknown as Record<string, unknown>;
  const sourceRefs = backendMessage.source_refs ?? msg.sourceRefs as typeof backendMessage.source_refs;

  return {
    id: messageId,
    role: backendMessage.role,
    content: backendMessage.content,
    timestamp: backendMessage.timestamp,
    sources: sourceRefs?.map((ref) => {
      const r = ref as unknown as Record<string, unknown>;
      return {
        documentId: (r.documentId as string) ?? ref.document_id,
        documentName: (r.documentName as string) ?? ref.document_name,
        page: ref.page,
        bboxIds: (r.bboxIds as string[]) ?? ref.bbox_ids,
      };
    }),
  };
}

/**
 * Transform backend session context to frontend format.
 * Handles both snake_case and camelCase for backward compatibility.
 */
function transformSessionContext(backend: BackendSessionContext): SessionContext {
  const b = backend as unknown as Record<string, unknown>;
  return {
    sessionId: (b.sessionId ?? b.session_id) as string,
    matterId: (b.matterId ?? b.matter_id) as string,
    userId: (b.userId ?? b.user_id) as string,
    messages: backend.messages.map(transformMessage),
    entities: backend.entities,
    hasArchived: (b.hasArchived ?? b.has_archived) as boolean,
  };
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch conversation history for a matter/user session.
 *
 * Returns the sliding window of messages (max 20) from the backend
 * SessionMemoryService.
 *
 * @param matterId - The matter UUID
 * @param userId - The user UUID
 * @returns Session context with messages
 */
export async function getConversationHistory(
  matterId: string,
  userId: string
): Promise<SessionContext> {
  const response = await api.get<{ data: BackendSessionContext }>(
    `/api/v1/session/${matterId}/${userId}`
  );
  return transformSessionContext(response.data);
}

/**
 * Load archived messages from Matter Memory.
 *
 * Called when user scrolls up and wants to load older messages
 * that have been archived from the session sliding window.
 *
 * @param matterId - The matter UUID
 * @param userId - The user UUID
 * @returns Archived messages with hasMore flag
 */
export async function getArchivedMessages(
  matterId: string,
  userId: string
): Promise<{ messages: ChatMessage[]; hasMore: boolean }> {
  const response = await api.get<{ data: BackendArchivedResponse }>(
    `/api/v1/session/${matterId}/${userId}/archived`
  );
  return {
    messages: response.data.messages.map(transformMessage),
    hasMore: response.data.has_more,
  };
}

