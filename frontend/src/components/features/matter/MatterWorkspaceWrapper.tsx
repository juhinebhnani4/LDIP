'use client';

import { useEffect, useCallback, type ReactNode } from 'react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ProcessingStatusBanner } from '@/components/features/processing';
import {
  useProcessingStore,
  selectActiveJobCount,
  selectFailedJobCount,
} from '@/stores/processingStore';
import { jobsApi } from '@/lib/api/jobs';
import { createClient } from '@/lib/supabase/client';
import { ActDiscoveryTrigger } from '@/components/features/citation';
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

  // Determine if banner should show
  const showBanner = activeCount > 0 || failedCount > 0;

  return (
    <TooltipProvider>
      <div className="flex flex-col min-h-full">
        {/* Processing status banner */}
        {showBanner && (
          <div className="px-6 pt-4">
            <ProcessingStatusBanner collapsible={true} />
          </div>
        )}

        {/* Workspace content */}
        <div className="flex-1">{children}</div>

        {/* Act Discovery Modal - auto-shows when missing Acts detected (Story 3-2) */}
        <ActDiscoveryTrigger matterId={matterId} />
      </div>
    </TooltipProvider>
  );
}
