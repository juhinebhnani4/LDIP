import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Dashboard page
 */
export class DashboardPage {
  readonly page: Page;

  // Locators
  readonly createMatterButton: Locator;
  readonly matterCards: Locator;
  readonly searchInput: Locator;
  readonly statusFilter: Locator;
  readonly viewToggle: Locator;
  readonly gridViewButton: Locator;
  readonly listViewButton: Locator;
  readonly activityFeed: Locator;
  readonly quickStats: Locator;
  readonly userMenu: Locator;
  readonly notificationsButton: Locator;
  readonly emptyState: Locator;
  readonly loadingState: Locator;

  constructor(page: Page) {
    this.page = page;

    // Main actions
    this.createMatterButton = page.getByRole('button', { name: /new matter|create matter|upload/i });

    // Matter display - updated with actual data-testid selectors
    this.matterCards = page.locator('[data-testid^="matter-card-"]');
    this.emptyState = page.locator('[data-testid="dashboard-empty-state"]');
    this.loadingState = page.locator('[data-testid="matter-card-skeleton"]');

    // Filters and search - updated with data-testid
    this.searchInput = page.locator('[data-testid="global-search-input"]');
    this.statusFilter = page.getByRole('combobox', { name: /status/i });

    // View controls
    this.viewToggle = page.locator('[data-testid="view-toggle"]');
    this.gridViewButton = page.getByRole('button', { name: /grid/i });
    this.listViewButton = page.getByRole('button', { name: /list/i });

    // Sidebar components
    this.activityFeed = page.locator('[data-testid="activity-feed"]');
    this.quickStats = page.locator('[data-testid="quick-stats"]');

    // Header components - match actual aria-labels
    this.userMenu = page.getByRole('button', { name: /user profile menu/i });
    this.notificationsButton = page.locator('[data-testid="notifications-trigger"]');
  }

  /**
   * Navigate to dashboard and wait for it to load
   */
  async goto() {
    await this.page.goto('/dashboard');
    await expect(this.page).toHaveURL(/\/dashboard/);
    // Wait for dashboard content to load
    await this.waitForLoad();
  }

  /**
   * Wait for dashboard to load completely
   */
  async waitForLoad() {
    // Wait for loading state to disappear
    await this.loadingState.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
    // Wait for either matters or empty state
    await expect(this.matterCards.first().or(this.emptyState)).toBeVisible();
  }

  /**
   * Click create new matter button
   */
  async clickCreateMatter() {
    await this.createMatterButton.click();
    await expect(this.page).toHaveURL(/\/upload/);
  }

  /**
   * Get count of visible matter cards
   */
  async getMatterCount(): Promise<number> {
    return await this.matterCards.count();
  }

  /**
   * Open a matter by clicking its card
   */
  async openMatter(matterName: string) {
    const matterCard = this.matterCards.filter({ hasText: matterName }).first();
    // Click the "Resume" or "View Progress" button inside the card
    const actionButton = matterCard.locator('[data-testid="matter-card-resume-button"], [data-testid="matter-card-view-progress-button"]');
    await actionButton.click();
    await this.page.waitForURL(/\/matter\/[a-f0-9-]+/);
  }

  /**
   * Open the first matter in the list
   */
  async openFirstMatter() {
    const firstCard = this.matterCards.first();
    // Click the "Resume" or "View Progress" button inside the card
    const actionButton = firstCard.locator('[data-testid="matter-card-resume-button"], [data-testid="matter-card-view-progress-button"]');
    await actionButton.click();
    await this.page.waitForURL(/\/matter\/[a-f0-9-]+/);
  }

  /**
   * Search for matters
   */
  async search(query: string) {
    await this.searchInput.fill(query);
    await this.page.keyboard.press('Enter');
    // Wait for search results to update
    await this.page.waitForTimeout(500);
  }

  /**
   * Clear search
   */
  async clearSearch() {
    await this.searchInput.clear();
    await this.page.keyboard.press('Enter');
  }

  /**
   * Filter by status
   */
  async filterByStatus(status: string) {
    await this.statusFilter.click();
    await this.page.getByRole('option', { name: new RegExp(status, 'i') }).click();
  }

  /**
   * Switch to grid view
   */
  async switchToGridView() {
    await this.gridViewButton.click();
  }

  /**
   * Switch to list view
   */
  async switchToListView() {
    await this.listViewButton.click();
  }

  /**
   * Open user menu
   */
  async openUserMenu() {
    await this.userMenu.click();
  }

  /**
   * Logout from user menu
   */
  async logout() {
    await this.openUserMenu();
    await this.page.getByRole('menuitem', { name: /log out|sign out/i }).click();
    await expect(this.page).toHaveURL(/\/login/);
  }

  /**
   * Open notifications dropdown
   */
  async openNotifications() {
    await this.notificationsButton.click();
    await this.page.waitForSelector('[data-testid="notifications-dropdown"]');
  }

  /**
   * Check if dashboard has any matters
   */
  async hasMatters(): Promise<boolean> {
    const count = await this.getMatterCount();
    return count > 0;
  }

  /**
   * Delete a matter from the dashboard
   */
  async deleteMatter(matterName: string) {
    const matterCard = this.matterCards.filter({ hasText: matterName });
    await matterCard.getByRole('button', { name: /more|actions|menu/i }).click();
    await this.page.getByRole('menuitem', { name: /delete/i }).click();
    await this.page.getByRole('button', { name: /confirm|delete/i }).click();
  }

  /**
   * Get matter names from visible cards
   */
  async getMatterNames(): Promise<string[]> {
    const cards = await this.matterCards.all();
    const names: string[] = [];
    for (const card of cards) {
      const nameElement = card.locator('[data-testid="matter-name"], h3, h4');
      const name = await nameElement.textContent();
      if (name) names.push(name.trim());
    }
    return names;
  }
}
