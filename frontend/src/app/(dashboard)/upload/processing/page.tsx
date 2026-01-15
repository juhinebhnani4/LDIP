'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useUploadWizardStore } from '@/stores/uploadWizardStore';

/**
 * Upload Processing Page (Placeholder)
 *
 * This page will be fully implemented in Story 9-5 (Upload Stage 3-4).
 * For now, it shows a placeholder indicating upload is in progress.
 */

export default function ProcessingPage() {
  const matterName = useUploadWizardStore((state) => state.matterName);
  const fileCount = useUploadWizardStore((state) => state.files.length);
  const reset = useUploadWizardStore((state) => state.reset);

  // If no files in store, redirect back
  useEffect(() => {
    if (fileCount === 0) {
      // Reset and let user start fresh
      reset();
    }
  }, [fileCount, reset]);

  if (fileCount === 0) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No files to process</p>
          <Button asChild>
            <Link href="/upload">Start New Upload</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header with back navigation */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" />
            Back to Dashboard
          </Link>
        </div>
      </header>

      {/* Main content - Placeholder */}
      <main className="container mx-auto px-4 py-16 max-w-md text-center">
        <div className="flex flex-col items-center gap-6">
          <Loader2 className="size-12 text-primary animate-spin" />

          <div>
            <h1 className="text-xl font-semibold mb-2">Processing Your Files</h1>
            <p className="text-muted-foreground">
              Uploading {fileCount} {fileCount === 1 ? 'file' : 'files'} to{' '}
              <strong>{matterName}</strong>
            </p>
          </div>

          <div className="bg-muted/50 rounded-lg p-4 text-sm text-muted-foreground">
            <p>
              <strong>Coming Soon:</strong> This page will show detailed upload progress,
              OCR processing status, and timeline analysis.
            </p>
            <p className="mt-2">
              (Story 9-5 & 9-6 implementation)
            </p>
          </div>

          <Button variant="outline" asChild className="mt-4">
            <Link href="/" onClick={() => reset()}>
              Return to Dashboard
            </Link>
          </Button>
        </div>
      </main>
    </div>
  );
}
