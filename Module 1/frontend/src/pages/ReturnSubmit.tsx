import { useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import QAForm from "../components/QAForm";
import MediaUpload from "../components/MediaUpload";
import { submitReturn } from "../services/returns";
import type { Question, ProductCategory, CatalogMetadata } from "../types";

/**
 * Navigation state passed from ReturnInitiate page.
 */
interface ReturnSubmitLocationState {
  return_id: string;
  category: ProductCategory;
  questions: Question[];
  window_days: number;
  days_elapsed: number;
}

/**
 * Return Submission page.
 * Combines QAForm and MediaUpload on a single page.
 * On submit: calls POST /api/returns/{id}/submit with Q&A answers, media URIs, and catalog metadata.
 * Routes to Health Card display or P2P divert UI based on the response.
 */
export default function ReturnSubmit() {
  const location = useLocation();
  const navigate = useNavigate();

  const state = location.state as ReturnSubmitLocationState | null;

  const [imageUris, setImageUris] = useState<string[]>([]);
  const [frameUris, setFrameUris] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleImagesChange = useCallback((uris: string[]) => {
    setImageUris(uris);
  }, []);

  const handleFramesChange = useCallback((uris: string[]) => {
    setFrameUris(uris);
  }, []);

  // If no navigation state is available, show an error
  if (!state) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <div
          className="rounded-lg border border-red-200 bg-red-50 p-4"
          role="alert"
        >
          <h2 className="text-lg font-semibold text-red-800">
            Missing Return Context
          </h2>
          <p className="mt-1 text-red-700">
            No return information found. Please start from the{" "}
            <a href="/return/initiate" className="underline hover:no-underline">
              return initiation page
            </a>
            .
          </p>
        </div>
      </div>
    );
  }

  const { return_id, category, questions } = state;
  const isFootwear = category === "Clothing & Footwear";

  async function handleQASubmit(answers: Record<string, string>) {
    setError(null);

    // Validate that at least one image is uploaded
    if (imageUris.length === 0) {
      setError("Please upload at least one image before submitting.");
      return;
    }

    setLoading(true);

    try {
      const catalogMetadata: CatalogMetadata = {
        category,
        original_price: 0, // Will be populated by backend from order data
        purchase_date: new Date().toISOString().split("T")[0]!,
        warranty_remaining_months: 0,
      };

      const response = await submitReturn(return_id, {
        qa_answers: answers,
        image_uris: imageUris,
        video_frame_uris: frameUris,
        catalog_metadata: catalogMetadata,
      });

      // Route based on response
      if (response.p2p_divert_offered) {
        navigate("/return/p2p-choice", {
          state: {
            return_id,
            health_card: response.health_card,
          },
        });
      } else {
        navigate("/return/health-card", {
          state: {
            return_id,
            health_card: response.health_card,
          },
        });
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message || "Failed to submit return. Please try again.");
      } else {
        setError("Failed to submit return. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-2 text-2xl font-bold text-gray-900">
        Submit Your Return
      </h1>
      <p className="mb-6 text-sm text-gray-500">
        Return ID: <span className="font-mono">{return_id}</span> &middot;
        Category: <span className="font-medium">{category}</span>
      </p>

      {/* Error message */}
      {error && (
        <div
          className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4"
          role="alert"
          aria-live="polite"
        >
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Loading overlay */}
      {loading && (
        <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="flex items-center gap-3">
            <svg
              className="h-5 w-5 animate-spin text-blue-600"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            <div>
              <p className="text-sm font-medium text-blue-800">
                Processing your return...
              </p>
              <p className="text-xs text-blue-600">
                This may take up to 2 seconds while we assess item condition.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Q&A Section */}
      <section className="mb-8">
        <h2 className="mb-4 text-lg font-semibold text-gray-800">
          Return Questions
        </h2>
        <QAForm
          questions={questions}
          onSubmit={handleQASubmit}
          isFootwear={isFootwear}
        />
      </section>

      {/* Media Upload Section */}
      <section className="mb-8">
        <h2 className="mb-4 text-lg font-semibold text-gray-800">
          Upload Photos & Video
        </h2>
        <MediaUpload
          onImagesChange={handleImagesChange}
          onFramesChange={handleFramesChange}
        />
      </section>
    </div>
  );
}
