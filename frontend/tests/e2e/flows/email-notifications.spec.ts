import { test, expect } from '@playwright/test';
import { SettingsPage } from '../pages';

/**
 * Email Notification Settings Tests
 *
 * Gap #19: Email Notification on Processing Completion
 *
 * Tests the user settings UI for email notifications:
 * - Toggle visibility and functionality
 * - Preference persistence via API
 */
test.describe('Email Notification Settings', () => {
  let settingsPage: SettingsPage;

  test.beforeEach(async ({ page }) => {
    settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForLoad();
  });

  test.describe('Notification Section', () => {
    test('should display notification section with all toggles', async () => {
      // Verify notification section is visible
      await expect(settingsPage.notificationSection).toBeVisible();

      // Verify all three notification toggles are present
      await expect(settingsPage.emailProcessingToggle).toBeVisible();
      await expect(settingsPage.emailVerificationToggle).toBeVisible();
      await expect(settingsPage.browserNotificationsToggle).toBeVisible();
    });

    test('should display correct labels for notification toggles', async ({ page }) => {
      // Check email processing label
      await expect(page.getByText('Document Processing')).toBeVisible();
      await expect(page.getByText('Email when document processing completes')).toBeVisible();

      // Check email verification label
      await expect(page.getByText('Verification Reminders')).toBeVisible();
      await expect(page.getByText('Email reminders for pending verifications')).toBeVisible();

      // Check browser notifications label
      await expect(page.getByText('Browser Notifications')).toBeVisible();
      await expect(page.getByText('Push notifications in your browser')).toBeVisible();
    });
  });

  test.describe('Email Processing Toggle', () => {
    test('should toggle email processing notifications off', async ({ page }) => {
      // Check initial state (should be on by default)
      const initialState = await settingsPage.isEmailProcessingEnabled();

      // Intercept the API call
      const apiPromise = page.waitForResponse(
        (response) =>
          response.url().includes('/api/users/me/preferences') &&
          response.request().method() === 'PATCH'
      );

      // Toggle the switch
      await settingsPage.toggleEmailProcessingNotifications();

      // Wait for API response
      const response = await apiPromise;
      expect(response.ok()).toBe(true);

      // Verify toggle state changed
      const newState = await settingsPage.isEmailProcessingEnabled();
      expect(newState).toBe(!initialState);
    });

    test('should persist email processing preference after page reload', async ({ page }) => {
      // Get initial state
      const initialState = await settingsPage.isEmailProcessingEnabled();

      // Toggle
      await settingsPage.toggleEmailProcessingNotifications();

      // Wait for API to complete
      await page.waitForResponse(
        (response) =>
          response.url().includes('/api/users/me/preferences') &&
          response.request().method() === 'PATCH'
      );

      // Give it a moment to save
      await page.waitForTimeout(500);

      // Reload page
      await page.reload();
      await settingsPage.waitForLoad();

      // Verify state persisted
      const stateAfterReload = await settingsPage.isEmailProcessingEnabled();
      expect(stateAfterReload).toBe(!initialState);

      // Toggle back to original state
      await settingsPage.toggleEmailProcessingNotifications();
      await page.waitForResponse(
        (response) =>
          response.url().includes('/api/users/me/preferences') &&
          response.request().method() === 'PATCH'
      );
    });

    test('should send correct payload when toggling email processing', async ({ page }) => {
      // Get initial state
      const initialState = await settingsPage.isEmailProcessingEnabled();

      // Intercept the request
      const requestPromise = page.waitForRequest(
        (request) =>
          request.url().includes('/api/users/me/preferences') &&
          request.method() === 'PATCH'
      );

      // Toggle
      await settingsPage.toggleEmailProcessingNotifications();

      // Verify request payload
      const request = await requestPromise;
      const postData = request.postDataJSON();

      expect(postData).toHaveProperty('email_notifications_processing');
      expect(postData.email_notifications_processing).toBe(!initialState);
    });
  });

  test.describe('Email Verification Toggle', () => {
    test('should toggle email verification notifications', async ({ page }) => {
      const initialState = await settingsPage.isEmailVerificationEnabled();

      // Intercept the API call
      const apiPromise = page.waitForResponse(
        (response) =>
          response.url().includes('/api/users/me/preferences') &&
          response.request().method() === 'PATCH'
      );

      await settingsPage.toggleEmailVerificationNotifications();

      const response = await apiPromise;
      expect(response.ok()).toBe(true);

      const newState = await settingsPage.isEmailVerificationEnabled();
      expect(newState).toBe(!initialState);

      // Toggle back
      await settingsPage.toggleEmailVerificationNotifications();
    });
  });

  test.describe('Browser Notifications Toggle', () => {
    test('should toggle browser notifications', async ({ page, context }) => {
      // Grant notification permission for the test
      await context.grantPermissions(['notifications']);

      const initialState = await settingsPage.isBrowserNotificationsEnabled();

      // Intercept the API call
      const apiPromise = page.waitForResponse(
        (response) =>
          response.url().includes('/api/users/me/preferences') &&
          response.request().method() === 'PATCH'
      );

      await settingsPage.toggleBrowserNotifications();

      const response = await apiPromise;
      expect(response.ok()).toBe(true);

      const newState = await settingsPage.isBrowserNotificationsEnabled();
      expect(newState).toBe(!initialState);

      // Toggle back
      await settingsPage.toggleBrowserNotifications();
    });
  });

  test.describe('Error Handling', () => {
    test('should show error message when API fails', async ({ page }) => {
      // Mock API failure
      await page.route('**/api/users/me/preferences', async (route) => {
        if (route.request().method() === 'PATCH') {
          await route.fulfill({
            status: 500,
            body: JSON.stringify({ error: 'Internal Server Error' }),
          });
        } else {
          await route.continue();
        }
      });

      // Toggle
      await settingsPage.toggleEmailProcessingNotifications();

      // Should show error message
      await expect(page.getByText(/failed to update preferences/i)).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Navigation', () => {
    test('should navigate back to dashboard', async ({ page }) => {
      await settingsPage.goToDashboard();
      await expect(page).toHaveURL(/\/dashboard|\//);
    });

    test('should be accessible from dashboard user menu', async ({ page }) => {
      // Go to dashboard
      await page.goto('/dashboard');

      // Open user menu
      await page.getByRole('button', { name: /user profile menu/i }).click();

      // Click settings
      await page.getByRole('menuitem', { name: /settings/i }).click();

      // Should be on settings page
      await expect(page).toHaveURL(/\/settings/);
      await expect(settingsPage.heading).toBeVisible();
    });
  });
});
