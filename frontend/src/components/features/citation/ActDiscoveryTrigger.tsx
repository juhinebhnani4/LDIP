'use client';

/**
 * ActDiscoveryTrigger Component
 *
 * Monitors document processing status and automatically shows the Act Discovery Modal
 * when citation extraction completes and missing Acts are detected.
 *
 * Story 3-2: Act Discovery Report UI
 *
 * Integration Point: Stage 2.5 - After document upload, before/during processing
 * This component should be placed in the MatterWorkspaceWrapper or upload flow.
 *
 * @example
 * ```tsx
 * // In MatterWorkspaceWrapper
 * <ActDiscoveryTrigger matterId={matterId} />
 * ```
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { getMissingActs } from '@/lib/api/citations';
import { ActDiscoveryModal } from './ActDiscoveryModal';

export interface ActDiscoveryTriggerProps {
  /** Matter ID for fetching Act Discovery Report */
  matterId: string;
  /** Callback when user continues from the modal (with or without uploading all Acts) */
  onContinue?: () => void;
  /** Whether to auto-open when missing Acts are detected (default: true) */
  autoOpen?: boolean;
}

/** Realtime event for citation extraction progress */
interface CitationExtractionEvent {
  event: 'citation_extraction_complete' | 'act_discovery_update';
  matter_id: string;
  acts_discovered?: number;
  missing_acts?: number;
}

/**
 * ActDiscoveryTrigger monitors for citation extraction completion
 * and displays the Act Discovery Modal when missing Acts are found.
 *
 * This component:
 * 1. Subscribes to `citations:{matter_id}` Realtime channel
 * 2. Listens for `citation_extraction_complete` events
 * 3. Auto-opens ActDiscoveryModal when missing Acts are detected
 * 4. Allows manual opening via the returned controls
 */
export function ActDiscoveryTrigger({
  matterId,
  onContinue,
  autoOpen = true,
}: ActDiscoveryTriggerProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const hasCheckedRef = useRef(false);
  const isMountedRef = useRef(true);

  /**
   * Check for missing Acts and show modal if found
   */
  const checkForMissingActs = useCallback(async () => {
    if (!matterId) return;

    try {
      const response = await getMissingActs(matterId);
      const missingCount = response.data.length;

      if (isMountedRef.current) {
        // Auto-open modal if missing Acts found and autoOpen is enabled
        if (autoOpen && missingCount > 0 && !hasCheckedRef.current) {
          hasCheckedRef.current = true;
          setIsModalOpen(true);
        }
      }
    } catch (error) {
      // Silently fail - citation extraction might not be complete yet
      // This is a progressive enhancement, log in dev for debugging
      if (process.env.NODE_ENV === 'development') {
        console.debug('[ActDiscoveryTrigger] Failed to check for missing acts:', error);
      }
    }
  }, [matterId, autoOpen]);

  /**
   * Handle citation extraction events from Realtime
   */
  const handleCitationEvent = useCallback(
    (payload: { payload: CitationExtractionEvent }) => {
      const event = payload.payload;
      if (!event || event.matter_id !== matterId) return;

      // When citation extraction completes, check for missing Acts
      if (event.event === 'citation_extraction_complete') {
        checkForMissingActs();
      }

      // When act discovery updates (e.g., user uploads an Act)
      if (event.event === 'act_discovery_update') {
        // Could refetch here if needed
      }
    },
    [matterId, checkForMissingActs]
  );

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Set up Supabase Realtime subscription for citation events
  useEffect(() => {
    if (!matterId) return;

    const supabase = createClient();
    const channel = supabase
      .channel(`citations:${matterId}`)
      .on('broadcast', { event: 'citation_extraction_complete' }, handleCitationEvent)
      .on('broadcast', { event: 'act_discovery_update' }, handleCitationEvent)
      .subscribe();

    // Also check immediately in case extraction already completed
    checkForMissingActs();

    return () => {
      channel.unsubscribe();
    };
  }, [matterId, handleCitationEvent, checkForMissingActs]);

  // Reset check flag when matterId changes
  useEffect(() => {
    hasCheckedRef.current = false;
  }, [matterId]);

  /**
   * Handle continue from modal
   */
  const handleContinue = useCallback(() => {
    onContinue?.();
  }, [onContinue]);

  /**
   * Handle modal open state change
   */
  const handleOpenChange = useCallback((open: boolean) => {
    setIsModalOpen(open);
  }, []);

  return (
    <ActDiscoveryModal
      matterId={matterId}
      open={isModalOpen}
      onOpenChange={handleOpenChange}
      onContinue={handleContinue}
    />
  );
}

/**
 * Hook to manually control the Act Discovery Modal
 *
 * Use this when you need programmatic control over when to show the modal,
 * rather than relying on automatic detection.
 *
 * @example
 * ```tsx
 * const { showModal, hideModal, checkAndShow } = useActDiscoveryControl();
 *
 * // After upload completes
 * await checkAndShow(matterId);
 * ```
 */
export function useActDiscoveryControl() {
  const [isOpen, setIsOpen] = useState(false);
  const [targetMatterId, setTargetMatterId] = useState<string | null>(null);

  const showModal = useCallback((matterId: string) => {
    setTargetMatterId(matterId);
    setIsOpen(true);
  }, []);

  const hideModal = useCallback(() => {
    setIsOpen(false);
  }, []);

  const checkAndShow = useCallback(async (matterId: string) => {
    try {
      const response = await getMissingActs(matterId);
      if (response.data.length > 0) {
        setTargetMatterId(matterId);
        setIsOpen(true);
        return true;
      }
      return false;
    } catch (error) {
      if (process.env.NODE_ENV === 'development') {
        console.debug('[useActDiscoveryControl] Failed to check for missing acts:', error);
      }
      return false;
    }
  }, []);

  return {
    isOpen,
    matterId: targetMatterId,
    showModal,
    hideModal,
    checkAndShow,
    setIsOpen,
  };
}
