'use client';

import Link from 'next/link';
import { JaanchLogo } from '@/components/ui/jaanch-logo';
import { NotificationsDropdown } from './NotificationsDropdown';
import { UserProfileDropdown } from './UserProfileDropdown';
import { GlobalSearch } from './GlobalSearch';
import { HelpButton } from '@/components/features/help';

/**
 * Dashboard Header Component
 *
 * Layout:
 * ┌─────────────────────────────────────────────────────────────────────────────────┐
 * │  HEADER                                                                         │
 * │  ┌────────────┐                                ┌────┐ ┌────┐ ┌───────────┐      │
 * │  │ jaanch.ai  │   [🔍 Search all matters...]   │ 🔔 │ │ ❓ │ │ JJ ▼     │      │
 * │  │ (logo)     │                                │ 3  │ │    │ │ Juhi     │      │
 * │  └────────────┘                                └────┘ └────┘ └───────────┘      │
 * └─────────────────────────────────────────────────────────────────────────────────┘
 */

interface DashboardHeaderProps {
  /** Optional user data passed from server component */
  user?: {
    email: string | null;
    fullName: string | null;
  };
}

export function DashboardHeader({ user }: DashboardHeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60" data-testid="dashboard-header">
      <div className="mx-auto w-full max-w-7xl flex h-14 items-center gap-4 px-4 sm:px-6">
        {/* Logo - Left side */}
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="flex items-center"
            aria-label="jaanch.ai Home"
          >
            <JaanchLogo variant="full" size="sm" />
          </Link>
        </div>

        {/* Global Search - Center (flex-1 to take available space) */}
        <div className="flex-1 flex justify-center px-4">
          <GlobalSearch />
        </div>

        {/* Right side controls */}
        <div className="flex items-center gap-1">
          {/* Notifications */}
          <NotificationsDropdown />

          {/* Help button */}
          <HelpButton data-tour="help-button" />

          {/* User Profile Dropdown */}
          <UserProfileDropdown initialUser={user} />
        </div>
      </div>
    </header>
  );
}
