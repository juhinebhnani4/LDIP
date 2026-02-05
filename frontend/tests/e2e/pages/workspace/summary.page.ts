import { Page, Locator, expect } from '@playwright/test';
import { WorkspaceBasePage } from './base.page';

/**
 * Page Object Model for the Summary tab
 */
export class SummaryPage extends WorkspaceBasePage {
  // Summary sections
  readonly attentionBanner: Locator;
  readonly partiesSection: Locator;
  readonly petitionerInfo: Locator;
  readonly respondentInfo: Locator;
  readonly subjectMatterSection: Locator;
  readonly currentStatusSection: Locator;
  readonly keyIssuesSection: Locator;

  // Statistics
  readonly matterStatistics: Locator;
  readonly documentCount: Locator;
  readonly entityCount: Locator;
  readonly citationCount: Locator;
  readonly verificationProgress: Locator;

  // Edit controls
  readonly editButtons: Locator;
  readonly saveButton: Locator;
  readonly cancelButton: Locator;

  // Notes
  readonly notesButton: Locator;
  readonly notesDialog: Locator;
  readonly notesTextarea: Locator;

  constructor(page: Page) {
    super(page);

    // Sections
    this.attentionBanner = page.locator('[data-testid="attention-banner"]');
    this.partiesSection = page.locator('[data-testid="parties-section"]');
    this.petitionerInfo = page.locator('[data-testid="petitioner-info"]');
    this.respondentInfo = page.locator('[data-testid="respondent-info"]');
    this.subjectMatterSection = page.locator('[data-testid="subject-matter-section"]');
    this.currentStatusSection = page.locator('[data-testid="current-status-section"]');
    this.keyIssuesSection = page.locator('[data-testid="key-issues-section"]');

    // Statistics
    this.matterStatistics = page.locator('[data-testid="matter-statistics"]');
    this.documentCount = page.locator('[data-testid="document-count"]');
    this.entityCount = page.locator('[data-testid="entity-count"]');
    this.citationCount = page.locator('[data-testid="citation-count"]');
    this.verificationProgress = page.locator('[data-testid="verification-progress"]');

    // Edit controls
    this.editButtons = page.locator('[data-testid="edit-button"]');
    this.saveButton = page.getByRole('button', { name: /save/i });
    this.cancelButton = page.getByRole('button', { name: /cancel/i });

    // Notes
    this.notesButton = page.getByRole('button', { name: /notes/i });
    this.notesDialog = page.locator('[data-testid="notes-dialog"]');
    this.notesTextarea = page.locator('[data-testid="notes-textarea"]');
  }

  /**
   * Navigate to summary tab for a matter
   */
  async gotoSummary(matterId: string) {
    await this.page.goto(`/matter/${matterId}/summary`);
    await this.waitForSummaryLoad();
  }

  /**
   * Wait for summary content to load
   */
  async waitForSummaryLoad() {
    await this.page.waitForSelector('[data-testid="summary-content"]');
  }

  /**
   * Check if attention banner is visible
   */
  async hasAttentionItems(): Promise<boolean> {
    return await this.attentionBanner.isVisible();
  }

  /**
   * Get petitioner name
   */
  async getPetitionerName(): Promise<string> {
    return await this.petitionerInfo.textContent() || '';
  }

  /**
   * Get respondent name
   */
  async getRespondentName(): Promise<string> {
    return await this.respondentInfo.textContent() || '';
  }

  /**
   * Edit parties section
   */
  async editParties(petitioner?: string, respondent?: string) {
    await this.partiesSection.getByRole('button', { name: /edit/i }).click();

    if (petitioner) {
      const petitionerInput = this.page.getByLabel(/petitioner/i);
      await petitionerInput.clear();
      await petitionerInput.fill(petitioner);
    }

    if (respondent) {
      const respondentInput = this.page.getByLabel(/respondent/i);
      await respondentInput.clear();
      await respondentInput.fill(respondent);
    }

    await this.saveButton.click();
  }

  /**
   * Edit subject matter
   */
  async editSubjectMatter(text: string) {
    await this.subjectMatterSection.getByRole('button', { name: /edit/i }).click();
    const textarea = this.subjectMatterSection.locator('textarea');
    await textarea.clear();
    await textarea.fill(text);
    await this.saveButton.click();
  }

  /**
   * Edit current status
   */
  async editCurrentStatus(text: string) {
    await this.currentStatusSection.getByRole('button', { name: /edit/i }).click();
    const textarea = this.currentStatusSection.locator('textarea');
    await textarea.clear();
    await textarea.fill(text);
    await this.saveButton.click();
  }

  /**
   * Get document count from statistics
   */
  async getDocumentCount(): Promise<number> {
    const text = await this.documentCount.textContent();
    return parseInt(text || '0', 10);
  }

  /**
   * Get entity count from statistics
   */
  async getEntityCount(): Promise<number> {
    const text = await this.entityCount.textContent();
    return parseInt(text || '0', 10);
  }

  /**
   * Open notes dialog
   */
  async openNotes() {
    await this.notesButton.click();
    await expect(this.notesDialog).toBeVisible();
  }

  /**
   * Add a note
   */
  async addNote(noteText: string) {
    await this.openNotes();
    await this.notesTextarea.fill(noteText);
    await this.page.getByRole('button', { name: /save|add/i }).click();
  }
}
