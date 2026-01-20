import { SummaryContent } from '@/components/features/summary';

interface SummaryPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Summary Tab Page
 *
 * Displays the complete matter summary including:
 * - Attention banner with items needing action
 * - Parties section (Petitioner/Respondent)
 * - Subject matter description
 * - Current status of proceedings
 * - Key issues identified
 * - Matter statistics with verification progress
 *
 * Story 10B.1: Summary Tab Content
 */
export default async function SummaryPage({ params }: SummaryPageProps) {
  const { matterId } = await params;

  return (
    <div
      className="w-full max-w-full px-4 sm:px-6 lg:px-8 py-8 overflow-x-hidden"
      id="tabpanel-summary"
      role="tabpanel"
      aria-labelledby="tab-summary"
    >
      <SummaryContent matterId={matterId} />
    </div>
  );
}
