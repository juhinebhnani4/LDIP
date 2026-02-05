import { test, expect } from '@playwright/test';
import { LoginPage, DashboardPage } from '../pages';
import { TEST_USER, TEST_USER_SECONDARY } from '../fixtures/auth.fixture';

test.describe('Authentication Flow', () => {
  test.describe('Login', () => {
    // Don't use saved auth state for login tests
    test.use({ storageState: { cookies: [], origins: [] } });

    test('should display login page with email and password fields', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      await expect(loginPage.emailInput).toBeVisible();
      await expect(loginPage.passwordInput).toBeVisible();
      await expect(loginPage.loginButton).toBeVisible();
    });

    test('should show error for invalid credentials', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      await loginPage.login('invalid@example.com', 'wrongpassword');

      await expect(loginPage.errorMessage).toBeVisible();
    });

    test('should login successfully with valid credentials', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      await loginPage.loginAndWaitForDashboard(TEST_USER.email, TEST_USER.password);

      await expect(page).toHaveURL(/\/dashboard/);
    });

    test('should navigate to forgot password page', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      await loginPage.goToForgotPassword();

      await expect(page).toHaveURL(/\/forgot-password/);
    });

    test('should navigate to signup page', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      await loginPage.goToSignup();

      await expect(page).toHaveURL(/\/signup/);
    });

    test('should have OTP login tab available', async ({ page }) => {
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      await expect(loginPage.otpTab).toBeVisible();
      await loginPage.switchToOtpLogin();
      await expect(loginPage.otpTab).toHaveAttribute('aria-selected', 'true');
    });
  });

  test.describe('Signup', () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test('should display signup form', async ({ page }) => {
      await page.goto('/signup');

      await expect(page.getByLabel('Email')).toBeVisible();
      await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Create Account' })).toBeVisible();
    });

    test('should show validation errors for invalid input', async ({ page }) => {
      await page.goto('/signup');

      // Submit without filling form
      await page.getByRole('button', { name: 'Create Account' }).click();

      // Should show validation errors - check for "is required" text (multiple errors shown)
      await expect(page.locator('text=/is required/i').first()).toBeVisible();
    });

    test('should show password requirements', async ({ page }) => {
      await page.goto('/signup');

      // Fill a weak password and trigger validation by clicking submit
      await page.getByLabel('Password', { exact: true }).fill('weak');
      await page.getByRole('button', { name: 'Create Account' }).click();

      // Should show password validation error about length
      await expect(page.locator('text=/at least 8 characters/i')).toBeVisible();
    });
  });

  test.describe('Password Reset', () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test('should display forgot password form', async ({ page }) => {
      await page.goto('/forgot-password');

      await expect(page.getByLabel('Email')).toBeVisible();
      // Button says "Send Reset Link"
      await expect(page.getByRole('button', { name: /send reset link/i })).toBeVisible();
    });

    test('should submit password reset request', async ({ page }) => {
      await page.goto('/forgot-password');

      await page.getByLabel('Email').fill(TEST_USER.email);
      await page.getByRole('button', { name: /send reset link/i }).click();

      // Should show success message - use first() as multiple elements may contain the text
      await expect(page.locator('text=/check your email|account exists/i').first()).toBeVisible({ timeout: 10000 });
    });

    test('should have link back to login', async ({ page }) => {
      await page.goto('/forgot-password');

      // Link says "Back to login"
      await page.getByRole('link', { name: /back to login/i }).click();

      await expect(page).toHaveURL(/\/login/);
    });
  });

  test.describe('Session Management', () => {
    test('should maintain session across page navigation', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Navigate to a different page
      await page.goto('/settings');

      // Should still be logged in - settings page shows "Settings" heading only when authenticated
      await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible({ timeout: 10000 });
      // Should not be redirected to login
      await expect(page).not.toHaveURL(/\/login/);
    });

    test('should logout successfully', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await dashboardPage.logout();

      await expect(page).toHaveURL(/\/login/);
    });

    test('should redirect to login when accessing protected routes without auth', async ({ page, context }) => {
      // Clear session
      await context.clearCookies();

      await page.goto('/dashboard');

      await expect(page).toHaveURL(/\/login/);
    });
  });
});
