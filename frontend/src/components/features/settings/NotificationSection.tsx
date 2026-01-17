'use client';

/**
 * NotificationSection Component
 *
 * Manages user notification preferences with toggles.
 *
 * Story 14.14: Settings Page Implementation
 * Task 6: Create NotificationSection component
 */

import { Bell, Mail, Monitor } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useUserPreferences } from '@/hooks/useUserPreferences';

interface NotificationToggleProps {
  id: string;
  icon: React.ElementType;
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (checked: boolean) => void;
}

function NotificationToggle({
  id,
  icon: Icon,
  label,
  description,
  checked,
  disabled,
  onCheckedChange,
}: NotificationToggleProps) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="flex gap-3">
        <div className="mt-0.5">
          <Icon className="size-5 text-muted-foreground" />
        </div>
        <div className="space-y-0.5">
          <Label htmlFor={id} className="text-sm font-medium cursor-pointer">
            {label}
          </Label>
          <p className="text-sm text-muted-foreground">
            {description}
          </p>
        </div>
      </div>
      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
      />
    </div>
  );
}

function NotificationToggleSkeleton() {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="flex gap-3">
        <Skeleton className="size-5 mt-0.5" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-48" />
        </div>
      </div>
      <Skeleton className="h-5 w-9 rounded-full" />
    </div>
  );
}

export function NotificationSection() {
  const { preferences, isLoading, updatePreferences, isUpdating, updateError } = useUserPreferences();

  const handleToggle = async (key: 'emailNotificationsProcessing' | 'emailNotificationsVerification' | 'browserNotifications', value: boolean) => {
    try {
      await updatePreferences({ [key]: value });
    } catch {
      // Error handled by hook
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56 mt-1" />
        </CardHeader>
        <CardContent className="divide-y">
          <NotificationToggleSkeleton />
          <NotificationToggleSkeleton />
          <NotificationToggleSkeleton />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bell className="size-5" />
          Notifications
        </CardTitle>
        <CardDescription>
          Control how you receive updates and alerts
        </CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {updateError && (
          <p className="text-sm text-destructive pb-3">
            Failed to update preferences. Please try again.
          </p>
        )}

        <NotificationToggle
          id="email-processing"
          icon={Mail}
          label="Document Processing"
          description="Email when document processing completes"
          checked={preferences?.emailNotificationsProcessing ?? true}
          disabled={isUpdating}
          onCheckedChange={(checked) => handleToggle('emailNotificationsProcessing', checked)}
        />

        <NotificationToggle
          id="email-verification"
          icon={Mail}
          label="Verification Reminders"
          description="Email reminders for pending verifications"
          checked={preferences?.emailNotificationsVerification ?? true}
          disabled={isUpdating}
          onCheckedChange={(checked) => handleToggle('emailNotificationsVerification', checked)}
        />

        <NotificationToggle
          id="browser-notifications"
          icon={Monitor}
          label="Browser Notifications"
          description="Push notifications in your browser"
          checked={preferences?.browserNotifications ?? false}
          disabled={isUpdating}
          onCheckedChange={(checked) => handleToggle('browserNotifications', checked)}
        />
      </CardContent>
    </Card>
  );
}
