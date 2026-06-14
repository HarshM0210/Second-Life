import { useState, useCallback } from "react";
import type { Question } from "../types/question";

interface QAFormProps {
  questions: Question[];
  onSubmit: (answers: Record<string, string>) => void;
  isFootwear?: boolean;
}

/**
 * Structured Q&A form component.
 * Renders category-specific questions dynamically from the API response.
 * Handles conditional display, supplementary inputs, and validation.
 */
export default function QAForm({
  questions,
  onSubmit,
  isFootwear = false,
}: QAFormProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [supplementary, setSupplementary] = useState<Record<string, string>>(
    {},
  );
  const [attempted, setAttempted] = useState(false);

  // Filter questions based on conditional display rules
  const visibleQuestions = questions.filter((q) => {
    if (q.conditional_display === "footwear_only") {
      return isFootwear;
    }
    return true;
  });

  const unansweredIds = visibleQuestions
    .filter((q) => !answers[q.id])
    .map((q) => q.id);

  const handleOptionSelect = useCallback(
    (questionId: string, option: string) => {
      setAnswers((prev) => ({ ...prev, [questionId]: option }));
    },
    [],
  );

  const handleSupplementaryChange = useCallback(
    (questionId: string, value: string) => {
      setSupplementary((prev) => ({ ...prev, [questionId]: value }));
    },
    [],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAttempted(true);

    if (unansweredIds.length > 0) {
      return;
    }

    // Merge supplementary inputs into the answer map
    const finalAnswers: Record<string, string> = { ...answers };
    for (const q of visibleQuestions) {
      if (q.supplementary_input && supplementary[q.id]) {
        finalAnswers[`${q.id}_supplementary`] = supplementary[q.id];
      }
    }

    onSubmit(finalAnswers);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {visibleQuestions.map((question, index) => {
        const isUnanswered = attempted && !answers[question.id];

        return (
          <div
            key={question.id}
            className={`rounded-lg border p-4 ${
              isUnanswered
                ? "border-red-400 bg-red-50"
                : "border-gray-200 bg-white"
            }`}
          >
            {/* Question header */}
            <div className="mb-3 flex items-start gap-2">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                {index + 1}
              </span>
              <p className="text-sm font-medium text-gray-800">
                {question.text}
                <span className="ml-1 text-red-500">*</span>
              </p>
            </div>

            {/* Unanswered indicator */}
            {isUnanswered && (
              <p className="mb-2 text-xs text-red-600">
                Please select an answer for this question.
              </p>
            )}

            {/* Radio options */}
            <div className="ml-8 space-y-2">
              {question.options.map((option) => (
                <label
                  key={option}
                  className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition-colors ${
                    answers[question.id] === option
                      ? "border-indigo-500 bg-indigo-50 text-indigo-800"
                      : "border-gray-200 bg-gray-50 text-gray-700 hover:border-gray-300 hover:bg-gray-100"
                  }`}
                >
                  <input
                    type="radio"
                    name={question.id}
                    value={option}
                    checked={answers[question.id] === option}
                    onChange={() => handleOptionSelect(question.id, option)}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>{option}</span>
                </label>
              ))}
            </div>

            {/* Supplementary input */}
            {question.supplementary_input && (
              <div className="ml-8 mt-3">
                {question.supplementary_input.type === "text_field" && (
                  <div>
                    <label
                      htmlFor={`${question.id}-supplementary`}
                      className="mb-1 block text-xs text-gray-500"
                    >
                      Additional details (optional, max{" "}
                      {question.supplementary_input.max_length ?? 200}{" "}
                      characters)
                    </label>
                    <input
                      id={`${question.id}-supplementary`}
                      type="text"
                      maxLength={question.supplementary_input.max_length ?? 200}
                      value={supplementary[question.id] ?? ""}
                      onChange={(e) =>
                        handleSupplementaryChange(question.id, e.target.value)
                      }
                      placeholder="Provide additional details..."
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    <p className="mt-1 text-right text-xs text-gray-400">
                      {(supplementary[question.id] ?? "").length}/
                      {question.supplementary_input.max_length ?? 200}
                    </p>
                  </div>
                )}

                {question.supplementary_input.type === "date_picker" && (
                  <div>
                    <label
                      htmlFor={`${question.id}-date`}
                      className="mb-1 block text-xs text-gray-500"
                    >
                      Select date
                    </label>
                    <input
                      id={`${question.id}-date`}
                      type="date"
                      value={supplementary[question.id] ?? ""}
                      onChange={(e) =>
                        handleSupplementaryChange(question.id, e.target.value)
                      }
                      className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* Validation summary */}
      {attempted && unansweredIds.length > 0 && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3">
          <p className="text-sm font-medium text-red-700">
            Please answer all required questions before submitting.
          </p>
          <p className="mt-1 text-xs text-red-600">
            {unansweredIds.length} unanswered{" "}
            {unansweredIds.length === 1 ? "question" : "questions"} remaining.
          </p>
        </div>
      )}

      {/* Submit button */}
      <button
        type="submit"
        className="w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Submit Answers
      </button>
    </form>
  );
}
