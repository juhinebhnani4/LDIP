/**
 * Browser Notifications Utility
 *
 * Handles browser notification permission and display for processing completion.
 *
 * Story 9-6: Implement Upload Flow Stage 5 and Notifications
 */

/** Notification title constant */
export const NOTIFICATION_TITLE = 'LDIP - Processing Complete';

/**
 * Check if the browser supports the Notification API
 */
export function isBrowserNotificationSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

/**
 * Get current notification permission status
 * @returns 'granted', 'denied', 'default', or 'unsupported'
 */
export function getNotificationPermission(): NotificationPermission | 'unsupported' {
  if (!isBrowserNotificationSupported()) {
    return 'unsupported';
  }
  return Notification.permission;
}

/**
 * Request notification permission from the user
 * @returns Promise that resolves to true if permission granted, false otherwise
 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!isBrowserNotificationSupported()) {
    console.warn('Browser does not support notifications');
    return false;
  }

  // Already granted
  if (Notification.permission === 'granted') {
    return true;
  }

  // Already denied - can't ask again
  if (Notification.permission === 'denied') {
    return false;
  }

  // Ask for permission
  try {
    const permission = await Notification.requestPermission();
    return permission === 'granted';
  } catch (error) {
    console.error('Failed to request notification permission:', error);
    return false;
  }
}

/**
 * Show a processing complete notification
 *
 * @param matterName - The name of the matter that completed processing
 * @param matterId - The ID of the completed matter (for navigation)
 */
export function showProcessingCompleteNotification(
  matterName: string,
  matterId: string
): void {
  // Check permission first
  if (!isBrowserNotificationSupported()) {
    console.warn('Browser does not support notifications');
    return;
  }

  if (Notification.permission !== 'granted') {
    console.warn('Notification permission not granted');
    return;
  }

  try {
    const notification = new Notification(NOTIFICATION_TITLE, {
      body: `Matter "${matterName}" is ready for analysis`,
      // Use favicon as fallback icon - always available in Next.js apps
      icon: '/favicon.ico',
      tag: `matter-complete-${matterId}`, // Prevents duplicate notifications
      requireInteraction: false,
    });

    notification.onclick = () => {
      // Focus the window
      window.focus();

      // Navigate to matter workspace
      window.location.href = `/matters/${matterId}`;

      // Close the notification
      notification.close();
    };
  } catch (error) {
    console.error('Failed to show notification:', error);
  }
}

/**
 * Show a toast notification fallback when browser notifications are not available
 * This is a placeholder - actual implementation would use a toast library
 *
 * @param matterName - The name of the matter that completed processing
 */
export function showNotificationFallback(matterName: string): void {
  // This would typically integrate with a toast notification system
  // For now, just log to console
  console.info(`Processing complete: Matter "${matterName}" is ready for analysis`);
}
