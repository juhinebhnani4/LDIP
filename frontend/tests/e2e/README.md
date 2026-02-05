# E2E Testing with Playwright

This directory contains end-to-end tests for the legal document management application using [Playwright](https://playwright.dev/).

## Quick Start

```bash
# Install dependencies (including Playwright)
npm install

# Install Playwright browsers
npx playwright install

# Run all E2E tests
npm run test:e2e

# Run tests with UI mode (recommended for development)
npm run test:e2e:ui

# Run tests in headed mode (see browser)
npm run test:e2e:headed

# Run tests in debug mode
npm run test:e2e:debug

# View test report
npm run test:e2e:report

# Generate tests with codegen
npm run test:e2e:codegen
```

## Directory Structure

```
tests/e2e/
├── fixtures/                    # Test fixtures and helpers
│   ├── auth.fixture.ts         # Authentication helpers
│   ├── matter.fixture.ts       # Matter management helpers
│   ├── documents.fixture.ts    # Document upload helpers
│   └── files/                  # Test PDF files (add your own)
├── pages/                       # Page Object Models
│   ├── login.page.ts           # Login page
│   ├── dashboard.page.ts       # Dashboard page
│   ├── upload.page.ts          # Upload wizard
│   └── workspace/              # Matter workspace pages
│       ├── base.page.ts        # Common workspace elements
│       ├── summary.page.ts     # Summary tab
│       ├── documents.page.ts   # Documents tab
│       ├── timeline.page.ts    # Timeline tab
│       ├── citations.page.ts   # Citations tab
│       ├── entities.page.ts    # Entities tab
│       └── verification.page.ts # Verification tab
├── flows/                       # Test specs by user flow
│   ├── auth.spec.ts            # Authentication tests
│   ├── matter-creation.spec.ts # Matter creation flow
│   ├── document-management.spec.ts
│   ├── chat-qa.spec.ts         # Q&A panel tests
│   ├── workspace-tabs.spec.ts  # All workspace tabs
│   └── search-navigation.spec.ts
├── .auth/                       # Auth state storage (gitignored)
├── auth.setup.ts               # Authentication setup
└── README.md                   # This file
```

## Configuration

### Environment Variables

Create a `.env.local` file in the frontend directory:

```env
# Test user credentials
TEST_USER_EMAIL=test@example.com
TEST_USER_PASSWORD=your-test-password

# Optional: Secondary test user
TEST_USER_SECONDARY_EMAIL=test2@example.com
TEST_USER_SECONDARY_PASSWORD=your-test-password

# Base URL (if different from default)
PLAYWRIGHT_BASE_URL=http://localhost:3000
```

### Test Files

Place your test PDF files in `tests/e2e/fixtures/files/`:

- `sample-contract.pdf` - A sample contract document
- `sample-pleading.pdf` - A sample legal pleading
- `sample-act.pdf` - A sample legal act (statute)
- `large-document.pdf` - For performance testing
- `poor-ocr-sample.pdf` - For OCR quality testing

## Test Coverage

### User Flows Tested

| Flow | Tests | Description |
|------|-------|-------------|
| **Authentication** | 12 | Login, signup, password reset, session management |
| **Matter Creation** | 15 | Upload wizard, file selection, processing |
| **Document Management** | 12 | Add, rename, delete, status indicators |
| **Chat Q&A** | 10 | Input, sending, streaming, history |
| **Workspace Tabs** | 20 | Summary, timeline, citations, entities, verification |
| **Search & Navigation** | 15 | Dashboard search, filters, deep linking |

### Page Objects

Each page object provides:
- Locators for all interactive elements
- Helper methods for common actions
- Assertions for expected states

## Writing Tests

### Using Page Objects

```typescript
import { test, expect } from '@playwright/test';
import { LoginPage, DashboardPage } from '../pages';

test('should login and view dashboard', async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.loginAndWaitForDashboard('user@example.com', 'password');

  const dashboardPage = new DashboardPage(page);
  await expect(dashboardPage.matterCards).toBeVisible();
});
```

### Using Fixtures

```typescript
import { test, expect } from '../fixtures/auth.fixture';

test('should have auth helper', async ({ page, auth }) => {
  await auth.login();
  // ... rest of test
});
```

### Data-Dependent Tests

Tests that require existing data use `test.skip()`:

```typescript
test('should open matter', async ({ page }) => {
  const dashboardPage = new DashboardPage(page);
  await dashboardPage.goto();

  const hasMatter = await dashboardPage.hasMatters();
  test.skip(!hasMatter, 'No matters available for testing');

  await dashboardPage.openFirstMatter();
});
```

## Running Specific Tests

```bash
# Run a specific test file
npx playwright test tests/e2e/flows/auth.spec.ts

# Run tests matching a pattern
npx playwright test -g "should login"

# Run tests in a specific browser
npx playwright test --project=chromium

# Run tests in a specific viewport
npx playwright test --project="Mobile Chrome"
```

## Debugging

### UI Mode (Recommended)

```bash
npm run test:e2e:ui
```

Opens an interactive UI where you can:
- Watch tests run in real-time
- Step through tests
- Inspect DOM at each step
- Time-travel through test execution

### Debug Mode

```bash
npm run test:e2e:debug
```

Opens browser with DevTools and pauses at `page.pause()` statements.

### Codegen

```bash
npm run test:e2e:codegen
```

Records your browser actions and generates test code.

## CI/CD Integration

The tests are configured to run in CI with:
- Single worker for stability
- Retries on failure
- HTML report generation
- Screenshot/video on failure

Example GitHub Actions:

```yaml
- name: Run E2E tests
  run: |
    cd frontend
    npm ci
    npx playwright install --with-deps
    npm run test:e2e
```

## Best Practices

1. **Use Page Objects** - Keep selectors and actions in page objects
2. **Skip gracefully** - Use `test.skip()` for data-dependent tests
3. **Isolate tests** - Each test should be independent
4. **Use descriptive names** - Test names should describe the behavior
5. **Wait properly** - Use Playwright's auto-waiting, avoid `waitForTimeout`
6. **Test user journeys** - Focus on complete flows, not just clicks

## Troubleshooting

### Browser not installed

```bash
npx playwright install
```

### Tests failing due to auth

1. Check test user credentials in `.env.local`
2. Ensure the test user exists in your database
3. Delete `.auth/user.json` and re-run

### Timeouts

Increase timeout in specific tests:

```typescript
test('slow test', async ({ page }) => {
  test.setTimeout(120000); // 2 minutes
  // ...
});
```

### Element not found

1. Add `data-testid` attributes to components
2. Update locators in page objects
3. Use Playwright's inspector to find correct selectors
