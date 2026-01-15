import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SummaryContent } from './SummaryContent';
import { useMatterSummary } from '@/hooks/useMatterSummary';
import type { MatterSummary } from '@/types/summary';

// Mock the useMatterSummary hook
vi.mock('@/hooks/useMatterSummary', () => ({
  useMatterSummary: vi.fn(),
}));

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

const createMockSummary = (overrides: Partial<MatterSummary> = {}): MatterSummary => ({
  matterId: 'test-matter-id',
  attentionItems: [
    { type: 'contradiction', count: 3, label: 'contradictions detected', targetTab: 'verification' },
  ],
  parties: [
    {
      entityId: 'p1',
      entityName: 'John Doe',
      role: 'petitioner',
      sourceDocument: 'Petition.pdf',
      sourcePage: 1,
      isVerified: false,
    },
    {
      entityId: 'r1',
      entityName: 'State Authority',
      role: 'respondent',
      sourceDocument: 'Petition.pdf',
      sourcePage: 2,
      isVerified: true,
    },
  ],
  subjectMatter: {
    description: 'Test subject matter description.',
    sources: [{ documentName: 'Petition.pdf', pageRange: '1-3' }],
    isVerified: false,
  },
  currentStatus: {
    lastOrderDate: '2024-01-15T00:00:00.000Z',
    description: 'Matter adjourned.',
    sourceDocument: 'Order.pdf',
    sourcePage: 1,
    isVerified: false,
  },
  keyIssues: [
    { id: '1', number: 1, title: 'First issue', verificationStatus: 'pending' },
  ],
  stats: {
    totalPages: 100,
    entitiesFound: 20,
    eventsExtracted: 15,
    citationsFound: 30,
    verificationPercent: 75,
  },
  generatedAt: new Date().toISOString(),
  ...overrides,
});

describe('SummaryContent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('renders loading skeleton when loading', () => {
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: undefined,
        isLoading: true,
        isError: false,
      });

      const { container } = render(<SummaryContent matterId="test-matter-id" />);

      // Should have skeleton elements with animate-pulse
      const skeletons = container.querySelectorAll('.animate-pulse, [data-slot="skeleton"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('error state', () => {
    it('renders error alert when error occurs', () => {
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: undefined,
        isLoading: false,
        isError: true,
      });

      render(<SummaryContent matterId="test-matter-id" />);

      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load summary data/)).toBeInTheDocument();
    });

    it('renders error when summary is null', () => {
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: null,
        isLoading: false,
        isError: false,
      });

      render(<SummaryContent matterId="test-matter-id" />);

      expect(screen.getByText('Error')).toBeInTheDocument();
    });
  });

  describe('success state', () => {
    it('renders all summary sections', async () => {
      const mockSummary = createMockSummary();
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: mockSummary,
        isLoading: false,
        isError: false,
      });

      render(<SummaryContent matterId="test-matter-id" />);

      // Check for all major sections
      await waitFor(() => {
        expect(screen.getByText('3 items need attention')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Parties' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Subject Matter' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Current Status' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Key Issues' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Matter Statistics' })).toBeInTheDocument();
      });
    });

    it('hides attention banner when no items', async () => {
      const mockSummary = createMockSummary({ attentionItems: [] });
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: mockSummary,
        isLoading: false,
        isError: false,
      });

      render(<SummaryContent matterId="test-matter-id" />);

      await waitFor(() => {
        expect(screen.queryByText(/items need attention/)).not.toBeInTheDocument();
      });
    });

    it('displays parties information', async () => {
      const mockSummary = createMockSummary();
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: mockSummary,
        isLoading: false,
        isError: false,
      });

      render(<SummaryContent matterId="test-matter-id" />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('State Authority')).toBeInTheDocument();
      });
    });

    it('displays statistics', async () => {
      const mockSummary = createMockSummary();
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: mockSummary,
        isLoading: false,
        isError: false,
      });

      render(<SummaryContent matterId="test-matter-id" />);

      await waitFor(() => {
        expect(screen.getByText('100')).toBeInTheDocument();
        expect(screen.getByText('Total Pages')).toBeInTheDocument();
        expect(screen.getByText('75%')).toBeInTheDocument();
      });
    });
  });

  describe('hook usage', () => {
    it('calls useMatterSummary with correct matterId', () => {
      (useMatterSummary as ReturnType<typeof vi.fn>).mockReturnValue({
        summary: undefined,
        isLoading: true,
        isError: false,
      });

      render(<SummaryContent matterId="my-matter-123" />);

      expect(useMatterSummary).toHaveBeenCalledWith('my-matter-123');
    });
  });
});
