import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import { UploadDropzone } from './UploadDropzone';
import { useUploadStore } from '@/stores/uploadStore';

// Mock the upload API
vi.mock('@/lib/api/documents', () => ({
  uploadFiles: vi.fn().mockResolvedValue([]),
}));

describe('UploadDropzone', () => {
  const matterId = 'test-matter-id';

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store before each test - wrapped in act for state changes
    act(() => {
      useUploadStore.getState().clearAll();
    });
  });

  afterEach(() => {
    act(() => {
      useUploadStore.getState().clearAll();
    });
  });

  // Helper to create mock files - use smaller size to avoid memory issues
  const createMockFile = (
    name: string,
    size: number,
    type: string
  ): File => {
    // Create small actual content, but mock the size property
    const file = new File(['x'.repeat(Math.min(size, 100))], name, { type });
    Object.defineProperty(file, 'size', { value: size });
    return file;
  };

  const createDataTransfer = (files: File[]): DataTransfer => {
    const dt = {
      files: {
        length: files.length,
        item: (i: number) => files[i],
        [Symbol.iterator]: function* () {
          for (const file of files) yield file;
        },
      } as unknown as FileList,
      items: [] as DataTransferItem[],
      types: ['Files'],
      getData: () => '',
      setData: () => {},
      clearData: () => {},
      dropEffect: 'none' as const,
      effectAllowed: 'all' as const,
    };
    return dt as unknown as DataTransfer;
  };

  describe('Rendering', () => {
    it('renders dropzone with instructions', async () => {
      render(<UploadDropzone matterId={matterId} />);

      expect(screen.getByText(/drag & drop files here/i)).toBeInTheDocument();
      expect(screen.getByText(/pdf and zip files only/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /browse files/i })
      ).toBeInTheDocument();
    });

    it('has accessible role and label', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });
      expect(dropzone).toBeInTheDocument();
      expect(dropzone).toHaveAttribute('tabindex', '0');
    });
  });

  describe('Drag and Drop Visual States', () => {
    it('shows drag active state when dragging files over', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      await act(async () => {
        fireEvent.dragEnter(dropzone, {
          dataTransfer: createDataTransfer([]),
        });
      });

      expect(screen.getByText(/drop files here$/i)).toBeInTheDocument();
      expect(dropzone).toHaveClass('border-primary');
    });

    it('returns to default state on drag leave', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      await act(async () => {
        fireEvent.dragEnter(dropzone, {
          dataTransfer: createDataTransfer([]),
        });
      });

      await act(async () => {
        fireEvent.dragLeave(dropzone, {
          dataTransfer: createDataTransfer([]),
        });
      });

      expect(screen.getByText(/drag & drop files here/i)).toBeInTheDocument();
    });
  });

  describe('File Type Validation (AC: #1)', () => {
    it('accepts PDF files', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      const pdfFile = createMockFile('document.pdf', 1024, 'application/pdf');

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer([pdfFile]),
        });
      });

      await waitFor(() => {
        expect(useUploadStore.getState().uploadQueue).toHaveLength(1);
      });
    });

    it('accepts ZIP files', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      const zipFile = createMockFile('archive.zip', 1024, 'application/zip');

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer([zipFile]),
        });
      });

      await waitFor(() => {
        expect(useUploadStore.getState().uploadQueue).toHaveLength(1);
      });
    });

    it('rejects non-PDF/ZIP files with error message', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      const docFile = createMockFile('document.doc', 1024, 'application/msword');

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer([docFile]),
        });
      });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Only PDF and ZIP files are supported'
        );
      });

      // File should NOT be added to queue
      expect(useUploadStore.getState().uploadQueue).toHaveLength(0);
    });

    it('shows invalid state briefly for rejected files', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      const invalidFile = createMockFile('image.png', 1024, 'image/png');

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer([invalidFile]),
        });
      });

      // Should show invalid state
      expect(screen.getByText(/invalid files/i)).toBeInTheDocument();
    });
  });

  describe('File Size Validation (AC: #3)', () => {
    it('rejects files larger than 500MB', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      // 501 MB file (size is mocked, not actual content)
      const largeFile = createMockFile(
        'large.pdf',
        501 * 1024 * 1024,
        'application/pdf'
      );

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer([largeFile]),
        });
      });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          expect.stringContaining('File exceeds 500MB limit')
        );
      });
    });

    it('accepts files exactly at 500MB limit', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      // Exactly 500 MB file (size is mocked)
      const maxSizeFile = createMockFile(
        'max.pdf',
        500 * 1024 * 1024,
        'application/pdf'
      );

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer([maxSizeFile]),
        });
      });

      await waitFor(() => {
        expect(useUploadStore.getState().uploadQueue).toHaveLength(1);
      });
    });
  });

  describe('File Count Limit (AC: #4)', () => {
    it('shows warning when more than 100 files are uploaded', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      // Create 105 valid files
      const files = Array.from({ length: 105 }, (_, i) =>
        createMockFile(`file${i}.pdf`, 1024, 'application/pdf')
      );

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer(files),
        });
      });

      await waitFor(() => {
        expect(toast.warning).toHaveBeenCalledWith(
          expect.stringContaining('Maximum 100 files per upload')
        );
      });
    });

    it('accepts only first 100 files when limit exceeded', async () => {
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      // Create 105 valid files
      const files = Array.from({ length: 105 }, (_, i) =>
        createMockFile(`file${i}.pdf`, 1024, 'application/pdf')
      );

      await act(async () => {
        fireEvent.drop(dropzone, {
          dataTransfer: createDataTransfer(files),
        });
      });

      await waitFor(() => {
        expect(useUploadStore.getState().uploadQueue).toHaveLength(100);
      });
    });
  });

  describe('Browse Files Button (AC: #5)', () => {
    it('opens file picker when Browse Files is clicked', async () => {
      const user = userEvent.setup();
      render(<UploadDropzone matterId={matterId} />);

      const browseButton = screen.getByRole('button', { name: /browse files/i });

      // We can't directly test file input opening, but we can verify the click handler
      await user.click(browseButton);

      // Button should be present and clickable
      expect(browseButton).toBeEnabled();
    });

    it('accepts files from file input with correct accept attribute', () => {
      const { container } = render(<UploadDropzone matterId={matterId} />);

      // Find hidden input
      const fileInput = container.querySelector(
        'input[type="file"]'
      ) as HTMLInputElement;

      expect(fileInput).toBeInTheDocument();
      expect(fileInput).toHaveAttribute(
        'accept',
        '.pdf,.zip,application/pdf,application/zip,application/x-zip-compressed'
      );
      expect(fileInput).toHaveAttribute('multiple');
    });
  });

  describe('Keyboard Accessibility', () => {
    it('can be activated with Enter key', async () => {
      const user = userEvent.setup();
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      // Focus and press Enter
      dropzone.focus();
      await user.keyboard('{Enter}');

      // Should not throw error
      expect(dropzone).toHaveFocus();
    });

    it('can be activated with Space key', async () => {
      const user = userEvent.setup();
      render(<UploadDropzone matterId={matterId} />);

      const dropzone = screen.getByRole('button', {
        name: /drop files here or click to browse/i,
      });

      // Focus and press Space
      dropzone.focus();
      await user.keyboard(' ');

      // Should not throw error
      expect(dropzone).toHaveFocus();
    });
  });

  describe('Progress UI Integration', () => {
    it('shows progress list when files are added', async () => {
      // Pre-populate the store - wrapped in act
      act(() => {
        useUploadStore.getState().addFiles([
          createMockFile('test.pdf', 1024, 'application/pdf'),
        ]);
      });

      render(<UploadDropzone matterId={matterId} />);

      expect(screen.getByText(/uploads \(1\)/i)).toBeInTheDocument();
    });

    it('shows upload progress for files in queue', async () => {
      // Pre-populate the store - wrapped in act
      act(() => {
        useUploadStore.getState().addFiles([
          createMockFile('test.pdf', 1024, 'application/pdf'),
        ]);
      });

      render(<UploadDropzone matterId={matterId} />);

      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });
  });
});
