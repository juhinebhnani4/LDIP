import type { ReactNode } from 'react';
import { createClient } from '@/lib/supabase/server';
import { DashboardHeader } from '@/components/features/dashboard';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default async function DashboardLayout({ children }: DashboardLayoutProps) {
  // Get user data server-side for header
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const headerUser = user
    ? {
        email: user.email ?? null,
        fullName: (user.user_metadata?.full_name as string) ?? null,
      }
    : undefined;

  return (
    <div className="min-h-screen flex flex-col">
      <DashboardHeader user={headerUser} />
      <main className="flex-1 container mx-auto py-6">{children}</main>
    </div>
  );
}
