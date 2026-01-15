/**
 * Verification Tab Page
 *
 * Displays the verification queue for reviewing AI findings:
 * - Statistics header with verification progress
 * - Filter controls for finding types and confidence tiers
 * - DataTable queue with all pending verifications
 * - Bulk actions toolbar for multi-select operations
 * - Notes dialog for reject/flag actions
 *
 * Story 8-5: Implement Verification Queue UI
 * Story 10D.1: Verification Tab Queue (DataTable)
 */

import { VerificationContent } from '@/components/features/verification';

interface VerificationPageProps {
  params: Promise<{ matterId: string }>;
}

export default async function VerificationPage({ params }: VerificationPageProps) {
  const { matterId } = await params;

  return (
    <div
      className="container py-8"
      id="tabpanel-verification"
      role="tabpanel"
      aria-labelledby="tab-verification"
    >
      <VerificationContent matterId={matterId} />
    </div>
  );
}
