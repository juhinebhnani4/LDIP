import { createClient } from "@/lib/supabase/server"
import { NextResponse } from "next/server"

export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const error = requestUrl.searchParams.get("error")
  const errorDescription = requestUrl.searchParams.get("error_description")
  const next = requestUrl.searchParams.get("next") ?? "/"

  if (error) {
    return NextResponse.redirect(
      new URL(
        `/login?error=auth_callback_error&message=${encodeURIComponent(errorDescription || error)}`,
        requestUrl.origin
      )
    )
  }

  if (!code) {
    return NextResponse.redirect(new URL("/login?error=auth_callback_error", requestUrl.origin))
  }

  const supabase = await createClient()
  const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)

  if (exchangeError) {
    return NextResponse.redirect(
      new URL(
        `/login?error=auth_callback_error&message=${encodeURIComponent(exchangeError.message)}`,
        requestUrl.origin
      )
    )
  }

  return NextResponse.redirect(new URL(next, requestUrl.origin))
}
