import { CitationsContent } from '@/components/features/citation';

interface CitationsPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Citations Tab Page
 *
 * Displays Act discovery results with split view for source document display
 * and citation highlighting.
 *
 * Story 10A.2: Tab Bar Navigation
 * Story 10C.5: Citations Tab UI Completion
 */
export default async function CitationsPage({ params }: CitationsPageProps) {
  const { matterId } = await params;

  return (
    <div
      className="w-full max-w-full px-4 sm:px-6 lg:px-8 py-6 overflow-x-hidden"
      id="tabpanel-citations"
      role="tabpanel"
      aria-labelledby="tab-citations"
    >
      <CitationsContent matterId={matterId} />
    </div>
  );
}
