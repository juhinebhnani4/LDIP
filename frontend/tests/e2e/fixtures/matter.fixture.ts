import { Page, expect } from '@playwright/test';

/**
 * Test matter data for E2E testing
 */
export const TEST_MATTER = {
  name: 'E2E Test Matter - Contract Dispute',
  description: 'Automated test matter for E2E testing',
};

/**
 * Matter management helper functions
 */
export class MatterHelper {
  constructor(private page: Page) {}

  /**
   * Navigate to dashboard
   */
  async goToDashboard() {
    await this.page.goto('/dashboard');
    await expect(this.page).toHaveURL(/\/dashboard/);
  }

  /**
   * Start creating a new matter (navigate to upload wizard)
   */
  async startNewMatter() {
    await this.goToDashboard();
    await this.page.getByRole('button', { name: /new matter|create matter|upload/i }).click();
    await expect(this.page).toHaveURL(/\/upload/);
  }

  /**
   * Open an existing matter by name
   */
  async openMatter(matterName: string) {
    await this.goToDashboard();
    await this.page.getByText(matterName).first().click();
    // Wait for matter workspace to load
    await this.page.waitForSelector('[data-testid="workspace-header"], [data-testid="matter-workspace"]');
  }

  /**
   * Open matter by clicking on a matter card
   */
  async openFirstMatter() {
    await this.goToDashboard();
    await this.page.locator('[data-testid="matter-card"]').first().click();
    await this.page.waitForSelector('[data-testid="workspace-header"], [data-testid="matter-workspace"]');
  }

  /**
   * Delete a matter (if permitted)
   */
  async deleteMatter(matterName: string) {
    await this.goToDashboard();

    // Find matter card and open actions menu
    const matterCard = this.page.locator('[data-testid="matter-card"]').filter({ hasText: matterName });
    await matterCard.getByRole('button', { name: /more|actions|menu/i }).click();
    await this.page.getByRole('menuitem', { name: /delete/i }).click();

    // Confirm deletion
    await this.page.getByRole('button', { name: /confirm|delete/i }).click();
  }

  /**
   * Filter matters by status
   */
  async filterByStatus(status: 'all' | 'active' | 'completed' | 'archived') {
    await this.page.getByRole('combobox', { name: /status/i }).click();
    await this.page.getByRole('option', { name: new RegExp(status, 'i') }).click();
  }

  /**
   * Search for a matter
   */
  async searchMatter(query: string) {
    await this.page.getByPlaceholder(/search/i).fill(query);
    await this.page.keyboard.press('Enter');
  }

  /**
   * Toggle view mode (grid/list)
   */
  async setViewMode(mode: 'grid' | 'list') {
    await this.page.getByRole('button', { name: new RegExp(mode, 'i') }).click();
  }

  /**
   * Get count of visible matter cards
   */
  async getMatterCount(): Promise<number> {
    return await this.page.locator('[data-testid="matter-card"]').count();
  }

  /**
   * Navigate to a specific tab in matter workspace
   */
  async navigateToTab(tab: 'summary' | 'documents' | 'timeline' | 'citations' | 'entities' | 'verification' | 'contradictions') {
    await this.page.getByRole('tab', { name: new RegExp(tab, 'i') }).click();
    // Wait for tab content to load
    await this.page.waitForSelector(`[data-testid="${tab}-content"], [data-testid="${tab}-tab"]`);
  }

  /**
   * Get matter ID from URL
   */
  getMatterIdFromUrl(): string | null {
    const url = this.page.url();
    const match = url.match(/\/matter\/([a-f0-9-]+)/);
    return match ? match[1] : null;
  }
}

/**
 * Factory function for creating matter helper
 */
export function createMatterHelper(page: Page): MatterHelper {
  return new MatterHelper(page);
}
