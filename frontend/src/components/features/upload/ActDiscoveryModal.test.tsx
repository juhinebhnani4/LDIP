import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActDiscoveryModal } from './ActDiscoveryModal';
import type { DetectedAct } from '@/types/upload';

const mockFoundActs: DetectedAct[] = [
  {
    id: '1',
    actName: 'Securities Act, 1992',
    citationCount: 5,
    status: 'found',
    sourceFile: 'Annexure_P3.pdf',
  },
  {
    id: '2',
    actName: 'SARFAESI Act, 2002',
    citationCount: 3,
    status: 'found',
    sourceFile: 'Annexure_K.pdf',
  },
];

const mockMissingActs: DetectedAct[] = [
  {
    id: '3',
    actName: 'BNS Act, 2023',
    citationCount: 12,
    status: 'missing',
  },
  {
    id: '4',
    actName: 'Negotiable Instruments Act',
    citationCount: 8,
    status: 'missing',
  },
];

const allMockActs = [...mockFoundActs, ...mockMissingActs];

describe('ActDiscoveryModal', () => {
  describe('rendering', () => {
    it('does not render when not open', () => {
      render(
        <ActDiscoveryModal
          isOpen={false}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('does not render when no detected acts', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={[]}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders dialog when open with acts', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('renders title', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByText(/act references detected/i)).toBeInTheDocument();
    });

    it('renders description with counts', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByText(/reference 4 acts/i)).toBeInTheDocument();
      expect(screen.getByText(/found 2 in your files/i)).toBeInTheDocument();
    });
  });

  describe('found acts section', () => {
    it('renders found acts with checkmark', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByText(/detected in your files \(2\)/i)).toBeInTheDocument();
      expect(screen.getByText('Securities Act, 1992')).toBeInTheDocument();
      expect(screen.getByText('SARFAESI Act, 2002')).toBeInTheDocument();
    });

    it('shows source file for found acts', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByText(/found in: annexure_p3\.pdf/i)).toBeInTheDocument();
    });
  });

  describe('missing acts section', () => {
    it('renders missing acts with citation count', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByText(/missing acts \(2\)/i)).toBeInTheDocument();
      expect(screen.getByText('BNS Act, 2023')).toBeInTheDocument();
      expect(screen.getByText(/cited 12 times/i)).toBeInTheDocument();
    });

    it('shows singular time when cited once', () => {
      const singleCitationAct: DetectedAct[] = [
        { id: '1', actName: 'Test Act', citationCount: 1, status: 'missing' },
      ];

      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={singleCitationAct}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByText(/cited 1 time$/i)).toBeInTheDocument();
    });

    it('renders Upload Missing Acts button', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /upload missing acts/i })).toBeInTheDocument();
    });
  });

  describe('info note', () => {
    it('renders info note about unverified citations', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByText(/citations to missing acts will show as/i)).toBeInTheDocument();
    });
  });

  describe('actions', () => {
    it('calls onSkip when Skip for Now clicked', async () => {
      const user = userEvent.setup();
      const onSkip = vi.fn();

      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={onSkip}
        />
      );

      await user.click(screen.getByRole('button', { name: /skip for now/i }));

      expect(onSkip).toHaveBeenCalled();
    });

    it('calls onContinue when Continue with Upload clicked', async () => {
      const user = userEvent.setup();
      const onContinue = vi.fn();

      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={onContinue}
          onSkip={vi.fn()}
        />
      );

      await user.click(screen.getByRole('button', { name: /continue with upload/i }));

      expect(onContinue).toHaveBeenCalled();
    });

    it('calls onClose when dialog is closed', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={onClose}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      // Click the close button (X)
      const closeButton = screen.getByRole('button', { name: /close/i });
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('upload missing acts', () => {
    it('has hidden file input for uploading acts', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeInTheDocument();
      expect(fileInput).toHaveClass('hidden');
    });

    it('file input accepts only PDFs', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toHaveAttribute('accept', '.pdf,application/pdf');
    });
  });

  describe('accessibility', () => {
    it('found acts list has proper aria-label', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByRole('list', { name: /found acts/i })).toBeInTheDocument();
    });

    it('missing acts list has proper aria-label', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByRole('list', { name: /missing acts/i })).toBeInTheDocument();
    });

    it('file input is hidden from accessibility tree', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={allMockActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('only found acts', () => {
    it('does not render missing section when no missing acts', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={mockFoundActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      // Check for the missing section header specifically (h4 with "Missing Acts")
      expect(screen.queryByRole('list', { name: /missing acts/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /upload missing acts/i })).not.toBeInTheDocument();
    });
  });

  describe('only missing acts', () => {
    it('does not render found section when no found acts', () => {
      render(
        <ActDiscoveryModal
          isOpen={true}
          onClose={vi.fn()}
          detectedActs={mockMissingActs}
          onUploadMissingActs={vi.fn()}
          onContinue={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.queryByText(/detected in your files/i)).not.toBeInTheDocument();
    });
  });
});
