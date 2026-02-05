import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Login page
 */
export class LoginPage {
  readonly page: Page;

  // Locators
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly loginButton: Locator;
  readonly otpTab: Locator;
  readonly passwordTab: Locator;
  readonly forgotPasswordLink: Locator;
  readonly signupLink: Locator;
  readonly errorMessage: Locator;
  readonly loadingSpinner: Locator;

  constructor(page: Page) {
    this.page = page;

    // Form elements - updated with data-testid selectors
    this.emailInput = page.locator('[data-testid="login-email-input"]');
    this.passwordInput = page.locator('[data-testid="login-password-input"]');
    this.loginButton = page.locator('[data-testid="login-submit-button"]');

    // Tab navigation
    this.otpTab = page.locator('[data-testid="login-tab-magic-link"]');
    this.passwordTab = page.locator('[data-testid="login-tab-password"]');

    // Links
    this.forgotPasswordLink = page.locator('[data-testid="login-forgot-password-link"]');
    this.signupLink = page.locator('[data-testid="login-signup-link"]');

    // Feedback
    this.errorMessage = page.locator('[data-testid="login-error-message"]');
    this.loadingSpinner = page.locator('[data-testid="loading"], .loading-spinner');
  }

  /**
   * Navigate to login page
   */
  async goto() {
    await this.page.goto('/login');
    await expect(this.page).toHaveURL(/\/login/);
  }

  /**
   * Login with email and password
   */
  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
  }

  /**
   * Login and wait for dashboard redirect
   */
  async loginAndWaitForDashboard(email: string, password: string) {
    await this.login(email, password);
    await expect(this.page).toHaveURL(/\/dashboard/, { timeout: 10000 });
  }

  /**
   * Switch to OTP login tab
   */
  async switchToOtpLogin() {
    await this.otpTab.click();
    await expect(this.otpTab).toHaveAttribute('aria-selected', 'true');
  }

  /**
   * Switch to password login tab
   */
  async switchToPasswordLogin() {
    await this.passwordTab.click();
    await expect(this.passwordTab).toHaveAttribute('aria-selected', 'true');
  }

  /**
   * Navigate to forgot password page
   */
  async goToForgotPassword() {
    await this.forgotPasswordLink.click();
    await expect(this.page).toHaveURL(/\/forgot-password/);
  }

  /**
   * Navigate to signup page
   */
  async goToSignup() {
    await this.signupLink.click();
    await expect(this.page).toHaveURL(/\/signup/);
  }

  /**
   * Check if error message is visible
   */
  async hasError(): Promise<boolean> {
    return await this.errorMessage.isVisible();
  }

  /**
   * Get error message text
   */
  async getErrorMessage(): Promise<string> {
    return await this.errorMessage.textContent() || '';
  }

  /**
   * Check if loading spinner is visible
   */
  async isLoading(): Promise<boolean> {
    return await this.loadingSpinner.isVisible();
  }
}
