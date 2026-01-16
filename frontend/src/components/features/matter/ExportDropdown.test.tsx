import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportDropdown } from './ExportDropdown';
import { toast } from 'sonner';
import * as exportsApi from '@/lib/api/exports';

// Mock sonner toast with proper vitest types
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

// Properly typed mock toast using vitest's Mock type
const mockToast = toast as unknown as {
  success: Mock;
  error: Mock;
  info: Mock;
};

// Mock exports API
vi.mock('@/lib/api/exports', () => ({
  generateExecutiveSummary: vi.fn(),
}));

const mockGenerateExecutiveSummary = exportsApi.generateExecutiveSummary as Mock;

// Mock Tooltip provider
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

// Mock ExportBuilder
vi.mock('@/components/features/export', () => ({
  ExportBuilder: ({ open }: { open: boolean }) =>
    open ? <div data-testid="export-builder-modal">Export Builder Modal</div> : null,
}));

describe('ExportDropdown', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset window.open mock
    vi.stubGlobal('open', vi.fn());
  });

  // ==========================================================================
  // Basic Rendering Tests
  // ==========================================================================

  it('renders export button with correct aria-label', () => {
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    expect(exportButton).toBeInTheDocument();
  });

  it('opens dropdown menu when clicked', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    // Menu items should be visible - including Quick Export
    expect(screen.getByText(/quick export: executive summary/i)).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /export as pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /export as word/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /export as powerpoint/i })).toBeInTheDocument();
  });

  it('renders download icon in trigger button', () => {
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    const icon = exportButton.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });

  it('renders icons for each menu item', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    // Each menu item should have an icon
    const menuItems = screen.getAllByRole('menuitem');
    menuItems.forEach((item) => {
      expect(item.querySelector('svg')).toBeInTheDocument();
    });
  });

  // ==========================================================================
  // Story 12.4: Quick Export Tests (AC #1)
  // ==========================================================================

  it('shows Quick Export: Executive Summary option in dropdown (AC #1)', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    // Quick Export should be visible with description
    expect(screen.getByText(/quick export: executive summary/i)).toBeInTheDocument();
    expect(screen.getByText(/1-2 page pdf overview/i)).toBeInTheDocument();
  });

  it('shows separator between quick export and full export options', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    // Separator should exist
    const separator = document.querySelector('[role="separator"]');
    expect(separator).toBeInTheDocument();
  });

  it('calls generateExecutiveSummary API when Quick Export clicked', async () => {
    const user = userEvent.setup();

    mockGenerateExecutiveSummary.mockResolvedValueOnce({
      exportId: 'export-123',
      status: 'completed',
      downloadUrl: 'https://storage.example.com/download/test.pdf',
      fileName: 'Test-Executive-Summary-2026-01-16.pdf',
      contentSummary: {
        partiesIncluded: 5,
        datesIncluded: 8,
        issuesIncluded: 3,
        pendingVerificationCount: 2,
      },
    });

    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const quickExportOption = screen.getByText(/quick export: executive summary/i).closest('[role="menuitem"]');
    await user.click(quickExportOption!);

    expect(mockGenerateExecutiveSummary).toHaveBeenCalledWith(mockMatterId);
  });

  it('opens download URL on successful quick export', async () => {
    const user = userEvent.setup();
    const mockWindowOpen = vi.fn();
    vi.stubGlobal('open', mockWindowOpen);

    mockGenerateExecutiveSummary.mockResolvedValueOnce({
      exportId: 'export-123',
      status: 'completed',
      downloadUrl: 'https://storage.example.com/download/test.pdf',
      fileName: 'Test-Executive-Summary.pdf',
      contentSummary: {
        partiesIncluded: 5,
        datesIncluded: 8,
        issuesIncluded: 3,
        pendingVerificationCount: 2,
      },
    });

    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const quickExportOption = screen.getByText(/quick export: executive summary/i).closest('[role="menuitem"]');
    await user.click(quickExportOption!);

    await waitFor(() => {
      expect(mockWindowOpen).toHaveBeenCalledWith('https://storage.example.com/download/test.pdf', '_blank');
    });

    expect(mockToast.success).toHaveBeenCalledWith('Executive summary downloaded');
  });

  it('shows error toast when quick export fails', async () => {
    const user = userEvent.setup();

    mockGenerateExecutiveSummary.mockRejectedValueOnce(new Error('Generation failed'));

    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const quickExportOption = screen.getByText(/quick export: executive summary/i).closest('[role="menuitem"]');
    await user.click(quickExportOption!);

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Generation failed');
    });
  });

  it('shows error when download URL is missing', async () => {
    const user = userEvent.setup();

    mockGenerateExecutiveSummary.mockResolvedValueOnce({
      exportId: 'export-123',
      status: 'completed',
      downloadUrl: null,
      fileName: 'Test.pdf',
      contentSummary: {
        partiesIncluded: 0,
        datesIncluded: 0,
        issuesIncluded: 0,
        pendingVerificationCount: 0,
      },
    });

    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const quickExportOption = screen.getByText(/quick export: executive summary/i).closest('[role="menuitem"]');
    await user.click(quickExportOption!);

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Failed to generate executive summary - no download URL');
    });
  });

  // ==========================================================================
  // Full Export Builder Tests
  // ==========================================================================

  it('opens ExportBuilder modal when PDF format selected', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const pdfOption = screen.getByRole('menuitem', { name: /export as pdf/i });
    await user.click(pdfOption);

    expect(screen.getByTestId('export-builder-modal')).toBeInTheDocument();
  });

  it('opens ExportBuilder modal when Word format selected', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const wordOption = screen.getByRole('menuitem', { name: /export as word/i });
    await user.click(wordOption);

    expect(screen.getByTestId('export-builder-modal')).toBeInTheDocument();
  });

  it('opens ExportBuilder modal when PowerPoint format selected', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const pptOption = screen.getByRole('menuitem', { name: /export as powerpoint/i });
    await user.click(pptOption);

    expect(screen.getByTestId('export-builder-modal')).toBeInTheDocument();
  });
});
