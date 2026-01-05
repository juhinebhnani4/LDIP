import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

// Token refresh threshold in seconds (5 minutes)
const TOKEN_REFRESH_THRESHOLD = 5 * 60;

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Get current session to check token expiry
  const { data: { session } } = await supabase.auth.getSession();

  // Check if token is about to expire and refresh proactively
  if (session?.expires_at) {
    const expiresAt = session.expires_at;
    const now = Math.floor(Date.now() / 1000);
    const timeUntilExpiry = expiresAt - now;

    // Refresh token if it expires within 5 minutes
    if (timeUntilExpiry > 0 && timeUntilExpiry < TOKEN_REFRESH_THRESHOLD) {
      const { data: { session: refreshedSession }, error } = await supabase.auth.refreshSession();

      if (error || !refreshedSession) {
        // Refresh failed - redirect to login with session_expired flag
        const url = request.nextUrl.clone();
        url.pathname = '/login';
        url.searchParams.set('session_expired', 'true');
        return NextResponse.redirect(url);
      }
    }
  }

  // IMPORTANT: Do NOT use getSession() alone - it doesn't validate the token
  // Always use getUser() which validates against Supabase Auth server
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  // Define route protection patterns
  const isProtectedRoute =
    request.nextUrl.pathname.startsWith('/dashboard') ||
    request.nextUrl.pathname.startsWith('/matter') ||
    request.nextUrl.pathname === '/';

  const isAuthRoute =
    request.nextUrl.pathname.startsWith('/login') ||
    request.nextUrl.pathname.startsWith('/signup');

  // Auth callback must be accessible during OAuth flow - don't redirect
  const isAuthCallback = request.nextUrl.pathname.startsWith('/auth/callback');

  // Redirect to login if not authenticated and accessing protected route
  if (!user && isProtectedRoute) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';

    // Add session_expired param if there was an auth error (likely expired session)
    if (userError) {
      url.searchParams.set('session_expired', 'true');
    }

    return NextResponse.redirect(url);
  }

  // Redirect authenticated users away from auth pages (but not callback)
  if (user && isAuthRoute && !isAuthCallback) {
    const url = request.nextUrl.clone();
    url.pathname = '/';
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
