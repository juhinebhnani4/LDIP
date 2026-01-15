/**
 * SummaryNotesDialog Component Tests
 *
 * Story 10B.2: Summary Tab Verification and Edit (AC #1)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SummaryNotesDialog } from './SummaryNotesDialog';

describe('SummaryNotesDialog', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSave: vi.fn(),
    sectionType: 'subject_matter' as const,
    sectionId: 'test-section-123',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders modal with textarea when open', () => {
    render(<SummaryNotesDialog {...defaultProps} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    render(<SummaryNotesDialog {...defaultProps} isOpen={false} />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('displays existing notes if any', () => {
    const existingNote = 'This is an existing note';
    render(
      <SummaryNotesDialog
        {...defaultProps}
        existingNote={existingNote}
      />
    );

    expect(screen.getByRole('textbox')).toHaveValue(existingNote);
  });

  it('calls onSave with note text when save button clicked', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    render(<SummaryNotesDialog {...defaultProps} onSave={onSave} />);

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'My new note');

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    expect(onSave).toHaveBeenCalledWith('My new note');
  });

  it('calls onClose when cancel button clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<SummaryNotesDialog {...defaultProps} onClose={onClose} />);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    expect(onClose).toHaveBeenCalled();
  });

  it('shows loading state while saving', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn(() => new Promise<void>((resolve) => setTimeout(resolve, 100)));

    render(<SummaryNotesDialog {...defaultProps} onSave={onSave} />);

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'My note');

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    // Button should be disabled during save
    expect(saveButton).toBeDisabled();

    // Wait for save to complete
    await waitFor(() => {
      expect(saveButton).not.toBeDisabled();
    });
  });

  it('closes dialog after successful save', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <SummaryNotesDialog
        {...defaultProps}
        onSave={onSave}
        onClose={onClose}
      />
    );

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'My note');

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('displays dialog title', () => {
    render(<SummaryNotesDialog {...defaultProps} />);

    expect(screen.getByRole('heading', { name: /add note/i })).toBeInTheDocument();
  });

  it('disables save button when textarea is empty', () => {
    render(<SummaryNotesDialog {...defaultProps} />);

    const saveButton = screen.getByRole('button', { name: /save/i });
    expect(saveButton).toBeDisabled();
  });

  it('enables save button when textarea has content', async () => {
    const user = userEvent.setup();

    render(<SummaryNotesDialog {...defaultProps} />);

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'Some content');

    const saveButton = screen.getByRole('button', { name: /save/i });
    expect(saveButton).not.toBeDisabled();
  });
});
