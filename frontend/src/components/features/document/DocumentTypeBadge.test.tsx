import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DocumentTypeBadge } from './DocumentTypeBadge';
import type { DocumentType } from '@/types/document';

describe('DocumentTypeBadge', () => {
  describe('Rendering', () => {
    it('renders case_file type with correct label', () => {
      render(<DocumentTypeBadge type="case_file" />);
      expect(screen.getByText('Case File')).toBeInTheDocument();
    });

    it('renders act type with correct label', () => {
      render(<DocumentTypeBadge type="act" />);
      expect(screen.getByText('Act')).toBeInTheDocument();
    });

    it('renders annexure type with correct label', () => {
      render(<DocumentTypeBadge type="annexure" />);
      expect(screen.getByText('Annexure')).toBeInTheDocument();
    });

    it('renders other type with correct label', () => {
      render(<DocumentTypeBadge type="other" />);
      expect(screen.getByText('Other')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies blue styling for case_file', () => {
      render(<DocumentTypeBadge type="case_file" />);
      const badge = screen.getByText('Case File');
      expect(badge).toHaveClass('bg-blue-100');
      expect(badge).toHaveClass('text-blue-800');
    });

    it('applies green styling for act', () => {
      render(<DocumentTypeBadge type="act" />);
      const badge = screen.getByText('Act');
      expect(badge).toHaveClass('bg-green-100');
      expect(badge).toHaveClass('text-green-800');
    });

    it('applies yellow styling for annexure', () => {
      render(<DocumentTypeBadge type="annexure" />);
      const badge = screen.getByText('Annexure');
      expect(badge).toHaveClass('bg-yellow-100');
      expect(badge).toHaveClass('text-yellow-800');
    });

    it('applies gray styling for other', () => {
      render(<DocumentTypeBadge type="other" />);
      const badge = screen.getByText('Other');
      expect(badge).toHaveClass('bg-gray-100');
      expect(badge).toHaveClass('text-gray-800');
    });

    it('accepts additional className prop', () => {
      render(<DocumentTypeBadge type="case_file" className="custom-class" />);
      const badge = screen.getByText('Case File');
      expect(badge).toHaveClass('custom-class');
    });
  });

  describe('Accessibility', () => {
    const typeLabels: [DocumentType, string][] = [
      ['case_file', 'Case File'],
      ['act', 'Act'],
      ['annexure', 'Annexure'],
      ['other', 'Other'],
    ];

    it.each(typeLabels)('renders %s type with data-slot attribute', (type, label) => {
      render(<DocumentTypeBadge type={type} />);
      const badge = screen.getByText(label);
      expect(badge).toHaveAttribute('data-slot', 'badge');
    });
  });
});
