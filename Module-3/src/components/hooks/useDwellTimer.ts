import { useRef, useCallback } from "react";

/**
 * Measures elapsed time (in seconds) since the PDP component mounts.
 *
 * Call the returned getter at checkout-click time to capture
 * `page_dwell_seconds` for the risk-score request.
 *
 * @returns A stable getter function that returns elapsed seconds since mount.
 */
export function useDwellTimer(): () => number {
  const startRef = useRef(Date.now());

  const getDwellSeconds = useCallback(
    () => (Date.now() - startRef.current) / 1000,
    [],
  );

  return getDwellSeconds;
}
