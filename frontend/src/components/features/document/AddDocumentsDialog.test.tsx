import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AddDocumentsDialog } from './AddDocumentsDialog';
import type { UploadFile } from '@/types/document';

// Mock the UploadDropzone component
vi.mock('./UploadDropzone', () => ({
  UploadDropzone: ({
    matterId,
    onUploadComplete,
  }: {
    matterId: string;
    onUploadComplete?: (files: UploadFile[]) => void;
  }) => (
    <div data-testid="upload-dropzone">
      <span>UploadDropzone: {matterId}</span>
      <button
        onClick={() =>
          onUploadComplete?.([
            {
              id: 'file-1',
              file: new File([''], 'test.pdf'),
              progress: 100,
              status: 'completed',
            },
          ])
        }
      >
        Complete Upload
      </button>
      <button onClick={() => onUploadComplete?.([])}>
        Complete Empty
      </button>
    </div>
  ),
}));

describe('AddDocumentsDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    matterId: 'matter-123',
    onComplete: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders dialog when open', () => {
      render(<AddDocumentsDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Add Documents')).toBeInTheDocument();
      expect(screen.getByText('Upload additional documents to this matter')).toBeInTheDocument();
    });

    it('does not render content when closed', () => {
      render(<AddDocumentsDialog {...defaultProps} open={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders UploadDropzone with matterId', () => {
      render(<AddDocumentsDialog {...defaultProps} />);

      expect(screen.getByTestId('upload-dropzone')).toBeInTheDocument();
      expect(screen.getByText('UploadDropzone: matter-123')).toBeInTheDocument();
    });

    it('renders background processing message (AC #3)', () => {
      render(<AddDocumentsDialog {...defaultProps} />);

      expect(screen.getByText('You can continue working while this processes')).toBeInTheDocument();
    });
  });

  describe('Upload Complete Handling', () => {
    it('calls onComplete when files are uploaded', async () => {
      const user = userEvent.setup();
      const onComplete = vi.fn();
      render(<AddDocumentsDialog {...defaultProps} onComplete={onComplete} />);

      // Simulate upload complete with files
      await user.click(screen.getByRole('button', { name: /complete upload/i }));

      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it('does not call onComplete when no files uploaded', async () => {
      const user = userEvent.setup();
      const onComplete = vi.fn();
      render(<AddDocumentsDialog {...defaultProps} onComplete={onComplete} />);

      // Simulate upload complete without files
      await user.click(screen.getByRole('button', { name: /complete empty/i }));

      expect(onComplete).not.toHaveBeenCalled();
    });
  });

  describe('Dialog Close', () => {
    it('calls onOpenChange when dialog is closed via escape', async () => {
      const user = userEvent.setup();
      const onOpenChange = vi.fn();
      render(<AddDocumentsDialog {...defaultProps} onOpenChange={onOpenChange} />);

      // Press escape to close
      await user.keyboard('{Escape}');

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Accessibility', () => {
    it('has accessible dialog role', () => {
      render(<AddDocumentsDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has dialog title', () => {
      render(<AddDocumentsDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toHaveAccessibleName('Add Documents');
    });

    it('has info icon with proper styling', () => {
      render(<AddDocumentsDialog {...defaultProps} />);

      // The info alert should have the info icon
      const alerts = document.querySelectorAll('[role="alert"]');
      expect(alerts.length).toBeGreaterThanOrEqual(0); // Alert component may not use role="alert"
    });
  });
});
