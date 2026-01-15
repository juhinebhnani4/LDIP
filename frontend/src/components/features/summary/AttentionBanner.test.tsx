import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AttentionBanner, AttentionBannerSkeleton } from './AttentionBanner';
import type { AttentionItem } from '@/types/summary';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

const createMockItems = (overrides: Partial<AttentionItem>[] = []): AttentionItem[] => [
  {
    type: 'contradiction',
    count: 3,
    label: 'contradictions detected',
    targetTab: 'verification',
    ...overrides[0],
  },
  {
    type: 'citation_issue',
    count: 2,
    label: 'citations need verification',
    targetTab: 'citations',
    ...overrides[1],
  },
];

describe('AttentionBanner', () => {
  describe('rendering', () => {
    it('renders nothing when no attention items', () => {
      const { container } = render(<AttentionBanner items={[]} />);
      expect(container).toBeEmptyDOMElement();
    });

    it('renders nothing when items is undefined', () => {
      const { container } = render(<AttentionBanner items={undefined as unknown as AttentionItem[]} />);
      expect(container).toBeEmptyDOMElement();
    });

    it('renders alert with correct total count', () => {
      const items = createMockItems();
      render(<AttentionBanner items={items} />);

      expect(screen.getByText('5 items need attention')).toBeInTheDocument();
    });

    it('uses singular form for single item', () => {
      const items: AttentionItem[] = [
        { type: 'contradiction', count: 1, label: 'contradiction detected', targetTab: 'verification' },
      ];
      render(<AttentionBanner items={items} />);

      expect(screen.getByText('1 item needs attention')).toBeInTheDocument();
    });

    it('displays each attention item with count and label', () => {
      const items = createMockItems();
      render(<AttentionBanner items={items} />);

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('contradictions detected')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('citations need verification')).toBeInTheDocument();
    });

    it('renders Review All button', () => {
      const items = createMockItems();
      render(<AttentionBanner items={items} />);

      expect(screen.getByRole('link', { name: 'Review All' })).toBeInTheDocument();
    });
  });

  describe('navigation links', () => {
    it('Review All links to verification tab', () => {
      const items = createMockItems();
      render(<AttentionBanner items={items} />);

      const reviewLink = screen.getByRole('link', { name: 'Review All' });
      expect(reviewLink).toHaveAttribute('href', '/matters/test-matter-id/verification');
    });

    it('each item links to its target tab', () => {
      const items = createMockItems();
      render(<AttentionBanner items={items} />);

      // Find the specific links by their accessible names
      const contradictionLink = screen.getByRole('link', {
        name: /3 contradictions detected/i,
      });
      const citationLink = screen.getByRole('link', {
        name: /2 citations need verification/i,
      });

      expect(contradictionLink).toHaveAttribute('href', '/matters/test-matter-id/verification');
      expect(citationLink).toHaveAttribute('href', '/matters/test-matter-id/citations');
    });
  });

  describe('accessibility', () => {
    it('has accessible labels on attention items', () => {
      const items = createMockItems();
      render(<AttentionBanner items={items} />);

      const contradictionLink = screen.getByRole('link', {
        name: /3 contradictions detected.*Click to review in verification tab/i,
      });
      expect(contradictionLink).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const items = createMockItems();
      const { container } = render(<AttentionBanner items={items} className="custom-class" />);

      const alert = container.querySelector('.custom-class');
      expect(alert).toBeInTheDocument();
    });
  });
});

describe('AttentionBannerSkeleton', () => {
  it('renders skeleton element', () => {
    const { container } = render(<AttentionBannerSkeleton />);

    const skeleton = container.querySelector('.animate-pulse');
    expect(skeleton).toBeInTheDocument();
  });

  it('applies className prop', () => {
    const { container } = render(<AttentionBannerSkeleton className="custom-class" />);

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('custom-class');
  });
});
