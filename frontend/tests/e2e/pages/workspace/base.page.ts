import { Page, Locator, expect } from '@playwright/test';

/**
 * Base Page Object Model for Matter Workspace
 * Contains common elements shared across all workspace tabs
 */
export class WorkspaceBasePage {
  readonly page: Page;

  // Header elements
  readonly header: Locator;
  readonly backButton: Locator;
  readonly matterName: Locator;
  readonly shareButton: Locator;
  readonly exportButton: Locator;
  readonly settingsButton: Locator;

  // Tab navigation
  readonly tabBar: Locator;
  readonly summaryTab: Locator;
  readonly documentsTab: Locator;
  readonly timelineTab: Locator;
  readonly citationsTab: Locator;
  readonly entitiesTab: Locator;
  readonly contradictionsTab: Locator;
  readonly verificationTab: Locator;

  // Q&A Panel
  readonly qaPanel: Locator;
  readonly qaPanelInput: Locator;
  readonly qaPanelSendButton: Locator;
  readonly qaPanelToggle: Locator;
  readonly qaPanelMessages: Locator;
  readonly qaPanelUserMessages: Locator;
  readonly qaPanelAssistantMessages: Locator;
  readonly qaPanelLoadingIndicator: Locator;
  readonly qaPanelCompletionStatus: Locator;
  readonly suggestedQuestions: Locator;

  // Status indicators
  readonly connectionStatus: Locator;
  readonly loadingIndicator: Locator;

  constructor(page: Page) {
    this.page = page;

    // Header
    this.header = page.locator('[data-testid="workspace-header"]');
    this.backButton = page.getByRole('button', { name: /back|←/i });
    this.matterName = page.locator('[data-testid="matter-name"], h1');
    this.shareButton = page.getByRole('button', { name: /share/i });
    this.exportButton = page.getByRole('button', { name: /export/i });
    this.settingsButton = page.getByRole('button', { name: /settings|gear/i });

    // Tabs
    this.tabBar = page.locator('[data-testid="workspace-tab-bar"], [role="tablist"]');
    this.summaryTab = page.getByRole('tab', { name: /summary/i });
    this.documentsTab = page.getByRole('tab', { name: /documents/i });
    this.timelineTab = page.getByRole('tab', { name: /timeline/i });
    this.citationsTab = page.getByRole('tab', { name: /citations/i });
    this.entitiesTab = page.getByRole('tab', { name: /entities/i });
    this.contradictionsTab = page.getByRole('tab', { name: /contradictions/i });
    this.verificationTab = page.getByRole('tab', { name: /verification/i });

    // Q&A Panel - updated selectors based on actual DOM structure
    this.qaPanel = page.locator('[data-testid="qa-panel"]');
    // The textarea has data-testid="chat-input-textarea"
    this.qaPanelInput = page.locator('[data-testid="chat-input-textarea"]');
    // Send button has data-testid="chat-submit-button"
    this.qaPanelSendButton = page.locator('[data-testid="chat-submit-button"]');
    this.qaPanelToggle = page.locator('[data-testid="qa-panel-toggle"]');
    // Messages are article elements with specific aria-labels
    this.qaPanelUserMessages = page.getByRole('article', { name: 'Your message' });
    this.qaPanelAssistantMessages = page.getByRole('article', { name: 'LDIP assistant message' });
    // Combined selector for all messages (both user and assistant)
    this.qaPanelMessages = page.getByRole('article', { name: /Your message|LDIP assistant message/ });
    this.qaPanelLoadingIndicator = page.getByRole('article', { name: 'LDIP assistant is responding' });
    this.qaPanelCompletionStatus = page.getByRole('status', { name: 'Response completed successfully' });
    // Suggested questions are listitem elements with Ask: prefix in aria-label
    this.suggestedQuestions = page.locator('[aria-label^="Ask:"]');

    // Status
    this.connectionStatus = page.locator('[data-testid="connection-status"]');
    this.loadingIndicator = page.locator('[data-testid="loading-indicator"]');
  }

  /**
   * Navigate to a specific matter
   */
  async goto(matterId: string) {
    await this.page.goto(`/matter/${matterId}`);
    await this.waitForLoad();
  }

  /**
   * Wait for workspace to load
   */
  async waitForLoad() {
    // Wait for loading indicator to disappear with extended timeout
    await this.loadingIndicator.waitFor({ state: 'hidden', timeout: 20000 }).catch(() => {});
    // Wait for tab bar to be visible - use longer timeout for slow loads
    await expect(this.tabBar).toBeVisible({ timeout: 20000 });
  }

  /**
   * Get current matter ID from URL
   */
  getMatterIdFromUrl(): string | null {
    const url = this.page.url();
    const match = url.match(/\/matter\/([a-f0-9-]+)/);
    return match ? match[1] : null;
  }

  /**
   * Navigate to Summary tab
   */
  async goToSummary() {
    await this.summaryTab.click();
    // Wait for URL to change to summary tab
    await this.page.waitForURL(/\/summary/);
    await expect(this.summaryTab).toHaveAttribute('aria-selected', 'true', { timeout: 10000 });
  }

  /**
   * Navigate to Documents tab
   */
  async goToDocuments() {
    await this.documentsTab.click();
    // Wait for URL to change to documents tab
    await this.page.waitForURL(/\/documents/);
    await expect(this.documentsTab).toHaveAttribute('aria-selected', 'true', { timeout: 10000 });
  }

  /**
   * Navigate to Timeline tab
   */
  async goToTimeline() {
    await this.timelineTab.click();
    await this.page.waitForURL(/\/timeline/);
    await expect(this.timelineTab).toHaveAttribute('aria-selected', 'true', { timeout: 10000 });
  }

  /**
   * Navigate to Citations tab
   */
  async goToCitations() {
    await this.citationsTab.click();
    await this.page.waitForURL(/\/citations/);
    await expect(this.citationsTab).toHaveAttribute('aria-selected', 'true', { timeout: 10000 });
  }

  /**
   * Navigate to Entities tab
   */
  async goToEntities() {
    await this.entitiesTab.click();
    await this.page.waitForURL(/\/entities/);
    await expect(this.entitiesTab).toHaveAttribute('aria-selected', 'true', { timeout: 10000 });
  }

  /**
   * Navigate to Contradictions tab
   */
  async goToContradictions() {
    await this.contradictionsTab.click();
    await this.page.waitForURL(/\/contradictions/);
    await expect(this.contradictionsTab).toHaveAttribute('aria-selected', 'true', { timeout: 10000 });
  }

  /**
   * Navigate to Verification tab
   */
  async goToVerification() {
    await this.verificationTab.click();
    await this.page.waitForURL(/\/verification/);
    await expect(this.verificationTab).toHaveAttribute('aria-selected', 'true', { timeout: 10000 });
  }

  /**
   * Go back to dashboard
   */
  async goBackToDashboard() {
    await this.backButton.click();
    await expect(this.page).toHaveURL(/\/dashboard/);
  }

  /**
   * Toggle Q&A panel visibility
   */
  async toggleQAPanel() {
    await this.qaPanelToggle.click();
  }

  /**
   * Ask a question in the Q&A panel
   */
  async askQuestion(question: string) {
    await this.qaPanelInput.fill(question);
    await this.qaPanelSendButton.click();
  }

  /**
   * Wait for Q&A response to complete
   */
  async waitForQAResponse(timeout: number = 60000) {
    // Wait for loading indicator to disappear (response started)
    await this.qaPanelLoadingIndicator.waitFor({ state: 'hidden', timeout }).catch(() => {});
    // Then wait for completion status OR an assistant message to appear
    await expect(this.qaPanelAssistantMessages.last()).toBeVisible({ timeout });
  }

  /**
   * Dismiss any dialogs that might block interaction (like Act References dialog)
   */
  async dismissBlockingDialogs() {
    // Check for Act References Detected dialog and close it
    const actReferencesDialog = this.page.getByRole('alertdialog').filter({ hasText: /act references detected/i });
    if (await actReferencesDialog.isVisible().catch(() => false)) {
      const closeButton = actReferencesDialog.getByRole('button', { name: /close|dismiss|ok|got it/i });
      if (await closeButton.isVisible().catch(() => false)) {
        await closeButton.click();
      }
    }
  }

  /**
   * Get number of messages in Q&A panel
   */
  async getMessageCount(): Promise<number> {
    return await this.qaPanelMessages.count();
  }

  /**
   * Click a suggested question
   */
  async clickSuggestedQuestion(index: number = 0) {
    await this.suggestedQuestions.nth(index).click();
  }

  /**
   * Open share dialog
   */
  async openShareDialog() {
    await this.shareButton.click();
    await this.page.waitForSelector('[data-testid="share-dialog"]');
  }

  /**
   * Open export dropdown
   */
  async openExportMenu() {
    await this.exportButton.click();
    await this.page.waitForSelector('[data-testid="export-menu"]');
  }
}
