'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { User, Settings, HelpCircle, LogOut, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { createClient } from '@/lib/supabase/client';
import type { User as SupabaseUser } from '@supabase/supabase-js';

/** Get initials from name or email for avatar */
function getInitials(name: string | null, email: string | null): string {
  if (name) {
    const parts = name.trim().split(/\s+/);
    const firstPart = parts[0];
    const lastPart = parts[parts.length - 1];
    if (parts.length >= 2 && firstPart && lastPart) {
      return `${firstPart[0]}${lastPart[0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }
  if (email) {
    return email.slice(0, 2).toUpperCase();
  }
  return 'U';
}

interface UserAvatarProps {
  initials: string;
  className?: string;
}

function UserAvatar({ initials, className }: UserAvatarProps) {
  return (
    <div
      className={`flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-medium ${className ?? ''}`}
    >
      {initials}
    </div>
  );
}

interface UserProfileDropdownProps {
  /** Optional user data passed from server component */
  initialUser?: {
    email: string | null;
    fullName: string | null;
  };
}

export function UserProfileDropdown({ initialUser }: UserProfileDropdownProps) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [user, setUser] = useState<SupabaseUser | null>(null);

  // Get user data client-side if not provided
  useEffect(() => {
    if (!initialUser) {
      const supabase = createClient();
      supabase.auth.getUser().then(({ data }) => {
        setUser(data.user);
      });
    }
  }, [initialUser]);

  const displayName = initialUser?.fullName ?? user?.user_metadata?.full_name ?? null;
  const email = initialUser?.email ?? user?.email ?? null;
  const initials = getInitials(displayName, email);

  const handleLogout = async () => {
    setIsLoading(true);
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
      await fetch('/auth/logout', { method: 'POST' });
    } catch {
      // Ignore; still redirect user to login
    } finally {
      router.push('/login');
      router.refresh();
      setIsLoading(false);
    }
  };

  const handleSettings = () => {
    // TODO: Navigate to settings page when implemented
    router.push('/settings');
  };

  const handleHelp = () => {
    // TODO: Open help modal or navigate to help page
    window.open('https://help.ldip.app', '_blank');
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="flex items-center gap-2 px-2"
          aria-label="User profile menu"
        >
          <UserAvatar initials={initials} />
          <div className="hidden flex-col items-start text-left sm:flex">
            <span className="text-sm font-medium">
              {displayName ?? email?.split('@')[0] ?? 'User'}
            </span>
          </div>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">
              {displayName ?? 'User'}
            </p>
            {email && (
              <p className="text-xs leading-none text-muted-foreground">{email}</p>
            )}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onClick={handleSettings}>
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleHelp}>
            <HelpCircle className="mr-2 h-4 w-4" />
            <span>Help</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={handleLogout}
          disabled={isLoading}
          className="text-destructive focus:text-destructive"
        >
          <LogOut className="mr-2 h-4 w-4" />
          <span>{isLoading ? 'Signing out...' : 'Sign Out'}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
