import { Users } from 'lucide-react';

interface EntitiesPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Entities Tab Placeholder Page
 *
 * Will show MIG graph visualization and entity detail panels with merge functionality.
 *
 * Story 10A.2: Tab Bar Navigation (placeholder)
 * Implementation: Epic 10C
 */
export default async function EntitiesPage({ params }: EntitiesPageProps) {
  const { matterId } = await params;

  return (
    <div className="container py-8" id="tabpanel-entities" role="tabpanel" aria-labelledby="tab-entities">
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <Users className="h-16 w-16 text-muted-foreground mb-4" aria-hidden="true" />
        <h1 className="text-2xl font-semibold mb-2">Entities</h1>
        <p className="text-muted-foreground max-w-md">
          The Entities tab will show the Matter Intelligence Graph (MIG) with
          entity relationships, detail panels, and alias merge functionality.
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
