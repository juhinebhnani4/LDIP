import { LoginForm } from "@/components/features/auth/LoginForm"

interface LoginPageProps {
  searchParams?: { session_expired?: string; password_reset?: string }
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

function PasswordResetSuccessBanner({ passwordReset }: { passwordReset: boolean }) {
  if (!passwordReset) {
    return null;
  }

  return (
    <div className="rounded-md bg-green-50 p-4 border border-green-200">
      <p className="text-sm text-green-700">
        Your password has been reset successfully. Please sign in with your new password.
      </p>
    </div>
  )
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  const sessionExpired = searchParams?.session_expired === "true"
  const passwordReset = searchParams?.password_reset === "success"
  return (
    <div className="space-y-6">
      <SessionExpiredBanner sessionExpired={sessionExpired} />
      <PasswordResetSuccessBanner passwordReset={passwordReset} />
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Welcome Back</h1>
        <p className="text-muted-foreground">Sign in to access your LDIP account</p>
      </div>
      <LoginForm />
    </div>
  )
}
