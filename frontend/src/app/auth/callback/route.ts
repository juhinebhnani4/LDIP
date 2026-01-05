import { createClient } from '@/lib/supabase/server';
import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');
  const error = requestUrl.searchParams.get('error');
  const errorDescription = requestUrl.searchParams.get('error_description');

  console.log('[Auth Callback Route] Processing callback...');
  console.log('[Auth Callback Route] Has code:', !!code);
  console.log('[Auth Callback Route] Error:', error, errorDescription);

  // Handle OAuth errors
  if (error) {
    console.error('[Auth Callback Route] OAuth error:', error, errorDescription);
    return NextResponse.redirect(
      new URL(`/login?error=auth_callback_error&message=${encodeURIComponent(errorDescription || error)}`, requestUrl.origin)
    );
  }

  // Exchange code for session (this works because route handlers have access to cookies)
  if (code) {
    const supabase = await createClient();
    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);

    if (exchangeError) {
      console.error('[Auth Callback Route] Exchange error:', exchangeError.message);
      return NextResponse.redirect(
        new URL(`/login?error=auth_callback_error&message=${encodeURIComponent(exchangeError.message)}`, requestUrl.origin)
      );
    }

    console.log('[Auth Callback Route] Session created successfully');
  }

  // Redirect to home page after successful auth
  return NextResponse.redirect(new URL('/', requestUrl.origin));
}
