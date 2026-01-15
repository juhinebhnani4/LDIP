import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EditableMatterName } from './EditableMatterName';
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

// Mock matterStore data
const mockMatterData = {
  matters: [
    {
      id: 'test-matter-123',
      title: 'Test Matter',
      description: null,
      status: 'active' as const,
      role: 'owner' as const,
      memberCount: 1,
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
      pageCount: 10,
      documentCount: 5,
      verificationPercent: 80,
      issueCount: 0,
      processingStatus: 'ready' as const,
    },
  ],
  currentMatter: null,
  updateMatterName: vi.fn(),
  fetchMatter: vi.fn(),
};

vi.mock('@/stores/matterStore', () => ({
  useMatterStore: (selector: (state: typeof mockMatterData) => unknown) => selector(mockMatterData),
}));

describe('EditableMatterName', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
    mockMatterData.updateMatterName.mockResolvedValue(undefined);
    mockMatterData.fetchMatter.mockResolvedValue(undefined);
  });

  it('displays matter name in view mode', () => {
    render(<EditableMatterName matterId={mockMatterId} />);

    expect(screen.getByRole('heading', { level: 1, name: /test matter/i })).toBeInTheDocument();
  });

  it('displays "Untitled Matter" when matter not found', () => {
    render(<EditableMatterName matterId="unknown-matter" />);

    expect(screen.getByRole('heading', { level: 1, name: /untitled matter/i })).toBeInTheDocument();
  });

  it('fetches matter when not found in store', () => {
    render(<EditableMatterName matterId="unknown-matter" />);

    expect(mockMatterData.fetchMatter).toHaveBeenCalledWith('unknown-matter');
  });

  it('does not fetch matter when already in store', () => {
    render(<EditableMatterName matterId={mockMatterId} />);

    expect(mockMatterData.fetchMatter).not.toHaveBeenCalled();
  });

  it('shows edit icon on hover', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });

    // Initially hidden (opacity-0)
    const pencilIcon = nameContainer.querySelector('svg');
    expect(pencilIcon).toHaveClass('opacity-0');

    // Hover to show
    await user.hover(nameContainer);
    expect(pencilIcon).toHaveClass('opacity-100');
  });

  it('switches to edit mode on click', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Should show input field
    expect(screen.getByRole('textbox', { name: /matter name/i })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /matter name/i })).toHaveValue('Test Matter');
  });

  it('switches to edit mode on Enter key', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    nameContainer.focus();
    await user.keyboard('{Enter}');

    expect(screen.getByRole('textbox', { name: /matter name/i })).toBeInTheDocument();
  });

  it('saves on Enter key', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Change value and press Enter
    const input = screen.getByRole('textbox', { name: /matter name/i });
    await user.clear(input);
    await user.type(input, 'New Matter Name{Enter}');

    await waitFor(() => {
      expect(mockMatterData.updateMatterName).toHaveBeenCalledWith(mockMatterId, 'New Matter Name');
    });
  });

  it('cancels on Escape key', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Change value and press Escape
    const input = screen.getByRole('textbox', { name: /matter name/i });
    await user.clear(input);
    await user.type(input, 'Changed Name{Escape}');

    // Should return to view mode without saving
    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
    expect(mockMatterData.updateMatterName).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { level: 1, name: /test matter/i })).toBeInTheDocument();
  });

  it('shows loading state while saving', async () => {
    // Make updateMatterName take some time
    mockMatterData.updateMatterName.mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 500))
    );

    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Change value and save
    const input = screen.getByRole('textbox', { name: /matter name/i });
    await user.clear(input);
    await user.type(input, 'New Name{Enter}');

    // Should show loading spinner
    expect(screen.getByLabelText(/saving/i)).toBeInTheDocument();
  });

  it('handles save error gracefully', async () => {
    mockMatterData.updateMatterName.mockRejectedValue(new Error('Save failed'));

    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Change value and save
    const input = screen.getByRole('textbox', { name: /matter name/i });
    await user.clear(input);
    await user.type(input, 'New Name{Enter}');

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith(
        'Failed to update matter name. Please try again.'
      );
    });
  });

  it('validates name is not empty', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Clear and try to save empty
    const input = screen.getByRole('textbox', { name: /matter name/i });
    await user.clear(input);
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Matter name cannot be empty');
    });
    expect(mockMatterData.updateMatterName).not.toHaveBeenCalled();
  });

  it('input has max length attribute to prevent exceeding limit', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Verify input has maxLength attribute set to 100
    const input = screen.getByRole('textbox', { name: /matter name/i });
    expect(input).toHaveAttribute('maxLength', '100');

    // Type a long name - browser will truncate at maxLength
    const longName = 'a'.repeat(150);
    await user.clear(input);
    await user.type(input, longName);

    // Value should be truncated to 100 characters
    expect(input).toHaveValue('a'.repeat(100));
  });

  it('does not save when name unchanged', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Press Enter without changing
    await user.keyboard('{Enter}');

    // Should not call update
    expect(mockMatterData.updateMatterName).not.toHaveBeenCalled();
  });

  it('shows save button in edit mode', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    expect(screen.getByRole('button', { name: /save name/i })).toBeInTheDocument();
  });

  it('shows cancel button in edit mode', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    expect(screen.getByRole('button', { name: /cancel editing/i })).toBeInTheDocument();
  });

  it('cancels when cancel button clicked', async () => {
    const user = userEvent.setup();
    render(<EditableMatterName matterId={mockMatterId} />);

    // Enter edit mode
    const nameContainer = screen.getByRole('button', { name: /edit matter name/i });
    await user.click(nameContainer);

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: /cancel editing/i });
    await user.click(cancelButton);

    // Should return to view mode
    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
    expect(mockMatterData.updateMatterName).not.toHaveBeenCalled();
  });
});
