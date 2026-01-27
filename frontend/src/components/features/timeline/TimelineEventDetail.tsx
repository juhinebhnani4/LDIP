'use client';

/**
 * Timeline Event Detail Component
 *
 * Compact detail panel displayed below horizontal/multi-track timeline
 * when an event is selected. Shows event information with navigation actions.
 *
 * Story 10B.4: Timeline Tab Alternative Views (AC #2, #3)
 */

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { format, parseISO } from 'date-fns';
import { X, List, ExternalLink, User, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import {
  EVENT_TYPE_ICONS,
  EVENT_TYPE_LABELS,
  EVENT_TYPE_COLORS,
} from './eventTypeIcons';
import type { TimelineEvent } from '@/types/timeline';
import type { TimelineEventContext } from '@/types/crossEngine';

interface TimelineEventDetailProps {
  /** Selected event */
  event: TimelineEvent;
  /** Callback to close/deselect */
  onClose: () => void;
  /** Callback to switch to list view at this event */
  onViewInList?: () => void;
  /** Cross-engine context data (Gap 5-3) */
  crossEngineContext?: TimelineEventContext | null;
  /** Whether cross-engine data is loading */
  crossEngineLoading?: boolean;
  /** Optional className */
  className?: string;
}

/**
 * Format event date for detail display
 */
function formatDetailDate(
  dateStr: string,
  precision: TimelineEvent['eventDatePrecision']
): string {
  try {
    const date = parseISO(dateStr);
    switch (precision) {
      case 'day':
        return format(date, 'EEEE, MMMM d, yyyy');
      case 'month':
        return format(date, 'MMMM yyyy');
      case 'year':
        return format(date, 'yyyy');
      case 'approximate':
        return `Approximately ${format(date, 'MMMM d, yyyy')}`;
      default:
        return format(date, 'MMMM d, yyyy');
    }
  } catch {
    return dateStr;
  }
}

export function TimelineEventDetail({
  event,
  onClose,
  onViewInList,
  crossEngineContext,
  crossEngineLoading = false,
  className,
}: TimelineEventDetailProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // Access static constants directly
  const Icon = EVENT_TYPE_ICONS[event.eventType] ?? EVENT_TYPE_ICONS.unclassified;
  const typeLabel = EVENT_TYPE_LABELS[event.eventType] ?? EVENT_TYPE_LABELS.unclassified;
  const typeColor = EVENT_TYPE_COLORS[event.eventType] ?? EVENT_TYPE_COLORS.unclassified;

  const formattedDate = formatDetailDate(event.eventDate, event.eventDatePrecision);

  return (
    <Card
      className={cn('relative', className)}
      role="region"
      aria-label="Selected event details"
    >
      <CardContent className="pt-4 pb-4">
        {/* Close button */}
        <Button
          variant="ghost"
          size="icon"
          className="absolute top-2 right-2 h-8 w-8"
          onClick={onClose}
          aria-label="Close event details"
        >
          <X className="h-4 w-4" />
        </Button>

        {/* Header: Icon, Type, Date */}
        <div className="flex items-start gap-3 mb-3 pr-10">
          {/* Type icon circle */}
          <div
            className={cn(
              'flex items-center justify-center w-10 h-10 rounded-full shrink-0',
              typeColor.replace('text-', 'bg-').split(' ')[0],
              'bg-opacity-20'
            )}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
          </div>

          <div className="flex-1 min-w-0">
            {/* Type badge and status */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <Badge
                variant="secondary"
                className={cn('flex items-center gap-1', typeColor)}
              >
                <span>{typeLabel.toUpperCase()}</span>
              </Badge>

              {event.isVerified && (
                <Badge
                  variant="outline"
                  className="text-green-600 border-green-500 dark:text-green-400 dark:border-green-600"
                >
                  <CheckCircle2 className="h-3 w-3 mr-1" aria-hidden="true" />
                  Verified
                </Badge>
              )}

              {event.hasContradiction && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge
                      variant="outline"
                      className="text-amber-600 border-amber-500 cursor-help dark:text-amber-400 dark:border-amber-600"
                    >
                      <AlertTriangle className="h-3 w-3 mr-1" aria-hidden="true" />
                      Contradiction
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    {event.contradictionDetails ?? 'This event has conflicting information'}
                  </TooltipContent>
                </Tooltip>
              )}
            </div>

            {/* Date */}
            <p className="text-sm text-muted-foreground">{formattedDate}</p>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-foreground mb-3">{event.description}</p>

        {/* Actors */}
        {event.entities.length > 0 && (
          <div className="flex items-start gap-2 mb-3 text-sm">
            <User
              className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0"
              aria-hidden="true"
            />
            <div className="flex flex-wrap items-center gap-x-1">
              <span className="text-muted-foreground">Actor:</span>
              {event.entities.map((entity, idx) => (
                <span key={entity.entityId}>
                  <Link
                    href={`/matter/${matterId}/entities?entity=${entity.entityId}`}
                    className="text-blue-600 hover:text-blue-800 hover:underline dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    {entity.canonicalName}
                  </Link>
                  {entity.role && (
                    <span className="text-muted-foreground"> ({entity.role})</span>
                  )}
                  {idx < event.entities.length - 1 && ', '}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Cross-Engine Links (Gap 5-3) */}
        {crossEngineContext && crossEngineContext.relatedContradictions.length > 0 && (
          <div className="flex items-start gap-2 mb-3 text-sm">
            <AlertTriangle
              className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0"
              aria-hidden="true"
            />
            <div className="flex flex-col gap-1">
              <span className="text-muted-foreground">
                Related Contradictions ({crossEngineContext.relatedContradictions.length}):
              </span>
              {crossEngineContext.relatedContradictions.slice(0, 3).map((c) => (
                <Link
                  key={c.contradictionId}
                  href={`/matter/${matterId}/contradictions?contradiction=${c.contradictionId}`}
                  className={cn(
                    'text-xs hover:underline',
                    c.severity === 'high'
                      ? 'text-red-600 dark:text-red-400'
                      : c.severity === 'medium'
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-muted-foreground'
                  )}
                >
                  <Badge
                    variant={c.severity === 'high' ? 'destructive' : 'outline'}
                    className="mr-1 text-[10px] px-1 py-0"
                  >
                    {c.severity}
                  </Badge>
                  {c.explanation.slice(0, 80)}
                  {c.explanation.length > 80 ? '...' : ''}
                </Link>
              ))}
              {crossEngineContext.relatedContradictions.length > 3 && (
                <Link
                  href={`/matter/${matterId}/contradictions?entity=${crossEngineContext.entities[0]?.entityId ?? ''}`}
                  className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                >
                  View all {crossEngineContext.relatedContradictions.length} contradictions
                </Link>
              )}
            </div>
          </div>
        )}

        {crossEngineLoading && (
          <div className="text-xs text-muted-foreground mb-3">
            Loading related data...
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t">
          {/* View in List */}
          {onViewInList && (
            <Button
              variant="outline"
              size="sm"
              onClick={onViewInList}
              className="gap-1.5"
            >
              <List className="h-4 w-4" aria-hidden="true" />
              View in List
            </Button>
          )}

          {/* View Source */}
          {event.documentId && (
            <Button variant="outline" size="sm" asChild className="gap-1.5">
              <Link
                href={`/matter/${matterId}/documents?doc=${event.documentId}${event.sourcePage ? `&page=${event.sourcePage}` : ''}`}
              >
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                View Source
                {event.sourcePage && ` (pg ${event.sourcePage})`}
              </Link>
            </Button>
          )}
        </div>

        {/* Low confidence warning */}
        {event.confidence < 0.7 && !event.isVerified && (
          <div className="mt-3 text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" aria-hidden="true" />
            Low confidence ({Math.round(event.confidence * 100)}%) - needs verification
          </div>
        )}
      </CardContent>
    </Card>
  );
}
