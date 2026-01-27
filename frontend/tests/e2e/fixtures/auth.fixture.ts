import { test as base, expect, Page } from '@playwright/test';

/**
 * Test user credentials for E2E testing
 * These should be configured in environment variables for CI
 */
export const TEST_USER = {
  email: process.env.TEST_USER_EMAIL || 'test@example.com',
  password: process.env.TEST_USER_PASSWORD || 'testpassword123',
};

export const TEST_USER_SECONDARY = {
  email: process.env.TEST_USER_SECONDARY_EMAIL || 'test2@example.com',
  password: process.env.TEST_USER_SECONDARY_PASSWORD || 'testpassword123',
};

/**
 * Authentication helper functions
 */
export class AuthHelper {
  constructor(private page: Page) {}

  /**
   * Login with email and password
   */
  async login(email: string = TEST_USER.email, password: string = TEST_USER.password) {
    await this.page.goto('/login');
    await this.page.getByLabel('Email').fill(email);
    await this.page.getByLabel('Password').fill(password);
    await this.page.getByRole('button', { name: /sign in|log in/i }).click();

    // Wait for redirect to dashboard
    await expect(this.page).toHaveURL(/\/dashboard/);
  }

  /**
   * Login via OTP (for testing OTP flow)
   */
  async loginWithOTP(email: string = TEST_USER.email) {
    await this.page.goto('/login');
    await this.page.getByRole('tab', { name: /otp|magic link/i }).click();
    await this.page.getByLabel('Email').fill(email);
    await this.page.getByRole('button', { name: /send|get code/i }).click();

    // In tests, we'd need to mock the OTP or use a test mailbox
    // For now, this sets up the flow
  }

  /**
   * Logout the current user
   */
  async logout() {
    // Click user menu and logout
    await this.page.getByRole('button', { name: /user|profile|account/i }).click();
    await this.page.getByRole('menuitem', { name: /log out|sign out/i }).click();

    // Wait for redirect to login
    await expect(this.page).toHaveURL(/\/login/);
  }

  /**
   * Check if user is logged in
   */
  async isLoggedIn(): Promise<boolean> {
    try {
      await this.page.waitForSelector('[data-testid="user-menu"], [data-testid="dashboard"]', {
        timeout: 3000,
      });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Navigate to signup page
   */
  async goToSignup() {
    await this.page.goto('/signup');
  }

  /**
   * Complete signup flow
   */
  async signup(email: string, password: string) {
    await this.goToSignup();
    await this.page.getByLabel('Email').fill(email);
    await this.page.getByLabel('Password').fill(password);
    await this.page.getByLabel(/confirm password/i).fill(password);
    await this.page.getByRole('button', { name: /sign up|create account/i }).click();
  }

  /**
   * Request password reset
   */
  async requestPasswordReset(email: string) {
    await this.page.goto('/forgot-password');
    await this.page.getByLabel('Email').fill(email);
    await this.page.getByRole('button', { name: /reset|send/i }).click();
  }
}

/**
 * Extended test fixture with auth helper
 */
export const test = base.extend<{ auth: AuthHelper }>({
  auth: async ({ page }, use) => {
    const auth = new AuthHelper(page);
    // eslint-disable-next-line react-hooks/rules-of-hooks -- Playwright fixture API, not React hook
    await use(auth);
  },
});

export { expect };
