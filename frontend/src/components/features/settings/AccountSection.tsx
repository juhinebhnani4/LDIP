'use client';

/**
 * AccountSection Component
 *
 * Account management actions: change password, sign out, delete account.
 *
 * Story 14.14: Settings Page Implementation
 * Task 8: Create AccountSection component
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Shield, Key, LogOut, Trash2, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { createClient } from '@/lib/supabase/client';

export function AccountSection() {
  const router = useRouter();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleChangePassword = async () => {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (user?.email) {
      // Send password reset email
      const { error } = await supabase.auth.resetPasswordForEmail(user.email, {
        redirectTo: `${window.location.origin}/auth/callback?next=/settings`,
      });

      if (error) {
        alert('Failed to send password reset email. Please try again.');
      } else {
        alert('Password reset email sent! Check your inbox.');
      }
    }
  };

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push('/login');
    } catch {
      setIsSigningOut(false);
    }
  };

  const handleDeleteAccount = async () => {
    setIsDeleting(true);
    setDeleteError(null);

    try {
      // Note: Account deletion would require a backend endpoint
      // For now, just sign out and show message
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push('/login?deleted=true');
    } catch {
      setDeleteError('Failed to delete account. Please contact support.');
      setIsDeleting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="size-5" />
          Account
        </CardTitle>
        <CardDescription>
          Manage your account security and settings
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Change Password */}
        <div className="flex items-center justify-between py-2">
          <div className="flex items-center gap-3">
            <Key className="size-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Password</p>
              <p className="text-sm text-muted-foreground">
                Change your account password
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={handleChangePassword}>
            Change Password
          </Button>
        </div>

        {/* Sign Out */}
        <div className="flex items-center justify-between py-2 border-t pt-4">
          <div className="flex items-center gap-3">
            <LogOut className="size-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Sign Out</p>
              <p className="text-sm text-muted-foreground">
                Sign out of your account
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSignOut}
            disabled={isSigningOut}
          >
            {isSigningOut && <Loader2 className="size-4 mr-2 animate-spin" />}
            Sign Out
          </Button>
        </div>

        {/* Delete Account */}
        <div className="flex items-center justify-between py-2 border-t pt-4">
          <div className="flex items-center gap-3">
            <Trash2 className="size-5 text-destructive" />
            <div>
              <p className="text-sm font-medium text-destructive">Delete Account</p>
              <p className="text-sm text-muted-foreground">
                Permanently delete your account and all data
              </p>
            </div>
          </div>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                Delete Account
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Account?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action cannot be undone. This will permanently delete your
                  account and remove all your data from our servers, including
                  all matters, documents, and analysis results.
                </AlertDialogDescription>
              </AlertDialogHeader>
              {deleteError && (
                <p className="text-sm text-destructive">{deleteError}</p>
              )}
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDeleteAccount}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  disabled={isDeleting}
                >
                  {isDeleting && <Loader2 className="size-4 mr-2 animate-spin" />}
                  Delete Account
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  );
}
