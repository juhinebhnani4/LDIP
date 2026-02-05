import { Page, expect } from '@playwright/test';
import * as path from 'path';

/**
 * Test document paths for E2E testing
 * Place test PDFs in tests/e2e/fixtures/files/
 */
export const TEST_DOCUMENTS = {
  samplePdf: path.join(__dirname, 'files', 'sample-contract.pdf'),
  sampleAct: path.join(__dirname, 'files', 'sample-act.pdf'),
  largePdf: path.join(__dirname, 'files', 'large-document.pdf'),
  poorOcrPdf: path.join(__dirname, 'files', 'poor-ocr-sample.pdf'),
};

/**
 * Document upload and management helper functions
 */
export class DocumentHelper {
  constructor(private page: Page) {}

  /**
   * Upload files via the file drop zone
   */
  async uploadFiles(filePaths: string[]) {
    // Find the file input (may be hidden)
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePaths);
  }

  /**
   * Upload files via drag and drop simulation
   */
  async uploadViaDropZone(filePaths: string[]) {
    const dropZone = this.page.locator('[data-testid="file-drop-zone"], [data-testid="dropzone"]');

    // Set files on the hidden input
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePaths);
  }

  /**
   * Wait for upload to complete
   */
  async waitForUploadComplete(timeout: number = 60000) {
    // Wait for processing screen or completion indicator
    await this.page.waitForSelector('[data-testid="upload-complete"], [data-testid="processing-complete"]', {
      timeout,
    });
  }

  /**
   * Wait for document processing to complete
   */
  async waitForProcessingComplete(timeout: number = 120000) {
    await this.page.waitForSelector('[data-testid="processing-complete"], [data-testid="completion-screen"]', {
      timeout,
    });
  }

  /**
   * Set matter name during upload
   */
  async setMatterName(name: string) {
    const matterNameInput = this.page.getByLabel(/matter name/i).or(
      this.page.locator('[data-testid="matter-name-input"]')
    );
    await matterNameInput.clear();
    await matterNameInput.fill(name);
  }

  /**
   * Proceed to next step in upload wizard
   */
  async proceedToNextStep() {
    await this.page.getByRole('button', { name: /next|continue|proceed/i }).click();
  }

  /**
   * Skip act discovery step
   */
  async skipActDiscovery() {
    const skipButton = this.page.getByRole('button', { name: /skip|no thanks|later/i });
    if (await skipButton.isVisible()) {
      await skipButton.click();
    }
  }

  /**
   * Remove a file from the review list
   */
  async removeFile(fileName: string) {
    const fileRow = this.page.locator('[data-testid="file-row"]').filter({ hasText: fileName });
    await fileRow.getByRole('button', { name: /remove|delete/i }).click();
  }

  /**
   * Get list of uploaded files in review
   */
  async getUploadedFiles(): Promise<string[]> {
    const fileRows = this.page.locator('[data-testid="file-row"], [data-testid="file-item"]');
    const count = await fileRows.count();
    const files: string[] = [];

    for (let i = 0; i < count; i++) {
      const text = await fileRows.nth(i).textContent();
      if (text) files.push(text);
    }

    return files;
  }

  /**
   * Navigate to documents tab
   */
  async goToDocumentsTab() {
    await this.page.getByRole('tab', { name: /documents/i }).click();
    await this.page.waitForSelector('[data-testid="documents-content"]');
  }

  /**
   * Add more documents to existing matter
   */
  async addMoreDocuments() {
    await this.page.getByRole('button', { name: /add document|upload/i }).click();
    await this.page.waitForSelector('[data-testid="add-documents-dialog"]');
  }

  /**
   * Rename a document
   */
  async renameDocument(currentName: string, newName: string) {
    const docRow = this.page.locator('[data-testid="document-row"]').filter({ hasText: currentName });
    await docRow.getByRole('button', { name: /more|actions/i }).click();
    await this.page.getByRole('menuitem', { name: /rename/i }).click();

    const input = this.page.getByRole('textbox', { name: /name/i });
    await input.clear();
    await input.fill(newName);
    await this.page.getByRole('button', { name: /save|confirm/i }).click();
  }

  /**
   * Delete a document
   */
  async deleteDocument(documentName: string) {
    const docRow = this.page.locator('[data-testid="document-row"]').filter({ hasText: documentName });
    await docRow.getByRole('button', { name: /more|actions/i }).click();
    await this.page.getByRole('menuitem', { name: /delete/i }).click();

    // Confirm deletion
    await this.page.getByRole('button', { name: /confirm|delete/i }).click();
  }

  /**
   * Flag document for manual review
   */
  async flagForManualReview(documentName: string) {
    const docRow = this.page.locator('[data-testid="document-row"]').filter({ hasText: documentName });
    await docRow.getByRole('button', { name: /more|actions/i }).click();
    await this.page.getByRole('menuitem', { name: /manual review|flag/i }).click();
  }

  /**
   * Get document count in documents tab
   */
  async getDocumentCount(): Promise<number> {
    return await this.page.locator('[data-testid="document-row"]').count();
  }

  /**
   * Check document processing status
   */
  async getDocumentStatus(documentName: string): Promise<string> {
    const docRow = this.page.locator('[data-testid="document-row"]').filter({ hasText: documentName });
    const statusBadge = docRow.locator('[data-testid="processing-status"]');
    return await statusBadge.textContent() || '';
  }
}

/**
 * Factory function for creating document helper
 */
export function createDocumentHelper(page: Page): DocumentHelper {
  return new DocumentHelper(page);
}
