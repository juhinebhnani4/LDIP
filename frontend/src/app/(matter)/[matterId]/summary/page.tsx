import { FileText } from 'lucide-react';

interface SummaryPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Summary Tab Placeholder Page
 *
 * Will show case overview, attention items, parties, subject matter, and key issues.
 *
 * Story 10A.2: Tab Bar Navigation (placeholder)
 * Implementation: Epic 10B
 */
export default async function SummaryPage({ params }: SummaryPageProps) {
  const { matterId } = await params;

  return (
    <div className="container py-8" id="tabpanel-summary" role="tabpanel" aria-labelledby="tab-summary">
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <FileText className="h-16 w-16 text-muted-foreground mb-4" aria-hidden="true" />
        <h1 className="text-2xl font-semibold mb-2">Summary</h1>
        <p className="text-muted-foreground max-w-md">
          The Summary tab will show case overview, attention items, parties,
          subject matter, and key issues.
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
