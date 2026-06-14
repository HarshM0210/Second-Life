import { useEffect, useState } from "react";
import { getImpact } from "@/api/client";
import type { ImpactSummary } from "@/types";

export default function ImpactTicker() {
  const [impact, setImpact] = useState<ImpactSummary | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const data = await getImpact();
        if (alive) { setImpact(data); setErr(false); }
      } catch {
        if (alive) setErr(true);
      }
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <div className="bg-amz-green text-white text-sm">
      <div className="max-w-[1500px] mx-auto px-3 py-1.5 flex items-center gap-4 flex-wrap">
        <span className="font-semibold">🌱 SecondLIFE impact, since launch</span>
        {err && <span className="text-white/80">· connecting to services…</span>}
        {impact && (
          <span className="flex items-center gap-4">
            <b>{impact.co2e_avoided_kg.toLocaleString()} kg</b> CO₂e avoided
            <span className="opacity-60">·</span>
            <b>{impact.items_given_second_life.toLocaleString()}</b> items given a second life
            <span className="opacity-60">·</span>
            ≈ <b>{impact.trees_equivalent.toLocaleString()}</b> trees
          </span>
        )}
      </div>
    </div>
  );
}
