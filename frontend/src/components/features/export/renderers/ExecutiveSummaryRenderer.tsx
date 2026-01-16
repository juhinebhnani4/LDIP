'use client';

/**
 * ExecutiveSummaryRenderer Component
 *
 * Renders the Executive Summary section in export preview.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import type { MatterSummary } from '@/types/summary';

export interface ExecutiveSummaryRendererProps {
  /** Summary data */
  summary?: MatterSummary;
  /** Whether editing is active */
  isEditing: boolean;
  /** Handler for updating text content */
  onUpdateText: (text: string) => void;
  /** Current edited text content */
  textContent?: string;
}

/**
 * ExecutiveSummaryRenderer displays parties, subject matter, and current status.
 */
export function ExecutiveSummaryRenderer({
  summary,
  isEditing,
  onUpdateText,
  textContent,
}: ExecutiveSummaryRendererProps) {
  if (!summary) {
    return <p className="text-muted-foreground text-sm">No summary data available</p>;
  }

  // If there's edited text content, show that in edit mode
  if (isEditing && textContent !== undefined) {
    return (
      <textarea
        value={textContent}
        onChange={(e) => onUpdateText(e.target.value)}
        className="w-full min-h-[200px] p-3 border rounded font-serif text-sm leading-relaxed resize-none"
        placeholder="Edit summary content..."
        data-testid="executive-summary-editor"
      />
    );
  }

  return (
    <div className="space-y-4 font-serif text-sm leading-relaxed">
      {/* Parties Section */}
      {summary.parties && summary.parties.length > 0 && (
        <div>
          <h3 className="font-semibold mb-2">Parties</h3>
          <ul className="list-disc list-inside space-y-1">
            {summary.parties.map((party) => (
              <li key={party.entityId} className="text-gray-700 dark:text-gray-300">
                <span className="font-medium">{party.entityName}</span>
                <span className="text-muted-foreground"> ({party.role})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Subject Matter */}
      {summary.subjectMatter?.description && (
        <div>
          <h3 className="font-semibold mb-2">Subject Matter</h3>
          <p className="text-gray-700 dark:text-gray-300">{summary.subjectMatter.description}</p>
        </div>
      )}

      {/* Current Status */}
      {summary.currentStatus?.description && (
        <div>
          <h3 className="font-semibold mb-2">Current Status</h3>
          <p className="text-gray-700 dark:text-gray-300">
            {summary.currentStatus.description}
            {summary.currentStatus.lastOrderDate && (
              <span className="text-muted-foreground">
                {' '}
                (as of {new Date(summary.currentStatus.lastOrderDate).toLocaleDateString()})
              </span>
            )}
          </p>
        </div>
      )}

      {/* Attention Items */}
      {summary.attentionItems && summary.attentionItems.length > 0 && (
        <div>
          <h3 className="font-semibold mb-2">Requires Attention</h3>
          <ul className="list-disc list-inside space-y-1">
            {summary.attentionItems.map((item, index) => (
              <li key={index} className="text-amber-600 dark:text-amber-400">
                {item.label}: {item.count}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
