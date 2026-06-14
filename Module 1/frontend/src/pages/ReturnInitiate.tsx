import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { initiateReturn } from "../services/returns";
import type {
  InitiateReturnRequest,
  InitiateReturnResponse,
  ReturnExpiredResponse,
} from "../types";

/**
 * Return Initiation page.
 * Collects order_id, product_id, and customer_id, then calls POST /api/returns/initiate.
 * On success (eligible), navigates to the Q&A page with the return context.
 * On expired window (ineligible), displays the expiry message and blocks further navigation.
 */
export default function ReturnInitiate() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState<InitiateReturnRequest>({
    order_id: "",
    product_id: "",
    customer_id: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expiredInfo, setExpiredInfo] = useState<ReturnExpiredResponse | null>(
    null,
  );

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setExpiredInfo(null);

    // Basic client-side validation
    if (
      !formData.order_id.trim() ||
      !formData.product_id.trim() ||
      !formData.customer_id.trim()
    ) {
      setError("All fields are required.");
      return;
    }

    setLoading(true);

    try {
      const response = await initiateReturn(formData);

      if (response.eligible) {
        // Eligible — navigate to Q&A page with return context
        const eligible = response as InitiateReturnResponse;
        navigate("/return/qa", {
          state: {
            return_id: eligible.return_id,
            category: eligible.category,
            questions: eligible.questions,
            window_days: eligible.window_days,
            days_elapsed: eligible.days_elapsed,
          },
        });
      } else {
        // Window expired — display expiry message
        setExpiredInfo(response as ReturnExpiredResponse);
      }
    } catch (err: unknown) {
      // Service error — prompt retry (Req 1.5)
      if (err instanceof Error) {
        setError(
          err.message ||
            "Unable to verify return eligibility. Please try again.",
        );
      } else {
        setError("Unable to verify return eligibility. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">
        Initiate a Return
      </h1>

      {/* Expired window message — blocks further navigation */}
      {expiredInfo && (
        <div
          className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4"
          role="alert"
          aria-live="assertive"
        >
          <h2 className="mb-1 text-lg font-semibold text-red-800">
            Return Window Expired
          </h2>
          <p className="text-red-700">{expiredInfo.message}</p>
          <p className="mt-2 text-sm text-red-600">
            Expiry date:{" "}
            <time dateTime={expiredInfo.expiry_date}>
              {new Date(expiredInfo.expiry_date).toLocaleDateString()}
            </time>
          </p>
        </div>
      )}

      {/* Error message for service errors */}
      {error && !expiredInfo && (
        <div
          className="mb-6 rounded-lg border border-yellow-200 bg-yellow-50 p-4"
          role="alert"
          aria-live="polite"
        >
          <p className="text-yellow-800">{error}</p>
        </div>
      )}

      {/* Form — hidden when return window is expired */}
      {!expiredInfo && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="order_id"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Order ID
            </label>
            <input
              id="order_id"
              name="order_id"
              type="text"
              value={formData.order_id}
              onChange={handleChange}
              placeholder="e.g. ORD-123456"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label
              htmlFor="product_id"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Product ID
            </label>
            <input
              id="product_id"
              name="product_id"
              type="text"
              value={formData.product_id}
              onChange={handleChange}
              placeholder="e.g. PROD-789"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label
              htmlFor="customer_id"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Customer ID
            </label>
            <input
              id="customer_id"
              name="customer_id"
              type="text"
              value={formData.customer_id}
              onChange={handleChange}
              placeholder="e.g. CUST-001"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={loading}
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Checking eligibility..." : "Check Return Eligibility"}
          </button>
        </form>
      )}
    </div>
  );
}
