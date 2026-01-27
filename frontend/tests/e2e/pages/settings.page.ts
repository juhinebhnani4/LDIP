import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Settings page
 *
 * Gap #19: Email Notification on Processing Completion
 */
export class SettingsPage {
  readonly page: Page;

  // Page structure
  readonly heading: Locator;
  readonly backButton: Locator;

  // Profile section
  readonly profileSection: Locator;

  // Notification section
  readonly notificationSection: Locator;
  readonly emailProcessingToggle: Locator;
  readonly emailVerificationToggle: Locator;
  readonly browserNotificationsToggle: Locator;

  // Appearance section
  readonly appearanceSection: Locator;
  readonly themeSelect: Locator;

  // Account section
  readonly accountSection: Locator;
  readonly signOutAllButton: Locator;
  readonly deleteAccountButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Page structure
    this.heading = page.getByRole('heading', { name: 'Settings' });
    this.backButton = page.getByRole('link', { name: /back to dashboard/i });

    // Profile section
    this.profileSection = page.locator('text=Profile').locator('..');

    // Notification section - find by card title
    this.notificationSection = page.locator('[class*="Card"]').filter({ hasText: 'Notifications' });

    // Notification toggles - use the switch role with labels
    this.emailProcessingToggle = page.locator('#email-processing');
    this.emailVerificationToggle = page.locator('#email-verification');
    this.browserNotificationsToggle = page.locator('#browser-notifications');

    // Appearance section
    this.appearanceSection = page.locator('[class*="Card"]').filter({ hasText: 'Appearance' });
    this.themeSelect = page.getByRole('combobox', { name: /theme/i });

    // Account section
    this.accountSection = page.locator('[class*="Card"]').filter({ hasText: 'Account' });
    this.signOutAllButton = page.getByRole('button', { name: /sign out.*devices/i });
    this.deleteAccountButton = page.getByRole('button', { name: /delete.*account/i });
  }

  /**
   * Navigate to settings page
   */
  async goto() {
    await this.page.goto('/settings');
    await expect(this.heading).toBeVisible({ timeout: 10000 });
  }

  /**
   * Wait for settings to load
   */
  async waitForLoad() {
    await expect(this.notificationSection).toBeVisible();
    await expect(this.emailProcessingToggle).toBeVisible();
  }

  /**
   * Toggle email processing notifications
   */
  async toggleEmailProcessingNotifications() {
    await this.emailProcessingToggle.click();
  }

  /**
   * Toggle email verification notifications
   */
  async toggleEmailVerificationNotifications() {
    await this.emailVerificationToggle.click();
  }

  /**
   * Toggle browser notifications
   */
  async toggleBrowserNotifications() {
    await this.browserNotificationsToggle.click();
  }

  /**
   * Check if email processing notifications are enabled
   */
  async isEmailProcessingEnabled(): Promise<boolean> {
    const checked = await this.emailProcessingToggle.getAttribute('aria-checked');
    return checked === 'true';
  }

  /**
   * Check if email verification notifications are enabled
   */
  async isEmailVerificationEnabled(): Promise<boolean> {
    const checked = await this.emailVerificationToggle.getAttribute('aria-checked');
    return checked === 'true';
  }

  /**
   * Check if browser notifications are enabled
   */
  async isBrowserNotificationsEnabled(): Promise<boolean> {
    const checked = await this.browserNotificationsToggle.getAttribute('aria-checked');
    return checked === 'true';
  }

  /**
   * Go back to dashboard
   */
  async goToDashboard() {
    await this.backButton.click();
    await expect(this.page).toHaveURL(/\/dashboard|\//);
  }

  /**
   * Select theme
   */
  async selectTheme(theme: 'light' | 'dark' | 'system') {
    await this.themeSelect.click();
    await this.page.getByRole('option', { name: new RegExp(theme, 'i') }).click();
  }
}
