import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useIsBelowBreakpoint, useMediaQuery, BREAKPOINTS } from './useBreakpoint';

/** jsdom has no matchMedia; stub one that reports a fixed `matches`. */
function stubMatchMedia(matches: boolean) {
  const mql = {
    matches,
    media: '',
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  };
  window.matchMedia = vi.fn().mockReturnValue(mql) as unknown as typeof window.matchMedia;
  return mql;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useMediaQuery', () => {
  it('returns true when the query matches', () => {
    stubMatchMedia(true);
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'));
    expect(result.current).toBe(true);
  });

  it('returns false when the query does not match', () => {
    stubMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'));
    expect(result.current).toBe(false);
  });

  it('subscribes and unsubscribes to the media query list', () => {
    const mql = stubMatchMedia(false);
    const { unmount } = renderHook(() => useMediaQuery('(max-width: 767px)'));
    expect(mql.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));
    unmount();
    expect(mql.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });
});

describe('useIsBelowBreakpoint', () => {
  it('queries max-width just below the breakpoint pixel (Tailwind min-width semantics)', () => {
    stubMatchMedia(false);
    renderHook(() => useIsBelowBreakpoint('md'));
    expect(window.matchMedia).toHaveBeenCalledWith(`(max-width: ${BREAKPOINTS.md - 0.02}px)`);
  });

  it('is true below the tablet breakpoint when the viewport matches', () => {
    stubMatchMedia(true);
    const { result } = renderHook(() => useIsBelowBreakpoint('md'));
    expect(result.current).toBe(true);
  });
});
