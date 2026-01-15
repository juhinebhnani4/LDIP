import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UploadWizard } from './UploadWizard';
import { useUploadWizardStore } from '@/stores/uploadWizardStore';

// Mock Next.js navigation
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Helper to create mock files
function createMockFile(name: string, size: number = 1024): File {
  const file = new File(['test content'], name, { type: 'application/pdf' });
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

describe('UploadWizard', () => {
  beforeEach(() => {
    // Reset store and mocks before each test
    useUploadWizardStore.getState().reset();
    mockPush.mockClear();
  });

  describe('initial render (Stage 1)', () => {
    it('renders page title', () => {
      render(<UploadWizard />);

      expect(screen.getByRole('heading', { name: /create new matter/i })).toBeInTheDocument();
    });

    it('renders back to dashboard link', () => {
      render(<UploadWizard />);

      expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute('href', '/');
    });

    it('renders file drop zone', () => {
      render(<UploadWizard />);

      expect(screen.getByText(/drag & drop your case files here/i)).toBeInTheDocument();
    });

    it('does not render matter name input in Stage 1', () => {
      render(<UploadWizard />);

      expect(screen.queryByLabelText(/matter name/i)).not.toBeInTheDocument();
    });

    it('does not render Start Processing button in Stage 1', () => {
      render(<UploadWizard />);

      expect(screen.queryByRole('button', { name: /start processing/i })).not.toBeInTheDocument();
    });
  });

  describe('file selection transition to Stage 2', () => {
    it('transitions to review stage when files are dropped', async () => {
      render(<UploadWizard />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      const file = createMockFile('test_document.pdf');
      const dataTransfer = createMockDataTransfer([file]);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(screen.getByLabelText(/matter name/i)).toBeInTheDocument();
      });
    });

    it('auto-generates matter name from first file', async () => {
      render(<UploadWizard />);

      const dropZone = screen.getByRole('button', { name: /drop files here or click to browse/i });
      const file = createMockFile('Shah_v_Mehta_Securities.pdf');
      const dataTransfer = createMockDataTransfer([file]);

      fireEvent.drop(dropZone, { dataTransfer });

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('Shah v Mehta Securities');
      });
    });
  });

  describe('Stage 2 - Review', () => {
    beforeEach(() => {
      // Set up store with a file to start in Stage 2
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
    });

    it('renders matter name input', () => {
      render(<UploadWizard />);

      expect(screen.getByLabelText(/matter name/i)).toBeInTheDocument();
    });

    it('renders file review list', () => {
      render(<UploadWizard />);

      expect(screen.getByRole('list', { name: /selected files/i })).toBeInTheDocument();
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    it('renders Cancel button', () => {
      render(<UploadWizard />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('renders Start Processing button', () => {
      render(<UploadWizard />);

      expect(screen.getByRole('button', { name: /start processing/i })).toBeInTheDocument();
    });

    it('allows editing matter name', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      const input = screen.getByRole('textbox');
      await user.clear(input);
      await user.type(input, 'Custom Matter Name');

      expect(input).toHaveValue('Custom Matter Name');
    });

    it('allows removing files', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      const removeButton = screen.getByRole('button', { name: /remove test\.pdf/i });
      await user.click(removeButton);

      // Should return to Stage 1 when all files removed
      await waitFor(() => {
        expect(screen.getByText(/drag & drop your case files here/i)).toBeInTheDocument();
      });
    });

    it('disables Start Processing when matter name is empty', async () => {
      const user = userEvent.setup();
      useUploadWizardStore.getState().setMatterName('');
      render(<UploadWizard />);

      const input = screen.getByRole('textbox');
      await user.clear(input);

      await waitFor(() => {
        const button = screen.getByRole('button', { name: /start processing/i });
        expect(button).toBeDisabled();
      });
    });
  });

  describe('Cancel action', () => {
    beforeEach(() => {
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
    });

    it('resets store when Cancel clicked', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(useUploadWizardStore.getState().files).toEqual([]);
    });

    it('navigates to dashboard when Cancel clicked', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('Start Processing action', () => {
    beforeEach(() => {
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().setMatterName('Test Matter');
    });

    it('shows Act Discovery modal when Start Processing clicked', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      await user.click(screen.getByRole('button', { name: /start processing/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/act references detected/i)).toBeInTheDocument();
      });
    });
  });

  describe('Act Discovery Modal interactions', () => {
    beforeEach(() => {
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().setMatterName('Test Matter');
    });

    it('navigates to processing on Continue with Upload', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      // Open modal
      await user.click(screen.getByRole('button', { name: /start processing/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Click continue
      await user.click(screen.getByRole('button', { name: /continue with upload/i }));

      expect(mockPush).toHaveBeenCalledWith('/upload/processing');
    });

    it('closes modal and returns to review on Skip for Now', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      // Open modal
      await user.click(screen.getByRole('button', { name: /start processing/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Click skip
      await user.click(screen.getByRole('button', { name: /skip for now/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });

      // Should still be in review stage
      expect(screen.getByLabelText(/matter name/i)).toBeInTheDocument();
    });

    it('shows modal only once per session', async () => {
      const user = userEvent.setup();
      render(<UploadWizard />);

      // Open modal first time
      await user.click(screen.getByRole('button', { name: /start processing/i }));
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Skip
      await user.click(screen.getByRole('button', { name: /skip for now/i }));
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });

      // Click Start Processing again
      await user.click(screen.getByRole('button', { name: /start processing/i }));

      // Should navigate directly without showing modal
      expect(mockPush).toHaveBeenCalledWith('/upload/processing');
    });
  });

  describe('loading state', () => {
    beforeEach(() => {
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().setMatterName('Test Matter');
    });

    it('disables Start Processing button when loading', () => {
      useUploadWizardStore.getState().setLoading(true);
      render(<UploadWizard />);

      expect(screen.getByRole('button', { name: /processing/i })).toBeDisabled();
    });

    it('shows loading spinner when loading', () => {
      useUploadWizardStore.getState().setLoading(true);
      render(<UploadWizard />);

      // The button text changes to Processing...
      expect(screen.getByText(/processing\.\.\./i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible back link', () => {
      render(<UploadWizard />);

      expect(screen.getByRole('link', { name: /back to dashboard/i })).toBeInTheDocument();
    });

    it('main content has proper heading hierarchy', () => {
      render(<UploadWizard />);

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent(/create new matter/i);
    });
  });
});
