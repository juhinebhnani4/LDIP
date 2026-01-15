import { describe, it, expect, vi } from 'vitest';
import {
  showNotificationFallback,
  NOTIFICATION_TITLE,
} from './browser-notifications';

/**
 * Browser Notifications Tests
 *
 * Note: Full Notification API testing is limited in Node/jsdom environment.
 * These tests cover the utility functions that don't require browser APIs.
 * Manual testing in browser is recommended for full coverage.
 */
describe('browser-notifications', () => {
  describe('NOTIFICATION_TITLE', () => {
    it('has correct value', () => {
      expect(NOTIFICATION_TITLE).toBe('LDIP - Processing Complete');
    });
  });

  describe('showNotificationFallback', () => {
    it('logs to console with matter name', () => {
      const consoleSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

      showNotificationFallback('Test Matter');

      expect(consoleSpy).toHaveBeenCalledWith(
        'Processing complete: Matter "Test Matter" is ready for analysis'
      );
      consoleSpy.mockRestore();
    });

    it('handles special characters in matter name', () => {
      const consoleSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

      showNotificationFallback('Matter "ABC" & Co.');

      expect(consoleSpy).toHaveBeenCalledWith(
        'Processing complete: Matter "Matter "ABC" & Co." is ready for analysis'
      );
      consoleSpy.mockRestore();
    });
  });
});
