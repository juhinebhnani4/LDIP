import { createClient } from "@/lib/supabase/server"
import { NextResponse } from "next/server"

export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const error = requestUrl.searchParams.get("error")
  const errorDescription = requestUrl.searchParams.get("error_description")
  const type = requestUrl.searchParams.get("type")
  const next = requestUrl.searchParams.get("next") ?? "/"

  if (error) {
    // For password recovery errors, redirect to forgot-password page
    if (type === "recovery") {
      return NextResponse.redirect(
        new URL("/forgot-password?error=invalid_link", requestUrl.origin)
      )
    }
    return NextResponse.redirect(
      new URL(
        `/login?error=auth_callback_error&message=${encodeURIComponent(errorDescription || error)}`,
        requestUrl.origin
      )
    )
  }

  if (!code) {
    // For password recovery without code, redirect to forgot-password
    if (type === "recovery") {
      return NextResponse.redirect(
        new URL("/forgot-password?error=invalid_link", requestUrl.origin)
      )
    }
    return NextResponse.redirect(new URL("/login?error=auth_callback_error", requestUrl.origin))
  }

  const supabase = await createClient()
  const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

  if (exchangeError) {
    // For password recovery exchange errors, redirect to forgot-password
    if (type === "recovery") {
      return NextResponse.redirect(
        new URL("/forgot-password?error=invalid_link", requestUrl.origin)
      )
    }
    return NextResponse.redirect(
      new URL(
        `/login?error=auth_callback_error&message=${encodeURIComponent(exchangeError.message)}`,
        requestUrl.origin
      )
    )
  }

  // For password recovery, redirect to reset-password page
  if (type === "recovery") {
    return NextResponse.redirect(new URL("/reset-password", requestUrl.origin))
  }

  return NextResponse.redirect(new URL(next, requestUrl.origin))
}
