/**
 * Verification Queue Page Route
 *
 * Story 8-5: Implement Verification Queue UI
 * Task 11: Navigation Integration
 */

import { VerificationPage } from '@/components/features/verification';

interface VerificationPageRouteProps {
  params: Promise<{ matterId: string }>;
}

export default async function VerificationPageRoute({
  params,
}: VerificationPageRouteProps) {
  const { matterId } = await params;

  return <VerificationPage matterId={matterId} />;
}
