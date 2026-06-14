import { useCallback, useEffect, useState } from "react";
import {
  getServices, getFeatureImportance, getScenarios, runScenario,
} from "@/api/client";
import type { ServicesResponse, ServiceStatus, PipelineResult, PipelineStep } from "@/types";

const MODULE_LABELS: Record<string, string> = {
  module_1_grading: "M1 · Grading / Fraud",
  module_2_recommend: "M2 · Recommend",
  module_3_prevention: "M3 · Return Prevention",
  module_4_green_coin: "M4 · Green Coin",
  module_5_p2p: "M5 · P2P Exchange",
};

export default function Ops() {
  const [services, setServices] = useState<ServicesResponse | null>(null);
  const [features, setFeatures] = useState<Record<string, number>>({});
  const [scenarios, setScenarios] = useState<{ name: string; label: string }[]>([]);
  const [trace, setTrace] = useState<PipelineResult | null>(null);
  const [running, setRunning] = useState("");

  const refresh = useCallback(async () => {
    try { setServices(await getServices()); } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(refresh, 5000);
    getFeatureImportance().then(setFeatures).catch(() => {});
    getScenarios().then(setScenarios).catch(() => {});
    return () => clearInterval(id);
  }, [refresh]);

  const run = async (name: string) => {
    setRunning(name); setTrace(null);
    try { setTrace(await runScenario(name)); }
    finally { setRunning(""); }
  };

  const maxFeat = Math.max(1, ...Object.values(features));

  return (
    <div className="space-y-4">
      <div className="card p-4 bg-amz-navy text-white">
        <h1 className="text-lg font-bold">Ops Console — The Intelligent Bridge, live</h1>
        <p className="text-sm text-gray-300">Service health, model explainability, and end-to-end pipeline traces across all five modules.</p>
      </div>

      {/* Service health */}
      <div className="card p-4">
        <h2 className="font-bold mb-3">Service health <span className="text-xs text-gray-400">(polls /services every 5s)</span></h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {services && Object.entries(MODULE_LABELS).map(([key, label]) => {
            const s = services[key] as ServiceStatus | undefined;
            const up = !!s?.up;
            return (
              <div key={key} className={`rounded-lg border p-3 ${up ? "border-emerald-300 bg-emerald-50" : "border-red-300 bg-red-50"}`}>
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span className={`w-2.5 h-2.5 rounded-full ${up ? "bg-emerald-500" : "bg-red-500"}`} />
                  {label}
                </div>
                <div className="text-xs text-gray-500 mt-1">{up ? "healthy" : "down"}</div>
              </div>
            );
          })}
          {!services && <div className="text-sm text-gray-500">Connecting…</div>}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Pipeline trace runner */}
        <div className="card p-4">
          <h2 className="font-bold mb-1">Run a pipeline trace</h2>
          <p className="text-xs text-gray-500 mb-3">
            Each scenario runs the full return → grade → route → reward → recommend flow via the gateway.
          </p>
          <div className="flex flex-wrap gap-2 mb-3">
            {scenarios.map((s) => (
              <button key={s.name} className="btn-ghost text-left" disabled={!!running}
                onClick={() => run(s.name)} title={s.label}>
                {running === s.name ? "Running…" : s.name}
              </button>
            ))}
          </div>

          {trace && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 text-sm">
                <Stat label="Disposition" value={trace.disposition ?? "—"} />
                <Stat label="Coins" value={trace.coins_earned?.toString() ?? "—"} />
                <Stat label="CO₂e kg" value={trace.co2e_kg?.toString() ?? "—"} />
              </div>
              {trace.health_card && (
                <div className="text-sm text-gray-700">
                  Health: <b>{trace.health_card.condition} {trace.health_card.health_score}/100</b> ·
                  fraud {(trace.health_card.fraud_signal.fraud_confidence * 100).toFixed(0)}%
                  {trace.chose_p2p && <span className="text-amz-orange"> · diverted to P2P</span>}
                </div>
              )}
              <ol className="space-y-1">
                {trace.steps.map((st: PipelineStep, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className={st.ok ? "text-emerald-600" : "text-red-600"}>{st.ok ? "✓" : "✗"}</span>
                    <span className="font-mono text-xs bg-gray-100 rounded px-1.5 py-0.5">{st.step}</span>
                    <span className="text-xs text-gray-500 truncate">
                      {Object.entries(st).filter(([k]) => !["step", "ok"].includes(k))
                        .map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ").slice(0, 90)}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>

        {/* Feature importance */}
        <div className="card p-4">
          <h2 className="font-bold mb-1">Return-risk model explainability</h2>
          <p className="text-xs text-gray-500 mb-3">LightGBM gain importance (Module 3) — serves the Trust Layer.</p>
          <div className="space-y-1.5">
            {Object.entries(features).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k}>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-700">{k}</span><span className="text-gray-400">{v}</span>
                </div>
                <div className="h-2 bg-gray-100 rounded">
                  <div className="h-full bg-amz-orange rounded" style={{ width: `${(v / maxFeat) * 100}%` }} />
                </div>
              </div>
            ))}
            {Object.keys(features).length === 0 && <div className="text-sm text-gray-500">Loading…</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-gray-100 bg-gray-50 p-2">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
