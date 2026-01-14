/**
 * VerificationQueue Component Tests
 *
 * Story 8-5: Implement Verification Queue UI (Task 10)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VerificationQueue } from './VerificationQueue';
import { VerificationDecision, VerificationRequirement } from '@/types';
import type { VerificationQueueItem } from '@/types';

const mockItem = (
  id: string,
  confidence: number = 75,
  findingType: string = 'citation_mismatch'
): VerificationQueueItem => ({
  id,
  findingId: `finding-${id}`,
  findingType,
  findingSummary: `Test finding summary for ${id}`,
  confidence,
  requirement: VerificationRequirement.SUGGESTED,
  decision: VerificationDecision.PENDING,
  createdAt: new Date().toISOString(),
  sourceDocument: 'test-doc.pdf',
  engine: 'citation',
});

const defaultProps = {
  data: [mockItem('1'), mockItem('2'), mockItem('3')],
  isLoading: false,
  onApprove: vi.fn(),
  onReject: vi.fn(),
  onFlag: vi.fn(),
  selectedIds: [] as string[],
  onToggleSelect: vi.fn(),
  onSelectAll: vi.fn(),
  processingIds: [] as string[],
};

describe('VerificationQueue', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading skeleton when isLoading is true', () => {
    render(<VerificationQueue {...defaultProps} isLoading={true} data={[]} />);

    // Table should still render but with skeleton rows
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<VerificationQueue {...defaultProps} data={[]} />);

    expect(screen.getByText('No verifications pending.')).toBeInTheDocument();
  });

  it('renders table with data rows', () => {
    render(<VerificationQueue {...defaultProps} />);

    expect(screen.getByText('Test finding summary for 1')).toBeInTheDocument();
    expect(screen.getByText('Test finding summary for 2')).toBeInTheDocument();
    expect(screen.getByText('Test finding summary for 3')).toBeInTheDocument();
  });

  it('renders column headers', () => {
    render(<VerificationQueue {...defaultProps} />);

    expect(screen.getByText('Type')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByText('Confidence')).toBeInTheDocument();
    expect(screen.getByText('Source')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('displays formatted finding type', () => {
    render(<VerificationQueue {...defaultProps} />);

    // citation_mismatch should be formatted as "Citation Mismatch"
    expect(screen.getAllByText('Citation Mismatch').length).toBeGreaterThan(0);
  });

  it('displays confidence percentage', () => {
    render(<VerificationQueue {...defaultProps} />);

    expect(screen.getAllByText('75%').length).toBe(3);
  });

  it('displays source document', () => {
    render(<VerificationQueue {...defaultProps} />);

    expect(screen.getAllByText('test-doc.pdf').length).toBe(3);
  });

  it('calls onApprove when approve button is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationQueue {...defaultProps} />);

    const approveButtons = screen.getAllByLabelText('Approve');
    await user.click(approveButtons[0]!);

    expect(defaultProps.onApprove).toHaveBeenCalledWith('1');
  });

  it('calls onReject when reject button is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationQueue {...defaultProps} />);

    const rejectButtons = screen.getAllByLabelText('Reject');
    await user.click(rejectButtons[0]!);

    expect(defaultProps.onReject).toHaveBeenCalledWith('1');
  });

  it('calls onFlag when flag button is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationQueue {...defaultProps} />);

    const flagButtons = screen.getAllByLabelText('Flag');
    await user.click(flagButtons[0]!);

    expect(defaultProps.onFlag).toHaveBeenCalledWith('1');
  });

  it('calls onToggleSelect when checkbox is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationQueue {...defaultProps} />);

    const checkboxes = screen.getAllByRole('checkbox');
    // First checkbox is "select all", second is first row
    await user.click(checkboxes[1]!);

    expect(defaultProps.onToggleSelect).toHaveBeenCalledWith('1');
  });

  it('shows checkboxes as checked for selected items', () => {
    render(<VerificationQueue {...defaultProps} selectedIds={['1', '2']} />);

    const checkboxes = screen.getAllByRole('checkbox');
    // Skip header checkbox, check row checkboxes
    expect(checkboxes[1]).toHaveAttribute('data-state', 'checked');
    expect(checkboxes[2]).toHaveAttribute('data-state', 'checked');
    expect(checkboxes[3]).not.toHaveAttribute('data-state', 'checked');
  });

  it('disables actions for processing items', () => {
    render(<VerificationQueue {...defaultProps} processingIds={['1']} />);

    // First row should have disabled buttons
    const row = screen.getByText('Test finding summary for 1').closest('tr');
    expect(row).toHaveClass('opacity-50');
  });

  it('disables checkbox for processing items', () => {
    render(<VerificationQueue {...defaultProps} processingIds={['1']} />);

    const checkboxes = screen.getAllByRole('checkbox');
    // Second checkbox (first data row) should be disabled
    expect(checkboxes[1]).toBeDisabled();
  });

  it('calls onSelectAll with all IDs when header checkbox is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationQueue {...defaultProps} />);

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]!); // Header checkbox

    expect(defaultProps.onSelectAll).toHaveBeenCalledWith(['1', '2', '3']);
  });

  it('renders different confidence colors based on value', () => {
    const data = [
      mockItem('1', 95), // High - green
      mockItem('2', 80), // Medium - yellow
      mockItem('3', 60), // Low - red
    ];

    const { container } = render(
      <VerificationQueue {...defaultProps} data={data} />
    );

    // Check that confidence bars exist with different colors
    const confidenceBars = container.querySelectorAll('[class*="bg-green-500"], [class*="bg-yellow-500"], [class*="bg-red-500"]');
    expect(confidenceBars.length).toBe(3);
  });
});
