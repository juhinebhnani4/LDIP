import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import { EntityEdge, getEdgeStyle, type EntityEdgeProps } from './EntityEdge';
import { Position } from '@xyflow/react';

const createMockEdgeProps = (
  overrides: Partial<EntityEdgeProps> = {}
): EntityEdgeProps => ({
  id: 'edge-1',
  source: 'node-1',
  target: 'node-2',
  sourceX: 0,
  sourceY: 0,
  targetX: 100,
  targetY: 100,
  sourcePosition: Position.Bottom,
  targetPosition: Position.Top,
  selected: false,
  data: {
    relationshipType: 'RELATED_TO',
    confidence: 0.85,
    metadata: {},
  },
  ...overrides,
});

// Note: Portal container creation function removed as ReactFlow handles portal setup internally

const renderEntityEdge = (props: Partial<EntityEdgeProps> = {}) => {
  const edgeProps = createMockEdgeProps(props);

  return render(
    <ReactFlowProvider>
      <svg width={200} height={200}>
        <EntityEdge {...edgeProps} />
      </svg>
    </ReactFlowProvider>
  );
};

describe('EntityEdge', () => {
  describe('rendering', () => {
    it('renders edge path', () => {
      const { container } = renderEntityEdge();

      // BaseEdge renders a path element
      const paths = container.querySelectorAll('path');
      expect(paths.length).toBeGreaterThan(0);
    });

    // Note: EdgeLabelRenderer renders labels to a portal outside the SVG.
    // In unit tests without a full ReactFlow setup, labels may not be rendered.
    // The label logic is tested via the getEdgeStyle helper function instead.

    it('uses correct relationship config for RELATED_TO', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'RELATED_TO',
          confidence: 0.9,
          metadata: {},
        },
      });

      // Verify the edge path exists with correct color
      const paths = container.querySelectorAll('path');
      const edgePath = Array.from(paths).find(
        (p) => p.getAttribute('id') === 'edge-1'
      );
      expect(edgePath).toBeInTheDocument();
      // Color should be green (#10b981) for RELATED_TO
      expect(edgePath?.getAttribute('style')).toContain('#10b981');
    });

    it('uses correct relationship config for ALIAS_OF', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'ALIAS_OF',
          confidence: 0.95,
          metadata: {},
        },
      });

      // Verify the edge path exists with correct color
      const paths = container.querySelectorAll('path');
      const edgePath = Array.from(paths).find(
        (p) => p.getAttribute('id') === 'edge-1'
      );
      expect(edgePath).toBeInTheDocument();
      // Color should be gray (#6b7280) for ALIAS_OF
      expect(edgePath?.getAttribute('style')).toContain('#6b7280');
    });

    it('uses correct relationship config for HAS_ROLE', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'HAS_ROLE',
          confidence: 0.8,
          metadata: {},
        },
      });

      // Verify the edge path exists with correct color
      const paths = container.querySelectorAll('path');
      const edgePath = Array.from(paths).find(
        (p) => p.getAttribute('id') === 'edge-1'
      );
      expect(edgePath).toBeInTheDocument();
      // Color should be blue (#3b82f6) for HAS_ROLE
      expect(edgePath?.getAttribute('style')).toContain('#3b82f6');
    });

    it('defaults to RELATED_TO style when no data provided', () => {
      const { container } = renderEntityEdge({ data: undefined });

      const paths = container.querySelectorAll('path');
      const edgePath = Array.from(paths).find(
        (p) => p.getAttribute('id') === 'edge-1'
      );
      expect(edgePath).toBeInTheDocument();
      // Default to green (#10b981) for RELATED_TO
      expect(edgePath?.getAttribute('style')).toContain('#10b981');
    });
  });

  describe('styling', () => {
    it('applies dashed style for ALIAS_OF relationship', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'ALIAS_OF',
          confidence: 0.9,
          metadata: {},
        },
      });

      // Find the main edge path with dashed style
      const paths = container.querySelectorAll('path');
      const edgePath = Array.from(paths).find(
        (p) => p.getAttribute('id') === 'edge-1'
      );
      expect(edgePath).toBeInTheDocument();
      // ALIAS_OF should have dashed stroke
      expect(edgePath?.getAttribute('style')).toContain('stroke-dasharray: 5 5');
    });

    it('applies solid style for HAS_ROLE relationship', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'HAS_ROLE',
          confidence: 0.9,
          metadata: {},
        },
      });

      // Find the main edge path
      const paths = container.querySelectorAll('path');
      const edgePath = Array.from(paths).find(
        (p) => p.getAttribute('id') === 'edge-1'
      );
      expect(edgePath).toBeInTheDocument();
      // HAS_ROLE should NOT have dashed stroke
      expect(edgePath?.getAttribute('style')).not.toContain('stroke-dasharray');
    });

    it('applies solid style for RELATED_TO relationship', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'RELATED_TO',
          confidence: 0.9,
          metadata: {},
        },
      });

      const paths = container.querySelectorAll('path');
      const edgePath = Array.from(paths).find(
        (p) => p.getAttribute('id') === 'edge-1'
      );
      expect(edgePath).toBeInTheDocument();
      // RELATED_TO should NOT have dashed stroke
      expect(edgePath?.getAttribute('style')).not.toContain('stroke-dasharray');
    });
  });

  describe('hover behavior', () => {
    it('renders hover detection path', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'RELATED_TO',
          confidence: 0.85,
          metadata: {},
        },
      });

      // Find the transparent hover detection path
      const hoverPath = container.querySelector(
        'path[stroke="transparent"]'
      ) as SVGPathElement;

      expect(hoverPath).toBeInTheDocument();
      expect(hoverPath.getAttribute('stroke-width')).toBe('20');
    });

    it('increases stroke width on hover', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'RELATED_TO',
          confidence: 0.85,
          metadata: {},
        },
      });

      const hoverPath = container.querySelector(
        'path[stroke="transparent"]'
      ) as SVGPathElement;

      // Before hover - stroke-width should be 2
      const edgePath = container.querySelector('path#edge-1') as SVGPathElement;
      expect(edgePath?.getAttribute('style')).toContain('stroke-width: 2');

      // Trigger hover
      fireEvent.mouseEnter(hoverPath);

      // After hover - stroke-width should be 3
      expect(edgePath?.getAttribute('style')).toContain('stroke-width: 3');
    });

    it('increases stroke width when selected', () => {
      const { container } = renderEntityEdge({
        selected: true,
        data: {
          relationshipType: 'RELATED_TO',
          confidence: 0.92,
          metadata: {},
        },
      });

      const edgePath = container.querySelector('path#edge-1') as SVGPathElement;
      // Selected edges should have stroke-width: 3
      expect(edgePath?.getAttribute('style')).toContain('stroke-width: 3');
    });

    it('resets stroke width on mouse leave', () => {
      const { container } = renderEntityEdge({
        data: {
          relationshipType: 'RELATED_TO',
          confidence: 0.85,
          metadata: {},
        },
      });

      const hoverPath = container.querySelector(
        'path[stroke="transparent"]'
      ) as SVGPathElement;
      const edgePath = container.querySelector('path#edge-1') as SVGPathElement;

      // Hover
      fireEvent.mouseEnter(hoverPath);
      expect(edgePath?.getAttribute('style')).toContain('stroke-width: 3');

      // Leave
      fireEvent.mouseLeave(hoverPath);
      expect(edgePath?.getAttribute('style')).toContain('stroke-width: 2');
    });
  });
});

describe('getEdgeStyle', () => {
  it('returns dashed style for ALIAS_OF', () => {
    const style = getEdgeStyle('ALIAS_OF');

    expect(style.strokeDasharray).toBe('5 5');
    expect(style.stroke).toBe('#6b7280');
  });

  it('returns solid style for HAS_ROLE', () => {
    const style = getEdgeStyle('HAS_ROLE');

    expect(style.strokeDasharray).toBeUndefined();
    expect(style.stroke).toBe('#3b82f6');
  });

  it('returns solid style for RELATED_TO', () => {
    const style = getEdgeStyle('RELATED_TO');

    expect(style.strokeDasharray).toBeUndefined();
    expect(style.stroke).toBe('#10b981');
  });
});
