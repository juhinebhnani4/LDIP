import { createClient } from "@/lib/supabase/server"
import { NextResponse } from "next/server"

/**
 * Handles user logout by clearing Supabase session cookies server-side.
 *
 * Supports both POST (form submission) and GET (direct navigation).
 */
async function handleLogout(request: Request): Promise<NextResponse> {
  const supabase = await createClient()
  await supabase.auth.signOut()

  const { origin } = new URL(request.url)
  return NextResponse.redirect(new URL("/login", origin))
}

export async function POST(request: Request) {
  return handleLogout(request)
}

export async function GET(request: Request) {
  return handleLogout(request)
}
