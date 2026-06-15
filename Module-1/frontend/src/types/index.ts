/**
 * Central type exports for the Second Life frontend.
 */

export type {
  Condition,
  Disposition,
  HealthCardSource,
  FraudSignal,
  ScoreBreakdown,
  HealthCard,
} from "./health-card";

export type {
  SupplementaryInputType,
  SupplementaryInput,
  Question,
  ValidationResult,
} from "./question";

export type {
  ProductCategory,
  CatalogMetadata,
  InitiateReturnRequest,
  InitiateReturnResponse,
  ReturnExpiredResponse,
  SubmitReturnRequest,
  SubmitReturnResponse,
  P2PChoiceRequest,
  P2PChoiceResponse,
} from "./return-request";
