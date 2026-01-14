import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MatterCard } from './MatterCard';
import type { MatterCardData } from '@/types/matter';

const createMockMatter = (overrides: Partial<MatterCardData> = {}): MatterCardData => ({
  id: 'matter-1',
  title: 'Test Matter',
  description: 'Test description',
  status: 'active',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
  role: 'owner',
  memberCount: 2,
  pageCount: 1000,
  documentCount: 50,
  verificationPercent: 85,
  issueCount: 3,
  processingStatus: 'ready',
  lastOpened: '2026-01-01T10:00:00Z',
  ...overrides,
});

describe('MatterCard', () => {
  describe('Ready state', () => {
    it('renders matter title', () => {
      const matter = createMockMatter({ title: 'Shah v. Mehta' });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('Shah v. Mehta')).toBeInTheDocument();
    });

    it('renders Ready status badge', () => {
      const matter = createMockMatter({ processingStatus: 'ready' });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('Ready')).toBeInTheDocument();
    });

    it('renders page count with formatting', () => {
      const matter = createMockMatter({ pageCount: 1247 });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('1,247 pages')).toBeInTheDocument();
    });

    it('renders verification percentage', () => {
      const matter = createMockMatter({ verificationPercent: 85 });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('85%')).toBeInTheDocument();
      expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('renders issue count', () => {
      const matter = createMockMatter({ issueCount: 3 });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('Issues')).toBeInTheDocument();
    });

    it('renders Resume button linking to matter workspace', () => {
      const matter = createMockMatter({ id: 'matter-123' });
      render(<MatterCard matter={matter} />);

      const resumeLink = screen.getByRole('link', { name: /resume/i });
      expect(resumeLink).toHaveAttribute('href', '/matter/matter-123');
    });

    it('has correct aria-label for accessibility', () => {
      const matter = createMockMatter({ title: 'Shah v. Mehta' });
      render(<MatterCard matter={matter} />);

      expect(screen.getByRole('article', { name: 'Matter: Shah v. Mehta' })).toBeInTheDocument();
    });

    it('applies high verification styling when >= 90%', () => {
      const matter = createMockMatter({ verificationPercent: 95 });
      render(<MatterCard matter={matter} />);

      // The verification box contains the percentage and "Verified" text
      const percentageText = screen.getByText('95%');
      const verifiedBox = percentageText.parentElement;
      expect(verifiedBox).toHaveClass('bg-green-50');
    });

    it('applies warning styling when verification < 70%', () => {
      const matter = createMockMatter({ verificationPercent: 60 });
      render(<MatterCard matter={matter} />);

      const percentageText = screen.getByText('60%');
      const verifiedBox = percentageText.parentElement;
      expect(verifiedBox).toHaveClass('bg-red-50');
    });
  });

  describe('Needs attention state', () => {
    it('renders Needs Attention status badge', () => {
      const matter = createMockMatter({ processingStatus: 'needs_attention' });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('Needs Attention')).toBeInTheDocument();
    });
  });

  describe('Processing state', () => {
    const processingMatter = createMockMatter({
      processingStatus: 'processing',
      processingProgress: 67,
      estimatedTimeRemaining: 180,
      documentCount: 89,
      pageCount: 2100,
    });

    it('renders Processing status badge', () => {
      render(<MatterCard matter={processingMatter} />);

      expect(screen.getByText('Processing')).toBeInTheDocument();
    });

    it('renders progress bar', () => {
      render(<MatterCard matter={processingMatter} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('renders progress percentage', () => {
      render(<MatterCard matter={processingMatter} />);

      expect(screen.getByText('67% complete')).toBeInTheDocument();
    });

    it('renders estimated time remaining', () => {
      render(<MatterCard matter={processingMatter} />);

      expect(screen.getByText('Est. 3 min left')).toBeInTheDocument();
    });

    it('renders document count', () => {
      render(<MatterCard matter={processingMatter} />);

      expect(screen.getByText('89 documents')).toBeInTheDocument();
    });

    it('renders page count', () => {
      render(<MatterCard matter={processingMatter} />);

      expect(screen.getByText('2,100 pages')).toBeInTheDocument();
    });

    it('renders View Progress button instead of Resume', () => {
      render(<MatterCard matter={processingMatter} />);

      expect(screen.getByRole('link', { name: /view progress/i })).toBeInTheDocument();
      expect(screen.queryByRole('link', { name: /resume/i })).not.toBeInTheDocument();
    });

    it('handles zero progress', () => {
      const matter = createMockMatter({
        processingStatus: 'processing',
        processingProgress: 0,
      });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('0% complete')).toBeInTheDocument();
    });

    it('formats hours correctly for long estimates', () => {
      const matter = createMockMatter({
        processingStatus: 'processing',
        processingProgress: 10,
        estimatedTimeRemaining: 3900, // 65 minutes = 1h 5m
      });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText('Est. 1h 5m left')).toBeInTheDocument();
    });
  });

  describe('Last opened formatting', () => {
    it('shows "Just now" for recent activity', () => {
      const matter = createMockMatter({
        lastOpened: new Date().toISOString(),
      });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText(/last opened: just now/i)).toBeInTheDocument();
    });

    it('shows minutes for activity within the hour', () => {
      const fifteenMinsAgo = new Date(Date.now() - 15 * 60000).toISOString();
      const matter = createMockMatter({ lastOpened: fifteenMinsAgo });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText(/last opened: 15m ago/i)).toBeInTheDocument();
    });

    it('shows hours for activity within the day', () => {
      const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60000).toISOString();
      const matter = createMockMatter({ lastOpened: threeHoursAgo });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText(/last opened: 3h ago/i)).toBeInTheDocument();
    });

    it('shows Never opened when lastOpened is undefined', () => {
      const matter = createMockMatter({ lastOpened: undefined });
      render(<MatterCard matter={matter} />);

      expect(screen.getByText(/last opened: never opened/i)).toBeInTheDocument();
    });
  });
});
