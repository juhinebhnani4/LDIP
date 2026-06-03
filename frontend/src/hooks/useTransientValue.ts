/**
 * useTransientValue
 *
 * A value that you set, and which automatically resets to `resetValue` after
 * `durationMs`. Replaces the repeated `setX(true); setTimeout(() => setX(false), N)`
 * pattern (the "transient flag" shape — see FE-024 in BUGS.md), giving one place
 * that owns timer cleanup so individual call sites can't leak timers.
 *
 * The timer is cancelled on unmount and re-armed on each call, so rapid repeats
 * don't stack timers or reset early.
 *
 * Boolean flag (e.g. a "Copied!" / "Saved!" confirmation):
 *   const [copied, flashCopied] = useTransientValue(false, 2000);
 *   // in a handler: flashCopied(true);
 *
 * Transient value (e.g. a graph focus pulse that should clear after the animation),
 * with an optional persistent initial value (e.g. a deep-linked id from the URL):
 *   const [focusNodeId, pulseFocus] = useTransientValue<string | null>(null, 600, initialId);
 *   // in a handler/effect: pulseFocus(nodeId);
 *
 * `initialValue` (defaults to `resetValue`) seeds the first render WITHOUT arming
 * a timer — so an initial value persists until the first explicit set, while every
 * value passed to the setter auto-resets.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export function useTransientValue<T>(
  resetValue: T,
  durationMs: number,
  initialValue?: T,
): [T, (next: T) => void] {
  const [value, setValue] = useState<T>(
    initialValue === undefined ? resetValue : initialValue,
  );
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const setTemporarily = useCallback(
    (next: T) => {
      clearTimer();
      setValue(next);
      timerRef.current = setTimeout(() => {
        setValue(resetValue);
        timerRef.current = null;
      }, durationMs);
    },
    [clearTimer, durationMs, resetValue],
  );

  // Cancel any pending timer on unmount.
  useEffect(() => clearTimer, [clearTimer]);

  return [value, setTemporarily];
}
