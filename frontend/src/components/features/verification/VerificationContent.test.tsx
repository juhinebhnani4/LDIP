/**
 * VerificationContent Component Tests
 *
 * Story 10D.1: Verification Tab Queue (DataTable)
 * Task 1.7: Integration tests for VerificationContent
 */

import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VerificationContent } from './VerificationContent';
import { useVerificationQueue } from '@/hooks/useVerificationQueue';
import { useVerificationStats } from '@/hooks/useVerificationStats';
import { useVerificationActions } from '@/hooks/useVerificationActions';
import { useVerificationStore } from '@/stores/verificationStore';
import { VerificationDecision, VerificationRequirement } from '@/types';
import type { VerificationQueueItem, VerificationStats, VerificationFilters } from '@/types';

// Mock the hooks
vi.mock('@/hooks/useVerificationQueue');
vi.mock('@/hooks/useVerificationStats');
vi.mock('@/hooks/useVerificationActions');
vi.mock('@/stores/verificationStore');

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockQueueItem = (
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

const mockStats: VerificationStats = {
  totalVerifications: 100,
  pendingCount: 40,
  approvedCount: 50,
  rejectedCount: 5,
  flaggedCount: 5,
  requiredPending: 10,
  suggestedPending: 20,
  optionalPending: 10,
  exportBlocked: false,
  blockingCount: 0,
};

const mockFilters: VerificationFilters = {
  findingType: null,
  confidenceTier: null,
  status: null,
  view: 'queue',
};

describe('VerificationContent', () => {
  const mockSetFilters = vi.fn();
  const mockResetFilters = vi.fn();
  const mockRefreshQueue = vi.fn();
  const mockRefreshStats = vi.fn();
  const mockApprove = vi.fn();
  const mockReject = vi.fn();
  const mockFlag = vi.fn();
  const mockBulkApprove = vi.fn();
  const mockBulkReject = vi.fn();
  const mockBulkFlag = vi.fn();
  const mockToggleSelected = vi.fn();
  const mockSelectAll = vi.fn();
  const mockClearSelection = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    (useVerificationQueue as Mock).mockReturnValue({
      filteredQueue: [mockQueueItem('1'), mockQueueItem('2'), mockQueueItem('3')],
      filters: mockFilters,
      isLoading: false,
      error: null,
      setFilters: mockSetFilters,
      resetFilters: mockResetFilters,
      findingTypes: ['citation_mismatch', 'contradiction'],
      refresh: mockRefreshQueue,
    });

    (useVerificationStats as Mock).mockReturnValue({
      stats: mockStats,
      isLoading: false,
      refresh: mockRefreshStats,
    });

    (useVerificationActions as Mock).mockReturnValue({
      approve: mockApprove,
      reject: mockReject,
      flag: mockFlag,
      bulkApprove: mockBulkApprove,
      bulkReject: mockBulkReject,
      bulkFlag: mockBulkFlag,
      isActioning: false,
      currentAction: null,
      processingIds: [],
    });

    (useVerificationStore as unknown as Mock).mockImplementation((selector: (state: Record<string, unknown>) => unknown) => {
      const state = {
        selectedIds: [],
        toggleSelected: mockToggleSelected,
        selectAll: mockSelectAll,
        clearSelection: mockClearSelection,
      };
      return selector(state);
    });
  });

  it('renders verification content with stats header', () => {
    render(<VerificationContent matterId="matter-123" />);

    // Stats header should be present
    expect(screen.getByText('Verification Center')).toBeInTheDocument();
  });

  it('renders queue items', () => {
    render(<VerificationContent matterId="matter-123" />);

    // Queue items should be rendered
    expect(screen.getByText('Test finding summary for 1')).toBeInTheDocument();
    expect(screen.getByText('Test finding summary for 2')).toBeInTheDocument();
    expect(screen.getByText('Test finding summary for 3')).toBeInTheDocument();
  });

  it('renders loading skeleton when queue is loading and empty', () => {
    (useVerificationQueue as Mock).mockReturnValue({
      filteredQueue: [],
      filters: mockFilters,
      isLoading: true,
      error: null,
      setFilters: mockSetFilters,
      resetFilters: mockResetFilters,
      findingTypes: [],
      refresh: mockRefreshQueue,
    });

    render(<VerificationContent matterId="matter-123" />);

    // Should show loading state, not content
    expect(screen.queryByText('Verification Center')).not.toBeInTheDocument();
  });

  it('renders error state when queue has error and no data', () => {
    (useVerificationQueue as Mock).mockReturnValue({
      filteredQueue: [],
      filters: mockFilters,
      isLoading: false,
      error: 'Failed to load queue',
      setFilters: mockSetFilters,
      resetFilters: mockResetFilters,
      findingTypes: [],
      refresh: mockRefreshQueue,
    });

    render(<VerificationContent matterId="matter-123" />);

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Failed to load queue')).toBeInTheDocument();
  });

  it('shows inline error when queue has data but also error', () => {
    (useVerificationQueue as Mock).mockReturnValue({
      filteredQueue: [mockQueueItem('1')],
      filters: mockFilters,
      isLoading: false,
      error: 'Refresh failed',
      setFilters: mockSetFilters,
      resetFilters: mockResetFilters,
      findingTypes: [],
      refresh: mockRefreshQueue,
    });

    render(<VerificationContent matterId="matter-123" />);

    // Should show content AND inline error
    expect(screen.getByText('Verification Center')).toBeInTheDocument();
    expect(screen.getByText('Refresh failed')).toBeInTheDocument();
  });

  it('calls approve when approve button is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    const approveButtons = screen.getAllByLabelText('Approve');
    await user.click(approveButtons[0]!);

    expect(mockApprove).toHaveBeenCalledWith('1');
  });

  it('shows bulk actions toolbar when items are selected', () => {
    (useVerificationStore as unknown as Mock).mockImplementation((selector: (state: Record<string, unknown>) => unknown) => {
      const state = {
        selectedIds: ['1', '2'],
        toggleSelected: mockToggleSelected,
        selectAll: mockSelectAll,
        clearSelection: mockClearSelection,
      };
      return selector(state);
    });

    render(<VerificationContent matterId="matter-123" />);

    expect(screen.getByText('2 items selected')).toBeInTheDocument();
    expect(screen.getByText('Approve Selected')).toBeInTheDocument();
    expect(screen.getByText('Reject Selected')).toBeInTheDocument();
    expect(screen.getByText('Flag Selected')).toBeInTheDocument();
  });

  it('calls bulkApprove when bulk approve is clicked', async () => {
    const user = userEvent.setup();
    (useVerificationStore as unknown as Mock).mockImplementation((selector: (state: Record<string, unknown>) => unknown) => {
      const state = {
        selectedIds: ['1', '2'],
        toggleSelected: mockToggleSelected,
        selectAll: mockSelectAll,
        clearSelection: mockClearSelection,
      };
      return selector(state);
    });

    render(<VerificationContent matterId="matter-123" />);

    const approveSelectedButton = screen.getByText('Approve Selected');
    await user.click(approveSelectedButton);

    expect(mockBulkApprove).toHaveBeenCalledWith(['1', '2']);
  });

  it('passes matterId to hooks', () => {
    render(<VerificationContent matterId="test-matter-id" />);

    expect(useVerificationQueue).toHaveBeenCalledWith({ matterId: 'test-matter-id' });
    expect(useVerificationStats).toHaveBeenCalledWith({ matterId: 'test-matter-id' });
    expect(useVerificationActions).toHaveBeenCalledWith(
      expect.objectContaining({ matterId: 'test-matter-id' })
    );
  });

  it('toggles row selection when checkbox is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    const checkboxes = screen.getAllByRole('checkbox');
    // First checkbox is header, second is first row
    await user.click(checkboxes[1]!);

    expect(mockToggleSelected).toHaveBeenCalledWith('1');
  });

  it('selects all when header checkbox is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]!); // Header checkbox

    expect(mockSelectAll).toHaveBeenCalledWith(['1', '2', '3']);
  });

  it('renders empty state when no queue items', () => {
    (useVerificationQueue as Mock).mockReturnValue({
      filteredQueue: [],
      filters: mockFilters,
      isLoading: false,
      error: null,
      setFilters: mockSetFilters,
      resetFilters: mockResetFilters,
      findingTypes: [],
      refresh: mockRefreshQueue,
    });

    render(<VerificationContent matterId="matter-123" />);

    expect(screen.getByText('No verifications pending.')).toBeInTheDocument();
  });

  // Issue 1: Test for notes dialog reset state
  it('resets notes dialog state when canceled', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    // Click reject to open notes dialog
    const rejectButtons = screen.getAllByLabelText('Reject');
    await user.click(rejectButtons[0]!);

    // Dialog should open
    expect(screen.getByText('Reject Verification')).toBeInTheDocument();

    // Type some notes
    const notesInput = screen.getByLabelText('Notes (required)');
    await user.type(notesInput, 'Test notes');
    expect(notesInput).toHaveValue('Test notes');

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    await user.click(cancelButton);

    // Open dialog again
    await user.click(rejectButtons[0]!);

    // Notes should be reset
    const newNotesInput = screen.getByLabelText('Notes (required)');
    expect(newNotesInput).toHaveValue('');
  });

  // Issue 2: Test for reject dialog submission flow
  it('completes full reject dialog submission flow', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    // Click reject to open notes dialog
    const rejectButtons = screen.getAllByLabelText('Reject');
    await user.click(rejectButtons[0]!);

    // Dialog should open with reject title
    expect(screen.getByText('Reject Verification')).toBeInTheDocument();

    // Enter notes
    const notesInput = screen.getByLabelText('Notes (required)');
    await user.type(notesInput, 'Rejection reason: incorrect citation');

    // Submit
    const submitButton = screen.getByRole('button', { name: 'Reject' });
    await user.click(submitButton);

    // Verify reject was called with notes
    expect(mockReject).toHaveBeenCalledWith('1', 'Rejection reason: incorrect citation');
  });

  // Issue 2: Test for flag dialog submission flow
  it('completes full flag dialog submission flow', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    // Click flag to open notes dialog
    const flagButtons = screen.getAllByLabelText('Flag');
    await user.click(flagButtons[0]!);

    // Dialog should open with flag title
    expect(screen.getByText('Flag for Review')).toBeInTheDocument();

    // Enter notes
    const notesInput = screen.getByLabelText('Notes (required)');
    await user.type(notesInput, 'Needs senior review');

    // Submit
    const submitButton = screen.getByRole('button', { name: 'Flag' });
    await user.click(submitButton);

    // Verify flag was called with notes
    expect(mockFlag).toHaveBeenCalledWith('1', 'Needs senior review');
  });

  // Issue 3: Test for inline error div structure
  it('renders inline error with correct styling classes when data exists but refresh failed', () => {
    (useVerificationQueue as Mock).mockReturnValue({
      filteredQueue: [mockQueueItem('1')],
      filters: mockFilters,
      isLoading: false,
      error: 'Network error during refresh',
      setFilters: mockSetFilters,
      resetFilters: mockResetFilters,
      findingTypes: [],
      refresh: mockRefreshQueue,
    });

    render(<VerificationContent matterId="matter-123" />);

    // Find the inline error element
    const errorDiv = screen.getByText('Network error during refresh');

    // Verify it has the correct styling classes
    expect(errorDiv).toHaveClass('p-4');
    expect(errorDiv).toHaveClass('bg-destructive/10');
    expect(errorDiv).toHaveClass('text-destructive');
    expect(errorDiv).toHaveClass('rounded-lg');

    // Verify content is still displayed alongside the error
    expect(screen.getByText('Verification Center')).toBeInTheDocument();
    expect(screen.getByText('Test finding summary for 1')).toBeInTheDocument();
  });

  // Issue 4: Test that onStartSession is passed to VerificationStats
  it('renders Start Review Session button when onStartSession is provided', () => {
    const mockOnStartSession = vi.fn();
    render(<VerificationContent matterId="matter-123" onStartSession={mockOnStartSession} />);

    // Button should be rendered when onStartSession is provided
    expect(screen.getByRole('button', { name: 'Start Review Session' })).toBeInTheDocument();
  });

  it('does not render Start Review Session button when onStartSession is not provided', () => {
    render(<VerificationContent matterId="matter-123" />);

    // Button should NOT be rendered when onStartSession is not provided
    expect(screen.queryByRole('button', { name: 'Start Review Session' })).not.toBeInTheDocument();
  });
});

// Story 10D.2 Task 5.5: Tier badge click filter mapping tests
describe('VerificationContent Tier Badge Click Filter (Task 5.5)', () => {
  const mockSetFilters = vi.fn();
  const mockResetFilters = vi.fn();
  const mockRefreshQueue = vi.fn();
  const mockRefreshStats = vi.fn();
  const mockApprove = vi.fn();
  const mockReject = vi.fn();
  const mockFlag = vi.fn();
  const mockBulkApprove = vi.fn();
  const mockBulkReject = vi.fn();
  const mockBulkFlag = vi.fn();
  const mockToggleSelected = vi.fn();
  const mockSelectAll = vi.fn();
  const mockClearSelection = vi.fn();

  const mockStatsWithTiers: VerificationStats = {
    totalVerifications: 100,
    pendingCount: 40,
    approvedCount: 50,
    rejectedCount: 5,
    flaggedCount: 5,
    requiredPending: 10,
    suggestedPending: 20,
    optionalPending: 10,
    exportBlocked: true,
    blockingCount: 10,
  };

  beforeEach(() => {
    vi.clearAllMocks();

    (useVerificationQueue as Mock).mockReturnValue({
      filteredQueue: [],
      filters: { findingType: null, confidenceTier: null, status: null, view: 'queue' },
      isLoading: false,
      error: null,
      setFilters: mockSetFilters,
      resetFilters: mockResetFilters,
      findingTypes: [],
      refresh: mockRefreshQueue,
    });

    (useVerificationStats as Mock).mockReturnValue({
      stats: mockStatsWithTiers,
      isLoading: false,
      refresh: mockRefreshStats,
    });

    (useVerificationActions as Mock).mockReturnValue({
      approve: mockApprove,
      reject: mockReject,
      flag: mockFlag,
      bulkApprove: mockBulkApprove,
      bulkReject: mockBulkReject,
      bulkFlag: mockBulkFlag,
      isActioning: false,
      currentAction: null,
      processingIds: [],
    });

    (useVerificationStore as unknown as Mock).mockImplementation((selector: (state: Record<string, unknown>) => unknown) => {
      const state = {
        selectedIds: [],
        toggleSelected: mockToggleSelected,
        selectAll: mockSelectAll,
        clearSelection: mockClearSelection,
      };
      return selector(state);
    });
  });

  it('sets confidenceTier to "low" when Required badge is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    // Click on "Required: 10 pending" badge
    await user.click(screen.getByText('Required: 10 pending'));

    // Should set filter to low confidence (< 70% = required tier per ADR-004)
    expect(mockSetFilters).toHaveBeenCalledWith({ confidenceTier: 'low' });
  });

  it('sets confidenceTier to "medium" when Suggested badge is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    // Click on "Suggested: 20 pending" badge
    await user.click(screen.getByText('Suggested: 20 pending'));

    // Should set filter to medium confidence (70-90% = suggested tier per ADR-004)
    expect(mockSetFilters).toHaveBeenCalledWith({ confidenceTier: 'medium' });
  });

  it('sets confidenceTier to "high" when Optional badge is clicked', async () => {
    const user = userEvent.setup();
    render(<VerificationContent matterId="matter-123" />);

    // Click on "Optional: 10 pending" badge
    await user.click(screen.getByText('Optional: 10 pending'));

    // Should set filter to high confidence (> 90% = optional tier per ADR-004)
    expect(mockSetFilters).toHaveBeenCalledWith({ confidenceTier: 'high' });
  });
});
