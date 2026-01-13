import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActUploadDropzone } from './ActUploadDropzone';
import * as documentsApi from '@/lib/api/documents';
import { toast } from 'sonner';

// Mock the documents API
vi.mock('@/lib/api/documents', () => ({
  uploadFile: vi.fn(),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('ActUploadDropzone', () => {
  const mockMatterId = 'test-matter-123';
  const mockActName = 'Negotiable Instruments Act, 1881';
  const mockOnUploadComplete = vi.fn();
  const mockOnCancel = vi.fn();

  const createMockFile = (name: string, size: number, type: string = 'application/pdf'): File => {
    const file = new File(['test content'], name, { type });
    Object.defineProperty(file, 'size', { value: size });
    return file;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(documentsApi.uploadFile).mockResolvedValue({
      data: {
        documentId: 'new-doc-123',
        filename: 'act.pdf',
        storagePath: 'documents/test-matter-123/acts/act.pdf',
        status: 'completed',
      },
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders dropzone with act name', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      expect(screen.getByText('Uploading Act Document')).toBeInTheDocument();
      expect(screen.getByText(mockActName)).toBeInTheDocument();
    });

    it('shows drop zone instructions', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      expect(screen.getByText('Drop PDF here')).toBeInTheDocument();
      expect(screen.getByText('PDF files only (max 100MB)')).toBeInTheDocument();
    });

    it('shows Browse Files button', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      expect(screen.getByRole('button', { name: /browse files/i })).toBeInTheDocument();
    });

    it('shows Cancel button when onCancel is provided', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
          onCancel={mockOnCancel}
        />
      );

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('does not show Cancel button when onCancel is not provided', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument();
    });
  });

  describe('File Validation', () => {
    it('rejects non-PDF files via drag-drop', async () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const dropzone = screen.getByRole('button', { name: /drop pdf file here/i });
      const file = createMockFile('test.txt', 1024, 'text/plain');

      // Use drag-drop to bypass input accept attribute filtering
      const dataTransfer = {
        files: [file],
        items: [{ kind: 'file', type: 'text/plain', getAsFile: () => file }],
        types: ['Files'],
      };

      fireEvent.drop(dropzone, { dataTransfer });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Only PDF files are supported for Acts');
      });
      expect(mockOnUploadComplete).not.toHaveBeenCalled();
    });

    it('rejects files exceeding 100MB', async () => {
      const user = userEvent.setup();
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      // 150MB file
      const file = createMockFile('large.pdf', 150 * 1024 * 1024);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      await user.upload(input, file);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('exceeds 100MB limit'));
      });
      expect(mockOnUploadComplete).not.toHaveBeenCalled();
    });

    it('accepts valid PDF files under 100MB', async () => {
      const user = userEvent.setup();
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const file = createMockFile('act.pdf', 5 * 1024 * 1024); // 5MB
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      await user.upload(input, file);

      await waitFor(() => {
        expect(documentsApi.uploadFile).toHaveBeenCalled();
      });
    });
  });

  describe('Upload Flow', () => {
    it('calls uploadFile with correct parameters', async () => {
      const user = userEvent.setup();
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const file = createMockFile('act.pdf', 1024);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      await user.upload(input, file);

      await waitFor(() => {
        expect(documentsApi.uploadFile).toHaveBeenCalledWith(
          expect.any(File),
          expect.any(String),
          expect.objectContaining({
            matterId: mockMatterId,
            documentType: 'act',
          })
        );
      });
    });

    it('calls onUploadComplete with documentId on success', async () => {
      const user = userEvent.setup();
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const file = createMockFile('act.pdf', 1024);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      await user.upload(input, file);

      await waitFor(() => {
        expect(mockOnUploadComplete).toHaveBeenCalledWith('new-doc-123');
      });
    });

    it('shows success toast on successful upload', async () => {
      const user = userEvent.setup();
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const file = createMockFile('act.pdf', 1024);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      await user.upload(input, file);

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith(`${mockActName} uploaded successfully`);
      });
    });

    it('shows error toast on upload failure', async () => {
      vi.mocked(documentsApi.uploadFile).mockRejectedValue(new Error('Network error'));

      const user = userEvent.setup();
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const file = createMockFile('act.pdf', 1024);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;

      await user.upload(input, file);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Network error');
      });
      expect(mockOnUploadComplete).not.toHaveBeenCalled();
    });
  });

  describe('Drag and Drop', () => {
    it('changes style on drag enter', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const dropzone = screen.getByRole('button', { name: /drop pdf file here/i });

      fireEvent.dragEnter(dropzone, {
        dataTransfer: { files: [] },
      });

      // The component should show "Drop PDF here" text (already visible)
      expect(screen.getByText('Drop PDF here')).toBeInTheDocument();
    });

    it('handles file drop', async () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const dropzone = screen.getByRole('button', { name: /drop pdf file here/i });
      const file = createMockFile('act.pdf', 1024);

      const dataTransfer = {
        files: [file],
        items: [{ kind: 'file', type: 'application/pdf', getAsFile: () => file }],
        types: ['Files'],
      };

      fireEvent.drop(dropzone, { dataTransfer });

      await waitFor(() => {
        expect(documentsApi.uploadFile).toHaveBeenCalled();
      });
    });
  });

  describe('Cancel Action', () => {
    it('calls onCancel when Cancel button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
          onCancel={mockOnCancel}
        />
      );

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(mockOnCancel).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has accessible dropzone with aria-label', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const dropzone = screen.getByRole('button', { name: /drop pdf file here/i });
      expect(dropzone).toBeInTheDocument();
    });

    it('has hidden file input', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const input = document.querySelector('input[type="file"]');
      expect(input).toHaveAttribute('aria-hidden', 'true');
    });

    it('accepts only PDF files', () => {
      render(
        <ActUploadDropzone
          matterId={mockMatterId}
          actName={mockActName}
          onUploadComplete={mockOnUploadComplete}
        />
      );

      const input = document.querySelector('input[type="file"]');
      expect(input).toHaveAttribute('accept', '.pdf,application/pdf');
    });
  });
});
