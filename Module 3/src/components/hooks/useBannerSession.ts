import { useCallback } from "react";

/**
 * Hook to manage PDP banner dismissal state in sessionStorage.
 *
 * A dismissed banner is suppressed for the lifetime of the browser tab.
 * On tab close or hard reload, sessionStorage is cleared and the banner
 * can appear again.
 *
 * Key format: `banner_dismissed:${customerId}:${productId}`
 * Value: ISO timestamp of dismissal
 */
export function useBannerSession() {
  const isDismissed = useCallback(
    (customerId: string, productId: string): boolean => {
      const key = `banner_dismissed:${customerId}:${productId}`;
      return sessionStorage.getItem(key) !== null;
    },
    [],
  );

  const dismiss = useCallback((customerId: string, productId: string): void => {
    const key = `banner_dismissed:${customerId}:${productId}`;
    sessionStorage.setItem(key, new Date().toISOString());
  }, []);

  return { isDismissed, dismiss };
}
