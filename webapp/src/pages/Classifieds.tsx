import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CATALOG } from "@/lib/catalog";
import { encodeImage } from "@/lib/image";
import {
  CLASSIFIEDS_QUESTIONS,
  toGradingAnswers,
  deriveListingMeta,
  type CQuestion,
} from "@/lib/classifiedsQuestions";
import { useSession } from "@/state/session";
import { useClassifieds } from "@/state/classifieds";
import {
  initiateReturn,
  submitReturn,
  p2pQuote,
  p2pAccept,
} from "@/api/client";
import type { SubmitResponse, PriceQuote, PickupJob } from "@/types";
import ProductCard from "@/components/ProductCard";
import ListingCard from "@/components/ListingCard";
import HealthCard from "@/components/HealthCard";

type Tab = "browse" | "sell";
type Step = "details" | "questions" | "grading" | "quote" | "listed";

const MAX_IMAGES = 5;

// Seller-facing categories. Each maps to a Module 1 grading category (drives the
// condition Q&A + return-window logic) and a Module 5 pricing category (drives
// demand / depreciation in the quote).
const CATEGORIES: { label: string; m1: string; m5: string; emoji: string }[] = [
  { label: "Clothing & Footwear", m1: "Clothing & Footwear", m5: "fashion", emoji: "👕" },
  { label: "Electronics", m1: "Electronics", m5: "electronics", emoji: "🔌" },
  { label: "Home & Other", m1: "Other", m5: "kitchen", emoji: "🏠" },
];

const BRAND_TIERS = [
  { value: "premium", label: "Premium (e.g. Sony, Levi's, Apple)" },
  { value: "standard", label: "Standard" },
  { value: "value", label: "Value / unbranded" },
];

function isoDateMonthsAgo(months: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - Math.max(0, months));
  return d.toISOString().slice(0, 10);
}

export default function Classifieds() {
  const { persona } = useSession();
  const { listings, addListing } = useClassifieds();
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get("tab") === "sell" ? "sell" : "browse";
  const setTab = (t: Tab) => setParams(t === "sell" ? { tab: "sell" } : {});

  const renewed = CATALOG.filter((p) => p.renewed);

  return (
    <div className="space-y-4">
      {/* Hero */}
      <div className="card overflow-hidden">
        <div className="bg-gradient-to-r from-amz-navy to-amz-slate text-white p-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Classifieds — community resale, certified by AI</h1>
            <p className="text-gray-300 text-sm mt-1 max-w-2xl">
              Buy Renewed and peer-to-peer items from the Second Life community, or list your own.
              Every listing is graded by our AI (Module 1 Health Card) and priced fairly by our
              resale model (Module 5) — so condition and price are always transparent. 🤝♻
            </p>
          </div>
          <div className="hidden md:block text-6xl">🏷️</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        <TabButton active={tab === "browse"} onClick={() => setTab("browse")}>
          Browse Renewed & P2P
        </TabButton>
        <TabButton active={tab === "sell"} onClick={() => setTab("sell")}>
          Sell your item
        </TabButton>
      </div>

      {tab === "browse" ? (
        <BrowseView renewed={renewed} listings={listings} onSell={() => setTab("sell")} />
      ) : (
        <SellWizard
          persona={persona}
          onListed={(l) => {
            addListing(l);
          }}
          goBrowse={() => setTab("browse")}
        />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 ${
        active
          ? "border-amz-orange text-[#0f1111]"
          : "border-transparent text-gray-500 hover:text-[#0f1111]"
      }`}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Browse
// ---------------------------------------------------------------------------

function BrowseView({
  renewed,
  listings,
  onSell,
}: {
  renewed: typeof CATALOG;
  listings: ReturnType<typeof useClassifieds>["listings"];
  onSell: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="card p-4 flex items-center justify-between bg-amz-green/5 border-amz-green/30">
        <div className="text-sm text-gray-700">
          Got something to sell? Get an instant AI grade + fair price and list it in minutes.
        </div>
        <button className="btn-amz-orange" onClick={onSell}>
          Sell your item
        </button>
      </div>

      {/* Community P2P listings */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Community resale (P2P)</h2>
          <span className="text-xs text-gray-500">{listings.length} listings</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {listings.map((l) => (
            <ListingCard key={l.id} listing={l} />
          ))}
        </div>
      </section>

      {/* Certified Renewed inventory */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Certified Renewed</h2>
          <span className="text-xs text-gray-500">{renewed.length} items</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {renewed.map((p) => (
            <ProductCard key={p.sku_id} product={p} />
          ))}
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sell wizard
// ---------------------------------------------------------------------------

function SellWizard({
  persona,
  onListed,
  goBrowse,
}: {
  persona: ReturnType<typeof useSession>["persona"];
  onListed: (l: Parameters<ReturnType<typeof useClassifieds>["addListing"]>[0]) => void;
  goBrowse: () => void;
}) {
  const [step, setStep] = useState<Step>("details");

  // Item details
  const [title, setTitle] = useState("");
  const [catIndex, setCatIndex] = useState(0);
  const [brand, setBrand] = useState("");
  const [brandTier, setBrandTier] = useState("standard");
  const [originalPrice, setOriginalPrice] = useState<number>(0);
  const [images, setImages] = useState<File[]>([]);
  const [imageUrls, setImageUrls] = useState<string[]>([]);

  // Flow state
  const [productId, setProductId] = useState("");
  const [returnId, setReturnId] = useState("");
  const [questions, setQuestions] = useState<CQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [meta, setMeta] = useState<ReturnType<typeof deriveListingMeta> | null>(null);
  const [result, setResult] = useState<SubmitResponse | null>(null);
  const [quote, setQuote] = useState<PriceQuote | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [pickup, setPickup] = useState<PickupJob | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const cat = CATEGORIES[catIndex];

  useEffect(() => {
    const urls = images.map((f) => URL.createObjectURL(f));
    setImageUrls(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [images]);

  const reset = () => {
    setStep("details");
    setTitle(""); setCatIndex(0); setBrand(""); setBrandTier("standard");
    setOriginalPrice(0);
    setImages([]); setProductId(""); setReturnId(""); setQuestions([]); setAnswers({});
    setMeta(null);
    setResult(null); setQuote(null); setPreview(""); setPickup(null); setError("");
  };

  const start = async () => {
    if (!title.trim()) { setError("Please enter a title for your item."); return; }
    if (!(originalPrice > 0)) { setError("Please enter the original price (₹)."); return; }
    setBusy(true); setError("");
    const pid = `P2P-${Date.now().toString(36).toUpperCase()}`;
    setProductId(pid);
    try {
      const res = await initiateReturn({
        order_id: `LISTING-${Date.now()}`,
        product_id: pid,
        customer_id: persona.customer_id,
        category: cat.m1,
      });
      setReturnId(res.return_id);
      // Classifieds uses its OWN seller question set (Questions.md), not the
      // return Q&A that `initiate` returns — we only need the session/return_id.
      const cqs = CLASSIFIEDS_QUESTIONS[cat.m1] ?? [];
      setQuestions(cqs);
      const defaults: Record<string, string> = {};
      cqs.forEach((q) => {
        defaults[q.id] = q.kind === "radio" ? (q.options?.[0] ?? "") : "";
      });
      setAnswers(defaults);
      setStep("questions");
    } catch (e) {
      setError(`Could not start listing: ${String((e as Error).message)}`);
    } finally {
      setBusy(false);
    }
  };

  const grade = async () => {
    setBusy(true); setError(""); setStep("grading");
    try {
      const encoded = images.length
        ? (await Promise.all(images.slice(0, MAX_IMAGES).map((f) => encodeImage(f)))).filter(Boolean)
        : [];
      const imageUris = encoded.length ? encoded : ["s3://uploads/listing.jpg"];
      if (encoded.length) setPreview(encoded[0]);

      // Translate the seller's answers into the grade-compatible (return-schema)
      // payload Module 1 understands, and derive the listing/quote metadata.
      const optionsMap = Object.fromEntries(
        questions.map((q) => [q.id, q.options ?? []]),
      ) as Record<string, string[]>;
      const gradingAnswers = toGradingAnswers(cat.m1, answers, optionsMap);
      const derived = deriveListingMeta(cat.m1, answers, optionsMap);
      setMeta(derived);

      const res = await submitReturn(returnId, {
        qa_answers: gradingAnswers,
        image_uris: imageUris,
        video_frame_uris: [],
        catalog_metadata: {
          category: cat.m1,
          original_price: originalPrice,
          purchase_date: isoDateMonthsAgo(derived.ageMonths),
          warranty_remaining_months:
            cat.m1 === "Electronics" ? Math.max(0, 12 - derived.ageMonths) : 0,
        },
        connected_accounts: [],
      });
      setResult(res);

      // Price the item with Module 5 using the Health Card we just earned.
      const q = await p2pQuote({
        sku_id: productId,
        category: cat.m5,
        original_price: originalPrice,
        age_months: derived.ageMonths,
        brand_tier: brandTier,
        has_box: derived.hasBox,
        accessories_complete: derived.accessoriesComplete,
        media_refs: [],
        health_card: res.health_card,
      });
      setQuote(q);
      setStep("quote");
    } catch (e) {
      setError(`AI grading failed: ${String((e as Error).message)}`);
      setStep("questions");
    } finally {
      setBusy(false);
    }
  };

  const list = async () => {
    if (!result || !quote) return;
    setBusy(true); setError("");
    try {
      let job: PickupJob | null = null;
      try {
        job = await p2pAccept(productId);
      } catch {
        /* pickup scheduling is best-effort for the demo */
      }
      setPickup(job);
      onListed({
        title: title.trim(),
        emoji: cat.emoji,
        category: cat.m1,
        brand: (meta?.brand ?? brand.trim()) || "Unbranded",
        seller: persona.name,
        original_price: originalPrice,
        age_months: meta?.ageMonths ?? 6,
        health_card: result.health_card,
        quote,
        health_score: result.health_card.health_score,
        condition: result.health_card.condition,
        ask_price: quote.gross_price,
        preview: preview || undefined,
        mine: true,
      });
      setStep("listed");
    } catch (e) {
      setError(`Could not publish listing: ${String((e as Error).message)}`);
    } finally {
      setBusy(false);
    }
  };

  const steps = ["Details", "Condition Q&A", "AI Grading", "Price & List"];
  const stepIndex = { details: 0, questions: 1, grading: 2, quote: 3, listed: 3 }[step];

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <Stepper steps={steps} active={stepIndex} />

      {error && (
        <div className="card p-3 text-sm text-red-700 bg-red-50 border-red-200">{error}</div>
      )}

      {step === "details" && (
        <div className="card p-5 space-y-4">
          <h2 className="text-lg font-bold">List an item for resale</h2>
          <p className="text-sm text-gray-600">
            Listing as <b>{persona.name}</b>. Tell us about your item — we'll grade it with AI and
            suggest a fair resale price.
          </p>

          <Field label="Title">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Nike Revolution Running Shoes (Size 8)"
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-amz-orange"
            />
          </Field>

          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Category">
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((c, i) => (
                  <button
                    key={c.label}
                    onClick={() => setCatIndex(i)}
                    className={`text-xs px-2.5 py-1 rounded-full border ${
                      catIndex === i
                        ? "bg-amz-navy text-white border-amz-navy"
                        : "bg-white border-gray-300 hover:border-amz-orange"
                    }`}
                  >
                    {c.emoji} {c.label}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Brand">
              <input
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                placeholder="e.g. Nike"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-amz-orange"
              />
            </Field>

            <Field label="Original price (₹)">
              <input
                type="number"
                min={1}
                value={originalPrice || ""}
                onChange={(e) => setOriginalPrice(Number(e.target.value))}
                placeholder="1999"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-amz-orange"
              />
            </Field>

            <Field label="Brand tier (affects resale price)">
              <select
                value={brandTier}
                onChange={(e) => setBrandTier(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-amz-orange"
              >
                {BRAND_TIERS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Photos of the item">
            <p className="text-xs text-gray-500 mb-2">
              Clear photos of the front, back, and any defects let the AI grader (DINOv2 anomaly +
              wear detection) assess condition accurately. Up to {MAX_IMAGES} photos.
            </p>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => setImages(Array.from(e.target.files ?? []).slice(0, MAX_IMAGES))}
              className="block text-sm text-gray-700 file:mr-3 file:rounded-full file:border file:border-gray-300 file:bg-white file:px-3 file:py-1.5 file:text-sm hover:file:bg-gray-50"
            />
            {images.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {images.map((f, i) => (
                  <div key={i} className="w-16 h-16 rounded border border-gray-200 overflow-hidden bg-gray-50">
                    <img src={imageUrls[i]} alt={f.name} className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            )}
          </Field>

          <button className="btn-amz-orange" onClick={start} disabled={busy}>
            {busy ? "Starting…" : "Continue to condition Q&A"}
          </button>
        </div>
      )}

      {step === "questions" && (
        <div className="card p-5 space-y-4">
          <h2 className="text-lg font-bold">Condition details for {title}</h2>
          <p className="text-xs text-gray-500">
            Listing draft {returnId} · structured Q&A feeds the AI grader
          </p>
          <div className="space-y-4">
            {questions.map((q) => (
              <div key={q.id}>
                <div className="text-sm font-medium mb-1">{q.text}</div>
                {q.kind === "radio" ? (
                  <div className="flex flex-wrap gap-2">
                    {(q.options ?? []).map((opt) => (
                      <button
                        key={opt}
                        onClick={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                        className={`text-xs px-2.5 py-1 rounded-full border ${
                          answers[q.id] === opt
                            ? "bg-amz-navy text-white border-amz-navy"
                            : "bg-white border-gray-300 hover:border-amz-orange"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                ) : (
                  <input
                    value={answers[q.id] ?? ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    placeholder={q.note ?? ""}
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-amz-orange"
                  />
                )}
                {q.kind === "radio" && q.note && (
                  <input
                    value={answers[`${q.id}__note`] ?? ""}
                    onChange={(e) =>
                      setAnswers((a) => ({ ...a, [`${q.id}__note`]: e.target.value }))
                    }
                    placeholder={q.note}
                    className="mt-2 w-full border border-gray-200 rounded px-3 py-1.5 text-xs outline-none focus:border-amz-orange"
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={() => setStep("details")}>Back</button>
            <button className="btn-amz-orange" onClick={grade} disabled={busy}>
              Submit for AI grading
            </button>
          </div>
        </div>
      )}

      {step === "grading" && (
        <div className="card p-10 text-center space-y-3">
          <div className="text-4xl animate-pulse">🔍</div>
          <div className="font-medium">Grading your item…</div>
          <div className="text-sm text-gray-500">
            DINOv2 anomaly detection · wear analysis · Q&A intent · resale pricing — target &lt; 2s
          </div>
        </div>
      )}

      {step === "quote" && result && (
        <div className="space-y-4">
          <HealthCard card={result.health_card} />

          {quote && (
            <div className="card p-5 space-y-2">
              <h2 className="font-bold flex items-center gap-2">
                <span className="text-amz-green">₹</span> Suggested resale price
                <span className="text-xs text-gray-400">({quote.model})</span>
              </h2>
              <div className="flex items-end gap-4 flex-wrap">
                <div>
                  <div className="text-xs text-gray-500">List price (gross)</div>
                  <div className="text-2xl font-bold">₹{quote.gross_price.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">You receive (net)</div>
                  <div className="text-2xl font-bold text-amz-green">
                    ₹{quote.net_payout.toLocaleString()}
                  </div>
                </div>
                <div className="text-sm text-gray-600">
                  fee ₹{quote.fee.toLocaleString()}
                  <br />range ₹{quote.low.toLocaleString()}–₹{quote.high.toLocaleString()} · conf{" "}
                  {(quote.confidence * 100).toFixed(0)}%
                </div>
              </div>
              <ul className="text-xs text-gray-600 list-disc pl-5">
                {quote.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex gap-2">
            <button className="btn-ghost" onClick={() => setStep("questions")}>Back</button>
            <button className="btn-amz-orange" onClick={list} disabled={busy || !quote}>
              {busy ? "Publishing…" : "List on Classifieds"}
            </button>
          </div>
        </div>
      )}

      {step === "listed" && (
        <div className="card p-6 text-center space-y-4">
          <div className="text-5xl">🎉</div>
          <h2 className="text-lg font-bold">Your item is live on Classifieds</h2>
          <p className="text-sm text-gray-600">
            <b>{title}</b> is now listed at ₹{quote?.gross_price.toLocaleString()} — AI-graded and
            certified for buyers across the Second Life community.
          </p>
          {pickup && (
            <div className="text-sm text-amz-green bg-emerald-50 border border-emerald-200 rounded p-2 inline-block">
              ✓ Courier pickup scheduled — job {String(pickup.job_id).slice(0, 8)} · {pickup.status}
            </div>
          )}
          <div className="flex gap-2 justify-center">
            <button className="btn-amz-orange" onClick={goBrowse}>View in Browse</button>
            <button className="btn-ghost" onClick={reset}>List another item</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}

function Stepper({ steps, active }: { steps: string[]; active: number }) {
  return (
    <ol className="flex items-center gap-2 text-sm flex-wrap">
      {steps.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span
            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
              i <= active ? "bg-amz-orange text-[#0f1111]" : "bg-gray-200 text-gray-500"
            }`}
          >
            {i + 1}
          </span>
          <span className={i <= active ? "font-medium" : "text-gray-400"}>{s}</span>
          {i < steps.length - 1 && <span className="text-gray-300">›</span>}
        </li>
      ))}
    </ol>
  );
}
