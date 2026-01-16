/**
 * ExportVerificationCheck Component Tests
 *
 * Story 12.3: Export Verification Check and Format Generation
 *
 * Tests for the export eligibility check dialog component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportVerificationCheck } from './ExportVerificationCheck';
import type { ExportEligibility } from '@/types';

// Mock the verifications API
vi.mock('@/lib/api/verifications', () => ({
  checkExportEligibility: vi.fn(),
}));

// Import the mocked function
import { checkExportEligibility } from '@/lib/api/verifications';
const mockCheckExportEligibility = vi.mocked(checkExportEligibility);

// Helper to create mock eligibility results
const createMockEligibility = (
  overrides: Partial<ExportEligibility> = {}
): ExportEligibility => ({
  eligible: true,
  blockingFindings: [],
  blockingCount: 0,
  warningFindings: [],
  warningCount: 0,
  message: 'All findings verified',
  ...overrides,
});

describe('ExportVerificationCheck', () => {
  const defaultProps = {
    matterId: 'test-matter-123',
    open: true,
    onOpenChange: vi.fn(),
    onProceed: vi.fn(),
    onNavigateToQueue: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading state while checking eligibility', async () => {
      // Create a promise that never resolves to keep loading state
      mockCheckExportEligibility.mockImplementation(
        () => new Promise(() => {})
      );

      render(<ExportVerificationCheck {...defaultProps} />);

      expect(screen.getByText('Checking Export Eligibility...')).toBeInTheDocument();
      expect(screen.getByText('Verifying all findings meet export requirements...')).toBeInTheDocument();
    });
  });

  describe('Ready to Export (No Issues)', () => {
    it('shows ready state when all findings verified', async () => {
      mockCheckExportEligibility.mockResolvedValue(createMockEligibility());

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Ready to Export')).toBeInTheDocument();
      });

      expect(screen.getByText('All findings meet the verification requirements for export.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Continue to Export' })).toBeInTheDocument();
    });

    it('calls onProceed when Continue to Export clicked', async () => {
      mockCheckExportEligibility.mockResolvedValue(createMockEligibility());
      const user = userEvent.setup();

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Ready to Export')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Continue to Export' }));

      expect(defaultProps.onProceed).toHaveBeenCalledTimes(1);
      expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Export Blocked (Blocking Findings)', () => {
    it('shows blocked state with blocking findings', async () => {
      mockCheckExportEligibility.mockResolvedValue(
        createMockEligibility({
          eligible: false,
          blockingCount: 2,
          blockingFindings: [
            {
              verificationId: 'ver-1',
              findingId: 'find-1',
              findingType: 'citation_mismatch',
              findingSummary: 'Citation does not match source',
              confidence: 45,
            },
            {
              verificationId: 'ver-2',
              findingId: 'find-2',
              findingType: 'timeline_anomaly',
              findingSummary: 'Date inconsistency detected',
              confidence: 60,
            },
          ],
          message: 'Export blocked: 2 findings require verification',
        })
      );

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export Blocked')).toBeInTheDocument();
      });

      expect(screen.getByText(/2 finding\(s\) with low confidence must be verified/)).toBeInTheDocument();
      expect(screen.getByText('Requires Verification (2)')).toBeInTheDocument();
      expect(screen.getByText('Citation Mismatch')).toBeInTheDocument();
      expect(screen.getByText('Timeline Anomaly')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Go to Verification Queue/ })).toBeInTheDocument();
    });

    it('does not show Continue button when blocked', async () => {
      mockCheckExportEligibility.mockResolvedValue(
        createMockEligibility({
          eligible: false,
          blockingCount: 1,
          blockingFindings: [
            {
              verificationId: 'ver-1',
              findingId: null,
              findingType: 'contradiction',
              findingSummary: 'Statements conflict',
              confidence: 50,
            },
          ],
        })
      );

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export Blocked')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: 'Continue to Export' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Continue with Warnings' })).not.toBeInTheDocument();
    });

    it('navigates to queue when Go to Verification Queue clicked', async () => {
      mockCheckExportEligibility.mockResolvedValue(
        createMockEligibility({
          eligible: false,
          blockingCount: 1,
          blockingFindings: [
            {
              verificationId: 'ver-1',
              findingId: 'find-1',
              findingType: 'citation_mismatch',
              findingSummary: 'Test finding',
              confidence: 65,
            },
          ],
        })
      );
      const user = userEvent.setup();

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export Blocked')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Go to Verification Queue/ }));

      expect(defaultProps.onNavigateToQueue).toHaveBeenCalledTimes(1);
      expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Export with Warnings', () => {
    it('shows warning state with warning findings', async () => {
      mockCheckExportEligibility.mockResolvedValue(
        createMockEligibility({
          eligible: true,
          warningCount: 2,
          warningFindings: [
            {
              verificationId: 'ver-1',
              findingId: 'find-1',
              findingType: 'entity_reference',
              findingSummary: 'Entity may be incorrect',
              confidence: 75,
            },
            {
              verificationId: 'ver-2',
              findingId: 'find-2',
              findingType: 'date_extraction',
              findingSummary: 'Date precision uncertain',
              confidence: 85,
            },
          ],
          message: 'Export allowed with 2 warnings',
        })
      );

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export Available with Warnings')).toBeInTheDocument();
      });

      expect(screen.getByText(/2 finding\(s\) are suggested for verification/)).toBeInTheDocument();
      expect(screen.getByText('Suggested for Verification (2)')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Continue with Warnings' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Verify First/ })).toBeInTheDocument();
    });

    it('proceeds with warnings when Continue with Warnings clicked', async () => {
      mockCheckExportEligibility.mockResolvedValue(
        createMockEligibility({
          eligible: true,
          warningCount: 1,
          warningFindings: [
            {
              verificationId: 'ver-1',
              findingId: 'find-1',
              findingType: 'entity_reference',
              findingSummary: 'Minor warning',
              confidence: 80,
            },
          ],
        })
      );
      const user = userEvent.setup();

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export Available with Warnings')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Continue with Warnings' }));

      expect(defaultProps.onProceed).toHaveBeenCalledTimes(1);
      expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Error Handling', () => {
    it('shows error state when eligibility check fails', async () => {
      mockCheckExportEligibility.mockRejectedValue(new Error('Network error'));

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Eligibility Check Failed')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByText('Unable to verify export eligibility. Please try again.')).toBeInTheDocument();
    });

    it('shows generic error for non-Error rejections', async () => {
      mockCheckExportEligibility.mockRejectedValue('Unknown error');

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Eligibility Check Failed')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to check export eligibility')).toBeInTheDocument();
    });
  });

  describe('Dialog Lifecycle', () => {
    it('fetches eligibility when dialog opens', async () => {
      mockCheckExportEligibility.mockResolvedValue(createMockEligibility());

      const { rerender } = render(
        <ExportVerificationCheck {...defaultProps} open={false} />
      );

      expect(mockCheckExportEligibility).not.toHaveBeenCalled();

      rerender(<ExportVerificationCheck {...defaultProps} open={true} />);

      await waitFor(() => {
        expect(mockCheckExportEligibility).toHaveBeenCalledWith('test-matter-123');
      });
    });

    it('resets state when dialog closes', async () => {
      mockCheckExportEligibility.mockResolvedValue(createMockEligibility());

      const { rerender } = render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Ready to Export')).toBeInTheDocument();
      });

      rerender(<ExportVerificationCheck {...defaultProps} open={false} />);

      // State should be reset, re-opening should trigger new fetch
      rerender(<ExportVerificationCheck {...defaultProps} open={true} />);

      await waitFor(() => {
        expect(mockCheckExportEligibility).toHaveBeenCalledTimes(2);
      });
    });

    it('renders Cancel button', async () => {
      mockCheckExportEligibility.mockResolvedValue(createMockEligibility());

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Ready to Export')).toBeInTheDocument();
      });

      // Cancel button should be present - dialog closing is handled by AlertDialogCancel
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });
  });

  describe('Null Safety (Issue #7)', () => {
    it('handles findings with missing verificationId', async () => {
      mockCheckExportEligibility.mockResolvedValue(
        createMockEligibility({
          eligible: false,
          blockingCount: 1,
          blockingFindings: [
            {
              verificationId: undefined as unknown as string, // Simulate missing ID
              findingId: null,
              findingType: 'test_type',
              findingSummary: 'Test summary',
              confidence: 50,
            },
          ],
        })
      );

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export Blocked')).toBeInTheDocument();
      });

      // Should render without crashing
      expect(screen.getByText('Test Type')).toBeInTheDocument();
      expect(screen.getByText('Test summary')).toBeInTheDocument();
    });

    it('handles findings with missing properties', async () => {
      mockCheckExportEligibility.mockResolvedValue(
        createMockEligibility({
          eligible: true,
          warningCount: 1,
          warningFindings: [
            {
              verificationId: 'ver-1',
              findingId: null,
              findingType: undefined as unknown as string,
              findingSummary: undefined as unknown as string,
              confidence: undefined as unknown as number,
            },
          ],
        })
      );

      render(<ExportVerificationCheck {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Export Available with Warnings')).toBeInTheDocument();
      });

      // Should render with fallback values
      expect(screen.getByText('Unknown')).toBeInTheDocument();
      expect(screen.getByText('No summary available')).toBeInTheDocument();
      expect(screen.getByText('0% confidence')).toBeInTheDocument();
    });
  });
});
