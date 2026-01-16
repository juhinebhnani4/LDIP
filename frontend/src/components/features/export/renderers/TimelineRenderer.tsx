'use client';

/**
 * TimelineRenderer Component
 *
 * Renders the Timeline section in export preview with event list.
 *
 * @see Story 12.2 - Export Inline Editing and Preview
 */

import { Button } from '@/components/ui/button';
import { X, RotateCcw, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TimelineEvent } from '@/types/timeline';

export interface TimelineRendererProps {
  /** Timeline events */
  events?: TimelineEvent[];
  /** IDs of removed events */
  removedItemIds: string[];
  /** Handler for removing an event */
  onRemoveItem: (itemId: string) => void;
  /** Handler for restoring an event */
  onRestoreItem: (itemId: string) => void;
  /** Whether editing is active */
  isEditing: boolean;
}

/**
 * Format date for display
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * TimelineRenderer displays events in chronological order.
 */
export function TimelineRenderer({
  events,
  removedItemIds,
  onRemoveItem,
  onRestoreItem,
  isEditing,
}: TimelineRendererProps) {
  if (!events || events.length === 0) {
    return <p className="text-muted-foreground text-sm">No timeline events available</p>;
  }

  // Filter out removed events for display (but keep them for restoration)
  const visibleEvents = events.filter((event) => !removedItemIds.includes(event.id));
  const removedEvents = events.filter((event) => removedItemIds.includes(event.id));

  return (
    <div className="space-y-3 font-serif text-sm">
      {visibleEvents.length === 0 ? (
        <p className="text-muted-foreground">All events have been removed</p>
      ) : (
        visibleEvents.map((event) => (
          <div
            key={event.id}
            className={cn(
              'relative flex gap-3 p-3 rounded border border-gray-200 dark:border-gray-700 group',
              isEditing && 'hover:border-red-300 dark:hover:border-red-700'
            )}
            data-testid={`timeline-event-${event.id}`}
          >
            {/* Date column */}
            <div className="flex items-start gap-2 shrink-0 w-28">
              <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
              <span className="text-muted-foreground">{formatDate(event.eventDate)}</span>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <span
                className={cn(
                  'inline-block px-2 py-0.5 text-xs rounded capitalize mb-1',
                  event.eventType === 'order' && 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
                  event.eventType === 'filing' && 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
                  event.eventType === 'hearing' && 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
                  event.eventType === 'notice' && 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
                  event.eventType === 'transaction' && 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
                  event.eventType === 'deadline' && 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                )}
              >
                {event.eventType}
              </span>
              <p className="text-gray-700 dark:text-gray-300">{event.description}</p>
              {event.entities && event.entities.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  Involves: {event.entities.map((e) => e.canonicalName).join(', ')}
                </p>
              )}
            </div>

            {/* Remove button (edit mode only) */}
            {isEditing && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                onClick={() => onRemoveItem(event.id)}
                aria-label={`Remove event: ${event.description.slice(0, 50)}`}
              >
                <X className="h-4 w-4 text-red-500" />
              </Button>
            )}
          </div>
        ))
      )}

      {/* Removed events (edit mode only) */}
      {isEditing && removedEvents.length > 0 && (
        <div className="mt-4 pt-4 border-t border-dashed">
          <h4 className="text-sm font-medium text-muted-foreground mb-2">Removed Events:</h4>
          {removedEvents.map((event) => (
            <div
              key={event.id}
              className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded opacity-60"
            >
              <span className="flex-1 text-sm line-through">{event.description.slice(0, 60)}...</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-1"
                onClick={() => onRestoreItem(event.id)}
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
