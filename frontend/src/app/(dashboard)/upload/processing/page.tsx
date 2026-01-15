'use client';

/**
 * Upload Processing Page
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 * Story 9-6: Add Stage 5 completion handling and redirect
 * Story 14-3: Wire to real backend APIs (with mock fallback)
 *
 * Shows upload progress (Stage 3), processing progress with live discoveries (Stage 4),
 * and completion screen with auto-redirect (Stage 5).
 *
 * Feature flag: NEXT_PUBLIC_USE_MOCK_PROCESSING
 * - true (default in dev): Use mock simulation
 * - false (production): Use real backend APIs
 */

import { useState, useEffect, useCallback, useRef, useLayoutEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useUploadWizardStore, selectIsProcessingComplete } from '@/stores/uploadWizardStore';
import { useBackgroundProcessingStore } from '@/stores/backgroundProcessingStore';
import { ProcessingScreen, CompletionScreen } from '@/components/features/upload';
import { simulateUploadAndProcessing } from '@/lib/utils/mock-processing';
import { createMatterAndUpload } from '@/lib/api/upload-orchestration';
import { useProcessingStatus } from '@/hooks/useProcessingStatus';
import { requestNotificationPermission } from '@/lib/utils/browser-notifications';

/**
 * Feature flag to toggle between mock and real processing.
 * Default to mock (true) for development safety.
 * Set NEXT_PUBLIC_USE_MOCK_PROCESSING=false for production.
 */
const USE_MOCK_PROCESSING = process.env.NEXT_PUBLIC_USE_MOCK_PROCESSING !== 'false';

export default function ProcessingPage() {
  const router = useRouter();
  const [showCompletion, setShowCompletion] = useState(false);
  const [uploadPhaseComplete, setUploadPhaseComplete] = useState(false);

  // Use selector pattern for store access
  const files = useUploadWizardStore((state) => state.files);
  const reset = useUploadWizardStore((state) => state.reset);
  const clearProcessingState = useUploadWizardStore(
    (state) => state.clearProcessingState
  );
  const setUploadProgress = useUploadWizardStore(
    (state) => state.setUploadProgress
  );
  const setProcessingStage = useUploadWizardStore(
    (state) => state.setProcessingStage
  );
  const setOverallProgress = useUploadWizardStore(
    (state) => state.setOverallProgress
  );
  const addLiveDiscovery = useUploadWizardStore(
    (state) => state.addLiveDiscovery
  );
  const setMatterId = useUploadWizardStore((state) => state.setMatterId);
  const setProcessingComplete = useUploadWizardStore(
    (state) => state.setProcessingComplete
  );
  const addUploadedDocumentId = useUploadWizardStore(
    (state) => state.addUploadedDocumentId
  );
  const matterName = useUploadWizardStore((state) => state.matterName);
  const matterId = useUploadWizardStore((state) => state.matterId);

  // Background processing store
  const addBackgroundMatter = useBackgroundProcessingStore(
    (state) => state.addBackgroundMatter
  );
  const markComplete = useBackgroundProcessingStore((state) => state.markComplete);

  // Use derived selector for completion check
  const processingStage = useUploadWizardStore((state) => state.processingStage);
  const overallProgressPct = useUploadWizardStore((state) => state.overallProgressPct);

  // Use ref to track simulation/upload state (avoids re-running effect)
  const processingStartedRef = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const isBackgroundedRef = useRef(false);

  // Real API: Poll processing status when we have a matter ID and upload is complete
  const {
    overallProgress: realProgress,
    currentStage: realStage,
    isComplete: realIsComplete,
    hasFailed: realHasFailed,
    error: processingError,
  } = useProcessingStatus(
    // Only poll if NOT using mock and upload phase is complete
    !USE_MOCK_PROCESSING && uploadPhaseComplete ? matterId : null,
    {
      pollingInterval: 1000,
      enabled: !USE_MOCK_PROCESSING && uploadPhaseComplete && !!matterId,
      stopOnComplete: true,
    }
  );

  // Sync real API progress to store when using real APIs
  useEffect(() => {
    if (!USE_MOCK_PROCESSING && uploadPhaseComplete && matterId) {
      setProcessingStage(realStage);
      setOverallProgress(realProgress);
    }
  }, [
    realStage,
    realProgress,
    uploadPhaseComplete,
    matterId,
    setProcessingStage,
    setOverallProgress,
  ]);

  // Compute completion state
  const isProcessingComplete = USE_MOCK_PROCESSING
    ? selectIsProcessingComplete({
        processingStage,
        overallProgressPct,
      } as Parameters<typeof selectIsProcessingComplete>[0])
    : realIsComplete;

  // Redirect if no files - use useLayoutEffect to redirect before paint
  useLayoutEffect(() => {
    if (files.length === 0) {
      reset();
      router.replace('/upload');
    }
  }, [files.length, reset, router]);

  // Start processing when component mounts (with files)
  useEffect(() => {
    if (files.length > 0 && !processingStartedRef.current) {
      processingStartedRef.current = true;

      // Clear any previous processing state
      clearProcessingState();

      if (USE_MOCK_PROCESSING) {
        // MOCK MODE: Use simulation
        const mockMatterId = `matter-${Date.now()}`;
        setMatterId(mockMatterId);

        const cleanup = simulateUploadAndProcessing(files, {
          onUploadProgress: setUploadProgress,
          onProcessingStage: setProcessingStage,
          onOverallProgress: setOverallProgress,
          onDiscovery: addLiveDiscovery,
          onComplete: () => {
            // Simulation complete
          },
        });

        cleanupRef.current = cleanup;
      } else {
        // REAL MODE: Create matter and upload files
        setProcessingStage('UPLOADING');
        setOverallProgress(0);

        const abortController = new AbortController();
        cleanupRef.current = () => abortController.abort();

        void (async () => {
          try {
            const result = await createMatterAndUpload(
              matterName || 'New Matter',
              files,
              {
                onMatterCreated: (id) => {
                  setMatterId(id);
                },
                onUploadProgress: (fileName, progress) => {
                  setUploadProgress(fileName, progress);
                },
                onFileUploaded: (_fileName, documentId) => {
                  addUploadedDocumentId(documentId);
                },
                onFileError: (fileName, error) => {
                  // Log error but continue with other files
                  console.error(`Upload failed for ${fileName}: ${error}`);
                },
                onAllUploadsComplete: (successCount, _failedCount) => {
                  if (successCount > 0) {
                    // Transition to processing phase - polling will take over
                    setUploadPhaseComplete(true);
                    setProcessingStage('OCR');
                  }
                },
              },
              abortController.signal
            );

            // Mark upload phase complete if we have uploads
            if (result.uploadedDocuments.size > 0) {
              setUploadPhaseComplete(true);
            }
          } catch (err) {
            console.error('Upload orchestration failed:', err);
            // Could show error state here
          }
        })();
      }
    }

    // Cleanup on unmount
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
      }
    };
  }, [
    files,
    matterName,
    clearProcessingState,
    setMatterId,
    setUploadProgress,
    setProcessingStage,
    setOverallProgress,
    addLiveDiscovery,
    addUploadedDocumentId,
  ]);

  // Detect processing completion and show completion screen
  useEffect(() => {
    if (isProcessingComplete && !showCompletion) {
      const timer = setTimeout(() => {
        setShowCompletion(true);
        setProcessingComplete(true);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [isProcessingComplete, showCompletion, setProcessingComplete]);

  // Handle continue in background
  const handleContinueInBackground = useCallback(async () => {
    if (!matterId) return;

    // Mark as backgrounded
    isBackgroundedRef.current = true;

    // Register matter in background processing store
    addBackgroundMatter({
      matterId,
      matterName: matterName || 'New Matter',
      progressPct: overallProgressPct,
      status: 'processing',
      startedAt: new Date(),
    });

    // Request notification permission if not already granted
    await requestNotificationPermission();

    if (USE_MOCK_PROCESSING) {
      // Mock: Simulate completion after a delay
      const remainingProgress = 100 - overallProgressPct;
      const estimatedTimeMs = Math.max(remainingProgress * 100, 3000);

      setTimeout(() => {
        markComplete(matterId);
      }, estimatedTimeMs);
    }
    // Real mode: Background polling will continue via backgroundProcessingStore
    // (Future enhancement: could add background polling for real matters)
  }, [matterId, matterName, overallProgressPct, addBackgroundMatter, markComplete]);

  // Show loading state while redirecting (files.length === 0)
  if (files.length === 0) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="size-8 text-muted-foreground animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Redirecting to upload...</p>
        </div>
      </div>
    );
  }

  // Show completion screen when processing is done (Stage 5)
  if (showCompletion) {
    return <CompletionScreen />;
  }

  return (
    <ProcessingScreen onContinueInBackground={handleContinueInBackground} />
  );
}
