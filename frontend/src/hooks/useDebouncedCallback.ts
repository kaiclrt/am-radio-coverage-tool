import { useEffect, useMemo, useRef } from 'react';

/**
 * Returns a debounced wrapper around `callback`. Used for the
 * "Estimate from Power" kW field, which calls `/api/estimate-rms` as the
 * user types - debounced so a burst of keystrokes is one request, not one
 * per character (the API caps that endpoint at 30/minute; see docs/api.md
 * and the "don't fire per keystroke" note in CLAUDE.md).
 */
export function useDebouncedCallback<TArgs extends unknown[]>(
  callback: (...args: TArgs) => void,
  delayMs: number,
): (...args: TArgs) => void {
  const callbackRef = useRef(callback);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return useMemo(
    () =>
      (...args: TArgs) => {
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => callbackRef.current(...args), delayMs);
      },
    [delayMs],
  );
}
