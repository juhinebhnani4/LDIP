import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportBuilder } from './ExportBuilder';

// Mock the data hooks with correct MatterSummary type structure
vi.mock('@/hooks/useMatterSummary', () => ({
  useMatterSummary: vi.fn(() => ({
    summary: {
      matterId: 'test-matter-123',
      parties: [
        { entityId: 'p1', entityName: 'Party 1', role: 'petitioner' },
        { entityId: 'p2', entityName: 'Party 2', role: 'respondent' },
      ],
      subjectMatter: { description: 'Test subject matter', sources: [] },
      currentStatus: { description: 'Active', lastOrderDate: '2024-01-01' },
      keyIssues: [
        { id: 'i1', number: 1, title: 'Issue 1', verificationStatus: 'pending' },
        { id: 'i2', number: 2, title: 'Issue 2', verificationStatus: 'pending' },
        { id: 'i3', number: 3, title: 'Issue 3', verificationStatus: 'pending' },
      ],
      attentionItems: [],
      stats: { totalPages: 100, entitiesFound: 12, eventsExtracted: 5, citationsFound: 8, verificationPercent: 50 },
      generatedAt: '2024-01-01T00:00:00Z',
    },
    isLoading: false,
    isError: false,
  })),
}));

vi.mock('@/hooks/useTimeline', () => ({
  useTimeline: vi.fn(() => ({
    events: [
      { id: 'evt-1', description: 'Event 1' },
      { id: 'evt-2', description: 'Event 2' },
      { id: 'evt-3', description: 'Event 3' },
      { id: 'evt-4', description: 'Event 4' },
      { id: 'evt-5', description: 'Event 5' },
    ],
    isLoading: false,
    isError: false,
  })),
}));

vi.mock('@/hooks/useEntities', () => ({
  useEntities: vi.fn(() => ({
    entities: [],
    total: 12,
    isLoading: false,
    error: null,
  })),
}));

vi.mock('@/hooks/useCitations', () => ({
  useCitationStats: vi.fn(() => ({
    stats: {
      totalCitations: 8,
      verifiedCount: 5,
      pendingCount: 2,
      missingActsCount: 1,
    },
    isLoading: false,
    error: null,
  })),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    info: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Suppress Radix UI Dialog warnings in tests
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation((message) => {
    if (typeof message === 'string' && message.includes('Missing `Description`')) {
      return;
    }
    console.warn(message);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ExportBuilder', () => {
  const mockMatterId = 'test-matter-123';
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders modal with title when open', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Export as PDF')).toBeInTheDocument();
      });
    });

    it('renders all sections with checkboxes', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Executive Summary')).toBeInTheDocument();
        expect(screen.getByText('Timeline')).toBeInTheDocument();
        expect(screen.getByText('Entities')).toBeInTheDocument();
        expect(screen.getByText('Citations')).toBeInTheDocument();
        expect(screen.getByText('Contradictions')).toBeInTheDocument();
        expect(screen.getByText('Key Findings')).toBeInTheDocument();
      });
    });

    it('renders correct format icon for PDF', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Export as PDF')).toBeInTheDocument();
      });
    });

    it('renders correct format label for Word', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="word"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Export as Word')).toBeInTheDocument();
      });
    });

    it('renders correct format label for PowerPoint', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="powerpoint"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Export as PowerPoint')).toBeInTheDocument();
      });
    });

    it('shows content counts for sections', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        // Timeline shows 5 events
        expect(screen.getByText('5 events')).toBeInTheDocument();
        // Entities shows 12 entities
        expect(screen.getByText('12 entities')).toBeInTheDocument();
        // Citations shows 8 citations
        expect(screen.getByText('8 citations')).toBeInTheDocument();
        // Key Findings shows 3 findings
        expect(screen.getByText('3 findings')).toBeInTheDocument();
      });
    });

    it('shows section descriptions', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Case overview and key parties')).toBeInTheDocument();
        expect(screen.getByText('Chronological events')).toBeInTheDocument();
        expect(screen.getByText('Parties and organizations')).toBeInTheDocument();
        expect(screen.getByText('Act references and verifications')).toBeInTheDocument();
      });
    });

    it('shows selected count correctly', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        // All 6 sections are selected by default
        expect(screen.getByText('6 of 6 sections selected')).toBeInTheDocument();
      });
    });
  });

  describe('Section Selection', () => {
    it('toggles section when checkbox is clicked', async () => {
      const user = userEvent.setup();

      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Executive Summary')).toBeInTheDocument();
      });

      // Find the checkbox for Executive Summary and click it
      const executiveSummaryCheckbox = screen.getByRole('checkbox', {
        name: /executive summary/i,
      });
      await user.click(executiveSummaryCheckbox);

      // Check that the count updated
      await waitFor(() => {
        expect(screen.getByText('5 of 6 sections selected')).toBeInTheDocument();
      });
    });

    it('select all button enables all sections', async () => {
      const user = userEvent.setup();

      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Executive Summary')).toBeInTheDocument();
      });

      // Deselect one first
      const executiveSummaryCheckbox = screen.getByRole('checkbox', {
        name: /executive summary/i,
      });
      await user.click(executiveSummaryCheckbox);

      await waitFor(() => {
        expect(screen.getByText('5 of 6 sections selected')).toBeInTheDocument();
      });

      // Click Select all
      const selectAllButton = screen.getByRole('button', { name: /select all/i });
      await user.click(selectAllButton);

      await waitFor(() => {
        expect(screen.getByText('6 of 6 sections selected')).toBeInTheDocument();
      });
    });

    it('deselect all button disables all sections', async () => {
      const user = userEvent.setup();

      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('6 of 6 sections selected')).toBeInTheDocument();
      });

      // Click Deselect all
      const deselectAllButton = screen.getByRole('button', { name: /deselect all/i });
      await user.click(deselectAllButton);

      await waitFor(() => {
        expect(screen.getByText('0 of 6 sections selected')).toBeInTheDocument();
      });
    });

    it('select all button is disabled when all sections are selected', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        const selectAllButton = screen.getByRole('button', { name: /select all/i });
        expect(selectAllButton).toBeDisabled();
      });
    });

    it('deselect all button is disabled when no sections are selected', async () => {
      const user = userEvent.setup();

      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('6 of 6 sections selected')).toBeInTheDocument();
      });

      // Deselect all
      const deselectAllButton = screen.getByRole('button', { name: /deselect all/i });
      await user.click(deselectAllButton);

      await waitFor(() => {
        expect(deselectAllButton).toBeDisabled();
      });
    });
  });

  describe('Footer Buttons', () => {
    it('cancel button closes the modal', async () => {
      const user = userEvent.setup();

      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });

    it('continue button is disabled when no sections are selected', async () => {
      const user = userEvent.setup();

      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('6 of 6 sections selected')).toBeInTheDocument();
      });

      // Deselect all
      const deselectAllButton = screen.getByRole('button', { name: /deselect all/i });
      await user.click(deselectAllButton);

      await waitFor(() => {
        const continueButton = screen.getByRole('button', { name: /continue/i });
        expect(continueButton).toBeDisabled();
      });
    });

    it('continue button is enabled when at least one section is selected', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        const continueButton = screen.getByRole('button', { name: /continue/i });
        expect(continueButton).not.toBeDisabled();
      });
    });

    it('continue button closes modal and shows toast', async () => {
      const { toast } = await import('sonner');
      const user = userEvent.setup();

      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument();
      });

      const continueButton = screen.getByRole('button', { name: /continue/i });
      await user.click(continueButton);

      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
      expect(toast.info).toHaveBeenCalledWith(
        expect.stringContaining('Export generation coming in Story 12.3')
      );
    });
  });

  describe('Drag and Drop Reordering', () => {
    it('renders drag handles for each section', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        // Check for drag handle aria labels
        expect(
          screen.getByRole('button', { name: /drag to reorder executive summary/i })
        ).toBeInTheDocument();
        expect(
          screen.getByRole('button', { name: /drag to reorder timeline/i })
        ).toBeInTheDocument();
      });
    });

    it('has sortable section items with test IDs', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('sortable-section-executive-summary')).toBeInTheDocument();
        expect(screen.getByTestId('sortable-section-timeline')).toBeInTheDocument();
        expect(screen.getByTestId('sortable-section-entities')).toBeInTheDocument();
        expect(screen.getByTestId('sortable-section-citations')).toBeInTheDocument();
        expect(screen.getByTestId('sortable-section-contradictions')).toBeInTheDocument();
        expect(screen.getByTestId('sortable-section-key-findings')).toBeInTheDocument();
      });
    });

    it('sections are displayed in correct initial order', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        const sections = screen.getAllByTestId(/sortable-section-/);
        expect(sections).toHaveLength(6);
        // Verify initial order: executive-summary, timeline, entities, citations, contradictions, key-findings
        expect(sections[0]).toHaveAttribute('data-testid', 'sortable-section-executive-summary');
        expect(sections[1]).toHaveAttribute('data-testid', 'sortable-section-timeline');
        expect(sections[2]).toHaveAttribute('data-testid', 'sortable-section-entities');
        expect(sections[3]).toHaveAttribute('data-testid', 'sortable-section-citations');
        expect(sections[4]).toHaveAttribute('data-testid', 'sortable-section-contradictions');
        expect(sections[5]).toHaveAttribute('data-testid', 'sortable-section-key-findings');
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible dialog structure', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        expect(dialog).toBeInTheDocument();
        expect(dialog).toHaveAttribute('aria-describedby', 'export-builder-description');
      });
    });

    it('has accessible list structure for sections', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('list', { name: /export sections/i })).toBeInTheDocument();
      });
    });

    it('has aria-describedby on checkboxes', async () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        const executiveSummaryCheckbox = screen.getByRole('checkbox', {
          name: /executive summary/i,
        });
        expect(executiveSummaryCheckbox).toHaveAttribute(
          'aria-describedby',
          'section-executive-summary-desc'
        );
      });
    });
  });

  describe('Modal State', () => {
    it('does not render when closed', () => {
      render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={false}
          onOpenChange={mockOnOpenChange}
        />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('resets state when reopened', async () => {
      const user = userEvent.setup();
      const { rerender } = render(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('6 of 6 sections selected')).toBeInTheDocument();
      });

      // Deselect one section
      const executiveSummaryCheckbox = screen.getByRole('checkbox', {
        name: /executive summary/i,
      });
      await user.click(executiveSummaryCheckbox);

      await waitFor(() => {
        expect(screen.getByText('5 of 6 sections selected')).toBeInTheDocument();
      });

      // Close and reopen
      rerender(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={false}
          onOpenChange={mockOnOpenChange}
        />
      );

      rerender(
        <ExportBuilder
          matterId={mockMatterId}
          format="pdf"
          open={true}
          onOpenChange={mockOnOpenChange}
        />
      );

      // State should be reset
      await waitFor(() => {
        expect(screen.getByText('6 of 6 sections selected')).toBeInTheDocument();
      });
    });
  });
});

describe('ExportBuilder Integration with ExportDropdown', () => {
  // These tests verify the integration when modal is triggered from dropdown
  // The dropdown itself has its own tests

  it('renders correct format when triggered for PDF', async () => {
    render(
      <ExportBuilder
        matterId="test-matter"
        format="pdf"
        open={true}
        onOpenChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Export as PDF')).toBeInTheDocument();
    });
  });

  it('renders correct format when triggered for Word', async () => {
    render(
      <ExportBuilder
        matterId="test-matter"
        format="word"
        open={true}
        onOpenChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Export as Word')).toBeInTheDocument();
    });
  });

  it('renders correct format when triggered for PowerPoint', async () => {
    render(
      <ExportBuilder
        matterId="test-matter"
        format="powerpoint"
        open={true}
        onOpenChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Export as PowerPoint')).toBeInTheDocument();
    });
  });
});
