import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { RenameDocumentDialog } from '../RenameDocumentDialog';
import type { DocumentListItem } from '@/types/document';

const mockDocument: DocumentListItem = {
  id: 'doc-123',
  matterId: 'matter-456',
  filename: 'original-filename.pdf',
  fileSize: 1024000,
  pageCount: 10,
  documentType: 'case_file',
  isReferenceMaterial: false,
  status: 'completed',
  uploadedAt: '2026-01-15T10:00:00Z',
  uploadedBy: 'user-789',
  ocrConfidence: 0.95,
  ocrQualityStatus: 'good',
};

describe('RenameDocumentDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    document: mockDocument,
    onRename: vi.fn(),
  };

  it('renders dialog with document filename pre-filled', () => {
    render(<RenameDocumentDialog {...defaultProps} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /rename document/i })).toBeInTheDocument();
    expect(screen.getByDisplayValue(mockDocument.filename)).toBeInTheDocument();
  });

  it('does not render when open is false', () => {
    render(<RenameDocumentDialog {...defaultProps} open={false} />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('calls onRename with new filename on submit', async () => {
    const user = userEvent.setup();
    const onRename = vi.fn().mockResolvedValue(undefined);
    render(<RenameDocumentDialog {...defaultProps} onRename={onRename} />);

    const input = screen.getByRole('textbox', { name: /new filename/i });
    await user.clear(input);
    await user.type(input, 'new-filename.pdf');
    await user.click(screen.getByRole('button', { name: /rename/i }));

    await waitFor(() => {
      expect(onRename).toHaveBeenCalledWith('new-filename.pdf');
    });
  });

  it('closes dialog on successful rename', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onRename = vi.fn().mockResolvedValue(undefined);
    render(
      <RenameDocumentDialog
        {...defaultProps}
        onOpenChange={onOpenChange}
        onRename={onRename}
      />
    );

    const input = screen.getByRole('textbox', { name: /new filename/i });
    await user.clear(input);
    await user.type(input, 'new-filename.pdf');
    await user.click(screen.getByRole('button', { name: /rename/i }));

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('shows error message on rename failure', async () => {
    const user = userEvent.setup();
    const onRename = vi.fn().mockRejectedValue(new Error('Rename failed'));
    render(<RenameDocumentDialog {...defaultProps} onRename={onRename} />);

    const input = screen.getByRole('textbox', { name: /new filename/i });
    await user.clear(input);
    await user.type(input, 'new-filename.pdf');
    await user.click(screen.getByRole('button', { name: /rename/i }));

    await waitFor(() => {
      expect(screen.getByText('Rename failed')).toBeInTheDocument();
    });
  });

  it('closes dialog without calling onRename when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onRename = vi.fn();
    render(
      <RenameDocumentDialog
        {...defaultProps}
        onOpenChange={onOpenChange}
        onRename={onRename}
      />
    );

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onRename).not.toHaveBeenCalled();
  });

  it('closes without calling onRename when filename unchanged', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onRename = vi.fn();
    render(
      <RenameDocumentDialog
        {...defaultProps}
        onOpenChange={onOpenChange}
        onRename={onRename}
      />
    );

    // Submit without changing filename
    await user.click(screen.getByRole('button', { name: /rename/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onRename).not.toHaveBeenCalled();
  });

  describe('validation', () => {
    it('shows error for empty filename', async () => {
      const user = userEvent.setup();
      render(<RenameDocumentDialog {...defaultProps} />);

      const input = screen.getByRole('textbox', { name: /new filename/i });
      await user.clear(input);
      await user.click(screen.getByRole('button', { name: /rename/i }));

      expect(screen.getByText(/filename is required/i)).toBeInTheDocument();
    });

    it('shows error for filename with invalid characters', async () => {
      const user = userEvent.setup();
      render(<RenameDocumentDialog {...defaultProps} />);

      const input = screen.getByRole('textbox', { name: /new filename/i });
      await user.clear(input);
      await user.type(input, 'file<name>.pdf');
      await user.click(screen.getByRole('button', { name: /rename/i }));

      expect(screen.getByText(/invalid characters/i)).toBeInTheDocument();
    });

    it.each(['<', '>', ':', '"', '/', '\\', '|', '?', '*'])(
      'shows error for filename containing %s',
      async (char) => {
        const user = userEvent.setup();
        render(<RenameDocumentDialog {...defaultProps} />);

        const input = screen.getByRole('textbox', { name: /new filename/i });
        await user.clear(input);
        await user.type(input, `file${char}name.pdf`);
        await user.click(screen.getByRole('button', { name: /rename/i }));

        expect(screen.getByText(/invalid characters/i)).toBeInTheDocument();
      }
    );

    it('shows error for filename exceeding 255 characters', async () => {
      const user = userEvent.setup();
      render(<RenameDocumentDialog {...defaultProps} />);

      const input = screen.getByRole('textbox', { name: /new filename/i }) as HTMLInputElement;
      await user.clear(input);
      // Paste instead of typing to avoid timeout
      await user.paste('a'.repeat(256));
      await user.click(screen.getByRole('button', { name: /rename/i }));

      expect(screen.getByText(/255 characters or less/i)).toBeInTheDocument();
    });
  });

  it('shows Renaming... text during submission', async () => {
    const user = userEvent.setup();
    let resolveRename: () => void;
    const onRename = vi.fn().mockImplementation(() => {
      return new Promise<void>((resolve) => {
        resolveRename = resolve;
      });
    });
    render(<RenameDocumentDialog {...defaultProps} onRename={onRename} />);

    const input = screen.getByRole('textbox', { name: /new filename/i });
    await user.clear(input);
    await user.type(input, 'new-filename.pdf');
    await user.click(screen.getByRole('button', { name: /rename/i }));

    expect(screen.getByRole('button', { name: /renaming/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /renaming/i })).toBeDisabled();

    // Resolve the promise and wait for state update to complete
    resolveRename!();
    await waitFor(() => {
      expect(onRename).toHaveBeenCalled();
    });
  });

  it('resets form when dialog opens with new document', async () => {
    const { rerender } = render(
      <RenameDocumentDialog {...defaultProps} open={false} />
    );

    // Open dialog
    rerender(<RenameDocumentDialog {...defaultProps} open={true} />);

    expect(screen.getByDisplayValue(mockDocument.filename)).toBeInTheDocument();
  });
});
