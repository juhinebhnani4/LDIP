/**
 * ExportBuilder Component Tests
 *
 * Story 12.1: Export Builder Modal with Section Selection
 * Story 12.2: Export Inline Editing and Preview
 *
 * Note: The Radix UI Dialog component causes infinite loops in jsdom due to
 * how @radix-ui/react-presence handles refs. The mocks for dialog, alert-dialog,
 * tabs, and resizable are configured in vitest.config.ts to avoid this issue.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportBuilder } from './ExportBuilder';

// Mock ExportPreviewPanel to simplify tests
vi.mock('./ExportPreviewPanel', () => ({
  ExportPreviewPanel: () => <div data-testid="export-preview-panel">Preview Panel</div>,
}));

// Mock ExportSectionList with functional implementation
vi.mock('./ExportSectionList', () => ({
  ExportSectionList: ({
    sections,
    onToggleSection,
    onSelectAll,
    onDeselectAll,
    selectedCount,
  }: {
    sections: Array<{ id: string; label: string; description: string; enabled: boolean; count?: number; countLabel?: string }>;
    onToggleSection: (id: string) => void;
    onSelectAll: () => void;
    onDeselectAll: () => void;
    selectedCount: number;
  }) => (
    <div data-testid="export-section-list">
      <div className="flex gap-2 mb-4">
        <button
          onClick={onSelectAll}
          disabled={selectedCount === sections.length}
        >
          Select all
        </button>
        <button
          onClick={onDeselectAll}
          disabled={selectedCount === 0}
        >
          Deselect all
        </button>
        <span>{selectedCount} of {sections.length} sections selected</span>
      </div>
      <ul role="list" aria-label="Export sections">
        {sections.map((section) => (
          <li key={section.id} data-testid={`sortable-section-${section.id}`}>
            <input
              type="checkbox"
              role="checkbox"
              checked={section.enabled}
              onChange={() => onToggleSection(section.id)}
              aria-label={section.label}
              aria-describedby={`section-${section.id}-desc`}
            />
            <span>{section.label}</span>
            <span id={`section-${section.id}-desc`}>{section.description}</span>
            {section.count !== undefined && (
              <span>{section.count} {section.countLabel}</span>
            )}
            <button aria-label={`Drag to reorder ${section.label}`}>⋮</button>
          </li>
        ))}
      </ul>
    </div>
  ),
}));

// Mock the data hooks with correct type structure
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
  useCitationsList: vi.fn(() => ({
    citations: [
      { id: 'cit-1', actName: 'Test Act', sectionNumber: '10', verificationStatus: 'pending' },
      { id: 'cit-2', actName: 'Test Act 2', sectionNumber: '20', verificationStatus: 'verified' },
    ],
    meta: null,
    isLoading: false,
    error: null,
    mutate: vi.fn(),
  })),
}));

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
        expect(screen.getByText('5 events')).toBeInTheDocument();
        expect(screen.getByText('12 entities')).toBeInTheDocument();
        expect(screen.getByText('8 citations')).toBeInTheDocument();
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

      const executiveSummaryCheckbox = screen.getByRole('checkbox', {
        name: /executive summary/i,
      });
      await user.click(executiveSummaryCheckbox);

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

      const deselectAllButton = screen.getByRole('button', { name: /deselect all/i });
      await user.click(deselectAllButton);

      await waitFor(() => {
        expect(screen.getByText('0 of 6 sections selected')).toBeInTheDocument();
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

  describe('Drag and Drop Reordering', () => {
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
        expect(
          screen.getByRole('button', { name: /drag to reorder executive summary/i })
        ).toBeInTheDocument();
        expect(
          screen.getByRole('button', { name: /drag to reorder timeline/i })
        ).toBeInTheDocument();
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
});

describe('ExportBuilder Integration with ExportDropdown', () => {
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
