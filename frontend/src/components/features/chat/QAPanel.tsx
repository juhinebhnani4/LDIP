'use client';

import { QAPanelHeader } from './QAPanelHeader';
import { ConversationHistory } from './ConversationHistory';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';
import type { SourceReference } from '@/types/chat';

interface QAPanelProps {
  /** Matter ID for loading conversation history */
  matterId?: string;
  /** User ID for loading conversation history */
  userId?: string;
  /** Callback when a source reference is clicked */
  onSourceClick?: (source: SourceReference) => void;
}

/**
 * Q&A Panel Component
 *
 * Main container for the Q&A panel, containing the header with position
 * controls and the conversation history content area.
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 * Story 11.2: Implement Q&A Conversation History
 */
export function QAPanel({ matterId, userId, onSourceClick }: QAPanelProps) {
  // Show placeholder if we don't have matter/user context
  const canLoadHistory = Boolean(matterId && userId);

  return (
    <div className="flex h-full flex-col bg-background">
      <QAPanelHeader />
      {canLoadHistory ? (
        <ConversationHistory
          matterId={matterId!}
          userId={userId!}
          onSourceClick={onSourceClick}
        />
      ) : (
        <QAPanelPlaceholder />
      )}
    </div>
  );
}
