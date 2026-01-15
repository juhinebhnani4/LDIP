'use client';

import { useState, useCallback } from 'react';
import { Users, X, Loader2, Crown, UserCheck, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import type { MatterRole } from '@/types/matter';

/** Collaborator roles available for invitation */
const COLLABORATOR_ROLES = ['editor', 'viewer'] as const;
type CollaboratorRole = (typeof COLLABORATOR_ROLES)[number];

/** Collaborator representation */
interface Collaborator {
  id: string;
  email: string;
  name: string;
  role: MatterRole;
  avatarUrl?: string;
}

/** Role configuration for display */
const ROLE_CONFIG = {
  owner: {
    label: 'Owner',
    icon: Crown,
    color: 'text-amber-600',
    badgeVariant: 'default' as const,
  },
  editor: {
    label: 'Editor',
    icon: UserCheck,
    color: 'text-blue-600',
    badgeVariant: 'secondary' as const,
  },
  viewer: {
    label: 'Viewer',
    icon: Eye,
    color: 'text-gray-600',
    badgeVariant: 'outline' as const,
  },
} as const;

/** Mock collaborators for MVP */
const MOCK_COLLABORATORS: Collaborator[] = [
  {
    id: '1',
    email: 'john.smith@lawfirm.com',
    name: 'John Smith',
    role: 'owner',
  },
  {
    id: '2',
    email: 'jane.doe@lawfirm.com',
    name: 'Jane Doe',
    role: 'editor',
  },
  {
    id: '3',
    email: 'bob.wilson@lawfirm.com',
    name: 'Bob Wilson',
    role: 'viewer',
  },
];

/** Email validation regex */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface ShareDialogProps {
  /** Matter ID for sharing context */
  matterId: string;
}

/**
 * Share Dialog Component
 *
 * Allows users to share matters with other attorneys.
 * - Email input with role selection
 * - Display of current collaborators
 * - Owner badge and remove functionality
 *
 * Story 10A.1: Workspace Shell Header - AC #4
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function ShareDialog({ matterId }: ShareDialogProps) {
  // matterId will be used when API endpoints are implemented
  const [isOpen, setIsOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<CollaboratorRole>('editor');
  const [isInviting, setIsInviting] = useState(false);
  const [collaborators, setCollaborators] = useState<Collaborator[]>(MOCK_COLLABORATORS);
  const [emailError, setEmailError] = useState<string | null>(null);

  // For MVP, assume current user is the owner
  const currentUserIsOwner = true;

  const validateEmail = useCallback((emailToValidate: string): boolean => {
    if (!emailToValidate.trim()) {
      setEmailError('Email is required');
      return false;
    }
    if (!EMAIL_REGEX.test(emailToValidate)) {
      setEmailError('Please enter a valid email address');
      return false;
    }
    if (collaborators.some((c) => c.email.toLowerCase() === emailToValidate.toLowerCase())) {
      setEmailError('This email is already a collaborator');
      return false;
    }
    setEmailError(null);
    return true;
  }, [collaborators]);

  const handleInvite = useCallback(async () => {
    if (!validateEmail(email)) {
      return;
    }

    setIsInviting(true);

    try {
      // TODO: Replace with actual API call when backend is ready
      // POST /api/matters/{matter_id}/members
      // Body: { email: string, role: string }

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Mock: Add new collaborator to list
      const newCollaborator: Collaborator = {
        id: `temp-${Date.now()}`,
        email: email.trim(),
        name: email.split('@')[0], // Use email prefix as name for mock
        role: role,
      };

      setCollaborators((prev) => [...prev, newCollaborator]);
      setEmail('');
      setRole('editor');
      toast.success(`Invitation sent to ${email}`);
    } catch {
      toast.error('Failed to send invite. Please check the email and try again.');
    } finally {
      setIsInviting(false);
    }
  }, [email, role, validateEmail]);

  const handleRemoveCollaborator = useCallback(async (collaboratorId: string) => {
    const collaboratorToRemove = collaborators.find((c) => c.id === collaboratorId);
    if (!collaboratorToRemove) return;

    if (collaboratorToRemove.role === 'owner') {
      toast.error('Cannot remove the owner');
      return;
    }

    try {
      // TODO: Replace with actual API call when backend is ready
      // DELETE /api/matters/{matter_id}/members/{member_id}

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 300));

      setCollaborators((prev) => prev.filter((c) => c.id !== collaboratorId));
      toast.success(`Removed ${collaboratorToRemove.name} from this matter`);
    } catch {
      toast.error('Failed to remove collaborator. Please try again.');
    }
  }, [collaborators]);

  const getInitials = (name: string): string => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DialogTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Share matter">
              <Users className="h-4 w-4" />
            </Button>
          </DialogTrigger>
        </TooltipTrigger>
        <TooltipContent>
          <p>Share</p>
        </TooltipContent>
      </Tooltip>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Share Matter</DialogTitle>
          <DialogDescription>
            Invite attorneys to collaborate on this matter. They will receive an email invitation.
          </DialogDescription>
        </DialogHeader>

        {/* Invite form */}
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="email">Email address</Label>
            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  id="email"
                  type="email"
                  placeholder="attorney@lawfirm.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (emailError) setEmailError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleInvite();
                    }
                  }}
                  className={emailError ? 'border-red-500' : ''}
                  aria-invalid={!!emailError}
                  aria-describedby={emailError ? 'email-error' : undefined}
                />
                {emailError && (
                  <p id="email-error" className="text-sm text-red-500 mt-1">
                    {emailError}
                  </p>
                )}
              </div>
              <Select value={role} onValueChange={(value) => setRole(value as CollaboratorRole)}>
                <SelectTrigger className="w-[110px]" aria-label="Select role">
                  <SelectValue placeholder="Role" />
                </SelectTrigger>
                <SelectContent>
                  {COLLABORATOR_ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {ROLE_CONFIG[r].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button onClick={handleInvite} disabled={isInviting || !email.trim()}>
            {isInviting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Sending...
              </>
            ) : (
              'Invite'
            )}
          </Button>
        </div>

        <Separator />

        {/* Collaborators list */}
        <div className="space-y-3">
          <Label>Current Collaborators</Label>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {collaborators.map((collaborator) => {
              const roleConfig = ROLE_CONFIG[collaborator.role];
              const RoleIcon = roleConfig.icon;

              return (
                <div
                  key={collaborator.id}
                  className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="text-xs">
                        {getInitials(collaborator.name)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col">
                      <span className="text-sm font-medium">{collaborator.name}</span>
                      <span className="text-xs text-muted-foreground">{collaborator.email}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={roleConfig.badgeVariant} className="flex items-center gap-1">
                      <RoleIcon className={`h-3 w-3 ${roleConfig.color}`} />
                      <span>{roleConfig.label}</span>
                    </Badge>
                    {currentUserIsOwner && collaborator.role !== 'owner' && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => handleRemoveCollaborator(collaborator.id)}
                        aria-label={`Remove ${collaborator.name}`}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
