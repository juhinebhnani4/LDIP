/**
 * CitationsByActView Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CitationsByActView } from './CitationsByActView';
import type { CitationListItem, CitationSummaryItem } from '@/types/citation';

const mockCitations: CitationListItem[] = [
  {
    id: 'cit-1',
    actName: 'Securities Act, 1992',
    sectionNumber: '3',
    subsection: '3',
    clause: null,
    rawCitationText: 'Section 3(3) of the Securities Act',
    sourcePage: 45,
    verificationStatus: 'verified',
    confidence: 95.0,
    documentId: 'doc-1',
    documentName: 'Petition.pdf',
  },
  {
    id: 'cit-2',
    actName: 'Securities Act, 1992',
    sectionNumber: '15',
    subsection: null,
    clause: null,
    rawCitationText: 'Section 15 of the Securities Act',
    sourcePage: 50,
    verificationStatus: 'mismatch',
    confidence: 78.0,
    documentId: 'doc-1',
    documentName: 'Petition.pdf',
  },
  {
    id: 'cit-3',
    actName: 'Negotiable Instruments Act, 1881',
    sectionNumber: '138',
    subsection: null,
    clause: null,
    rawCitationText: 'Section 138 of the NI Act',
    sourcePage: 12,
    verificationStatus: 'pending',
    confidence: 90.0,
    documentId: 'doc-2',
    documentName: 'Reply.pdf',
  },
];

const mockSummary: CitationSummaryItem[] = [
  { actName: 'Securities Act, 1992', citationCount: 2, verifiedCount: 1, pendingCount: 0 },
  { actName: 'Negotiable Instruments Act, 1881', citationCount: 1, verifiedCount: 0, pendingCount: 1 },
];

describe('CitationsByActView', () => {
  const defaultProps = {
    citations: mockCitations,
    summary: mockSummary,
  };

  it('renders Act groups as collapsible sections', () => {
    render(<CitationsByActView {...defaultProps} />);

    expect(screen.getByText('Securities Act, 1992')).toBeInTheDocument();
    expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();
  });

  it('shows citation count for each Act', () => {
    render(<CitationsByActView {...defaultProps} />);

    expect(screen.getByText(/2 citations? in 2 sections?/)).toBeInTheDocument();
    expect(screen.getByText(/1 citation in 1 section/)).toBeInTheDocument();
  });

  it('shows verified/pending counts from summary', () => {
    render(<CitationsByActView {...defaultProps} />);

    expect(screen.getByText('1 verified')).toBeInTheDocument();
    expect(screen.getByText('1 pending')).toBeInTheDocument();
  });

  it('shows Issues badge for Acts with problematic citations', () => {
    render(<CitationsByActView {...defaultProps} />);

    // Securities Act has a mismatch citation
    const issuesBadges = screen.getAllByText('Issues');
    expect(issuesBadges.length).toBeGreaterThan(0);
  });

  it('expands Act on click to show sections', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    // Click on Securities Act to expand
    await user.click(screen.getByText('Securities Act, 1992'));

    // Should show section breakdown
    expect(screen.getByText('Section 3.3')).toBeInTheDocument();
    expect(screen.getByText('Section 15')).toBeInTheDocument();
  });

  it('collapses Act on second click', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    // Click to expand
    await user.click(screen.getByText('Securities Act, 1992'));
    expect(screen.getByText('Section 3.3')).toBeInTheDocument();

    // Click to collapse
    await user.click(screen.getByText('Securities Act, 1992'));

    // Section should be removed from DOM or hidden after collapse
    await vi.waitFor(() => {
      const section = screen.queryByText('Section 3.3');
      expect(section === null || !section.checkVisibility()).toBeTruthy();
    });
  });

  it('shows citation text within section', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    await user.click(screen.getByText('Securities Act, 1992'));

    expect(screen.getByText('Section 3(3) of the Securities Act')).toBeInTheDocument();
  });

  it('shows page number for citations', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    await user.click(screen.getByText('Securities Act, 1992'));

    expect(screen.getByText('p.45')).toBeInTheDocument();
  });

  it('shows View button for each citation', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    await user.click(screen.getByText('Securities Act, 1992'));

    const viewButtons = screen.getAllByRole('button', { name: /view/i });
    expect(viewButtons.length).toBeGreaterThan(0);
  });

  it('shows Fix button for citations with issues', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    await user.click(screen.getByText('Securities Act, 1992'));

    const fixButtons = screen.getAllByRole('button', { name: /fix/i });
    expect(fixButtons.length).toBeGreaterThan(0);
  });

  it('calls onViewCitation when View button clicked', async () => {
    const user = userEvent.setup();
    const onViewCitation = vi.fn();

    render(<CitationsByActView {...defaultProps} onViewCitation={onViewCitation} />);

    await user.click(screen.getByText('Securities Act, 1992'));
    const viewButtons = screen.getAllByRole('button', { name: /view/i });
    const firstButton = viewButtons[0];
    if (firstButton) {
      await user.click(firstButton);
    }

    expect(onViewCitation).toHaveBeenCalled();
  });

  it('calls onFixCitation when Fix button clicked', async () => {
    const user = userEvent.setup();
    const onFixCitation = vi.fn();

    render(<CitationsByActView {...defaultProps} onFixCitation={onFixCitation} />);

    await user.click(screen.getByText('Securities Act, 1992'));
    await user.click(screen.getByRole('button', { name: /fix/i }));

    expect(onFixCitation).toHaveBeenCalledWith('cit-2');
  });

  it('shows loading state', () => {
    render(<CitationsByActView {...defaultProps} isLoading={true} />);

    expect(screen.queryByText('Securities Act, 1992')).not.toBeInTheDocument();
  });

  it('shows error state', () => {
    render(<CitationsByActView {...defaultProps} error="Failed to load" />);

    expect(screen.getByText('Failed to load')).toBeInTheDocument();
  });

  it('shows empty state when no citations', () => {
    render(<CitationsByActView citations={[]} summary={[]} />);

    expect(screen.getByText('No citations found')).toBeInTheDocument();
  });

  it('shows issue indicator on sections with problems', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    await user.click(screen.getByText('Securities Act, 1992'));

    expect(screen.getByText(/Section may have issues/)).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <CitationsByActView {...defaultProps} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('displays status icons for each citation', async () => {
    const user = userEvent.setup();
    render(<CitationsByActView {...defaultProps} />);

    await user.click(screen.getByText('Securities Act, 1992'));

    // Status icons should be rendered (CheckCircle for verified, AlertTriangle for mismatch)
    // We check by finding elements with status icon classes
    const elements = document.querySelectorAll('[class*="text-green"]');
    expect(elements.length).toBeGreaterThan(0);
  });
});
