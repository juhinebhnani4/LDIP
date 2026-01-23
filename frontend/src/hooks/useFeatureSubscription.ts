/**
 * Feature Subscription Hook
 *
 * Subscribes to real-time feature availability broadcasts from the backend.
 * Updates the feature store when document features become ready.
 *
 * This enables progressive UX - users can interact with features as they
 * become available rather than waiting for full processing.
 */

import { useEffect, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import {
  useFeatureStore,
  type FeatureReadyEvent,
  type FeaturesUpdateEvent,
} from '@/stores/featureStore';

interface UseFeatureSubscriptionOptions {
  /** Matter ID to subscribe to */
  matterId: string;
  /** Document IDs to track (optional - tracks all if not specified) */
  documentIds?: string[];
  /** Whether to enable subscription */
  enabled?: boolean;
}

/**
 * Subscribe to feature availability broadcasts
 *
 * @example
 * ```tsx
 * function DocumentViewer({ matterId, documentId }) {
 *   useFeatureSubscription({ matterId, documentIds: [documentId] });
 *
 *   const features = useFeatureStore(selectDocumentFeatures(documentId));
 *
 *   return (
 *     <div>
 *       {features.search && <SearchButton />}
 *       {features.entities && <EntityPanel />}
 *       {features.citations && <CitationsPanel />}
 *     </div>
 *   );
 * }
 * ```
 */
export function useFeatureSubscription({
  matterId,
  documentIds,
  enabled = true,
}: UseFeatureSubscriptionOptions) {
  const handleFeatureReadyEvent = useFeatureStore(
    (state) => state.handleFeatureReadyEvent
  );
  const handleFeaturesUpdateEvent = useFeatureStore(
    (state) => state.handleFeaturesUpdateEvent
  );

  // Handle feature_ready events
  const onFeatureReady = useCallback(
    (payload: { payload: FeatureReadyEvent }) => {
      const event = payload.payload;
      if (!event) return;

      // Filter by document if specified
      if (documentIds && !documentIds.includes(event.document_id)) {
        return;
      }

      handleFeatureReadyEvent(event);
    },
    [documentIds, handleFeatureReadyEvent]
  );

  // Handle features_update batch events
  const onFeaturesUpdate = useCallback(
    (payload: { payload: FeaturesUpdateEvent }) => {
      const event = payload.payload;
      if (!event) return;

      // Filter by document if specified
      if (documentIds && !documentIds.includes(event.document_id)) {
        return;
      }

      handleFeaturesUpdateEvent(event);
    },
    [documentIds, handleFeaturesUpdateEvent]
  );

  useEffect(() => {
    if (!enabled || !matterId) return;

    const supabase = createClient();

    // Subscribe to the features channel for this matter
    // Pattern: features:{matter_id}:document:{document_id}
    // We subscribe to all documents for the matter and filter client-side
    const channel = supabase
      .channel(`features:${matterId}`)
      .on('broadcast', { event: 'feature_ready' }, onFeatureReady)
      .on('broadcast', { event: 'features_update' }, onFeaturesUpdate)
      .subscribe();

    return () => {
      channel.unsubscribe();
    };
  }, [matterId, enabled, onFeatureReady, onFeaturesUpdate]);
}

/**
 * Hook to subscribe to features for a single document
 */
export function useDocumentFeatures(matterId: string, documentId: string) {
  useFeatureSubscription({
    matterId,
    documentIds: [documentId],
    enabled: !!matterId && !!documentId,
  });

  return useFeatureStore((state) => state.getFeatures(documentId));
}
