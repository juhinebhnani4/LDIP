'use client';

/**
 * AppearanceSection Component
 *
 * Manages theme preferences (light/dark/system).
 *
 * Story 14.14: Settings Page Implementation
 * Task 7: Create AppearanceSection component
 */

import { Palette, Sun, Moon, Monitor } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { cn } from '@/lib/utils';

type Theme = 'light' | 'dark' | 'system';

interface ThemeOptionProps {
  value: Theme;
  label: string;
  icon: React.ElementType;
  selected: boolean;
  disabled?: boolean;
  onSelect: (theme: Theme) => void;
}

function ThemeOption({
  value,
  label,
  icon: Icon,
  selected,
  disabled,
  onSelect,
}: ThemeOptionProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      disabled={disabled}
      className={cn(
        'flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors',
        'hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        selected ? 'border-primary bg-primary/5' : 'border-muted',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <Icon className={cn('size-6', selected ? 'text-primary' : 'text-muted-foreground')} />
      <span className={cn('text-sm font-medium', selected ? 'text-primary' : 'text-muted-foreground')}>
        {label}
      </span>
    </button>
  );
}

export function AppearanceSection() {
  const { preferences, isLoading, updatePreferences, isUpdating, updateError } = useUserPreferences();

  const handleThemeChange = async (theme: Theme) => {
    try {
      await updatePreferences({ theme });

      // Apply theme immediately to document
      if (theme === 'system') {
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.classList.toggle('dark', systemTheme === 'dark');
      } else {
        document.documentElement.classList.toggle('dark', theme === 'dark');
      }

      // Also persist to localStorage for immediate effect on page load
      localStorage.setItem('theme', theme);
    } catch {
      // Error handled by hook
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48 mt-1" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3">
            <Skeleton className="h-24 rounded-lg" />
            <Skeleton className="h-24 rounded-lg" />
            <Skeleton className="h-24 rounded-lg" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const currentTheme = preferences?.theme ?? 'system';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Palette className="size-5" />
          Appearance
        </CardTitle>
        <CardDescription>
          Customize how LDIP looks on your device
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {updateError && (
          <p className="text-sm text-destructive">
            Failed to update theme. Please try again.
          </p>
        )}

        <div className="space-y-2">
          <Label>Theme</Label>
          {/* Desktop: show all 3 options */}
          <div className="hidden lg:grid grid-cols-3 gap-3">
            <ThemeOption
              value="light"
              label="Light"
              icon={Sun}
              selected={currentTheme === 'light'}
              disabled={isUpdating}
              onSelect={handleThemeChange}
            />
            <ThemeOption
              value="dark"
              label="Dark"
              icon={Moon}
              selected={currentTheme === 'dark'}
              disabled={isUpdating}
              onSelect={handleThemeChange}
            />
            <ThemeOption
              value="system"
              label="System"
              icon={Monitor}
              selected={currentTheme === 'system'}
              disabled={isUpdating}
              onSelect={handleThemeChange}
            />
          </div>
          {/* Mobile: only light mode, dark mode disabled on mobile */}
          <div className="lg:hidden">
            <div className="flex items-center gap-3 p-4 rounded-lg border-2 border-primary bg-primary/5">
              <Sun className="size-6 text-primary" />
              <div>
                <span className="text-sm font-medium text-primary">Light Mode</span>
                <p className="text-xs text-muted-foreground">Dark mode is available on desktop</p>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
