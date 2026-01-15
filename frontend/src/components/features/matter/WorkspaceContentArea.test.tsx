import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { act } from '@testing-library/react';
import { WorkspaceContentArea } from './WorkspaceContentArea';
import { useQAPanelStore } from '@/stores/qaPanelStore';

// Mock ResizablePanelGroup and related components
vi.mock('@/components/ui/resizable', () => ({
  ResizablePanelGroup: ({
    children,
    direction,
    className,
  }: {
    children: React.ReactNode;
    direction: string;
    className?: string;
  }) => (
    <div
      data-testid="resizable-panel-group"
      data-direction={direction}
      className={className}
    >
      {children}
    </div>
  ),
  ResizablePanel: ({
    children,
    defaultSize,
    minSize,
    maxSize,
    onResize,
  }: {
    children: React.ReactNode;
    defaultSize?: number;
    minSize?: number;
    maxSize?: number;
    onResize?: (size: number) => void;
  }) => (
    <div
      data-testid="resizable-panel"
      data-default-size={defaultSize}
      data-min-size={minSize}
      data-max-size={maxSize}
      onClick={() => onResize?.(50)}
    >
      {children}
    </div>
  ),
  ResizableHandle: ({ withHandle }: { withHandle?: boolean }) => (
    <div data-testid="resizable-handle" data-with-handle={withHandle} />
  ),
}));

// Mock Q&A Panel components
vi.mock('@/components/features/chat/QAPanel', () => ({
  QAPanel: ({ matterId }: { matterId: string }) => (
    <div data-testid="qa-panel">QA Panel: {matterId}</div>
  ),
}));

vi.mock('@/components/features/chat/FloatingQAPanel', () => ({
  FloatingQAPanel: ({ matterId }: { matterId: string }) => (
    <div data-testid="floating-qa-panel">Floating QA: {matterId}</div>
  ),
}));

vi.mock('@/components/features/chat/QAPanelExpandButton', () => ({
  QAPanelExpandButton: () => <button data-testid="qa-expand-button">Expand</button>,
}));

describe('WorkspaceContentArea', () => {
  const mockMatterId = 'test-matter-123';
  const mockChildren = <div data-testid="tab-content">Tab Content</div>;

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store state
    act(() => {
      useQAPanelStore.getState().reset();
    });
  });

  describe('Right sidebar layout (AC #1, #2)', () => {
    beforeEach(() => {
      act(() => {
        useQAPanelStore.getState().setPosition('right');
      });
    });

    it('renders horizontal resizable layout for right position', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      const panelGroup = screen.getByTestId('resizable-panel-group');
      expect(panelGroup).toHaveAttribute('data-direction', 'horizontal');
    });

    it('renders children in content panel', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('tab-content')).toBeInTheDocument();
    });

    it('renders QAPanel in sidebar', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('qa-panel')).toBeInTheDocument();
      expect(screen.getByTestId('qa-panel')).toHaveTextContent(
        `QA Panel: ${mockMatterId}`
      );
    });

    it('renders resize handle with handle indicator', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      const handle = screen.getByTestId('resizable-handle');
      expect(handle).toHaveAttribute('data-with-handle', 'true');
    });

    it('applies correct min/max constraints to QA panel', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      const panels = screen.getAllByTestId('resizable-panel');
      const qaPanel = panels[1]; // Second panel is QA

      expect(qaPanel).toHaveAttribute('data-min-size', '20');
      expect(qaPanel).toHaveAttribute('data-max-size', '60');
    });
  });

  describe('Bottom panel layout (AC #1, #2)', () => {
    beforeEach(() => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
      });
    });

    it('renders vertical resizable layout for bottom position', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      const panelGroup = screen.getByTestId('resizable-panel-group');
      expect(panelGroup).toHaveAttribute('data-direction', 'vertical');
    });

    it('renders children in content panel', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('tab-content')).toBeInTheDocument();
    });

    it('renders QAPanel in bottom panel', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('qa-panel')).toBeInTheDocument();
    });

    it('applies correct min/max constraints to QA panel', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      const panels = screen.getAllByTestId('resizable-panel');
      const qaPanel = panels[1]; // Second panel is QA

      expect(qaPanel).toHaveAttribute('data-min-size', '20');
      expect(qaPanel).toHaveAttribute('data-max-size', '60');
    });
  });

  describe('Floating panel layout (AC #3)', () => {
    beforeEach(() => {
      act(() => {
        useQAPanelStore.getState().setPosition('float');
      });
    });

    it('renders floating QA panel when position is float', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('floating-qa-panel')).toBeInTheDocument();
      expect(screen.getByTestId('floating-qa-panel')).toHaveTextContent(
        `Floating QA: ${mockMatterId}`
      );
    });

    it('renders children in content area', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('tab-content')).toBeInTheDocument();
    });

    it('does not render resizable panel group', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.queryByTestId('resizable-panel-group')).not.toBeInTheDocument();
    });
  });

  describe('Hidden panel layout (AC #3)', () => {
    beforeEach(() => {
      act(() => {
        useQAPanelStore.getState().setPosition('hidden');
      });
    });

    it('renders expand button when position is hidden', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('qa-expand-button')).toBeInTheDocument();
    });

    it('renders children in content area', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('tab-content')).toBeInTheDocument();
    });

    it('does not render QA panel or floating panel', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.queryByTestId('qa-panel')).not.toBeInTheDocument();
      expect(screen.queryByTestId('floating-qa-panel')).not.toBeInTheDocument();
    });

    it('does not render resizable panel group', () => {
      render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.queryByTestId('resizable-panel-group')).not.toBeInTheDocument();
    });
  });

  describe('Position transitions (AC #3)', () => {
    it('switches from right to bottom correctly', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('right');
      });

      const { rerender } = render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('resizable-panel-group')).toHaveAttribute(
        'data-direction',
        'horizontal'
      );

      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
      });

      rerender(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('resizable-panel-group')).toHaveAttribute(
        'data-direction',
        'vertical'
      );
    });

    it('switches from bottom to float correctly', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('bottom');
      });

      const { rerender } = render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('resizable-panel-group')).toBeInTheDocument();

      act(() => {
        useQAPanelStore.getState().setPosition('float');
      });

      rerender(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.queryByTestId('resizable-panel-group')).not.toBeInTheDocument();
      expect(screen.getByTestId('floating-qa-panel')).toBeInTheDocument();
    });

    it('switches from float to hidden correctly', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('float');
      });

      const { rerender } = render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('floating-qa-panel')).toBeInTheDocument();

      act(() => {
        useQAPanelStore.getState().setPosition('hidden');
      });

      rerender(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.queryByTestId('floating-qa-panel')).not.toBeInTheDocument();
      expect(screen.getByTestId('qa-expand-button')).toBeInTheDocument();
    });

    it('switches from hidden to right correctly', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('hidden');
      });

      const { rerender } = render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.getByTestId('qa-expand-button')).toBeInTheDocument();

      act(() => {
        useQAPanelStore.getState().setPosition('right');
      });

      rerender(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      expect(screen.queryByTestId('qa-expand-button')).not.toBeInTheDocument();
      expect(screen.getByTestId('qa-panel')).toBeInTheDocument();
    });
  });

  describe('Content wrapper styling', () => {
    it('has overflow-auto on content wrapper in right mode', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('right');
      });

      const { container } = render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      const contentWrapper = container.querySelector('.overflow-auto');
      expect(contentWrapper).toBeInTheDocument();
    });

    it('has h-full on content wrapper in right mode', () => {
      act(() => {
        useQAPanelStore.getState().setPosition('right');
      });

      const { container } = render(
        <WorkspaceContentArea matterId={mockMatterId}>
          {mockChildren}
        </WorkspaceContentArea>
      );

      const contentWrapper = container.querySelector('.h-full');
      expect(contentWrapper).toBeInTheDocument();
    });
  });
});
