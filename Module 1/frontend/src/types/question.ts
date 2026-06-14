/**
 * Structured Q&A models used by the QA Collector.
 */

export type SupplementaryInputType = "text_field" | "date_picker";

export interface SupplementaryInput {
  type: SupplementaryInputType;
  max_length?: number; // 200 for text fields
}

export interface Question {
  id: string;
  text: string;
  options: string[];
  supplementary_input: SupplementaryInput | null;
  conditional_display: string | null; // e.g., "footwear_only"
}

export interface ValidationResult {
  is_valid: boolean;
  missing_question_ids: string[];
}
