'use client';

import Link from 'next/link';
import { CheckCircle2, AlertTriangle, Clock, FileText, ArrowRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import type { MatterCardData } from '@/types/matter';

/**
 * Matter Card Component
 *
 * Displays a matter as a card with status information.
 * Has two variants: ready state and processing state.
 *
 * UX Layout from Story 9-2:
 * Processing State:
 * ┌────────────────────┐
 * │  ████████░░░ 67%   │
 * │  SEBI v. Parekh    │
 * │  Processing...     │
 * │  Est. 3 min left   │
 * │  89 documents      │
 * │  2,100 pages       │
 * │  [View Progress →] │
 * └────────────────────┘
 *
 * Ready State:
 * ┌────────────────────┐
 * │  ✓ Ready           │
 * │  Shah v. Mehta     │
 * │  1,247 pages       │
 * │  Last opened: 2h   │
 * │  ┌────┐ ┌────┐     │
 * │  │85% │ │ 3  │     │
 * │  │ ✓  │ │ ⚠️ │     │
 * │  └────┘ └────┘     │
 * │  Verified  Issues  │
 * │  [Resume →]        │
 * └────────────────────┘
 */

interface MatterCardProps {
  /** Matter data to display */
  matter: MatterCardData;
  /** Optional className for styling */
  className?: string;
}

/** Format relative time for last opened */
function formatRelativeTime(isoDate: string | undefined): string {
  if (!isoDate) return 'Never opened';

  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

/** Format estimated time remaining */
function formatTimeRemaining(seconds: number | undefined): string {
  if (!seconds) return '';
  const mins = Math.ceil(seconds / 60);
  if (mins < 60) return `Est. ${mins} min left`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return `Est. ${hours}h ${remainingMins}m left`;
}

/** Status badge component */
function StatusBadge({ status }: { status: MatterCardData['processingStatus'] }) {
  switch (status) {
    case 'processing':
      return (
        <Badge variant="secondary" className="gap-1" aria-label="Processing status">
          <Clock className="size-3" />
          Processing
        </Badge>
      );
    case 'ready':
      return (
        <Badge variant="default" className="gap-1 bg-green-600" aria-label="Ready status">
          <CheckCircle2 className="size-3" />
          Ready
        </Badge>
      );
    case 'needs_attention':
      return (
        <Badge variant="destructive" className="gap-1" aria-label="Needs attention status">
          <AlertTriangle className="size-3" />
          Needs Attention
        </Badge>
      );
  }
}

/** Processing state card content */
function ProcessingContent({ matter }: { matter: MatterCardData }) {
  return (
    <>
      {/* Progress bar at top */}
      <div className="space-y-1">
        <Progress value={matter.processingProgress ?? 0} className="h-2" />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{matter.processingProgress ?? 0}% complete</span>
          <span>{formatTimeRemaining(matter.estimatedTimeRemaining)}</span>
        </div>
      </div>

      {/* Matter title */}
      <div className="space-y-1">
        <h3 className="font-semibold text-lg leading-tight line-clamp-2">{matter.title}</h3>
        <StatusBadge status={matter.processingStatus} />
      </div>

      {/* Document/page counts */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <FileText className="size-4" />
          <span>{matter.documentCount} documents</span>
        </div>
      </div>
      <div className="text-sm text-muted-foreground">
        {matter.pageCount.toLocaleString()} pages
      </div>

      {/* Action button */}
      <Button variant="outline" className="w-full mt-2" asChild>
        <Link href={`/matter/${matter.id}`}>
          View Progress
          <ArrowRight className="size-4 ml-1" />
        </Link>
      </Button>
    </>
  );
}

/** Ready/Needs attention state card content */
function ReadyContent({ matter }: { matter: MatterCardData }) {
  return (
    <>
      {/* Status badge at top */}
      <StatusBadge status={matter.processingStatus} />

      {/* Matter title */}
      <h3 className="font-semibold text-lg leading-tight line-clamp-2">{matter.title}</h3>

      {/* Page count and last opened */}
      <div className="space-y-1 text-sm text-muted-foreground">
        <div>{matter.pageCount.toLocaleString()} pages</div>
        <div>Last opened: {formatRelativeTime(matter.lastOpened)}</div>
      </div>

      {/* Verification % and Issues indicators */}
      <div className="flex gap-3">
        {/* Verification percentage */}
        <div
          className={cn(
            'flex-1 rounded-md border p-2 text-center',
            matter.verificationPercent >= 90
              ? 'border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950'
              : matter.verificationPercent >= 70
                ? 'border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950'
                : 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950'
          )}
        >
          <div className="text-lg font-bold">{matter.verificationPercent}%</div>
          <div className="text-xs text-muted-foreground flex items-center justify-center gap-1">
            <CheckCircle2 className="size-3" />
            Verified
          </div>
        </div>

        {/* Issue count */}
        <div
          className={cn(
            'flex-1 rounded-md border p-2 text-center',
            matter.issueCount === 0
              ? 'border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950'
              : 'border-orange-200 bg-orange-50 dark:border-orange-900 dark:bg-orange-950'
          )}
        >
          <div className="text-lg font-bold">{matter.issueCount}</div>
          <div className="text-xs text-muted-foreground flex items-center justify-center gap-1">
            <AlertTriangle className="size-3" />
            Issues
          </div>
        </div>
      </div>

      {/* Action button */}
      <Button className="w-full mt-2" asChild>
        <Link href={`/matter/${matter.id}`}>
          Resume
          <ArrowRight className="size-4 ml-1" />
        </Link>
      </Button>
    </>
  );
}

export function MatterCard({ matter, className }: MatterCardProps) {
  const isProcessing = matter.processingStatus === 'processing';

  return (
    <Card
      className={cn('hover:shadow-md transition-shadow', className)}
      role="article"
      aria-label={`Matter: ${matter.title}`}
    >
      <CardContent className="flex flex-col gap-3 pt-4">
        {isProcessing ? (
          <ProcessingContent matter={matter} />
        ) : (
          <ReadyContent matter={matter} />
        )}
      </CardContent>
    </Card>
  );
}
