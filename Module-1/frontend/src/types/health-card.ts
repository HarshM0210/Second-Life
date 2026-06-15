/**
 * Health Card JSON — the inter-module contract consumed by Modules 2–5.
 * Fields are never removed or renamed; new fields are additive and optional.
 */

export type Condition = "Excellent" | "Good" | "Fair" | "Poor";

export type Disposition =
  | "resell"
  | "refurbish"
  | "donate"
  | "recycle"
  | "return_to_seller"
  | "manual_review";

export type HealthCardSource = "standard_return" | "p2p_fraud_divert";

export interface FraudSignal {
  social_scan_performed: boolean;
  product_found_in_social: boolean;
  fraud_confidence: number; // 0.0–1.0
  p2p_offered: boolean;
  customer_chose_p2p: boolean;
}

export interface ScoreBreakdown {
  w1_anomaly_contribution: number;
  w2_defect_contribution: number;
  w3_reason_contribution: number;
  w4_wear_contribution: number;
}

export interface HealthCard {
  condition: Condition;
  health_score: number; // 0–100 integer
  confidence: number; // 0.0–1.0
  warranty_left_months: number;
  defects: string[];
  anomaly_heatmap_uri: string;
  justification: string;
  disposition: Disposition;
  source: HealthCardSource;
  fraud_signal: FraudSignal;
  score_breakdown?: ScoreBreakdown;
}
