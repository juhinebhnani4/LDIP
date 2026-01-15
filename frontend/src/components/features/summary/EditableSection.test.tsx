/**
 * EditableSection Component Tests
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #3)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EditableSection } from './EditableSection';

describe('EditableSection', () => {
  const defaultProps = {
    sectionType: 'subject_matter' as const,
    sectionId: 'test-section-123',
    content: 'Original content from AI',
    onSave: vi.fn(),
    onRegenerate: vi.fn(),
    children: <div data-testid="child-content">Child Content</div>,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders content in view mode by default', () => {
    render(<EditableSection {...defaultProps} />);

    expect(screen.getByTestId('child-content')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('shows edit button on hover', async () => {
    const user = userEvent.setup();

    render(<EditableSection {...defaultProps} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
  });

  it('enters edit mode when edit button clicked', async () => {
    const user = userEvent.setup();

    render(<EditableSection {...defaultProps} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toHaveValue('Original content from AI');
  });

  it('shows save and cancel buttons in edit mode', async () => {
    const user = userEvent.setup();

    render(<EditableSection {...defaultProps} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('saves content when save clicked', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(<EditableSection {...defaultProps} onSave={onSave} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    const textarea = screen.getByRole('textbox');
    await user.clear(textarea);
    await user.type(textarea, 'Updated content');

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    expect(onSave).toHaveBeenCalledWith('Updated content');
  });

  it('discards changes when cancel clicked', async () => {
    const user = userEvent.setup();

    render(<EditableSection {...defaultProps} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    const textarea = screen.getByRole('textbox');
    await user.clear(textarea);
    await user.type(textarea, 'Changed content');

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Should be back in view mode
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getByTestId('child-content')).toBeInTheDocument();
  });

  it('shows regenerate button in edit mode', async () => {
    const user = userEvent.setup();

    render(<EditableSection {...defaultProps} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument();
  });

  it('calls onRegenerate when regenerate clicked', async () => {
    const user = userEvent.setup();
    const onRegenerate = vi.fn().mockResolvedValue(undefined);

    render(<EditableSection {...defaultProps} onRegenerate={onRegenerate} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    const regenerateButton = screen.getByRole('button', { name: /regenerate/i });
    await user.click(regenerateButton);

    expect(onRegenerate).toHaveBeenCalledTimes(1);
  });

  it('shows loading state while saving', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn(() => new Promise<void>((resolve) => setTimeout(resolve, 100)));

    render(<EditableSection {...defaultProps} onSave={onSave} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    // Save button should be disabled during save
    expect(saveButton).toBeDisabled();

    await waitFor(() => {
      expect(saveButton).not.toBeDisabled();
    });
  });

  it('exits edit mode after successful save', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(<EditableSection {...defaultProps} onSave={onSave} />);

    const container = screen.getByTestId('editable-section');
    await user.hover(container);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });

  it('applies custom className', () => {
    render(<EditableSection {...defaultProps} className="custom-class" />);

    const container = screen.getByTestId('editable-section');
    expect(container).toHaveClass('custom-class');
  });
});
