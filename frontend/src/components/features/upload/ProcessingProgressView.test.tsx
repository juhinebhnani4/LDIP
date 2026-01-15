import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProcessingProgressView } from './ProcessingProgressView';
import type { ProcessingStage } from '@/types/upload';

describe('ProcessingProgressView', () => {
  describe('rendering', () => {
    it('renders title', () => {
      render(
        <ProcessingProgressView
          currentStage="OCR"
          overallProgressPct={50}
        />
      );

      expect(screen.getByText('PROCESSING YOUR CASE')).toBeInTheDocument();
    });

    it('renders overall progress bar', () => {
      render(
        <ProcessingProgressView
          currentStage="OCR"
          overallProgressPct={67}
        />
      );

      const progressBar = screen.getByRole('progressbar', {
        name: /overall processing progress/i,
      });
      expect(progressBar).toBeInTheDocument();
    });

    it('displays progress percentage', () => {
      render(
        <ProcessingProgressView
          currentStage="ENTITY_EXTRACTION"
          overallProgressPct={75}
        />
      );

      expect(screen.getByText('75%')).toBeInTheDocument();
    });
  });

  describe('stage indicators', () => {
    it('shows stage 1 of 5 for UPLOADING', () => {
      render(
        <ProcessingProgressView
          currentStage="UPLOADING"
          overallProgressPct={10}
        />
      );

      expect(screen.getByText(/stage 1 of 5/i)).toBeInTheDocument();
      expect(screen.getByText(/uploading files/i)).toBeInTheDocument();
    });

    it('shows stage 2 of 5 for OCR', () => {
      render(
        <ProcessingProgressView
          currentStage="OCR"
          overallProgressPct={30}
        />
      );

      expect(screen.getByText(/stage 2 of 5/i)).toBeInTheDocument();
    });

    it('shows stage 3 of 5 for ENTITY_EXTRACTION', () => {
      render(
        <ProcessingProgressView
          currentStage="ENTITY_EXTRACTION"
          overallProgressPct={50}
        />
      );

      expect(screen.getByText(/stage 3 of 5/i)).toBeInTheDocument();
    });

    it('shows stage 4 of 5 for ANALYSIS', () => {
      render(
        <ProcessingProgressView
          currentStage="ANALYSIS"
          overallProgressPct={70}
        />
      );

      expect(screen.getByText(/stage 4 of 5/i)).toBeInTheDocument();
    });

    it('shows stage 5 of 5 for INDEXING', () => {
      render(
        <ProcessingProgressView
          currentStage="INDEXING"
          overallProgressPct={90}
        />
      );

      expect(screen.getByText(/stage 5 of 5/i)).toBeInTheDocument();
    });

    it('renders all 5 stage indicator dots', () => {
      render(
        <ProcessingProgressView
          currentStage="ENTITY_EXTRACTION"
          overallProgressPct={50}
        />
      );

      const group = screen.getByRole('group', { name: /processing stages/i });
      expect(group).toBeInTheDocument();

      // Check stage numbers are present
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  describe('completion state', () => {
    it('shows completion message when at 100%', () => {
      render(
        <ProcessingProgressView
          currentStage="INDEXING"
          overallProgressPct={100}
        />
      );

      expect(screen.getByText('Processing complete!')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
    });
  });

  describe('optional statistics', () => {
    it('shows files received when provided', () => {
      render(
        <ProcessingProgressView
          currentStage="OCR"
          overallProgressPct={30}
          filesReceived={89}
        />
      );

      expect(screen.getByText('89')).toBeInTheDocument();
      expect(screen.getByText('Files Received')).toBeInTheDocument();
    });

    it('shows pages extracted when provided', () => {
      render(
        <ProcessingProgressView
          currentStage="OCR"
          overallProgressPct={40}
          filesReceived={10}
          pagesExtracted={2100}
        />
      );

      expect(screen.getByText('2,100')).toBeInTheDocument();
      expect(screen.getByText('Pages Extracted')).toBeInTheDocument();
    });

    it('shows OCR progress when in OCR stage', () => {
      render(
        <ProcessingProgressView
          currentStage="OCR"
          overallProgressPct={30}
          ocrProgressPct={78}
        />
      );

      expect(screen.getByText('OCR Progress')).toBeInTheDocument();
      expect(screen.getByText('78%')).toBeInTheDocument();
    });

    it('does not show OCR progress for non-OCR stages', () => {
      render(
        <ProcessingProgressView
          currentStage="ENTITY_EXTRACTION"
          overallProgressPct={50}
          ocrProgressPct={100}
        />
      );

      expect(screen.queryByText('OCR Progress')).not.toBeInTheDocument();
    });

    it('shows documents processed count when provided', () => {
      render(
        <ProcessingProgressView
          currentStage="ENTITY_EXTRACTION"
          overallProgressPct={50}
          filesReceived={89}
          documentsProcessed={45}
          totalDocuments={89}
        />
      );

      expect(screen.getByText(/45 of 89 documents processed/i)).toBeInTheDocument();
    });
  });

  describe('null stage', () => {
    it('handles null stage gracefully', () => {
      render(
        <ProcessingProgressView
          currentStage={null}
          overallProgressPct={0}
        />
      );

      expect(screen.getByText('0%')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('progress bar has proper aria attributes', () => {
      render(
        <ProcessingProgressView
          currentStage="ANALYSIS"
          overallProgressPct={67}
        />
      );

      const progressBar = screen.getByRole('progressbar', {
        name: /overall processing progress/i,
      });
      expect(progressBar).toHaveAttribute('aria-valuenow', '67');
    });

    it('stage indicator has live region for announcements', () => {
      render(
        <ProcessingProgressView
          currentStage="ENTITY_EXTRACTION"
          overallProgressPct={50}
        />
      );

      const stageText = screen.getByText(/stage 3 of 5/i);
      expect(stageText).toHaveAttribute('aria-live', 'polite');
    });
  });
});
