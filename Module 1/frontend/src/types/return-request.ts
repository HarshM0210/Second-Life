/**
 * Return request models for initiating and submitting returns.
 */

import type { HealthCard } from "./health-card";
import type { Question } from "./question";

export type ProductCategory =
  | "Food & Grocery"
  | "Electronics"
  | "Clothing & Footwear"
  | "Other";

export interface CatalogMetadata {
  category: ProductCategory;
  original_price: number;
  purchase_date: string; // ISO 8601
  warranty_remaining_months: number;
}

/** POST /api/returns/initiate — request body */
export interface InitiateReturnRequest {
  order_id: string;
  product_id: string;
  customer_id: string;
}

/** POST /api/returns/initiate — success response */
export interface InitiateReturnResponse {
  return_id: string;
  eligible: boolean;
  window_days: number;
  days_elapsed: number;
  category: ProductCategory;
  questions: Question[];
}

/** POST /api/returns/initiate — window expired response */
export interface ReturnExpiredResponse {
  return_id: null;
  eligible: false;
  message: string;
  expiry_date: string; // ISO 8601
}

/** POST /api/returns/{id}/submit — request body */
export interface SubmitReturnRequest {
  qa_answers: Record<string, string>;
  image_uris: string[];
  video_frame_uris: string[];
  catalog_metadata: CatalogMetadata;
}

/** POST /api/returns/{id}/submit — success response */
export interface SubmitReturnResponse {
  health_card: HealthCard;
  p2p_divert_offered: boolean;
}

/** POST /api/returns/{id}/p2p-choice — request body */
export interface P2PChoiceRequest {
  chose_p2p: boolean;
}

/** POST /api/returns/{id}/p2p-choice — success response */
export interface P2PChoiceResponse {
  health_card: HealthCard;
}
