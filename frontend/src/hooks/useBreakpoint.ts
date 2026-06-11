'use client';

import { useCallback, useSyncExternalStore } from 'react';

/**
 * Tailwind's default breakpoints, in pixels. These are the `min-width` values at
 * which each named breakpoint's styles begin to apply (sm ≥ 640, md ≥ 768, …).
 * Keep in sync with tailwind.config — Tailwind v4 uses the defaults here.
 *
 * This module is the SINGLE structural primitive for "how wide is the screen
 * right now" that FE-ARCH-02 was missing. Components must read viewport-driven
 * layout decisions from here — NOT by hand-adding raw `sm:`/`md:` classes for
 * structural (multi-pane) layout, and NOT by reading window.innerWidth ad hoc.
 */
export const BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const;

export type Breakpoint = keyof typeof BREAKPOINTS;

const EMPTY_SUBSCRIBE = () => () => {};

/**
 * SSR-safe media-query hook. Returns whether `query` currently matches.
 *
 * Uses `useSyncExternalStore` so the server render and the first client render
 * agree on a deterministic value (the server snapshot), and React swaps to the
 * real value on mount WITHOUT a hydration-mismatch warning. The server snapshot
 * is `false` — i.e. we render the desktop layout on the server / before mount,
 * then correct to mobile on the client if the viewport is actually narrow.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (callback: () => void) => {
      if (typeof window === 'undefined' || !window.matchMedia) {
        return EMPTY_SUBSCRIBE();
      }
      const mql = window.matchMedia(query);
      mql.addEventListener('change', callback);
      return () => mql.removeEventListener('change', callback);
    },
    [query]
  );

  const getSnapshot = useCallback(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return false;
    }
    return window.matchMedia(query).matches;
  }, [query]);

  const getServerSnapshot = () => false;

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/**
 * Returns true when the viewport is NARROWER than the given Tailwind breakpoint
 * — e.g. `useIsBelowBreakpoint('md')` is true below 768px (phones / small
 * tablets), which is where the matter workspace must collapse its split layout.
 *
 * `max-width` is inclusive, so we subtract a hair: the breakpoint pixel itself
 * counts as "at/above" (matching Tailwind's min-width semantics for `md:`).
 */
export function useIsBelowBreakpoint(breakpoint: Breakpoint): boolean {
  return useMediaQuery(`(max-width: ${BREAKPOINTS[breakpoint] - 0.02}px)`);
}
