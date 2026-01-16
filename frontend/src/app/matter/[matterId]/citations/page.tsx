import { Quote } from 'lucide-react';

interface CitationsPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Citations Tab Placeholder Page
 *
 * Will show Act discovery results with split view for citation highlighting.
 *
 * Story 10A.2: Tab Bar Navigation (placeholder)
 * Implementation: Epic 10C
 */
export default async function CitationsPage({ params }: CitationsPageProps) {
  const { matterId } = await params;

  return (
    <div className="container py-8" id="tabpanel-citations" role="tabpanel" aria-labelledby="tab-citations">
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <Quote className="h-16 w-16 text-muted-foreground mb-4" aria-hidden="true" />
        <h1 className="text-2xl font-semibold mb-2">Citations</h1>
        <p className="text-muted-foreground max-w-md">
          The Citations tab will show Act discovery results with a split view
          for source document display and citation highlighting.
        </p>
        <p className="text-sm text-muted-foreground mt-4">
          Coming in Epic 10C
        </p>
        <p className="text-xs text-muted-foreground/70 mt-2">
          Matter ID: {matterId}
        </p>
      </div>
    </div>
  );
}
