import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CATALOG, skuToProduct, type Product } from "@/lib/catalog";
import { useSession } from "@/state/session";
import {
  initiateReturn, submitReturn, p2pChoice, p2pQuote, p2pAccept,
} from "@/api/client";
import type { Question, SubmitResponse, PriceQuote, PickupJob } from "@/types";
import HealthCard from "@/components/HealthCard";
import { Price } from "@/components/ui";

type Step = "select" | "questions" | "grading" | "result";

export default function ReturnWizard() {
  const { sku } = useParams();
  const { persona } = useSession();
  const [product, setProduct] = useState<Product>(
    (sku && skuToProduct(sku)) || CATALOG[0]);
  const [step, setStep] = useState<Step>("select");
  const [returnId, setReturnId] = useState<string>("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [connected, setConnected] = useState(false);
  const [result, setResult] = useState<SubmitResponse | null>(null);
  const [quote, setQuote] = useState<PriceQuote | null>(null);
  const [pickup, setPickup] = useState<PickupJob | null>(null);
  const [choice, setChoice] = useState<"pending" | "p2p" | "standard">("pending");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (sku) { const p = skuToProduct(sku); if (p) setProduct(p); }
  }, [sku]);

  const reset = () => {
    setStep("select"); setReturnId(""); setQuestions([]); setAnswers({});
    setResult(null); setQuote(null); setPickup(null); setChoice("pending"); setError("");
  };

  const start = async () => {
    setBusy(true); setError("");
    try {
      const res = await initiateReturn({
        order_id: `ORD-${Date.now()}`,
        product_id: product.sku_id,
        customer_id: persona.customer_id,
        category: product.category,
      });
      setReturnId(res.return_id);
      setQuestions(res.questions);
      // default each answer to first option
      const defaults: Record<string, string> = {};
      res.questions.forEach((q) => { defaults[q.id] = q.options[0]; });
      setAnswers(defaults);
      setStep("questions");
    } catch (e) {
      setError(`Could not start return: ${String((e as Error).message)}`);
    } finally { setBusy(false); }
  };

  const submit = async () => {
    setBusy(true); setError(""); setStep("grading");
    try {
      const res = await submitReturn(returnId, {
        qa_answers: answers,
        image_uris: ["s3://uploads/item.jpg"],
        catalog_metadata: {
          category: product.category,
          original_price: product.price,
          purchase_date: "2026-05-20",
          warranty_remaining_months: product.category === "Electronics" ? 6 : 0,
        },
        connected_accounts: connected ? ["instagram", "facebook"] : [],
      });
      setResult(res);
      setStep("result");
      // auto-quote when graded resell or P2P divert is on the table
      if (!res.p2p_divert_offered && res.health_card.disposition === "resell") {
        void fetchQuote();
      }
    } catch (e) {
      setError(`Grading failed: ${String((e as Error).message)}`);
      setStep("questions");
    } finally { setBusy(false); }
  };

  const fetchQuote = async () => {
    try {
      const q = await p2pQuote({
        sku_id: product.sku_id,
        category: product.category === "Electronics" ? "electronics" : "fashion",
        original_price: product.original_price,
        age_months: 6,
        brand_tier: "standard",
        has_box: true,
        accessories_complete: true,
        media_refs: [],
        health_card: result?.health_card ?? undefined,
      });
      setQuote(q);
    } catch { /* best-effort */ }
  };

  const choose = async (p2p: boolean) => {
    setBusy(true);
    try {
      await p2pChoice(returnId, p2p);
      setChoice(p2p ? "p2p" : "standard");
      if (p2p) {
        await fetchQuote();
        const job = await p2pAccept(product.sku_id);
        setPickup(job);
      }
    } catch (e) {
      setError(String((e as Error).message));
    } finally { setBusy(false); }
  };

  const steps = ["Item", "Condition Q&A", "AI Grading", "Decision"];
  const stepIndex = { select: 0, questions: 1, grading: 2, result: 3 }[step];

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <Stepper steps={steps} active={stepIndex} />

      {error && <div className="card p-3 text-sm text-red-700 bg-red-50 border-red-200">{error}</div>}

      {step === "select" && (
        <div className="card p-5 space-y-4">
          <h1 className="text-lg font-bold">Return or resell an item</h1>
          <p className="text-sm text-gray-600">
            Returning as <b>{persona.name}</b>. Pick the item and we'll collect a few details,
            grade it with AI, and route it to its best second life.
          </p>
          <div className="grid sm:grid-cols-2 gap-2">
            {CATALOG.filter((p) => !p.renewed).map((p) => (
              <button key={p.sku_id}
                onClick={() => setProduct(p)}
                className={`text-left card p-3 flex items-center gap-3 border-2 ${
                  product.sku_id === p.sku_id ? "border-amz-orange" : "border-transparent"}`}>
                <span className="text-3xl">{p.emoji}</span>
                <span>
                  <div className="text-sm line-clamp-1">{p.title}</div>
                  <div className="text-xs text-gray-500">{p.category}</div>
                  <Price value={p.price} />
                </span>
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={connected} onChange={(e) => setConnected(e.target.checked)} />
            Social Connect linked (enables wardrobing fraud check for Clothing &amp; Footwear)
          </label>
          <button className="btn-amz-orange" onClick={start} disabled={busy}>
            {busy ? "Starting…" : "Start return"}
          </button>
        </div>
      )}

      {step === "questions" && (
        <div className="card p-5 space-y-4">
          <h1 className="text-lg font-bold">Tell us about the {product.title}</h1>
          <p className="text-xs text-gray-500">Return ID {returnId} · structured Q&A feeds the AI grader</p>
          <div className="space-y-4">
            {questions.map((q) => (
              <div key={q.id}>
                <div className="text-sm font-medium mb-1">{q.text}</div>
                <div className="flex flex-wrap gap-2">
                  {q.options.map((opt) => (
                    <button key={opt}
                      onClick={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                      className={`text-xs px-2.5 py-1 rounded-full border ${
                        answers[q.id] === opt
                          ? "bg-amz-navy text-white border-amz-navy"
                          : "bg-white border-gray-300 hover:border-amz-orange"}`}>
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={() => setStep("select")}>Back</button>
            <button className="btn-amz-orange" onClick={submit} disabled={busy}>
              Submit for AI grading
            </button>
          </div>
        </div>
      )}

      {step === "grading" && (
        <div className="card p-10 text-center space-y-3">
          <div className="text-4xl animate-pulse">🔍</div>
          <div className="font-medium">Grading in progress…</div>
          <div className="text-sm text-gray-500">
            Anomaly detection · wear analysis · Q&A intent · fraud check — target &lt; 2s
          </div>
        </div>
      )}

      {step === "result" && result && (
        <div className="space-y-4">
          <HealthCard card={result.health_card} />

          {result.p2p_divert_offered && choice === "pending" && (
            <div className="card p-5 border-2 border-amz-orange space-y-3">
              <h2 className="font-bold">We noticed this item may have been used</h2>
              <p className="text-sm text-gray-700">
                Instead of a standard return, would you like to resell it directly to another
                customer? You'll receive Green Credits + a partial refund equal to the resale value.
              </p>
              <div className="flex gap-2">
                <button className="btn-amz-orange" disabled={busy} onClick={() => choose(true)}>
                  Resell via ReLoop P2P
                </button>
                <button className="btn-ghost" disabled={busy} onClick={() => choose(false)}>
                  Proceed with standard return inspection
                </button>
              </div>
            </div>
          )}

          {choice === "standard" && (
            <div className="card p-4 text-sm bg-gray-50">
              Standard return inspection scheduled. Item flagged for enhanced inspection.
            </div>
          )}

          {quote && (
            <div className="card p-5 space-y-2">
              <h2 className="font-bold flex items-center gap-2">
                <span className="text-amz-green">₹</span> P2P resale quote
                <span className="text-xs text-gray-400">({quote.model})</span>
              </h2>
              <div className="flex items-end gap-4">
                <div>
                  <div className="text-xs text-gray-500">You receive (net)</div>
                  <div className="text-2xl font-bold text-amz-green">₹{quote.net_payout.toLocaleString()}</div>
                </div>
                <div className="text-sm text-gray-600">
                  gross ₹{quote.gross_price.toLocaleString()} − fee ₹{quote.fee.toLocaleString()}
                  <br />range ₹{quote.low.toLocaleString()}–₹{quote.high.toLocaleString()} · conf {(quote.confidence * 100).toFixed(0)}%
                </div>
              </div>
              <ul className="text-xs text-gray-600 list-disc pl-5">
                {quote.reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
              {pickup && (
                <div className="text-sm text-amz-green bg-emerald-50 border border-emerald-200 rounded p-2">
                  ✓ Courier pickup scheduled — job {String(pickup.job_id).slice(0, 8)} · {pickup.status}
                </div>
              )}
            </div>
          )}

          <button className="btn-ghost" onClick={reset}>Start another return</button>
        </div>
      )}
    </div>
  );
}

function Stepper({ steps, active }: { steps: string[]; active: number }) {
  return (
    <ol className="flex items-center gap-2 text-sm">
      {steps.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
            i <= active ? "bg-amz-orange text-[#0f1111]" : "bg-gray-200 text-gray-500"}`}>
            {i + 1}
          </span>
          <span className={i <= active ? "font-medium" : "text-gray-400"}>{s}</span>
          {i < steps.length - 1 && <span className="text-gray-300">›</span>}
        </li>
      ))}
    </ol>
  );
}
