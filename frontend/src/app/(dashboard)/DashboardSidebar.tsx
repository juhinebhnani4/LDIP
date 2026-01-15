'use client';

import { ActivityFeed, QuickStats, SidebarErrorBoundary } from '@/components/features/dashboard';

/**
 * Dashboard Sidebar
 *
 * Client component containing ActivityFeed and QuickStats.
 * Separated from the server component page for proper hydration.
 *
 * NOTE: This sidebar is hidden on mobile/tablet (< lg breakpoint) by design.
 * MVP decision: Activity feed and quick stats are desktop-only features.
 * Future enhancement: Consider bottom sheet or collapsible section for mobile.
 * See: page.tsx line 70 - `hidden lg:block`
 */

interface DashboardSidebarProps {
  /** Optional className for styling */
  className?: string;
}

export function DashboardSidebar({ className }: DashboardSidebarProps) {
  return (
    <div className={className}>
      <div className="sticky top-20 space-y-6">
        <SidebarErrorBoundary componentName="Activity Feed">
          <ActivityFeed />
        </SidebarErrorBoundary>
        <SidebarErrorBoundary componentName="Quick Stats">
          <QuickStats />
        </SidebarErrorBoundary>
      </div>
    </div>
  );
}
