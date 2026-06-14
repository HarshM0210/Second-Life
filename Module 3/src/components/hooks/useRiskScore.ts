import { useState, useCallback } from "react";

/**
 * Response shape from POST /api/v1/risk-score.
 */
export interface RiskScoreResponse {
  risk_score: number;
  intervention_type: string | null;
  intervention_copy: string | null;
  taxonomy_miss: boolean;
}

/**
 * Payload accepted by fireRiskScore.
 */
export interface RiskScorePayload {
  customer_id: string;
  product_id: string;
  page_dwell_seconds: number;
  is_buy_now: boolean;
  seller_id?: string;
  product_price?: number;
  is_sale_active?: boolean;
}

/**
 * Hook that fires a risk-score request and manages async state.
 *
 * `fireRiskScore(payload)` POSTs to `/api/v1/risk-score`, sets `loading = true`,
 * and on response sets `data`. On any error (network failure, non-200 status,
 * or 3-second timeout via AbortController) sets `error = true` without
 * displaying any message to the user.
 *
 * The call is non-blocking — components should NOT await it.
 */
export function useRiskScore() {
  const [data, setData] = useState<RiskScoreResponse | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const fireRiskScore = useCallback((payload: RiskScorePayload): void => {
    setLoading(true);
    setError(false);
    setData(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    fetch("/api/v1/risk-score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json() as Promise<RiskScoreResponse>;
      })
      .then((json) => {
        setData(json);
      })
      .catch(() => {
        setError(true);
      })
      .finally(() => {
        clearTimeout(timeoutId);
        setLoading(false);
      });
  }, []);

  return { fireRiskScore, data, error, loading };
}
