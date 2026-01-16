import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import type { MatterMember } from '@/types/matter';

// Mock Supabase client BEFORE importing components (required by api/client.ts)
vi.mock('@/lib/supabase/client', () => ({
  createClient: vi.fn(() => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      refreshSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  })),
}));

// Mock sonner toast with proper vitest types
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

// Mock matters API
vi.mock('@/lib/api/matters', () => ({
  getMembers: vi.fn(),
  inviteMember: vi.fn(),
  removeMember: vi.fn(),
}));

// Mock useUser hook - current user is the owner (user-1)
vi.mock('@/hooks', () => ({
  useUser: () => ({ user: { id: 'user-1' }, loading: false, error: null }),
}));

// Import AFTER mocks are defined (vitest hoists vi.mock calls automatically, but for clarity)
import { ShareDialog } from './ShareDialog';
import { getMembers, inviteMember, removeMember } from '@/lib/api/matters';
import { ApiError } from '@/lib/api/client';

// Properly typed mock toast using vitest's Mock type
const mockToast = toast as unknown as {
  success: Mock;
  error: Mock;
  info: Mock;
};

// Properly typed mock API functions
const mockGetMembers = getMembers as Mock;
const mockInviteMember = inviteMember as Mock;
const mockRemoveMember = removeMember as Mock;

// Mock member data matching backend MatterMember type
const mockMembers: MatterMember[] = [
  {
    id: 'member-1',
    userId: 'user-1',
    email: 'john.smith@lawfirm.com',
    fullName: 'John Smith',
    role: 'owner',
    invitedBy: null,
    invitedAt: null,
  },
  {
    id: 'member-2',
    userId: 'user-2',
    email: 'jane.doe@lawfirm.com',
    fullName: 'Jane Doe',
    role: 'editor',
    invitedBy: 'user-1',
    invitedAt: '2026-01-10T10:00:00Z',
  },
  {
    id: 'member-3',
    userId: 'user-3',
    email: 'bob.wilson@lawfirm.com',
    fullName: 'Bob Wilson',
    role: 'viewer',
    invitedBy: 'user-1',
    invitedAt: '2026-01-11T10:00:00Z',
  },
];

// Mock Tooltip provider
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

// Mock Skeleton component for loading states
vi.mock('@/components/ui/skeleton', () => ({
  Skeleton: ({ className }: { className: string }) => (
    <div data-testid="skeleton" className={className} />
  ),
}));

describe('ShareDialog', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
    // Default: getMembers returns mock data
    mockGetMembers.mockResolvedValue(mockMembers);
    // Default: inviteMember succeeds
    mockInviteMember.mockImplementation(async (_matterId: string, email: string, role: string) => {
      const emailPrefix = email.split('@')[0] ?? email;
      return {
        id: `member-new-${Date.now()}`,
        userId: `user-new-${Date.now()}`,
        email,
        fullName: emailPrefix,
        role,
        invitedBy: 'user-1',
        invitedAt: new Date().toISOString(),
      } as MatterMember;
    });
    // Default: removeMember succeeds
    mockRemoveMember.mockResolvedValue(undefined);
  });

  it('renders share button with correct aria-label', () => {
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    expect(shareButton).toBeInTheDocument();
  });

  it('opens dialog when triggered', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Share Matter')).toBeInTheDocument();
  });

  it('displays email input field', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/attorney@lawfirm.com/i)).toBeInTheDocument();
  });

  it('displays role selector', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Check for role selector
    expect(screen.getByRole('combobox', { name: /select role/i })).toBeInTheDocument();
  });

  it('disables invite button when email is empty', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Invite button should be disabled when email is empty
    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    expect(inviteButton).toBeDisabled();
  });

  it('validates email format', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Enter invalid email
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'invalid-email');

    // Click invite
    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument();
    });
  });

  it('sends invite on button click with valid email', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Enter valid email
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'new.attorney@lawfirm.com');

    // Click invite
    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalledWith('Invitation sent to new.attorney@lawfirm.com');
    });
  });

  it('displays current collaborators', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load (async fetch on dialog open)
    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });
    expect(screen.getByText('john.smith@lawfirm.com')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
  });

  it('shows owner badge for owner', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load, then look for Owner badge
    await waitFor(() => {
      const ownerBadges = screen.getAllByText('Owner');
      expect(ownerBadges.length).toBeGreaterThan(0);
    });
  });

  it('shows Editor and Viewer badges for respective roles', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });

    // Editor appears both in role selector and in collaborator badge
    // Viewer only appears in collaborator badge
    const editorTexts = screen.getAllByText('Editor');
    expect(editorTexts.length).toBeGreaterThanOrEqual(1);

    const viewerTexts = screen.getAllByText('Viewer');
    expect(viewerTexts.length).toBeGreaterThanOrEqual(1);
  });

  it('allows owner to remove collaborators (non-owners)', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });

    // Find remove button for Jane Doe (editor)
    const removeButton = screen.getByRole('button', { name: /remove jane doe/i });
    expect(removeButton).toBeInTheDocument();

    await user.click(removeButton);

    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalledWith('Removed Jane Doe from this matter');
    });
  });

  it('does not show remove button for owner', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });

    // Should not have remove button for John Smith (owner)
    expect(screen.queryByRole('button', { name: /remove john smith/i })).not.toBeInTheDocument();
  });

  it('validates duplicate email', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });

    // Enter existing collaborator email
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'john.smith@lawfirm.com');

    // Click invite
    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(screen.getByText('This email is already a collaborator')).toBeInTheDocument();
    });
  });

  it('clears email input after successful invite', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Enter valid email
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'new.attorney@lawfirm.com');

    // Click invite
    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(emailInput).toHaveValue('');
    });
  });

  it('shows loading state while sending invite', async () => {
    // Use a delayed mock to observe loading state
    let resolveInvite: (value: MatterMember) => void;
    mockInviteMember.mockImplementationOnce(() => new Promise((resolve) => {
      resolveInvite = resolve;
    }));

    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Enter valid email
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'new.attorney@lawfirm.com');

    // Click invite
    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    // Should show loading text while waiting
    expect(screen.getByText(/sending/i)).toBeInTheDocument();

    // Resolve the invite to clean up
    resolveInvite!({
      id: 'member-new',
      userId: 'user-new',
      email: 'new.attorney@lawfirm.com',
      fullName: 'new.attorney',
      role: 'editor',
      invitedBy: 'user-1',
      invitedAt: new Date().toISOString(),
    });
  });

  it('adds new collaborator to list after invite', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Enter valid email
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'new.attorney@lawfirm.com');

    // Click invite
    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(screen.getByText('new.attorney@lawfirm.com')).toBeInTheDocument();
    });
  });

  it('supports keyboard navigation to invite', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Enter email and press Enter
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'keyboard.test@lawfirm.com{Enter}');

    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalledWith('Invitation sent to keyboard.test@lawfirm.com');
    });
  });

  it('removes collaborator from list after removal', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load, then verify Jane Doe is visible
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });

    // Remove Jane Doe
    const removeButton = screen.getByRole('button', { name: /remove jane doe/i });
    await user.click(removeButton);

    await waitFor(() => {
      expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument();
    });
  });

  // API Error State Tests
  it('shows error toast when fetch collaborators fails', async () => {
    mockGetMembers.mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Failed to load collaborators');
    });
  });

  it('shows validation error when member already exists', async () => {
    mockInviteMember.mockRejectedValueOnce(
      new ApiError('MEMBER_ALREADY_EXISTS', 'User is already a member', 409)
    );
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });

    // Enter email and invite
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'existing@lawfirm.com');

    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(screen.getByText('This email is already a collaborator')).toBeInTheDocument();
    });
  });

  it('shows validation error when user not found', async () => {
    mockInviteMember.mockRejectedValueOnce(
      new ApiError('USER_NOT_FOUND', 'User not found', 404)
    );
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });

    // Enter email and invite
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'unknown@lawfirm.com');

    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(screen.getByText('User not found. They must have an account first.')).toBeInTheDocument();
    });
  });

  it('shows error toast when remove fails with network error', async () => {
    mockRemoveMember.mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });

    // Try to remove Jane Doe
    const removeButton = screen.getByRole('button', { name: /remove jane doe/i });
    await user.click(removeButton);

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Failed to remove collaborator. Please try again.');
    });

    // Jane Doe should still be in the list (not removed due to error)
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
  });

  it('calls getMembers API when dialog opens', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    await waitFor(() => {
      expect(mockGetMembers).toHaveBeenCalledWith(mockMatterId);
    });
  });

  it('calls inviteMember API with correct parameters', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });

    // Enter email and invite
    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, 'new.attorney@lawfirm.com');

    const inviteButton = screen.getByRole('button', { name: /^invite$/i });
    await user.click(inviteButton);

    await waitFor(() => {
      expect(mockInviteMember).toHaveBeenCalledWith(mockMatterId, 'new.attorney@lawfirm.com', 'editor');
    });
  });

  it('calls removeMember API with correct parameters', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Wait for collaborators to load
    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });

    // Remove Jane Doe
    const removeButton = screen.getByRole('button', { name: /remove jane doe/i });
    await user.click(removeButton);

    await waitFor(() => {
      // Should use userId (user-2), not membership id (member-2)
      expect(mockRemoveMember).toHaveBeenCalledWith(mockMatterId, 'user-2');
    });
  });
});
