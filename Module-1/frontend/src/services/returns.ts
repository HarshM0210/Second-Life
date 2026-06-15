import apiClient from "./api";
import type {
  InitiateReturnRequest,
  InitiateReturnResponse,
  ReturnExpiredResponse,
  SubmitReturnRequest,
  SubmitReturnResponse,
  P2PChoiceRequest,
  P2PChoiceResponse,
} from "../types";

/**
 * Returns API service layer.
 * Wraps all /api/returns/* endpoints for the frontend.
 */

/**
 * Initiate a return request — validates return window and returns Q&A questions.
 * Returns the eligible response on 200, or the expired response on 403.
 */
export async function initiateReturn(
  data: InitiateReturnRequest,
): Promise<InitiateReturnResponse | ReturnExpiredResponse> {
  try {
    const response = await apiClient.post<InitiateReturnResponse>(
      "/returns/initiate",
      data,
    );
    return response.data;
  } catch (error: unknown) {
    if (
      error &&
      typeof error === "object" &&
      "response" in error &&
      (error as { response?: { status?: number; data?: unknown } }).response
        ?.status === 403
    ) {
      return (error as { response: { data: ReturnExpiredResponse } }).response
        .data;
    }
    throw error;
  }
}

/**
 * Submit Q&A answers, media URIs, and catalog metadata to trigger the grading pipeline.
 */
export async function submitReturn(
  returnId: string,
  data: SubmitReturnRequest,
): Promise<SubmitReturnResponse> {
  const response = await apiClient.post<SubmitReturnResponse>(
    `/returns/${returnId}/submit`,
    data,
  );
  return response.data;
}

/**
 * Submit the customer's P2P divert choice.
 */
export async function submitP2PChoice(
  returnId: string,
  data: P2PChoiceRequest,
): Promise<P2PChoiceResponse> {
  const response = await apiClient.post<P2PChoiceResponse>(
    `/returns/${returnId}/p2p-choice`,
    data,
  );
  return response.data;
}
