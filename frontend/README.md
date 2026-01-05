# LDIP Frontend (Next.js)

Legal Document Intelligence Platform (LDIP) frontend built with **Next.js App Router**, **Tailwind CSS**, and **shadcn/ui**.

## Run locally

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

App: `http://localhost:3000`

## Environment variables

Required:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL` (FastAPI backend; default `http://localhost:8000`)

## Useful commands

```bash
npm run lint
npm run build
```

## Authentication Setup

The frontend uses **Supabase Auth** with SSR support via `@supabase/ssr`. Three authentication methods are supported:

1. **Email/Password** - Standard signup and login
2. **Magic Link** - Passwordless email authentication
3. **Google OAuth** - Sign in with Google

### Supabase Dashboard Configuration

Before running the app, configure your Supabase project:

1. **Authentication > URL Configuration**
   - Site URL: `http://localhost:3000` (development) or your production domain
   - Redirect URLs: Add `http://localhost:3000/auth/callback`

2. **Authentication > Providers**
   - Email: Enabled by default
   - Google: Enable and add OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

3. **Database > Migrations**
   - Run the migration in `supabase/migrations/20260104000000_create_users_table.sql`
   - This creates the `public.users` table with RLS policies

### Google OAuth Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 Client ID (Web application type)
3. Add Authorized JavaScript origins: `http://localhost:3000`
4. Add Authorized redirect URIs: `https://<your-project-ref>.supabase.co/auth/v1/callback`
5. Copy Client ID and Client Secret to Supabase dashboard

### Protected Routes

The middleware (`src/middleware.ts`) protects these routes:
- `/` - Dashboard (requires auth)
- `/dashboard/*` - All dashboard pages
- `/matter/*` - All matter pages

Unauthenticated users are redirected to `/login`.

## Notes

- Routing uses **App Router route groups** (`(auth)`, `(dashboard)`, `(matter)`), which do **not** appear in the URL.
- Supabase config is client-side only; never put service-role keys in the frontend.
- **ALWAYS use `getUser()` not `getSession()`** for auth checks - `getSession()` doesn't validate tokens server-side.
