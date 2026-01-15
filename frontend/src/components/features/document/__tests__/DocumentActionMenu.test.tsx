import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DocumentActionMenu } from '../DocumentActionMenu';
import type { DocumentListItem } from '@/types/document';

const mockDocument: DocumentListItem = {
  id: 'doc-123',
  matterId: 'matter-456',
  filename: 'test-document.pdf',
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

const mockActDocument: DocumentListItem = {
  ...mockDocument,
  id: 'doc-act-123',
  documentType: 'act',
  isReferenceMaterial: true,
};

const mockDocumentWithNullPageCount: DocumentListItem = {
  ...mockDocument,
  id: 'doc-null-pages',
  pageCount: null,
};

describe('DocumentActionMenu', () => {
  const defaultProps = {
    document: mockDocument,
    onView: vi.fn(),
    onRename: vi.fn(),
    onSetAsAct: vi.fn(),
    onDelete: vi.fn(),
  };

  it('renders the menu trigger button', () => {
    render(<DocumentActionMenu {...defaultProps} />);

    const trigger = screen.getByRole('button', {
      name: `Actions for ${mockDocument.filename}`,
    });
    expect(trigger).toBeInTheDocument();
  });

  it('opens dropdown menu on click', async () => {
    const user = userEvent.setup();
    render(<DocumentActionMenu {...defaultProps} />);

    const trigger = screen.getByRole('button', {
      name: `Actions for ${mockDocument.filename}`,
    });
    await user.click(trigger);

    expect(screen.getByRole('menuitem', { name: /view/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /rename/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /set as act/i })).toBeInTheDocument();
  });

  it('calls onView when View is clicked', async () => {
    const user = userEvent.setup();
    const onView = vi.fn();
    render(<DocumentActionMenu {...defaultProps} onView={onView} />);

    await user.click(screen.getByRole('button', { name: /actions for/i }));
    await user.click(screen.getByRole('menuitem', { name: /view/i }));

    expect(onView).toHaveBeenCalledTimes(1);
  });

  it('calls onRename when Rename is clicked', async () => {
    const user = userEvent.setup();
    const onRename = vi.fn();
    render(<DocumentActionMenu {...defaultProps} onRename={onRename} />);

    await user.click(screen.getByRole('button', { name: /actions for/i }));
    await user.click(screen.getByRole('menuitem', { name: /rename/i }));

    expect(onRename).toHaveBeenCalledTimes(1);
  });

  it('calls onSetAsAct when Set as Act is clicked', async () => {
    const user = userEvent.setup();
    const onSetAsAct = vi.fn();
    render(<DocumentActionMenu {...defaultProps} onSetAsAct={onSetAsAct} />);

    await user.click(screen.getByRole('button', { name: /actions for/i }));
    await user.click(screen.getByRole('menuitem', { name: /set as act/i }));

    expect(onSetAsAct).toHaveBeenCalledTimes(1);
  });

  it('does not show Set as Act option for documents already marked as Act', async () => {
    const user = userEvent.setup();
    render(<DocumentActionMenu {...defaultProps} document={mockActDocument} />);

    await user.click(screen.getByRole('button', { name: /actions for/i }));

    expect(screen.queryByRole('menuitem', { name: /set as act/i })).not.toBeInTheDocument();
  });

  describe('role-based visibility', () => {
    it('shows Delete option for owner role', async () => {
      const user = userEvent.setup();
      render(<DocumentActionMenu {...defaultProps} userRole="owner" />);

      await user.click(screen.getByRole('button', { name: /actions for/i }));

      expect(screen.getByRole('menuitem', { name: /delete/i })).toBeInTheDocument();
    });

    it('hides Delete option for editor role', async () => {
      const user = userEvent.setup();
      render(<DocumentActionMenu {...defaultProps} userRole="editor" />);

      await user.click(screen.getByRole('button', { name: /actions for/i }));

      expect(screen.queryByRole('menuitem', { name: /delete/i })).not.toBeInTheDocument();
    });

    it('hides Delete option for viewer role', async () => {
      const user = userEvent.setup();
      render(<DocumentActionMenu {...defaultProps} userRole="viewer" />);

      await user.click(screen.getByRole('button', { name: /actions for/i }));

      expect(screen.queryByRole('menuitem', { name: /delete/i })).not.toBeInTheDocument();
    });

    it('hides Rename and Set as Act for viewer role', async () => {
      const user = userEvent.setup();
      render(<DocumentActionMenu {...defaultProps} userRole="viewer" />);

      await user.click(screen.getByRole('button', { name: /actions for/i }));

      expect(screen.queryByRole('menuitem', { name: /rename/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('menuitem', { name: /set as act/i })).not.toBeInTheDocument();
    });

    it('shows Rename and Set as Act for editor role', async () => {
      const user = userEvent.setup();
      render(<DocumentActionMenu {...defaultProps} userRole="editor" />);

      await user.click(screen.getByRole('button', { name: /actions for/i }));

      expect(screen.getByRole('menuitem', { name: /rename/i })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /set as act/i })).toBeInTheDocument();
    });
  });

  it('calls onDelete when Delete is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<DocumentActionMenu {...defaultProps} onDelete={onDelete} userRole="owner" />);

    await user.click(screen.getByRole('button', { name: /actions for/i }));
    await user.click(screen.getByRole('menuitem', { name: /delete/i }));

    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it('disables trigger button when disabled prop is true', () => {
    render(<DocumentActionMenu {...defaultProps} disabled />);

    const trigger = screen.getByRole('button', { name: /actions for/i });
    expect(trigger).toBeDisabled();
  });

  it('handles document with null pageCount', async () => {
    const user = userEvent.setup();
    render(<DocumentActionMenu {...defaultProps} document={mockDocumentWithNullPageCount} />);

    const trigger = screen.getByRole('button', {
      name: `Actions for ${mockDocumentWithNullPageCount.filename}`,
    });
    await user.click(trigger);

    // Menu should still render all options correctly
    expect(screen.getByRole('menuitem', { name: /view/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /rename/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /set as act/i })).toBeInTheDocument();
  });
});
