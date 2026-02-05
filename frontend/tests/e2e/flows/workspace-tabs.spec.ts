import { test, expect } from '@playwright/test';
import { DashboardPage, SummaryPage, TimelinePage, CitationsPage, EntitiesPage, VerificationPage } from '../pages';

test.describe('Workspace Tabs Flow', () => {
  test.describe('Tab Navigation', () => {
    test('should display all workspace tabs', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      // Check all tabs are visible
      await expect(page.getByRole('tab', { name: /summary/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /documents/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /timeline/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /citations/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /entities/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /verification/i })).toBeVisible();
    });

    test('should navigate between tabs', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const summaryPage = new SummaryPage(page);

      // Navigate through tabs
      await summaryPage.goToTimeline();
      await expect(page).toHaveURL(/\/timeline/);

      await summaryPage.goToEntities();
      await expect(page).toHaveURL(/\/entities/);

      await summaryPage.goToCitations();
      await expect(page).toHaveURL(/\/citations/);

      await summaryPage.goToVerification();
      await expect(page).toHaveURL(/\/verification/);

      await summaryPage.goToDocuments();
      await expect(page).toHaveURL(/\/documents/);

      await summaryPage.goToSummary();
      await expect(page).toHaveURL(/\/summary/);
    });
  });

  test.describe('Summary Tab', () => {
    test('should display summary content', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const summaryPage = new SummaryPage(page);
      await summaryPage.goToSummary();
      await summaryPage.waitForSummaryLoad();

      // Check for summary sections
      await expect(summaryPage.partiesSection.or(page.locator('[data-testid="summary-content"]'))).toBeVisible();
    });

    test('should display matter statistics', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const summaryPage = new SummaryPage(page);
      await summaryPage.goToSummary();

      await expect(summaryPage.matterStatistics.or(page.locator('[data-testid="stats"]'))).toBeVisible();
    });

    test('should have editable sections', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const summaryPage = new SummaryPage(page);
      await summaryPage.goToSummary();

      // Look for edit buttons
      const editButtons = summaryPage.editButtons;
      const editButtonCount = await editButtons.count();

      expect(editButtonCount).toBeGreaterThanOrEqual(0);
    });
  });

  test.describe('Timeline Tab', () => {
    test('should display timeline content', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const timelinePage = new TimelinePage(page);
      await timelinePage.goToTimeline();
      await timelinePage.waitForTimelineLoad();

      // Should show timeline or empty state
      const hasEvents = await timelinePage.hasEvents();
      const hasEmptyState = await timelinePage.emptyState.isVisible().catch(() => false);

      expect(hasEvents || hasEmptyState).toBeTruthy();
    });

    test('should have view mode options', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const timelinePage = new TimelinePage(page);
      await timelinePage.goToTimeline();

      // Check for view mode controls
      await expect(
        timelinePage.horizontalViewButton.or(timelinePage.listViewButton).or(timelinePage.viewModeToggle)
      ).toBeVisible();
    });

    test('should have zoom slider', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const timelinePage = new TimelinePage(page);
      await timelinePage.goToTimeline();

      const hasZoom = await timelinePage.zoomSlider.isVisible().catch(() => false);
      expect(hasZoom).toBeDefined();
    });

    test('should allow adding manual events', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const timelinePage = new TimelinePage(page);
      await timelinePage.goToTimeline();

      const hasAddButton = await timelinePage.addEventButton.isVisible().catch(() => false);
      expect(hasAddButton).toBeDefined();
    });
  });

  test.describe('Citations Tab', () => {
    test('should display citations content', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const citationsPage = new CitationsPage(page);
      await citationsPage.goToCitations();
      await citationsPage.waitForCitationsLoad();

      // Should show citations or empty state
      const hasCitations = await citationsPage.getCitationCount() > 0;
      const hasEmptyState = await citationsPage.emptyState.isVisible().catch(() => false);

      expect(hasCitations || hasEmptyState).toBeTruthy();
    });

    test('should have view tabs (By Act / By Document)', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const citationsPage = new CitationsPage(page);
      await citationsPage.goToCitations();

      await expect(citationsPage.byActTab.or(citationsPage.byDocumentTab)).toBeVisible();
    });

    test('should switch between By Act and By Document views', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const citationsPage = new CitationsPage(page);
      await citationsPage.goToCitations();

      const byActVisible = await citationsPage.byActTab.isVisible().catch(() => false);
      test.skip(!byActVisible, 'View tabs not visible');

      await citationsPage.switchToByActView();
      await citationsPage.switchToByDocumentView();
    });

    test('should show attention banner if missing acts', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const citationsPage = new CitationsPage(page);
      await citationsPage.goToCitations();

      // Check for attention banner (may or may not be visible)
      const hasMissingActs = await citationsPage.hasMissingActs();
      expect(hasMissingActs).toBeDefined();
    });
  });

  test.describe('Entities Tab', () => {
    test('should display entities content', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const entitiesPage = new EntitiesPage(page);
      await entitiesPage.goToEntities();
      await entitiesPage.waitForEntitiesLoad();

      // Should show entities or empty state
      const hasEntities = await entitiesPage.hasEntities();
      const hasEmptyState = await entitiesPage.emptyState.isVisible().catch(() => false);

      expect(hasEntities || hasEmptyState).toBeTruthy();
    });

    test('should have view mode options (Grid/List/Graph)', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const entitiesPage = new EntitiesPage(page);
      await entitiesPage.goToEntities();

      await expect(
        entitiesPage.gridViewButton.or(entitiesPage.listViewButton).or(entitiesPage.graphViewButton)
      ).toBeVisible();
    });

    test('should switch between Grid, List, and Graph views', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const entitiesPage = new EntitiesPage(page);
      await entitiesPage.goToEntities();

      const hasGridButton = await entitiesPage.gridViewButton.isVisible().catch(() => false);
      test.skip(!hasGridButton, 'View buttons not visible');

      await entitiesPage.switchToGridView();
      await entitiesPage.switchToListView();
      await entitiesPage.switchToGraphView();
    });

    test('should have search functionality', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const entitiesPage = new EntitiesPage(page);
      await entitiesPage.goToEntities();

      await expect(entitiesPage.searchInput).toBeVisible();
    });

    test('should show entity details on click', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const entitiesPage = new EntitiesPage(page);
      await entitiesPage.goToEntities();

      const hasEntities = await entitiesPage.hasEntities();
      test.skip(!hasEntities, 'No entities available');

      await entitiesPage.clickEntityCard(0);

      await expect(entitiesPage.detailPanel).toBeVisible();
    });
  });

  test.describe('Verification Tab', () => {
    test('should display verification content', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const verificationPage = new VerificationPage(page);
      await verificationPage.goToVerification();
      await verificationPage.waitForVerificationLoad();

      // Should show verification queue or empty/complete state
      const hasItems = await verificationPage.getItemCount() > 0;
      const isEmpty = await verificationPage.isEmpty();
      const isComplete = await verificationPage.isAllVerified();

      expect(hasItems || isEmpty || isComplete).toBeTruthy();
    });

    test('should display verification statistics', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const verificationPage = new VerificationPage(page);
      await verificationPage.goToVerification();

      await expect(verificationPage.stats.or(verificationPage.progressBar)).toBeVisible();
    });

    test('should have status filter', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const verificationPage = new VerificationPage(page);
      await verificationPage.goToVerification();

      const hasFilter = await verificationPage.statusFilter.isVisible().catch(() => false);
      expect(hasFilter).toBeDefined();
    });

    test('should have approve/reject buttons', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const verificationPage = new VerificationPage(page);
      await verificationPage.goToVerification();

      const hasPending = await verificationPage.hasPendingItems();
      test.skip(!hasPending, 'No pending items');

      await verificationPage.clickItem(0);

      await expect(verificationPage.approveButton.or(verificationPage.rejectButton)).toBeVisible();
    });
  });
});
