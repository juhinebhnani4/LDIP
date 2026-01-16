'use client';

import Link from 'next/link';
import { HelpCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { JaanchLogo } from '@/components/ui/jaanch-logo';
import { NotificationsDropdown } from './NotificationsDropdown';
import { UserProfileDropdown } from './UserProfileDropdown';
import { GlobalSearch } from './GlobalSearch';

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
  const handleHelpClick = () => {
    // Opens external help documentation in new tab with security attributes
    window.open('https://help.jaanch.ai', '_blank', 'noopener,noreferrer');
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center gap-4 px-4 sm:px-6">
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
          <Button
            variant="ghost"
            size="icon"
            onClick={handleHelpClick}
            aria-label="Help"
          >
            <HelpCircle className="h-5 w-5" />
          </Button>

          {/* User Profile Dropdown */}
          <UserProfileDropdown initialUser={user} />
        </div>
      </div>
    </header>
  );
}
