import { LoginForm } from "@/components/features/auth/LoginForm"

interface LoginPageProps {
  searchParams?: Promise<{ session_expired?: string; password_reset?: string; info?: string }>
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

function VerificationLinkInfoBanner({ show }: { show: boolean }) {
  if (!show) {
    return null;
  }

  return (
    <div className="rounded-md bg-blue-50 p-4 border border-blue-200">
      <p className="text-sm text-blue-800">
        The verification link was opened in a different browser. Your account is ready - please sign in with your email and password.
      </p>
    </div>
  )
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = searchParams ? await searchParams : {}
  const sessionExpired = params?.session_expired === "true"
  const passwordReset = params?.password_reset === "success"
  const verificationLinkExpired = params?.info === "verification_link_expired"
  return (
    <div className="space-y-6">
      <SessionExpiredBanner sessionExpired={sessionExpired} />
      <PasswordResetSuccessBanner passwordReset={passwordReset} />
      <VerificationLinkInfoBanner show={verificationLinkExpired} />
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Welcome Back</h1>
        <p className="text-muted-foreground">Sign in to access your LDIP account</p>
      </div>
      <LoginForm />
    </div>
  )
}
