'use client';

/**
 * PowerUserSection Component
 *
 * Manages Power User Mode preference for progressive disclosure.
 *
 * Story 6.1: Progressive Disclosure UI
 * Task 6.1.5: Create PowerUserSection.tsx settings component
 */

import { Zap, Keyboard, Layers, ArrowRightLeft } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { useUserPreferences } from '@/hooks/useUserPreferences';

interface FeatureItemProps {
  icon: React.ElementType;
  label: string;
  description: string;
}

function FeatureItem({ icon: Icon, label, description }: FeatureItemProps) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 p-1.5 rounded-md bg-muted">
        <Icon className="size-4 text-muted-foreground" />
      </div>
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

export function PowerUserSection() {
  const { preferences, isLoading, updatePreferences, isUpdating, updateError } = useUserPreferences();

  const handleToggle = async (checked: boolean) => {
    try {
      await updatePreferences({ powerUserMode: checked });
    } catch {
      // Error handled by hook
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-64 mt-1" />
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-5 w-9 rounded-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const isPowerUser = preferences?.powerUserMode ?? false;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Zap className="size-5" />
            Power User Mode
          </CardTitle>
          {isPowerUser && (
            <Badge variant="secondary" className="text-xs">
              Enabled
            </Badge>
          )}
        </div>
        <CardDescription>
          Enable advanced features for power users
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {updateError && (
          <p className="text-sm text-destructive">
            Failed to update preference. Please try again.
          </p>
        )}

        <div className="flex items-center justify-between py-2">
          <div className="space-y-0.5">
            <Label htmlFor="power-user-mode" className="text-sm font-medium cursor-pointer">
              Enable Power User Mode
            </Label>
            <p className="text-sm text-muted-foreground">
              Unlock advanced features for experienced users
            </p>
          </div>
          <Switch
            id="power-user-mode"
            checked={isPowerUser}
            onCheckedChange={handleToggle}
            disabled={isUpdating}
          />
        </div>

        {/* Feature list - shown when enabled */}
        {isPowerUser && (
          <div className="pt-4 border-t space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Unlocked Features
            </p>
            <div className="grid gap-3">
              <FeatureItem
                icon={Layers}
                label="Bulk Operations"
                description="Select and manage multiple matters at once"
              />
              <FeatureItem
                icon={Keyboard}
                label="Keyboard Shortcuts"
                description="Navigate and verify findings with keyboard shortcuts"
              />
              <FeatureItem
                icon={ArrowRightLeft}
                label="Cross-Engine Links"
                description="See connections between timeline events and contradictions"
              />
            </div>
          </div>
        )}

        {/* Hint when disabled */}
        {!isPowerUser && (
          <div className="pt-4 border-t">
            <p className="text-sm text-muted-foreground">
              Power User Mode reveals advanced features like bulk operations, keyboard shortcuts,
              and cross-engine correlation links. Recommended after you&apos;re familiar with the basics.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
