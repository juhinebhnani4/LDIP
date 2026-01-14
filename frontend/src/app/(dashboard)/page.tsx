import { createClient } from '@/lib/supabase/server';

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // User should always be defined here since middleware protects this route
  const displayName = user?.user_metadata?.full_name ?? user?.email ?? 'User';

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Welcome, {displayName}</h1>
        <p className="text-lg text-muted-foreground">
          Legal Document Intelligence Platform — upload documents, extract entities/citations,
          and build matter timelines with verifiable evidence.
        </p>
      </div>

      <div className="rounded-lg border p-6">
        <h2 className="font-semibold">Getting Started</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Dashboard features will be implemented in upcoming stories. Matter cards, activity feed,
          and quick stats are coming soon.
        </p>
      </div>
    </div>
  );
}
