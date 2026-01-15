import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PartiesSection, PartiesSectionSkeleton } from './PartiesSection';
import type { PartyInfo } from '@/types/summary';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

const createMockParties = (overrides: Partial<PartyInfo>[] = []): PartyInfo[] => [
  {
    entityId: 'petitioner-1',
    entityName: 'John Doe',
    role: 'petitioner',
    sourceDocument: 'Petition.pdf',
    sourcePage: 1,
    isVerified: false,
    ...overrides[0],
  },
  {
    entityId: 'respondent-1',
    entityName: 'State Authority',
    role: 'respondent',
    sourceDocument: 'Petition.pdf',
    sourcePage: 2,
    isVerified: true,
    ...overrides[1],
  },
];

describe('PartiesSection', () => {
  describe('rendering', () => {
    it('renders section heading', () => {
      const parties = createMockParties();
      render(<PartiesSection parties={parties} />);

      expect(screen.getByRole('heading', { name: 'Parties' })).toBeInTheDocument();
    });

    it('renders petitioner card with entity name', () => {
      const parties = createMockParties();
      render(<PartiesSection parties={parties} />);

      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Petitioner')).toBeInTheDocument();
    });

    it('renders respondent card with entity name', () => {
      const parties = createMockParties();
      render(<PartiesSection parties={parties} />);

      expect(screen.getByText('State Authority')).toBeInTheDocument();
      expect(screen.getByText('Respondent')).toBeInTheDocument();
    });

    it('shows source document and page number', () => {
      const parties = createMockParties();
      render(<PartiesSection parties={parties} />);

      expect(screen.getByText('Petition.pdf, p. 1')).toBeInTheDocument();
      expect(screen.getByText('Petition.pdf, p. 2')).toBeInTheDocument();
    });

    it('shows empty state when no parties', () => {
      render(<PartiesSection parties={[]} />);

      expect(screen.getByText('No parties have been identified yet.')).toBeInTheDocument();
    });
  });

  describe('verification status', () => {
    it('shows no verification badge for unverified party', () => {
      const parties = createMockParties([{ isVerified: false }, { isVerified: false }]);
      render(<PartiesSection parties={parties} />);

      // When not verified, no badge is shown until user takes action
      expect(screen.queryByText('Verified')).not.toBeInTheDocument();
      expect(screen.queryByText('Flagged')).not.toBeInTheDocument();
    });

    it('shows Verified badge for verified party', () => {
      const parties = createMockParties([{ isVerified: false }, { isVerified: true }]);
      render(<PartiesSection parties={parties} />);

      expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('has inline verification buttons for each party', () => {
      const parties = createMockParties([{ isVerified: false }, { isVerified: false }]);
      render(<PartiesSection parties={parties} />);

      // Each party should have verification buttons (2 parties * 3 buttons = 6)
      const verifyButtons = screen.getAllByRole('button', { name: /verify this section/i });
      expect(verifyButtons).toHaveLength(2);
    });
  });

  describe('navigation', () => {
    it('has View Entity button linking to entities tab with entityId', () => {
      const parties = createMockParties();
      render(<PartiesSection parties={parties} />);

      const viewEntityLinks = screen.getAllByRole('link', { name: /View Entity/i });
      expect(viewEntityLinks[0]).toHaveAttribute(
        'href',
        '/matters/test-matter-id/entities?entityId=petitioner-1'
      );
    });

    it('has View Source link for each party with correct href', () => {
      const parties = createMockParties();
      render(<PartiesSection parties={parties} />);

      const viewSourceLinks = screen.getAllByRole('link', { name: /View Source/i });
      expect(viewSourceLinks).toHaveLength(2);
      expect(viewSourceLinks[0]).toHaveAttribute(
        'href',
        '/matters/test-matter-id/documents?doc=Petition.pdf&page=1'
      );
      expect(viewSourceLinks[1]).toHaveAttribute(
        'href',
        '/matters/test-matter-id/documents?doc=Petition.pdf&page=2'
      );
    });

    it('View Source links have accessible aria-labels', () => {
      const parties = createMockParties();
      render(<PartiesSection parties={parties} />);

      const viewSourceLink = screen.getByRole('link', {
        name: 'View source: Petition.pdf, page 1',
      });
      expect(viewSourceLink).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible section with aria-labelledby', () => {
      const parties = createMockParties();
      const { container } = render(<PartiesSection parties={parties} />);

      const section = container.querySelector('section[aria-labelledby="parties-heading"]');
      expect(section).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const parties = createMockParties();
      const { container } = render(<PartiesSection parties={parties} className="custom-class" />);

      const section = container.querySelector('section.custom-class');
      expect(section).toBeInTheDocument();
    });
  });
});

describe('PartiesSectionSkeleton', () => {
  it('renders skeleton cards', () => {
    const { container } = render(<PartiesSectionSkeleton />);

    // Should have skeleton elements
    const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('applies className prop', () => {
    const { container } = render(<PartiesSectionSkeleton className="custom-class" />);

    const section = container.firstChild;
    expect(section).toHaveClass('custom-class');
  });
});
