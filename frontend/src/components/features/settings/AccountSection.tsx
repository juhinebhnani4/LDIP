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
import { Shield, Key, LogOut, Trash2, Loader2, Monitor } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { api } from '@/lib/api/client';

export function AccountSection() {
  const router = useRouter();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isSigningOutAll, setIsSigningOutAll] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [signOutAllSuccess, setSignOutAllSuccess] = useState(false);

  const CONFIRMATION_TEXT = 'DELETE';

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
      await fetch('/auth/logout', { method: 'POST' });
      router.push('/login');
    } catch {
      setIsSigningOut(false);
    }
  };

  const handleSignOutAll = async () => {
    setIsSigningOutAll(true);
    setSignOutAllSuccess(false);
    try {
      await api.post('/api/users/me/sign-out-all', {});
      setSignOutAllSuccess(true);

      // Sign out locally after 2 seconds
      setTimeout(async () => {
        const supabase = createClient();
        await supabase.auth.signOut();
        router.push('/login');
      }, 2000);
    } catch {
      alert('Failed to sign out from all devices. Please try again.');
      setIsSigningOutAll(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmation !== CONFIRMATION_TEXT) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      // Call backend to delete account
      await api.delete('/api/users/me');

      // Sign out after deletion
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push('/login?deleted=true');
    } catch (error) {
      setDeleteError('Failed to delete account. Please contact support.');
      setIsDeleting(false);
    }
  };

  const handleDialogOpenChange = (open: boolean) => {
    setIsDialogOpen(open);
    if (!open) {
      setDeleteConfirmation('');
      setDeleteError(null);
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

        {/* Sign Out All Devices */}
        <div className="flex items-center justify-between py-2 border-t pt-4">
          <div className="flex items-center gap-3">
            <Monitor className="size-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Sign Out All Devices</p>
              <p className="text-sm text-muted-foreground">
                Sign out from all logged in devices
              </p>
              {signOutAllSuccess && (
                <p className="text-sm text-green-600 mt-1">
                  Successfully signed out all devices. Redirecting...
                </p>
              )}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSignOutAll}
            disabled={isSigningOutAll}
          >
            {isSigningOutAll && <Loader2 className="size-4 mr-2 animate-spin" />}
            Sign Out All
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

          <AlertDialog open={isDialogOpen} onOpenChange={handleDialogOpenChange}>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                Delete Account
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action cannot be undone. This will permanently delete your
                  account and remove all your data from our servers, including
                  all matters, documents, and analysis results.
                </AlertDialogDescription>
              </AlertDialogHeader>

              <div className="space-y-2 py-2">
                <Label htmlFor="delete-confirmation" className="text-sm">
                  Type <span className="font-mono font-bold">{CONFIRMATION_TEXT}</span> to confirm
                </Label>
                <Input
                  id="delete-confirmation"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  placeholder={CONFIRMATION_TEXT}
                  className="font-mono"
                />
              </div>

              {deleteError && (
                <p className="text-sm text-destructive">{deleteError}</p>
              )}
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDeleteAccount}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  disabled={isDeleting || deleteConfirmation !== CONFIRMATION_TEXT}
                  aria-label="Confirm delete"
                >
                  {isDeleting && <Loader2 className="size-4 mr-2 animate-spin" />}
                  Confirm Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  );
}
