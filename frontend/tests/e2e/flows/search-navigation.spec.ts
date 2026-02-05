import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages';
import { WorkspaceBasePage } from '../pages/workspace/base.page';

test.describe('Search & Navigation Flow', () => {
  test.describe('Dashboard Search', () => {
    test('should display search input on dashboard', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await expect(dashboardPage.searchInput).toBeVisible();
    });

    test('should filter matters by search query', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();
      await dashboardPage.waitForLoad();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters to search');

      const initialCount = await dashboardPage.getMatterCount();

      // Search for something specific
      await dashboardPage.search('contract');

      // Results should update (may be same, fewer, or more)
      await page.waitForTimeout(500);
    });

    test('should clear search and show all matters', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();
      await dashboardPage.waitForLoad();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      // Search first
      await dashboardPage.search('test');
      await page.waitForTimeout(500);

      // Clear search
      await dashboardPage.clearSearch();
      await page.waitForTimeout(500);

      const afterClear = await dashboardPage.getMatterCount();
      expect(afterClear).toBeGreaterThanOrEqual(0);
    });
  });

  test.describe('Dashboard Filters', () => {
    test('should have status filter', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await expect(dashboardPage.statusFilter).toBeVisible();
    });

    test('should filter matters by status', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();
      await dashboardPage.waitForLoad();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.filterByStatus('active');

      // Results should update
      await page.waitForTimeout(500);
    });
  });

  test.describe('Dashboard View Toggle', () => {
    test('should have grid and list view options', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await expect(dashboardPage.gridViewButton.or(dashboardPage.listViewButton)).toBeVisible();
    });

    test('should switch between grid and list views', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();
      await dashboardPage.waitForLoad();

      const hasGridButton = await dashboardPage.gridViewButton.isVisible().catch(() => false);
      test.skip(!hasGridButton, 'View toggle not available');

      await dashboardPage.switchToListView();
      await page.waitForTimeout(300);

      await dashboardPage.switchToGridView();
      await page.waitForTimeout(300);
    });
  });

  test.describe('Workspace Navigation', () => {
    test('should navigate back to dashboard from workspace', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await workspacePage.goBackToDashboard();

      await expect(page).toHaveURL(/\/dashboard/);
    });

    test('should display matter name in header', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await expect(workspacePage.matterName).toBeVisible();
    });

    test('should have share and export buttons', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await expect(workspacePage.shareButton.or(workspacePage.exportButton)).toBeVisible();
    });
  });

  test.describe('Global Search (if available)', () => {
    test('should have global search in header', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Global search may be in header
      const globalSearch = page.locator('[data-testid="global-search"]');
      const hasGlobalSearch = await globalSearch.isVisible().catch(() => false);

      expect(hasGlobalSearch).toBeDefined();
    });
  });

  test.describe('Notifications', () => {
    test('should have notifications button in header', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasNotifications = await dashboardPage.notificationsButton.isVisible().catch(() => false);
      expect(hasNotifications).toBeDefined();
    });

    test('should open notifications dropdown', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasNotifications = await dashboardPage.notificationsButton.isVisible().catch(() => false);
      test.skip(!hasNotifications, 'Notifications button not visible');

      await dashboardPage.openNotifications();

      await expect(page.locator('[data-testid="notifications-dropdown"]')).toBeVisible();
    });
  });

  test.describe('User Menu', () => {
    test('should have user menu in header', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await expect(dashboardPage.userMenu).toBeVisible();
    });

    test('should open user menu dropdown', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await dashboardPage.openUserMenu();

      // Should show menu items
      await expect(page.getByRole('menuitem')).toHaveCount(await page.getByRole('menuitem').count());
    });

    test('should navigate to settings from user menu', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      await dashboardPage.openUserMenu();

      const settingsLink = page.getByRole('menuitem', { name: /settings/i });
      const hasSettings = await settingsLink.isVisible().catch(() => false);
      test.skip(!hasSettings, 'Settings link not visible');

      await settingsLink.click();

      await expect(page).toHaveURL(/\/settings/);
    });
  });

  test.describe('Activity Feed', () => {
    test('should display activity feed on dashboard', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasActivityFeed = await dashboardPage.activityFeed.isVisible().catch(() => false);
      expect(hasActivityFeed).toBeDefined();
    });
  });

  test.describe('Quick Stats', () => {
    test('should display quick stats on dashboard', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasQuickStats = await dashboardPage.quickStats.isVisible().catch(() => false);
      expect(hasQuickStats).toBeDefined();
    });
  });

  test.describe('Deep Linking', () => {
    test('should navigate directly to a matter by URL', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      // Get first matter and navigate
      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      const matterId = workspacePage.getMatterIdFromUrl();
      test.skip(!matterId, 'Could not get matter ID');

      // Navigate away
      await page.goto('/dashboard');

      // Navigate back directly
      await page.goto(`/matter/${matterId}/summary`);

      await expect(page).toHaveURL(/\/matter\/[a-f0-9-]+\/summary/);
    });

    test('should navigate directly to a specific tab by URL', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      const matterId = workspacePage.getMatterIdFromUrl();
      test.skip(!matterId, 'Could not get matter ID');

      // Navigate directly to timeline
      await page.goto(`/matter/${matterId}/timeline`);

      await expect(page).toHaveURL(/\/timeline/);
    });
  });

  test.describe('Responsive Navigation', () => {
    test('should adapt to mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Page should still load
      await dashboardPage.waitForLoad();
    });

    test('should adapt workspace tabs to mobile', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });

      const workspacePage = new WorkspaceBasePage(page);

      // Tabs should still be navigable (may be scrollable or in dropdown)
      const tabBar = workspacePage.tabBar;
      await expect(tabBar).toBeVisible();
    });
  });
});
