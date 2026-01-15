/**
 * Chat Types
 *
 * Type definitions for the Q&A conversation history functionality.
 *
 * Story 11.2: Implement Q&A Conversation History
 */

/**
 * Source reference for linking to document locations.
 * Used when assistant messages contain citations.
 */
export interface SourceReference {
  /** Document UUID */
  documentId: string;
  /** Display name of the document */
  documentName: string;
  /** Page number in the document (1-indexed) */
  page?: number;
  /** Bounding box IDs for highlighting specific content */
  bboxIds?: string[];
}

/**
 * Chat message representing either a user question or assistant response.
 */
export interface ChatMessage {
  /** Unique identifier for the message */
  id: string;
  /** Who sent the message */
  role: 'user' | 'assistant';
  /** Message content text */
  content: string;
  /** ISO8601 timestamp when the message was sent */
  timestamp: string;
  /** Source references for citations (assistant messages only) */
  sources?: SourceReference[];
}

/**
 * Session context from the backend session memory service.
 * Corresponds to backend/app/models/memory.py:SessionContext
 */
export interface SessionContext {
  /** Session identifier */
  sessionId: string;
  /** Matter this session belongs to */
  matterId: string;
  /** User who owns this session */
  userId: string;
  /** Messages in the sliding window (max 20) */
  messages: ChatMessage[];
  /** Active entities tracked in session */
  entities: string[];
  /** Whether there are archived messages available */
  hasArchived: boolean;
}

/**
 * API response wrapper for session data.
 */
export interface SessionResponse {
  data: SessionContext;
}

/**
 * API response for restoring archived messages.
 */
export interface ArchivedMessagesResponse {
  data: {
    messages: ChatMessage[];
    hasMore: boolean;
  };
}
