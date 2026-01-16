import { TimelineContentSkeleton } from '@/components/features/timeline';

/**
 * Timeline Loading Component
 *
 * Suspense boundary loading state for Timeline tab.
 *
 * Story 10B.3: Timeline Tab Vertical List View
 */
export default function TimelineLoading() {
  return (
    <div className="container py-6">
      <TimelineContentSkeleton />
    </div>
  );
}
