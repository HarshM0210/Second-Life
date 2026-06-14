export function Stars({ rating, reviews }: { rating: number; reviews?: number }) {
  const full = Math.round(rating);
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span className="text-amz-orange tracking-tight" aria-label={`${rating} stars`}>
        {"★".repeat(full)}<span className="text-gray-300">{"★".repeat(5 - full)}</span>
      </span>
      {reviews !== undefined && <span className="text-amz-link">{reviews.toLocaleString()}</span>}
    </span>
  );
}

export function Price({ value, original }: { value: number; original?: number }) {
  return (
    <span className="flex items-baseline gap-2">
      <span className="text-lg font-medium text-[#0f1111]">
        <span className="text-xs align-top">₹</span>{value.toLocaleString()}
      </span>
      {original && original > value && (
        <span className="text-xs text-gray-500 line-through">₹{original.toLocaleString()}</span>
      )}
    </span>
  );
}

export function RenewedBadge() {
  return (
    <span className="pill bg-amz-green/10 text-amz-green border border-amz-green/30">
      ♻ Renewed
    </span>
  );
}

const conditionColor: Record<string, string> = {
  Excellent: "bg-emerald-100 text-emerald-800 border-emerald-300",
  Good: "bg-lime-100 text-lime-800 border-lime-300",
  Fair: "bg-amber-100 text-amber-800 border-amber-300",
  Poor: "bg-red-100 text-red-800 border-red-300",
};

export function ConditionBadge({ condition }: { condition: string }) {
  return (
    <span className={`pill border ${conditionColor[condition] ?? "bg-gray-100 text-gray-700 border-gray-300"}`}>
      {condition}
    </span>
  );
}
