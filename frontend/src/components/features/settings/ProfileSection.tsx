'use client';

/**
 * ProfileSection Component
 *
 * Displays and allows editing of user profile information.
 *
 * Story 14.14: Settings Page Implementation
 * Task 5: Create ProfileSection component
 */

import { useState, useRef } from 'react';
import { User, Mail, Save, Loader2, Camera } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useUserProfile } from '@/hooks/useUserProfile';
import { Skeleton } from '@/components/ui/skeleton';

function getInitials(name: string | null, email: string): string {
  if (name) {
    const parts = name.split(' ').filter(Boolean);
    if (parts.length >= 2) {
      const first = parts[0];
      const second = parts[1];
      if (first && second && first[0] && second[0]) {
        return `${first[0]}${second[0]}`.toUpperCase();
      }
    }
    return name.slice(0, 2).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}

export function ProfileSection() {
  const { profile, isLoading, updateProfile, isUpdating, updateError } = useUserProfile();
  const [fullName, setFullName] = useState<string>('');
  const [hasChanges, setHasChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Initialize form when profile loads
  if (profile && !hasChanges && fullName === '') {
    setFullName(profile.fullName ?? '');
  }

  const handleNameChange = (value: string) => {
    setFullName(value);
    setHasChanges(value !== (profile?.fullName ?? ''));
    setSaveSuccess(false);
  };

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleAvatarChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert('Image must be less than 2MB');
      return;
    }

    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setAvatarPreview(e.target?.result as string);
    };
    reader.readAsDataURL(file);

    // Upload avatar
    setIsUploadingAvatar(true);
    try {
      // Convert to base64 data URL for storage
      // In production, this would upload to a storage service
      const dataUrl = await new Promise<string>((resolve) => {
        const r = new FileReader();
        r.onload = () => resolve(r.result as string);
        r.readAsDataURL(file);
      });

      await updateProfile({ avatarUrl: dataUrl });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      setAvatarPreview(null);
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const handleSave = async () => {
    try {
      await updateProfile({ fullName: fullName || undefined });
      setHasChanges(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch {
      // Error handled by hook
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48 mt-1" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="size-5" />
          Profile
        </CardTitle>
        <CardDescription>
          Manage your personal information
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Avatar */}
        <div className="flex items-center gap-4">
          <div className="relative">
            <Avatar className="size-16">
              <AvatarImage
                src={avatarPreview ?? profile?.avatarUrl ?? undefined}
                alt={profile?.fullName ?? 'User'}
              />
              <AvatarFallback className="text-lg">
                {getInitials(profile?.fullName ?? null, profile?.email ?? '')}
              </AvatarFallback>
            </Avatar>
            <button
              onClick={handleAvatarClick}
              disabled={isUploadingAvatar}
              className="absolute -bottom-1 -right-1 flex items-center justify-center size-7 rounded-full bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 disabled:opacity-50"
              aria-label="Change avatar"
            >
              {isUploadingAvatar ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Camera className="size-3.5" />
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleAvatarChange}
              className="hidden"
              aria-label="Upload avatar image"
            />
          </div>
          <div>
            <p className="text-sm font-medium">{profile?.fullName || 'No name set'}</p>
            <p className="text-sm text-muted-foreground">{profile?.email}</p>
            <p className="text-xs text-muted-foreground mt-1">Click the camera icon to change your photo</p>
          </div>
        </div>

        {/* Email (read-only) */}
        <div className="space-y-2">
          <Label htmlFor="email" className="flex items-center gap-2">
            <Mail className="size-4" />
            Email
          </Label>
          <Input
            id="email"
            type="email"
            value={profile?.email ?? ''}
            disabled
            className="bg-muted"
          />
          <p className="text-xs text-muted-foreground">
            Email cannot be changed
          </p>
        </div>

        {/* Full Name (editable) */}
        <div className="space-y-2">
          <Label htmlFor="fullName">Full Name</Label>
          <Input
            id="fullName"
            type="text"
            value={fullName}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Enter your full name"
            maxLength={100}
          />
        </div>

        {/* Save button */}
        <div className="flex items-center justify-between">
          <div>
            {updateError && (
              <p className="text-sm text-destructive">
                Failed to save changes. Please try again.
              </p>
            )}
            {saveSuccess && (
              <p className="text-sm text-green-600">
                Profile updated successfully!
              </p>
            )}
          </div>
          <Button
            onClick={handleSave}
            disabled={!hasChanges || isUpdating}
          >
            {isUpdating ? (
              <Loader2 className="size-4 mr-2 animate-spin" />
            ) : (
              <Save className="size-4 mr-2" />
            )}
            Save Changes
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
