import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from '@testing-library/react';
import { QAPanelExpandButton } from './QAPanelExpandButton';
import { useQAPanelStore } from '@/stores/qaPanelStore';

// Mock Tooltip components
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

describe('QAPanelExpandButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store state
    act(() => {
      useQAPanelStore.getState().reset();
    });
  });

  it('renders expand button with proper aria-label', () => {
    render(<QAPanelExpandButton />);

    const button = screen.getByRole('button', { name: /open q&a panel/i });
    expect(button).toBeInTheDocument();
  });

  it('renders message square icon', () => {
    const { container } = render(<QAPanelExpandButton />);

    // MessageSquare icon should be present
    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass('h-5');
    expect(icon).toHaveClass('w-5');
  });

  it('does not show badge when unreadCount is 0', () => {
    act(() => {
      useQAPanelStore.getState().setUnreadCount(0);
    });

    render(<QAPanelExpandButton />);

    // Badge should not be present
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  it('shows badge with unread count when count > 0', () => {
    act(() => {
      useQAPanelStore.getState().setUnreadCount(5);
    });

    render(<QAPanelExpandButton />);

    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('shows 99+ for counts over 99', () => {
    act(() => {
      useQAPanelStore.getState().setUnreadCount(150);
    });

    render(<QAPanelExpandButton />);

    expect(screen.getByText('99+')).toBeInTheDocument();
  });

  it('calls restoreFromHidden when clicked', async () => {
    const user = userEvent.setup();

    // Set to hidden with previous position as bottom
    act(() => {
      useQAPanelStore.getState().setPosition('bottom');
      useQAPanelStore.getState().setPosition('hidden');
    });

    render(<QAPanelExpandButton />);

    const button = screen.getByRole('button', { name: /open q&a panel/i });
    await user.click(button);

    // Should restore to bottom (previous position)
    expect(useQAPanelStore.getState().position).toBe('bottom');
  });

  it('has fixed positioning', () => {
    const { container } = render(<QAPanelExpandButton />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('fixed');
    expect(wrapper).toHaveClass('bottom-4');
    expect(wrapper).toHaveClass('right-4');
    expect(wrapper).toHaveClass('z-30');
  });

  it('button has rounded-full styling', () => {
    render(<QAPanelExpandButton />);

    const button = screen.getByRole('button', { name: /open q&a panel/i });
    expect(button).toHaveClass('rounded-full');
    expect(button).toHaveClass('h-12');
    expect(button).toHaveClass('w-12');
    expect(button).toHaveClass('shadow-lg');
  });

  it('renders tooltip with correct text', () => {
    render(<QAPanelExpandButton />);

    expect(screen.getByTestId('tooltip-content')).toHaveTextContent(
      'Open Q&A Panel'
    );
  });
});
