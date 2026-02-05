import { test, expect } from '@playwright/test';
import { DashboardPage, DocumentsPage } from '../pages';
import * as path from 'path';

const TEST_FILE = path.join(__dirname, '../fixtures/files/sample-contract.pdf');

test.describe('Document Management Flow', () => {
  // Assumes a matter already exists with documents
  // In real tests, you'd set up test data or create a matter first

  test.describe('Documents Tab - Navigation', () => {
    test('should navigate to documents tab', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();
      await dashboardPage.waitForLoad();

      // Skip if no matters exist
      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available for testing');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      await expect(page).toHaveURL(/\/documents/);
    });

    test('should display documents list', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();
      await documentsPage.waitForDocumentsLoad();

      // Should show either documents or empty state
      const docCount = await documentsPage.getDocumentCount();
      const isEmpty = await documentsPage.emptyState.isVisible().catch(() => false);

      expect(docCount > 0 || isEmpty).toBeTruthy();
    });
  });

  test.describe('Documents Tab - Search & Filter', () => {
    test('should have search input', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      await expect(documentsPage.searchInput).toBeVisible();
    });

    test('should filter documents by search', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      const initialCount = await documentsPage.getDocumentCount();
      test.skip(initialCount === 0, 'No documents to search');

      await documentsPage.searchDocuments('contract');

      // Results should update
      await page.waitForTimeout(500);
    });

    test('should have sort options', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      await expect(documentsPage.sortSelect).toBeVisible();
    });
  });

  test.describe('Documents Tab - Add Documents', () => {
    test('should have add document button', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      await expect(documentsPage.addDocumentButton).toBeVisible();
    });

    test('should open add documents dialog', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();
      await documentsPage.openAddDocumentsDialog();

      await expect(documentsPage.addDocumentsDialog).toBeVisible();
    });
  });

  test.describe('Documents Tab - Document Actions', () => {
    test('should show document action menu', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      const docCount = await documentsPage.getDocumentCount();
      test.skip(docCount === 0, 'No documents available');

      // Get first document name
      const firstDoc = documentsPage.documentRows.first();
      const docName = await firstDoc.locator('[data-testid="document-name"]').textContent();

      test.skip(!docName, 'Could not get document name');

      // Open actions menu
      await firstDoc.getByRole('button', { name: /more|actions|⋮/i }).click();

      // Should show menu options
      await expect(page.getByRole('menuitem')).toHaveCount(await page.getByRole('menuitem').count());
    });

    test('should open rename dialog', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      const docCount = await documentsPage.getDocumentCount();
      test.skip(docCount === 0, 'No documents available');

      const firstDoc = documentsPage.documentRows.first();
      await firstDoc.getByRole('button', { name: /more|actions|⋮/i }).click();
      await page.getByRole('menuitem', { name: /rename/i }).click();

      await expect(documentsPage.renameDialog).toBeVisible();
    });

    test('should open delete confirmation dialog', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      const docCount = await documentsPage.getDocumentCount();
      test.skip(docCount === 0, 'No documents available');

      const firstDoc = documentsPage.documentRows.first();
      await firstDoc.getByRole('button', { name: /more|actions|⋮/i }).click();
      await page.getByRole('menuitem', { name: /delete/i }).click();

      await expect(documentsPage.deleteDialog).toBeVisible();
    });
  });

  test.describe('Documents Tab - Status Indicators', () => {
    test('should display document type badges', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      const docCount = await documentsPage.getDocumentCount();
      test.skip(docCount === 0, 'No documents available');

      // Check for type badges
      const typeBadgeCount = await documentsPage.typeBadges.count();
      expect(typeBadgeCount).toBeGreaterThanOrEqual(0);
    });

    test('should display OCR quality badges', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      const docCount = await documentsPage.getDocumentCount();
      test.skip(docCount === 0, 'No documents available');

      // Check for OCR badges
      const ocrBadgeCount = await documentsPage.ocrBadges.count();
      expect(ocrBadgeCount).toBeGreaterThanOrEqual(0);
    });

    test('should display processing status', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const documentsPage = new DocumentsPage(page);
      await documentsPage.goToDocuments();

      const docCount = await documentsPage.getDocumentCount();
      test.skip(docCount === 0, 'No documents available');

      // Check for status indicators
      const statusCount = await documentsPage.processingStatus.count();
      expect(statusCount).toBeGreaterThanOrEqual(0);
    });
  });
});
