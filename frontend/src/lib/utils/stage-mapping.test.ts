/**
 * Stage Mapping Tests
 *
 * Tests for backend to UI stage mapping utilities.
 * Story 14-3: Wire Upload Stage 3-4 UI to Real APIs
 */

import { describe, it, expect } from 'vitest';
import {
  mapBackendStageToUI,
  determineOverallStage,
  isTerminalStatus,
  isActiveStatus,
} from './stage-mapping';

describe('mapBackendStageToUI', () => {
  describe('UPLOADING stage mapping', () => {
    it('maps "upload" to UPLOADING', () => {
      expect(mapBackendStageToUI('upload')).toBe('UPLOADING');
    });

    it('maps "receiving" to UPLOADING', () => {
      expect(mapBackendStageToUI('receiving')).toBe('UPLOADING');
    });

    it('maps "queued" to UPLOADING', () => {
      expect(mapBackendStageToUI('queued')).toBe('UPLOADING');
    });
  });

  describe('OCR stage mapping', () => {
    it('maps "ocr" to OCR', () => {
      expect(mapBackendStageToUI('ocr')).toBe('OCR');
    });

    it('maps "validation" to OCR', () => {
      expect(mapBackendStageToUI('validation')).toBe('OCR');
    });

    it('maps "text_extraction" to OCR', () => {
      expect(mapBackendStageToUI('text_extraction')).toBe('OCR');
    });
  });

  describe('ENTITY_EXTRACTION stage mapping', () => {
    it('maps "entity_extraction" to ENTITY_EXTRACTION', () => {
      expect(mapBackendStageToUI('entity_extraction')).toBe('ENTITY_EXTRACTION');
    });

    it('maps "alias_resolution" to ENTITY_EXTRACTION', () => {
      expect(mapBackendStageToUI('alias_resolution')).toBe('ENTITY_EXTRACTION');
    });

    it('maps "mig_construction" to ENTITY_EXTRACTION', () => {
      expect(mapBackendStageToUI('mig_construction')).toBe('ENTITY_EXTRACTION');
    });
  });

  describe('ANALYSIS stage mapping', () => {
    it('maps "chunking" to ANALYSIS', () => {
      expect(mapBackendStageToUI('chunking')).toBe('ANALYSIS');
    });

    it('maps "embedding" to ANALYSIS', () => {
      expect(mapBackendStageToUI('embedding')).toBe('ANALYSIS');
    });

    it('maps "date_extraction" to ANALYSIS', () => {
      expect(mapBackendStageToUI('date_extraction')).toBe('ANALYSIS');
    });

    it('maps "event_classification" to ANALYSIS', () => {
      expect(mapBackendStageToUI('event_classification')).toBe('ANALYSIS');
    });

    it('maps "citation_extraction" to ANALYSIS', () => {
      expect(mapBackendStageToUI('citation_extraction')).toBe('ANALYSIS');
    });
  });

  describe('INDEXING stage mapping', () => {
    it('maps "indexing" to INDEXING', () => {
      expect(mapBackendStageToUI('indexing')).toBe('INDEXING');
    });

    it('maps "completed" to INDEXING', () => {
      expect(mapBackendStageToUI('completed')).toBe('INDEXING');
    });

    it('maps "finalizing" to INDEXING', () => {
      expect(mapBackendStageToUI('finalizing')).toBe('INDEXING');
    });
  });

  describe('edge cases', () => {
    it('returns UPLOADING for null', () => {
      expect(mapBackendStageToUI(null)).toBe('UPLOADING');
    });

    it('returns UPLOADING for undefined', () => {
      expect(mapBackendStageToUI(undefined)).toBe('UPLOADING');
    });

    it('returns UPLOADING for empty string', () => {
      expect(mapBackendStageToUI('')).toBe('UPLOADING');
    });

    it('returns UPLOADING for unknown stage', () => {
      expect(mapBackendStageToUI('unknown_stage')).toBe('UPLOADING');
    });

    it('handles uppercase input', () => {
      expect(mapBackendStageToUI('OCR')).toBe('OCR');
    });

    it('handles mixed case input', () => {
      expect(mapBackendStageToUI('Entity_Extraction')).toBe('ENTITY_EXTRACTION');
    });

    it('handles whitespace', () => {
      expect(mapBackendStageToUI('  ocr  ')).toBe('OCR');
    });
  });
});

describe('determineOverallStage', () => {
  it('returns UPLOADING for empty array', () => {
    expect(determineOverallStage([])).toBe('UPLOADING');
  });

  it('returns UPLOADING for array of nulls', () => {
    expect(determineOverallStage([null, undefined])).toBe('UPLOADING');
  });

  it('returns the single stage for single-element array', () => {
    expect(determineOverallStage(['ocr'])).toBe('OCR');
  });

  it('returns the most advanced stage from multiple stages', () => {
    expect(determineOverallStage(['upload', 'ocr', 'entity_extraction'])).toBe(
      'ENTITY_EXTRACTION'
    );
  });

  it('returns INDEXING when any stage is indexing/completed', () => {
    expect(determineOverallStage(['ocr', 'completed'])).toBe('INDEXING');
  });

  it('returns ANALYSIS for analysis-stage jobs', () => {
    expect(determineOverallStage(['chunking', 'embedding'])).toBe('ANALYSIS');
  });

  it('handles mixed valid and null stages', () => {
    expect(determineOverallStage([null, 'ocr', undefined, 'chunking'])).toBe(
      'ANALYSIS'
    );
  });
});

describe('isTerminalStatus', () => {
  it('returns true for COMPLETED', () => {
    expect(isTerminalStatus('COMPLETED')).toBe(true);
  });

  it('returns true for FAILED', () => {
    expect(isTerminalStatus('FAILED')).toBe(true);
  });

  it('returns true for CANCELLED', () => {
    expect(isTerminalStatus('CANCELLED')).toBe(true);
  });

  it('returns true for SKIPPED', () => {
    expect(isTerminalStatus('SKIPPED')).toBe(true);
  });

  it('returns false for QUEUED', () => {
    expect(isTerminalStatus('QUEUED')).toBe(false);
  });

  it('returns false for PROCESSING', () => {
    expect(isTerminalStatus('PROCESSING')).toBe(false);
  });

  it('returns false for null', () => {
    expect(isTerminalStatus(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isTerminalStatus(undefined)).toBe(false);
  });

  it('handles lowercase input', () => {
    expect(isTerminalStatus('completed')).toBe(true);
  });
});

describe('isActiveStatus', () => {
  it('returns true for QUEUED', () => {
    expect(isActiveStatus('QUEUED')).toBe(true);
  });

  it('returns true for PROCESSING', () => {
    expect(isActiveStatus('PROCESSING')).toBe(true);
  });

  it('returns false for COMPLETED', () => {
    expect(isActiveStatus('COMPLETED')).toBe(false);
  });

  it('returns false for FAILED', () => {
    expect(isActiveStatus('FAILED')).toBe(false);
  });

  it('returns false for null', () => {
    expect(isActiveStatus(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isActiveStatus(undefined)).toBe(false);
  });

  it('handles lowercase input', () => {
    expect(isActiveStatus('queued')).toBe(true);
  });
});
