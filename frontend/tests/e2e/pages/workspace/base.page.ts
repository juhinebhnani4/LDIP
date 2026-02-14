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
  readonly exportButton: Locator;
  readonly moreActionsButton: Locator;

  // Tab navigation - directly visible tabs
  readonly tabBar: Locator;
  readonly summaryTab: Locator;
  readonly documentsTab: Locator;
  readonly timelineTab: Locator;

  // Tab navigation - tabs behind "More" dropdown (menuitem role)
  readonly moreTabsButton: Locator;
  readonly citationsMenuItem: Locator;
  readonly entitiesMenuItem: Locator;
  readonly contradictionsMenuItem: Locator;
  readonly verificationMenuItem: Locator;

  // Legacy aliases for backwards compatibility with tests
  readonly citationsTab: Locator;
  readonly entitiesTab: Locator;
  readonly contradictionsTab: Locator;
  readonly verificationTab: Locator;

  // Q&A Panel
  readonly qaPanel: Locator;
  readonly qaPanelInput: Locator;
  readonly qaPanelSendButton: Locator;
  readonly qaPanelMinimizeButton: Locator;
  readonly qaPanelSettingsButton: Locator;
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
    this.header = page.locator('header, [role="banner"]');
    this.backButton = page.getByRole('link', { name: /back to dashboard|dashboard/i });
    this.matterName = page.locator('h1');
    this.exportButton = page.getByRole('button', { name: /export/i });
    this.moreActionsButton = page.getByRole('button', { name: /more actions/i });

    // Directly visible tabs (tab role)
    this.tabBar = page.getByRole('tablist', { name: /matter workspace navigation/i });
    this.summaryTab = page.getByRole('tab', { name: /summary/i });
    this.documentsTab = page.getByRole('tab', { name: /documents/i });
    this.timelineTab = page.getByRole('tab', { name: /timeline/i });

    // "More" dropdown button and its menuitem children
    this.moreTabsButton = page.locator('[data-testid="workspace-tab-more"]');
    this.citationsMenuItem = page.getByRole('menuitem', { name: /citations/i });
    this.entitiesMenuItem = page.getByRole('menuitem', { name: /entities/i });
    this.contradictionsMenuItem = page.getByRole('menuitem', { name: /contradictions/i });
    this.verificationMenuItem = page.getByRole('menuitem', { name: /verification/i });

    // Legacy aliases — tests may reference these
    this.citationsTab = this.citationsMenuItem;
    this.entitiesTab = this.entitiesMenuItem;
    this.contradictionsTab = this.contradictionsMenuItem;
    this.verificationTab = this.verificationMenuItem;

    // Q&A Panel — always visible in workspace, no toggle
    this.qaPanel = page.getByRole('heading', { name: /ask jaanch/i }).locator('..');
    this.qaPanelInput = page.getByPlaceholder('Ask jaanch a question...');
    this.qaPanelSendButton = page.locator('[data-testid="chat-submit-button"]').or(
      page.locator('button').filter({ has: page.locator('img') }).last()
    );
    this.qaPanelMinimizeButton = page.getByRole('button', { name: /minimize panel/i });
    this.qaPanelSettingsButton = page.getByRole('button', { name: /panel settings/i });
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
   * Open the "More" dropdown and click a menuitem tab
   */
  private async clickMoreTab(menuItem: Locator) {
    await this.moreTabsButton.click();
    await menuItem.click();
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
    await this.page.waitForURL(/\/summary/);
  }

  /**
   * Navigate to Documents tab
   */
  async goToDocuments() {
    await this.documentsTab.click();
    await this.page.waitForURL(/\/documents/);
  }

  /**
   * Navigate to Timeline tab
   */
  async goToTimeline() {
    await this.timelineTab.click();
    await this.page.waitForURL(/\/timeline/);
  }

  /**
   * Navigate to Citations tab (behind "More" dropdown)
   */
  async goToCitations() {
    await this.clickMoreTab(this.citationsMenuItem);
    await this.page.waitForURL(/\/citations/);
  }

  /**
   * Navigate to Entities tab (behind "More" dropdown)
   */
  async goToEntities() {
    await this.clickMoreTab(this.entitiesMenuItem);
    await this.page.waitForURL(/\/entities/);
  }

  /**
   * Navigate to Contradictions tab (behind "More" dropdown)
   */
  async goToContradictions() {
    await this.clickMoreTab(this.contradictionsMenuItem);
    await this.page.waitForURL(/\/contradictions/);
  }

  /**
   * Navigate to Verification tab (behind "More" dropdown)
   */
  async goToVerification() {
    await this.clickMoreTab(this.verificationMenuItem);
    await this.page.waitForURL(/\/verification/);
  }

  /**
   * Go back to dashboard
   */
  async goBackToDashboard() {
    await this.backButton.click();
    await expect(this.page).toHaveURL(/\/dashboard/);
  }

  /**
   * Minimize/restore Q&A panel
   */
  async toggleQAPanel() {
    await this.qaPanelMinimizeButton.click();
  }

  /**
   * Ask a question in the Q&A panel
   */
  async askQuestion(question: string) {
    await this.qaPanelInput.fill(question);
    // Press Enter to send since the send button may be tricky to locate
    await this.page.keyboard.press('Enter');
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
   * Open export dropdown
   */
  async openExportMenu() {
    await this.exportButton.click();
    await this.page.waitForSelector('[data-testid="export-menu"]');
  }
}
