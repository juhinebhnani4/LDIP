import { redirect } from 'next/navigation';
import { Shield } from 'lucide-react';
import { createClient } from '@/lib/supabase/server';
import { LLMQuotaWidget } from '@/components/features/admin/LLMQuotaWidget';

/**
 * Admin Dashboard Page
 *
 * Story gap-5.2: LLM Quota Monitoring Dashboard
 *
 * Admin-only page displaying:
 * - LLM quota monitoring widget
 * - Future: Pipeline management, system health, etc.
 *
 * Access Control:
 * - F1 fix: Server-side check using NEXT_PUBLIC_ADMIN_EMAILS (set at runtime)
 * - Falls back to backend API protection if env var check fails
 * - API endpoints still require backend admin validation
 */

export default async function AdminPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // F1 fix: Use NEXT_PUBLIC_ prefix for runtime access, or skip check entirely
  // and rely on backend API protection (fail-open for UI, fail-closed for data)
  const adminEmails = (process.env.NEXT_PUBLIC_ADMIN_EMAILS || '')
    .split(',')
    .map(e => e.trim().toLowerCase())
    .filter(Boolean);

  const userEmail = user?.email?.toLowerCase() || '';
  const isAdmin = adminEmails.length === 0 || adminEmails.includes(userEmail);

  // Redirect non-admins to main dashboard
  // Note: Even if this check is bypassed, the LLM quota API requires backend admin auth
  if (!isAdmin) {
    redirect('/dashboard');
  }

  return (
    <div className="px-4 sm:px-6 py-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Shield className="size-8 text-primary" />
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Admin Dashboard
            </h1>
            <p className="text-muted-foreground">
              System monitoring and management
            </p>
          </div>
        </div>

        {/* Admin widgets grid */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* LLM Quota Monitoring Widget */}
          <LLMQuotaWidget className="md:col-span-2" />

          {/* Placeholder for future admin widgets */}
          {/* <SystemHealthWidget /> */}
          {/* <PipelineStatusWidget /> */}
        </div>

        {/* Admin info footer */}
        <div className="text-xs text-muted-foreground text-center pt-4 border-t">
          Admin access granted to: {userEmail}
        </div>
      </div>
    </div>
  );
}
