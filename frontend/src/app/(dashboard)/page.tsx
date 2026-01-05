import { createClient } from '@/lib/supabase/server';
import { LogoutButton } from '@/components/features/auth/LogoutButton';

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // User should always be defined here since middleware protects this route
  const displayName = user?.user_metadata?.full_name ?? user?.email ?? 'User';
  const email = user?.email;

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header with user info */}
      <header className="border-b">
        <div className="container mx-auto flex items-center justify-between px-6 py-4">
          <h1 className="text-xl font-bold">LDIP</h1>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium">{displayName}</p>
              {email && displayName !== email && (
                <p className="text-xs text-muted-foreground">{email}</p>
              )}
            </div>
            <LogoutButton variant="outline" size="sm" />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto flex-1 px-6 py-12">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="space-y-2">
            <h2 className="text-3xl font-bold tracking-tight">Welcome, {displayName}</h2>
            <p className="text-lg text-muted-foreground">
              Legal Document Intelligence Platform — upload documents, extract entities/citations,
              and build matter timelines with verifiable evidence.
            </p>
          </div>

          <div className="rounded-lg border p-6">
            <h3 className="font-semibold">Getting Started</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Dashboard features will be implemented in Epic 9. For now, you are successfully
              authenticated.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
