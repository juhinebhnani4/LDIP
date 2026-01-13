import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActDiscoveryItem } from './ActDiscoveryItem';
import type { ActDiscoverySummary } from '@/types';

describe('ActDiscoveryItem', () => {
  const mockOnUpload = vi.fn();
  const mockOnSkip = vi.fn();

  const mockAvailableAct: ActDiscoverySummary = {
    actName: 'Securities Act, 1992',
    actNameNormalized: 'securities_act_1992',
    citationCount: 5,
    resolutionStatus: 'available',
    userAction: 'uploaded',
    actDocumentId: 'doc-123',
  };

  const mockMissingAct: ActDiscoverySummary = {
    actName: 'Negotiable Instruments Act, 1881',
    actNameNormalized: 'negotiable_instruments_act_1881',
    citationCount: 12,
    resolutionStatus: 'missing',
    userAction: 'pending',
    actDocumentId: null,
  };

  const mockSkippedAct: ActDiscoverySummary = {
    actName: 'Companies Act, 2013',
    actNameNormalized: 'companies_act_2013',
    citationCount: 3,
    resolutionStatus: 'skipped',
    userAction: 'skipped',
    actDocumentId: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Display', () => {
    it('displays act name', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();
    });

    it('displays citation count for available acts', () => {
      render(
        <ActDiscoveryItem
          act={mockAvailableAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(screen.getByText('5 citations')).toBeInTheDocument();
    });

    it('displays singular citation count correctly', () => {
      const singleCitationAct: ActDiscoverySummary = {
        ...mockAvailableAct,
        citationCount: 1,
      };

      render(
        <ActDiscoveryItem
          act={singleCitationAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(screen.getByText('1 citation')).toBeInTheDocument();
    });
  });

  describe('Status Badges', () => {
    it('shows Available badge for available acts', () => {
      render(
        <ActDiscoveryItem
          act={mockAvailableAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(screen.getByText('Available')).toBeInTheDocument();
    });

    it('shows Missing badge with citation count for missing acts', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(screen.getByText(/Missing \(12 citations\)/i)).toBeInTheDocument();
    });

    it('shows Skipped badge for skipped acts', () => {
      render(
        <ActDiscoveryItem
          act={mockSkippedAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(screen.getByText('Skipped')).toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    it('shows Upload button for missing acts', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(
        screen.getByRole('button', { name: /upload negotiable instruments act/i })
      ).toBeInTheDocument();
    });

    it('shows Skip button for missing acts', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(
        screen.getByRole('button', { name: /skip negotiable instruments act/i })
      ).toBeInTheDocument();
    });

    it('does not show action buttons for available acts', () => {
      render(
        <ActDiscoveryItem
          act={mockAvailableAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(
        screen.queryByRole('button', { name: /upload/i })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: /skip/i })
      ).not.toBeInTheDocument();
    });

    it('does not show action buttons for skipped acts', () => {
      render(
        <ActDiscoveryItem
          act={mockSkippedAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(
        screen.queryByRole('button', { name: /upload/i })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: /skip/i })
      ).not.toBeInTheDocument();
    });
  });

  describe('Button Callbacks', () => {
    it('calls onUpload with act name when Upload is clicked', async () => {
      const user = userEvent.setup();

      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      const uploadButton = screen.getByRole('button', {
        name: /upload negotiable instruments act/i,
      });
      await user.click(uploadButton);

      expect(mockOnUpload).toHaveBeenCalledWith('Negotiable Instruments Act, 1881');
      expect(mockOnUpload).toHaveBeenCalledTimes(1);
    });

    it('calls onSkip with act name when Skip is clicked', async () => {
      const user = userEvent.setup();

      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      const skipButton = screen.getByRole('button', {
        name: /skip negotiable instruments act/i,
      });
      await user.click(skipButton);

      expect(mockOnSkip).toHaveBeenCalledWith('Negotiable Instruments Act, 1881');
      expect(mockOnSkip).toHaveBeenCalledTimes(1);
    });
  });

  describe('Disabled State', () => {
    it('disables buttons when isDisabled is true', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
          isDisabled={true}
        />
      );

      expect(
        screen.getByRole('button', { name: /upload/i })
      ).toBeDisabled();
      expect(
        screen.getByRole('button', { name: /skip/i })
      ).toBeDisabled();
    });

    it('disables buttons when isUploading is true', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
          isUploading={true}
        />
      );

      expect(
        screen.getByRole('button', { name: /upload/i })
      ).toBeDisabled();
      expect(
        screen.getByRole('button', { name: /skip/i })
      ).toBeDisabled();
    });
  });

  describe('Accessibility', () => {
    it('has accessible list item role', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      expect(screen.getByRole('listitem')).toBeInTheDocument();
    });

    it('has accessible aria-label with act info', () => {
      render(
        <ActDiscoveryItem
          act={mockMissingAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      const listItem = screen.getByRole('listitem');
      expect(listItem).toHaveAttribute(
        'aria-label',
        'Negotiable Instruments Act, 1881, missing, 12 citations'
      );
    });

    it('badges have accessible aria-labels', () => {
      render(
        <ActDiscoveryItem
          act={mockAvailableAct}
          onUpload={mockOnUpload}
          onSkip={mockOnSkip}
        />
      );

      const badge = screen.getByText('Available');
      expect(badge).toHaveAttribute('aria-label', 'Act available for verification');
    });
  });
});
