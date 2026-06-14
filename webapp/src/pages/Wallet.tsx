import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/state/session";
import { getWallet, getRewards, redeem } from "@/api/client";
import type { Wallet as WalletT, Reward } from "@/types";

export default function Wallet() {
  const { persona } = useSession();
  const [wallet, setWallet] = useState<WalletT | null>(null);
  const [rewards, setRewards] = useState<Reward[]>([]);
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [w, r] = await Promise.all([getWallet(persona.customer_id), getRewards()]);
      setWallet(w); setRewards(r);
    } catch { setMsg("Could not load wallet — are the services running?"); }
    finally { setLoading(false); }
  }, [persona.customer_id]);

  useEffect(() => { void load(); }, [load]);

  const doRedeem = async (rewardId: string) => {
    setMsg("");
    try {
      const res = await redeem(persona.customer_id, rewardId) as { success?: boolean; reason?: string };
      setMsg(res.success ? "Redeemed! Balance updated." : `Could not redeem: ${res.reason}`);
      await load();
    } catch { setMsg("Redeem failed."); }
  };

  if (loading) return <div className="card p-6">Loading wallet…</div>;
  if (!wallet) return <div className="card p-6 text-red-700">{msg || "No wallet."}</div>;

  return (
    <div className="space-y-4">
      {/* Hero */}
      <div className="card overflow-hidden">
        <div className="bg-gradient-to-r from-amz-green to-emerald-700 text-white p-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-sm opacity-90">{persona.name}'s Green Coin balance</div>
            <div className="text-5xl font-bold">{wallet.balance.toLocaleString()} <span className="text-lg">coins</span></div>
          </div>
          <div className="text-right text-sm">
            <div className="text-3xl font-bold">{wallet.co2e_total_kg.toLocaleString()} kg</div>
            <div className="opacity-90">CO₂e avoided</div>
            <div className="mt-1 opacity-90">
              ≈ {Math.round(wallet.equivalents.trees_per_month ?? 0)} trees/mo ·
              {" "}{Math.round(wallet.equivalents.km_not_driven ?? 0)} km not driven
            </div>
          </div>
        </div>
        {/* Badges */}
        <div className="p-4 flex gap-3 flex-wrap">
          {wallet.badges.map((b) => (
            <div key={b.slug} title={b.equivalent}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${
                b.unlocked ? "bg-white border-amz-green/40" : "bg-gray-50 border-gray-200 opacity-50 grayscale"}`}>
              <span className="text-2xl">{b.icon}</span>
              <div className="text-xs">
                <div className="font-semibold">{b.name}</div>
                <div className="text-gray-500">{b.threshold_kg} kg</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {msg && <div className="card p-3 text-sm">{msg}</div>}

      <div className="grid md:grid-cols-2 gap-4">
        {/* Redeem catalog */}
        <div className="card p-4">
          <h2 className="font-bold mb-3">Redeem — Renewed only (closes the loop)</h2>
          <div className="space-y-2">
            {rewards.map((r) => {
              const afford = wallet.balance >= r.cost;
              return (
                <div key={r.reward_id} className="flex items-center justify-between border-b border-gray-100 pb-2">
                  <div>
                    <div className="text-sm font-medium">{r.name}</div>
                    <div className="text-xs text-gray-500">{r.description}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold">{r.cost} coins</div>
                    <button className="btn-amz mt-1" disabled={!afford} onClick={() => doRedeem(r.reward_id)}>
                      {afford ? "Redeem" : "Need more"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Timeline */}
        <div className="card p-4">
          <h2 className="font-bold mb-3">Activity</h2>
          <ul className="space-y-2">
            {wallet.history.length === 0 && (
              <li className="text-sm text-gray-500">No activity yet — process a return to earn coins.</li>
            )}
            {wallet.history.map((e) => (
              <li key={e.id} className="flex items-center justify-between text-sm border-b border-gray-50 pb-1.5">
                <div>
                  <span className="text-gray-700">{e.source.replace(/[:_]/g, " ")}</span>
                  {e.co2e_kg > 0 && <span className="text-xs text-gray-400"> · {e.co2e_kg.toFixed(1)} kg CO₂e</span>}
                </div>
                <span className={e.amount >= 0 ? "text-amz-green font-medium" : "text-amz-price font-medium"}>
                  {e.amount >= 0 ? "+" : ""}{e.amount}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
