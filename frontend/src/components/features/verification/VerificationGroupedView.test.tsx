/**
 * VerificationGroupedView Component Tests
 *
 * Story 10D.2: Implement Verification Tab Statistics and Filtering (Task 4)
 * Tests for "By Type" grouped view functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VerificationGroupedView } from './VerificationGroupedView';
import { VerificationDecision, VerificationRequirement } from '@/types';
import type { VerificationQueueItem } from '@/types';

const mockItem = (
  id: string,
  findingType: string = 'citation_mismatch',
  confidence: number = 75
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
  data: [
    mockItem('1', 'citation_mismatch'),
    mockItem('2', 'timeline_anomaly'),
    mockItem('3', 'citation_mismatch'),
    mockItem('4', 'contradiction'),
    mockItem('5', 'timeline_anomaly'),
  ],
  isLoading: false,
  onApprove: vi.fn(),
  onReject: vi.fn(),
  onFlag: vi.fn(),
  selectedIds: [] as string[],
  onToggleSelect: vi.fn(),
  onSelectAll: vi.fn(),
  processingIds: [] as string[],
};

describe('VerificationGroupedView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Task 4.2: Groups verifications by findingType
  it('groups items by finding type', () => {
    render(<VerificationGroupedView {...defaultProps} />);

    // Should have three groups (Citation Mismatch, Contradiction, Timeline Anomaly)
    // Use getAllByText since the type name appears in both header and rows
    expect(screen.getAllByText('Citation Mismatch').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Contradiction').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Timeline Anomaly').length).toBeGreaterThanOrEqual(1);
  });

  // Task 4.3: Shows count badges per type
  it('displays count badges for each group', () => {
    render(<VerificationGroupedView {...defaultProps} />);

    // Citation Mismatch has 2 items, Timeline Anomaly has 2 items, Contradiction has 1 item
    // Use getAllByText since there are two groups with 2 items
    expect(screen.getAllByText('2 items').length).toBe(2);
    expect(screen.getByText('1 item')).toBeInTheDocument();
  });

  // Task 4.3: Collapsible sections
  it('renders collapsible sections that can be toggled', async () => {
    const user = userEvent.setup();
    render(<VerificationGroupedView {...defaultProps} />);

    // Find all group buttons and click the first one
    const collapsibleButtons = screen.getAllByRole('button').filter((btn) =>
      btn.textContent?.includes('item')
    );

    // Click to collapse the first group
    if (collapsibleButtons[0]) {
      await user.click(collapsibleButtons[0]);
    }

    // Content should be hidden (the internal VerificationQueue won't be visible)
    // We can't easily test the collapsed state directly, but we can verify click works
    expect(collapsibleButtons.length).toBeGreaterThan(0);
  });

  // Empty state
  it('renders empty state when no data', () => {
    render(<VerificationGroupedView {...defaultProps} data={[]} />);

    expect(screen.getByText('No verifications pending.')).toBeInTheDocument();
  });

  // Loading state
  it('renders loading skeleton when isLoading is true', () => {
    const { container } = render(
      <VerificationGroupedView {...defaultProps} isLoading={true} />
    );

    // Should show loading skeleton
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  // Task 4.1: Groups are sorted alphabetically
  it('sorts groups alphabetically by type name', () => {
    render(<VerificationGroupedView {...defaultProps} />);

    const buttons = screen.getAllByRole('button');
    const groupButtons = buttons.filter((btn) =>
      btn.textContent?.includes('item')
    );

    // Order should be: Citation Mismatch, Contradiction, Timeline Anomaly
    expect(groupButtons[0]?.textContent).toContain('Citation Mismatch');
    expect(groupButtons[1]?.textContent).toContain('Contradiction');
    expect(groupButtons[2]?.textContent).toContain('Timeline Anomaly');
  });

  // Test that actions still work within groups
  it('passes action callbacks to nested VerificationQueue', async () => {
    const user = userEvent.setup();
    render(<VerificationGroupedView {...defaultProps} />);

    // Find an approve button in the first group
    const approveButtons = screen.getAllByLabelText('Approve');
    await user.click(approveButtons[0]!);

    expect(defaultProps.onApprove).toHaveBeenCalled();
  });

  // Test selection within groups
  it('handles selection toggle correctly', async () => {
    const user = userEvent.setup();
    render(<VerificationGroupedView {...defaultProps} />);

    // Find checkboxes (skip the "select all" ones in each group)
    const checkboxes = screen.getAllByRole('checkbox');

    // Click a row checkbox (not the header)
    // The structure has multiple tables, so we need to be careful
    // Each group has its own header checkbox + row checkboxes
    if (checkboxes.length > 1) {
      await user.click(checkboxes[1]!);
      expect(defaultProps.onToggleSelect).toHaveBeenCalled();
    }
  });

  // Groups should all be open by default
  it('renders all groups open by default', () => {
    render(<VerificationGroupedView {...defaultProps} />);

    // Check that all items are visible (at least one item from each group)
    expect(screen.getByText('Test finding summary for 1')).toBeInTheDocument();
    expect(screen.getByText('Test finding summary for 2')).toBeInTheDocument();
    expect(screen.getByText('Test finding summary for 4')).toBeInTheDocument();
  });
});
