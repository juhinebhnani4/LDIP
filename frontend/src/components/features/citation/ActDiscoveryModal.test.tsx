import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActDiscoveryModal } from './ActDiscoveryModal';
import * as citationsApi from '@/lib/api/citations';
import type { ActDiscoveryResponse, ActDiscoverySummary } from '@/types';

// Mock the citations API
vi.mock('@/lib/api/citations', () => ({
  getActDiscoveryReport: vi.fn(),
  markActUploaded: vi.fn(),
  markActSkipped: vi.fn(),
}));

// Mock the upload store
vi.mock('@/stores/uploadStore', () => ({
  useUploadStore: vi.fn((selector) => {
    const state = {
      uploadQueue: [],
      isUploading: false,
      addFiles: vi.fn(),
      clearAll: vi.fn(),
    };
    return selector(state);
  }),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));


describe('ActDiscoveryModal', () => {
  const mockMatterId = 'test-matter-123';
  const mockOnOpenChange = vi.fn();
  const mockOnContinue = vi.fn();

  const mockAvailableAct: ActDiscoverySummary = {
    actName: 'Securities Act, 1992',
    actNameNormalized: 'securities_act_1992',
    citationCount: 5,
    resolutionStatus: 'available',
    userAction: 'uploaded',
    actDocumentId: 'doc-123',
  };

  const mockAutoFetchedAct: ActDiscoverySummary = {
    actName: 'Indian Penal Code, 1860',
    actNameNormalized: 'indian_penal_code_1860',
    citationCount: 8,
    resolutionStatus: 'auto_fetched',
    userAction: 'pending',
    actDocumentId: 'doc-456',
  };

  const mockMissingAct: ActDiscoverySummary = {
    actName: 'Negotiable Instruments Act, 1881',
    actNameNormalized: 'negotiable_instruments_act_1881',
    citationCount: 12,
    resolutionStatus: 'missing',
    userAction: 'pending',
    actDocumentId: null,
  };

  const mockNotOnIndiacodeAct: ActDiscoverySummary = {
    actName: 'Maharashtra Rent Control Act, 1999',
    actNameNormalized: 'maharashtra_rent_control_act_1999',
    citationCount: 4,
    resolutionStatus: 'not_on_indiacode',
    userAction: 'pending',
    actDocumentId: null,
  };

  const mockSkippedAct: ActDiscoverySummary = {
    actName: 'Companies Act, 2013',
    actNameNormalized: 'companies_act_2013',
    citationCount: 3,
    resolutionStatus: 'skipped',
    userAction: 'skipped',
    actDocumentId: null,
  };

  const mockReport: ActDiscoveryResponse = {
    data: [mockAvailableAct, mockAutoFetchedAct, mockMissingAct, mockNotOnIndiacodeAct, mockSkippedAct],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(citationsApi.getActDiscoveryReport).mockResolvedValue(mockReport);
    vi.mocked(citationsApi.markActUploaded).mockResolvedValue({
      success: true,
      actName: mockMissingAct.actName,
      resolutionStatus: 'available',
    });
    vi.mocked(citationsApi.markActSkipped).mockResolvedValue({
      success: true,
      actName: mockMissingAct.actName,
      resolutionStatus: 'skipped',
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders modal with title when open', async () => {
      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Act References Detected')).toBeInTheDocument();
      });
    });

    it('shows loading state while fetching', async () => {
      // Delay the API response so we can catch loading state
      let resolvePromise: (value: ActDiscoveryResponse) => void;
      vi.mocked(citationsApi.getActDiscoveryReport).mockImplementation(
        () => new Promise((resolve) => { resolvePromise = resolve; })
      );

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      // Loading state is indicated by skeleton presence - check for skeleton data-slot
      // or the modal being open and not showing act content yet
      expect(screen.getByRole('dialog')).toBeInTheDocument();

      // Resolve and wait for content
      resolvePromise!(mockReport);
      await waitFor(() => {
        expect(screen.getByText('Securities Act, 1992')).toBeInTheDocument();
      });
    });

    it('shows act list when loaded', async () => {
      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Securities Act, 1992')).toBeInTheDocument();
        expect(screen.getByText('Indian Penal Code, 1860')).toBeInTheDocument();
        expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();
        expect(screen.getByText('Maharashtra Rent Control Act, 1999')).toBeInTheDocument();
        expect(screen.getByText('Companies Act, 2013')).toBeInTheDocument();
      });
    });

    it('shows correct section headers', async () => {
      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      // Wait for acts to load
      await waitFor(() => {
        expect(screen.getByText('Securities Act, 1992')).toBeInTheDocument();
      });

      // Now check for section headers - the headers contain count in parens
      // auto_fetched merges into "Detected in Your Files" (available + auto_fetched = 2)
      expect(screen.getByText(/Detected in Your Files \(2\)/)).toBeInTheDocument();
      expect(screen.getByText(/Missing Acts \(1\)/)).toBeInTheDocument();
      expect(screen.getByText(/Not Available on India Code \(1\)/)).toBeInTheDocument();
      expect(screen.getByText(/Skipped \(1\)/)).toBeInTheDocument();
    });

    it('shows auto_fetched acts in Detected in Your Files section', async () => {
      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Indian Penal Code, 1860')).toBeInTheDocument();
      });

      // The auto_fetched act should be inside the "Available Acts" list
      const availableList = screen.getByRole('list', { name: /available acts/i });
      expect(availableList).toContainElement(screen.getByText('Indian Penal Code, 1860'));
    });

    it('shows graceful degradation info when missing acts exist', async () => {
      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(
          screen.getByText(/Unverified - Act not provided/i)
        ).toBeInTheDocument();
      });
    });

    it('shows not_on_indiacode acts even when no other statuses exist', async () => {
      // Scenario: modal shows only not_on_indiacode acts (the stuck-UI scenario)
      vi.mocked(citationsApi.getActDiscoveryReport).mockResolvedValue({
        data: [mockNotOnIndiacodeAct],
      });

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Maharashtra Rent Control Act, 1999')).toBeInTheDocument();
        expect(screen.getByText(/Not Available on India Code \(1\)/)).toBeInTheDocument();
      });

      // Graceful degradation banner should show since not_on_indiacode needs attention
      expect(screen.getByText(/Unverified - Act not provided/i)).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('shows error state when fetch fails', async () => {
      vi.mocked(citationsApi.getActDiscoveryReport).mockRejectedValue(
        new Error('Network error')
      );

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Failed to load Act Discovery Report/i)).toBeInTheDocument();
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });
    });

    it('shows retry button on error', async () => {
      vi.mocked(citationsApi.getActDiscoveryReport).mockRejectedValue(
        new Error('Network error')
      );

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no acts are detected', async () => {
      vi.mocked(citationsApi.getActDiscoveryReport).mockResolvedValue({ data: [] });

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/No Acts Referenced/i)).toBeInTheDocument();
      });
    });
  });

  describe('Skip Action', () => {
    it('calls markActSkipped when skip button is clicked', async () => {
      const user = userEvent.setup();

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();
      });

      // Find and click the skip button for the missing act
      const skipButton = screen.getByRole('button', {
        name: /skip negotiable instruments act/i,
      });
      await user.click(skipButton);

      await waitFor(() => {
        expect(citationsApi.markActSkipped).toHaveBeenCalledWith(mockMatterId, {
          actName: mockMissingAct.actName,
        });
      });
    });
  });

  describe('Continue Actions', () => {
    it('calls onContinue when Continue button is clicked', async () => {
      const user = userEvent.setup();

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument();
      });

      const continueButton = screen.getByRole('button', { name: /^continue$/i });
      await user.click(continueButton);

      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      expect(mockOnContinue).toHaveBeenCalled();
    });

    it('calls onContinue when Skip for Now is clicked', async () => {
      const user = userEvent.setup();

      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /skip for now/i })).toBeInTheDocument();
      });

      const skipForNowButton = screen.getByRole('button', { name: /skip for now/i });
      await user.click(skipForNowButton);

      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      expect(mockOnContinue).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has accessible dialog structure', async () => {
      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        expect(dialog).toBeInTheDocument();
        // Verify title and description are rendered (Radix handles aria associations)
        expect(screen.getByText('Act References Detected')).toBeInTheDocument();
      });
    });

    it('has accessible list structure for acts', async () => {
      render(
        <ActDiscoveryModal
          matterId={mockMatterId}
          open={true}
          onOpenChange={mockOnOpenChange}
          onContinue={mockOnContinue}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('list', { name: /available acts/i })).toBeInTheDocument();
        expect(screen.getByRole('list', { name: /missing acts/i })).toBeInTheDocument();
        expect(screen.getByRole('list', { name: /acts not on india code/i })).toBeInTheDocument();
      });
    });
  });
});
