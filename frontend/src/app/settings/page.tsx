'use client';

/**
 * Settings Page
 *
 * User account and preferences management.
 *
 * Story 14.14: Settings Page Implementation
 * Task 4: Create SettingsPage component
 */

import { ArrowLeft, Settings } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  ProfileSection,
  NotificationSection,
  AppearanceSection,
  PowerUserSection,
  AccountSection,
} from '@/components/features/settings';

export default function SettingsPage() {
  return (
    <div className="container max-w-3xl py-6 px-4 sm:px-6">
      {/* Header */}
      <div className="mb-8">
        <Button variant="ghost" size="sm" asChild className="mb-4 -ml-2">
          <Link href="/">
            <ArrowLeft className="size-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-3">
          <Settings className="size-7" />
          Settings
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage your account and preferences
        </p>
      </div>

      {/* Settings Sections */}
      <div className="space-y-6">
        <ProfileSection />
        <NotificationSection />
        <AppearanceSection />
        <PowerUserSection />
        <AccountSection />
      </div>
    </div>
  );
}
