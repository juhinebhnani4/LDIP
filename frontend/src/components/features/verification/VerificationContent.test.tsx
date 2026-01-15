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
});
