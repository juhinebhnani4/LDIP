import { Page, Locator, expect } from '@playwright/test';
import { WorkspaceBasePage } from './base.page';

/**
 * Page Object Model for the Timeline tab
 */
export class TimelinePage extends WorkspaceBasePage {
  // Header controls
  readonly viewModeToggle: Locator;
  readonly horizontalViewButton: Locator;
  readonly multiTrackViewButton: Locator;
  readonly listViewButton: Locator;
  readonly filterButton: Locator;
  readonly addEventButton: Locator;
  readonly zoomSlider: Locator;

  // Timeline views
  readonly timelineHorizontal: Locator;
  readonly timelineMultiTrack: Locator;
  readonly timelineList: Locator;

  // Event elements
  readonly eventCards: Locator;
  readonly eventTracks: Locator;
  readonly eventConnectors: Locator;

  // Event detail panel
  readonly eventDetailPanel: Locator;
  readonly eventTitle: Locator;
  readonly eventDate: Locator;
  readonly eventDescription: Locator;
  readonly eventEntities: Locator;
  readonly editEventButton: Locator;
  readonly deleteEventButton: Locator;
  readonly verifyEventButton: Locator;

  // Dialogs
  readonly addEventDialog: Locator;
  readonly deleteConfirmDialog: Locator;

  // Empty state
  readonly emptyState: Locator;

  constructor(page: Page) {
    super(page);

    // Header controls
    this.viewModeToggle = page.locator('[data-testid="view-mode-toggle"]');
    this.horizontalViewButton = page.getByRole('button', { name: /horizontal/i });
    this.multiTrackViewButton = page.getByRole('button', { name: /multi-track|tracks/i });
    this.listViewButton = page.getByRole('button', { name: /list/i });
    this.filterButton = page.getByRole('button', { name: /filter/i });
    this.addEventButton = page.getByRole('button', { name: /add event/i });
    this.zoomSlider = page.locator('[data-testid="zoom-slider"]');

    // Views
    this.timelineHorizontal = page.locator('[data-testid="timeline-horizontal"]');
    this.timelineMultiTrack = page.locator('[data-testid="timeline-multitrack"]');
    this.timelineList = page.locator('[data-testid="timeline-list"]');

    // Events
    this.eventCards = page.locator('[data-testid="timeline-event-card"]');
    this.eventTracks = page.locator('[data-testid="entity-track"]');
    this.eventConnectors = page.locator('[data-testid="timeline-connector"]');

    // Detail panel
    this.eventDetailPanel = page.locator('[data-testid="event-detail-panel"]');
    this.eventTitle = page.locator('[data-testid="event-title"]');
    this.eventDate = page.locator('[data-testid="event-date"]');
    this.eventDescription = page.locator('[data-testid="event-description"]');
    this.eventEntities = page.locator('[data-testid="event-entities"]');
    this.editEventButton = page.getByRole('button', { name: /edit/i });
    this.deleteEventButton = page.getByRole('button', { name: /delete/i });
    this.verifyEventButton = page.getByRole('button', { name: /verify/i });

    // Dialogs
    this.addEventDialog = page.locator('[data-testid="add-event-dialog"]');
    this.deleteConfirmDialog = page.locator('[data-testid="delete-confirm-dialog"]');

    // Empty
    this.emptyState = page.locator('[data-testid="timeline-empty-state"]');
  }

  /**
   * Navigate to timeline tab for a matter
   */
  async gotoTimeline(matterId: string) {
    await this.page.goto(`/matter/${matterId}/timeline`);
    await this.waitForTimelineLoad();
  }

  /**
   * Wait for timeline content to load
   */
  async waitForTimelineLoad() {
    await this.page.waitForSelector('[data-testid="timeline-content"]');
  }

  /**
   * Get count of events
   */
  async getEventCount(): Promise<number> {
    return await this.eventCards.count();
  }

  /**
   * Switch to horizontal view
   */
  async switchToHorizontalView() {
    await this.horizontalViewButton.click();
    await expect(this.timelineHorizontal).toBeVisible();
  }

  /**
   * Switch to multi-track view
   */
  async switchToMultiTrackView() {
    await this.multiTrackViewButton.click();
    await expect(this.timelineMultiTrack).toBeVisible();
  }

  /**
   * Switch to list view
   */
  async switchToListView() {
    await this.listViewButton.click();
    await expect(this.timelineList).toBeVisible();
  }

  /**
   * Click on an event card
   */
  async clickEvent(index: number = 0) {
    await this.eventCards.nth(index).click();
    await expect(this.eventDetailPanel).toBeVisible();
  }

  /**
   * Click on event by text content
   */
  async clickEventByText(text: string) {
    await this.eventCards.filter({ hasText: text }).first().click();
    await expect(this.eventDetailPanel).toBeVisible();
  }

  /**
   * Open add event dialog
   */
  async openAddEventDialog() {
    await this.addEventButton.click();
    await expect(this.addEventDialog).toBeVisible();
  }

  /**
   * Add a manual event
   */
  async addEvent(title: string, date: string, description?: string) {
    await this.openAddEventDialog();

    await this.page.getByLabel(/title|event name/i).fill(title);
    await this.page.getByLabel(/date/i).fill(date);

    if (description) {
      await this.page.getByLabel(/description/i).fill(description);
    }

    await this.page.getByRole('button', { name: /add|create|save/i }).click();
  }

  /**
   * Delete the currently selected event
   */
  async deleteSelectedEvent() {
    await this.deleteEventButton.click();
    await expect(this.deleteConfirmDialog).toBeVisible();
    await this.page.getByRole('button', { name: /confirm|delete/i }).click();
  }

  /**
   * Verify the currently selected event
   */
  async verifySelectedEvent() {
    await this.verifyEventButton.click();
  }

  /**
   * Zoom timeline
   */
  async setZoom(level: number) {
    await this.zoomSlider.fill(level.toString());
  }

  /**
   * Get number of entity tracks (in multi-track view)
   */
  async getTrackCount(): Promise<number> {
    return await this.eventTracks.count();
  }

  /**
   * Open filters
   */
  async openFilters() {
    await this.filterButton.click();
  }

  /**
   * Filter by entity type
   */
  async filterByEntityType(type: string) {
    await this.openFilters();
    await this.page.getByLabel(new RegExp(type, 'i')).check();
    await this.page.getByRole('button', { name: /apply/i }).click();
  }

  /**
   * Check if timeline has events
   */
  async hasEvents(): Promise<boolean> {
    const count = await this.getEventCount();
    return count > 0;
  }
}
