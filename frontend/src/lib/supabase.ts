/**
 * Supabase Client Re-exports
 *
 * This file provides backward compatibility and convenience exports.
 * For new code, prefer importing directly from:
 * - '@/lib/supabase/client' for browser/client components
 * - '@/lib/supabase/server' for server components and actions
 */

// Re-export client creator for browser contexts
export { createClient as createBrowserClient } from './supabase/client';

// Note: Server client cannot be re-exported here as it uses 'server-only'
// Import directly from '@/lib/supabase/server' in server components

// Configuration check utility
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);
