/**
 * CitationsTab Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CitationsTab } from './CitationsTab';
import * as useCitationsModule from '@/hooks/useCitations';
import type { CitationStats, CitationSummaryItem, ActDiscoverySummary } from '@/types';

// Mock the hooks
vi.mock('@/hooks/useCitations');
vi.mock('@/hooks/useSplitView', () => ({
  useSplitView: () => ({
    isOpen: false,
    openSplitView: vi.fn(),
    closeSplitView: vi.fn(),
    setCitationIds: vi.fn(),
  }),
}));

const mockStats: CitationStats = {
  totalCitations: 23,
  uniqueActs: 6,
  verifiedCount: 18,
  pendingCount: 2,
  missingActsCount: 2,
};

const mockSummary: CitationSummaryItem[] = [
  { actName: 'Securities Act, 1992', citationCount: 12, verifiedCount: 10, pendingCount: 2 },
];

const mockActs: ActDiscoverySummary[] = [
  {
    actName: 'Securities Act, 1992',
    actNameNormalized: 'securities_act_1992',
    citationCount: 12,
    resolutionStatus: 'available',
    userAction: 'uploaded',
    actDocumentId: 'doc-123',
  },
];

describe('CitationsTab', () => {
  const mutateFn = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useCitationsModule.useCitationStats).mockReturnValue({
      stats: mockStats,
      isLoading: false,
      error: null,
      mutate: mutateFn,
    });

    vi.mocked(useCitationsModule.useCitationSummaryByAct).mockReturnValue({
      summary: mockSummary,
      isLoading: false,
      error: null,
      mutate: mutateFn,
    });

    vi.mocked(useCitationsModule.useActDiscoveryReport).mockReturnValue({
      acts: mockActs,
      missingCount: 0,
      availableCount: 1,
      skippedCount: 0,
      isLoading: false,
      error: null,
      mutate: mutateFn,
    });

    vi.mocked(useCitationsModule.useCitationsList).mockReturnValue({
      citations: [],
      meta: { total: 0, page: 1, perPage: 20, totalPages: 1 },
      isLoading: false,
      error: null,
      mutate: mutateFn,
    });

    vi.mocked(useCitationsModule.useActMutations).mockReturnValue({
      markUploaded: vi.fn(),
      markSkipped: vi.fn().mockResolvedValue(undefined),
      markUploadedAndVerify: vi.fn().mockResolvedValue(undefined),
      isLoading: false,
    });

    vi.mocked(useCitationsModule.getActNamesFromSummary).mockReturnValue([
      'Securities Act, 1992',
    ]);
  });

  it('renders CitationsContent with matterId', () => {
    render(<CitationsTab matterId="matter-123" />);

    expect(screen.getByText('Citations')).toBeInTheDocument();
  });

  it('passes matterId to CitationsContent', () => {
    render(<CitationsTab matterId="matter-123" />);

    expect(useCitationsModule.useCitationStats).toHaveBeenCalledWith('matter-123');
  });

  it('renders full height container', () => {
    const { container } = render(<CitationsTab matterId="matter-123" />);

    expect(container.firstChild).toHaveClass('h-full');
    expect(container.firstChild).toHaveClass('p-4');
  });

  it('passes onViewInDocument callback', () => {
    const onViewInDocument = vi.fn();

    render(
      <CitationsTab
        matterId="matter-123"
        onViewInDocument={onViewInDocument}
      />
    );

    // The callback is passed through to CitationsContent
    // We verify the component renders without error
    expect(screen.getByText('Citations')).toBeInTheDocument();
  });
});
