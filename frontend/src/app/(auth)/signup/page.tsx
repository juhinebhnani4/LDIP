import { SignupForm } from '@/components/features/auth/SignupForm';

export default function SignupPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Create Account</h1>
        <p className="text-muted-foreground">Sign up to get started with LDIP</p>
      </div>
      <SignupForm />
    </div>
  );
}
