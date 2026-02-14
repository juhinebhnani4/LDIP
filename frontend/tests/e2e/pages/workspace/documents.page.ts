import { Page, Locator, expect } from '@playwright/test';
import { WorkspaceBasePage } from './base.page';

/**
 * Page Object Model for the Documents tab
 */
export class DocumentsPage extends WorkspaceBasePage {
  // Header controls
  readonly searchInput: Locator;
  readonly sortSelect: Locator;
  readonly addDocumentButton: Locator;

  // Document list
  readonly documentRows: Locator;
  readonly documentNames: Locator;
  readonly emptyState: Locator;

  // Document row elements
  readonly typeBadges: Locator;
  readonly ocrBadges: Locator;
  readonly processingStatus: Locator;
  readonly actionMenus: Locator;

  // Dialogs
  readonly addDocumentsDialog: Locator;
  readonly renameDialog: Locator;
  readonly deleteDialog: Locator;
  readonly manualReviewDialog: Locator;

  constructor(page: Page) {
    super(page);

    // Header
    this.searchInput = page.getByPlaceholder(/search documents/i);
    this.sortSelect = page.getByRole('combobox', { name: /sort/i });
    this.addDocumentButton = page.getByRole('button', { name: /add document|upload/i });

    // Document list
    this.documentRows = page.locator('[data-testid="document-row"]');
    this.documentNames = page.locator('[data-testid="document-name"]');
    this.emptyState = page.locator('[data-testid="documents-empty-state"]');

    // Row elements
    this.typeBadges = page.locator('[data-testid="document-type-badge"]');
    this.ocrBadges = page.locator('[data-testid="ocr-quality-badge"]');
    this.processingStatus = page.locator('[data-testid="processing-status"]');
    this.actionMenus = page.locator('[data-testid="document-actions"]');

    // Dialogs
    this.addDocumentsDialog = page.locator('[data-testid="add-documents-dialog"]');
    this.renameDialog = page.locator('[data-testid="rename-dialog"]');
    this.deleteDialog = page.locator('[data-testid="delete-dialog"]');
    this.manualReviewDialog = page.locator('[data-testid="manual-review-dialog"]');
  }

  /**
   * Navigate to documents tab for a matter
   */
  async gotoDocuments(matterId: string) {
    await this.page.goto(`/matter/${matterId}/documents`);
    await this.waitForDocumentsLoad();
  }

  /**
   * Wait for documents content to load
   */
  async waitForDocumentsLoad() {
    await this.page.waitForURL(/\/documents/, { timeout: 10000 });
    await this.page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
  }

  /**
   * Get count of documents
   */
  async getDocumentCount(): Promise<number> {
    return await this.documentRows.count();
  }

  /**
   * Search for documents
   */
  async searchDocuments(query: string) {
    await this.searchInput.fill(query);
    await this.page.keyboard.press('Enter');
  }

  /**
   * Clear search
   */
  async clearSearch() {
    await this.searchInput.clear();
  }

  /**
   * Sort documents
   */
  async sortBy(option: 'name' | 'date' | 'type' | 'status') {
    await this.sortSelect.click();
    await this.page.getByRole('option', { name: new RegExp(option, 'i') }).click();
  }

  /**
   * Open add documents dialog
   */
  async openAddDocumentsDialog() {
    await this.addDocumentButton.click();
    await expect(this.addDocumentsDialog).toBeVisible();
  }

  /**
   * Upload more documents
   */
  async uploadMoreDocuments(filePaths: string[]) {
    await this.openAddDocumentsDialog();
    await this.page.locator('input[type="file"]').setInputFiles(filePaths);
    await this.page.getByRole('button', { name: /upload|add/i }).click();
  }

  /**
   * Get a specific document row
   */
  getDocumentRow(documentName: string): Locator {
    return this.documentRows.filter({ hasText: documentName });
  }

  /**
   * Open document actions menu
   */
  async openDocumentActions(documentName: string) {
    const row = this.getDocumentRow(documentName);
    await row.getByRole('button', { name: /more|actions|⋮/i }).click();
  }

  /**
   * Rename a document
   */
  async renameDocument(currentName: string, newName: string) {
    await this.openDocumentActions(currentName);
    await this.page.getByRole('menuitem', { name: /rename/i }).click();

    await expect(this.renameDialog).toBeVisible();
    const input = this.renameDialog.getByRole('textbox');
    await input.clear();
    await input.fill(newName);
    await this.page.getByRole('button', { name: /save|confirm/i }).click();
  }

  /**
   * Delete a document
   */
  async deleteDocument(documentName: string) {
    await this.openDocumentActions(documentName);
    await this.page.getByRole('menuitem', { name: /delete/i }).click();

    await expect(this.deleteDialog).toBeVisible();
    await this.page.getByRole('button', { name: /confirm|delete/i }).click();
  }

  /**
   * Flag document for manual review
   */
  async flagForManualReview(documentName: string, reason?: string) {
    await this.openDocumentActions(documentName);
    await this.page.getByRole('menuitem', { name: /manual review|flag/i }).click();

    await expect(this.manualReviewDialog).toBeVisible();
    if (reason) {
      await this.manualReviewDialog.getByRole('textbox').fill(reason);
    }
    await this.page.getByRole('button', { name: /confirm|flag/i }).click();
  }

  /**
   * Get document status
   */
  async getDocumentStatus(documentName: string): Promise<string> {
    const row = this.getDocumentRow(documentName);
    const status = row.locator('[data-testid="processing-status"]');
    return await status.textContent() || '';
  }

  /**
   * Get document type
   */
  async getDocumentType(documentName: string): Promise<string> {
    const row = this.getDocumentRow(documentName);
    const badge = row.locator('[data-testid="document-type-badge"]');
    return await badge.textContent() || '';
  }

  /**
   * Get OCR quality
   */
  async getOCRQuality(documentName: string): Promise<string> {
    const row = this.getDocumentRow(documentName);
    const badge = row.locator('[data-testid="ocr-quality-badge"]');
    return await badge.textContent() || '';
  }

  /**
   * Check if any documents are processing
   */
  async hasProcessingDocuments(): Promise<boolean> {
    const processingCount = await this.processingStatus.filter({ hasText: /processing|pending/i }).count();
    return processingCount > 0;
  }

  /**
   * Wait for all documents to finish processing
   */
  async waitForAllDocumentsProcessed(timeout: number = 120000) {
    await expect(async () => {
      const hasProcessing = await this.hasProcessingDocuments();
      expect(hasProcessing).toBe(false);
    }).toPass({ timeout });
  }
}
