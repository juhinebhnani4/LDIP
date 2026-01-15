'use client';

import { ActivityFeed, QuickStats } from '@/components/features/dashboard';

/**
 * Dashboard Sidebar
 *
 * Client component containing ActivityFeed and QuickStats.
 * Separated from the server component page for proper hydration.
 */

interface DashboardSidebarProps {
  /** Optional className for styling */
  className?: string;
}

export function DashboardSidebar({ className }: DashboardSidebarProps) {
  return (
    <div className={className}>
      <div className="sticky top-20 space-y-6">
        <ActivityFeed />
        <QuickStats />
      </div>
    </div>
  );
}
