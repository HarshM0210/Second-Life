import type { HealthCard as HC } from "@/types";
import { ConditionBadge } from "@/components/ui";

const dispositionCopy: Record<string, { label: string; color: string }> = {
  resell: { label: "Resell as Renewed", color: "text-amz-green" },
  refurbish: { label: "Refurbish → list", color: "text-lime-700" },
  donate: { label: "Donate locally", color: "text-amber-700" },
  recycle: { label: "Recycle responsibly", color: "text-red-700" },
  return_to_seller: { label: "Return to seller", color: "text-gray-700" },
  manual_review: { label: "Manual review", color: "text-gray-700" },
};

function scoreColor(s: number) {
  if (s > 90) return "bg-emerald-500";
  if (s > 70) return "bg-lime-500";
  if (s > 50) return "bg-amber-500";
  return "bg-red-500";
}

export default function HealthCard({ card }: { card: HC }) {
  const disp = dispositionCopy[card.disposition] ?? { label: card.disposition, color: "text-gray-700" };
  const fraud = card.fraud_signal;
  return (
    <div className="card overflow-hidden">
      <div className="bg-amz-navy text-white px-4 py-2 flex items-center justify-between">
        <span className="font-semibold flex items-center gap-2">
          <span className="text-amz-orange">✓</span> Product Health Card
        </span>
        <span className="text-xs text-gray-300">Certified by Amazon AI</span>
      </div>

      <div className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ConditionBadge condition={card.condition} />
            <span className="text-sm text-gray-600">
              confidence {(card.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold">{card.health_score}<span className="text-sm text-gray-400">/100</span></div>
            <div className="text-xs text-gray-500">health score</div>
          </div>
        </div>

        {/* Score bar */}
        <div>
          <div className="h-3 w-full rounded-full bg-gray-200 overflow-hidden">
            <div className={`h-full ${scoreColor(card.health_score)}`} style={{ width: `${card.health_score}%` }} />
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-gray-400">
            <span>Recycle</span><span>Donate</span><span>Refurbish</span><span>Resell</span>
          </div>
        </div>

        <div className="text-sm">
          <span className="text-gray-500">Disposition: </span>
          <span className={`font-semibold ${disp.color}`}>{disp.label}</span>
        </div>

        <p className="text-sm text-gray-700 bg-gray-50 rounded p-3 border border-gray-100">
          {card.justification}
        </p>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <Info label="Warranty left" value={`${card.warranty_left_months} mo`} />
          <Info label="Defects" value={card.defects.length ? card.defects.join(", ") : "none detected"} />
          <Info label="Source" value={card.source === "p2p_fraud_divert" ? "P2P fraud divert" : "Standard return"} />
          <Info label="Fraud confidence" value={`${(fraud.fraud_confidence * 100).toFixed(0)}%`}
                highlight={fraud.fraud_confidence >= 0.6} />
        </div>

        {card.flags?.includes("enhanced_inspection") && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
            ⚑ Flagged for enhanced inspection at the warehouse.
          </div>
        )}
      </div>
    </div>
  );
}

function Info({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`rounded border p-2 ${highlight ? "border-red-300 bg-red-50" : "border-gray-100 bg-gray-50"}`}>
      <div className="text-gray-400">{label}</div>
      <div className={`font-medium ${highlight ? "text-red-700" : "text-[#0f1111]"}`}>{value}</div>
    </div>
  );
}
