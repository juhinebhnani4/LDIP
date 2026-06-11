'use client';

import { useEffect, useCallback, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { useMatterStore } from '@/stores/matterStore';
import { ApiError } from '@/lib/api/client';
import { MatterErrorScreen } from './MatterErrorScreen';

interface MatterGateProps {
  /** Matter ID from the route segment */
  matterId: string;
  /** The workspace shell (header, tab bar, content area) to render once the matter is confirmed */
  children: ReactNode;
}

/**
 * Matter Workspace Convergence Gate (FE-ARCH-01).
 *
 * Resolves matter existence + authorization ONCE, before the workspace shell
 * (header, tab bar, 7 feature panels, ~29 fetch hooks) mounts. This is the single
 * convergence point the matter workspace previously lacked: instead of every panel
 * independently discovering a missing/forbidden matter and erroring on its own
 * (18 console errors — FE-003), nothing below the gate renders until the matter is
 * confirmed loadable.
 *
 *   loading / idle  → workspace loading screen
 *   error (404/403) → MatterErrorScreen (the expected "can't open this matter" path)
 *   other error     → MatterErrorScreen (generic "something went wrong")
 *   ready           → render the workspace shell (children)
 *
 * Replaces the old `matterStore.fetchMatter` placeholder fabrication ("Untitled
 * Matter"), which swallowed the 404 so the shell rendered over a matter that did
 * not exist. Because this gate lives in the segment layout, every current and future
 * tab page is structurally behind it — the guard is the framework's layout nesting,
 * not a per-panel convention.
 */
export function MatterGate({ matterId, children }: MatterGateProps) {
  const fetchMatter = useMatterStore((state) => state.fetchMatter);
  const status = useMatterStore((state) => state.currentMatterStatus);
  const stateMatterId = useMatterStore((state) => state.currentMatterId);
  const currentMatter = useMatterStore((state) => state.currentMatter);
  const error = useMatterStore((state) => state.currentMatterError);

  useEffect(() => {
    fetchMatter(matterId);
  }, [matterId, fetchMatter]);

  const retry = useCallback(() => {
    fetchMatter(matterId);
  }, [matterId, fetchMatter]);

  // The store is a singleton; during A→B navigation its status/error may still
  // describe matter A for a render. Only trust them when they describe THIS matter.
  const describesThisMatter = stateMatterId === matterId;

  if (describesThisMatter && status === 'error') {
    const notAvailable =
      error instanceof ApiError && (error.status === 404 || error.status === 403);
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <MatterErrorScreen
          title={notAvailable ? 'Matter not available' : 'Something went wrong'}
          description={
            notAvailable
              ? "This matter doesn't exist, or you don't have access to it. It may have been deleted, or you may have been removed from it."
              : 'There was a problem loading this matter. Please try again or return to the dashboard.'
          }
          onRetry={retry}
          details={error?.message}
        />
      </div>
    );
  }

  const isReady =
    describesThisMatter && status === 'ready' && currentMatter?.id === matterId;

  if (!isReady) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
        <span className="text-sm" role="status">
          Loading matter…
        </span>
      </div>
    );
  }

  return <>{children}</>;
}
