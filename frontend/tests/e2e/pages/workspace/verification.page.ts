import { Page, Locator, expect } from '@playwright/test';
import { WorkspaceBasePage } from './base.page';

/**
 * Page Object Model for the Verification tab
 */
export class VerificationPage extends WorkspaceBasePage {
  // Statistics
  readonly stats: Locator;
  readonly totalCount: Locator;
  readonly verifiedCount: Locator;
  readonly pendingCount: Locator;
  readonly rejectedCount: Locator;
  readonly progressBar: Locator;

  // Filters
  readonly statusFilter: Locator;
  readonly typeFilter: Locator;
  readonly sortSelect: Locator;

  // View controls
  readonly queueView: Locator;
  readonly groupedView: Locator;
  readonly viewToggle: Locator;

  // Verification items
  readonly verificationItems: Locator;
  readonly itemPreview: Locator;
  readonly itemStatus: Locator;

  // Action buttons
  readonly approveButton: Locator;
  readonly rejectButton: Locator;
  readonly skipButton: Locator;
  readonly notesButton: Locator;

  // Notes dialog
  readonly notesDialog: Locator;
  readonly notesTextarea: Locator;

  // Bulk actions
  readonly selectAllCheckbox: Locator;
  readonly bulkApproveButton: Locator;
  readonly bulkRejectButton: Locator;

  // Empty state
  readonly emptyState: Locator;
  readonly allVerifiedState: Locator;

  constructor(page: Page) {
    super(page);

    // Stats
    this.stats = page.locator('[data-testid="verification-stats"]');
    this.totalCount = page.locator('[data-testid="total-count"]');
    this.verifiedCount = page.locator('[data-testid="verified-count"]');
    this.pendingCount = page.locator('[data-testid="pending-count"]');
    this.rejectedCount = page.locator('[data-testid="rejected-count"]');
    this.progressBar = page.locator('[data-testid="verification-progress"]');

    // Filters
    this.statusFilter = page.getByRole('combobox', { name: /status/i });
    this.typeFilter = page.getByRole('combobox', { name: /type/i });
    this.sortSelect = page.getByRole('combobox', { name: /sort/i });

    // Views
    this.queueView = page.locator('[data-testid="verification-queue"]');
    this.groupedView = page.locator('[data-testid="verification-grouped-view"]');
    this.viewToggle = page.locator('[data-testid="view-toggle"]');

    // Items
    this.verificationItems = page.locator('[data-testid="verification-item"]');
    this.itemPreview = page.locator('[data-testid="item-preview"]');
    this.itemStatus = page.locator('[data-testid="item-status"]');

    // Actions
    this.approveButton = page.getByRole('button', { name: /approve/i });
    this.rejectButton = page.getByRole('button', { name: /reject/i });
    this.skipButton = page.getByRole('button', { name: /skip/i });
    this.notesButton = page.getByRole('button', { name: /notes|add note/i });

    // Notes
    this.notesDialog = page.locator('[data-testid="verification-notes-dialog"]');
    this.notesTextarea = page.locator('[data-testid="notes-textarea"]');

    // Bulk
    this.selectAllCheckbox = page.getByRole('checkbox', { name: /select all/i });
    this.bulkApproveButton = page.getByRole('button', { name: /approve selected/i });
    this.bulkRejectButton = page.getByRole('button', { name: /reject selected/i });

    // Empty/Complete states
    this.emptyState = page.locator('[data-testid="verification-empty-state"]');
    this.allVerifiedState = page.locator('[data-testid="all-verified-state"]');
  }

  /**
   * Navigate to verification tab for a matter
   */
  async gotoVerification(matterId: string) {
    await this.page.goto(`/matter/${matterId}/verification`);
    await this.waitForVerificationLoad();
  }

  /**
   * Wait for verification content to load
   */
  async waitForVerificationLoad() {
    await this.page.waitForSelector('[data-testid="verification-content"]');
  }

  /**
   * Get total item count
   */
  async getTotalCount(): Promise<number> {
    const text = await this.totalCount.textContent();
    return parseInt(text || '0', 10);
  }

  /**
   * Get verified count
   */
  async getVerifiedCount(): Promise<number> {
    const text = await this.verifiedCount.textContent();
    return parseInt(text || '0', 10);
  }

  /**
   * Get pending count
   */
  async getPendingCount(): Promise<number> {
    const text = await this.pendingCount.textContent();
    return parseInt(text || '0', 10);
  }

  /**
   * Get rejected count
   */
  async getRejectedCount(): Promise<number> {
    const text = await this.rejectedCount.textContent();
    return parseInt(text || '0', 10);
  }

  /**
   * Get verification progress percentage
   */
  async getProgressPercentage(): Promise<number> {
    const value = await this.progressBar.getAttribute('aria-valuenow');
    return value ? parseInt(value, 10) : 0;
  }

  /**
   * Get count of visible verification items
   */
  async getItemCount(): Promise<number> {
    return await this.verificationItems.count();
  }

  /**
   * Click on a verification item
   */
  async clickItem(index: number = 0) {
    await this.verificationItems.nth(index).click();
  }

  /**
   * Approve current/selected item
   */
  async approveItem() {
    await this.approveButton.click();
  }

  /**
   * Reject current/selected item
   */
  async rejectItem() {
    await this.rejectButton.click();
  }

  /**
   * Skip current item
   */
  async skipItem() {
    await this.skipButton.click();
  }

  /**
   * Add notes to current item
   */
  async addNotes(notes: string) {
    await this.notesButton.click();
    await expect(this.notesDialog).toBeVisible();
    await this.notesTextarea.fill(notes);
    await this.page.getByRole('button', { name: /save|add/i }).click();
  }

  /**
   * Filter by status
   */
  async filterByStatus(status: 'all' | 'pending' | 'verified' | 'rejected') {
    await this.statusFilter.click();
    await this.page.getByRole('option', { name: new RegExp(status, 'i') }).click();
  }

  /**
   * Filter by type
   */
  async filterByType(type: string) {
    await this.typeFilter.click();
    await this.page.getByRole('option', { name: new RegExp(type, 'i') }).click();
  }

  /**
   * Select all items
   */
  async selectAll() {
    await this.selectAllCheckbox.check();
  }

  /**
   * Bulk approve selected items
   */
  async bulkApprove() {
    await this.bulkApproveButton.click();
  }

  /**
   * Bulk reject selected items
   */
  async bulkReject() {
    await this.bulkRejectButton.click();
  }

  /**
   * Process verification queue (approve all pending)
   */
  async processQueue() {
    let pendingCount = await this.getPendingCount();

    while (pendingCount > 0) {
      await this.clickItem(0);
      await this.approveItem();
      pendingCount = await this.getPendingCount();
    }
  }

  /**
   * Check if all items are verified
   */
  async isAllVerified(): Promise<boolean> {
    return await this.allVerifiedState.isVisible();
  }

  /**
   * Check if verification queue is empty
   */
  async isEmpty(): Promise<boolean> {
    return await this.emptyState.isVisible();
  }

  /**
   * Check if there are pending items
   */
  async hasPendingItems(): Promise<boolean> {
    const pending = await this.getPendingCount();
    return pending > 0;
  }
}
