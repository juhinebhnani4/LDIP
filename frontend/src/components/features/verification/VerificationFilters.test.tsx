/**
 * VerificationFilters Component Tests
 *
 * Story 10D.2: Implement Verification Tab Statistics and Filtering (Task 2)
 * Tests filtering functionality for AC #2
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VerificationFilters } from './VerificationFilters';
import { VerificationDecision } from '@/types';
import type { VerificationFilters as FiltersType } from '@/types';

const defaultFilters: FiltersType = {
  findingType: null,
  confidenceTier: null,
  status: null,
  view: 'queue',
};

const defaultProps = {
  filters: defaultFilters,
  onFiltersChange: vi.fn(),
  onReset: vi.fn(),
  findingTypes: ['citation_mismatch', 'timeline_anomaly', 'contradiction'],
  hasActiveFilters: false,
};

describe('VerificationFilters', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Task 2.1: Finding type dropdown filters queue correctly
  describe('Finding Type Filter (2.1)', () => {
    it('renders finding type dropdown with all types', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      // Open the dropdown (first combobox is finding type)
      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[0]!);

      // Check all types are present - use getAllByText where text may appear multiple times
      expect(screen.getAllByText('All Types').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Citation Mismatch')).toBeInTheDocument();
      expect(screen.getByText('Timeline Anomaly')).toBeInTheDocument();
      expect(screen.getByText('Contradiction')).toBeInTheDocument();
    });

    it('calls onFiltersChange when finding type is selected', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[0]!);
      await user.click(screen.getByText('Citation Mismatch'));

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        findingType: 'citation_mismatch',
      });
    });

    it('clears finding type when "All Types" is selected', async () => {
      const user = userEvent.setup();
      const filtersWithType = { ...defaultFilters, findingType: 'citation_mismatch' };
      render(<VerificationFilters {...defaultProps} filters={filtersWithType} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[0]!);
      await user.click(screen.getByText('All Types'));

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        findingType: null,
      });
    });
  });

  // Task 2.2: Confidence tier filter works correctly
  describe('Confidence Tier Filter (2.2)', () => {
    it('renders confidence tier dropdown with all tiers', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      // Second combobox is confidence tier
      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[1]!);

      // Use getAllByText for All Confidence since it may appear in both trigger and option
      expect(screen.getAllByText('All Confidence').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Low.*<70%/)).toBeInTheDocument();
      expect(screen.getByText(/Medium.*70-90%/)).toBeInTheDocument();
      expect(screen.getByText(/High.*>90%/)).toBeInTheDocument();
    });

    it('calls onFiltersChange when confidence tier is selected', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[1]!);
      await user.click(screen.getByText(/Low.*<70%/));

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        confidenceTier: 'low',
      });
    });

    it('clears confidence tier when "All Confidence" is selected', async () => {
      const user = userEvent.setup();
      const filtersWithTier = { ...defaultFilters, confidenceTier: 'low' as const };
      render(<VerificationFilters {...defaultProps} filters={filtersWithTier} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[1]!);
      await user.click(screen.getByText('All Confidence'));

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        confidenceTier: null,
      });
    });
  });

  // Task 2.3: Verification status filter works correctly
  describe('Verification Status Filter (2.3)', () => {
    it('renders status dropdown with all statuses', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      // Third combobox is status
      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[2]!);

      // Use getAllByText for All Status since it appears in both trigger and option
      expect(screen.getAllByText('All Status').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Pending')).toBeInTheDocument();
      expect(screen.getByText('Approved')).toBeInTheDocument();
      expect(screen.getByText('Rejected')).toBeInTheDocument();
      expect(screen.getByText('Flagged')).toBeInTheDocument();
    });

    it('calls onFiltersChange when status is selected', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[2]!);
      await user.click(screen.getByText('Pending'));

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        status: VerificationDecision.PENDING,
      });
    });

    it('clears status when "All Status" is selected', async () => {
      const user = userEvent.setup();
      const filtersWithStatus = { ...defaultFilters, status: VerificationDecision.PENDING };
      render(<VerificationFilters {...defaultProps} filters={filtersWithStatus} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[2]!);
      await user.click(screen.getByText('All Status'));

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        status: null,
      });
    });
  });

  // Task 2.5: Clear Filters button resets all filters
  describe('Clear Filters (2.5)', () => {
    it('does not show Clear Filters button when no filters active', () => {
      render(<VerificationFilters {...defaultProps} />);

      expect(screen.queryByText('Clear Filters')).not.toBeInTheDocument();
    });

    it('shows Clear Filters button when findingType filter is active', () => {
      const filtersWithType = { ...defaultFilters, findingType: 'citation_mismatch' };
      render(<VerificationFilters {...defaultProps} filters={filtersWithType} />);

      expect(screen.getByText('Clear Filters')).toBeInTheDocument();
    });

    it('shows Clear Filters button when confidenceTier filter is active', () => {
      const filtersWithTier = { ...defaultFilters, confidenceTier: 'low' as const };
      render(<VerificationFilters {...defaultProps} filters={filtersWithTier} />);

      expect(screen.getByText('Clear Filters')).toBeInTheDocument();
    });

    it('shows Clear Filters button when status filter is active', () => {
      const filtersWithStatus = { ...defaultFilters, status: VerificationDecision.PENDING };
      render(<VerificationFilters {...defaultProps} filters={filtersWithStatus} />);

      expect(screen.getByText('Clear Filters')).toBeInTheDocument();
    });

    it('shows Clear Filters button when hasActiveFilters prop is true', () => {
      render(<VerificationFilters {...defaultProps} hasActiveFilters={true} />);

      expect(screen.getByText('Clear Filters')).toBeInTheDocument();
    });

    it('calls onReset when Clear Filters button is clicked', async () => {
      const user = userEvent.setup();
      const filtersWithType = { ...defaultFilters, findingType: 'citation_mismatch' };
      render(<VerificationFilters {...defaultProps} filters={filtersWithType} />);

      await user.click(screen.getByText('Clear Filters'));

      expect(defaultProps.onReset).toHaveBeenCalledTimes(1);
    });
  });

  // Task 2.4: Test combined filters (via onFiltersChange being called correctly)
  describe('Combined Filters (2.4)', () => {
    it('allows multiple filters to be set independently', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      // Get all comboboxes
      const comboboxes = screen.getAllByRole('combobox');

      // Select finding type (first combobox)
      await user.click(comboboxes[0]!);
      await user.click(screen.getByText('Citation Mismatch'));

      expect(defaultProps.onFiltersChange).toHaveBeenLastCalledWith({
        findingType: 'citation_mismatch',
      });

      // Select confidence tier (second combobox)
      await user.click(comboboxes[1]!);
      await user.click(screen.getByText(/Low.*<70%/));

      expect(defaultProps.onFiltersChange).toHaveBeenLastCalledWith({
        confidenceTier: 'low',
      });

      // Each filter change should have been called independently
      expect(defaultProps.onFiltersChange).toHaveBeenCalledTimes(2);
    });
  });

  // View mode selector tests
  describe('View Mode Selector', () => {
    it('renders view mode dropdown with enabled By Type option', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      // Fourth combobox is view mode
      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[3]!);

      // Use getAllByText for Queue View since it appears in both trigger and option
      expect(screen.getAllByText('Queue View').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('By Type')).toBeInTheDocument();
      expect(screen.getByText(/History.*coming soon/i)).toBeInTheDocument();
    });

    it('calls onFiltersChange when By Type view is selected', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[3]!);
      await user.click(screen.getByText('By Type'));

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        view: 'by-type',
      });
    });

    it('has History option disabled', async () => {
      const user = userEvent.setup();
      render(<VerificationFilters {...defaultProps} />);

      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[3]!);

      // The "History" option should be disabled
      const historyOption = screen.getByText(/History.*coming soon/i);
      expect(historyOption.closest('[role="option"]')).toHaveAttribute('data-disabled');
    });
  });
});
