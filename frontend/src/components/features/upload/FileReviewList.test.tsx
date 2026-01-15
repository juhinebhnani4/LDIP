import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FileReviewList } from './FileReviewList';

// Helper to create mock files
function createMockFile(name: string, size: number = 1024): File {
  const file = new File(['test content'], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

describe('FileReviewList', () => {
  describe('rendering', () => {
    it('renders file count and total size in header', () => {
      const files = [
        createMockFile('test1.pdf', 1024),
        createMockFile('test2.pdf', 2048),
      ];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByText(/files to upload \(2 files/i)).toBeInTheDocument();
    });

    it('shows singular file when only one file', () => {
      const files = [createMockFile('test.pdf', 1024)];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByText(/files to upload \(1 file/i)).toBeInTheDocument();
    });

    it('renders each file with name and size', () => {
      const files = [
        createMockFile('document.pdf', 1024 * 1024), // 1MB
        createMockFile('other.pdf', 2048),
      ];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByText('document.pdf')).toBeInTheDocument();
      expect(screen.getByText('other.pdf')).toBeInTheDocument();
      expect(screen.getByText('1 MB')).toBeInTheDocument();
    });

    it('renders remove button for each file', () => {
      const files = [
        createMockFile('test1.pdf'),
        createMockFile('test2.pdf'),
      ];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /remove test1\.pdf/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /remove test2\.pdf/i })).toBeInTheDocument();
    });

    it('renders Add More Files button', () => {
      const files = [createMockFile('test.pdf')];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /add more files/i })).toBeInTheDocument();
    });
  });

  describe('remove functionality', () => {
    it('calls onRemoveFile with correct index when remove clicked', async () => {
      const user = userEvent.setup();
      const onRemoveFile = vi.fn();
      const files = [
        createMockFile('first.pdf'),
        createMockFile('second.pdf'),
        createMockFile('third.pdf'),
      ];

      render(
        <FileReviewList
          files={files}
          onRemoveFile={onRemoveFile}
          onAddFiles={vi.fn()}
        />
      );

      const removeButton = screen.getByRole('button', { name: /remove second\.pdf/i });
      await user.click(removeButton);

      expect(onRemoveFile).toHaveBeenCalledWith(1);
    });
  });

  describe('add more files', () => {
    it('has hidden file input for adding more files', () => {
      const files = [createMockFile('test.pdf')];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeInTheDocument();
      expect(fileInput).toHaveClass('hidden');
    });

    it('accepts multiple files', () => {
      const files = [createMockFile('test.pdf')];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toHaveAttribute('multiple');
    });
  });

  describe('max files limit', () => {
    it('hides Add More Files when at max capacity', () => {
      // Create 100 files (max limit)
      const files = Array.from({ length: 100 }, (_, i) =>
        createMockFile(`file${i}.pdf`)
      );

      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.queryByRole('button', { name: /add more files/i })).not.toBeInTheDocument();
    });

    it('shows maximum files reached warning', () => {
      const files = Array.from({ length: 100 }, (_, i) =>
        createMockFile(`file${i}.pdf`)
      );

      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByText(/maximum files reached/i)).toBeInTheDocument();
    });

    it('shows Add More Files when below max capacity', () => {
      const files = Array.from({ length: 99 }, (_, i) =>
        createMockFile(`file${i}.pdf`)
      );

      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /add more files/i })).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('renders file list with list role', () => {
      const files = [createMockFile('test.pdf')];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByRole('list', { name: /selected files/i })).toBeInTheDocument();
    });

    it('file items are list items', () => {
      const files = [
        createMockFile('test1.pdf'),
        createMockFile('test2.pdf'),
      ];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      const list = screen.getByRole('list', { name: /selected files/i });
      const items = within(list).getAllByRole('listitem');
      expect(items).toHaveLength(2);
    });

    it('remove buttons have descriptive aria-label', () => {
      const files = [createMockFile('important_document.pdf')];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(
        screen.getByRole('button', { name: /remove important_document\.pdf/i })
      ).toBeInTheDocument();
    });

    it('file input is hidden from accessibility tree', () => {
      const files = [createMockFile('test.pdf')];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('file size formatting', () => {
    it('formats bytes correctly', () => {
      const files = [createMockFile('test.pdf', 500)];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByText('500 Bytes')).toBeInTheDocument();
    });

    it('formats kilobytes correctly', () => {
      const files = [createMockFile('test.pdf', 1024)];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByText('1 KB')).toBeInTheDocument();
    });

    it('formats megabytes correctly', () => {
      const files = [createMockFile('test.pdf', 5 * 1024 * 1024)];
      render(
        <FileReviewList
          files={files}
          onRemoveFile={vi.fn()}
          onAddFiles={vi.fn()}
        />
      );

      expect(screen.getByText('5 MB')).toBeInTheDocument();
    });
  });
});
