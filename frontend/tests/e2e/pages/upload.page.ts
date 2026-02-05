import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Upload Wizard pages
 */
export class UploadPage {
  readonly page: Page;

  // File selection stage
  readonly fileDropZone: Locator;
  readonly fileInput: Locator;
  readonly browseButton: Locator;

  // Review stage
  readonly matterNameInput: Locator;
  readonly fileList: Locator;
  readonly fileRows: Locator;
  readonly nextButton: Locator;
  readonly backButton: Locator;

  // Act discovery stage
  readonly actDiscoveryModal: Locator;
  readonly skipActDiscoveryButton: Locator;
  readonly uploadActsButton: Locator;
  readonly detectedActsList: Locator;

  // Processing stage
  readonly processingScreen: Locator;
  readonly progressBars: Locator;
  readonly processingStatus: Locator;
  readonly completionScreen: Locator;
  readonly goToMatterButton: Locator;

  // Wizard navigation
  readonly wizardSteps: Locator;
  readonly currentStep: Locator;

  constructor(page: Page) {
    this.page = page;

    // File selection - updated with actual data-testid selectors
    this.fileDropZone = page.locator('[data-testid="file-drop-zone"]');
    this.fileInput = page.locator('[data-testid="file-input"]');
    this.browseButton = page.locator('[data-testid="file-browse-button"]');

    // Review - updated with actual data-testid selectors
    this.matterNameInput = page.locator('[data-testid="matter-name-input"]');
    this.fileList = page.locator('[data-testid="file-review-list"]');
    this.fileRows = page.locator('[data-testid="file-review-list-items"] li');
    this.nextButton = page.locator('[data-testid="upload-wizard-start-button"]');
    this.backButton = page.locator('[data-testid="upload-wizard-cancel-button"]');

    // Act discovery
    this.actDiscoveryModal = page.locator('[data-testid="act-discovery-modal"]');
    this.skipActDiscoveryButton = page.getByRole('button', { name: /skip|no thanks|later/i });
    this.uploadActsButton = page.getByRole('button', { name: /upload acts/i });
    this.detectedActsList = page.locator('[data-testid="detected-acts"]');

    // Processing
    this.processingScreen = page.locator('[data-testid="processing-screen"]');
    this.progressBars = page.locator('[data-testid="progress-bar"], [role="progressbar"]');
    this.processingStatus = page.locator('[data-testid="processing-status"]');
    // CompletionScreen uses role="status" with aria-label="Processing complete"
    this.completionScreen = page.locator('[role="status"][aria-label="Processing complete"]');
    this.goToMatterButton = page.getByRole('button', { name: /go to.*workspace.*now|go to matter|view matter|open matter/i });

    // Wizard
    this.wizardSteps = page.locator('[data-testid="wizard-step"]');
    this.currentStep = page.locator('[data-testid="wizard-step"][aria-current="step"]');
  }

  /**
   * Navigate to upload page
   */
  async goto() {
    await this.page.goto('/upload');
    await expect(this.page).toHaveURL(/\/upload/);
  }

  /**
   * Upload files using the file input
   */
  async uploadFiles(filePaths: string[]) {
    await this.fileInput.setInputFiles(filePaths);
  }

  /**
   * Set the matter name
   */
  async setMatterName(name: string) {
    await this.matterNameInput.clear();
    await this.matterNameInput.fill(name);
  }

  /**
   * Get the current matter name
   */
  async getMatterName(): Promise<string> {
    return await this.matterNameInput.inputValue();
  }

  /**
   * Get count of files in the list
   */
  async getFileCount(): Promise<number> {
    return await this.fileRows.count();
  }

  /**
   * Remove a file from the list
   */
  async removeFile(fileName: string) {
    const fileRow = this.fileRows.filter({ hasText: fileName });
    await fileRow.getByRole('button', { name: /remove|delete|×/i }).click();
  }

  /**
   * Proceed to next step
   */
  async clickNext() {
    await this.nextButton.click();
  }

  /**
   * Go back to previous step
   */
  async clickBack() {
    await this.backButton.click();
  }

  /**
   * Skip act discovery
   */
  async skipActDiscovery() {
    if (await this.skipActDiscoveryButton.isVisible()) {
      await this.skipActDiscoveryButton.click();
    }
  }

  /**
   * Wait for processing to complete
   */
  async waitForProcessingComplete(timeout: number = 120000) {
    await this.completionScreen.waitFor({ state: 'visible', timeout });
  }

  /**
   * Navigate to the created matter
   */
  async goToMatter() {
    await this.goToMatterButton.click();
    await this.page.waitForURL(/\/matter\/[a-f0-9-]+/);
  }

  /**
   * Complete the full upload flow
   */
  async completeUploadFlow(filePaths: string[], matterName?: string) {
    // Step 1: Select files
    await this.uploadFiles(filePaths);

    // Step 2: Review and set name
    await this.clickNext();
    if (matterName) {
      await this.setMatterName(matterName);
    }

    // Step 3: Proceed (may trigger act discovery)
    await this.clickNext();

    // Skip act discovery if shown
    await this.skipActDiscovery();

    // Step 4: Wait for processing
    await this.waitForProcessingComplete();
  }

  /**
   * Check if currently in file selection stage
   */
  async isInFileSelectionStage(): Promise<boolean> {
    return await this.fileDropZone.isVisible();
  }

  /**
   * Check if currently in review stage
   */
  async isInReviewStage(): Promise<boolean> {
    return await this.matterNameInput.isVisible();
  }

  /**
   * Check if currently in processing stage
   */
  async isInProcessingStage(): Promise<boolean> {
    return await this.processingScreen.isVisible();
  }

  /**
   * Get current processing progress percentage
   */
  async getProcessingProgress(): Promise<number> {
    const progressBar = this.progressBars.first();
    const value = await progressBar.getAttribute('aria-valuenow');
    return value ? parseInt(value, 10) : 0;
  }

  /**
   * Get processing status text
   */
  async getProcessingStatusText(): Promise<string> {
    return await this.processingStatus.textContent() || '';
  }
}
