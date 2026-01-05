import { LoginForm } from "@/components/features/auth/LoginForm"

interface LoginPageProps {
  searchParams?: { session_expired?: string }
}

function SessionExpiredBanner({ sessionExpired }: { sessionExpired: boolean }) {
  if (!sessionExpired) {
    return null;
  }

  return (
    <div className="rounded-md bg-yellow-50 p-4 border border-yellow-200">
      <p className="text-sm text-yellow-800">
        Your session has expired. Please sign in again to continue.
      </p>
    </div>
  )
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  const sessionExpired = searchParams?.session_expired === "true"
  return (
    <div className="space-y-6">
      <SessionExpiredBanner sessionExpired={sessionExpired} />
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Welcome Back</h1>
        <p className="text-muted-foreground">Sign in to access your LDIP account</p>
      </div>
      <LoginForm />
    </div>
  )
}
