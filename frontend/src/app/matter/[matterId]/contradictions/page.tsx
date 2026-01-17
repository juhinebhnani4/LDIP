import { ContradictionsContent } from '@/components/features/contradiction';

interface ContradictionsPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Contradictions Tab Page
 *
 * Displays detected contradictions with severity scoring and explanations,
 * grouped by entity for easy review.
 *
 * Story 14.13: Contradictions Tab UI Completion
 * Task 8: Update Contradictions page
 */
export default async function ContradictionsPage({ params }: ContradictionsPageProps) {
  const { matterId } = await params;

  return (
    <div
      className="w-full h-full px-4 sm:px-6 lg:px-8 py-6 overflow-auto"
      id="tabpanel-contradictions"
      role="tabpanel"
      aria-labelledby="tab-contradictions"
    >
      <ContradictionsContent matterId={matterId} />
    </div>
  );
}
