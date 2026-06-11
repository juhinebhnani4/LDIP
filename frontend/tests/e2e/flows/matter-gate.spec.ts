import { test, expect } from '@playwright/test';

/**
 * FE-ARCH-01 verification — matter workspace convergence gate (L2).
 *
 * Proves the FE-003 kill: opening a non-existent / forbidden matter shows ONE
 * clean error screen and does NOT mount the shell or the 7 feature panels, so the
 * page no longer fires ~18 background panel 404s.
 *
 * Auth is provided by tests/e2e/auth.setup.ts via the chromium project's
 * storageState (see playwright.config.ts).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
// Well-formed UUID that does not correspond to any matter the test user can see.
const BAD_MATTER_ID = '00000000-0000-0000-0000-000000000000';

test.describe('FE-ARCH-01 matter gate', () => {
  test('bad matter → clean error screen, no shell, no panel 404 storm', async ({ page }) => {
    const apiErrors: string[] = [];
    const consoleErrors: string[] = [];

    page.on('response', (res) => {
      const url = res.url();
      if (API_BASE && url.startsWith(API_BASE) && res.status() >= 400) {
        apiErrors.push(`${res.status()} ${url}`);
      }
    });
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto(`/matter/${BAD_MATTER_ID}`);

    // The gate's error screen is shown (404/403 → "Matter not available").
    await expect(page.getByText('Matter not available')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('link', { name: /back to dashboard/i })).toBeVisible();

    // The shell never mounted: the workspace <main data-matter-id> and the tab bar
    // are absent (panels live inside it, so they never fetch).
    await expect(page.locator('[data-matter-id]')).toHaveCount(0);
    await expect(page.getByRole('tab', { name: /timeline/i })).toHaveCount(0);

    // Settle, then snapshot the error state for the human record.
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'test-results/fe-arch-01-bad-matter.png', fullPage: true });

    // The FE-003 kill: at most the single gate fetch should 4xx — not ~18 panel calls.
    console.log(`[matter-gate] API 4xx during bad-matter load (${apiErrors.length}):`, apiErrors);
    console.log(`[matter-gate] console errors (${consoleErrors.length}):`, consoleErrors);
    expect(apiErrors.length, `expected ≤2 API 4xx, got:\n${apiErrors.join('\n')}`).toBeLessThanOrEqual(2);
  });

  test('valid matter (from dashboard) still renders the shell', async ({ page }) => {
    await page.goto('/dashboard');
    // Find the first matter link on the dashboard, if any.
    const matterLink = page.locator('a[href^="/matter/"]').first();
    const hasMatter = await matterLink.count();
    test.skip(hasMatter === 0, 'Test user has no matters to open — happy-path skipped.');

    const href = await matterLink.getAttribute('href');
    await page.goto(href!);

    // Shell mounts: the workspace main and at least one tab are present.
    await expect(page.locator('[data-matter-id]')).toHaveCount(1, { timeout: 20000 });
    await expect(page.getByText('Matter not available')).toHaveCount(0);
    await page.screenshot({ path: 'test-results/fe-arch-01-valid-matter.png', fullPage: true });
  });
});
