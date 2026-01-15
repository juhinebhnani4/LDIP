'use client';

import { QAPanelHeader } from './QAPanelHeader';
import { QAPanelPlaceholder } from './QAPanelPlaceholder';

/**
 * Q&A Panel Component
 *
 * Main container for the Q&A panel, containing the header with position
 * controls and the content area. The actual Q&A functionality will be
 * implemented in Epic 11.
 *
 * Story 10A.3: Main Content Area and Q&A Panel Integration
 */
export function QAPanel() {
  return (
    <div className="flex h-full flex-col bg-background">
      <QAPanelHeader />
      <QAPanelPlaceholder />
    </div>
  );
}
