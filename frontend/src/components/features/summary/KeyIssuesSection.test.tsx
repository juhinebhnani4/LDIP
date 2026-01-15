import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KeyIssuesSection, KeyIssuesSectionSkeleton } from './KeyIssuesSection';
import type { KeyIssue } from '@/types/summary';

const createMockIssues = (overrides: Partial<KeyIssue>[] = []): KeyIssue[] => [
  {
    id: 'issue-1',
    number: 1,
    title: 'Whether the documents fall under exempted categories?',
    verificationStatus: 'verified',
    ...overrides[0],
  },
  {
    id: 'issue-2',
    number: 2,
    title: 'Whether partial disclosure is warranted?',
    verificationStatus: 'pending',
    ...overrides[1],
  },
  {
    id: 'issue-3',
    number: 3,
    title: 'Whether there was unreasonable delay?',
    verificationStatus: 'flagged',
    ...overrides[2],
  },
];

describe('KeyIssuesSection', () => {
  describe('rendering', () => {
    it('renders section heading', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByRole('heading', { name: 'Key Issues' })).toBeInTheDocument();
    });

    it('displays total issue count', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('3 Issues Identified')).toBeInTheDocument();
    });

    it('displays each issue with number and title', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText(/Whether the documents fall under exempted categories/)).toBeInTheDocument();
      expect(screen.getByText(/Whether partial disclosure is warranted/)).toBeInTheDocument();
      expect(screen.getByText(/Whether there was unreasonable delay/)).toBeInTheDocument();
    });

    it('shows empty state when no issues', () => {
      render(<KeyIssuesSection keyIssues={[]} />);

      expect(screen.getByText('No key issues have been identified yet.')).toBeInTheDocument();
    });
  });

  describe('verification status badges', () => {
    it('shows Verified badge for verified issues', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('shows Pending badge for pending issues', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    it('shows Flagged badge for flagged issues', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('Flagged')).toBeInTheDocument();
    });
  });

  describe('status summary', () => {
    it('displays verified count', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('1 verified')).toBeInTheDocument();
    });

    it('displays pending count', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('1 pending')).toBeInTheDocument();
    });

    it('displays flagged count', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.getByText('1 flagged')).toBeInTheDocument();
    });

    it('hides zero count categories', () => {
      const issues: KeyIssue[] = [
        { id: '1', number: 1, title: 'Issue 1', verificationStatus: 'verified' },
        { id: '2', number: 2, title: 'Issue 2', verificationStatus: 'verified' },
      ];
      render(<KeyIssuesSection keyIssues={issues} />);

      expect(screen.queryByText(/pending/)).not.toBeInTheDocument();
      expect(screen.queryByText(/flagged/)).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible section with aria-labelledby', () => {
      const issues = createMockIssues();
      const { container } = render(<KeyIssuesSection keyIssues={issues} />);

      const section = container.querySelector('section[aria-labelledby="key-issues-heading"]');
      expect(section).toBeInTheDocument();
    });

    it('has ordered list with aria-label', () => {
      const issues = createMockIssues();
      render(<KeyIssuesSection keyIssues={issues} />);

      const list = screen.getByRole('list', { name: 'Key issues list' });
      expect(list).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies className prop', () => {
      const issues = createMockIssues();
      const { container } = render(<KeyIssuesSection keyIssues={issues} className="custom-class" />);

      const section = container.querySelector('section.custom-class');
      expect(section).toBeInTheDocument();
    });
  });
});

describe('KeyIssuesSectionSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<KeyIssuesSectionSkeleton />);

    const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders three skeleton issue items', () => {
    const { container } = render(<KeyIssuesSectionSkeleton />);

    const roundedSkeletons = container.querySelectorAll('.rounded-full');
    expect(roundedSkeletons).toHaveLength(3);
  });

  it('applies className prop', () => {
    const { container } = render(<KeyIssuesSectionSkeleton className="custom-class" />);

    const section = container.firstChild;
    expect(section).toHaveClass('custom-class');
  });
});
