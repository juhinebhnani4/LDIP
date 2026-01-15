import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  simulateUploadAndProcessing,
  simulateUploadProgress,
  simulateProcessingProgress,
  MOCK_ENTITIES,
  MOCK_DATES,
  MOCK_CITATIONS,
  MOCK_INSIGHTS,
} from './mock-processing';
import type { UploadProgress, ProcessingStage, LiveDiscovery } from '@/types/upload';

// Helper to create mock file
function createMockFile(name: string, size: number = 1024): File {
  const file = new File(['test'], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

describe('mock-processing', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('MOCK_ENTITIES', () => {
    it('contains expected entities', () => {
      expect(MOCK_ENTITIES.length).toBeGreaterThan(0);
      expect(MOCK_ENTITIES[0]).toHaveProperty('name');
      expect(MOCK_ENTITIES[0]).toHaveProperty('role');
    });

    it('includes expected entity names', () => {
      const names = MOCK_ENTITIES.map((e) => e.name);
      expect(names).toContain('Mehul Parekh');
      expect(names).toContain('SEBI');
    });
  });

  describe('MOCK_DATES', () => {
    it('has valid date range', () => {
      expect(MOCK_DATES.earliest).toBeInstanceOf(Date);
      expect(MOCK_DATES.latest).toBeInstanceOf(Date);
      expect(MOCK_DATES.earliest < MOCK_DATES.latest).toBe(true);
    });

    it('has count property', () => {
      expect(MOCK_DATES.count).toBeGreaterThan(0);
    });
  });

  describe('MOCK_CITATIONS', () => {
    it('contains citation data', () => {
      expect(MOCK_CITATIONS.length).toBeGreaterThan(0);
      expect(MOCK_CITATIONS[0]).toHaveProperty('actName');
      expect(MOCK_CITATIONS[0]).toHaveProperty('count');
    });
  });

  describe('MOCK_INSIGHTS', () => {
    it('contains info and warning insights', () => {
      expect(MOCK_INSIGHTS.length).toBeGreaterThan(0);
      const types = MOCK_INSIGHTS.map((i) => i.type);
      expect(types).toContain('info');
      expect(types).toContain('warning');
    });
  });

  describe('simulateUploadProgress', () => {
    it('calls onProgress for each file', async () => {
      const onProgress = vi.fn();
      const files = [createMockFile('test.pdf')];

      const cleanup = simulateUploadProgress(files, onProgress);

      // Fast-forward through upload
      await vi.runAllTimersAsync();

      expect(onProgress).toHaveBeenCalled();
      cleanup();
    });

    it('progresses from pending to complete', async () => {
      const progressUpdates: UploadProgress[] = [];
      const files = [createMockFile('test.pdf')];

      const cleanup = simulateUploadProgress(files, (fileName, progress) => {
        progressUpdates.push({ ...progress });
      });

      await vi.runAllTimersAsync();

      // Should have pending -> uploading -> complete
      const statuses = progressUpdates.map((p) => p.status);
      expect(statuses[0]).toBe('pending');
      expect(statuses).toContain('uploading');
      expect(statuses[statuses.length - 1]).toBe('complete');

      cleanup();
    });

    it('can be cancelled', async () => {
      const onProgress = vi.fn();
      const files = [createMockFile('test.pdf')];

      const cleanup = simulateUploadProgress(files, onProgress);

      // Allow initial synchronous calls to happen (pending + uploading states)
      // These happen before the first await in simulateFileUpload
      await vi.advanceTimersByTimeAsync(0);

      cleanup(); // Cancel after initial calls

      await vi.runAllTimersAsync();
      const callCountAfter = onProgress.mock.calls.length;

      // After cancel, progress should stop - not reach 'complete' status
      const lastCall = onProgress.mock.calls[callCountAfter - 1]?.[1];
      expect(lastCall?.status).not.toBe('complete');
    });
  });

  describe('simulateProcessingProgress', () => {
    it('cycles through all stages', async () => {
      const stages: ProcessingStage[] = [];
      const cleanup = simulateProcessingProgress({
        onProcessingStage: (stage) => {
          if (stage) stages.push(stage);
        },
        onOverallProgress: vi.fn(),
        onDiscovery: vi.fn(),
        onComplete: vi.fn(),
      });

      await vi.runAllTimersAsync();

      expect(stages).toContain('UPLOADING');
      expect(stages).toContain('OCR');
      expect(stages).toContain('ENTITY_EXTRACTION');
      expect(stages).toContain('ANALYSIS');
      expect(stages).toContain('INDEXING');

      cleanup();
    });

    it('progresses from 0 to 100', async () => {
      const progressUpdates: number[] = [];
      const cleanup = simulateProcessingProgress({
        onProcessingStage: vi.fn(),
        onOverallProgress: (pct) => progressUpdates.push(pct),
        onDiscovery: vi.fn(),
        onComplete: vi.fn(),
      });

      await vi.runAllTimersAsync();

      expect(progressUpdates[0]!).toBeLessThan(progressUpdates[progressUpdates.length - 1]!);
      expect(progressUpdates[progressUpdates.length - 1]!).toBe(100);

      cleanup();
    });

    it('generates discoveries', async () => {
      const discoveries: LiveDiscovery[] = [];
      const cleanup = simulateProcessingProgress({
        onProcessingStage: vi.fn(),
        onOverallProgress: vi.fn(),
        onDiscovery: (d) => discoveries.push(d),
        onComplete: vi.fn(),
      });

      await vi.runAllTimersAsync();

      expect(discoveries.length).toBeGreaterThan(0);
      const types = discoveries.map((d) => d.type);
      expect(types).toContain('entity');
      expect(types).toContain('date');
      expect(types).toContain('citation');
      expect(types).toContain('insight');

      cleanup();
    });

    it('calls onComplete at end', async () => {
      const onComplete = vi.fn();
      const cleanup = simulateProcessingProgress({
        onProcessingStage: vi.fn(),
        onOverallProgress: vi.fn(),
        onDiscovery: vi.fn(),
        onComplete,
      });

      await vi.runAllTimersAsync();

      expect(onComplete).toHaveBeenCalledTimes(1);

      cleanup();
    });
  });

  describe('simulateUploadAndProcessing', () => {
    it('runs upload phase then processing phase', async () => {
      const uploadUpdates: UploadProgress[] = [];
      const stages: (ProcessingStage | null)[] = [];

      const files = [createMockFile('test.pdf')];

      const cleanup = simulateUploadAndProcessing(files, {
        onUploadProgress: (fileName, progress) => {
          uploadUpdates.push({ ...progress });
        },
        onProcessingStage: (stage) => stages.push(stage),
        onOverallProgress: vi.fn(),
        onDiscovery: vi.fn(),
        onComplete: vi.fn(),
      });

      await vi.runAllTimersAsync();

      // Should have upload progress updates
      expect(uploadUpdates.length).toBeGreaterThan(0);
      // Should go through all stages
      expect(stages).toContain('UPLOADING');
      expect(stages).toContain('INDEXING');

      cleanup();
    });

    it('handles multiple files', async () => {
      const fileProgress = new Map<string, UploadProgress[]>();
      const files = [
        createMockFile('file1.pdf'),
        createMockFile('file2.pdf'),
        createMockFile('file3.pdf'),
      ];

      const cleanup = simulateUploadAndProcessing(files, {
        onUploadProgress: (fileName, progress) => {
          if (!fileProgress.has(fileName)) {
            fileProgress.set(fileName, []);
          }
          fileProgress.get(fileName)!.push({ ...progress });
        },
        onProcessingStage: vi.fn(),
        onOverallProgress: vi.fn(),
        onDiscovery: vi.fn(),
        onComplete: vi.fn(),
      });

      await vi.runAllTimersAsync();

      // Each file should have progress updates
      expect(fileProgress.size).toBe(3);
      for (const [, updates] of fileProgress) {
        const lastUpdate = updates[updates.length - 1]!;
        expect(lastUpdate.status).toBe('complete');
      }

      cleanup();
    });

    it('cleanup aborts simulation', async () => {
      const onComplete = vi.fn();
      const files = [createMockFile('test.pdf')];

      const cleanup = simulateUploadAndProcessing(files, {
        onUploadProgress: vi.fn(),
        onProcessingStage: vi.fn(),
        onOverallProgress: vi.fn(),
        onDiscovery: vi.fn(),
        onComplete,
      });

      // Cancel before completion
      cleanup();
      await vi.runAllTimersAsync();

      // onComplete should not be called
      expect(onComplete).not.toHaveBeenCalled();
    });
  });
});
