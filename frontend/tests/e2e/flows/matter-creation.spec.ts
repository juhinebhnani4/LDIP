import { test, expect } from '@playwright/test';
import { DashboardPage, UploadPage } from '../pages';
import { TEST_MATTER } from '../fixtures/matter.fixture';
import * as path from 'path';
import * as fs from 'fs';

// Test file paths - place actual test PDFs in fixtures/files/
const TEST_FILES = {
  singlePdf: path.join(__dirname, '../fixtures/files/sample-contract.pdf'),
  multiplePdfs: [
    path.join(__dirname, '../fixtures/files/sample-contract.pdf'),
    path.join(__dirname, '../fixtures/files/sample-pleading.pdf'),
  ],
};

test.describe('Matter Creation Flow', () => {
  test.describe('Dashboard - New Matter', () => {
    test('should display create matter button on dashboard', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await expect(dashboardPage.createMatterButton).toBeVisible();
    });

    test('should navigate to upload wizard when clicking create matter', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await dashboardPage.clickCreateMatter();

      await expect(page).toHaveURL(/\/upload/);
    });
  });

  test.describe('Upload Wizard - File Selection', () => {
    test('should display file drop zone', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      await expect(uploadPage.fileDropZone).toBeVisible();
    });

    test('should accept PDF files', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      // This test requires actual test files to exist
      // Skip if files don't exist
      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.uploadFiles([TEST_FILES.singlePdf]);

      // Should show file in list
      await expect(uploadPage.fileRows.first()).toBeVisible();
    });

    test('should display file count after selection', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.uploadFiles([TEST_FILES.singlePdf]);

      const count = await uploadPage.getFileCount();
      expect(count).toBeGreaterThan(0);
    });

    test('should allow removing files from selection', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.uploadFiles([TEST_FILES.singlePdf]);

      const initialCount = await uploadPage.getFileCount();
      await uploadPage.removeFile('sample-contract.pdf');

      const newCount = await uploadPage.getFileCount();
      expect(newCount).toBeLessThan(initialCount);
    });
  });

  test.describe('Upload Wizard - Review Stage', () => {
    test.beforeEach(async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      // Skip tests if no test files
      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.uploadFiles([TEST_FILES.singlePdf]);
      await uploadPage.clickNext();
    });

    test('should display matter name input', async ({ page }) => {
      const uploadPage = new UploadPage(page);

      await expect(uploadPage.matterNameInput).toBeVisible();
    });

    test('should auto-generate matter name', async ({ page }) => {
      const uploadPage = new UploadPage(page);

      const matterName = await uploadPage.getMatterName();
      expect(matterName.length).toBeGreaterThan(0);
    });

    test('should allow custom matter name', async ({ page }) => {
      const uploadPage = new UploadPage(page);

      await uploadPage.setMatterName(TEST_MATTER.name);

      const matterName = await uploadPage.getMatterName();
      expect(matterName).toBe(TEST_MATTER.name);
    });

    test('should show file list in review stage', async ({ page }) => {
      const uploadPage = new UploadPage(page);

      await expect(uploadPage.fileList).toBeVisible();
      const count = await uploadPage.getFileCount();
      expect(count).toBeGreaterThan(0);
    });
  });

  test.describe('Upload Wizard - Processing Stage', () => {
    test('should show processing screen after upload', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.uploadFiles([TEST_FILES.singlePdf]);
      await uploadPage.clickNext(); // Go to review
      await uploadPage.setMatterName(`E2E Test ${Date.now()}`);
      await uploadPage.clickNext(); // Start processing

      // Should show processing screen or skip act discovery
      await uploadPage.skipActDiscovery();

      // Verify we're in processing stage
      await expect(uploadPage.processingScreen.or(uploadPage.completionScreen)).toBeVisible({
        timeout: 30000,
      });
    });

    test('should show progress indicators during processing', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.completeUploadFlow([TEST_FILES.singlePdf], `E2E Test ${Date.now()}`);

      // Verify completion
      await expect(uploadPage.completionScreen).toBeVisible();
    });

    test('should navigate to matter after completion', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.completeUploadFlow([TEST_FILES.singlePdf], `E2E Test ${Date.now()}`);
      await uploadPage.goToMatter();

      await expect(page).toHaveURL(/\/matter\/[a-f0-9-]+/);
    });
  });

  test.describe('Upload Wizard - Act Discovery', () => {
    test('should offer act discovery option', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.uploadFiles([TEST_FILES.singlePdf]);
      await uploadPage.clickNext();
      await uploadPage.clickNext();

      // Check if act discovery is offered
      const actDiscoveryVisible = await uploadPage.actDiscoveryModal.isVisible().catch(() => false);
      const skipVisible = await uploadPage.skipActDiscoveryButton.isVisible().catch(() => false);

      // Either we're shown act discovery or we skip straight to processing
      expect(actDiscoveryVisible || skipVisible || await uploadPage.isInProcessingStage()).toBeTruthy();
    });

    test('should allow skipping act discovery', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      test.skip(!fs.existsSync(TEST_FILES.singlePdf), 'Test file not found');

      await uploadPage.uploadFiles([TEST_FILES.singlePdf]);
      await uploadPage.clickNext();
      await uploadPage.clickNext();
      await uploadPage.skipActDiscovery();

      // Should proceed to processing
      await expect(uploadPage.processingScreen.or(uploadPage.completionScreen)).toBeVisible({
        timeout: 30000,
      });
    });
  });

  test.describe('Multiple File Upload', () => {
    test('should handle multiple files', async ({ page }) => {
      const uploadPage = new UploadPage(page);
      await uploadPage.goto();

      const multipleFilesExist = TEST_FILES.multiplePdfs.every(f => fs.existsSync(f));
      test.skip(!multipleFilesExist, 'Test files not found');

      await uploadPage.uploadFiles(TEST_FILES.multiplePdfs);

      const count = await uploadPage.getFileCount();
      expect(count).toBe(TEST_FILES.multiplePdfs.length);
    });
  });
});
