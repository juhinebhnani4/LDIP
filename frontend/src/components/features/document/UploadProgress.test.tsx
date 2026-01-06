import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UploadProgressList } from './UploadProgress';
import { useUploadStore } from '@/stores/uploadStore';
import type { UploadFile } from '@/types/document';

describe('UploadProgressList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store before each test
    act(() => {
      useUploadStore.getState().clearAll();
    });
  });

  afterEach(() => {
    act(() => {
      useUploadStore.getState().clearAll();
    });
  });

  // Helper to create mock files
  const createMockFile = (
    name: string,
    size: number,
    type: string
  ): File => {
    const file = new File(['x'.repeat(Math.min(size, 100))], name, { type });
    Object.defineProperty(file, 'size', { value: size });
    return file;
  };

  // Helper to add files to store
  const addFilesToStore = (files: File[]): void => {
    act(() => {
      useUploadStore.getState().addFiles(files);
    });
  };

  // Helper to update file status
  const updateFileStatus = (
    id: string,
    status: UploadFile['status'],
    error?: string
  ): void => {
    act(() => {
      useUploadStore.getState().updateStatus(id, status, error);
    });
  };

  // Helper to update file progress
  const updateFileProgress = (id: string, progress: number): void => {
    act(() => {
      useUploadStore.getState().updateProgress(id, progress);
    });
  };

  describe('Rendering', () => {
    it('returns null when upload queue is empty', () => {
      const { container } = render(<UploadProgressList />);
      expect(container.firstChild).toBeNull();
    });

    it('renders file list when files are in queue', () => {
      addFilesToStore([createMockFile('test.pdf', 1024, 'application/pdf')]);

      render(<UploadProgressList />);

      expect(screen.getByText('Uploads (1)')).toBeInTheDocument();
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    it('shows correct file count for multiple files', () => {
      addFilesToStore([
        createMockFile('file1.pdf', 1024, 'application/pdf'),
        createMockFile('file2.pdf', 2048, 'application/pdf'),
        createMockFile('file3.zip', 4096, 'application/zip'),
      ]);

      render(<UploadProgressList />);

      expect(screen.getByText('Uploads (3)')).toBeInTheDocument();
    });

    it('displays formatted file size', () => {
      addFilesToStore([
        createMockFile('large.pdf', 5 * 1024 * 1024, 'application/pdf'),
      ]);

      render(<UploadProgressList />);

      expect(screen.getByText('5 MB')).toBeInTheDocument();
    });
  });

  describe('File Status Display', () => {
    it('shows "Waiting..." for pending files', () => {
      addFilesToStore([createMockFile('pending.pdf', 1024, 'application/pdf')]);

      render(<UploadProgressList />);

      expect(screen.getByText('Waiting...')).toBeInTheDocument();
    });

    it('shows progress bar and percentage for uploading files', () => {
      addFilesToStore([createMockFile('uploading.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileProgress(fileId, 45);

      render(<UploadProgressList />);

      expect(screen.getByText('45%')).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('shows success message for completed files', () => {
      addFilesToStore([createMockFile('done.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileStatus(fileId, 'completed');

      render(<UploadProgressList />);

      expect(screen.getByText('Uploaded successfully')).toBeInTheDocument();
    });

    it('shows error message for failed files', () => {
      addFilesToStore([createMockFile('failed.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileStatus(fileId, 'error', 'Network error');

      render(<UploadProgressList />);

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  describe('Cancel Button', () => {
    it('shows cancel button for pending files', () => {
      addFilesToStore([createMockFile('pending.pdf', 1024, 'application/pdf')]);

      render(<UploadProgressList />);

      expect(
        screen.getByRole('button', { name: /cancel upload for pending\.pdf/i })
      ).toBeInTheDocument();
    });

    it('shows cancel button for uploading files', () => {
      addFilesToStore([createMockFile('uploading.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileProgress(fileId, 50);

      render(<UploadProgressList />);

      expect(
        screen.getByRole('button', { name: /cancel upload for uploading\.pdf/i })
      ).toBeInTheDocument();
    });

    it('hides cancel button for completed files', () => {
      addFilesToStore([createMockFile('done.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileStatus(fileId, 'completed');

      render(<UploadProgressList />);

      expect(
        screen.queryByRole('button', { name: /cancel upload/i })
      ).not.toBeInTheDocument();
    });

    it('hides cancel button for error files', () => {
      addFilesToStore([createMockFile('error.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileStatus(fileId, 'error', 'Failed');

      render(<UploadProgressList />);

      expect(
        screen.queryByRole('button', { name: /cancel upload/i })
      ).not.toBeInTheDocument();
    });

    it('removes file from queue when cancel is clicked', async () => {
      const user = userEvent.setup();
      addFilesToStore([createMockFile('cancel-me.pdf', 1024, 'application/pdf')]);

      render(<UploadProgressList />);

      const cancelButton = screen.getByRole('button', {
        name: /cancel upload for cancel-me\.pdf/i,
      });

      await user.click(cancelButton);

      await waitFor(() => {
        expect(useUploadStore.getState().uploadQueue).toHaveLength(0);
      });
    });

    it('calls onCancelFile callback when provided', async () => {
      const user = userEvent.setup();
      const onCancelFile = vi.fn();
      addFilesToStore([createMockFile('callback.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;

      render(<UploadProgressList onCancelFile={onCancelFile} />);

      const cancelButton = screen.getByRole('button', {
        name: /cancel upload for callback\.pdf/i,
      });

      await user.click(cancelButton);

      expect(onCancelFile).toHaveBeenCalledWith(fileId);
    });
  });

  describe('Clear Completed Button', () => {
    it('shows Clear completed button when completed files exist', () => {
      addFilesToStore([createMockFile('done.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileStatus(fileId, 'completed');

      render(<UploadProgressList />);

      expect(
        screen.getByRole('button', { name: /clear completed/i })
      ).toBeInTheDocument();
    });

    it('hides Clear completed button when no completed files', () => {
      addFilesToStore([createMockFile('pending.pdf', 1024, 'application/pdf')]);

      render(<UploadProgressList />);

      expect(
        screen.queryByRole('button', { name: /clear completed/i })
      ).not.toBeInTheDocument();
    });

    it('removes only completed files when Clear completed is clicked', async () => {
      const user = userEvent.setup();
      addFilesToStore([
        createMockFile('pending.pdf', 1024, 'application/pdf'),
        createMockFile('done.pdf', 1024, 'application/pdf'),
      ]);

      const queue = useUploadStore.getState().uploadQueue;
      updateFileStatus(queue[1].id, 'completed');

      render(<UploadProgressList />);

      const clearButton = screen.getByRole('button', { name: /clear completed/i });
      await user.click(clearButton);

      await waitFor(() => {
        const finalQueue = useUploadStore.getState().uploadQueue;
        expect(finalQueue).toHaveLength(1);
        expect(finalQueue[0].file.name).toBe('pending.pdf');
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible list role', () => {
      addFilesToStore([createMockFile('test.pdf', 1024, 'application/pdf')]);

      render(<UploadProgressList />);

      expect(screen.getByRole('list', { name: /upload queue/i })).toBeInTheDocument();
    });

    it('has accessible list items with file status', () => {
      addFilesToStore([createMockFile('test.pdf', 1024, 'application/pdf')]);

      render(<UploadProgressList />);

      expect(
        screen.getByRole('listitem', { name: /test\.pdf - pending/i })
      ).toBeInTheDocument();
    });

    it('progress bar is accessible with aria-label', () => {
      addFilesToStore([createMockFile('uploading.pdf', 1024, 'application/pdf')]);
      const fileId = useUploadStore.getState().uploadQueue[0].id;
      updateFileProgress(fileId, 75);

      render(<UploadProgressList />);

      // Radix Progress handles aria-valuenow/min/max internally
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute('aria-label', 'Upload progress: 75%');
    });
  });

  describe('Multiple Files', () => {
    it('renders all files in queue', () => {
      addFilesToStore([
        createMockFile('file1.pdf', 1024, 'application/pdf'),
        createMockFile('file2.pdf', 2048, 'application/pdf'),
        createMockFile('file3.zip', 4096, 'application/zip'),
      ]);

      render(<UploadProgressList />);

      expect(screen.getByText('file1.pdf')).toBeInTheDocument();
      expect(screen.getByText('file2.pdf')).toBeInTheDocument();
      expect(screen.getByText('file3.zip')).toBeInTheDocument();
    });

    it('shows mixed statuses correctly', () => {
      addFilesToStore([
        createMockFile('pending.pdf', 1024, 'application/pdf'),
        createMockFile('uploading.pdf', 1024, 'application/pdf'),
        createMockFile('done.pdf', 1024, 'application/pdf'),
      ]);

      const queue = useUploadStore.getState().uploadQueue;
      updateFileProgress(queue[1].id, 50);
      updateFileStatus(queue[2].id, 'completed');

      render(<UploadProgressList />);

      expect(screen.getByText('Waiting...')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
      expect(screen.getByText('Uploaded successfully')).toBeInTheDocument();
    });
  });
});
