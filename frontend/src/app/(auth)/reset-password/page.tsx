import Link from 'next/link';
import { ResetPasswordForm } from '@/components/features/auth/ResetPasswordForm';

interface ResetPasswordPageProps {
  searchParams?: { error?: string };
}

function ErrorDisplay({ error }: { error: string | undefined }) {
  if (!error) {
    return null;
  }

  const errorMessages: Record<string, string> = {
    invalid_link: 'This reset link has expired or already been used.',
    expired: 'This reset link has expired.',
    no_session: 'Unable to verify your identity. Please request a new reset link.',
  };

  const message = errorMessages[error] || 'An error occurred. Please try again.';

  return (
    <div className="space-y-4">
      <div className="rounded-md bg-destructive/10 p-4 border border-destructive/20">
        <p className="text-sm text-destructive">{message}</p>
      </div>
      <div className="text-center">
        <Link
          href="/forgot-password"
          className="text-sm text-primary hover:underline"
        >
          Request a new reset link
        </Link>
      </div>
    </div>
  );
}

export default function ResetPasswordPage({ searchParams }: ResetPasswordPageProps) {
  const error = searchParams?.error;

  // If there's an error, show error state instead of form
  if (error) {
    return (
      <div className="space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold">Reset Password</h1>
          <p className="text-muted-foreground">There was a problem with your reset link</p>
        </div>
        <ErrorDisplay error={error} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Reset Password</h1>
        <p className="text-muted-foreground">Enter your new password below</p>
      </div>
      <ResetPasswordForm />
    </div>
  );
}
