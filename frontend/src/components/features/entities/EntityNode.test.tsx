import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import { EntityNode, calculateNodeSize, type EntityNodeProps } from './EntityNode';
import type { EntityNodeData } from '@/types/entity';

// Mock the Tooltip components to simplify testing
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const createMockNodeData = (overrides: Partial<EntityNodeData> = {}): EntityNodeData => ({
  id: 'entity-1',
  canonicalName: 'Test Entity',
  entityType: 'PERSON',
  mentionCount: 10,
  aliases: [],
  metadata: {},
  isSelected: false,
  isConnected: false,
  isDimmed: false,
  ...overrides,
});

const renderEntityNode = (props: Partial<EntityNodeProps> = {}) => {
  const defaultProps: EntityNodeProps = {
    id: 'node-1',
    data: createMockNodeData(),
    type: 'entity',
    // React Flow NodeProps fields
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    dragging: false,
    selected: false,
    isConnectable: true,
    zIndex: 1,
    ...props,
  };

  return render(
    <ReactFlowProvider>
      <EntityNode {...defaultProps} />
    </ReactFlowProvider>
  );
};

describe('EntityNode', () => {
  describe('rendering', () => {
    it('renders entity canonical name', () => {
      renderEntityNode({
        data: createMockNodeData({ canonicalName: 'John Doe' }),
      });

      // Use getAllByText since name appears in both node and tooltip
      expect(screen.getAllByText('John Doe').length).toBeGreaterThan(0);
    });

    it('truncates long names with ellipsis', () => {
      renderEntityNode({
        data: createMockNodeData({ canonicalName: 'Very Long Entity Name That Exceeds' }),
      });

      expect(screen.getByText('Very Long En...')).toBeInTheDocument();
    });

    it('displays entity type badge for PERSON', () => {
      renderEntityNode({
        data: createMockNodeData({ entityType: 'PERSON' }),
      });

      expect(screen.getByText('Person')).toBeInTheDocument();
    });

    it('displays entity type badge for ORG', () => {
      renderEntityNode({
        data: createMockNodeData({ entityType: 'ORG' }),
      });

      expect(screen.getByText('Org')).toBeInTheDocument();
    });

    it('displays entity type badge for INSTITUTION', () => {
      renderEntityNode({
        data: createMockNodeData({ entityType: 'INSTITUTION' }),
      });

      expect(screen.getByText('Institution')).toBeInTheDocument();
    });

    it('displays entity type badge for ASSET', () => {
      renderEntityNode({
        data: createMockNodeData({ entityType: 'ASSET' }),
      });

      expect(screen.getByText('Asset')).toBeInTheDocument();
    });
  });

  describe('visual states', () => {
    it('applies selected styles when isSelected is true', () => {
      const { container } = renderEntityNode({
        data: createMockNodeData({ isSelected: true }),
      });

      const nodeDiv = container.querySelector('[role="button"]');
      expect(nodeDiv).toHaveClass('ring-4', 'ring-primary', 'ring-offset-2');
    });

    it('applies connected styles when isConnected is true', () => {
      const { container } = renderEntityNode({
        data: createMockNodeData({ isConnected: true }),
      });

      const nodeDiv = container.querySelector('[role="button"]');
      expect(nodeDiv).toHaveClass('ring-2', 'ring-primary/50');
    });

    it('applies dimmed styles when isDimmed is true', () => {
      const { container } = renderEntityNode({
        data: createMockNodeData({ isDimmed: true }),
      });

      const nodeDiv = container.querySelector('[role="button"]');
      expect(nodeDiv).toHaveClass('opacity-30');
    });

    it('does not apply dimmed styles by default', () => {
      const { container } = renderEntityNode({
        data: createMockNodeData({ isDimmed: false }),
      });

      const nodeDiv = container.querySelector('[role="button"]');
      expect(nodeDiv).not.toHaveClass('opacity-30');
    });
  });

  describe('accessibility', () => {
    it('has role="button" for interaction', () => {
      renderEntityNode();

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('has tabIndex for keyboard navigation', () => {
      const { container } = renderEntityNode();

      const nodeDiv = container.querySelector('[role="button"]');
      expect(nodeDiv).toHaveAttribute('tabIndex', '0');
    });

    it('has aria-label with entity information', () => {
      renderEntityNode({
        data: createMockNodeData({
          canonicalName: 'John Doe',
          entityType: 'PERSON',
          mentionCount: 42,
        }),
      });

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute(
        'aria-label',
        'John Doe, Person, 42 mentions. Press Enter to select, F to focus.'
      );
    });

    it('has aria-pressed when selected', () => {
      renderEntityNode({
        data: createMockNodeData({ isSelected: true }),
      });

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('tooltip content', () => {
    it('shows full canonical name in tooltip', () => {
      renderEntityNode({
        data: createMockNodeData({ canonicalName: 'Full Entity Name' }),
      });

      const tooltipContent = screen.getByTestId('tooltip-content');
      expect(tooltipContent).toHaveTextContent('Full Entity Name');
    });

    it('shows mention count in tooltip', () => {
      renderEntityNode({
        data: createMockNodeData({ mentionCount: 127 }),
      });

      const tooltipContent = screen.getByTestId('tooltip-content');
      expect(tooltipContent).toHaveTextContent('127 mentions');
    });

    it('shows singular mention for count of 1', () => {
      renderEntityNode({
        data: createMockNodeData({ mentionCount: 1 }),
      });

      const tooltipContent = screen.getByTestId('tooltip-content');
      expect(tooltipContent).toHaveTextContent('1 mention');
      expect(tooltipContent).not.toHaveTextContent('1 mentions');
    });

    it('shows alias count when aliases exist', () => {
      renderEntityNode({
        data: createMockNodeData({ aliases: ['Alias 1', 'Alias 2', 'Alias 3'] }),
      });

      const tooltipContent = screen.getByTestId('tooltip-content');
      expect(tooltipContent).toHaveTextContent('3 aliases');
    });

    it('shows singular alias for count of 1', () => {
      renderEntityNode({
        data: createMockNodeData({ aliases: ['Alias 1'] }),
      });

      const tooltipContent = screen.getByTestId('tooltip-content');
      expect(tooltipContent).toHaveTextContent('1 alias');
      expect(tooltipContent).not.toHaveTextContent('1 aliases');
    });

    it('does not show alias count when no aliases', () => {
      renderEntityNode({
        data: createMockNodeData({ aliases: [] }),
      });

      const tooltipContent = screen.getByTestId('tooltip-content');
      expect(tooltipContent).not.toHaveTextContent('alias');
    });
  });
});

describe('calculateNodeSize', () => {
  // Note: The formula is: minSize + (maxSize - minSize) * Math.min(Math.log10(Math.max(count, 1) + 1) / 3, 1)
  // For 0 mentions: log10(2) ≈ 0.301, so size ≈ 60 + 60 * 0.100 ≈ 66

  it('returns near minimum size for 0 mentions', () => {
    const size = calculateNodeSize(0);
    expect(size).toBeGreaterThanOrEqual(60);
    expect(size).toBeLessThan(70);
  });

  it('returns near minimum size for 1 mention', () => {
    const size = calculateNodeSize(1);
    expect(size).toBeGreaterThanOrEqual(60);
    expect(size).toBeLessThan(75);
  });

  it('returns medium size for moderate mentions', () => {
    const size = calculateNodeSize(50);
    expect(size).toBeGreaterThan(70);
    expect(size).toBeLessThan(110);
  });

  it('approaches maximum size (120px) for high mentions', () => {
    const size = calculateNodeSize(1000);
    expect(size).toBeGreaterThan(110);
    expect(size).toBeLessThanOrEqual(120);
  });

  it('caps at maximum size for very high mentions', () => {
    const size1000 = calculateNodeSize(1000);
    const size10000 = calculateNodeSize(10000);
    // Should be capped, so difference should be minimal
    expect(size10000 - size1000).toBeLessThan(10);
  });

  it('handles negative values same as 0 mentions', () => {
    const sizeNegative = calculateNodeSize(-5);
    const sizeZero = calculateNodeSize(0);
    expect(sizeNegative).toBe(sizeZero);
  });

  it('scales logarithmically', () => {
    const size10 = calculateNodeSize(10);
    const size100 = calculateNodeSize(100);
    const size1000 = calculateNodeSize(1000);

    // The difference between 10->100 should be similar to 100->1000 (log scale)
    const diff1 = size100 - size10;
    const diff2 = size1000 - size100;
    expect(Math.abs(diff1 - diff2)).toBeLessThan(10);
  });
});
