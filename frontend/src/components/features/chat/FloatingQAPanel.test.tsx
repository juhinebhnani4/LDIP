import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from '@testing-library/react';
import { FloatingQAPanel } from './FloatingQAPanel';
import { useQAPanelStore } from '@/stores/qaPanelStore';

// Mock Tooltip components
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

// Mock QAPanelHeader - receives actions prop
vi.mock('./QAPanelHeader', () => ({
  QAPanelHeader: ({ actions }: { actions?: React.ReactNode }) => (
    <div data-testid="qa-panel-header">
      Q&A Assistant
      {actions}
    </div>
  ),
}));

// Mock QAPanelPlaceholder
vi.mock('./QAPanelPlaceholder', () => ({
  QAPanelPlaceholder: () => <div data-testid="qa-panel-placeholder">Placeholder</div>,
}));

describe('FloatingQAPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store state
    act(() => {
      useQAPanelStore.getState().reset();
    });
  });

  it('renders as a dialog with aria-label', () => {
    render(<FloatingQAPanel />);

    const dialog = screen.getByRole('dialog', { name: /q&a assistant/i });
    expect(dialog).toBeInTheDocument();
  });

  it('renders Q&A Assistant title in header', () => {
    render(<FloatingQAPanel />);

    expect(screen.getByText('Q&A Assistant')).toBeInTheDocument();
  });

  it('renders minimize button with aria-label', () => {
    render(<FloatingQAPanel />);

    const button = screen.getByRole('button', { name: /minimize panel/i });
    expect(button).toBeInTheDocument();
  });

  it('renders placeholder content', () => {
    render(<FloatingQAPanel />);

    expect(screen.getByTestId('qa-panel-placeholder')).toBeInTheDocument();
  });

  it('renders resize handle with aria-label', () => {
    render(<FloatingQAPanel />);

    const handle = screen.getByRole('separator', { name: /resize panel/i });
    expect(handle).toBeInTheDocument();
  });

  it('sets position to hidden when minimize clicked', async () => {
    const user = userEvent.setup();

    act(() => {
      useQAPanelStore.getState().setPosition('float');
    });

    render(<FloatingQAPanel />);

    const button = screen.getByRole('button', { name: /minimize panel/i });
    await user.click(button);

    expect(useQAPanelStore.getState().position).toBe('hidden');
  });

  it('has fixed positioning with correct z-index', () => {
    render(<FloatingQAPanel />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('fixed');
    expect(dialog).toHaveClass('z-40');
  });

  it('applies position from store', () => {
    act(() => {
      useQAPanelStore.getState().setFloatPosition(200, 150);
    });

    render(<FloatingQAPanel />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveStyle({ left: '200px', top: '150px' });
  });

  it('applies size from store', () => {
    act(() => {
      useQAPanelStore.getState().setFloatSize(500, 600);
    });

    render(<FloatingQAPanel />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveStyle({ width: '500px', height: '600px' });
  });

  it('has proper styling classes', () => {
    render(<FloatingQAPanel />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('rounded-lg');
    expect(dialog).toHaveClass('border');
    expect(dialog).toHaveClass('bg-background');
    expect(dialog).toHaveClass('shadow-lg');
  });

  it('renders tooltip for minimize button', () => {
    render(<FloatingQAPanel />);

    expect(screen.getByTestId('tooltip-content')).toHaveTextContent('Minimize');
  });

  it('reuses QAPanelHeader component', () => {
    render(<FloatingQAPanel />);

    expect(screen.getByTestId('qa-panel-header')).toBeInTheDocument();
  });

  describe('Drag behavior', () => {
    it('does not start drag when clicking button', () => {
      render(<FloatingQAPanel />);

      const button = screen.getByRole('button', { name: /minimize panel/i });

      // Initial position
      const initialX = useQAPanelStore.getState().floatX;
      const initialY = useQAPanelStore.getState().floatY;

      // Click button (should not start drag)
      fireEvent.mouseDown(button);
      fireEvent.mouseMove(document, { clientX: 500, clientY: 500 });
      fireEvent.mouseUp(document);

      // Position should not change
      expect(useQAPanelStore.getState().floatX).toBe(initialX);
      expect(useQAPanelStore.getState().floatY).toBe(initialY);
    });

    it('has draggable header area with cursor-move class', () => {
      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const draggableArea = dialog.querySelector('.cursor-move');

      expect(draggableArea).toBeInTheDocument();
    });

    it('has keyboard accessible drag area', () => {
      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const dragButton = dialog.querySelector('[role="button"][aria-label*="arrow keys"]');

      expect(dragButton).toBeInTheDocument();
      expect(dragButton).toHaveAttribute('tabindex', '0');
    });
  });

  describe('Keyboard navigation (M2 fix)', () => {
    it('moves panel up with ArrowUp key', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(100, 100);
      });

      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const dragArea = dialog.querySelector('.cursor-move');

      fireEvent.keyDown(dragArea!, { key: 'ArrowUp' });

      expect(useQAPanelStore.getState().floatY).toBe(80); // 100 - 20 (KEYBOARD_MOVE_STEP)
    });

    it('moves panel down with ArrowDown key', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(100, 100);
      });

      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const dragArea = dialog.querySelector('.cursor-move');

      fireEvent.keyDown(dragArea!, { key: 'ArrowDown' });

      expect(useQAPanelStore.getState().floatY).toBe(120); // 100 + 20
    });

    it('moves panel left with ArrowLeft key', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(100, 100);
      });

      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const dragArea = dialog.querySelector('.cursor-move');

      fireEvent.keyDown(dragArea!, { key: 'ArrowLeft' });

      expect(useQAPanelStore.getState().floatX).toBe(80); // 100 - 20
    });

    it('moves panel right with ArrowRight key', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(100, 100);
      });

      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const dragArea = dialog.querySelector('.cursor-move');

      fireEvent.keyDown(dragArea!, { key: 'ArrowRight' });

      expect(useQAPanelStore.getState().floatX).toBe(120); // 100 + 20
    });

    it('constrains keyboard movement to top boundary', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(100, 10);
      });

      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const dragArea = dialog.querySelector('.cursor-move');

      fireEvent.keyDown(dragArea!, { key: 'ArrowUp' });

      expect(useQAPanelStore.getState().floatY).toBe(0); // Clamped to 0
    });

    it('constrains keyboard movement to left boundary', () => {
      act(() => {
        useQAPanelStore.getState().setFloatPosition(10, 100);
      });

      render(<FloatingQAPanel />);

      const dialog = screen.getByRole('dialog');
      const dragArea = dialog.querySelector('.cursor-move');

      fireEvent.keyDown(dragArea!, { key: 'ArrowLeft' });

      expect(useQAPanelStore.getState().floatX).toBe(0); // Clamped to 0
    });
  });

  describe('Resize behavior', () => {
    it('updates size on resize', () => {
      render(<FloatingQAPanel />);

      // Set initial size
      act(() => {
        useQAPanelStore.getState().setFloatSize(400, 500);
      });

      const handle = screen.getByRole('separator', { name: /resize panel/i });

      // Start resize
      fireEvent.mouseDown(handle, { clientX: 500, clientY: 600 });
      fireEvent.mouseMove(document, { clientX: 600, clientY: 700 });
      fireEvent.mouseUp(document);

      // Size should have changed
      const state = useQAPanelStore.getState();
      expect(state.floatWidth).toBe(500); // 400 + (600-500)
      expect(state.floatHeight).toBe(600); // 500 + (700-600)
    });

    it('enforces minimum size during resize', () => {
      render(<FloatingQAPanel />);

      // Set initial size
      act(() => {
        useQAPanelStore.getState().setFloatSize(400, 500);
      });

      const handle = screen.getByRole('separator', { name: /resize panel/i });

      // Try to resize to below minimum
      fireEvent.mouseDown(handle, { clientX: 500, clientY: 600 });
      fireEvent.mouseMove(document, { clientX: 200, clientY: 200 }); // Would result in negative size
      fireEvent.mouseUp(document);

      // Size should be clamped to minimum
      const state = useQAPanelStore.getState();
      expect(state.floatWidth).toBeGreaterThanOrEqual(300); // MIN_FLOAT_WIDTH
      expect(state.floatHeight).toBeGreaterThanOrEqual(200); // MIN_FLOAT_HEIGHT
    });

    it('resize handle has correct ARIA role (separator not slider)', () => {
      render(<FloatingQAPanel />);

      // Should find separator, not slider
      const handle = screen.getByRole('separator', { name: /resize panel/i });
      expect(handle).toBeInTheDocument();

      // Should NOT find slider
      expect(screen.queryByRole('slider')).not.toBeInTheDocument();
    });
  });
});
