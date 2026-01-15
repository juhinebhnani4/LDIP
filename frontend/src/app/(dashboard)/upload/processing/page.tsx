'use client';

/**
 * Upload Processing Page
 *
 * Story 9-5: Implement Upload Flow Stages 3-4
 *
 * Shows upload progress (Stage 3) and processing progress with live discoveries (Stage 4).
 * Uses mock progress simulation for MVP until backend is ready.
 */

import { useEffect, useCallback, useRef, useLayoutEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useUploadWizardStore } from '@/stores/uploadWizardStore';
import { ProcessingScreen } from '@/components/features/upload';
import { simulateUploadAndProcessing } from '@/lib/utils/mock-processing';

export default function ProcessingPage() {
  const router = useRouter();
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

  // Use ref to track simulation state (avoids re-running effect)
  const simulationStartedRef = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);

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

  // Handle continue in background
  const handleContinueInBackground = useCallback(() => {
    // In a real implementation, this would register the matter for background processing
    // For MVP, we just navigate away (simulation continues until page unmount)
  }, []);

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

  return (
    <ProcessingScreen onContinueInBackground={handleContinueInBackground} />
  );
}
