import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ShareDialog } from './ShareDialog';
import { toast } from 'sonner';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

// Type cast for mocked toast
const mockToast = toast as unknown as {
  success: ReturnType<typeof vi.fn>;
  error: ReturnType<typeof vi.fn>;
  info: ReturnType<typeof vi.fn>;
};

// Mock Tooltip provider
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

describe('ShareDialog', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
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

    // Check for mock collaborators
    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('john.smith@lawfirm.com')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
  });

  it('shows owner badge for owner', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

    // Look for Owner badge
    const ownerBadges = screen.getAllByText('Owner');
    expect(ownerBadges.length).toBeGreaterThan(0);
  });

  it('shows Editor and Viewer badges for respective roles', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

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

    // Should not have remove button for John Smith (owner)
    expect(screen.queryByRole('button', { name: /remove john smith/i })).not.toBeInTheDocument();
  });

  it('validates duplicate email', async () => {
    const user = userEvent.setup();
    render(<ShareDialog matterId={mockMatterId} />);

    const shareButton = screen.getByRole('button', { name: /share matter/i });
    await user.click(shareButton);

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

    // Should show loading text (briefly)
    expect(screen.getByText(/sending/i)).toBeInTheDocument();
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

    // Initially Jane Doe should be visible
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();

    // Remove Jane Doe
    const removeButton = screen.getByRole('button', { name: /remove jane doe/i });
    await user.click(removeButton);

    await waitFor(() => {
      expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument();
    });
  });
});
