import { redirect } from 'next/navigation';

interface MatterPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Matter Page Redirect
 *
 * Redirects from /matters/[matterId] to /matters/[matterId]/summary
 *
 * Story 10A.2: Tab Bar Navigation
 */
export default async function MatterPage({ params }: MatterPageProps) {
  const { matterId } = await params;

  // Redirect to summary tab (default tab)
  redirect(`/matters/${matterId}/summary`);
}
