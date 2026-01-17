'use client';

/**
 * MobileActivitySection Component
 *
 * Displays Quick Stats and Activity Feed on mobile screens.
 * Hidden on desktop where the sidebar handles this.
 *
 * Story 14.15: Mobile Activity Feed
 * Task 1 & 6: Mobile-optimized dashboard sections
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MobileQuickStats } from '@/components/features/dashboard/MobileQuickStats';
import { MobileActivityFeed } from '@/components/features/dashboard/MobileActivityFeed';
import { cn } from '@/lib/utils';

export function MobileActivitySection() {
  const [isActivityExpanded, setIsActivityExpanded] = useState(false);

  return (
    <div className="lg:hidden space-y-4">
      {/* Mobile Quick Stats - Always visible, horizontal scroll */}
      <MobileQuickStats />

      {/* Collapsible Activity Feed */}
      <div className="space-y-2">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-between h-auto py-2"
          onClick={() => setIsActivityExpanded(!isActivityExpanded)}
        >
          <span className="text-sm font-medium">Recent Activity</span>
          {isActivityExpanded ? (
            <ChevronUp className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )}
        </Button>

        <div
          className={cn(
            'overflow-hidden transition-all duration-200',
            isActivityExpanded ? 'max-h-[400px]' : 'max-h-0'
          )}
        >
          <MobileActivityFeed maxItems={5} />
        </div>
      </div>
    </div>
  );
}
