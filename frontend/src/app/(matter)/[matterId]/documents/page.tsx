import { FolderOpen } from 'lucide-react';

interface DocumentsPageProps {
  params: Promise<{ matterId: string }>;
}

/**
 * Documents Tab Placeholder Page
 *
 * Will show file list with document actions (download, delete, OCR status).
 *
 * Story 10A.2: Tab Bar Navigation (placeholder)
 * Implementation: Epic 10D
 */
export default async function DocumentsPage({ params }: DocumentsPageProps) {
  const { matterId } = await params;

  return (
    <div className="container py-8" id="tabpanel-documents" role="tabpanel" aria-labelledby="tab-documents">
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
        <FolderOpen className="h-16 w-16 text-muted-foreground mb-4" aria-hidden="true" />
        <h1 className="text-2xl font-semibold mb-2">Documents</h1>
        <p className="text-muted-foreground max-w-md">
          The Documents tab will show a file list with document actions
          including download, delete, and OCR status information.
        </p>
        <p className="text-sm text-muted-foreground mt-4">
          Coming in Epic 10D
        </p>
        <p className="text-xs text-muted-foreground/70 mt-2">
          Matter ID: {matterId}
        </p>
      </div>
    </div>
  );
}
