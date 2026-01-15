import { EntitiesContent } from '@/components/features/entities/EntitiesContent';

interface EntitiesPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Entities Tab Page
 *
 * Displays the MIG graph visualization with entity relationships and detail panels.
 *
 * @see Story 10C.1 - Entities Tab MIG Graph Visualization
 */
export default async function EntitiesPage({ params }: EntitiesPageProps) {
  const { matterId } = await params;

  return (
    <div
      className="container py-6 h-[calc(100vh-12rem)]"
      id="tabpanel-entities"
      role="tabpanel"
      aria-labelledby="tab-entities"
    >
      <EntitiesContent matterId={matterId} className="h-full" />
    </div>
  );
}
