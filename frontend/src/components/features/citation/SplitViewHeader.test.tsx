/**
 * SplitViewHeader Unit Tests
 *
 * Story 3-4: Split-View Citation Highlighting (AC: #1, #3)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SplitViewHeader } from './SplitViewHeader';
import type { Citation, VerificationResult } from '@/types/citation';

// Mock citation data
const mockCitation: Citation = {
  id: 'citation-123',
  matterId: 'matter-456',
  documentId: 'doc-789',
  documentName: 'Case File.pdf',
  actName: 'Negotiable Instruments Act, 1881',
  sectionNumber: '138',
  subsection: null,
  clause: null,
  rawCitationText: 'Section 138 of the Negotiable Instruments Act, 1881',
  quotedText: null,
  actNameOriginal: null,
  confidence: 95.5,
  sourcePage: 45,
  sourceBboxIds: ['bbox-1', 'bbox-2'],
  targetPage: null,
  targetBboxIds: [],
  targetActDocumentId: null,
  verificationStatus: 'pending',
  extractionMetadata: {},
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
};

const mockVerification: VerificationResult = {
  status: 'verified',
  sectionFound: true,
  sectionText: 'Section 138 text content',
  targetPage: 89,
  targetBboxIds: ['bbox-1', 'bbox-2'],
  similarityScore: 98.5,
  explanation: 'Citation verified successfully',
  diffDetails: null,
};

const mockNavigationInfo = {
  currentIndex: 0,
  totalCount: 5,
  canPrev: false,
  canNext: true,
};

describe('SplitViewHeader', () => {
  it('renders citation information correctly', () => {
    const onClose = vi.fn();
    const onToggleFullScreen = vi.fn();
    const onPrev = vi.fn();
    const onNext = vi.fn();

    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={mockNavigationInfo}
        onClose={onClose}
        onToggleFullScreen={onToggleFullScreen}
        onPrev={onPrev}
        onNext={onNext}
      />
    );

    // Check Act name is displayed
    expect(screen.getByText('Negotiable Instruments Act, 1881')).toBeInTheDocument();

    // Check section number is displayed
    expect(screen.getByText(/Section 138/)).toBeInTheDocument();
  });

  it('displays pending status badge', () => {
    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={mockNavigationInfo}
        onClose={vi.fn()}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('displays verified status badge', () => {
    const verifiedCitation = { ...mockCitation, verificationStatus: 'verified' as const };

    render(
      <SplitViewHeader
        citation={verifiedCitation}
        verification={mockVerification}
        isFullScreen={false}
        navigationInfo={mockNavigationInfo}
        onClose={vi.fn()}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('98.5% match')).toBeInTheDocument();
  });

  it('displays mismatch explanation when status is mismatch (AC: #3)', () => {
    const mismatchCitation = { ...mockCitation, verificationStatus: 'mismatch' as const };
    const mismatchVerification: VerificationResult = {
      status: 'mismatch',
      sectionFound: true,
      sectionText: 'may be liable for punishment',
      targetPage: 89,
      targetBboxIds: ['bbox-1'],
      similarityScore: 75.0,
      explanation: 'Text differs at word "shall" vs "may"',
      diffDetails: {
        citationText: 'shall be liable',
        actText: 'may be liable',
        matchType: 'mismatch',
        differences: ['shall vs may'],
      },
    };

    render(
      <SplitViewHeader
        citation={mismatchCitation}
        verification={mismatchVerification}
        isFullScreen={false}
        navigationInfo={mockNavigationInfo}
        onClose={vi.fn()}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    expect(screen.getByText('Mismatch')).toBeInTheDocument();
    expect(screen.getByText('Mismatch Detected')).toBeInTheDocument();
    expect(screen.getByText('Text differs at word "shall" vs "may"')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();

    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={mockNavigationInfo}
        onClose={onClose}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTitle('Close (Escape)'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onToggleFullScreen when expand button is clicked', () => {
    const onToggleFullScreen = vi.fn();

    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={mockNavigationInfo}
        onClose={vi.fn()}
        onToggleFullScreen={onToggleFullScreen}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTitle('Full screen (F)'));
    expect(onToggleFullScreen).toHaveBeenCalledTimes(1);
  });

  it('disables prev button when at first citation', () => {
    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={{ ...mockNavigationInfo, canPrev: false }}
        onClose={vi.fn()}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    const prevButton = screen.getByTitle('Previous citation (Left Arrow)');
    expect(prevButton).toBeDisabled();
  });

  it('enables next button when not at last citation', () => {
    const onNext = vi.fn();

    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={{ ...mockNavigationInfo, canNext: true }}
        onClose={vi.fn()}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={onNext}
      />
    );

    const nextButton = screen.getByTitle('Next citation (Right Arrow)');
    expect(nextButton).not.toBeDisabled();

    fireEvent.click(nextButton);
    expect(onNext).toHaveBeenCalledTimes(1);
  });

  it('shows navigation counter correctly', () => {
    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={{ currentIndex: 2, totalCount: 10, canPrev: true, canNext: true }}
        onClose={vi.fn()}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    // Index is 0-based, display is 1-based
    expect(screen.getByText('3 / 10')).toBeInTheDocument();
  });

  it('hides navigation when only one citation', () => {
    render(
      <SplitViewHeader
        citation={mockCitation}
        verification={null}
        isFullScreen={false}
        navigationInfo={{ currentIndex: 0, totalCount: 1, canPrev: false, canNext: false }}
        onClose={vi.fn()}
        onToggleFullScreen={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
      />
    );

    // Navigation buttons should not be present
    expect(screen.queryByTitle('Previous citation (Left Arrow)')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Next citation (Right Arrow)')).not.toBeInTheDocument();
  });
});
