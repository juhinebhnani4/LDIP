import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  showNotificationFallback,
  isBrowserNotificationSupported,
  getNotificationPermission,
  requestNotificationPermission,
  showProcessingCompleteNotification,
  NOTIFICATION_TITLE,
} from './browser-notifications';

/**
 * Browser Notifications Tests
 *
 * Note: Full Notification API testing is limited in Node/jsdom environment.
 * We mock the Notification API to test the utility functions.
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

  describe('isBrowserNotificationSupported', () => {
    it('returns false when Notification is not available', () => {
      // In jsdom, Notification is not available by default
      const originalNotification = (global as Record<string, unknown>).Notification;
      delete (global as Record<string, unknown>).Notification;

      expect(isBrowserNotificationSupported()).toBe(false);

      // Restore
      if (originalNotification) {
        (global as Record<string, unknown>).Notification = originalNotification;
      }
    });

    it('returns true when Notification is available', () => {
      // Mock Notification API
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'default',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotification);

      expect(isBrowserNotificationSupported()).toBe(true);

      vi.unstubAllGlobals();
    });
  });

  describe('getNotificationPermission', () => {
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('returns unsupported when Notification API is not available', () => {
      // Ensure Notification is not defined
      const originalNotification = (global as Record<string, unknown>).Notification;
      delete (global as Record<string, unknown>).Notification;

      expect(getNotificationPermission()).toBe('unsupported');

      if (originalNotification) {
        (global as Record<string, unknown>).Notification = originalNotification;
      }
    });

    it('returns granted when permission is granted', () => {
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'granted',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotification);

      expect(getNotificationPermission()).toBe('granted');
    });

    it('returns denied when permission is denied', () => {
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'denied',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotification);

      expect(getNotificationPermission()).toBe('denied');
    });

    it('returns default when permission is default', () => {
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'default',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotification);

      expect(getNotificationPermission()).toBe('default');
    });
  });

  describe('requestNotificationPermission', () => {
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('returns false when Notification API is not supported', async () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const originalNotification = (global as Record<string, unknown>).Notification;
      delete (global as Record<string, unknown>).Notification;

      const result = await requestNotificationPermission();

      expect(result).toBe(false);
      expect(consoleSpy).toHaveBeenCalledWith('Browser does not support notifications');

      consoleSpy.mockRestore();
      if (originalNotification) {
        (global as Record<string, unknown>).Notification = originalNotification;
      }
    });

    it('returns true when permission is already granted', async () => {
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'granted',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotification);

      const result = await requestNotificationPermission();

      expect(result).toBe(true);
    });

    it('returns false when permission is denied', async () => {
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'denied',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotification);

      const result = await requestNotificationPermission();

      expect(result).toBe(false);
    });

    it('requests permission when status is default', async () => {
      const mockRequestPermission = vi.fn().mockResolvedValue('granted');
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'default',
        writable: true,
      });
      mockNotification.requestPermission = mockRequestPermission;
      vi.stubGlobal('Notification', mockNotification);

      const result = await requestNotificationPermission();

      expect(mockRequestPermission).toHaveBeenCalled();
      expect(result).toBe(true);
    });

    it('returns false when permission request is denied', async () => {
      const mockRequestPermission = vi.fn().mockResolvedValue('denied');
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'default',
        writable: true,
      });
      mockNotification.requestPermission = mockRequestPermission;
      vi.stubGlobal('Notification', mockNotification);

      const result = await requestNotificationPermission();

      expect(result).toBe(false);
    });

    it('handles permission request errors', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const mockRequestPermission = vi.fn().mockRejectedValue(new Error('User cancelled'));
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'default',
        writable: true,
      });
      mockNotification.requestPermission = mockRequestPermission;
      vi.stubGlobal('Notification', mockNotification);

      const result = await requestNotificationPermission();

      expect(result).toBe(false);
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('showProcessingCompleteNotification', () => {
    let mockNotificationInstance: { onclick: (() => void) | null; close: ReturnType<typeof vi.fn> };

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('logs warning when Notification API is not supported', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const originalNotification = (global as Record<string, unknown>).Notification;
      delete (global as Record<string, unknown>).Notification;

      showProcessingCompleteNotification('Test Matter', 'matter-123');

      expect(consoleSpy).toHaveBeenCalledWith('Browser does not support notifications');
      consoleSpy.mockRestore();
      if (originalNotification) {
        (global as Record<string, unknown>).Notification = originalNotification;
      }
    });

    it('logs warning when permission is not granted', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const mockNotification = vi.fn();
      Object.defineProperty(mockNotification, 'permission', {
        value: 'denied',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotification);

      showProcessingCompleteNotification('Test Matter', 'matter-123');

      expect(consoleSpy).toHaveBeenCalledWith('Notification permission not granted');
      consoleSpy.mockRestore();
    });

    it('creates notification with correct title and body', () => {
      mockNotificationInstance = {
        onclick: null,
        close: vi.fn(),
      };
      const mockNotificationConstructor = vi.fn(() => mockNotificationInstance);
      Object.defineProperty(mockNotificationConstructor, 'permission', {
        value: 'granted',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotificationConstructor);

      showProcessingCompleteNotification('SEBI v. Parekh', 'matter-456');

      expect(mockNotificationConstructor).toHaveBeenCalledWith(
        'LDIP - Processing Complete',
        expect.objectContaining({
          body: 'Matter "SEBI v. Parekh" is ready for analysis',
          tag: 'matter-complete-matter-456',
          requireInteraction: false,
        })
      );
    });

    it('handles notification creation errors', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const mockNotificationConstructor = vi.fn(() => {
        throw new Error('Notification failed');
      });
      Object.defineProperty(mockNotificationConstructor, 'permission', {
        value: 'granted',
        writable: true,
      });
      vi.stubGlobal('Notification', mockNotificationConstructor);

      showProcessingCompleteNotification('Test Matter', 'matter-123');

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to show notification:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });
  });
});
