'use client';

/**
 * ProcessingScreen Component
 *
 * Combined Stage 3-4 screen showing upload and processing progress.
 * Split layout: left panel shows document progress, right panel shows live discoveries.
 * Includes "Continue in Background" button and header with matter name.
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 */

import { useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useUploadWizardStore } from '@/stores/uploadWizardStore';
import { UploadProgressView } from './UploadProgressView';
import { ProcessingProgressView } from './ProcessingProgressView';
import { LiveDiscoveriesPanel } from './LiveDiscoveriesPanel';
import type { UploadProgress } from '@/types/upload';

interface ProcessingScreenProps {
  /** Optional className for the container */
  className?: string;
  /** Callback when user clicks "Continue in Background" */
  onContinueInBackground?: () => void;
}

export function ProcessingScreen({
  className,
  onContinueInBackground,
}: ProcessingScreenProps) {
  const router = useRouter();

  // Use selector pattern for store access
  const matterName = useUploadWizardStore((state) => state.matterName);
  const files = useUploadWizardStore((state) => state.files);
  const uploadProgress = useUploadWizardStore((state) => state.uploadProgress);
  const processingStage = useUploadWizardStore((state) => state.processingStage);
  const overallProgressPct = useUploadWizardStore((state) => state.overallProgressPct);
  const liveDiscoveries = useUploadWizardStore((state) => state.liveDiscoveries);
  const cancelFileUpload = useUploadWizardStore((state) => state.cancelFileUpload);

  // Convert Map to array for components
  const uploadProgressArray = useMemo((): UploadProgress[] => {
    return Array.from(uploadProgress.values());
  }, [uploadProgress]);

  // Determine if we're in upload phase or processing phase
  const isUploadPhase =
    processingStage === null || processingStage === 'UPLOADING';

  // Check if all uploads are complete
  const uploadsComplete = useMemo(() => {
    if (files.length === 0) return false;
    for (const file of files) {
      const progress = uploadProgress.get(file.name);
      if (!progress || progress.status !== 'complete') {
        return false;
      }
    }
    return true;
  }, [files, uploadProgress]);

  // Handle continue in background
  const handleContinueInBackground = useCallback(() => {
    if (onContinueInBackground) {
      onContinueInBackground();
    }
    router.push('/');
  }, [onContinueInBackground, router]);

  // Handle cancel file upload
  const handleCancelFile = useCallback(
    (fileName: string) => {
      cancelFileUpload(fileName);
    },
    [cancelFileUpload]
  );

  return (
    <div className={cn('min-h-screen bg-muted/30', className)}>
      {/* Header */}
      <header className="sticky top-0 z-10 bg-background border-b">
        <div className="container max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="size-4" />
                <span className="hidden sm:inline">Back to Dashboard</span>
              </Link>
            </div>
            <h1 className="text-lg font-semibold truncate max-w-[200px] sm:max-w-none">
              {matterName || 'New Matter'}
            </h1>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container max-w-6xl mx-auto px-4 py-6">
        {/* Processing progress bar (always visible) */}
        <ProcessingProgressView
          currentStage={processingStage}
          overallProgressPct={overallProgressPct}
          filesReceived={files.length}
          className="mb-6"
        />

        {/* Split layout: Documents | Discoveries */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left panel: Document progress */}
          <div className="space-y-4">
            <h2 className="text-base font-medium flex items-center gap-2">
              <span className="text-lg">📄</span>
              DOCUMENTS
            </h2>

            {/* Show upload progress during upload phase */}
            {isUploadPhase && (
              <UploadProgressView
                uploadProgress={uploadProgressArray}
                totalFiles={files.length}
                onCancelFile={handleCancelFile}
              />
            )}

            {/* Show processing details after upload complete */}
            {!isUploadPhase && uploadsComplete && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <span>✓</span>
                  <span>{files.length} files received</span>
                </div>
                {/* Additional processing stats can be added here */}
              </div>
            )}
          </div>

          {/* Right panel: Live discoveries */}
          <div className="space-y-4">
            <h2 className="text-base font-medium flex items-center gap-2">
              <span className="text-lg">🔍</span>
              LIVE DISCOVERIES
            </h2>

            <LiveDiscoveriesPanel
              discoveries={liveDiscoveries}
              isProcessing={!uploadsComplete || processingStage !== null}
              currentStage={processingStage}
            />
          </div>
        </div>

        {/* Continue in Background button */}
        <div className="flex justify-center mt-8">
          <Button
            variant="outline"
            size="lg"
            onClick={handleContinueInBackground}
            className="min-w-[200px]"
          >
            Continue in Background
          </Button>
        </div>
      </main>
    </div>
  );
}
