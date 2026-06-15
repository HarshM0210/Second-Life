// Lightweight onboarding/session flags persisted for the tab. There is no auth
// backend in this prototype — completing sign-up or sign-in sets the gate so the
// storefront becomes reachable.
const ONBOARDED_KEY = "sl_onboarded";
const SOCIAL_TRACKING_KEY = "sl_social_tracking";

export function hasOnboarded(): boolean {
  try {
    return sessionStorage.getItem(ONBOARDED_KEY) === "1";
  } catch {
    return false;
  }
}

export function completeOnboarding(): void {
  try {
    sessionStorage.setItem(ONBOARDED_KEY, "1");
  } catch {
    /* storage unavailable — ignore */
  }
}

export function setSocialTracking(enabled: boolean): void {
  try {
    sessionStorage.setItem(SOCIAL_TRACKING_KEY, enabled ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function isSocialTrackingEnabled(): boolean {
  try {
    return sessionStorage.getItem(SOCIAL_TRACKING_KEY) !== "0";
  } catch {
    return true;
  }
}
