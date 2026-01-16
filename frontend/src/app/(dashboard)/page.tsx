import Link from 'next/link';
import { Plus } from 'lucide-react';
import { createClient } from '@/lib/supabase/server';
import { Button } from '@/components/ui/button';
import { DashboardContent } from './DashboardContent';
import { DashboardSidebar } from './DashboardSidebar';

/**
 * Dashboard Page
 *
 * Layout from UX-Decisions-Log.md (70/30 split):
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  HEADER (from Story 9-1)                                        │
 * ├─────────────────────────────────────────┬───────────────────────┤
 * │                                         │                       │
 * │  Welcome, Juhi                          │  ACTIVITY FEED        │
 * │  [+ New Matter]                         │  (Story 9-3)          │
 * │                                         │                       │
 * │  ┌────────────┐  ┌────────────┐         │  Recent activity...   │
 * │  │  Matter 1  │  │  Matter 2  │         │                       │
 * │  │  Ready     │  │Processing  │         ├───────────────────────┤
 * │  │  892 pgs   │  │  67%       │         │  QUICK STATS          │
 * │  │[Resume →]  │  │[Progress →]│         │  (Story 9-3)          │
 * │  └────────────┘  └────────────┘         │                       │
 * │                                         │  📁 5 Active Matters  │
 * │  ┌────────────┐                         │  ✓ 127 Verified       │
 * │  │  + New     │                         │  ⏳ 3 Pending         │
 * │  │  Matter    │                         │                       │
 * │  └────────────┘                         │                       │
 * │  (70% width - this story)               │  (30% width - 9-3)    │
 * └─────────────────────────────────────────┴───────────────────────┘
 */

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // User should always be defined here since middleware protects this route
  const displayName = user?.user_metadata?.full_name ?? user?.email ?? 'User';

  return (
    <div className="flex gap-6 px-4 sm:px-6 py-6">
      {/* Left side - 70% width - Matter cards grid */}
      <div className="flex-[7] min-w-0 space-y-6">
        {/* Hero section with greeting and CTA */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Welcome, {displayName}
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage your legal matters and documents
            </p>
          </div>
          <Button asChild>
            <Link href="/upload">
              <Plus className="size-4 mr-1" />
              New Matter
            </Link>
          </Button>
        </div>

        {/* Dashboard content (client component for filters, view toggle, grid) */}
        <DashboardContent />
      </div>

      {/* Right side - 30% width - Activity feed and Quick Stats (Story 9-3) */}
      <DashboardSidebar className="hidden lg:block flex-[3] min-w-0" />
    </div>
  );
}
