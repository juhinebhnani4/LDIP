import { test as setup, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/auth.fixture';

const authFile = 'tests/e2e/.auth/user.json';

/**
 * Authentication setup - runs before all tests
 * Logs in and saves the session state for reuse
 */
setup('authenticate', async ({ page, context }) => {
  // Clear any existing session
  await context.clearCookies();

  // Navigate to login page
  await page.goto('/login');
  await page.waitForLoadState('networkidle');

  // Dismiss any modal overlay by clicking on it or pressing Escape multiple times
  const modalOverlay = page.locator('.fixed.inset-0.bg-black\\/50, [data-radix-dialog-overlay]');
  for (let i = 0; i < 3; i++) {
    if (await modalOverlay.isVisible({ timeout: 1000 }).catch(() => false)) {
      // Try clicking on backdrop
      await modalOverlay.click({ position: { x: 10, y: 10 }, force: true }).catch(() => {});
      await page.waitForTimeout(300);
    }
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  }

  // Wait for login form to be ready
  const emailInput = page.getByRole('textbox', { name: /email/i });
  await expect(emailInput).toBeVisible({ timeout: 5000 });

  // Fill in credentials
  await emailInput.fill(TEST_USER.email);
  await page.locator('input[type="password"]').fill(TEST_USER.password);

  // Submit login form
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();

  // Wait for navigation or error
  try {
    await page.waitForURL(/\/(dashboard|matter|upload|settings)/, { timeout: 20000 });
  } catch (e) {
    // Check if there's an error message
    const errorText = await page.locator('[role="alert"], .error, .text-red, .text-destructive').textContent().catch(() => '');
    if (errorText) {
      throw new Error(`Login failed with error: ${errorText}`);
    }
    throw e;
  }

  // Dismiss any post-login modals
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  // Verify we're on an authenticated page
  await expect(page).toHaveURL(/\/(dashboard|matter|upload|settings)/, { timeout: 5000 });

  // Verify we're logged in by checking for user menu or dashboard element
  await expect(
    page.getByRole('button', { name: /user|profile|account/i }).or(
      page.locator('[data-testid="dashboard-content"]')
    )
  ).toBeVisible();

  // Save session state
  await page.context().storageState({ path: authFile });
});
