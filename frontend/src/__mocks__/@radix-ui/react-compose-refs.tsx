/**
 * Mock for @radix-ui/react-compose-refs
 *
 * This mock prevents an infinite loop that occurs in jsdom when
 * setRef is called in a way that triggers re-renders.
 */
import * as React from 'react';

type PossibleRef<T> = React.Ref<T> | undefined;

/**
 * A safe version of setRef that doesn't trigger state updates
 */
function setRef<T>(ref: PossibleRef<T>, value: T) {
  if (typeof ref === 'function') {
    ref(value);
  } else if (ref !== null && ref !== undefined) {
    (ref as React.MutableRefObject<T>).current = value;
  }
}

/**
 * Compose multiple refs into a single ref callback
 */
function composeRefs<T>(...refs: PossibleRef<T>[]): React.RefCallback<T> {
  return (node: T) => refs.forEach((ref) => setRef(ref, node));
}

/**
 * Hook to compose refs
 */
function useComposedRefs<T>(...refs: PossibleRef<T>[]): React.RefCallback<T> {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return React.useCallback(composeRefs(...refs), refs);
}

export { composeRefs, useComposedRefs };
