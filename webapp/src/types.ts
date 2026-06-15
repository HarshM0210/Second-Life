// Shared types mirroring the backend contracts (Health Card, feed, wallet, etc.)

export type Disposition =
  | "resell" | "refurbish" | "donate" | "recycle"
  | "return_to_seller" | "manual_review";

export interface FraudSignal {
  social_scan_performed: boolean;
  product_found_in_social: boolean;
  fraud_confidence: number;
  p2p_offered: boolean;
  customer_chose_p2p: boolean;
}

export interface HealthCard {
  condition: "Excellent" | "Good" | "Fair" | "Poor";
  health_score: number;
  confidence: number;
  warranty_left_months: number;
  defects: string[];
  anomaly_heatmap_uri: string;
  justification: string;
  disposition: Disposition;
  source: "standard_return" | "p2p_fraud_divert";
  fraud_signal: FraudSignal;
  flags?: string[];
}

export interface Question {
  id: string;
  text: string;
  options: string[];
  supplementary_input: unknown | null;
  conditional_display: string | null;
}

export interface InitiateResponse {
  return_id: string;
  eligible: boolean;
  window_days: number;
  days_elapsed: number;
  category: string;
  questions: Question[];
}

export interface SubmitResponse {
  health_card: HealthCard;
  p2p_divert_offered: boolean;
}

export interface RiskResponse {
  risk_score: number;
  intervention_type: string | null;
  intervention_copy: string | null;
  taxonomy_miss: boolean;
}

export interface FeedItem {
  sku_id: string;
  rank: number;
  score: number;
  badge: "New" | "Renewed";
  health_score: number;
  reasons: string[];
}

export interface Feed {
  user_id: string;
  items: FeedItem[];
}

export interface Badge {
  slug: string;
  name: string;
  icon: string;
  threshold_kg: number;
  equivalent: string;
  unlocked: boolean;
}

export interface CoinEvent {
  id: string;
  event_type: "earned" | "redeemed" | "expired" | "badge_earned";
  amount: number;
  source: string;
  co2e_kg: number;
  streak_day: number;
  badge: string | null;
  item_id: string | null;
  created_at: string;
}

export interface Wallet {
  user_id: string;
  balance: number;
  co2e_total_kg: number;
  equivalents: Record<string, number>;
  badges: Badge[];
  history: CoinEvent[];
}

export interface Reward {
  reward_id: string;
  name: string;
  cost: number;
  description: string;
  category: string;
}

export interface ImpactSummary {
  co2e_avoided_kg: number;
  items_given_second_life: number;
  trees_equivalent: number;
}

export interface PriceQuote {
  sku_id?: string;
  gross_price: number;
  low: number;
  high: number;
  confidence: number;
  fee: number;
  net_payout: number;
  currency: string;
  feature_source: string;
  reasons: string[];
  model: string;
}

export interface PickupJob {
  job_id: string;
  status: string;
  [k: string]: unknown;
}

// Pipeline trace (gateway /pipeline/return)
export interface PipelineStep {
  step: string;
  ok?: boolean;
  [k: string]: unknown;
}

export interface PipelineResult {
  persona: string;
  disposition: Disposition | null;
  green_coin_disposition: string | null;
  coins_earned: number | null;
  co2e_kg: number | null;
  chose_p2p: boolean;
  health_card: HealthCard | null;
  p2p_quote: PriceQuote | null;
  steps: PipelineStep[];
}
