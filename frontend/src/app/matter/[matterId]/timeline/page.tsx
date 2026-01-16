import { TimelineContent } from '@/components/features/timeline';
import { TooltipProvider } from '@/components/ui/tooltip';

interface TimelinePageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Timeline Tab Page
 *
 * Displays chronological vertical list of events with:
 * - Event count and date range header
 * - Event cards with type icons, dates, descriptions
 * - Actor links to Entities tab
 * - Source document links
 * - Verification status badges
 * - Connector lines with duration between events
 * - Gap detection for significant delays
 *
 * Story 10B.3: Timeline Tab Vertical List View
 */
export default async function TimelinePage({ params }: TimelinePageProps) {
  // Wait for params (Next.js 15 async params)
  await params;

  return (
    <TooltipProvider>
      <div className="container py-6">
        <TimelineContent />
      </div>
    </TooltipProvider>
  );
}
