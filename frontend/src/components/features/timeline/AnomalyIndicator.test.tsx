/**
 * AnomalyIndicator Component Tests
 *
 * Tests for the AnomalyIndicator and AnomalyBadge components.
 *
 * Story 14.16: Anomalies UI Integration (AC #1)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AnomalyIndicator, AnomalyBadge } from './AnomalyIndicator';
import type { AnomalyListItem } from '@/hooks/useAnomalies';

// Mock tooltip components
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <span data-testid="tooltip-content">{children}</span>,
}));

const mockAnomalies: AnomalyListItem[] = [
  {
    id: 'anomaly-1',
    anomalyType: 'gap',
    severity: 'high',
    title: 'Unusual gap detected',
    explanation: 'A gap of 120 days was detected between events',
    eventIds: ['event-1', 'event-2'],
    gapDays: 120,
    confidence: 0.85,
    verified: false,
    dismissed: false,
    createdAt: '2024-01-15T10:00:00Z',
  },
  {
    id: 'anomaly-2',
    anomalyType: 'sequence_violation',
    severity: 'medium',
    title: 'Events out of order',
    explanation: 'Filing appeared before initial notice',
    eventIds: ['event-1', 'event-3'],
    gapDays: null,
    confidence: 0.75,
    verified: false,
    dismissed: false,
    createdAt: '2024-01-16T10:00:00Z',
  },
];

describe('AnomalyIndicator', () => {
  it('renders nothing when no anomalies provided', () => {
    const { container } = render(<AnomalyIndicator anomalies={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders indicator with anomaly count', () => {
    render(<AnomalyIndicator anomalies={mockAnomalies} />);
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('calls onClick with first anomaly when clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<AnomalyIndicator anomalies={mockAnomalies} onClick={onClick} />);

    await user.click(screen.getByRole('button'));

    expect(onClick).toHaveBeenCalledWith(mockAnomalies[0]);
  });

  it('shows highest severity icon color for critical', () => {
    const criticalAnomalies: AnomalyListItem[] = [
      { ...mockAnomalies[0], severity: 'critical' },
    ];
    const { container } = render(<AnomalyIndicator anomalies={criticalAnomalies} />);

    // Icon color is applied to the SVG element inside the button
    const svg = container.querySelector('svg');
    expect(svg?.className.baseVal).toContain('text-red');
  });

  it('shows medium severity icon color for medium', () => {
    const mediumAnomalies: AnomalyListItem[] = [
      { ...mockAnomalies[0], severity: 'medium' },
    ];
    const { container } = render(<AnomalyIndicator anomalies={mediumAnomalies} />);

    const svg = container.querySelector('svg');
    expect(svg?.className.baseVal).toContain('text-orange');
  });

  it('has accessible label', () => {
    render(<AnomalyIndicator anomalies={mockAnomalies} />);
    expect(screen.getByLabelText(/2 anomalies/i)).toBeInTheDocument();
  });

  describe('size variants', () => {
    it('renders small size correctly', () => {
      render(<AnomalyIndicator anomalies={mockAnomalies} size="sm" />);
      const button = screen.getByRole('button');
      // Small size uses compact styling
      expect(button).toBeInTheDocument();
    });

    it('renders medium size correctly', () => {
      render(<AnomalyIndicator anomalies={mockAnomalies} size="md" />);
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('renders large size correctly', () => {
      render(<AnomalyIndicator anomalies={mockAnomalies} size="lg" />);
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });
  });
});

describe('AnomalyBadge', () => {
  const highAnomalies: AnomalyListItem[] = [
    { ...mockAnomalies[0], severity: 'high' },
  ];

  const criticalAnomalies: AnomalyListItem[] = [
    { ...mockAnomalies[0], severity: 'critical' },
  ];

  const mediumAnomalies: AnomalyListItem[] = [
    { ...mockAnomalies[0], severity: 'medium' },
  ];

  const lowAnomalies: AnomalyListItem[] = [
    { ...mockAnomalies[0], severity: 'low' },
  ];

  it('renders nothing when no anomalies', () => {
    const { container } = render(<AnomalyBadge anomalies={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders badge with count', () => {
    render(<AnomalyBadge anomalies={mockAnomalies} />);
    expect(screen.getByText('2 Issues')).toBeInTheDocument();
  });

  it('applies correct styling for critical severity', () => {
    const { container } = render(<AnomalyBadge anomalies={criticalAnomalies} />);
    const badge = container.querySelector('.inline-flex');
    expect(badge?.className).toContain('text-red');
  });

  it('applies correct styling for high severity', () => {
    const { container } = render(<AnomalyBadge anomalies={highAnomalies} />);
    const badge = container.querySelector('.inline-flex');
    expect(badge?.className).toContain('text-red');
  });

  it('applies correct styling for medium severity', () => {
    const { container } = render(<AnomalyBadge anomalies={mediumAnomalies} />);
    const badge = container.querySelector('.inline-flex');
    expect(badge?.className).toContain('text-orange');
  });

  it('applies correct styling for low severity', () => {
    const { container } = render(<AnomalyBadge anomalies={lowAnomalies} />);
    const badge = container.querySelector('.inline-flex');
    expect(badge?.className).toContain('text-yellow');
  });

  it('calls onClick with first anomaly when clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<AnomalyBadge anomalies={mockAnomalies} onClick={onClick} />);

    await user.click(screen.getByText('2 Issues'));

    expect(onClick).toHaveBeenCalledWith(mockAnomalies[0]);
  });
});
