import axios from "axios";
import type {
  Feed, ImpactSummary, InitiateResponse, PickupJob, PriceQuote,
  PipelineResult, Reward, RiskResponse, SubmitResponse, Wallet,
} from "@/types";

// Single origin: everything is relative and proxied to the gateway (:8080).
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const http = axios.create({ baseURL: API_BASE, timeout: 40000 });

// --- Module 4: Green Coin ---
export const getWallet = (userId: string) =>
  http.get<Wallet>(`/api/wallet/${encodeURIComponent(userId)}`).then((r) => r.data);

export const getImpact = () =>
  http.get<ImpactSummary>("/api/impact").then((r) => r.data);

export const getRewards = () =>
  http.get<Reward[]>("/api/rewards").then((r) => r.data);

export const redeem = (userId: string, rewardId: string) =>
  http.post("/api/redeem", { user_id: userId, reward_id: rewardId }).then((r) => r.data);

// --- Module 2: Recommend ---
export const getRecommend = (userId: string, k = 8) =>
  http.get<Feed>(`/api/recommend`, { params: { user_id: userId, k } }).then((r) => r.data);

// --- Module 3: Return Prevention ---
export const getRiskScore = (body: {
  customer_id: string;
  product_id: string;
  page_dwell_seconds?: number;
  is_buy_now?: boolean;
  seller_id?: string;
  product_price?: number;
  is_sale_active?: boolean;
  product_review_rating?: number;
}) => http.post<RiskResponse>("/api/risk-score", body).then((r) => r.data);

// --- Module 1: Returns flow ---
export const initiateReturn = (body: {
  order_id: string; product_id: string; customer_id: string;
  category: string; delivery_date?: string;
}) => http.post<InitiateResponse>("/api/returns/initiate", body).then((r) => r.data);

export const submitReturn = (returnId: string, body: {
  qa_answers: Record<string, string>;
  image_uris: string[];
  catalog_metadata: Record<string, unknown>;
  video_frame_uris?: string[];
  connected_accounts?: string[];
}) => http.post<SubmitResponse>(`/api/returns/${returnId}/submit`, body).then((r) => r.data);

export const p2pChoice = (returnId: string, choseP2p: boolean) =>
  http.post(`/api/returns/${returnId}/p2p-choice`, { chose_p2p: choseP2p }).then((r) => r.data);

// --- Module 5: P2P ---
export const p2pQuote = (listing: Record<string, unknown>) =>
  http.post<PriceQuote>("/api/p2p/quote", listing).then((r) => r.data);

export const p2pAccept = (skuId: string) =>
  http.post<PickupJob>("/api/p2p/accept", { sku_id: skuId }).then((r) => r.data);

// --- Gateway orchestrated pipeline ---
export const runPipelineReturn = (body: Record<string, unknown>) =>
  http.post<PipelineResult>("/pipeline/return", body).then((r) => r.data);
