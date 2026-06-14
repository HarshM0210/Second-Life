import { useState } from "react";
import type {
  HealthCard as HealthCardType,
  Condition,
  Disposition,
} from "../types";

interface HealthCardProps {
  healthCard: HealthCardType;
}

const conditionColors: Record<
  Condition,
  { bg: string; text: string; border: string }
> = {
  Excellent: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
  },
  Good: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  Fair: {
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200",
  },
  Poor: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
};

const dispositionLabels: Record<Disposition, string> = {
  resell: "Resell",
  refurbish: "Refurbish",
  donate: "Donate",
  recycle: "Recycle",
  return_to_seller: "Return to Seller",
  manual_review: "Manual Review",
};

const dispositionColors: Record<Disposition, string> = {
  resell: "bg-emerald-100 text-emerald-800",
  refurbish: "bg-blue-100 text-blue-800",
  donate: "bg-purple-100 text-purple-800",
  recycle: "bg-gray-100 text-gray-800",
  return_to_seller: "bg-amber-100 text-amber-800",
  manual_review: "bg-red-100 text-red-800",
};

export function HealthCard({ healthCard }: HealthCardProps) {
  const [heatmapError, setHeatmapError] = useState(false);

  const conditionStyle = conditionColors[healthCard.condition];
  const confidencePercent = Math.round(healthCard.confidence * 100);

  const breakdown = healthCard.score_breakdown;
  const totalPenalty = breakdown
    ? breakdown.w1_anomaly_contribution +
      breakdown.w2_defect_contribution +
      breakdown.w3_reason_contribution +
      breakdown.w4_wear_contribution
    : 0;

  return (
    <div className="max-w-2xl mx-auto rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Health Card</h2>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium">
          <svg
            className="w-3.5 h-3.5"
            fill="currentColor"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M16.403 12.652a3 3 0 000-5.304 3 3 0 00-3.75-3.751 3 3 0 00-5.305 0 3 3 0 00-3.751 3.75 3 3 0 000 5.305 3 3 0 003.75 3.751 3 3 0 005.305 0 3 3 0 003.751-3.75zm-2.546-4.46a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.06l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
              clipRule="evenodd"
            />
          </svg>
          Certified by Amazon AI
        </span>
      </div>

      <div className="p-6 space-y-5">
        {/* Condition + Score + Confidence row */}
        <div className="flex items-center gap-4 flex-wrap">
          <span
            className={`px-3 py-1 rounded-full text-sm font-semibold border ${conditionStyle.bg} ${conditionStyle.text} ${conditionStyle.border}`}
          >
            {healthCard.condition}
          </span>
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-bold text-gray-900">
              {healthCard.health_score}
            </span>
            <span className="text-sm text-gray-500">/100</span>
          </div>
          <span className="text-sm text-gray-500">
            Confidence:{" "}
            <span className="font-medium text-gray-700">
              {confidencePercent}%
            </span>
          </span>
        </div>

        {/* Score Breakdown Bar */}
        {breakdown && totalPenalty > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-gray-700">
              Score Breakdown
            </h3>
            <div className="flex h-7 rounded-lg overflow-hidden border border-gray-200">
              <BreakdownSegment
                label="Anomaly"
                value={breakdown.w1_anomaly_contribution}
                total={totalPenalty}
                color="bg-rose-400"
              />
              <BreakdownSegment
                label="Defect"
                value={breakdown.w2_defect_contribution}
                total={totalPenalty}
                color="bg-orange-400"
              />
              <BreakdownSegment
                label="Reason"
                value={breakdown.w3_reason_contribution}
                total={totalPenalty}
                color="bg-yellow-400"
              />
              <BreakdownSegment
                label="Wear"
                value={breakdown.w4_wear_contribution}
                total={totalPenalty}
                color="bg-sky-400"
              />
            </div>
          </div>
        )}

        {/* Defects */}
        <div className="space-y-1.5">
          <h3 className="text-sm font-medium text-gray-700">Defects</h3>
          {healthCard.defects.length === 0 ? (
            <p className="text-sm text-gray-500 italic">No defects detected</p>
          ) : (
            <ul className="list-disc list-inside space-y-0.5">
              {healthCard.defects.map((defect, i) => (
                <li key={i} className="text-sm text-gray-700">
                  {defect}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Heatmap */}
        <div className="space-y-1.5">
          <h3 className="text-sm font-medium text-gray-700">Anomaly Heatmap</h3>
          {heatmapError ? (
            <div className="flex items-center justify-center h-40 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-sm text-gray-400">Heatmap unavailable</span>
            </div>
          ) : (
            <img
              src={healthCard.anomaly_heatmap_uri}
              alt="Anomaly heatmap showing detected regions"
              className="w-full h-40 object-contain rounded-lg border border-gray-200 bg-gray-50"
              onError={() => setHeatmapError(true)}
            />
          )}
        </div>

        {/* Justification */}
        <div className="space-y-1.5">
          <h3 className="text-sm font-medium text-gray-700">Justification</h3>
          <p className="text-sm text-gray-600 leading-relaxed">
            {healthCard.justification}
          </p>
        </div>

        {/* Disposition */}
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-gray-700">Disposition:</h3>
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${dispositionColors[healthCard.disposition]}`}
          >
            {dispositionLabels[healthCard.disposition]}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ---------- Internal Components ---------- */

interface BreakdownSegmentProps {
  label: string;
  value: number;
  total: number;
  color: string;
}

function BreakdownSegment({
  label,
  value,
  total,
  color,
}: BreakdownSegmentProps) {
  if (value <= 0) return null;

  const percentage = (value / total) * 100;
  const displayValue = value.toFixed(1);

  return (
    <div
      className={`${color} flex items-center justify-center text-xs font-medium text-white relative`}
      style={{ width: `${percentage}%` }}
      title={`${label}: ${displayValue}`}
    >
      {percentage >= 15 && (
        <span className="truncate px-1">
          {label} {displayValue}
        </span>
      )}
    </div>
  );
}
