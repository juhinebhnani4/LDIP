import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from '@testing-library/react';
import { QAPanelHeader } from './QAPanelHeader';
import { useQAPanelStore } from '@/stores/qaPanelStore';

// Mock DropdownMenu components
vi.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-menu">{children}</div>
  ),
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-trigger">{children}</div>
  ),
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-content">{children}</div>
  ),
  DropdownMenuItem: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <button data-testid="dropdown-item" onClick={onClick}>
      {children}
    </button>
  ),
  DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-label">{children}</div>
  ),
  DropdownMenuSeparator: () => <hr data-testid="dropdown-separator" />,
}));

describe('QAPanelHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store state
    act(() => {
      useQAPanelStore.getState().reset();
    });
  });

  it('renders Q&A Assistant title', () => {
    render(<QAPanelHeader />);

    expect(screen.getByText('Q&A Assistant')).toBeInTheDocument();
  });

  it('renders position dropdown menu', () => {
    render(<QAPanelHeader />);

    expect(screen.getByTestId('dropdown-menu')).toBeInTheDocument();
  });

  it('renders settings button with aria-label', () => {
    render(<QAPanelHeader />);

    const button = screen.getByRole('button', { name: /panel position/i });
    expect(button).toBeInTheDocument();
  });

  it('shows all four position options', () => {
    render(<QAPanelHeader />);

    const items = screen.getAllByTestId('dropdown-item');
    expect(items.length).toBe(4);

    expect(screen.getByText('Right Sidebar')).toBeInTheDocument();
    expect(screen.getByText('Bottom Panel')).toBeInTheDocument();
    expect(screen.getByText('Floating')).toBeInTheDocument();
    expect(screen.getByText('Hide Panel')).toBeInTheDocument();
  });

  it('shows Panel Position label in dropdown', () => {
    render(<QAPanelHeader />);

    expect(screen.getByTestId('dropdown-label')).toHaveTextContent(
      'Panel Position'
    );
  });

  it('calls setPosition when right sidebar option clicked', async () => {
    const user = userEvent.setup();
    render(<QAPanelHeader />);

    const items = screen.getAllByTestId('dropdown-item');
    const rightItem = items.find((item) =>
      item.textContent?.includes('Right Sidebar')
    );

    await user.click(rightItem!);

    expect(useQAPanelStore.getState().position).toBe('right');
  });

  it('calls setPosition when bottom panel option clicked', async () => {
    const user = userEvent.setup();
    render(<QAPanelHeader />);

    const items = screen.getAllByTestId('dropdown-item');
    const bottomItem = items.find((item) =>
      item.textContent?.includes('Bottom Panel')
    );

    await user.click(bottomItem!);

    expect(useQAPanelStore.getState().position).toBe('bottom');
  });

  it('calls setPosition when floating option clicked', async () => {
    const user = userEvent.setup();
    render(<QAPanelHeader />);

    const items = screen.getAllByTestId('dropdown-item');
    const floatItem = items.find((item) =>
      item.textContent?.includes('Floating')
    );

    await user.click(floatItem!);

    expect(useQAPanelStore.getState().position).toBe('float');
  });

  it('calls setPosition when hide panel option clicked', async () => {
    const user = userEvent.setup();
    render(<QAPanelHeader />);

    const items = screen.getAllByTestId('dropdown-item');
    const hideItem = items.find((item) =>
      item.textContent?.includes('Hide Panel')
    );

    await user.click(hideItem!);

    expect(useQAPanelStore.getState().position).toBe('hidden');
  });

  it('has proper layout structure', () => {
    const { container } = render(<QAPanelHeader />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('flex');
    expect(wrapper).toHaveClass('items-center');
    expect(wrapper).toHaveClass('justify-between');
    expect(wrapper).toHaveClass('border-b');
    expect(wrapper).toHaveClass('p-3');
  });

  it('renders title with correct styling', () => {
    render(<QAPanelHeader />);

    const title = screen.getByText('Q&A Assistant');
    expect(title.tagName).toBe('H2');
    expect(title).toHaveClass('text-sm');
    expect(title).toHaveClass('font-semibold');
  });

  it('shows checkmark for the current position', () => {
    act(() => {
      useQAPanelStore.getState().setPosition('bottom');
    });

    render(<QAPanelHeader />);

    // Find the bottom item and check it has a checkmark (lucide-react Check icon)
    const items = screen.getAllByTestId('dropdown-item');
    const bottomItem = items.find((item) =>
      item.textContent?.includes('Bottom Panel')
    );

    // The Check icon should be a child of the bottom item
    const checkIcon = bottomItem?.querySelector('svg');
    expect(checkIcon).toBeInTheDocument();
  });

  it('renders custom actions when provided', () => {
    const CustomAction = () => (
      <button data-testid="custom-action">Custom</button>
    );

    render(<QAPanelHeader actions={<CustomAction />} />);

    expect(screen.getByTestId('custom-action')).toBeInTheDocument();
  });
});
