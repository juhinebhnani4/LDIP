import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FileDropZone } from './FileDropZone';

// Helper to create mock files
function createMockFile(name: string, size: number = 1024, type: string = 'application/pdf'): File {
  const file = new File(['test content'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

// Helper to create mock DataTransfer for drag events (jsdom doesn't have DataTransfer)
function createMockDataTransfer(files: File[]): { files: FileList } {
  // Create a FileList-like object
  const fileList = {
    length: files.length,
    item: (index: number) => files[index] ?? null,
    [Symbol.iterator]: function* () {
      for (const file of files) {
        yield file;
      }
    },
  } as unknown as FileList;

  // Add indexed access
  files.forEach((file, index) => {
    Object.defineProperty(fileList, index, { value: file, enumerable: true });
  });

  return { files: fileList };
}

describe('FileDropZone', () => {
  describe('rendering', () => {
    it('renders drop zone with instructions', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      expect(screen.getByText(/drag & drop your case files here/i)).toBeInTheDocument();
    });

    it('renders Browse Files button', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      expect(screen.getByRole('button', { name: /browse files/i })).toBeInTheDocument();
    });

    it('renders supported formats text', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      expect(screen.getByText(/supported: pdf, zip/i)).toBeInTheDocument();
    });

    it('renders file limits text', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      expect(screen.getByText(/maximum: 500mb per file/i)).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      const onFilesSelected = vi.fn();
      const { container } = render(
        <FileDropZone onFilesSelected={onFilesSelected} className="custom-class" />
      );

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('drag and drop', () => {
    it('shows drop to upload text on drag over', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });

      fireEvent.dragOver(dropZone);

      expect(screen.getByText(/drop to upload/i)).toBeInTheDocument();
    });

    it('reverts text on drag leave', async () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });

      fireEvent.dragOver(dropZone);
      expect(screen.getByText(/drop to upload/i)).toBeInTheDocument();

      fireEvent.dragLeave(dropZone);
      expect(screen.getByText(/drag & drop your case files here/i)).toBeInTheDocument();
    });

    it('calls onFilesSelected when valid files are dropped', async () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      const file = createMockFile('test.pdf');
      const dataTransfer = createMockDataTransfer([file]);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(onFilesSelected).toHaveBeenCalledWith([file]);
      });
    });

    it('does not call onFilesSelected for invalid file types', async () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      const file = createMockFile('test.xlsx', 1024, 'application/vnd.ms-excel');
      const dataTransfer = createMockDataTransfer([file]);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(onFilesSelected).not.toHaveBeenCalled();
      });
    });
  });

  describe('file input', () => {
    it('opens file picker when browse button clicked', async () => {
      const user = userEvent.setup();
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const browseButton = screen.getByRole('button', { name: /browse files/i });
      await user.click(browseButton);

      // File input exists and accepts correct types
      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeInTheDocument();
      expect(fileInput).toHaveAttribute(
        'accept',
        '.pdf,.zip,application/pdf,application/zip,application/x-zip-compressed'
      );
    });

    it('accepts multiple files', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toHaveAttribute('multiple');
    });
  });

  describe('validation errors', () => {
    it('shows error for invalid file type', async () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      const file = createMockFile('test.xlsx', 1024, 'application/vnd.ms-excel');
      const dataTransfer = createMockDataTransfer([file]);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(screen.getByText(/ldip supports pdf files only/i)).toBeInTheDocument();
      });
    });

    it('shows error for file too large', async () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      // Create file larger than 500MB
      const largeFile = createMockFile('large.pdf', 600 * 1024 * 1024);
      const dataTransfer = createMockDataTransfer([largeFile]);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(screen.getByText(/file too large/i)).toBeInTheDocument();
      });
    });

    it('shows warning when max files exceeded', async () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      // Create 101 files
      const files = Array.from({ length: 101 }, (_, i) =>
        createMockFile(`test${i}.pdf`)
      );
      const dataTransfer = createMockDataTransfer(files);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(screen.getByText(/maximum 100 files per upload/i)).toBeInTheDocument();
      });
    });

    it('validation errors have alert role for accessibility', async () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      const file = createMockFile('test.xlsx', 1024, 'application/vnd.ms-excel');
      const dataTransfer = createMockDataTransfer([file]);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
    });
  });

  describe('accessibility', () => {
    it('is keyboard accessible via tab', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      expect(dropZone).toHaveAttribute('tabIndex', '0');
    });

    it('has accessible name for drop zone', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      expect(
        screen.getByRole('button', { name: /drop files here or click to browse/i })
      ).toBeInTheDocument();
    });

    it('hides file input from accessibility tree', () => {
      const onFilesSelected = vi.fn();
      render(<FileDropZone onFilesSelected={onFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toHaveAttribute('aria-hidden', 'true');
    });
  });
});
