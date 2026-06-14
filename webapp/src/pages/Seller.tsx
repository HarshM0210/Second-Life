import { useEffect, useState } from "react";
import { getImpact } from "@/api/client";
import type { ImpactSummary } from "@/types";

// Illustrative seller batch (the "Small Seller — 200 returns/month" persona).
const BATCH = [
  { item: "Cotton T-Shirt", disp: "resell", score: 95, coins: 60 },
  { item: "Bluetooth Speaker", disp: "refurbish", score: 82, coins: 380 },
  { item: "Running Shoes", disp: "donate", score: 64, coins: 80 },
  { item: "Phone Case", disp: "recycle", score: 28, coins: 4 },
  { item: "Yoga Mat", disp: "resell", score: 91, coins: 50 },
] as Array<{ item: string; disp?: string; disposition?: string; score: number; coins: number }>;

const dispColor: Record<string, string> = {
  resell: "text-amz-green", refurbish: "text-lime-700",
  donate: "text-amber-700", recycle: "text-red-700",
};

export default function Seller() {
  const [impact, setImpact] = useState<ImpactSummary | null>(null);
  useEffect(() => { getImpact().then(setImpact).catch(() => {}); }, []);

  const rows = BATCH.map((b) => ({ ...b, d: b.disp ?? b.disposition ?? "resell" }));
  const totalCoins = rows.reduce((s, r) => s + r.coins, 0);

  return (
    <div className="space-y-4">
      <div className="card p-5 bg-gradient-to-r from-amz-slate to-amz-navy text-white">
        <h1 className="text-xl font-bold">Seller Hub</h1>
        <p className="text-sm text-gray-300 mt-1">
          200 returns/month, auto-graded by AI — no manual inspection, no guesswork on price.
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="text-xs text-gray-500">Items auto-graded (this batch)</div>
          <div className="text-3xl font-bold">{rows.length}</div>
          <div className="text-xs text-amz-green">0 manual inspections</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-gray-500">Green Coin issued to buyers</div>
          <div className="text-3xl font-bold">{totalCoins.toLocaleString()}</div>
          <div className="text-xs text-gray-400">drives Renewed demand</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-gray-500">Platform CO₂e avoided (ESG)</div>
          <div className="text-3xl font-bold text-amz-green">
            {impact ? impact.co2e_avoided_kg.toLocaleString() : "…"} kg
          </div>
          <div className="text-xs text-gray-400">
            ≈ {impact ? impact.trees_equivalent.toLocaleString() : "…"} trees · investor-ready number
          </div>
        </div>
      </div>

      <div className="card p-4">
        <h2 className="font-bold mb-3">Auto-graded returns queue</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-200">
              <th className="py-2">Item</th><th>Health score</th><th>Disposition</th><th className="text-right">Green Coin</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.item} className="border-b border-gray-50">
                <td className="py-2">{r.item}</td>
                <td>{r.score}/100</td>
                <td className={`font-medium ${dispColor[r.d] ?? "text-gray-700"}`}>{r.d}</td>
                <td className="text-right text-amz-green">+{r.coins}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-gray-400 mt-2">
          Illustrative batch. In the live flow each row is a Module 1 Health Card → routing decision.
        </p>
      </div>
    </div>
  );
}
