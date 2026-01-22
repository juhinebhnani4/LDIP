import Link from 'next/link';
import { Plus } from 'lucide-react';
import { createClient } from '@/lib/supabase/server';
import { Button } from '@/components/ui/button';
import { DashboardContent } from '../DashboardContent';
import { DashboardSidebar } from '../DashboardSidebar';
import { MobileActivitySection } from '../MobileActivitySection';

/**
 * Dashboard Page
 *
 * Responsive layout (Story 14.15 - Mobile Activity Feed):
 * - Mobile (< lg): Single column with stacked Quick Stats and Activity Feed
 * - Desktop (lg+): 70/30 split with sidebar
 */

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // User should always be defined here since middleware protects this route
  const displayName = user?.user_metadata?.full_name ?? user?.email ?? 'User';

  return (
    <div className="px-4 sm:px-6 py-6">
      {/* Desktop layout: 70/30 split */}
      <div className="flex gap-6">
        {/* Left side - Matter cards grid (full width on mobile, 70% on desktop) */}
        <div className="flex-1 lg:flex-[7] min-w-0 space-y-6">
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

          {/* Mobile Quick Stats - horizontal scrollable (Story 14.15) */}
          <MobileActivitySection />

          {/* Dashboard content (client component for filters, view toggle, grid) */}
          <DashboardContent />
        </div>

        {/* Right side - Desktop sidebar (30% width, hidden on mobile) */}
        <DashboardSidebar className="hidden lg:block flex-[3] min-w-0" />
      </div>
    </div>
  );
}
