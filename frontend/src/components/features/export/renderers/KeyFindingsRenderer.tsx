'use client';

/**
 * KeyFindingsRenderer Component
 *
 * Renders the Key Findings section in export preview.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { Button } from '@/components/ui/button';
import { X, RotateCcw, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { KeyIssue } from '@/types/summary';

export interface KeyFindingsRendererProps {
  /** Key findings/issues */
  findings?: KeyIssue[];
  /** IDs of removed findings */
  removedItemIds: string[];
  /** Handler for removing a finding */
  onRemoveItem: (itemId: string) => void;
  /** Handler for restoring a finding */
  onRestoreItem: (itemId: string) => void;
  /** Whether editing is active */
  isEditing: boolean;
}

/**
 * Get verification status display
 */
function getStatusDisplay(status: string) {
  switch (status) {
    case 'verified':
      return { icon: CheckCircle, className: 'text-green-500', label: 'Verified' };
    case 'pending':
      return { icon: Clock, className: 'text-yellow-500', label: 'Pending' };
    case 'flagged':
      return { icon: AlertCircle, className: 'text-red-500', label: 'Flagged' };
    default:
      return { icon: Clock, className: 'text-gray-500', label: 'Unknown' };
  }
}

/**
 * KeyFindingsRenderer displays numbered findings list.
 */
export function KeyFindingsRenderer({
  findings,
  removedItemIds,
  onRemoveItem,
  onRestoreItem,
  isEditing,
}: KeyFindingsRendererProps) {
  if (!findings || findings.length === 0) {
    return <p className="text-muted-foreground text-sm">No key findings available</p>;
  }

  // Filter out removed findings
  const visibleFindings = findings.filter((finding) => !removedItemIds.includes(finding.id));
  const removedFindings = findings.filter((finding) => removedItemIds.includes(finding.id));

  return (
    <div className="space-y-3 font-serif text-sm">
      {visibleFindings.length === 0 ? (
        <p className="text-muted-foreground">All findings have been removed</p>
      ) : (
        <ol className="list-decimal list-inside space-y-3">
          {visibleFindings.map((finding) => {
            const { icon: StatusIcon, className: statusClassName, label } = getStatusDisplay(
              finding.verificationStatus
            );
            return (
              <li
                key={finding.id}
                className={cn(
                  'relative flex items-start gap-3 p-3 rounded border border-gray-200 dark:border-gray-700 group list-none',
                  isEditing && 'hover:border-red-300 dark:hover:border-red-700'
                )}
                data-testid={`finding-item-${finding.id}`}
              >
                {/* Number badge */}
                <span className="flex items-center justify-center h-6 w-6 rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  {finding.number}
                </span>

                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-700 dark:text-gray-300">{finding.title}</p>
                  <div className="flex items-center gap-1 mt-1">
                    <StatusIcon className={cn('h-3 w-3', statusClassName)} />
                    <span className={cn('text-xs', statusClassName)}>{label}</span>
                  </div>
                </div>

                {isEditing && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                    onClick={() => onRemoveItem(finding.id)}
                    aria-label={`Remove finding: ${finding.title}`}
                  >
                    <X className="h-4 w-4 text-red-500" />
                  </Button>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {/* Removed findings (edit mode only) */}
      {isEditing && removedFindings.length > 0 && (
        <div className="mt-4 pt-4 border-t border-dashed">
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Removed Findings:</h4>
          {removedFindings.map((finding) => (
            <div
              key={finding.id}
              className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded opacity-60"
            >
              <span className="flex-1 text-sm line-through">
                #{finding.number}: {finding.title}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-1"
                onClick={() => onRestoreItem(finding.id)}
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
