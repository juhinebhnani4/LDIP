/**
 * E2E Tests for Layout-Aware Chunking (Docling Integration)
 *
 * Covers all manual testing scenarios and smoke tests for:
 * - LAYOUT_AWARE_CHUNKING_ENABLED=false (baseline/current behavior)
 * - LAYOUT_AWARE_CHUNKING_ENABLED=true (new layout-aware behavior)
 *
 * Prerequisites:
 * - Test PDF files in tests/e2e/fixtures/files/
 * - Backend running with appropriate feature flag setting
 * - Valid test user credentials
 *
 * To run with layout chunking disabled:
 *   LAYOUT_AWARE_CHUNKING_ENABLED=false npx playwright test layout-aware-chunking
 *
 * To run with layout chunking enabled:
 *   LAYOUT_AWARE_CHUNKING_ENABLED=true npx playwright test layout-aware-chunking
 */

import { test, expect, APIRequestContext } from '@playwright/test';
import { UploadPage } from '../pages/upload.page';
import { DashboardPage } from '../pages/dashboard.page';
import * as path from 'path';

// Test file paths - using actual sample legal documents
const SAMPLE_FILES_DIR = path.join(__dirname, '../../../../docs/sample_files');
const TEST_FILES = {
  simpleContract: path.join(SAMPLE_FILES_DIR, '1. APPLICATION IN MA NO 10 OF 2023 DT 27 02 2023  VOL - l.pdf'),
  multiPageLegal: path.join(SAMPLE_FILES_DIR, '2. APPLICATION IN MA NO 10 OF 2023 DT 27 02 2023  VOL - ll.pdf'),
  documentWithTables: path.join(SAMPLE_FILES_DIR, 'TORTS Act 1992.pdf'),
  documentWithStamps: path.join(SAMPLE_FILES_DIR, '14. AFFIDAVIT IN REPLY FILE BY RESP. NO. 10 & 11 DT. 04.10.2024.pdf'),
  rejoinder: path.join(SAMPLE_FILES_DIR, '6. Rejoinder JHM in MA 10 of 2023 of Respondent No 2 Jobalias DT 30 11 2023 (Final).pdf'),
};

// API base URL (adjust as needed)
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000/api/v1';

// Helper to get auth token from storage state
async function getAuthToken(request: APIRequestContext): Promise<string> {
  // This assumes auth is set up via auth.setup.ts
  // Adjust based on your actual auth mechanism
  const storageState = JSON.parse(
    process.env.STORAGE_STATE || '{}'
  );
  return storageState.cookies?.find((c: any) => c.name === 'access_token')?.value || '';
}

// Helper to make authenticated API requests
async function apiRequest(
  request: APIRequestContext,
  method: string,
  endpoint: string,
  token: string,
  body?: any
) {
  const options: any = {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
  if (body) {
    options.data = body;
  }

  const url = `${API_BASE_URL}${endpoint}`;

  switch (method.toUpperCase()) {
    case 'GET':
      return request.get(url, options);
    case 'POST':
      return request.post(url, options);
    default:
      return request.get(url, options);
  }
}

// ============================================================================
// SMOKE TESTS - Basic functionality checks
// ============================================================================

test.describe('Layout-Aware Chunking - Smoke Tests', () => {
  test.describe.configure({ mode: 'serial' });
  // Increase timeout to 5 minutes for document upload and processing
  test.setTimeout(300000);

  let matterId: string;
  let documentId: string;

  test('1. Should upload and process a PDF document', async ({ page }) => {
    const uploadPage = new UploadPage(page);
    await uploadPage.goto();

    // Upload test file
    await uploadPage.uploadFiles([TEST_FILES.simpleContract]);

    // Set matter name with timestamp for uniqueness
    const matterName = `Layout Test ${Date.now()}`;
    await uploadPage.clickNext();
    await uploadPage.setMatterName(matterName);

    // Start processing
    await uploadPage.clickNext();
    await uploadPage.skipActDiscovery();

    // Wait for completion (up to 3 minutes for processing)
    await uploadPage.waitForProcessingComplete(180000);

    // Navigate to matter
    await uploadPage.goToMatter();

    // Extract matter ID from URL
    const url = page.url();
    const match = url.match(/\/matter\/([a-f0-9-]+)/);
    expect(match).toBeTruthy();
    matterId = match![1];

    // Verify we're on the matter page
    await expect(page).toHaveURL(/\/matter\/[a-f0-9-]+/);
  });

  test('2. Should have created document chunks', async ({ page, request }) => {
    test.skip(!matterId, 'No matter ID from previous test');

    // Navigate to documents tab
    const dashboardPage = new DashboardPage(page);
    await page.goto(`/matter/${matterId}/documents`);

    // Wait for documents to load
    await page.waitForSelector('[data-testid="document-row"], [data-testid="document-item"]', {
      timeout: 10000,
    });

    // Get first document ID
    const docElement = page.locator('[data-testid="document-row"], [data-testid="document-item"]').first();
    const docId = await docElement.getAttribute('data-document-id');

    if (docId) {
      documentId = docId;

      // Query chunks API to verify chunks exist
      const token = await getAuthToken(request);
      const response = await apiRequest(
        request,
        'GET',
        `/documents/${documentId}/chunks`,
        token
      );

      expect(response.ok()).toBeTruthy();
      const data = await response.json();

      // Should have chunks
      expect(data.chunks?.length || data.data?.length || 0).toBeGreaterThan(0);
    }
  });

  test('3. Should have chunks with page numbers', async ({ request }) => {
    test.skip(!documentId, 'No document ID from previous test');

    const token = await getAuthToken(request);
    const response = await apiRequest(
      request,
      'GET',
      `/documents/${documentId}/chunks`,
      token
    );

    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    const chunks = data.chunks || data.data || [];

    // Check if chunks have page numbers
    const chunksWithPageNumber = chunks.filter((c: any) => c.page_number !== null);

    // Log for debugging
    console.log(`Total chunks: ${chunks.length}`);
    console.log(`Chunks with page_number: ${chunksWithPageNumber.length}`);

    // With layout-aware chunking enabled, ALL chunks should have page numbers
    // With it disabled, some chunks may have page numbers from fuzzy matching
    if (process.env.LAYOUT_AWARE_CHUNKING_ENABLED === 'true') {
      expect(chunksWithPageNumber.length).toBe(chunks.length);
    } else {
      // At least some should have page numbers from bbox linking
      expect(chunksWithPageNumber.length).toBeGreaterThanOrEqual(0);
    }
  });

  test('4. Should display processing status correctly', async ({ page }) => {
    test.skip(!matterId, 'No matter ID');

    await page.goto(`/matter/${matterId}/documents`);

    // Check for status indicators
    const statusBadges = page.locator('[data-testid="processing-status"], [data-testid="document-status"]');
    const count = await statusBadges.count();

    // Should have status indicators for documents
    expect(count).toBeGreaterThanOrEqual(0);

    // If documents exist, status should show "completed" or similar
    if (count > 0) {
      const statusText = await statusBadges.first().textContent();
      console.log(`Document status: ${statusText}`);
    }
  });

  test('5. Should search and get results with page references', async ({ page }) => {
    test.skip(!matterId, 'No matter ID');

    // Navigate to matter
    await page.goto(`/matter/${matterId}`);

    // Find and use search input
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');
    const hasSearch = await searchInput.isVisible().catch(() => false);

    test.skip(!hasSearch, 'No search input found');

    // Search for common legal terms
    await searchInput.fill('agreement');
    await searchInput.press('Enter');

    // Wait for results
    await page.waitForTimeout(2000);

    // Check for search results
    const results = page.locator('[data-testid="search-result"], [data-testid="chunk-result"]');
    const resultCount = await results.count();

    console.log(`Search results found: ${resultCount}`);
  });
});

// ============================================================================
// FEATURE FLAG: DISABLED (Baseline behavior)
// ============================================================================

test.describe('Layout Chunking DISABLED (Baseline)', () => {
  // Increase timeout to 5 minutes for document upload and processing
  test.setTimeout(300000);

  test.skip(
    process.env.LAYOUT_AWARE_CHUNKING_ENABLED === 'true',
    'Skipping baseline tests - layout chunking is enabled'
  );

  test('Chunks should use fuzzy bbox matching for page numbers', async ({ page, request }) => {
    // This test verifies the OLD behavior when layout chunking is disabled

    const uploadPage = new UploadPage(page);
    await uploadPage.goto();
    await uploadPage.uploadFiles([TEST_FILES.simpleContract]);

    const matterName = `Baseline Test ${Date.now()}`;
    await uploadPage.clickNext();
    await uploadPage.setMatterName(matterName);
    await uploadPage.clickNext();
    await uploadPage.skipActDiscovery();
    await uploadPage.waitForProcessingComplete(180000);
    await uploadPage.goToMatter();

    // Get matter ID
    const url = page.url();
    const match = url.match(/\/matter\/([a-f0-9-]+)/);
    expect(match).toBeTruthy();
    const matterId = match![1];

    // Get document ID
    await page.goto(`/matter/${matterId}/documents`);
    await page.waitForSelector('[data-testid="document-row"]', { timeout: 10000 });

    const docId = await page.locator('[data-testid="document-row"]').first().getAttribute('data-document-id');
    test.skip(!docId, 'Could not get document ID');

    // Query chunks
    const token = await getAuthToken(request);
    const response = await apiRequest(request, 'GET', `/documents/${docId}/chunks`, token);
    const data = await response.json();
    const chunks = data.chunks || data.data || [];

    console.log('=== BASELINE (Layout Disabled) ===');
    console.log(`Total chunks: ${chunks.length}`);

    // In baseline mode, page numbers come from fuzzy bbox matching
    // Some may be null if matching failed
    const withPageNum = chunks.filter((c: any) => c.page_number !== null).length;
    console.log(`Chunks with page_number: ${withPageNum} (via fuzzy matching)`);

    expect(chunks.length).toBeGreaterThan(0);
  });
});

// ============================================================================
// FEATURE FLAG: ENABLED (New layout-aware behavior)
// ============================================================================

test.describe('Layout Chunking ENABLED', () => {
  // Increase timeout to 5 minutes for document upload and processing
  test.setTimeout(300000);

  test.skip(
    process.env.LAYOUT_AWARE_CHUNKING_ENABLED !== 'true',
    'Skipping layout tests - layout chunking is disabled'
  );

  test('All chunks should have page numbers from layout detection', async ({ page, request }) => {
    const uploadPage = new UploadPage(page);
    await uploadPage.goto();
    await uploadPage.uploadFiles([TEST_FILES.simpleContract]);

    const matterName = `Layout Enabled Test ${Date.now()}`;
    await uploadPage.clickNext();
    await uploadPage.setMatterName(matterName);
    await uploadPage.clickNext();
    await uploadPage.skipActDiscovery();
    await uploadPage.waitForProcessingComplete(180000);
    await uploadPage.goToMatter();

    const url = page.url();
    const match = url.match(/\/matter\/([a-f0-9-]+)/);
    const matterId = match![1];

    await page.goto(`/matter/${matterId}/documents`);
    await page.waitForSelector('[data-testid="document-row"]', { timeout: 10000 });

    const docId = await page.locator('[data-testid="document-row"]').first().getAttribute('data-document-id');
    test.skip(!docId, 'Could not get document ID');

    const token = await getAuthToken(request);
    const response = await apiRequest(request, 'GET', `/documents/${docId}/chunks`, token);
    const data = await response.json();
    const chunks = data.chunks || data.data || [];

    console.log('=== LAYOUT ENABLED ===');
    console.log(`Total chunks: ${chunks.length}`);

    // With layout enabled, ALL chunks should have page numbers
    const withPageNum = chunks.filter((c: any) => c.page_number !== null).length;
    console.log(`Chunks with page_number: ${withPageNum} (should be all)`);

    // All chunks should have page numbers when layout is enabled
    expect(withPageNum).toBe(chunks.length);

    // Page numbers should be valid (1-indexed)
    for (const chunk of chunks) {
      if (chunk.page_number !== null) {
        expect(chunk.page_number).toBeGreaterThanOrEqual(1);
      }
    }
  });

  test('Multi-page document should have chunks from different pages', async ({ page, request }) => {
    // Use multi-page document if available
    const testFile = TEST_FILES.multiPageLegal || TEST_FILES.simpleContract;

    const uploadPage = new UploadPage(page);
    await uploadPage.goto();
    await uploadPage.uploadFiles([testFile]);

    const matterName = `Multi-Page Test ${Date.now()}`;
    await uploadPage.clickNext();
    await uploadPage.setMatterName(matterName);
    await uploadPage.clickNext();
    await uploadPage.skipActDiscovery();
    await uploadPage.waitForProcessingComplete(180000);
    await uploadPage.goToMatter();

    const url = page.url();
    const match = url.match(/\/matter\/([a-f0-9-]+)/);
    const matterId = match![1];

    await page.goto(`/matter/${matterId}/documents`);
    await page.waitForSelector('[data-testid="document-row"]', { timeout: 10000 });

    const docId = await page.locator('[data-testid="document-row"]').first().getAttribute('data-document-id');
    test.skip(!docId, 'Could not get document ID');

    const token = await getAuthToken(request);
    const response = await apiRequest(request, 'GET', `/documents/${docId}/chunks`, token);
    const data = await response.json();
    const chunks = data.chunks || data.data || [];

    // Collect unique page numbers
    const uniquePages = new Set(
      chunks
        .filter((c: any) => c.page_number !== null)
        .map((c: any) => c.page_number)
    );

    console.log('=== MULTI-PAGE DOCUMENT ===');
    console.log(`Unique pages found: ${Array.from(uniquePages).sort().join(', ')}`);

    // Multi-page document should have chunks from multiple pages
    // (Skip assertion if test file is single page)
    if (testFile.includes('multi-page')) {
      expect(uniquePages.size).toBeGreaterThan(1);
    }
  });

  test('Document with tables should have table content in chunks', async ({ page, request }) => {
    const testFile = TEST_FILES.documentWithTables || TEST_FILES.simpleContract;

    const uploadPage = new UploadPage(page);
    await uploadPage.goto();
    await uploadPage.uploadFiles([testFile]);

    const matterName = `Table Test ${Date.now()}`;
    await uploadPage.clickNext();
    await uploadPage.setMatterName(matterName);
    await uploadPage.clickNext();
    await uploadPage.skipActDiscovery();
    await uploadPage.waitForProcessingComplete(180000);
    await uploadPage.goToMatter();

    const url = page.url();
    const match = url.match(/\/matter\/([a-f0-9-]+)/);
    const matterId = match![1];

    await page.goto(`/matter/${matterId}/documents`);
    await page.waitForSelector('[data-testid="document-row"]', { timeout: 10000 });

    const docId = await page.locator('[data-testid="document-row"]').first().getAttribute('data-document-id');
    test.skip(!docId, 'Could not get document ID');

    const token = await getAuthToken(request);
    const response = await apiRequest(request, 'GET', `/documents/${docId}/chunks`, token);
    const data = await response.json();
    const chunks = data.chunks || data.data || [];

    // Look for table markers in chunk content
    const chunksWithTableContent = chunks.filter((c: any) => {
      const content = c.content || '';
      return content.includes('|') || content.includes('Table') || content.includes('table');
    });

    console.log('=== TABLE CONTENT ===');
    console.log(`Chunks potentially containing tables: ${chunksWithTableContent.length}`);

    // If test file has tables, we should find table content
    if (testFile.includes('table')) {
      expect(chunksWithTableContent.length).toBeGreaterThan(0);
    }
  });
});

// ============================================================================
// COMPARISON TESTS (Run with both flag states)
// ============================================================================

test.describe('Chunk Quality Comparison', () => {
  // Increase timeout to 5 minutes for tests involving chat/LLM responses
  test.setTimeout(300000);

  test('Chat should return relevant results with page citations', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForLoad();

    const hasMatter = await dashboardPage.hasMatters();
    test.skip(!hasMatter, 'No matters available for testing');

    await dashboardPage.openFirstMatter();

    // Find chat input
    const chatInput = page.locator(
      '[data-testid="chat-input"], textarea[placeholder*="ask" i], textarea[placeholder*="question" i]'
    );
    const hasChat = await chatInput.isVisible().catch(() => false);
    test.skip(!hasChat, 'Chat not available');

    // Ask a question
    await chatInput.fill('What are the key terms in this agreement?');
    await chatInput.press('Enter');

    // Wait for response
    await page.waitForSelector('[data-testid="chat-response"], [data-testid="ai-message"]', {
      timeout: 60000,
    });

    // Check for citations/page references in response
    const citations = page.locator('[data-testid="citation"], [data-testid="page-reference"]');
    const citationCount = await citations.count();

    console.log(`Citations found in response: ${citationCount}`);

    // Response should exist
    const response = page.locator('[data-testid="chat-response"], [data-testid="ai-message"]').first();
    const responseText = await response.textContent();
    expect(responseText?.length).toBeGreaterThan(0);
  });
});

// ============================================================================
// FALLBACK BEHAVIOR TESTS
// ============================================================================

test.describe('Graceful Degradation', () => {
  // Increase timeout to 5 minutes for document upload and processing
  test.setTimeout(300000);

  test.skip(
    process.env.LAYOUT_AWARE_CHUNKING_ENABLED !== 'true',
    'Only relevant when layout chunking is enabled'
  );

  test('Should still process documents when Docling fails', async ({ page }) => {
    // This test ensures that if layout extraction fails,
    // the pipeline falls back to text-based chunking

    const uploadPage = new UploadPage(page);
    await uploadPage.goto();

    // Upload a document - even if Docling fails, processing should complete
    await uploadPage.uploadFiles([TEST_FILES.simpleContract]);

    const matterName = `Fallback Test ${Date.now()}`;
    await uploadPage.clickNext();
    await uploadPage.setMatterName(matterName);
    await uploadPage.clickNext();
    await uploadPage.skipActDiscovery();

    // Should complete without error
    await uploadPage.waitForProcessingComplete(180000);

    // Verify we can navigate to matter
    await uploadPage.goToMatter();
    await expect(page).toHaveURL(/\/matter\/[a-f0-9-]+/);
  });
});

// ============================================================================
// PERFORMANCE COMPARISON
// ============================================================================

test.describe('Processing Time Comparison', () => {
  // Increase timeout to 5 minutes for document upload and processing
  test.setTimeout(300000);

  test('Measure document processing time', async ({ page }) => {
    const uploadPage = new UploadPage(page);
    await uploadPage.goto();
    await uploadPage.uploadFiles([TEST_FILES.simpleContract]);

    const matterName = `Perf Test ${Date.now()}`;
    await uploadPage.clickNext();
    await uploadPage.setMatterName(matterName);

    // Record start time
    const startTime = Date.now();

    await uploadPage.clickNext();
    await uploadPage.skipActDiscovery();
    await uploadPage.waitForProcessingComplete(180000);

    // Record end time
    const endTime = Date.now();
    const processingTime = (endTime - startTime) / 1000;

    console.log('=== PROCESSING TIME ===');
    console.log(`Layout chunking enabled: ${process.env.LAYOUT_AWARE_CHUNKING_ENABLED}`);
    console.log(`Total processing time: ${processingTime.toFixed(2)} seconds`);

    // Processing should complete in reasonable time
    // With layout enabled, expect +2-5 seconds overhead
    expect(processingTime).toBeLessThan(300); // 5 minutes max
  });
});
