import { Clock } from 'lucide-react';

interface TimelinePageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Timeline Tab Placeholder Page
 *
 * Will show vertical event list and horizontal multi-track timeline views.
 *
 * Story 10A.2: Tab Bar Navigation (placeholder)
 * Implementation: Epic 10B
 */
export default async function TimelinePage({ params }: TimelinePageProps) {
  const { matterId } = await params;

  return (
    <div className="container py-8" id="tabpanel-timeline" role="tabpanel" aria-labelledby="tab-timeline">
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <Clock className="h-16 w-16 text-muted-foreground mb-4" aria-hidden="true" />
        <h1 className="text-2xl font-semibold mb-2">Timeline</h1>
        <p className="text-muted-foreground max-w-md">
          The Timeline tab will show events in vertical list and horizontal
          multi-track views with filtering and manual event creation.
        </p>
        <p className="text-sm text-muted-foreground mt-4">
          Coming in Epic 10B
        </p>
        <p className="text-xs text-muted-foreground/70 mt-2">
          Matter ID: {matterId}
        </p>
      </div>
    </div>
  );
}
