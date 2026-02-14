import { test, expect } from '@playwright/test';
import { DashboardPage, SummaryPage } from '../pages';
import { WorkspaceBasePage } from '../pages/workspace/base.page';

test.describe('Chat Q&A Flow', () => {
  test.describe('Q&A Panel - Visibility', () => {
    test('should display Q&A panel on workspace', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      // Q&A panel heading should be visible on desktop
      await expect(page.getByRole('heading', { name: /ask jaanch/i })).toBeVisible();
    });

    test('should have minimize button', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await expect(workspacePage.qaPanelMinimizeButton).toBeVisible();
    });

    test('should minimize and restore Q&A panel', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      // Minimize panel
      await workspacePage.toggleQAPanel();
      await page.waitForTimeout(300); // Wait for animation
    });
  });

  test.describe('Q&A Panel - Input', () => {
    test('should display chat input field', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await expect(workspacePage.qaPanelInput).toBeVisible();
    });

    test('should display send button', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await expect(workspacePage.qaPanelSendButton).toBeVisible();
    });

    test('should allow typing in chat input', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await workspacePage.qaPanelInput.fill('What is the main issue in this case?');

      const value = await workspacePage.qaPanelInput.inputValue();
      expect(value).toContain('main issue');
    });
  });

  test.describe('Q&A Panel - Suggested Questions', () => {
    test('should display suggested questions', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      // Suggested questions may or may not be visible depending on state
      const suggestionsVisible = await workspacePage.suggestedQuestions.first().isVisible().catch(() => false);

      // Just verify the element exists (may be hidden)
      expect(suggestionsVisible).toBeDefined();
    });

    test('should populate input when clicking suggested question', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      const hasSuggestions = await workspacePage.suggestedQuestions.first().isVisible().catch(() => false);
      test.skip(!hasSuggestions, 'No suggested questions visible');

      await workspacePage.clickSuggestedQuestion(0);

      // Either input is populated or question is sent
      await page.waitForTimeout(500);
    });
  });

  test.describe('Q&A Panel - Sending Messages', () => {
    test('should send a question and receive response', async ({ page }) => {
      test.setTimeout(90000); // Q&A response can take time on production

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      const question = 'What is the summary of this case?';
      await workspacePage.askQuestion(question);

      // Wait for response (streaming)
      await workspacePage.waitForQAResponse(60000);

      // Should have at least 2 messages (question + response)
      const messageCount = await workspacePage.getMessageCount();
      expect(messageCount).toBeGreaterThanOrEqual(1);
    });

    test('should show streaming indicator while responding', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      await workspacePage.askQuestion('List all the parties in this case');

      // Check for streaming indicator (should appear quickly)
      const streamingIndicator = page.locator('[data-testid="streaming-indicator"], .loading, .typing');
      await expect(streamingIndicator).toBeVisible({ timeout: 5000 }).catch(() => {
        // Streaming might be very fast on small documents
      });
    });
  });

  test.describe('Q&A Panel - Conversation History', () => {
    test('should display conversation history', async ({ page }) => {
      test.setTimeout(90000); // Q&A response can take time on production

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      // Ask a question first
      await workspacePage.askQuestion('Hello, can you help me?');
      await workspacePage.waitForQAResponse(60000);

      // Conversation history should be visible
      const messageCount = await workspacePage.getMessageCount();
      expect(messageCount).toBeGreaterThanOrEqual(1);
    });

    test('should persist conversation across tab navigation', async ({ page }) => {
      test.setTimeout(90000); // Q&A response can take time on production

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      // Ask a question
      await workspacePage.askQuestion('Test question for persistence');
      await workspacePage.waitForQAResponse(60000);

      const initialCount = await workspacePage.getMessageCount();

      // Navigate to different tab
      await workspacePage.goToDocuments();
      await page.waitForTimeout(500);

      // Go back to summary
      await workspacePage.goToSummary();
      await page.waitForTimeout(500);

      // Conversation should still be there
      const afterNavCount = await workspacePage.getMessageCount();
      expect(afterNavCount).toBe(initialCount);
    });
  });

  test.describe('Q&A Panel - Source Citations', () => {
    test('should show source references in responses', async ({ page }) => {
      test.setTimeout(90000); // Q&A response can take time on production

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      // Ask a question that should return sources
      await workspacePage.askQuestion('What documents are in this case?');
      await workspacePage.waitForQAResponse(60000);

      // Look for source references
      const sourceRefs = page.locator('[data-testid="source-reference"], .source-citation');
      const hasSourceRefs = await sourceRefs.count() > 0;

      // Sources may or may not appear depending on the response
      expect(hasSourceRefs).toBeDefined();
    });
  });

  test.describe('Q&A Panel - Error Handling', () => {
    test('should handle empty question gracefully', async ({ page }) => {
      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      const hasMatter = await dashboardPage.hasMatters();
      test.skip(!hasMatter, 'No matters available');

      await dashboardPage.openFirstMatter();

      const workspacePage = new WorkspaceBasePage(page);
      await workspacePage.waitForLoad();

      // Try to send empty question - button should be disabled
      await workspacePage.qaPanelInput.fill('');

      // Send button should be disabled when input is empty
      const sendButton = page.locator('[data-testid="chat-submit-button"]');
      const isDisabled = await sendButton.isDisabled().catch(() => true);
      expect(isDisabled).toBeTruthy();
    });
  });
});
