import { Suspense } from 'react';
import { LoginForm } from '@/components/features/auth/LoginForm';

function LoginFormWrapper() {
  return <LoginForm />;
}

export default function LoginPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Welcome Back</h1>
        <p className="text-muted-foreground">Sign in to access your LDIP account</p>
      </div>
      <Suspense fallback={<div className="text-center">Loading...</div>}>
        <LoginFormWrapper />
      </Suspense>
    </div>
  );
}
