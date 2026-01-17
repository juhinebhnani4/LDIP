import { Skeleton } from '@/components/ui/skeleton';

/**
 * Citations Loading Component
 *
 * Suspense boundary loading state for Citations tab.
 *
 * Story 10C.5: Citations Tab UI Completion
 */
export default function CitationsLoading() {
  return (
    <div className="w-full max-w-full px-4 sm:px-6 lg:px-8 py-6 overflow-x-hidden">
      <div className="flex flex-col h-full space-y-4">
        {/* Header skeleton */}
        <Skeleton className="h-24 w-full" />
        {/* Attention banner skeleton */}
        <Skeleton className="h-16 w-full" />
        {/* Content skeleton */}
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}
