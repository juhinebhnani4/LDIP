import { SignupForm } from '@/components/features/auth/SignupForm';
import { JaanchLogo } from '@/components/ui/jaanch-logo';

export default function SignupPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-4 text-center">
        <div className="flex justify-center">
          <JaanchLogo variant="full" size="lg" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold">Create Account</h1>
          <p className="text-muted-foreground">Sign up to get started</p>
        </div>
      </div>
      <SignupForm />
    </div>
  );
}
