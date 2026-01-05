import { ForgotPasswordForm } from '@/components/features/auth/ForgotPasswordForm';

interface ForgotPasswordPageProps {
  searchParams?: { error?: string };
}

function ErrorBanner({ error }: { error: string | undefined }) {
  if (!error) {
    return null;
  }

  const errorMessages: Record<string, string> = {
    invalid_link: 'This reset link has expired or already been used. Please request a new one.',
  };

  const message = errorMessages[error] || 'An error occurred. Please try again.';

  return (
    <div className="rounded-md bg-destructive/10 p-4 border border-destructive/20">
      <p className="text-sm text-destructive">{message}</p>
    </div>
  );
}

export default function ForgotPasswordPage({ searchParams }: ForgotPasswordPageProps) {
  const error = searchParams?.error;

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Forgot Password?</h1>
        <p className="text-muted-foreground">No worries, we&apos;ll help you reset it</p>
      </div>
      <ForgotPasswordForm />
    </div>
  );
}
