/**
 * CitationsContent Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 * @see Story 10C.4 - Split-View Verification Integration
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CitationsContent } from './CitationsContent';
import * as useCitationsModule from '@/hooks/useCitations';
import type { CitationListItem, CitationStats, CitationSummaryItem, ActDiscoverySummary } from '@/types';

// Mock the hooks
vi.mock('@/hooks/useCitations');

// Create configurable mock for useSplitView
const mockOpenSplitView = vi.fn();
const mockCloseSplitView = vi.fn();
const mockToggleFullScreen = vi.fn();
const mockSetCitationIds = vi.fn();

const defaultSplitViewMock = {
  isOpen: false,
  isFullScreen: false,
  splitViewData: null as unknown,
  isLoading: false,
  error: null as string | null,
  navigationInfo: { currentIndex: 0, totalCount: 0, canPrev: false, canNext: false },
  openSplitView: mockOpenSplitView,
  closeSplitView: mockCloseSplitView,
  toggleFullScreen: mockToggleFullScreen,
  navigateToPrev: vi.fn(),
  navigateToNext: vi.fn(),
  setCitationIds: mockSetCitationIds,
};

let splitViewMockOverrides: Partial<typeof defaultSplitViewMock> = {};

vi.mock('@/hooks/useSplitView', () => ({
  useSplitView: () => ({ ...defaultSplitViewMock, ...splitViewMockOverrides }),
}));

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockCitations: CitationListItem[] = [
  {
    id: 'cit-1',
    actName: 'Securities Act, 1992',
    sectionNumber: '3',
    subsection: '3',
    clause: null,
    rawCitationText: 'Section 3(3) of the Securities Act',
    sourcePage: 45,
    verificationStatus: 'verified',
    confidence: 95.0,
    documentId: 'doc-1',
    documentName: 'Petition.pdf',
  },
  {
    id: 'cit-2',
    actName: 'Negotiable Instruments Act, 1881',
    sectionNumber: '138',
    subsection: null,
    clause: null,
    rawCitationText: 'Section 138 of the NI Act',
    sourcePage: 12,
    verificationStatus: 'mismatch',
    confidence: 78.0,
    documentId: 'doc-1',
    documentName: 'Petition.pdf',
  },
];

const mockStats: CitationStats = {
  totalCitations: 23,
  uniqueActs: 6,
  verifiedCount: 18,
  pendingCount: 2,
  missingActsCount: 2,
};

const mockSummary: CitationSummaryItem[] = [
  { actName: 'Securities Act, 1992', citationCount: 12, verifiedCount: 10, pendingCount: 2 },
  { actName: 'Negotiable Instruments Act, 1881', citationCount: 8, verifiedCount: 6, pendingCount: 0 },
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
  {
    actName: 'Negotiable Instruments Act, 1881',
    actNameNormalized: 'negotiable_instruments_act_1881',
    citationCount: 8,
    resolutionStatus: 'missing',
    userAction: 'pending',
    actDocumentId: null,
  },
];

describe('CitationsContent', () => {
  const mutateFn = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    splitViewMockOverrides = {}; // Reset split view mock to defaults

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
      missingCount: 1,
      availableCount: 1,
      skippedCount: 0,
      isLoading: false,
      error: null,
      mutate: mutateFn,
    });

    vi.mocked(useCitationsModule.useCitationsList).mockReturnValue({
      citations: mockCitations,
      meta: { total: 2, page: 1, perPage: 20, totalPages: 1 },
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
      'Negotiable Instruments Act, 1881',
      'Securities Act, 1992',
    ]);
  });

  it('renders the header with statistics', () => {
    render(<CitationsContent matterId="matter-123" />);

    expect(screen.getByText('Citations')).toBeInTheDocument();
    expect(screen.getByText('23 found')).toBeInTheDocument();
  });

  it('renders attention banner when there are issues', () => {
    render(<CitationsContent matterId="matter-123" />);

    // There's 1 missing act and 3 issues (23 - 18 - 2)
    expect(screen.getByText(/CITATIONS? NEED ATTENTION/)).toBeInTheDocument();
  });

  it('renders citations list by default', () => {
    render(<CitationsContent matterId="matter-123" />);

    expect(screen.getByText('Securities Act, 1992')).toBeInTheDocument();
    expect(screen.getByText('Section 3(3) of the Securities Act')).toBeInTheDocument();
  });

  it('renders MissingActsCard in sidebar when there are missing acts', () => {
    render(<CitationsContent matterId="matter-123" />);

    // Check for Missing Acts card title
    expect(screen.getByText('Missing Acts')).toBeInTheDocument();
    // The act name appears in both the list and the missing acts card
    // Use getAllByText and check length is at least 1
    const actElements = screen.getAllByText('Negotiable Instruments Act, 1881');
    expect(actElements.length).toBeGreaterThanOrEqual(1);
  });

  it('switches to By Act view when toggle clicked', async () => {
    const user = userEvent.setup();
    render(<CitationsContent matterId="matter-123" />);

    // Click the By Act view toggle (radio button)
    await user.click(screen.getByRole('radio', { name: /by act view/i }));

    // The useCitationsList hook should still be called
    expect(useCitationsModule.useCitationsList).toHaveBeenCalled();
  });

  it('switches to By Document view when toggle clicked', async () => {
    const user = userEvent.setup();
    render(<CitationsContent matterId="matter-123" />);

    // Click the By Document view toggle (radio button)
    await user.click(screen.getByRole('radio', { name: /by document view/i }));

    // The useCitationsList hook should still be called
    expect(useCitationsModule.useCitationsList).toHaveBeenCalled();
  });

  it('shows loading skeleton when data is loading', () => {
    vi.mocked(useCitationsModule.useCitationStats).mockReturnValue({
      stats: null,
      isLoading: true,
      error: null,
      mutate: mutateFn,
    });

    render(<CitationsContent matterId="matter-123" />);

    // Should not show the header stats
    expect(screen.queryByText('23 found')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <CitationsContent matterId="matter-123" className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('passes matterId to hooks', () => {
    render(<CitationsContent matterId="matter-123" />);

    expect(useCitationsModule.useCitationStats).toHaveBeenCalledWith('matter-123');
    expect(useCitationsModule.useCitationSummaryByAct).toHaveBeenCalledWith('matter-123');
    expect(useCitationsModule.useActDiscoveryReport).toHaveBeenCalledWith('matter-123');
    expect(useCitationsModule.useCitationsList).toHaveBeenCalledWith(
      'matter-123',
      expect.any(Object)
    );
  });

  it('shows Review Issues button in attention banner', () => {
    render(<CitationsContent matterId="matter-123" />);

    expect(screen.getByRole('button', { name: /review issues/i })).toBeInTheDocument();
  });

  it('shows Upload Missing Acts button in attention banner', () => {
    render(<CitationsContent matterId="matter-123" />);

    expect(screen.getByRole('button', { name: /upload missing acts/i })).toBeInTheDocument();
  });

  it('activates showOnlyIssues filter when Review Issues clicked', async () => {
    const user = userEvent.setup();
    render(<CitationsContent matterId="matter-123" />);

    await user.click(screen.getByRole('button', { name: /review issues/i }));

    // Filter changes are debounced by 300ms, so wait for the debounce to apply
    await waitFor(() => {
      // Check that useCitationsList was called with the filter after debounce
      expect(useCitationsModule.useCitationsList).toHaveBeenCalledWith(
        'matter-123',
        expect.objectContaining({
          filters: expect.objectContaining({
            showOnlyIssues: true,
          }),
        })
      );
    }, { timeout: 500 });
  });

  it('hides attention banner when no issues or missing acts', () => {
    vi.mocked(useCitationsModule.useCitationStats).mockReturnValue({
      stats: {
        ...mockStats,
        verifiedCount: 21, // 23 - 21 - 2 = 0 issues
        pendingCount: 2,
        missingActsCount: 0,
      },
      isLoading: false,
      error: null,
      mutate: mutateFn,
    });

    vi.mocked(useCitationsModule.useActDiscoveryReport).mockReturnValue({
      acts: mockActs.filter((act) => act.resolutionStatus === 'available'),
      missingCount: 0,
      availableCount: 1,
      skippedCount: 0,
      isLoading: false,
      error: null,
      mutate: mutateFn,
    });

    render(<CitationsContent matterId="matter-123" />);

    expect(screen.queryByText(/CITATIONS? NEED ATTENTION/)).not.toBeInTheDocument();
  });

  // Split-view integration tests (Story 10C.4)
  describe('split-view integration', () => {
    const mockSplitViewData = {
      citation: {
        id: 'cit-1',
        actName: 'Securities Act, 1992',
        sectionNumber: '3',
        subsection: '3',
        clause: null,
        verificationStatus: 'verified' as const,
        rawCitationText: 'Section 3(3) of the Securities Act',
      },
      sourceDocument: {
        documentId: 'doc-1',
        documentUrl: '/api/documents/doc-1/file',
        pageNumber: 45,
        boundingBoxes: [{ x: 100, y: 200, width: 300, height: 50 }],
      },
      targetDocument: {
        documentId: 'act-1',
        documentUrl: '/api/documents/act-1/file',
        pageNumber: 12,
        boundingBoxes: [{ x: 50, y: 150, width: 400, height: 60 }],
      },
      verification: {
        status: 'verified' as const,
        similarityScore: 95.5,
      },
    };

    it('renders split-view panel when isOpen is true and has data', () => {
      splitViewMockOverrides = {
        isOpen: true,
        isFullScreen: false,
        splitViewData: mockSplitViewData,
      };

      render(<CitationsContent matterId="matter-123" />);

      // Should show split-view panel with source document header
      expect(screen.getByText('Source Document')).toBeInTheDocument();
    });

    it('shows loading state in split-view when loading', () => {
      // Note: SplitViewCitationPanel handles loading state internally with isLoading prop
      // The panel needs some data structure even when loading
      splitViewMockOverrides = {
        isOpen: true,
        isFullScreen: false,
        splitViewData: mockSplitViewData, // Provide data, panel shows loading via isLoading prop
        isLoading: true,
      };

      render(<CitationsContent matterId="matter-123" />);

      // When isLoading is true, the SplitViewCitationPanel shows loading state
      expect(screen.getByText('Loading citation view...')).toBeInTheDocument();
    });

    it('calls setCitationIds when citations are loaded', () => {
      render(<CitationsContent matterId="matter-123" />);

      expect(mockSetCitationIds).toHaveBeenCalledWith(['cit-1', 'cit-2']);
    });

    it('calls openSplitView when view button is clicked in list', async () => {
      const user = userEvent.setup();
      render(<CitationsContent matterId="matter-123" />);

      // Click the first View button
      const viewButtons = screen.getAllByTitle('View in split view');
      expect(viewButtons.length).toBeGreaterThan(0);
      await user.click(viewButtons[0]!);

      expect(mockOpenSplitView).toHaveBeenCalled();
    });
  });
});
