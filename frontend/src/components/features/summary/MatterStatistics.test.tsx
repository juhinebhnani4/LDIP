import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MatterStatistics, MatterStatisticsSkeleton } from './MatterStatistics';
import type { MatterStats } from '@/types/summary';

const createMockStats = (overrides: Partial<MatterStats> = {}): MatterStats => ({
  totalPages: 156,
  entitiesFound: 24,
  eventsExtracted: 18,
  citationsFound: 42,
  verificationPercent: 67,
  ...overrides,
});

describe('MatterStatistics', () => {
  describe('rendering', () => {
    it('renders section heading', () => {
      const stats = createMockStats();
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByRole('heading', { name: 'Matter Statistics' })).toBeInTheDocument();
    });

    it('renders all four stat cards', () => {
      const stats = createMockStats();
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByText('Total Pages')).toBeInTheDocument();
      expect(screen.getByText('Entities Found')).toBeInTheDocument();
      expect(screen.getByText('Events Extracted')).toBeInTheDocument();
      expect(screen.getByText('Citations Found')).toBeInTheDocument();
    });

    it('displays correct counts', () => {
      const stats = createMockStats();
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByText('156')).toBeInTheDocument();
      expect(screen.getByText('24')).toBeInTheDocument();
      expect(screen.getByText('18')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('formats large numbers with locale', () => {
      const stats = createMockStats({ totalPages: 1234 });
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByText('1,234')).toBeInTheDocument();
    });

    it('handles zero values', () => {
      const stats = createMockStats({
        totalPages: 0,
        entitiesFound: 0,
        eventsExtracted: 0,
        citationsFound: 0,
      });
      render(<MatterStatistics stats={stats} />);

      const zeros = screen.getAllByText('0');
      expect(zeros).toHaveLength(4);
    });
  });

  describe('verification progress', () => {
    it('displays verification percentage', () => {
      const stats = createMockStats({ verificationPercent: 67 });
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByText('67%')).toBeInTheDocument();
    });

    it('displays progress bar', () => {
      const stats = createMockStats();
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByRole('progressbar', { name: /67% verification complete/i })).toBeInTheDocument();
    });

    it('shows appropriate message for low progress', () => {
      const stats = createMockStats({ verificationPercent: 50 });
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByText('Many items still need verification')).toBeInTheDocument();
    });

    it('shows appropriate message for medium progress', () => {
      const stats = createMockStats({ verificationPercent: 80 });
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByText('Good progress - some items need review')).toBeInTheDocument();
    });

    it('shows appropriate message for high progress', () => {
      const stats = createMockStats({ verificationPercent: 95 });
      render(<MatterStatistics stats={stats} />);

      expect(screen.getByText('Almost ready for export')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders blue icon for total pages', () => {
      const stats = createMockStats();
      const { container } = render(<MatterStatistics stats={stats} />);

      const blueIcon = container.querySelector('.text-blue-500');
      expect(blueIcon).toBeInTheDocument();
    });

    it('renders purple icon for entities', () => {
      const stats = createMockStats();
      const { container } = render(<MatterStatistics stats={stats} />);

      const purpleIcon = container.querySelector('.text-purple-500');
      expect(purpleIcon).toBeInTheDocument();
    });

    it('renders green icon for events', () => {
      const stats = createMockStats();
      const { container } = render(<MatterStatistics stats={stats} />);

      const greenIcon = container.querySelector('.text-green-500');
      expect(greenIcon).toBeInTheDocument();
    });

    it('renders orange icon for citations', () => {
      const stats = createMockStats();
      const { container } = render(<MatterStatistics stats={stats} />);

      const orangeIcon = container.querySelector('.text-orange-500');
      expect(orangeIcon).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible section with aria-labelledby', () => {
      const stats = createMockStats();
      const { container } = render(<MatterStatistics stats={stats} />);

      const section = container.querySelector('section[aria-labelledby="matter-stats-heading"]');
      expect(section).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const stats = createMockStats();
      const { container } = render(<MatterStatistics stats={stats} className="custom-class" />);

      const section = container.querySelector('section.custom-class');
      expect(section).toBeInTheDocument();
    });
  });
});

describe('MatterStatisticsSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<MatterStatisticsSkeleton />);

    const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders four stat card skeletons', () => {
    const { container } = render(<MatterStatisticsSkeleton />);

    const iconSkeletons = container.querySelectorAll('.size-12.rounded-lg');
    expect(iconSkeletons).toHaveLength(4);
  });

  it('applies className prop', () => {
    const { container } = render(<MatterStatisticsSkeleton className="custom-class" />);

    const section = container.firstChild;
    expect(section).toHaveClass('custom-class');
  });
});
