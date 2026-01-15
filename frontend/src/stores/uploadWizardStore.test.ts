import { describe, it, expect, beforeEach } from 'vitest';
import {
  useUploadWizardStore,
  selectTotalFileSize,
  selectFileCount,
  selectActsByStatus,
  selectIsMatterNameValid,
  selectCanStartUpload,
  selectUploadComplete,
  selectDiscoveriesByType,
  selectCurrentStageName,
  selectCurrentStageNumber,
  selectCompletedUploadsCount,
  selectFailedUploadsCount,
  selectHasFailedUploads,
  selectUploadProgressArray,
} from './uploadWizardStore';
import type { DetectedAct, UploadProgress, LiveDiscovery } from '@/types/upload';

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

  // ==========================================================================
  // Processing State Tests (Story 9-5)
  // ==========================================================================

  describe('processing state', () => {
    describe('initial processing state', () => {
      it('starts with empty upload progress', () => {
        expect(useUploadWizardStore.getState().uploadProgress.size).toBe(0);
      });

      it('starts with null processing stage', () => {
        expect(useUploadWizardStore.getState().processingStage).toBeNull();
      });

      it('starts with 0% overall progress', () => {
        expect(useUploadWizardStore.getState().overallProgressPct).toBe(0);
      });

      it('starts with empty live discoveries', () => {
        expect(useUploadWizardStore.getState().liveDiscoveries).toEqual([]);
      });

      it('starts with null matter ID', () => {
        expect(useUploadWizardStore.getState().matterId).toBeNull();
      });

      it('starts with empty failed uploads', () => {
        expect(useUploadWizardStore.getState().failedUploads.size).toBe(0);
      });
    });

    describe('setUploadProgress', () => {
      it('sets upload progress for a file', () => {
        const progress: UploadProgress = {
          fileName: 'test.pdf',
          fileSize: 1024,
          progressPct: 50,
          status: 'uploading',
        };

        useUploadWizardStore.getState().setUploadProgress('test.pdf', progress);

        const stored = useUploadWizardStore.getState().uploadProgress.get('test.pdf');
        expect(stored).toEqual(progress);
      });

      it('updates existing progress', () => {
        const initial: UploadProgress = {
          fileName: 'test.pdf',
          fileSize: 1024,
          progressPct: 25,
          status: 'uploading',
        };
        const updated: UploadProgress = {
          fileName: 'test.pdf',
          fileSize: 1024,
          progressPct: 75,
          status: 'uploading',
        };

        useUploadWizardStore.getState().setUploadProgress('test.pdf', initial);
        useUploadWizardStore.getState().setUploadProgress('test.pdf', updated);

        const stored = useUploadWizardStore.getState().uploadProgress.get('test.pdf');
        expect(stored?.progressPct).toBe(75);
      });
    });

    describe('setProcessingStage', () => {
      it('sets the processing stage', () => {
        useUploadWizardStore.getState().setProcessingStage('OCR');
        expect(useUploadWizardStore.getState().processingStage).toBe('OCR');
      });

      it('can set stage to null', () => {
        useUploadWizardStore.getState().setProcessingStage('OCR');
        useUploadWizardStore.getState().setProcessingStage(null);
        expect(useUploadWizardStore.getState().processingStage).toBeNull();
      });
    });

    describe('addLiveDiscovery', () => {
      it('adds discovery to array', () => {
        const discovery: LiveDiscovery = {
          id: '1',
          type: 'entity',
          count: 5,
          details: [{ name: 'Test', role: 'Role' }],
          timestamp: new Date(),
        };

        useUploadWizardStore.getState().addLiveDiscovery(discovery);

        expect(useUploadWizardStore.getState().liveDiscoveries).toHaveLength(1);
        expect(useUploadWizardStore.getState().liveDiscoveries[0]).toEqual(discovery);
      });

      it('appends multiple discoveries', () => {
        const discovery1: LiveDiscovery = {
          id: '1',
          type: 'entity',
          count: 5,
          details: [],
          timestamp: new Date(),
        };
        const discovery2: LiveDiscovery = {
          id: '2',
          type: 'date',
          count: 10,
          details: { earliest: new Date(), latest: new Date(), count: 10 },
          timestamp: new Date(),
        };

        useUploadWizardStore.getState().addLiveDiscovery(discovery1);
        useUploadWizardStore.getState().addLiveDiscovery(discovery2);

        expect(useUploadWizardStore.getState().liveDiscoveries).toHaveLength(2);
      });
    });

    describe('setMatterId', () => {
      it('sets matter ID', () => {
        useUploadWizardStore.getState().setMatterId('matter-123');
        expect(useUploadWizardStore.getState().matterId).toBe('matter-123');
      });

      it('can clear matter ID', () => {
        useUploadWizardStore.getState().setMatterId('matter-123');
        useUploadWizardStore.getState().setMatterId(null);
        expect(useUploadWizardStore.getState().matterId).toBeNull();
      });
    });

    describe('setOverallProgress', () => {
      it('sets overall progress percentage', () => {
        useUploadWizardStore.getState().setOverallProgress(67);
        expect(useUploadWizardStore.getState().overallProgressPct).toBe(67);
      });
    });

    describe('setUploadFailed', () => {
      it('marks file as failed', () => {
        useUploadWizardStore.getState().setUploadFailed('test.pdf', 'Network error');

        expect(useUploadWizardStore.getState().failedUploads.get('test.pdf')).toBe('Network error');
      });

      it('updates upload progress status to error', () => {
        const progress: UploadProgress = {
          fileName: 'test.pdf',
          fileSize: 1024,
          progressPct: 50,
          status: 'uploading',
        };
        useUploadWizardStore.getState().setUploadProgress('test.pdf', progress);
        useUploadWizardStore.getState().setUploadFailed('test.pdf', 'Failed');

        const stored = useUploadWizardStore.getState().uploadProgress.get('test.pdf');
        expect(stored?.status).toBe('error');
        expect(stored?.errorMessage).toBe('Failed');
      });
    });

    describe('clearProcessingState', () => {
      it('clears all processing state', () => {
        // Set up some processing state
        useUploadWizardStore.getState().setUploadProgress('test.pdf', {
          fileName: 'test.pdf',
          fileSize: 1024,
          progressPct: 100,
          status: 'complete',
        });
        useUploadWizardStore.getState().setProcessingStage('OCR');
        useUploadWizardStore.getState().setOverallProgress(50);
        useUploadWizardStore.getState().addLiveDiscovery({
          id: '1',
          type: 'entity',
          count: 1,
          details: [],
          timestamp: new Date(),
        });
        useUploadWizardStore.getState().setMatterId('matter-123');
        useUploadWizardStore.getState().setUploadFailed('bad.pdf', 'Error');

        // Clear
        useUploadWizardStore.getState().clearProcessingState();

        // Verify all cleared
        const state = useUploadWizardStore.getState();
        expect(state.uploadProgress.size).toBe(0);
        expect(state.processingStage).toBeNull();
        expect(state.overallProgressPct).toBe(0);
        expect(state.liveDiscoveries).toEqual([]);
        expect(state.matterId).toBeNull();
        expect(state.failedUploads.size).toBe(0);
      });
    });
  });

  describe('processing selectors', () => {
    describe('selectUploadComplete', () => {
      it('returns false when no files', () => {
        expect(selectUploadComplete(useUploadWizardStore.getState())).toBe(false);
      });

      it('returns false when upload incomplete', () => {
        const file = createMockFile('test.pdf');
        useUploadWizardStore.getState().addFiles([file]);
        useUploadWizardStore.getState().setUploadProgress('test.pdf', {
          fileName: 'test.pdf',
          fileSize: 1024,
          progressPct: 50,
          status: 'uploading',
        });

        expect(selectUploadComplete(useUploadWizardStore.getState())).toBe(false);
      });

      it('returns true when all uploads complete', () => {
        const file1 = createMockFile('test1.pdf');
        const file2 = createMockFile('test2.pdf');
        useUploadWizardStore.getState().addFiles([file1, file2]);
        useUploadWizardStore.getState().setUploadProgress('test1.pdf', {
          fileName: 'test1.pdf',
          fileSize: 1024,
          progressPct: 100,
          status: 'complete',
        });
        useUploadWizardStore.getState().setUploadProgress('test2.pdf', {
          fileName: 'test2.pdf',
          fileSize: 1024,
          progressPct: 100,
          status: 'complete',
        });

        expect(selectUploadComplete(useUploadWizardStore.getState())).toBe(true);
      });
    });

    describe('selectDiscoveriesByType', () => {
      it('filters discoveries by type', () => {
        useUploadWizardStore.getState().addLiveDiscovery({
          id: '1',
          type: 'entity',
          count: 5,
          details: [],
          timestamp: new Date(),
        });
        useUploadWizardStore.getState().addLiveDiscovery({
          id: '2',
          type: 'date',
          count: 10,
          details: { earliest: new Date(), latest: new Date(), count: 10 },
          timestamp: new Date(),
        });
        useUploadWizardStore.getState().addLiveDiscovery({
          id: '3',
          type: 'entity',
          count: 3,
          details: [],
          timestamp: new Date(),
        });

        const entities = selectDiscoveriesByType(useUploadWizardStore.getState(), 'entity');
        expect(entities).toHaveLength(2);
        expect(entities.every((d) => d.type === 'entity')).toBe(true);
      });
    });

    describe('selectCurrentStageName', () => {
      it('returns empty string when no stage', () => {
        expect(selectCurrentStageName(useUploadWizardStore.getState())).toBe('');
      });

      it('returns human-readable stage name', () => {
        useUploadWizardStore.getState().setProcessingStage('ENTITY_EXTRACTION');
        expect(selectCurrentStageName(useUploadWizardStore.getState())).toBe(
          'Extracting entities & relationships'
        );
      });
    });

    describe('selectCurrentStageNumber', () => {
      it('returns 0 when no stage', () => {
        expect(selectCurrentStageNumber(useUploadWizardStore.getState())).toBe(0);
      });

      it('returns correct stage number', () => {
        useUploadWizardStore.getState().setProcessingStage('UPLOADING');
        expect(selectCurrentStageNumber(useUploadWizardStore.getState())).toBe(1);

        useUploadWizardStore.getState().setProcessingStage('OCR');
        expect(selectCurrentStageNumber(useUploadWizardStore.getState())).toBe(2);

        useUploadWizardStore.getState().setProcessingStage('INDEXING');
        expect(selectCurrentStageNumber(useUploadWizardStore.getState())).toBe(5);
      });
    });

    describe('selectCompletedUploadsCount', () => {
      it('returns count of completed uploads', () => {
        useUploadWizardStore.getState().setUploadProgress('file1.pdf', {
          fileName: 'file1.pdf',
          fileSize: 1024,
          progressPct: 100,
          status: 'complete',
        });
        useUploadWizardStore.getState().setUploadProgress('file2.pdf', {
          fileName: 'file2.pdf',
          fileSize: 1024,
          progressPct: 50,
          status: 'uploading',
        });
        useUploadWizardStore.getState().setUploadProgress('file3.pdf', {
          fileName: 'file3.pdf',
          fileSize: 1024,
          progressPct: 100,
          status: 'complete',
        });

        expect(selectCompletedUploadsCount(useUploadWizardStore.getState())).toBe(2);
      });
    });

    describe('selectFailedUploadsCount', () => {
      it('returns count of failed uploads', () => {
        useUploadWizardStore.getState().setUploadFailed('bad1.pdf', 'Error');
        useUploadWizardStore.getState().setUploadFailed('bad2.pdf', 'Error');

        expect(selectFailedUploadsCount(useUploadWizardStore.getState())).toBe(2);
      });
    });

    describe('selectHasFailedUploads', () => {
      it('returns false when no failures', () => {
        expect(selectHasFailedUploads(useUploadWizardStore.getState())).toBe(false);
      });

      it('returns true when there are failures', () => {
        useUploadWizardStore.getState().setUploadFailed('bad.pdf', 'Error');
        expect(selectHasFailedUploads(useUploadWizardStore.getState())).toBe(true);
      });
    });

    describe('selectUploadProgressArray', () => {
      it('converts Map to array', () => {
        useUploadWizardStore.getState().setUploadProgress('file1.pdf', {
          fileName: 'file1.pdf',
          fileSize: 1024,
          progressPct: 100,
          status: 'complete',
        });
        useUploadWizardStore.getState().setUploadProgress('file2.pdf', {
          fileName: 'file2.pdf',
          fileSize: 2048,
          progressPct: 50,
          status: 'uploading',
        });

        const array = selectUploadProgressArray(useUploadWizardStore.getState());
        expect(Array.isArray(array)).toBe(true);
        expect(array).toHaveLength(2);
      });
    });
  });
});
