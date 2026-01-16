/**
 * Tests for EngineTrace Component
 *
 * Story 11.3: Streaming Response with Engine Trace
 * Task 12: Write comprehensive tests (AC: #2-3)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { EngineTrace } from '../EngineTrace';
import type { EngineTraceData } from '@/hooks/useSSE';

const mockTraces: EngineTraceData[] = [
  {
    engine: 'citation',
    executionTimeMs: 150,
    findingsCount: 3,
    success: true,
  },
  {
    engine: 'rag',
    executionTimeMs: 200,
    findingsCount: 10,
    success: true,
  },
];

describe('EngineTrace', () => {
  it('does not render when traces is empty', () => {
    const { container } = render(
      <EngineTrace traces={[]} totalTimeMs={0} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('displays summary with total time and engine count', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    expect(screen.getByText('350ms')).toBeInTheDocument();
    expect(screen.getByText('2 engines')).toBeInTheDocument();
  });

  it('displays total findings count', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    expect(screen.getByText('13 findings')).toBeInTheDocument();
  });

  it('expands to show engine details when clicked', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    // Click to expand
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    // Should show engine names
    expect(screen.getByText('Citation Verification')).toBeInTheDocument();
    expect(screen.getByText('Document Search')).toBeInTheDocument();
  });

  it('shows engine execution times in expanded view', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    // Click to expand
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    // Should show individual times
    expect(screen.getByText('150ms')).toBeInTheDocument();
    expect(screen.getByText('200ms')).toBeInTheDocument();
  });

  it('shows success indicators for successful engines', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    // Click to expand
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    // Should show success indicator (checkmark icons)
    const successIcons = screen.getAllByLabelText('Success');
    expect(successIcons).toHaveLength(2);
  });

  it('shows failure indicator for failed engine', () => {
    const tracesWithFailure: EngineTraceData[] = [
      {
        engine: 'citation',
        executionTimeMs: 150,
        findingsCount: 0,
        success: false,
        error: 'Connection timeout',
      },
    ];

    render(
      <EngineTrace traces={tracesWithFailure} totalTimeMs={150} />
    );

    // Click to expand
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);

    // Should show failure indicator
    expect(screen.getByLabelText('Failed')).toBeInTheDocument();
  });

  it('collapses when clicked again', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    const trigger = screen.getByRole('button');

    // Expand
    fireEvent.click(trigger);
    expect(screen.getByText('Citation Verification')).toBeInTheDocument();

    // Collapse
    fireEvent.click(trigger);

    // Engine details should be hidden (but element may still be in DOM due to animation)
    // Check aria-expanded instead
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('has correct accessibility attributes', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    const trigger = screen.getByRole('button');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('has correct test id', () => {
    render(
      <EngineTrace traces={mockTraces} totalTimeMs={350} />
    );

    expect(screen.getByTestId('engine-trace')).toBeInTheDocument();
  });

  it('displays singular "engine" when only one trace', () => {
    render(
      <EngineTrace
        traces={[mockTraces[0]!]}
        totalTimeMs={150}
      />
    );

    expect(screen.getByText('1 engine')).toBeInTheDocument();
  });
});
