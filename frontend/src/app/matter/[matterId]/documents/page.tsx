import { DocumentsContent } from '@/components/features/document/DocumentsContent';

interface DocumentsPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Documents Tab Page
 *
 * Displays the document list for a matter with upload functionality.
 *
 * Story 10D.3: Documents Tab File List
 * Task 5: Update documents page to use DocumentsContent
 */
export default async function DocumentsPage({ params }: DocumentsPageProps) {
  const { matterId } = await params;

  return (
    <div
      className="container py-8"
      id="tabpanel-documents"
      role="tabpanel"
      aria-labelledby="tab-documents"
    >
      <DocumentsContent matterId={matterId} />
    </div>
  );
}
