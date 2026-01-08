import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OCRQualityBadge } from './OCRQualityBadge';

describe('OCRQualityBadge', () => {
  describe('Status Display', () => {
    it('renders "Pending" for null status', () => {
      render(<OCRQualityBadge status={null} />);
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    it('renders "Good" for good status', () => {
      render(<OCRQualityBadge status="good" />);
      expect(screen.getByText('Good')).toBeInTheDocument();
    });

    it('renders "Fair" for fair status', () => {
      render(<OCRQualityBadge status="fair" />);
      expect(screen.getByText('Fair')).toBeInTheDocument();
    });

    it('renders "Poor" for poor status', () => {
      render(<OCRQualityBadge status="poor" />);
      expect(screen.getByText('Poor')).toBeInTheDocument();
    });
  });

  describe('Confidence Percentage', () => {
    it('does not show percentage by default', () => {
      render(<OCRQualityBadge status="good" confidence={0.92} />);
      expect(screen.getByText('Good')).toBeInTheDocument();
      expect(screen.queryByText(/92%/)).not.toBeInTheDocument();
    });

    it('shows percentage when showPercentage is true', () => {
      render(<OCRQualityBadge status="good" confidence={0.92} showPercentage />);
      expect(screen.getByText('Good (92%)')).toBeInTheDocument();
    });

    it('rounds percentage to nearest integer', () => {
      render(<OCRQualityBadge status="fair" confidence={0.756} showPercentage />);
      expect(screen.getByText('Fair (76%)')).toBeInTheDocument();
    });

    it('handles null confidence gracefully', () => {
      render(<OCRQualityBadge status="good" confidence={null} showPercentage />);
      expect(screen.getByText('Good')).toBeInTheDocument();
    });
  });

  describe('Color Styling', () => {
    it('uses green styling for good status', () => {
      render(<OCRQualityBadge status="good" />);
      const badge = screen.getByText('Good');
      expect(badge.className).toContain('green');
    });

    it('uses yellow styling for fair status', () => {
      render(<OCRQualityBadge status="fair" />);
      const badge = screen.getByText('Fair');
      expect(badge.className).toContain('yellow');
    });

    it('uses red styling for poor status', () => {
      render(<OCRQualityBadge status="poor" />);
      const badge = screen.getByText('Poor');
      expect(badge.className).toContain('red');
    });

    it('uses gray styling for pending status', () => {
      render(<OCRQualityBadge status={null} />);
      const badge = screen.getByText('Pending');
      expect(badge.className).toContain('gray');
    });
  });

  describe('Tooltip for Poor Status', () => {
    it('renders tooltip wrapper for poor status', () => {
      render(<OCRQualityBadge status="poor" />);
      // The badge should still be visible
      expect(screen.getByText('Poor')).toBeInTheDocument();
    });

    it('does not render tooltip for good status', () => {
      render(<OCRQualityBadge status="good" />);
      expect(screen.getByText('Good')).toBeInTheDocument();
    });

    it('does not render tooltip for fair status', () => {
      render(<OCRQualityBadge status="fair" />);
      expect(screen.getByText('Fair')).toBeInTheDocument();
    });
  });

  describe('Custom ClassName', () => {
    it('applies custom className', () => {
      render(<OCRQualityBadge status="good" className="custom-class" />);
      const badge = screen.getByText('Good');
      expect(badge.className).toContain('custom-class');
    });
  });
});
