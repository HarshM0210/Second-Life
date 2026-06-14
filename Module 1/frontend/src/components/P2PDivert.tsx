import { useState, useEffect, useCallback, useRef } from "react";
import type { HealthCard } from "../types";
import { submitP2PChoice } from "../services/returns";

interface P2PDivertProps {
  returnId: string;
  onComplete: (healthCard: HealthCard) => void;
}

/** 30-minute timeout in milliseconds */
const TIMEOUT_MS = 30 * 60 * 1000;

/**
 * P2P Divert UI — a non-accusatory offer screen presented when fraud confidence
 * is elevated. Offers the customer two choices without any fraud/theft/dishonesty
 * language.
 */
export function P2PDivert({ returnId, onComplete }: P2PDivertProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeLeft, setTimeLeft] = useState(TIMEOUT_MS);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasSubmitted = useRef(false);

  const handleChoice = useCallback(
    async (choseP2P: boolean) => {
      if (hasSubmitted.current || isSubmitting) return;
      hasSubmitted.current = true;
      setIsSubmitting(true);
      setError(null);

      try {
        const response = await submitP2PChoice(returnId, {
          chose_p2p: choseP2P,
        });
        onComplete(response.health_card);
      } catch (err: unknown) {
        hasSubmitted.current = false;
        setIsSubmitting(false);
        const message =
          err instanceof Error
            ? err.message
            : "Something went wrong. Please try again.";
        setError(message);
      }
    },
    [returnId, onComplete, isSubmitting],
  );

  // Handle 30-minute timeout: auto-proceed with standard return + enhanced_inspection
  useEffect(() => {
    const startTime = Date.now();

    // Countdown timer (updates every second)
    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, TIMEOUT_MS - elapsed);
      setTimeLeft(remaining);

      if (remaining <= 0 && timerRef.current) {
        clearInterval(timerRef.current);
      }
    }, 1000);

    // Timeout handler: auto-proceed with standard return
    timeoutRef.current = setTimeout(() => {
      if (!hasSubmitted.current) {
        handleChoice(false);
      }
    }, TIMEOUT_MS);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [handleChoice]);

  const formatTimeLeft = (ms: number): string => {
    const totalSeconds = Math.ceil(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  return (
    <div className="max-w-lg mx-auto p-6">
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-indigo-100">
              <svg
                className="w-5 h-5 text-indigo-600"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
                />
              </svg>
            </span>
            <h2 className="text-lg font-semibold text-gray-900">
              You have options
            </h2>
          </div>
          <p className="text-sm text-gray-600 leading-relaxed">
            We noticed this item may have been used. You can choose how
            you&apos;d like to proceed with your return.
          </p>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {/* Option 1: P2P Resell */}
          <button
            type="button"
            onClick={() => handleChoice(true)}
            disabled={isSubmitting}
            className="w-full text-left rounded-lg border-2 border-indigo-200 bg-indigo-50/50 p-4 transition hover:border-indigo-400 hover:bg-indigo-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="flex items-start gap-3">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-indigo-100 shrink-0 mt-0.5">
                <svg
                  className="w-4 h-4 text-indigo-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.75 10.5V6a3.75 3.75 0 1 0-7.5 0v4.5m11.356-1.993 1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 0 1-1.12-1.243l1.264-12A1.125 1.125 0 0 1 5.513 7.5h12.974c.576 0 1.059.435 1.119 1.007ZM8.625 10.5a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm7.5 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z"
                  />
                </svg>
              </span>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">
                  Resell via ReLoop P2P
                </h3>
                <p className="mt-1 text-xs text-gray-500 leading-relaxed">
                  List your item on our peer-to-peer marketplace. Get a fair
                  price while giving it a second life.
                </p>
              </div>
            </div>
          </button>

          {/* Option 2: Standard Return Inspection */}
          <button
            type="button"
            onClick={() => handleChoice(false)}
            disabled={isSubmitting}
            className="w-full text-left rounded-lg border-2 border-gray-200 bg-gray-50/50 p-4 transition hover:border-gray-400 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="flex items-start gap-3">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 shrink-0 mt-0.5">
                <svg
                  className="w-4 h-4 text-gray-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
                  />
                </svg>
              </span>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">
                  Proceed with standard return inspection
                </h3>
                <p className="mt-1 text-xs text-gray-500 leading-relaxed">
                  Continue with the standard return process. Your item will
                  undergo quality inspection.
                </p>
              </div>
            </div>
          </button>

          {/* Error message */}
          {error && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 px-4 py-3"
            >
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Loading state */}
          {isSubmitting && (
            <div className="flex items-center justify-center gap-2 py-2">
              <svg
                className="animate-spin h-4 w-4 text-indigo-600"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
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
              <span className="text-sm text-gray-600">
                Processing your choice...
              </span>
            </div>
          )}
        </div>

        {/* Footer with timer */}
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
          <p className="text-xs text-gray-500 text-center">
            Time remaining to make a choice:{" "}
            <span className="font-medium text-gray-700">
              {formatTimeLeft(timeLeft)}
            </span>
          </p>
          <p className="text-xs text-gray-400 text-center mt-1">
            If no selection is made, the standard return inspection will proceed
            automatically.
          </p>
        </div>
      </div>
    </div>
  );
}
