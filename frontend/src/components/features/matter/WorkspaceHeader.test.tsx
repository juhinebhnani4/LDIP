import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorkspaceHeader } from './WorkspaceHeader';

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

// Mock the child components
vi.mock('./EditableMatterName', () => ({
  EditableMatterName: ({ matterId }: { matterId: string }) => (
    <div data-testid="editable-matter-name">Matter: {matterId}</div>
  ),
}));

vi.mock('./ExportDropdown', () => ({
  ExportDropdown: ({ matterId }: { matterId: string }) => (
    <button data-testid="export-dropdown">Export ({matterId})</button>
  ),
}));

vi.mock('./ShareDialog', () => ({
  ShareDialog: ({ matterId }: { matterId: string }) => (
    <button data-testid="share-dialog">Share ({matterId})</button>
  ),
}));

// Mock Tooltip provider
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

describe('WorkspaceHeader', () => {
  const mockMatterId = 'test-matter-123';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders back to dashboard link', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    const backLink = screen.getByRole('link', { name: /back to dashboard/i });
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute('href', '/');
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('renders the editable matter name component', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    expect(screen.getByTestId('editable-matter-name')).toBeInTheDocument();
    expect(screen.getByText(`Matter: ${mockMatterId}`)).toBeInTheDocument();
  });

  it('renders export dropdown', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    expect(screen.getByTestId('export-dropdown')).toBeInTheDocument();
  });

  it('renders share dialog', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    expect(screen.getByTestId('share-dialog')).toBeInTheDocument();
  });

  it('renders settings button with correct aria-label', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    const settingsButton = screen.getByRole('button', { name: /settings/i });
    expect(settingsButton).toBeInTheDocument();
  });

  it('shows toast when settings button is clicked', async () => {
    const { toast } = await import('sonner');
    const user = userEvent.setup();

    render(<WorkspaceHeader matterId={mockMatterId} />);

    const settingsButton = screen.getByRole('button', { name: /settings/i });
    await user.click(settingsButton);

    expect(toast.info).toHaveBeenCalledWith('Settings coming soon');
  });

  it('has sticky positioning with proper z-index', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    const header = screen.getByRole('banner');
    expect(header).toHaveClass('sticky');
    expect(header).toHaveClass('top-0');
    expect(header).toHaveClass('z-50');
  });

  it('passes matterId to all child components', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    expect(screen.getByText(`Matter: ${mockMatterId}`)).toBeInTheDocument();
    expect(screen.getByText(`Export (${mockMatterId})`)).toBeInTheDocument();
    expect(screen.getByText(`Share (${mockMatterId})`)).toBeInTheDocument();
  });

  it('renders with correct layout structure', () => {
    render(<WorkspaceHeader matterId={mockMatterId} />);

    const header = screen.getByRole('banner');
    expect(header).toBeInTheDocument();

    // Check container exists with flex layout
    const container = header.querySelector('.container');
    expect(container).toHaveClass('flex');
    expect(container).toHaveClass('h-14');
    expect(container).toHaveClass('items-center');
  });
});
