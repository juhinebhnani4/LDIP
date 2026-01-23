/**
 * Processing Skeleton Components
 *
 * Skeleton loaders for document processing views to improve perceived performance.
 * Shows users immediately that content is loading while processing happens.
 */

import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { cn } from '@/lib/utils';

/**
 * Skeleton for individual document card during processing
 */
export function DocumentCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-5 w-20" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Progress bar skeleton */}
        <Skeleton className="h-2 w-full" />
        {/* Stage text */}
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-16" />
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for processing queue list
 */
export function ProcessingQueueSkeleton({
  count = 3,
  className,
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <DocumentCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for entity panel while entities are being extracted
 */
export function EntityPanelSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-4 p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-8 w-24" />
      </div>

      {/* Search bar */}
      <Skeleton className="h-10 w-full" />

      {/* Entity list */}
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-8 w-8 rounded-full" />
            <div className="flex-1 space-y-1">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-20" />
            </div>
            <Skeleton className="h-5 w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for citation list while citations are being extracted
 */
export function CitationListSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-3 p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-5 w-16" />
      </div>

      {/* Citation items */}
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="p-3">
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-3 w-16" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Skeleton for timeline view while dates are being extracted
 */
export function TimelineSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-4 p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-8 w-32" />
      </div>

      {/* Timeline items */}
      <div className="relative pl-8">
        {/* Vertical line */}
        <div className="absolute left-3 top-0 h-full w-0.5 bg-muted" />

        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="relative mb-6 pb-2">
            {/* Dot */}
            <div className="absolute -left-5 top-1.5 h-3 w-3 rounded-full bg-muted" />

            {/* Content */}
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for document viewer sidebar while features load
 */
export function DocumentSidebarSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-6 p-4', className)}>
      {/* Document info */}
      <div className="space-y-2">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-24" />
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2">
        <div className="space-y-1">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-3 w-12" />
        </div>
        <div className="space-y-1">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-3 w-12" />
        </div>
        <div className="space-y-1">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-3 w-12" />
        </div>
      </div>

      {/* Processing stages */}
      <div className="space-y-2">
        <Skeleton className="h-5 w-32" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <Skeleton className="h-4 w-4 rounded-full" />
            <Skeleton className="h-4 w-24" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Inline processing indicator for feature sections
 */
export function FeatureProcessingSkeleton({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-sm text-muted-foreground',
        className
      )}
    >
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      <span>{label}</span>
    </div>
  );
}

/**
 * Full-page processing overlay skeleton
 */
export function ProcessingOverlaySkeleton({
  stage,
  progress,
  className,
}: {
  stage?: string;
  progress?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-4 p-8',
        className
      )}
    >
      {/* Spinner */}
      <div className="h-12 w-12 animate-spin rounded-full border-4 border-muted border-t-primary" />

      {/* Stage info */}
      {stage && (
        <div className="text-center">
          <p className="text-sm font-medium">{stage}</p>
          {progress !== undefined && (
            <p className="text-xs text-muted-foreground">{progress}% complete</p>
          )}
        </div>
      )}

      {/* Progress bar */}
      {progress !== undefined && (
        <div className="h-2 w-64 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
