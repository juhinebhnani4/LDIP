import { Page, Locator, expect } from '@playwright/test';
import { WorkspaceBasePage } from './base.page';

/**
 * Page Object Model for the Citations tab
 */
export class CitationsPage extends WorkspaceBasePage {
  // Attention banner
  readonly attentionBanner: Locator;
  readonly missingActsAlert: Locator;
  readonly unverifiedAlert: Locator;

  // Tab controls
  readonly byActTab: Locator;
  readonly byDocumentTab: Locator;

  // Views
  readonly byActView: Locator;
  readonly byDocumentView: Locator;

  // Citation elements
  readonly actGroups: Locator;
  readonly citationCards: Locator;
  readonly verificationBadges: Locator;

  // Missing acts
  readonly missingActCards: Locator;
  readonly uploadActButton: Locator;
  readonly skipActButton: Locator;

  // Act discovery
  readonly actDiscoveryModal: Locator;
  readonly actUploadDropzone: Locator;
  readonly actDiscoveryTrigger: Locator;

  // Split view
  readonly splitViewButton: Locator;
  readonly pdfSplitView: Locator;
  readonly splitViewHeader: Locator;
  readonly splitViewClose: Locator;

  // Verification
  readonly verifyButton: Locator;
  readonly batchVerifyButton: Locator;

  // Empty state
  readonly emptyState: Locator;

  constructor(page: Page) {
    super(page);

    // Attention
    this.attentionBanner = page.locator('[data-testid="citations-attention-banner"]');
    this.missingActsAlert = page.locator('[data-testid="missing-acts-alert"]');
    this.unverifiedAlert = page.locator('[data-testid="unverified-alert"]');

    // Tabs
    this.byActTab = page.getByRole('tab', { name: /by act/i });
    this.byDocumentTab = page.getByRole('tab', { name: /by document/i });

    // Views
    this.byActView = page.locator('[data-testid="citations-by-act-view"]');
    this.byDocumentView = page.locator('[data-testid="citations-by-document-view"]');

    // Citations
    this.actGroups = page.locator('[data-testid="act-group"]');
    this.citationCards = page.locator('[data-testid="citation-card"]');
    this.verificationBadges = page.locator('[data-testid="verification-badge"]');

    // Missing acts
    this.missingActCards = page.locator('[data-testid="missing-act-card"]');
    this.uploadActButton = page.getByRole('button', { name: /upload act/i });
    this.skipActButton = page.getByRole('button', { name: /skip/i });

    // Act discovery
    this.actDiscoveryModal = page.locator('[data-testid="act-discovery-modal"]');
    this.actUploadDropzone = page.locator('[data-testid="act-upload-dropzone"]');
    this.actDiscoveryTrigger = page.getByRole('button', { name: /discover acts/i });

    // Split view
    this.splitViewButton = page.getByRole('button', { name: /compare|split view/i });
    this.pdfSplitView = page.locator('[data-testid="pdf-split-view"]');
    this.splitViewHeader = page.locator('[data-testid="split-view-header"]');
    this.splitViewClose = page.getByRole('button', { name: /close split view/i });

    // Verification
    this.verifyButton = page.getByRole('button', { name: /verify/i });
    this.batchVerifyButton = page.getByRole('button', { name: /batch verify|verify all/i });

    // Empty
    this.emptyState = page.locator('[data-testid="citations-empty-state"]');
  }

  /**
   * Navigate to citations tab for a matter
   */
  async gotoCitations(matterId: string) {
    await this.page.goto(`/matter/${matterId}/citations`);
    await this.waitForCitationsLoad();
  }

  /**
   * Wait for citations content to load
   */
  async waitForCitationsLoad() {
    await this.page.waitForURL(/\/citations/, { timeout: 10000 });
    await this.page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
  }

  /**
   * Switch to By Act view
   */
  async switchToByActView() {
    await this.byActTab.click();
    await expect(this.byActView).toBeVisible();
  }

  /**
   * Switch to By Document view
   */
  async switchToByDocumentView() {
    await this.byDocumentTab.click();
    await expect(this.byDocumentView).toBeVisible();
  }

  /**
   * Get count of act groups
   */
  async getActGroupCount(): Promise<number> {
    return await this.actGroups.count();
  }

  /**
   * Get count of all citations
   */
  async getCitationCount(): Promise<number> {
    return await this.citationCards.count();
  }

  /**
   * Get count of missing acts
   */
  async getMissingActCount(): Promise<number> {
    return await this.missingActCards.count();
  }

  /**
   * Check if there are missing acts
   */
  async hasMissingActs(): Promise<boolean> {
    return await this.missingActsAlert.isVisible();
  }

  /**
   * Click on a citation card
   */
  async clickCitation(index: number = 0) {
    await this.citationCards.nth(index).click();
  }

  /**
   * Click on citation by text
   */
  async clickCitationByText(text: string) {
    await this.citationCards.filter({ hasText: text }).first().click();
  }

  /**
   * Open split view for a citation
   */
  async openSplitView(citationIndex: number = 0) {
    await this.citationCards.nth(citationIndex).click();
    await this.splitViewButton.click();
    await expect(this.pdfSplitView).toBeVisible();
  }

  /**
   * Close split view
   */
  async closeSplitView() {
    await this.splitViewClose.click();
    await expect(this.pdfSplitView).not.toBeVisible();
  }

  /**
   * Verify a citation from split view
   */
  async verifyCitationFromSplitView() {
    await this.pdfSplitView.getByRole('button', { name: /verify/i }).click();
  }

  /**
   * Upload act for missing act resolution
   */
  async uploadActForMissingAct(actName: string, filePath: string) {
    const missingActCard = this.missingActCards.filter({ hasText: actName });
    await missingActCard.getByRole('button', { name: /upload/i }).click();

    await this.page.locator('input[type="file"]').setInputFiles(filePath);
    await this.page.getByRole('button', { name: /upload|submit/i }).click();
  }

  /**
   * Skip a missing act
   */
  async skipMissingAct(actName: string) {
    const missingActCard = this.missingActCards.filter({ hasText: actName });
    await missingActCard.getByRole('button', { name: /skip/i }).click();
  }

  /**
   * Open act discovery modal
   */
  async openActDiscovery() {
    await this.actDiscoveryTrigger.click();
    await expect(this.actDiscoveryModal).toBeVisible();
  }

  /**
   * Get verification status of a citation
   */
  async getCitationVerificationStatus(index: number): Promise<string> {
    const badge = this.citationCards.nth(index).locator('[data-testid="verification-badge"]');
    return await badge.textContent() || '';
  }

  /**
   * Batch verify all citations
   */
  async batchVerifyAll() {
    await this.batchVerifyButton.click();
  }

  /**
   * Expand an act group
   */
  async expandActGroup(actName: string) {
    await this.actGroups.filter({ hasText: actName }).click();
  }

  /**
   * Check if any citations are unverified
   */
  async hasUnverifiedCitations(): Promise<boolean> {
    return await this.unverifiedAlert.isVisible();
  }
}
