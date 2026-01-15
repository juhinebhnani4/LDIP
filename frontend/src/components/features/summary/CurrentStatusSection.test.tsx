import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CurrentStatusSection, CurrentStatusSectionSkeleton } from './CurrentStatusSection';
import type { CurrentStatus } from '@/types/summary';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

const createMockStatus = (overrides: Partial<CurrentStatus> = {}): CurrentStatus => ({
  lastOrderDate: '2024-01-15T00:00:00.000Z',
  description: 'Matter adjourned for hearing. Respondent directed to file reply.',
  sourceDocument: 'Order_2024_01.pdf',
  sourcePage: 1,
  isVerified: false,
  ...overrides,
});

describe('CurrentStatusSection', () => {
  describe('rendering', () => {
    it('renders section heading', () => {
      const status = createMockStatus();
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByRole('heading', { name: 'Current Status' })).toBeInTheDocument();
    });

    it('displays formatted last order date', () => {
      const status = createMockStatus({ lastOrderDate: '2024-01-15T00:00:00.000Z' });
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByText(/Last Order:.*15 January 2024/)).toBeInTheDocument();
    });

    it('displays the description', () => {
      const status = createMockStatus();
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByText(/Matter adjourned for hearing/)).toBeInTheDocument();
    });

    it('displays source document and page', () => {
      const status = createMockStatus();
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByText(/Source:.*Order_2024_01\.pdf.*p\. 1/)).toBeInTheDocument();
    });
  });

  describe('verification status', () => {
    it('shows Pending Verification badge when not verified', () => {
      const status = createMockStatus({ isVerified: false });
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByText('Pending Verification')).toBeInTheDocument();
    });

    it('shows Verified badge when verified', () => {
      const status = createMockStatus({ isVerified: true });
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('shows Verify button when not verified', () => {
      const status = createMockStatus({ isVerified: false });
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByRole('button', { name: /Verify/i })).toBeInTheDocument();
    });

    it('hides Verify button when verified', () => {
      const status = createMockStatus({ isVerified: true });
      render(<CurrentStatusSection currentStatus={status} />);

      // Should not have Verify button
      expect(screen.queryByRole('button', { name: /^Verify$/i })).not.toBeInTheDocument();
    });
  });

  describe('actions', () => {
    it('has View Full Order link with correct href', () => {
      const status = createMockStatus();
      render(<CurrentStatusSection currentStatus={status} />);

      const viewOrderLink = screen.getByRole('link', { name: /View Full Order/i });
      expect(viewOrderLink).toBeInTheDocument();
      expect(viewOrderLink).toHaveAttribute(
        'href',
        '/matters/test-matter-id/documents?doc=Order_2024_01.pdf&page=1'
      );
    });

    it('View Full Order link has accessible aria-label', () => {
      const status = createMockStatus();
      render(<CurrentStatusSection currentStatus={status} />);

      const viewOrderLink = screen.getByRole('link', {
        name: 'View full order: Order_2024_01.pdf, page 1',
      });
      expect(viewOrderLink).toBeInTheDocument();
    });
  });

  describe('date formatting', () => {
    it('handles invalid date gracefully', () => {
      const status = createMockStatus({ lastOrderDate: 'invalid-date' });
      render(<CurrentStatusSection currentStatus={status} />);

      expect(screen.getByText(/Last Order:.*Unknown date/)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible section with aria-labelledby', () => {
      const status = createMockStatus();
      const { container } = render(<CurrentStatusSection currentStatus={status} />);

      const section = container.querySelector('section[aria-labelledby="current-status-heading"]');
      expect(section).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const status = createMockStatus();
      const { container } = render(<CurrentStatusSection currentStatus={status} className="custom-class" />);

      const section = container.querySelector('section.custom-class');
      expect(section).toBeInTheDocument();
    });
  });
});

describe('CurrentStatusSectionSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<CurrentStatusSectionSkeleton />);

    const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('applies className prop', () => {
    const { container } = render(<CurrentStatusSectionSkeleton className="custom-class" />);

    const section = container.firstChild;
    expect(section).toHaveClass('custom-class');
  });
});
