import { describe, it, expect, beforeEach } from 'vitest';
import {
  useUploadWizardStore,
  selectTotalFileSize,
  selectFileCount,
  selectActsByStatus,
  selectIsMatterNameValid,
  selectCanStartUpload,
} from './uploadWizardStore';
import type { DetectedAct } from '@/types/upload';

// Helper to create mock files
function createMockFile(name: string, size: number = 1024): File {
  const file = new File([''], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

describe('uploadWizardStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useUploadWizardStore.getState().reset();
  });

  describe('initial state', () => {
    it('starts with FILE_SELECTION stage', () => {
      expect(useUploadWizardStore.getState().currentStage).toBe('FILE_SELECTION');
    });

    it('starts with empty files array', () => {
      expect(useUploadWizardStore.getState().files).toEqual([]);
    });

    it('starts with empty matter name', () => {
      expect(useUploadWizardStore.getState().matterName).toBe('');
    });

    it('starts with empty detected acts', () => {
      expect(useUploadWizardStore.getState().detectedActs).toEqual([]);
    });

    it('starts with loading false', () => {
      expect(useUploadWizardStore.getState().isLoading).toBe(false);
    });

    it('starts with no error', () => {
      expect(useUploadWizardStore.getState().error).toBeNull();
    });
  });

  describe('setStage', () => {
    it('updates the current stage', () => {
      useUploadWizardStore.getState().setStage('REVIEW');
      expect(useUploadWizardStore.getState().currentStage).toBe('REVIEW');

      useUploadWizardStore.getState().setStage('ACT_DISCOVERY');
      expect(useUploadWizardStore.getState().currentStage).toBe('ACT_DISCOVERY');
    });
  });

  describe('addFiles', () => {
    it('adds files to the array', () => {
      const file1 = createMockFile('test1.pdf');
      const file2 = createMockFile('test2.pdf');

      useUploadWizardStore.getState().addFiles([file1, file2]);

      expect(useUploadWizardStore.getState().files).toHaveLength(2);
    });

    it('auto-generates matter name from first file', () => {
      const file = createMockFile('Shah_v_Mehta_Case.pdf');

      useUploadWizardStore.getState().addFiles([file]);

      expect(useUploadWizardStore.getState().matterName).toBe('Shah v Mehta Case');
    });

    it('handles files with hyphens in name', () => {
      const file = createMockFile('my-important-document.pdf');

      useUploadWizardStore.getState().addFiles([file]);

      expect(useUploadWizardStore.getState().matterName).toBe('my important document');
    });

    it('transitions to REVIEW stage when files are added', () => {
      const file = createMockFile('test.pdf');

      useUploadWizardStore.getState().addFiles([file]);

      expect(useUploadWizardStore.getState().currentStage).toBe('REVIEW');
    });

    it('preserves existing matter name if already set', () => {
      useUploadWizardStore.getState().setMatterName('Custom Name');
      const file = createMockFile('test.pdf');

      useUploadWizardStore.getState().addFiles([file]);

      expect(useUploadWizardStore.getState().matterName).toBe('Custom Name');
    });

    it('appends to existing files', () => {
      const file1 = createMockFile('test1.pdf');
      const file2 = createMockFile('test2.pdf');

      useUploadWizardStore.getState().addFiles([file1]);
      useUploadWizardStore.getState().addFiles([file2]);

      expect(useUploadWizardStore.getState().files).toHaveLength(2);
    });
  });

  describe('removeFile', () => {
    it('removes file at specified index', () => {
      const file1 = createMockFile('test1.pdf');
      const file2 = createMockFile('test2.pdf');
      const file3 = createMockFile('test3.pdf');

      useUploadWizardStore.getState().addFiles([file1, file2, file3]);
      useUploadWizardStore.getState().removeFile(1);

      const files = useUploadWizardStore.getState().files;
      expect(files).toHaveLength(2);
      expect(files[0]?.name).toBe('test1.pdf');
      expect(files[1]?.name).toBe('test3.pdf');
    });

    it('transitions back to FILE_SELECTION when all files removed', () => {
      const file = createMockFile('test.pdf');

      useUploadWizardStore.getState().addFiles([file]);
      expect(useUploadWizardStore.getState().currentStage).toBe('REVIEW');

      useUploadWizardStore.getState().removeFile(0);
      expect(useUploadWizardStore.getState().currentStage).toBe('FILE_SELECTION');
    });

    it('updates matter name when first file is removed and name was auto-generated', () => {
      const file1 = createMockFile('first_file.pdf');
      const file2 = createMockFile('second_file.pdf');

      useUploadWizardStore.getState().addFiles([file1, file2]);
      expect(useUploadWizardStore.getState().matterName).toBe('first file');

      useUploadWizardStore.getState().removeFile(0);
      expect(useUploadWizardStore.getState().matterName).toBe('second file');
    });

    it('clears matter name when last file is removed', () => {
      const file = createMockFile('test_file.pdf');

      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().removeFile(0);

      expect(useUploadWizardStore.getState().matterName).toBe('');
    });
  });

  describe('setMatterName', () => {
    it('updates the matter name', () => {
      useUploadWizardStore.getState().setMatterName('New Matter Name');

      expect(useUploadWizardStore.getState().matterName).toBe('New Matter Name');
    });
  });

  describe('setDetectedActs', () => {
    it('sets detected acts', () => {
      const acts: DetectedAct[] = [
        { id: '1', actName: 'Test Act', citationCount: 5, status: 'found' },
      ];

      useUploadWizardStore.getState().setDetectedActs(acts);

      expect(useUploadWizardStore.getState().detectedActs).toEqual(acts);
    });
  });

  describe('startUpload', () => {
    it('sets stage to UPLOADING and loading to true', () => {
      useUploadWizardStore.getState().startUpload();

      expect(useUploadWizardStore.getState().currentStage).toBe('UPLOADING');
      expect(useUploadWizardStore.getState().isLoading).toBe(true);
    });
  });

  describe('setLoading', () => {
    it('updates loading state', () => {
      useUploadWizardStore.getState().setLoading(true);
      expect(useUploadWizardStore.getState().isLoading).toBe(true);

      useUploadWizardStore.getState().setLoading(false);
      expect(useUploadWizardStore.getState().isLoading).toBe(false);
    });
  });

  describe('setError', () => {
    it('sets error message', () => {
      useUploadWizardStore.getState().setError('Test error');
      expect(useUploadWizardStore.getState().error).toBe('Test error');
    });

    it('clears error message', () => {
      useUploadWizardStore.getState().setError('Test error');
      useUploadWizardStore.getState().setError(null);
      expect(useUploadWizardStore.getState().error).toBeNull();
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', () => {
      // Set up some state
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().setMatterName('Test Matter');
      useUploadWizardStore.getState().setError('Error');
      useUploadWizardStore.getState().setLoading(true);

      // Reset
      useUploadWizardStore.getState().reset();

      // Verify all reset
      const state = useUploadWizardStore.getState();
      expect(state.currentStage).toBe('FILE_SELECTION');
      expect(state.files).toEqual([]);
      expect(state.matterName).toBe('');
      expect(state.detectedActs).toEqual([]);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('selectTotalFileSize', () => {
    it('returns sum of file sizes', () => {
      const file1 = createMockFile('test1.pdf', 1000);
      const file2 = createMockFile('test2.pdf', 2000);
      const file3 = createMockFile('test3.pdf', 3000);

      useUploadWizardStore.getState().addFiles([file1, file2, file3]);

      expect(selectTotalFileSize(useUploadWizardStore.getState())).toBe(6000);
    });

    it('returns 0 for empty files', () => {
      expect(selectTotalFileSize(useUploadWizardStore.getState())).toBe(0);
    });
  });

  describe('selectFileCount', () => {
    it('returns number of files', () => {
      const files = [
        createMockFile('test1.pdf'),
        createMockFile('test2.pdf'),
        createMockFile('test3.pdf'),
      ];

      useUploadWizardStore.getState().addFiles(files);

      expect(selectFileCount(useUploadWizardStore.getState())).toBe(3);
    });
  });

  describe('selectActsByStatus', () => {
    beforeEach(() => {
      const acts: DetectedAct[] = [
        { id: '1', actName: 'Found Act 1', citationCount: 5, status: 'found' },
        { id: '2', actName: 'Found Act 2', citationCount: 3, status: 'found' },
        { id: '3', actName: 'Missing Act', citationCount: 8, status: 'missing' },
      ];
      useUploadWizardStore.getState().setDetectedActs(acts);
    });

    it('returns found acts', () => {
      const found = selectActsByStatus(useUploadWizardStore.getState(), 'found');
      expect(found).toHaveLength(2);
      expect(found.every((a) => a.status === 'found')).toBe(true);
    });

    it('returns missing acts', () => {
      const missing = selectActsByStatus(useUploadWizardStore.getState(), 'missing');
      expect(missing).toHaveLength(1);
      expect(missing[0]?.actName).toBe('Missing Act');
    });
  });

  describe('selectIsMatterNameValid', () => {
    it('returns true for valid name', () => {
      useUploadWizardStore.getState().setMatterName('Valid Matter Name');
      expect(selectIsMatterNameValid(useUploadWizardStore.getState())).toBe(true);
    });

    it('returns false for empty name', () => {
      useUploadWizardStore.getState().setMatterName('');
      expect(selectIsMatterNameValid(useUploadWizardStore.getState())).toBe(false);
    });

    it('returns false for whitespace-only name', () => {
      useUploadWizardStore.getState().setMatterName('   ');
      expect(selectIsMatterNameValid(useUploadWizardStore.getState())).toBe(false);
    });

    it('returns false for name over 100 chars', () => {
      const longName = 'a'.repeat(101);
      useUploadWizardStore.getState().setMatterName(longName);
      expect(selectIsMatterNameValid(useUploadWizardStore.getState())).toBe(false);
    });

    it('returns true for name exactly 100 chars', () => {
      const maxName = 'a'.repeat(100);
      useUploadWizardStore.getState().setMatterName(maxName);
      expect(selectIsMatterNameValid(useUploadWizardStore.getState())).toBe(true);
    });
  });

  describe('selectCanStartUpload', () => {
    it('returns true when valid', () => {
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().setMatterName('Valid Name');

      expect(selectCanStartUpload(useUploadWizardStore.getState())).toBe(true);
    });

    it('returns false when no files', () => {
      useUploadWizardStore.getState().setMatterName('Valid Name');
      expect(selectCanStartUpload(useUploadWizardStore.getState())).toBe(false);
    });

    it('returns false when matter name invalid', () => {
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().setMatterName('');

      expect(selectCanStartUpload(useUploadWizardStore.getState())).toBe(false);
    });

    it('returns false when loading', () => {
      const file = createMockFile('test.pdf');
      useUploadWizardStore.getState().addFiles([file]);
      useUploadWizardStore.getState().setMatterName('Valid Name');
      useUploadWizardStore.getState().setLoading(true);

      expect(selectCanStartUpload(useUploadWizardStore.getState())).toBe(false);
    });
  });
});
