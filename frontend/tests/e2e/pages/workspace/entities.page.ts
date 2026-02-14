import { Page, Locator, expect } from '@playwright/test';
import { WorkspaceBasePage } from './base.page';

/**
 * Page Object Model for the Entities tab
 */
export class EntitiesPage extends WorkspaceBasePage {
  // Header controls
  readonly searchInput: Locator;
  readonly viewModeToggle: Locator;
  readonly gridViewButton: Locator;
  readonly listViewButton: Locator;
  readonly graphViewButton: Locator;
  readonly sortSelect: Locator;
  readonly filterButton: Locator;

  // Views
  readonly gridView: Locator;
  readonly listView: Locator;
  readonly graphView: Locator;

  // Entity elements
  readonly entityCards: Locator;
  readonly entityRows: Locator;
  readonly entityNodes: Locator;

  // Detail panel
  readonly detailPanel: Locator;
  readonly entityName: Locator;
  readonly entityType: Locator;
  readonly aliasesList: Locator;
  readonly mentionsList: Locator;
  readonly relationshipsList: Locator;

  // Alias management
  readonly addAliasButton: Locator;
  readonly aliasInput: Locator;
  readonly removeAliasButton: Locator;

  // Merge functionality
  readonly mergeButton: Locator;
  readonly mergeDialog: Locator;
  readonly mergeSuggestions: Locator;

  // Empty state
  readonly emptyState: Locator;

  constructor(page: Page) {
    super(page);

    // Header
    this.searchInput = page.getByPlaceholder(/search entities/i);
    this.viewModeToggle = page.locator('[data-testid="view-mode-toggle"]');
    this.gridViewButton = page.getByRole('button', { name: /grid/i });
    this.listViewButton = page.getByRole('button', { name: /list/i });
    this.graphViewButton = page.getByRole('button', { name: /graph|network/i });
    this.sortSelect = page.getByRole('combobox', { name: /sort/i });
    this.filterButton = page.getByRole('button', { name: /filter/i });

    // Views
    this.gridView = page.locator('[data-testid="entities-grid-view"]');
    this.listView = page.locator('[data-testid="entities-list-view"]');
    this.graphView = page.locator('[data-testid="entities-graph"]');

    // Entities
    this.entityCards = page.locator('[data-testid="entity-card"]');
    this.entityRows = page.locator('[data-testid="entity-row"]');
    this.entityNodes = page.locator('[data-testid="entity-node"]');

    // Detail panel
    this.detailPanel = page.locator('[data-testid="entity-detail-panel"]');
    this.entityName = page.locator('[data-testid="entity-name"]');
    this.entityType = page.locator('[data-testid="entity-type"]');
    this.aliasesList = page.locator('[data-testid="aliases-list"]');
    this.mentionsList = page.locator('[data-testid="mentions-list"]');
    this.relationshipsList = page.locator('[data-testid="relationships-list"]');

    // Aliases
    this.addAliasButton = page.getByRole('button', { name: /add alias/i });
    this.aliasInput = page.getByPlaceholder(/alias/i);
    this.removeAliasButton = page.locator('[data-testid="remove-alias"]');

    // Merge
    this.mergeButton = page.getByRole('button', { name: /merge/i });
    this.mergeDialog = page.locator('[data-testid="entity-merge-dialog"]');
    this.mergeSuggestions = page.locator('[data-testid="merge-suggestion"]');

    // Empty
    this.emptyState = page.locator('[data-testid="entities-empty-state"]');
  }

  /**
   * Navigate to entities tab for a matter
   */
  async gotoEntities(matterId: string) {
    await this.page.goto(`/matter/${matterId}/entities`);
    await this.waitForEntitiesLoad();
  }

  /**
   * Wait for entities content to load
   */
  async waitForEntitiesLoad() {
    await this.page.waitForURL(/\/entities/, { timeout: 10000 });
    await this.page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
  }

  /**
   * Get count of entities
   */
  async getEntityCount(): Promise<number> {
    // Count based on current view
    const gridCount = await this.entityCards.count();
    const listCount = await this.entityRows.count();
    return Math.max(gridCount, listCount);
  }

  /**
   * Search for entities
   */
  async searchEntities(query: string) {
    await this.searchInput.fill(query);
    await this.page.keyboard.press('Enter');
  }

  /**
   * Clear search
   */
  async clearSearch() {
    await this.searchInput.clear();
  }

  /**
   * Switch to grid view
   */
  async switchToGridView() {
    await this.gridViewButton.click();
    await expect(this.gridView).toBeVisible();
  }

  /**
   * Switch to list view
   */
  async switchToListView() {
    await this.listViewButton.click();
    await expect(this.listView).toBeVisible();
  }

  /**
   * Switch to graph view
   */
  async switchToGraphView() {
    await this.graphViewButton.click();
    await expect(this.graphView).toBeVisible();
  }

  /**
   * Click on an entity card (grid view)
   */
  async clickEntityCard(index: number = 0) {
    await this.entityCards.nth(index).click();
    await expect(this.detailPanel).toBeVisible();
  }

  /**
   * Click on entity by name
   */
  async clickEntityByName(name: string) {
    const entity = this.entityCards.filter({ hasText: name }).or(
      this.entityRows.filter({ hasText: name })
    );
    await entity.first().click();
    await expect(this.detailPanel).toBeVisible();
  }

  /**
   * Click on entity node in graph
   */
  async clickEntityNode(index: number = 0) {
    await this.entityNodes.nth(index).click();
    await expect(this.detailPanel).toBeVisible();
  }

  /**
   * Get entity name from detail panel
   */
  async getSelectedEntityName(): Promise<string> {
    return await this.entityName.textContent() || '';
  }

  /**
   * Get entity type from detail panel
   */
  async getSelectedEntityType(): Promise<string> {
    return await this.entityType.textContent() || '';
  }

  /**
   * Add an alias to selected entity
   */
  async addAlias(alias: string) {
    await this.addAliasButton.click();
    await this.aliasInput.fill(alias);
    await this.page.keyboard.press('Enter');
  }

  /**
   * Remove an alias
   */
  async removeAlias(alias: string) {
    const aliasItem = this.aliasesList.locator(`text="${alias}"`);
    await aliasItem.locator('[data-testid="remove-alias"]').click();
  }

  /**
   * Get list of aliases
   */
  async getAliases(): Promise<string[]> {
    const aliases = await this.aliasesList.locator('[data-testid="alias-item"]').all();
    const aliasTexts: string[] = [];
    for (const alias of aliases) {
      const text = await alias.textContent();
      if (text) aliasTexts.push(text.trim());
    }
    return aliasTexts;
  }

  /**
   * Get mention count for selected entity
   */
  async getMentionCount(): Promise<number> {
    const mentions = await this.mentionsList.locator('[data-testid="mention-item"]').count();
    return mentions;
  }

  /**
   * Open merge dialog
   */
  async openMergeDialog() {
    await this.mergeButton.click();
    await expect(this.mergeDialog).toBeVisible();
  }

  /**
   * Merge with suggested entity
   */
  async mergeWithSuggestion(index: number = 0) {
    await this.openMergeDialog();
    await this.mergeSuggestions.nth(index).click();
    await this.page.getByRole('button', { name: /confirm|merge/i }).click();
  }

  /**
   * Filter by entity type
   */
  async filterByType(type: string) {
    await this.filterButton.click();
    await this.page.getByLabel(new RegExp(type, 'i')).check();
    await this.page.getByRole('button', { name: /apply/i }).click();
  }

  /**
   * Sort entities
   */
  async sortBy(option: 'name' | 'type' | 'mentions' | 'relationships') {
    await this.sortSelect.click();
    await this.page.getByRole('option', { name: new RegExp(option, 'i') }).click();
  }

  /**
   * Check if entities exist
   */
  async hasEntities(): Promise<boolean> {
    const count = await this.getEntityCount();
    return count > 0;
  }
}
