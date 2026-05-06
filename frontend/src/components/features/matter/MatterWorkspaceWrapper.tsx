'use client';

import { useEffect, useCallback, useRef, type ReactNode } from 'react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ProcessingStatusBanner } from '@/components/features/processing';
import {
  useProcessingStore,
  selectActiveJobCount,
  selectFailedJobCount,
} from '@/stores/processingStore';
import { useWorkspaceStore, selectIsAnyTabProcessing } from '@/stores/workspaceStore';
import { useMatterStore } from '@/stores/matterStore';
import { jobsApi } from '@/lib/api/jobs';
import { mattersApi } from '@/lib/api/matters';
import { createClient } from '@/lib/supabase/client';
import { ActDiscoveryTrigger } from '@/components/features/citation';
import { useFeatureSubscription } from '@/hooks/useFeatureSubscription';
import type { JobProgressEvent, JobStatusChangeEvent } from '@/types/job';

interface MatterWorkspaceWrapperProps {
  /** Matter ID for tracking */
  matterId: string;
  /** Child content */
  children: ReactNode;
}

/**
 * Matter Workspace Wrapper
 *
 * Client component that wraps the matter workspace with:
 * - Processing status banner when jobs are active
 * - Job tracking store initialization
 * - Real-time job updates via Supabase Realtime (broadcast channel)
 *
 * Story 2c-3: Background Job Status Tracking
 */
export function MatterWorkspaceWrapper({
  matterId,
  children,
}: MatterWorkspaceWrapperProps) {
  const setMatterId = useProcessingStore((state) => state.setMatterId);
  const setJobs = useProcessingStore((state) => state.setJobs);
  const setStats = useProcessingStore((state) => state.setStats);
  const setLoading = useProcessingStore((state) => state.setLoading);
  const handleProgressEvent = useProcessingStore((state) => state.handleProgressEvent);
  const handleStatusChangeEvent = useProcessingStore((state) => state.handleStatusChangeEvent);

  const activeCount = useProcessingStore(selectActiveJobCount);
  const failedCount = useProcessingStore(selectFailedJobCount);

  // Handle real-time progress events from Supabase
  const onProgressEvent = useCallback(
    (payload: { payload: JobProgressEvent }) => {
      if (payload.payload) {
        handleProgressEvent(payload.payload);
      }
    },
    [handleProgressEvent]
  );

  // Handle real-time status change events from Supabase
  const onStatusChangeEvent = useCallback(
    (payload: { payload: JobStatusChangeEvent }) => {
      if (payload.payload) {
        handleStatusChangeEvent(payload.payload);
      }
    },
    [handleStatusChangeEvent]
  );

  // Pre-fetch matter data so children (e.g. EditableMatterName) don't start from null
  const fetchMatter = useMatterStore((state) => state.fetchMatter);
  useEffect(() => {
    fetchMatter(matterId);
  }, [matterId, fetchMatter]);

  // Initialize store with matter ID and load jobs
  useEffect(() => {
    setMatterId(matterId);

    const loadJobs = async () => {
      setLoading(true);
      try {
        const [jobsResponse, statsResponse] = await Promise.all([
          jobsApi.list({ matterId }),
          jobsApi.getStats(matterId),
        ]);
        setJobs(jobsResponse.jobs);
        setStats(statsResponse);
      } catch {
        // Silently fail - jobs API might not be fully deployed yet
        // This is a progressive enhancement
      } finally {
        setLoading(false);
      }
    };

    loadJobs();

    // UX-005: Record that the user opened this matter (fire-and-forget)
    mattersApi.touch(matterId).catch((e) => console.warn('touch failed:', e));

    // Set up Supabase Realtime subscription for job updates (Story 2c-3)
    const supabase = createClient();
    const channel = supabase
      .channel(`processing:${matterId}`)
      .on('broadcast', { event: 'job_progress' }, onProgressEvent)
      .on('broadcast', { event: 'job_status_change' }, onStatusChangeEvent)
      .subscribe();

    return () => {
      channel.unsubscribe();
      setMatterId(null);
    };
  }, [matterId, setMatterId, setJobs, setStats, setLoading, onProgressEvent, onStatusChangeEvent]);

  // Fetch tab stats (counts + processing status) on mount
  const fetchTabStats = useWorkspaceStore((state) => state.fetchTabStats);
  const isAnyTabProcessing = useWorkspaceStore(selectIsAnyTabProcessing);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Initial fetch
    fetchTabStats(matterId);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [matterId, fetchTabStats]);

  // Poll tab stats while any tab is processing (refresh counts as processing completes)
  useEffect(() => {
    if (isAnyTabProcessing) {
      pollIntervalRef.current = setInterval(() => {
        fetchTabStats(matterId);
      }, 15_000); // 15s — balance between freshness and API load
    } else if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [isAnyTabProcessing, matterId, fetchTabStats]);

  // Subscribe to feature availability broadcasts for progressive UI
  // This enables showing features as they become ready during processing
  useFeatureSubscription({ matterId, enabled: true });

  // Determine if banner should show
  const showBanner = activeCount > 0 || failedCount > 0;

  return (
    <TooltipProvider>
      <div className="flex h-full flex-col overflow-hidden">
        {/* Processing status banner */}
        {showBanner && (
          <div className="shrink-0 px-6 pt-4">
            <ProcessingStatusBanner collapsible={true} />
          </div>
        )}

        {/* Workspace content */}
        <div className="h-full min-h-0 flex-1">{children}</div>

        {/* Act Discovery Modal - auto-shows when missing Acts detected (Story 3-2) */}
        <ActDiscoveryTrigger matterId={matterId} />
      </div>
    </TooltipProvider>
  );
}
