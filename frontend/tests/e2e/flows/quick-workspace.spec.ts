import { test, expect } from '@playwright/test';

test.describe('Comprehensive Workspace UI Test', () => {
  test('should verify all workspace UI components', async ({ page }) => {
    test.setTimeout(120000); // 2 minutes for comprehensive test

    // ============ DASHBOARD ============
    console.log('--- DASHBOARD ---');
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Dashboard header
    const dashboardHeader = page.locator('[data-testid="dashboard-header"]');
    console.log(`Dashboard header visible: ${await dashboardHeader.isVisible()}`);

    // Search input
    const searchInput = page.locator('[data-testid="global-search-input"]');
    await expect(searchInput).toBeVisible();
    console.log('✓ Search input visible');

    // Matter cards
    const matterCards = page.locator('[data-testid^="matter-card-"]');
    const cardCount = await matterCards.count();
    console.log(`✓ Found ${cardCount} matter cards`);

    // New matter card
    const newMatterCard = page.locator('[data-testid="new-matter-card"]');
    console.log(`New matter card visible: ${await newMatterCard.isVisible()}`);

    // Find Nirav matter and open it
    const niravMatter = matterCards.filter({ hasText: /nirav/i }).first();
    await expect(niravMatter).toBeVisible();
    console.log('✓ Nirav matter found');

    // Check matter card components
    const resumeButton = niravMatter.locator('[data-testid="matter-card-resume-button"]');
    await expect(resumeButton).toBeVisible();
    console.log('✓ Resume button visible');

    // Click to open workspace
    await resumeButton.click();
    await page.waitForURL(/\/matter\/[a-f0-9-]+/, { timeout: 15000 });
    console.log('✓ Navigated to workspace');

    // Handle any modals that might appear (Act References, etc.)
    const dismissModal = async () => {
      await page.waitForTimeout(500);
      // Try multiple button patterns
      const buttonPatterns = [
        page.getByRole('button', { name: /skip for now/i }),
        page.getByRole('button', { name: /skip/i }),
        page.getByRole('button', { name: /continue/i }),
        page.getByRole('button', { name: /close/i }),
        page.locator('[data-state="open"] button').first(),
      ];

      for (const button of buttonPatterns) {
        try {
          if (await button.isVisible({ timeout: 1000 })) {
            await button.click();
            console.log('✓ Dismissed modal dialog');
            await page.waitForTimeout(500);
            return true;
          }
        } catch {
          // Try next pattern
        }
      }
      return false;
    };

    // Try to dismiss modals multiple times
    for (let i = 0; i < 3; i++) {
      const dismissed = await dismissModal();
      if (!dismissed) break;
    }

    // ============ WORKSPACE HEADER ============
    console.log('\n--- WORKSPACE HEADER ---');

    const workspaceHeader = page.locator('[data-testid="workspace-header"]');
    await expect(workspaceHeader).toBeVisible();
    console.log('✓ Workspace header visible');

    const backLink = page.locator('[data-testid="workspace-back-link"]');
    await expect(backLink).toBeVisible();
    console.log('✓ Back to dashboard link visible');

    const settingsButton = page.locator('[data-testid="workspace-settings-button"]');
    await expect(settingsButton).toBeVisible();
    console.log('✓ Settings button visible');

    const deleteButton = page.locator('[data-testid="workspace-delete-button"]');
    const deleteVisible = await deleteButton.isVisible().catch(() => false);
    console.log(`${deleteVisible ? '✓' : '-'} Delete button ${deleteVisible ? 'visible' : 'not shown (may be conditional)'}`);


    // ============ WORKSPACE TABS ============
    console.log('\n--- WORKSPACE TABS ---');

    const tabBar = page.locator('[data-testid="workspace-tab-bar"]');
    await expect(tabBar).toBeVisible();
    console.log('✓ Tab bar visible');

    const tabs = [
      { id: 'summary', name: 'Summary' },
      { id: 'timeline', name: 'Timeline' },
      { id: 'entities', name: 'Entities' },
      { id: 'citations', name: 'Citations' },
      { id: 'contradictions', name: 'Contradictions' },
      { id: 'verification', name: 'Verification' },
      { id: 'documents', name: 'Documents' },
    ];

    for (const tab of tabs) {
      const tabElement = page.locator(`[data-testid="workspace-tab-${tab.id}"]`);
      const isVisible = await tabElement.isVisible();
      console.log(`${isVisible ? '✓' : '✗'} ${tab.name} tab ${isVisible ? 'visible' : 'NOT FOUND'}`);
    }

    // ============ SUMMARY TAB ============
    console.log('\n--- SUMMARY TAB ---');
    await page.locator('[data-testid="workspace-tab-summary"]').click();
    await page.waitForTimeout(1000);

    const contentArea = page.locator('[data-testid="workspace-content-area"]');
    await expect(contentArea).toBeVisible();
    console.log('✓ Content area visible');

    const mainContent = page.locator('[data-testid="workspace-main-content"]');
    await expect(mainContent).toBeVisible();
    console.log('✓ Main content visible');

    // ============ DOCUMENTS TAB ============
    console.log('\n--- DOCUMENTS TAB ---');
    await page.locator('[data-testid="workspace-tab-documents"]').click();
    await expect(page).toHaveURL(/\/documents/);
    await page.waitForTimeout(1000);

    const documentsContent = page.locator('[data-testid="documents-content"]');
    await expect(documentsContent).toBeVisible();
    console.log('✓ Documents content visible');

    const documentsHeader = page.locator('[data-testid="documents-header"]');
    await expect(documentsHeader).toBeVisible();
    console.log('✓ Documents header visible');

    const addFilesButton = page.locator('[data-testid="add-files-button"]');
    await expect(addFilesButton).toBeVisible();
    console.log('✓ Add Files button visible');

    const documentList = page.locator('[data-testid="document-list"]');
    const documentListVisible = await documentList.isVisible();
    console.log(`${documentListVisible ? '✓' : '-'} Document list ${documentListVisible ? 'visible' : 'empty or loading'}`);

    if (documentListVisible) {
      const documentTable = page.locator('[data-testid="document-table"]');
      const tableVisible = await documentTable.isVisible();
      console.log(`${tableVisible ? '✓' : '-'} Document table ${tableVisible ? 'visible' : 'no documents'}`);

      if (tableVisible) {
        const docRows = page.locator('[data-testid^="document-row-"]');
        const rowCount = await docRows.count();
        console.log(`✓ Found ${rowCount} document rows`);
      }
    }

    // Helper to click tab and handle any overlays
    const clickTab = async (tabId: string, tabName: string) => {
      // Try to dismiss any dialogs first
      const skipBtn = page.getByRole('button', { name: /skip for now/i });
      if (await skipBtn.isVisible({ timeout: 500 }).catch(() => false)) {
        await skipBtn.click();
        await page.waitForTimeout(300);
      }

      const tab = page.locator(`[data-testid="workspace-tab-${tabId}"]`);
      await tab.click({ force: true });
      await page.waitForURL(new RegExp(`\\/${tabId}`), { timeout: 10000 });
      console.log(`✓ ${tabName} tab navigated`);
    };

    // ============ TIMELINE TAB ============
    console.log('\n--- TIMELINE TAB ---');
    await clickTab('timeline', 'Timeline');

    // ============ ENTITIES TAB ============
    console.log('\n--- ENTITIES TAB ---');
    await clickTab('entities', 'Entities');

    // ============ CITATIONS TAB ============
    console.log('\n--- CITATIONS TAB ---');
    await clickTab('citations', 'Citations');

    // ============ VERIFICATION TAB ============
    console.log('\n--- VERIFICATION TAB ---');
    await clickTab('verification', 'Verification');

    // ============ BACK TO DASHBOARD ============
    console.log('\n--- NAVIGATION ---');
    await backLink.click();
    await expect(page).toHaveURL(/\/dashboard/);
    console.log('✓ Back to dashboard works');

    console.log('\n=== ALL UI COMPONENTS CHECKED ===');
  });
});
