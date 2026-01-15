import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SubjectMatterSection, SubjectMatterSectionSkeleton } from './SubjectMatterSection';
import type { SubjectMatter } from '@/types/summary';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ matterId: 'test-matter-id' }),
}));

const createMockSubjectMatter = (overrides: Partial<SubjectMatter> = {}): SubjectMatter => ({
  description: 'This matter concerns an RTI application seeking disclosure of records.',
  sources: [
    { documentName: 'Petition.pdf', pageRange: '1-3' },
    { documentName: 'Application.pdf', pageRange: '1-2' },
  ],
  isVerified: false,
  ...overrides,
});

describe('SubjectMatterSection', () => {
  describe('rendering', () => {
    it('renders section heading', () => {
      const subjectMatter = createMockSubjectMatter();
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.getByRole('heading', { name: 'Subject Matter' })).toBeInTheDocument();
    });

    it('renders Case Overview title', () => {
      const subjectMatter = createMockSubjectMatter();
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.getByText('Case Overview')).toBeInTheDocument();
    });

    it('displays the description', () => {
      const subjectMatter = createMockSubjectMatter();
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.getByText(/This matter concerns an RTI application/)).toBeInTheDocument();
    });

    it('displays source citations as links', () => {
      const subjectMatter = createMockSubjectMatter();
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.getByText('Sources:')).toBeInTheDocument();
      expect(screen.getByText(/Petition\.pdf.*pp\. 1-3/)).toBeInTheDocument();
      expect(screen.getByText(/Application\.pdf.*pp\. 1-2/)).toBeInTheDocument();

      // Verify sources are navigable links
      const sourceLinks = screen.getAllByRole('link', { name: /View source:/i });
      expect(sourceLinks).toHaveLength(2);
      expect(sourceLinks[0]).toHaveAttribute(
        'href',
        '/matters/test-matter-id/documents?doc=Petition.pdf&pages=1-3'
      );
    });

    it('handles empty sources array', () => {
      const subjectMatter = createMockSubjectMatter({ sources: [] });
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.queryByText('Sources:')).not.toBeInTheDocument();
    });
  });

  describe('verification status', () => {
    it('shows Pending Verification badge when not verified', () => {
      const subjectMatter = createMockSubjectMatter({ isVerified: false });
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.getByText('Pending Verification')).toBeInTheDocument();
    });

    it('shows Verified badge when verified', () => {
      const subjectMatter = createMockSubjectMatter({ isVerified: true });
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('shows Verify button when not verified', () => {
      const subjectMatter = createMockSubjectMatter({ isVerified: false });
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.getByRole('button', { name: /Verify/i })).toBeInTheDocument();
    });

    it('hides Verify button when verified', () => {
      const subjectMatter = createMockSubjectMatter({ isVerified: true });
      render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      expect(screen.queryByRole('button', { name: /^Verify$/i })).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible section with aria-labelledby', () => {
      const subjectMatter = createMockSubjectMatter();
      const { container } = render(<SubjectMatterSection subjectMatter={subjectMatter} />);

      const section = container.querySelector('section[aria-labelledby="subject-matter-heading"]');
      expect(section).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const subjectMatter = createMockSubjectMatter();
      const { container } = render(<SubjectMatterSection subjectMatter={subjectMatter} className="custom-class" />);

      const section = container.querySelector('section.custom-class');
      expect(section).toBeInTheDocument();
    });
  });
});

describe('SubjectMatterSectionSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<SubjectMatterSectionSkeleton />);

    const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('applies className prop', () => {
    const { container } = render(<SubjectMatterSectionSkeleton className="custom-class" />);

    const section = container.firstChild;
    expect(section).toHaveClass('custom-class');
  });
});
