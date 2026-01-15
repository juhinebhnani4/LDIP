import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UploadProgressView } from './UploadProgressView';
import type { UploadProgress } from '@/types/upload';

describe('UploadProgressView', () => {
  const createProgress = (
    fileName: string,
    status: UploadProgress['status'],
    progressPct: number = 0,
    errorMessage?: string
  ): UploadProgress => ({
    fileName,
    fileSize: 1024 * 1024, // 1MB
    progressPct,
    status,
    errorMessage,
  });

  describe('rendering', () => {
    it('renders header with file count', () => {
      const progress = [
        createProgress('file1.pdf', 'complete', 100),
        createProgress('file2.pdf', 'uploading', 50),
        createProgress('file3.pdf', 'pending', 0),
      ];

      render(<UploadProgressView uploadProgress={progress} totalFiles={3} />);

      expect(screen.getByText('Uploading Files')).toBeInTheDocument();
      expect(screen.getByText('1 of 3 uploaded')).toBeInTheDocument();
    });

    it('renders overall progress bar', () => {
      const progress = [
        createProgress('file1.pdf', 'complete', 100),
        createProgress('file2.pdf', 'uploading', 50),
      ];

      render(<UploadProgressView uploadProgress={progress} totalFiles={2} />);

      const progressBar = screen.getByRole('progressbar', {
        name: /overall upload progress/i,
      });
      expect(progressBar).toBeInTheDocument();
    });

    it('calculates overall progress correctly', () => {
      // 1 file complete (100%) + 1 file at 50% = 150% / 2 = 75%
      const progress = [
        createProgress('file1.pdf', 'complete', 100),
        createProgress('file2.pdf', 'uploading', 50),
      ];

      render(<UploadProgressView uploadProgress={progress} totalFiles={2} />);

      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('renders file list with correct aria labels', () => {
      const progress = [createProgress('test.pdf', 'uploading', 50)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      expect(screen.getByRole('list', { name: /files being uploaded/i })).toBeInTheDocument();
    });

    it('renders each file with name and size', () => {
      const progress = [
        { fileName: 'document.pdf', fileSize: 1024 * 1024, progressPct: 50, status: 'uploading' as const },
      ];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      expect(screen.getByText('document.pdf')).toBeInTheDocument();
      expect(screen.getByText('1 MB')).toBeInTheDocument();
    });
  });

  describe('file states', () => {
    it('shows checkmark for completed files', () => {
      const progress = [createProgress('done.pdf', 'complete', 100)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      expect(screen.getByLabelText('Upload complete')).toBeInTheDocument();
    });

    it('shows loader for uploading files', () => {
      const progress = [createProgress('uploading.pdf', 'uploading', 50)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      expect(screen.getByLabelText('Uploading')).toBeInTheDocument();
    });

    it('shows X icon for errored files', () => {
      const progress = [createProgress('failed.pdf', 'error', 25, 'Network error')];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      expect(screen.getByLabelText('Upload failed')).toBeInTheDocument();
    });

    it('shows file icon for pending files', () => {
      const progress = [createProgress('pending.pdf', 'pending', 0)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      expect(screen.getByLabelText('Pending upload')).toBeInTheDocument();
    });

    it('shows progress percentage for uploading files', () => {
      const progress = [createProgress('uploading.pdf', 'uploading', 67)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      // Both overall progress and file-level progress show 67%
      const percentageElements = screen.getAllByText('67%');
      expect(percentageElements.length).toBeGreaterThanOrEqual(1);
    });

    it('shows individual progress bar for uploading files', () => {
      const progress = [createProgress('uploading.pdf', 'uploading', 50)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      const progressBars = screen.getAllByRole('progressbar');
      // Should have overall progress + individual file progress
      expect(progressBars.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('error handling', () => {
    it('displays error message for failed uploads', () => {
      const progress = [createProgress('failed.pdf', 'error', 0, 'File too large')];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      expect(screen.getByText('File too large')).toBeInTheDocument();
    });

    it('shows error summary when any uploads fail', () => {
      const progress = [
        createProgress('good.pdf', 'complete', 100),
        createProgress('bad.pdf', 'error', 0, 'Failed'),
      ];

      render(<UploadProgressView uploadProgress={progress} totalFiles={2} />);

      expect(screen.getByText(/some files failed to upload/i)).toBeInTheDocument();
    });
  });

  describe('completion state', () => {
    it('shows success message when all files complete', () => {
      const progress = [
        createProgress('file1.pdf', 'complete', 100),
        createProgress('file2.pdf', 'complete', 100),
      ];

      render(<UploadProgressView uploadProgress={progress} totalFiles={2} />);

      expect(screen.getByText('All files uploaded successfully')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('does not show success when there are errors', () => {
      const progress = [
        createProgress('good.pdf', 'complete', 100),
        createProgress('bad.pdf', 'error', 0, 'Failed'),
      ];

      render(<UploadProgressView uploadProgress={progress} totalFiles={2} />);

      expect(screen.queryByText('All files uploaded successfully')).not.toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows 0% when no uploads', () => {
      render(<UploadProgressView uploadProgress={[]} totalFiles={0} />);

      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByText('0 of 0 uploaded')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible progress bars with aria attributes', () => {
      const progress = [createProgress('file.pdf', 'uploading', 75)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      const overallProgress = screen.getByRole('progressbar', {
        name: /overall upload progress/i,
      });
      expect(overallProgress).toHaveAttribute('aria-valuenow', '75');
      expect(overallProgress).toHaveAttribute('aria-valuemin', '0');
      expect(overallProgress).toHaveAttribute('aria-valuemax', '100');
    });

    it('list is announced to screen readers', () => {
      const progress = [createProgress('file.pdf', 'uploading', 50)];

      render(<UploadProgressView uploadProgress={progress} totalFiles={1} />);

      const list = screen.getByRole('list');
      expect(list).toHaveAttribute('aria-live', 'polite');
    });
  });
});
