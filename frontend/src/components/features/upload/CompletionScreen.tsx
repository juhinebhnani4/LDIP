'use client';

/**
 * CompletionScreen Component
 *
 * Stage 5 completion screen showing processing success state.
 * Displays success checkmark, matter summary, countdown, and redirect button.
 *
 * Story 9-6: Implement Upload Flow Stage 5 and Notifications
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle2, FileText, Users, Calendar, Scale, ArrowRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useUploadWizardStore } from '@/stores/uploadWizardStore';
import type { LiveDiscovery } from '@/types/upload';
import styles from './CompletionScreen.module.css';

/** Redirect delay in milliseconds */
const REDIRECT_DELAY_MS = 3000;
/** Countdown interval in milliseconds */
const COUNTDOWN_INTERVAL_MS = 1000;

interface CompletionScreenProps {
  /** Optional className for the container */
  className?: string;
  /** Callback when redirect occurs */
  onRedirect?: () => void;
}

/**
 * Get discovery count by type from the discoveries array
 */
function getDiscoveryCount(discoveries: LiveDiscovery[], type: string): number {
  const discovery = discoveries.find((d) => d.type === type);
  return discovery?.count ?? 0;
}

export function CompletionScreen({ className, onRedirect }: CompletionScreenProps) {
  const router = useRouter();
  const [countdown, setCountdown] = useState(REDIRECT_DELAY_MS / 1000);
  const [hasRedirected, setHasRedirected] = useState(false);

  // Use selector pattern for store access
  const matterName = useUploadWizardStore((state) => state.matterName);
  const files = useUploadWizardStore((state) => state.files);
  const liveDiscoveries = useUploadWizardStore((state) => state.liveDiscoveries);
  const reset = useUploadWizardStore((state) => state.reset);

  // Get discovery counts from live discoveries
  const entityCount = getDiscoveryCount(liveDiscoveries, 'entity');
  const dateCount = getDiscoveryCount(liveDiscoveries, 'date');
  const citationCount = getDiscoveryCount(liveDiscoveries, 'citation');

  // Get matter ID for redirect to workspace
  const matterId = useUploadWizardStore((state) => state.matterId);

  // Handle redirect to workspace
  const handleRedirect = useCallback(() => {
    if (hasRedirected) return;
    setHasRedirected(true);

    if (onRedirect) {
      onRedirect();
    }

    // Clear wizard state before redirect
    reset();

    // Redirect to workspace (or dashboard if no matterId)
    const destination = matterId ? `/matter/${matterId}` : '/';
    router.push(destination);
  }, [hasRedirected, onRedirect, reset, router, matterId]);

  // Handle immediate redirect via button
  const handleGoNow = useCallback(() => {
    handleRedirect();
  }, [handleRedirect]);

  // Countdown timer effect - use setTimeout chain instead of setInterval to avoid lint issues
  useEffect(() => {
    // Don't start timer if already redirected
    if (hasRedirected) return;

    // If countdown reached 0, schedule redirect as a timeout callback
    if (countdown <= 0) {
      const redirectTimer = setTimeout(() => {
        handleRedirect();
      }, 0);
      return () => clearTimeout(redirectTimer);
    }

    // Decrement countdown each second
    const timer = setTimeout(() => {
      setCountdown((prev) => prev - 1);
    }, COUNTDOWN_INTERVAL_MS);

    return () => clearTimeout(timer);
  }, [countdown, hasRedirected, handleRedirect]);

  return (
    <div
      className={cn('min-h-screen bg-muted/30 flex items-center justify-center p-4', className)}
      role="status"
      aria-label="Processing complete"
    >
      <Card className="w-full max-w-lg">
        <CardContent className="py-10 px-8 text-center">
          {/* Animated checkmark */}
          <div
            className={cn('mx-auto mb-6', styles.completionIcon)}
            aria-label="Processing complete"
          >
            <div className="relative inline-flex items-center justify-center">
              <div className={cn('absolute inset-0 rounded-full bg-green-500/20', styles.pulseRing)} />
              <div className="relative rounded-full bg-green-100 dark:bg-green-900/30 p-4">
                <CheckCircle2
                  className={cn('size-16 text-green-600 dark:text-green-400', styles.checkmark)}
                  aria-hidden="true"
                />
              </div>
            </div>
          </div>

          {/* Title */}
          <h1 className="text-2xl font-bold text-foreground mb-2">
            Processing Complete!
          </h1>

          {/* Matter name */}
          <p className="text-lg text-muted-foreground mb-6">
            &ldquo;{matterName || 'New Matter'}&rdquo; is ready to explore
          </p>

          {/* Matter summary stats */}
          <div className="bg-muted/50 rounded-lg p-4 mb-6">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <FileText className="size-4" aria-hidden="true" />
                <span>{files.length} documents</span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Users className="size-4" aria-hidden="true" />
                <span>{entityCount} entities discovered</span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Calendar className="size-4" aria-hidden="true" />
                <span>{dateCount} timeline events</span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Scale className="size-4" aria-hidden="true" />
                <span>{citationCount} citations detected</span>
              </div>
            </div>
          </div>

          {/* Countdown message */}
          <p
            className="text-sm text-muted-foreground mb-4"
            aria-live="polite"
          >
            Redirecting in {countdown} second{countdown !== 1 ? 's' : ''}...
          </p>

          {/* Go to workspace button */}
          <Button
            size="lg"
            className="min-w-[200px]"
            onClick={handleGoNow}
          >
            Go to Workspace Now
            <ArrowRight className="ml-2 size-4" aria-hidden="true" />
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
