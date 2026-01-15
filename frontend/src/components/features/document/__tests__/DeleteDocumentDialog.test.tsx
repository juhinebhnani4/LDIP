import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DeleteDocumentDialog } from '../DeleteDocumentDialog';
import type { DocumentListItem } from '@/types/document';

const mockDocument: DocumentListItem = {
  id: 'doc-123',
  matterId: 'matter-456',
  filename: 'document-to-delete.pdf',
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

describe('DeleteDocumentDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    document: mockDocument,
    onDelete: vi.fn(),
  };

  it('renders dialog with document filename', () => {
    render(<DeleteDocumentDialog {...defaultProps} />);

    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /delete document/i })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(mockDocument.filename))).toBeInTheDocument();
  });

  it('displays 30-day retention message', () => {
    render(<DeleteDocumentDialog {...defaultProps} />);

    expect(screen.getByText(/30 days/i)).toBeInTheDocument();
  });

  it('does not render when open is false', () => {
    render(<DeleteDocumentDialog {...defaultProps} open={false} />);

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('calls onDelete when Delete button is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<DeleteDocumentDialog {...defaultProps} onDelete={onDelete} />);

    await user.click(screen.getByRole('button', { name: /^delete$/i }));

    await waitFor(() => {
      expect(onDelete).toHaveBeenCalledTimes(1);
    });
  });

  it('closes dialog on successful delete', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(
      <DeleteDocumentDialog
        {...defaultProps}
        onOpenChange={onOpenChange}
        onDelete={onDelete}
      />
    );

    await user.click(screen.getByRole('button', { name: /^delete$/i }));

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('closes dialog without calling onDelete when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onDelete = vi.fn();
    render(
      <DeleteDocumentDialog
        {...defaultProps}
        onOpenChange={onOpenChange}
        onDelete={onDelete}
      />
    );

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onDelete).not.toHaveBeenCalled();
  });

  it('shows Deleting... text during deletion', async () => {
    const user = userEvent.setup();
    let resolveDelete: () => void;
    const onDelete = vi.fn().mockImplementation(() => {
      return new Promise<void>((resolve) => {
        resolveDelete = resolve;
      });
    });
    render(<DeleteDocumentDialog {...defaultProps} onDelete={onDelete} />);

    await user.click(screen.getByRole('button', { name: /^delete$/i }));

    expect(screen.getByRole('button', { name: /deleting/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /deleting/i })).toBeDisabled();

    resolveDelete!();
  });

  it('disables buttons during deletion', async () => {
    const user = userEvent.setup();
    let resolveDelete: () => void;
    const onDelete = vi.fn().mockImplementation(() => {
      return new Promise<void>((resolve) => {
        resolveDelete = resolve;
      });
    });
    render(<DeleteDocumentDialog {...defaultProps} onDelete={onDelete} />);

    await user.click(screen.getByRole('button', { name: /^delete$/i }));

    expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /deleting/i })).toBeDisabled();

    resolveDelete!();
  });

  it('resets deleting state after error', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn().mockRejectedValue(new Error('Delete failed'));
    render(<DeleteDocumentDialog {...defaultProps} onDelete={onDelete} />);

    await user.click(screen.getByRole('button', { name: /^delete$/i }));

    // Wait for the error to be handled
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^delete$/i })).not.toBeDisabled();
    });
  });

  it('has destructive styling on Delete button', () => {
    render(<DeleteDocumentDialog {...defaultProps} />);

    const deleteButton = screen.getByRole('button', { name: /^delete$/i });
    expect(deleteButton).toHaveClass('bg-destructive');
  });
});
