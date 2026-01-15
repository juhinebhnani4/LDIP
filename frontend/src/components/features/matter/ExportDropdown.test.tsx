import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportDropdown } from './ExportDropdown';
import { toast } from 'sonner';

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

// Mock Tooltip provider
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

describe('ExportDropdown', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
  });

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

    // Menu items should be visible
    expect(screen.getByRole('menuitem', { name: /export as pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /export as word/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /export as powerpoint/i })).toBeInTheDocument();
  });

  it('shows toast for PDF export with placeholder message', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const pdfOption = screen.getByRole('menuitem', { name: /export as pdf/i });
    await user.click(pdfOption);

    expect(mockToast.info).toHaveBeenCalledWith(
      'Export Builder coming in Epic 12 (PDF format selected)'
    );
  });

  it('shows toast for Word export with placeholder message', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const wordOption = screen.getByRole('menuitem', { name: /export as word/i });
    await user.click(wordOption);

    expect(mockToast.info).toHaveBeenCalledWith(
      'Export Builder coming in Epic 12 (WORD format selected)'
    );
  });

  it('shows toast for PowerPoint export with placeholder message', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const pptOption = screen.getByRole('menuitem', { name: /export as powerpoint/i });
    await user.click(pptOption);

    expect(mockToast.info).toHaveBeenCalledWith(
      'Export Builder coming in Epic 12 (POWERPOINT format selected)'
    );
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

  it('closes dropdown after selection', async () => {
    const user = userEvent.setup();
    render(<ExportDropdown matterId={mockMatterId} />);

    const exportButton = screen.getByRole('button', { name: /export options/i });
    await user.click(exportButton);

    const pdfOption = screen.getByRole('menuitem', { name: /export as pdf/i });
    await user.click(pdfOption);

    // Menu should be closed
    expect(screen.queryByRole('menuitem', { name: /export as pdf/i })).not.toBeInTheDocument();
  });
});
