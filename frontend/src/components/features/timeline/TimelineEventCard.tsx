'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { format, parseISO } from 'date-fns';
import {
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  User,
  Pencil,
  Trash2,
  UserCircle,
  MoreVertical,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import {
  EVENT_TYPE_ICONS,
  EVENT_TYPE_LABELS,
  EVENT_TYPE_COLORS,
} from './eventTypeIcons';
import { AnomalyIndicator } from './AnomalyIndicator';
import type { TimelineEvent } from '@/types/timeline';
import type { AnomalyListItem } from '@/hooks/useAnomalies';

/**
 * Timeline Event Card Component
 *
 * Displays a single event in the timeline with:
 * - Date with precision formatting
 * - Event type icon and badge
 * - Description
 * - Actors (entities) with links
 * - Source document link
 * - Verification status
 * - Contradiction flag
 * - Anomaly indicator (Story 14.16)
 * - Edit/Delete actions (for manual events)
 *
 * Story 10B.3: Timeline Tab Vertical List View (AC #2)
 * Story 10B.5: Timeline Filtering and Manual Event Addition (AC #6, #7, #8)
 * Story 14.16: Anomalies UI Integration (AC #1)
 */

interface TimelineEventCardProps {
  /** Event data */
  event: TimelineEvent;
  /** Anomalies affecting this event (Story 14.16) */
  anomalies?: AnomalyListItem[];
  /** Callback when anomaly indicator is clicked */
  onAnomalyClick?: (anomaly: AnomalyListItem) => void;
  /** Callback when edit is clicked */
  onEdit?: (event: TimelineEvent) => void;
  /** Callback when delete is clicked (only for manual events) */
  onDelete?: (event: TimelineEvent) => void;
  /** Callback when source document is clicked - opens in PDF split view */
  onSourceClick?: (event: TimelineEvent) => void;
  /** Optional className */
  className?: string;
}

/**
 * Format event date based on precision
 */
function formatEventDate(
  dateStr: string,
  precision: TimelineEvent['eventDatePrecision']
): string {
  try {
    const date = parseISO(dateStr);
    switch (precision) {
      case 'day':
        return format(date, 'MMMM d, yyyy');
      case 'month':
        return format(date, 'MMMM yyyy');
      case 'year':
        return format(date, 'yyyy');
      case 'approximate':
        return `~${format(date, 'MMMM d, yyyy')}`;
      default:
        return format(date, 'MMMM d, yyyy');
    }
  } catch {
    return dateStr;
  }
}

export function TimelineEventCard({
  event,
  anomalies = [],
  onAnomalyClick,
  onEdit,
  onDelete,
  onSourceClick,
  className,
}: TimelineEventCardProps) {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  // Access static constants directly to avoid "component created during render" lint error
  const Icon = EVENT_TYPE_ICONS[event.eventType] ?? EVENT_TYPE_ICONS.unclassified;
  const typeLabel = EVENT_TYPE_LABELS[event.eventType] ?? EVENT_TYPE_LABELS.unclassified;
  const typeColor = EVENT_TYPE_COLORS[event.eventType] ?? EVENT_TYPE_COLORS.unclassified;

  const formattedDate = formatEventDate(event.eventDate, event.eventDatePrecision);
  const isManual = event.isManual === true;
  const hasAnomalies = anomalies.length > 0;

  return (
    <Card
      className={cn(
        'relative',
        hasAnomalies && 'border-orange-200 dark:border-orange-800',
        className
      )}
      data-testid={`timeline-event-${event.id}`}
    >
      <CardContent className="pt-4">
        {/* Actions dropdown */}
        {(onEdit || (onDelete && isManual)) && (
          <div className="absolute top-2 right-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0"
                  aria-label="Event actions"
                >
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onEdit && (
                  <DropdownMenuItem onClick={() => onEdit(event)}>
                    <Pencil className="h-4 w-4 mr-2" />
                    {isManual ? 'Edit event' : 'Edit classification'}
                  </DropdownMenuItem>
                )}
                {onDelete && isManual && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => onDelete(event)}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete event
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
        {/* Date */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <span className="font-medium">{formattedDate}</span>
          {event.eventDateText &&
            event.eventDateText !== event.eventDate && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-xs italic cursor-help">
                    ({event.eventDateText})
                  </span>
                </TooltipTrigger>
                <TooltipContent>Original text from document</TooltipContent>
              </Tooltip>
            )}
        </div>

        {/* Event Type Badge + Status Badges */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <Badge
            variant="secondary"
            className={cn('flex items-center gap-1', typeColor)}
          >
            <Icon className="h-3 w-3" aria-hidden="true" />
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
                {event.contradictionDetails ??
                  'This event has conflicting information'}
              </TooltipContent>
            </Tooltip>
          )}

          {isManual && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge
                  variant="outline"
                  className="text-blue-600 border-blue-500 cursor-help dark:text-blue-400 dark:border-blue-600"
                >
                  <UserCircle className="h-3 w-3 mr-1" aria-hidden="true" />
                  Manually added
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                This event was manually added by {event.createdBy ?? 'a user'}
              </TooltipContent>
            </Tooltip>
          )}

          {/* Anomaly Indicator (Story 14.16) */}
          {hasAnomalies && (
            <AnomalyIndicator
              anomalies={anomalies}
              onClick={onAnomalyClick}
              size="sm"
            />
          )}
        </div>

        {/* Description */}
        <p className="text-sm text-foreground mb-3">{event.description}</p>

        {/* Actors (Entities) */}
        {event.entities.length > 0 && (
          <div className="flex items-start gap-2 mb-2 text-sm">
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
                    <span className="text-muted-foreground">
                      {' '}
                      ({entity.role})
                    </span>
                  )}
                  {idx < event.entities.length - 1 && ', '}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Source Document */}
        {event.documentId && (
          <div className="flex items-center gap-2 text-sm">
            <ExternalLink
              className="h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
            <span className="text-muted-foreground">Source:</span>
            {onSourceClick ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => onSourceClick(event)}
                    className={cn(
                      'hover:underline',
                      event.sourcePage
                        ? 'text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300'
                        : 'text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300'
                    )}
                  >
                    {event.sourcePage
                      ? `Document, pg ${event.sourcePage}`
                      : 'Document'}
                    {!event.sourcePage && (
                      <AlertTriangle className="inline-block ml-1 h-3 w-3" aria-hidden="true" />
                    )}
                  </button>
                </TooltipTrigger>
                {!event.sourcePage && (
                  <TooltipContent>
                    <p>Page number unknown - will open to page 1</p>
                  </TooltipContent>
                )}
              </Tooltip>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link
                    href={`/matter/${matterId}/documents?doc=${event.documentId}${event.sourcePage ? `&page=${event.sourcePage}` : ''}`}
                    className={cn(
                      'hover:underline',
                      event.sourcePage
                        ? 'text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300'
                        : 'text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300'
                    )}
                  >
                    {event.sourcePage
                      ? `Document, pg ${event.sourcePage}`
                      : 'Document'}
                    {!event.sourcePage && (
                      <AlertTriangle className="inline-block ml-1 h-3 w-3" aria-hidden="true" />
                    )}
                  </Link>
                </TooltipTrigger>
                {!event.sourcePage && (
                  <TooltipContent>
                    <p>Page number unknown - will open to page 1</p>
                  </TooltipContent>
                )}
              </Tooltip>
            )}
          </div>
        )}

        {/* Cross-references */}
        {event.crossReferences && event.crossReferences.length > 0 && (
          <div className="mt-2 text-sm text-muted-foreground">
            <span>Cross-ref: {event.crossReferences.join(', ')}</span>
          </div>
        )}

        {/* Low confidence warning */}
        {event.confidence < 0.7 && !event.isVerified && (
          <div className="mt-2 text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" aria-hidden="true" />
            Low confidence ({Math.round(event.confidence * 100)}%) - needs
            verification
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Timeline Event Card Skeleton
 */
export function TimelineEventCardSkeleton({
  className,
}: {
  className?: string;
}) {
  return (
    <Card className={cn('relative', className)}>
      <CardContent className="pt-4">
        {/* Date skeleton */}
        <Skeleton className="h-4 w-32 mb-2" />

        {/* Badge skeletons */}
        <div className="flex items-center gap-2 mb-2">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-16" />
        </div>

        {/* Description skeleton */}
        <Skeleton className="h-4 w-full mb-1" />
        <Skeleton className="h-4 w-3/4 mb-3" />

        {/* Actor skeleton */}
        <div className="flex items-center gap-2 mb-2">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-4 w-40" />
        </div>

        {/* Source skeleton */}
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-4 w-28" />
        </div>
      </CardContent>
    </Card>
  );
}
