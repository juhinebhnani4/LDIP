'use client';

import Link from 'next/link';
import { CheckCircle2, AlertTriangle, Clock, FileText, ArrowRight, Zap, TestTube } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Checkbox } from '@/components/ui/checkbox';
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
  /** Whether selection mode is active */
  selectionMode?: boolean;
  /** Whether this card is selected */
  isSelected?: boolean;
  /** Callback when selection changes */
  onSelectChange?: (checked: boolean) => void;
  /** Whether this matter can be deleted (owner only) */
  canDelete?: boolean;
}

// Time constants for readability
const MS_PER_MINUTE = 60000;
const MINUTES_PER_HOUR = 60;
const HOURS_PER_DAY = 24;
const SECONDS_PER_MINUTE = 60;

/** Format relative time for last opened */
function formatRelativeTime(isoDate: string | undefined): string {
  if (!isoDate) return 'Never opened';

  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / MS_PER_MINUTE);
  const diffHours = Math.floor(diffMins / MINUTES_PER_HOUR);
  const diffDays = Math.floor(diffHours / HOURS_PER_DAY);

  if (diffMins < 1) return 'Just now';
  if (diffMins < MINUTES_PER_HOUR) return `${diffMins}m ago`;
  if (diffHours < HOURS_PER_DAY) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

/** Format estimated time remaining */
function formatTimeRemaining(seconds: number | undefined): string {
  if (!seconds) return '';
  const mins = Math.ceil(seconds / SECONDS_PER_MINUTE);
  if (mins < MINUTES_PER_HOUR) return `Est. ${mins} min left`;
  const hours = Math.floor(mins / MINUTES_PER_HOUR);
  const remainingMins = mins % MINUTES_PER_HOUR;
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
        <Badge variant="default" className="gap-1 bg-[var(--success)]" aria-label="Ready status">
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
  const isQuickScan = matter.analysisMode === 'quick_scan';
  const isSampleCase = matter.practiceGroup === '_sample_case';

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
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge status={matter.processingStatus} />
          {/* Story 6.4 AC 6.4.5: Quick badge for quick_scan mode */}
          {isQuickScan && (
            <Badge variant="outline" className="gap-1 text-xs" aria-label="Quick scan mode">
              <Zap className="size-3" />
              Quick
            </Badge>
          )}
          {/* Story 6.3 AC 6.3.7: Sample badge for sample case */}
          {isSampleCase && (
            <Badge variant="secondary" className="gap-1 text-xs" aria-label="Sample case">
              <TestTube className="size-3" />
              Sample
            </Badge>
          )}
        </div>
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
      <Button variant="outline" className="w-full mt-2" asChild data-testid="matter-card-view-progress-button">
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
  const isQuickScan = matter.analysisMode === 'quick_scan';
  const isSampleCase = matter.practiceGroup === '_sample_case';

  return (
    <>
      {/* Status and mode badges at top */}
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge status={matter.processingStatus} />
        {/* Story 6.4 AC 6.4.5: Quick badge for quick_scan mode */}
        {isQuickScan && (
          <Badge variant="outline" className="gap-1 text-xs" aria-label="Quick scan mode">
            <Zap className="size-3" />
            Quick
          </Badge>
        )}
        {/* Story 6.3 AC 6.3.7: Sample badge for sample case */}
        {isSampleCase && (
          <Badge variant="secondary" className="gap-1 text-xs" aria-label="Sample case">
            <TestTube className="size-3" />
            Sample
          </Badge>
        )}
      </div>

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
              ? 'border-[var(--success)]/30 bg-[var(--success)]/10 dark:border-[var(--success)]/40 dark:bg-[var(--success)]/20'
              : matter.verificationPercent >= 70
                ? 'border-[var(--warning)]/30 bg-[var(--warning)]/10 dark:border-[var(--warning)]/40 dark:bg-[var(--warning)]/20'
                : 'border-destructive/30 bg-destructive/10 dark:border-destructive/40 dark:bg-destructive/20'
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
              ? 'border-[var(--success)]/30 bg-[var(--success)]/10 dark:border-[var(--success)]/40 dark:bg-[var(--success)]/20'
              : 'border-[var(--warning)]/30 bg-[var(--warning)]/10 dark:border-[var(--warning)]/40 dark:bg-[var(--warning)]/20'
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
      <Button className="w-full mt-2" asChild data-testid="matter-card-resume-button">
        <Link href={`/matter/${matter.id}`}>
          Resume
          <ArrowRight className="size-4 ml-1" />
        </Link>
      </Button>
    </>
  );
}

export function MatterCard({
  matter,
  className,
  selectionMode = false,
  isSelected = false,
  onSelectChange,
  canDelete = true,
}: MatterCardProps) {
  const isProcessing = matter.processingStatus === 'processing';

  const handleCheckboxChange = (checked: boolean | 'indeterminate') => {
    if (onSelectChange && checked !== 'indeterminate') {
      onSelectChange(checked);
    }
  };

  return (
    <Card
      className={cn(
        'hover:shadow-md transition-shadow relative',
        isSelected && 'ring-2 ring-primary bg-primary/5',
        className
      )}
      role="article"
      aria-label={`Matter: ${matter.title}`}
      aria-selected={selectionMode ? isSelected : undefined}
      data-testid={`matter-card-${matter.id}`}
    >
      {/* Selection checkbox - visible in selection mode */}
      {selectionMode && canDelete && (
        <div className="absolute top-3 right-3 z-10">
          <Checkbox
            checked={isSelected}
            onCheckedChange={handleCheckboxChange}
            aria-label={`Select ${matter.title}`}
            className="h-5 w-5 border-2"
            data-testid={`matter-card-checkbox-${matter.id}`}
          />
        </div>
      )}
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
