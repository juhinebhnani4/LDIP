'use client';

/**
 * CitationsRenderer Component
 *
 * Renders the Citations section in export preview.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { Button } from '@/components/ui/button';
import { X, RotateCcw, BookOpen, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CitationListItem } from '@/types/citation';

export interface CitationsRendererProps {
  /** Citations list */
  citations?: CitationListItem[];
  /** IDs of removed citations */
  removedItemIds: string[];
  /** Handler for removing a citation */
  onRemoveItem: (itemId: string) => void;
  /** Handler for restoring a citation */
  onRestoreItem: (itemId: string) => void;
  /** Whether editing is active */
  isEditing: boolean;
}

/**
 * Get verification status icon
 */
function getStatusIcon(status: string) {
  switch (status) {
    case 'verified':
      return { icon: CheckCircle, className: 'text-green-500' };
    case 'pending':
      return { icon: Clock, className: 'text-yellow-500' };
    case 'mismatch':
    case 'section_not_found':
    case 'act_unavailable':
      return { icon: AlertCircle, className: 'text-red-500' };
    default:
      return { icon: Clock, className: 'text-gray-500' };
  }
}

/**
 * CitationsRenderer displays citations with Act references.
 */
export function CitationsRenderer({
  citations,
  removedItemIds,
  onRemoveItem,
  onRestoreItem,
  isEditing,
}: CitationsRendererProps) {
  if (!citations || citations.length === 0) {
    return <p className="text-muted-foreground text-sm">No citations available</p>;
  }

  // Filter out removed citations
  const visibleCitations = citations.filter((citation) => !removedItemIds.includes(citation.id));
  const removedCitations = citations.filter((citation) => removedItemIds.includes(citation.id));

  return (
    <div className="space-y-2 font-serif text-sm">
      {visibleCitations.length === 0 ? (
        <p className="text-muted-foreground">All citations have been removed</p>
      ) : (
        <div className="space-y-2">
          {visibleCitations.map((citation) => {
            const { icon: StatusIcon, className: statusClassName } = getStatusIcon(citation.verificationStatus);
            return (
              <div
                key={citation.id}
                className={cn(
                  'flex items-start gap-3 p-3 rounded border border-gray-200 dark:border-gray-700 group',
                  isEditing && 'hover:border-red-300 dark:hover:border-red-700'
                )}
                data-testid={`citation-item-${citation.id}`}
              >
                <BookOpen className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />

                <div className="flex-1 min-w-0">
                  <p className="font-medium">{citation.actName}</p>
                  <p className="text-muted-foreground">
                    Section {citation.sectionNumber}
                  </p>
                  {citation.rawCitationText && (
                    <p className="mt-1 text-gray-600 dark:text-gray-400 italic text-xs line-clamp-2">
                      &quot;{citation.rawCitationText}&quot;
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <StatusIcon className={cn('h-4 w-4', statusClassName)} />

                  {isEditing && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => onRemoveItem(citation.id)}
                      aria-label={`Remove citation: ${citation.actName} Section ${citation.sectionNumber}`}
                    >
                      <X className="h-4 w-4 text-red-500" />
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Removed citations (edit mode only) */}
      {isEditing && removedCitations.length > 0 && (
        <div className="mt-4 pt-4 border-t border-dashed">
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Removed Citations:</h4>
          {removedCitations.map((citation) => (
            <div
              key={citation.id}
              className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded opacity-60"
            >
              <span className="flex-1 text-sm line-through">
                {citation.actName} - Section {citation.sectionNumber}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-1"
                onClick={() => onRestoreItem(citation.id)}
              >
                <RotateCcw className="h-3 w-3" />
                Restore
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
