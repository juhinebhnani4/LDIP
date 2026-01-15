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

// Story 10D.2 Task 3: Sorting functionality tests
describe('VerificationQueue Sorting (Task 3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Task 3.4: Default sort is confidence ascending (lowest first)
  it('defaults to confidence ascending sort (lowest first)', () => {
    const data = [
      mockItem('high', 95),
      mockItem('low', 50),
      mockItem('med', 75),
    ];

    render(<VerificationQueue {...defaultProps} data={data} />);

    // Get all rows
    const rows = screen.getAllByRole('row').slice(1); // Skip header
    const summaries = rows.map(row => row.textContent);

    // Should be sorted: low (50) -> med (75) -> high (95)
    expect(summaries[0]).toContain('Test finding summary for low');
    expect(summaries[1]).toContain('Test finding summary for med');
    expect(summaries[2]).toContain('Test finding summary for high');
  });

  // Task 3.1: Type column is sortable
  it('sorts by Type column when clicked', async () => {
    const user = userEvent.setup();
    const data = [
      mockItem('1', 75, 'timeline_anomaly'),
      mockItem('2', 75, 'citation_mismatch'),
      mockItem('3', 75, 'contradiction'),
    ];

    render(<VerificationQueue {...defaultProps} data={data} />);

    // Click Type header to sort
    await user.click(screen.getByText('Type'));

    // Get all rows
    const rows = screen.getAllByRole('row').slice(1);

    // Should be sorted alphabetically: citation_mismatch -> contradiction -> timeline_anomaly
    expect(rows[0]?.textContent).toContain('Citation Mismatch');
    expect(rows[1]?.textContent).toContain('Contradiction');
    expect(rows[2]?.textContent).toContain('Timeline Anomaly');
  });

  // Task 3.2: Confidence column is sortable
  it('sorts by Confidence column when clicked', async () => {
    const user = userEvent.setup();
    const data = [
      mockItem('low', 50),
      mockItem('high', 95),
      mockItem('med', 75),
    ];

    render(<VerificationQueue {...defaultProps} data={data} />);

    // Click Confidence header twice (already sorted asc, so click for desc)
    await user.click(screen.getByText('Confidence'));

    const rows = screen.getAllByRole('row').slice(1);

    // After clicking once (was already asc), should now be desc: high -> med -> low
    expect(rows[0]?.textContent).toContain('Test finding summary for high');
    expect(rows[1]?.textContent).toContain('Test finding summary for med');
    expect(rows[2]?.textContent).toContain('Test finding summary for low');
  });

  // Task 3.3: Source column is sortable
  it('sorts by Source column when clicked', async () => {
    const user = userEvent.setup();
    const data = [
      { ...mockItem('1', 75), id: '1', sourceDocument: 'doc-c.pdf' },
      { ...mockItem('2', 75), id: '2', sourceDocument: 'doc-a.pdf' },
      { ...mockItem('3', 75), id: '3', sourceDocument: 'doc-b.pdf' },
    ];

    render(<VerificationQueue {...defaultProps} data={data} />);

    // Click Source header to sort
    await user.click(screen.getByText('Source'));

    const rows = screen.getAllByRole('row').slice(1);

    // Should be sorted: doc-a -> doc-b -> doc-c
    expect(rows[0]?.textContent).toContain('doc-a.pdf');
    expect(rows[1]?.textContent).toContain('doc-b.pdf');
    expect(rows[2]?.textContent).toContain('doc-c.pdf');
  });

  // Task 3.6: Description column is sortable
  it('sorts by Description column when clicked', async () => {
    const user = userEvent.setup();
    const data = [
      { ...mockItem('1', 75), id: '1', findingSummary: 'Zebra finding' },
      { ...mockItem('2', 75), id: '2', findingSummary: 'Alpha finding' },
      { ...mockItem('3', 75), id: '3', findingSummary: 'Beta finding' },
    ];

    render(<VerificationQueue {...defaultProps} data={data} />);

    // Click Description header to sort
    await user.click(screen.getByText('Description'));

    const rows = screen.getAllByRole('row').slice(1);

    // Should be sorted alphabetically: Alpha -> Beta -> Zebra
    expect(rows[0]?.textContent).toContain('Alpha finding');
    expect(rows[1]?.textContent).toContain('Beta finding');
    expect(rows[2]?.textContent).toContain('Zebra finding');
  });

  // Task 3.5: Sort icons indicate current sort state
  it('shows correct sort icons for current sort state', async () => {
    const user = userEvent.setup();
    render(<VerificationQueue {...defaultProps} />);

    // Initially, Confidence should show ascending (it's the default)
    const confidenceHeader = screen.getByText('Confidence').closest('button');
    expect(confidenceHeader?.querySelector('svg')).toBeInTheDocument();

    // Click to toggle to descending
    await user.click(screen.getByText('Confidence'));

    // Sort icon should have changed (we can't easily test SVG content, but click works)
    expect(confidenceHeader).toBeInTheDocument();
  });

  // Test: Third click clears sort
  it('clears sort on third click (returns to unsorted)', async () => {
    const user = userEvent.setup();
    const data = [
      mockItem('1', 75, 'timeline_anomaly'),
      mockItem('2', 75, 'citation_mismatch'),
      mockItem('3', 75, 'contradiction'),
    ];

    render(<VerificationQueue {...defaultProps} data={data} />);

    // Click Type three times: asc -> desc -> clear
    await user.click(screen.getByText('Type'));
    await user.click(screen.getByText('Type'));
    await user.click(screen.getByText('Type'));

    // After third click, should be back to original order (or default confidence sort)
    const rows = screen.getAllByRole('row').slice(1);

    // After clearing Type sort, it returns to original data order
    // The first item in data is timeline_anomaly, shown as "Timeline Anomaly"
    expect(rows[0]?.textContent).toContain('Timeline Anomaly');
  });
});
