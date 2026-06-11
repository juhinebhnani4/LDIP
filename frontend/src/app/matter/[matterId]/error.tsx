'use client';

import { useEffect } from 'react';
import { MatterErrorScreen } from '@/components/features/matter';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Matter Error Boundary (route-level).
 *
 * Catches UNEXPECTED render/throw errors anywhere in the matter route subtree.
 * Expected "can't open this matter" cases (404/403) are handled upstream by
 * MatterGate before the shell mounts (FE-ARCH-01); this boundary is the safety
 * net for everything else. Renders the shared MatterErrorScreen so the two error
 * surfaces can't drift apart (FE-ARCH-03 duplication shape).
 */
export default function MatterError({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log error for debugging (dev only)
    if (process.env.NODE_ENV !== 'production') {
      console.error('[MatterError] Error in matter route:', error);
    }
  }, [error]);

  // Check if this is an access denied error
  const isAccessDenied =
    error.message?.toLowerCase().includes('not found') ||
    error.message?.toLowerCase().includes('access') ||
    error.message?.toLowerCase().includes('permission') ||
    error.message?.toLowerCase().includes('unauthorized');

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <MatterErrorScreen
        title={isAccessDenied ? 'Access Denied' : 'Something went wrong'}
        description={
          isAccessDenied
            ? "You don't have access to this matter. You may have been removed from this matter, or the matter may have been deleted."
            : 'There was an error loading this matter. Please try again or return to the dashboard.'
        }
        onRetry={reset}
        details={error.digest ? `${error.message}\nDigest: ${error.digest}` : error.message}
      />
    </div>
  );
}
