'use client';

import { useState, useCallback, useEffect } from 'react';
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
import { Skeleton } from '@/components/ui/skeleton';
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

/** Mock collaborators for MVP - loaded on dialog open to simulate API fetch */
const getMockCollaborators = (): Collaborator[] => [
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
 *
 * @param matterId - Matter ID for API calls (used when fetching/inviting collaborators)
 */
export function ShareDialog({ matterId }: ShareDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<CollaboratorRole>('editor');
  const [isInviting, setIsInviting] = useState(false);
  const [isLoadingCollaborators, setIsLoadingCollaborators] = useState(false);
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [emailError, setEmailError] = useState<string | null>(null);

  // For MVP, assume current user is the owner
  const currentUserIsOwner = true;

  // Fetch collaborators when dialog opens
  useEffect(() => {
    if (isOpen && collaborators.length === 0) {
      const fetchCollaborators = async () => {
        setIsLoadingCollaborators(true);
        try {
          // TODO: Replace with actual API call when backend is ready
          // GET /api/matters/${matterId}/members
          void matterId; // Will be used in API call

          // Simulate network delay
          await new Promise((resolve) => setTimeout(resolve, 300));

          setCollaborators(getMockCollaborators());
        } catch (error) {
          console.error('[ShareDialog] Failed to fetch collaborators:', {
            matterId,
            error: error instanceof Error ? error.message : 'Unknown error',
          });
          toast.error('Failed to load collaborators');
        } finally {
          setIsLoadingCollaborators(false);
        }
      };

      fetchCollaborators();
    }
  }, [isOpen, matterId, collaborators.length]);

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
    const emailToInvite = email.trim();

    try {
      // TODO: Replace with actual API call when backend is ready
      // POST /api/matters/${matterId}/members
      // Body: { email: string, role: string }
      void matterId; // Will be used in API call

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Mock: Add new collaborator to list
      const newCollaborator: Collaborator = {
        id: `temp-${Date.now()}`,
        email: emailToInvite,
        name: emailToInvite.split('@')[0], // Use email prefix as name for mock
        role: role,
      };

      setCollaborators((prev) => [...prev, newCollaborator]);
      setEmail('');
      setRole('editor');
      toast.success(`Invitation sent to ${emailToInvite}`);
    } catch (error) {
      console.error('[ShareDialog] Failed to invite collaborator:', {
        matterId,
        email: emailToInvite,
        role,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
      toast.error('Failed to send invite. Please check the email and try again.');
    } finally {
      setIsInviting(false);
    }
  }, [email, role, validateEmail, matterId]);

  const handleRemoveCollaborator = useCallback(async (collaboratorId: string) => {
    const collaboratorToRemove = collaborators.find((c) => c.id === collaboratorId);
    if (!collaboratorToRemove) return;

    if (collaboratorToRemove.role === 'owner') {
      toast.error('Cannot remove the owner');
      return;
    }

    try {
      // TODO: Replace with actual API call when backend is ready
      // DELETE /api/matters/${matterId}/members/${collaboratorId}
      void matterId; // Will be used in API call

      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 300));

      setCollaborators((prev) => prev.filter((c) => c.id !== collaboratorId));
      toast.success(`Removed ${collaboratorToRemove.name} from this matter`);
    } catch (error) {
      console.error('[ShareDialog] Failed to remove collaborator:', {
        matterId,
        collaboratorId,
        collaboratorName: collaboratorToRemove.name,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
      toast.error('Failed to remove collaborator. Please try again.');
    }
  }, [collaborators, matterId]);

  // Keyboard shortcut handler for Cmd/Ctrl+Enter to submit
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && email.trim() && !isInviting) {
        e.preventDefault();
        handleInvite();
      }
    },
    [email, isInviting, handleInvite]
  );

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
      <DialogContent className="sm:max-w-[425px]" onKeyDown={handleKeyDown}>
        <DialogHeader>
          <DialogTitle>Share Matter</DialogTitle>
          <DialogDescription>
            Invite attorneys to collaborate on this matter. They will receive an email invitation.
            <span className="block text-xs mt-1 text-muted-foreground">
              Tip: Press {navigator?.platform?.includes('Mac') ? '⌘' : 'Ctrl'}+Enter to send invite
            </span>
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
            {isLoadingCollaborators ? (
              // Loading skeleton for collaborators
              <>
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center justify-between p-2">
                    <div className="flex items-center gap-3">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <div className="flex flex-col gap-1">
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-3 w-32" />
                      </div>
                    </div>
                    <Skeleton className="h-5 w-16 rounded-full" />
                  </div>
                ))}
              </>
            ) : collaborators.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No collaborators yet. Invite someone to get started.
              </p>
            ) : (
              collaborators.map((collaborator) => {
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
              })
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
