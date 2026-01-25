/**
 * Chat Types
 *
 * Type definitions for the Q&A conversation history functionality.
 *
 * Story 11.2: Implement Q&A Conversation History
 * Story 11.3: Streaming Response with Engine Trace
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
  /** Chunk UUID for specific content reference */
  chunkId?: string;
  /** Relevance/confidence score from engine */
  confidence?: number;
  /** Bounding box IDs for highlighting specific content (UI-only) */
  bboxIds?: string[];
  /** Preview snippet of the cited content for lawyer context */
  contextSnippet?: string;
}

/**
 * Source reference as received from backend API (snake_case).
 * Story 11.3: Maps to SourceReferenceEvent from backend/app/models/chat.py
 */
export interface SourceReferenceAPI {
  document_id: string;
  document_name?: string | null;
  page?: number | null;
  chunk_id?: string | null;
  confidence?: number | null;
  context_snippet?: string | null;
}

/**
 * Transform backend API source reference to frontend format.
 */
export function transformSourceReference(api: SourceReferenceAPI): SourceReference {
  return {
    documentId: api.document_id,
    documentName: api.document_name ?? 'Unknown Document',
    page: api.page ?? undefined,
    chunkId: api.chunk_id ?? undefined,
    confidence: api.confidence ?? undefined,
    contextSnippet: api.context_snippet ?? undefined,
  };
}

/**
 * Engine execution trace for displaying processing details.
 * Story 11.3: Streaming Response with Engine Trace
 */
export interface EngineTrace {
  /** Engine identifier (citation, timeline, contradiction, rag) */
  engine: string;
  /** Execution time in milliseconds */
  executionTimeMs: number;
  /** Number of findings produced */
  findingsCount: number;
  /** Whether execution succeeded */
  success: boolean;
  /** Error message if failed */
  error?: string;
}

/**
 * Engine trace as received from backend API (snake_case).
 * Story 11.3: Maps to EngineTraceEvent from backend/app/models/chat.py
 */
export interface EngineTraceAPI {
  engine: string;
  execution_time_ms: number;
  findings_count: number;
  success: boolean;
  error?: string | null;
}

/**
 * Transform backend API engine trace to frontend format.
 */
export function transformEngineTrace(api: EngineTraceAPI): EngineTrace {
  return {
    engine: api.engine,
    executionTimeMs: api.execution_time_ms,
    findingsCount: api.findings_count,
    success: api.success,
    error: api.error ?? undefined,
  };
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
  /** Engine execution traces (assistant messages only) - Story 11.3 */
  engineTraces?: EngineTrace[];
  /** Search mode used: hybrid, bm25_only, or bm25_fallback (Optimistic RAG) */
  searchMode?: 'hybrid' | 'bm25_only' | 'bm25_fallback';
  /** Embedding completion percentage 0-100 (Optimistic RAG) */
  embeddingCompletionPct?: number;
  /** User-friendly notice about search limitations (Optimistic RAG) */
  searchNotice?: string;
  /**
   * Story 2.3: Whether the response completed normally.
   * - true: Response completed with proper 'complete' event
   * - false: Response was interrupted (error, timeout, or parse failure)
   * - undefined: User message or legacy message (no completion tracking)
   */
  isComplete?: boolean;
  /** Whether the response was truncated due to length */
  truncated?: boolean;
  /** Whether more results are available beyond what was shown */
  moreAvailable?: boolean;
  /** Hint showing total results available (if moreAvailable is true) */
  totalResultsHint?: number;
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
