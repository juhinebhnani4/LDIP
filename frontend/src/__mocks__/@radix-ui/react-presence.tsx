/**
 * Mock for @radix-ui/react-presence
 *
 * This mock prevents an infinite loop that occurs in jsdom when Radix's
 * Presence component's setRef triggers setState in a loop.
 */
import * as React from 'react';

interface PresenceProps {
  children: React.ReactNode;
  present: boolean;
}

export function Presence({ children, present }: PresenceProps) {
  return present ? <>{children}</> : null;
}
