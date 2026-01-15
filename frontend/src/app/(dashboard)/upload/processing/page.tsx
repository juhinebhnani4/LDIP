'use client';

/**
 * Upload Processing Page
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 * Story 9-6: Add Stage 5 completion handling and redirect
 *
 * Shows upload progress (Stage 3), processing progress with live discoveries (Stage 4),
 * and completion screen with auto-redirect (Stage 5).
 * Uses mock progress simulation for MVP until backend is ready.
 */

import { useState, useEffect, useCallback, useRef, useLayoutEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useUploadWizardStore, selectIsProcessingComplete } from '@/stores/uploadWizardStore';
import { useBackgroundProcessingStore } from '@/stores/backgroundProcessingStore';
import { ProcessingScreen, CompletionScreen } from '@/components/features/upload';
import { simulateUploadAndProcessing } from '@/lib/utils/mock-processing';
import { requestNotificationPermission } from '@/lib/utils/browser-notifications';

export default function ProcessingPage() {
  const router = useRouter();
  const [showCompletion, setShowCompletion] = useState(false);

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
  const isProcessingComplete = selectIsProcessingComplete({
    processingStage,
    overallProgressPct,
  } as Parameters<typeof selectIsProcessingComplete>[0]);

  // Use ref to track simulation state (avoids re-running effect)
  const simulationStartedRef = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const isBackgroundedRef = useRef(false);

  // Redirect if no files - use layoutEffect to redirect before paint
  useLayoutEffect(() => {
    if (files.length === 0) {
      reset();
      router.replace('/upload');
    }
  }, [files.length, reset, router]);

  // Start simulation when component mounts (with files)
  useEffect(() => {
    if (files.length > 0 && !simulationStartedRef.current) {
      simulationStartedRef.current = true;

      // Clear any previous processing state
      clearProcessingState();

      // Generate mock matter ID
      const mockMatterId = `matter-${Date.now()}`;
      setMatterId(mockMatterId);

      // Start the simulation
      const cleanup = simulateUploadAndProcessing(files, {
        onUploadProgress: setUploadProgress,
        onProcessingStage: setProcessingStage,
        onOverallProgress: setOverallProgress,
        onDiscovery: addLiveDiscovery,
        onComplete: () => {
          // Simulation complete - processing finished
        },
      });

      cleanupRef.current = cleanup;
    }

    // Cleanup on unmount
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
      }
    };
  }, [
    files,
    clearProcessingState,
    setMatterId,
    setUploadProgress,
    setProcessingStage,
    setOverallProgress,
    addLiveDiscovery,
  ]);

  // Detect processing completion and show completion screen (Story 9-6)
  // Use setTimeout to schedule state updates, avoiding synchronous setState in effect
  useEffect(() => {
    if (isProcessingComplete && !showCompletion) {
      const timer = setTimeout(() => {
        setShowCompletion(true);
        setProcessingComplete(true);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [isProcessingComplete, showCompletion, setProcessingComplete]);

  // Handle continue in background (Story 9-6)
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

    // Simulate completion after a delay (mock background processing)
    // In a real implementation, this would be handled by the backend
    const remainingProgress = 100 - overallProgressPct;
    const estimatedTimeMs = Math.max(remainingProgress * 100, 3000); // At least 3 seconds

    setTimeout(() => {
      markComplete(matterId);
    }, estimatedTimeMs);
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
