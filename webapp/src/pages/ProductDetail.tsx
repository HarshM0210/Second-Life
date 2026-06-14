import { useEffect, useRef, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { skuToProduct } from "@/lib/catalog";
import { Price, Stars, RenewedBadge } from "@/components/ui";
import { getRiskScore } from "@/api/client";
import type { RiskResponse } from "@/types";
import { useSession } from "@/state/session";

function RiskBanner({ risk }: { risk: RiskResponse }) {
  if (risk.taxonomy_miss || !risk.intervention_copy) return null;
  const high = risk.risk_score >= 0.6;
  return (
    <div className={`rounded-md border p-3 text-sm flex gap-3 ${
      high ? "bg-amber-50 border-amber-300" : "bg-blue-50 border-blue-200"}`}>
      <span className="text-xl">{high ? "💡" : "ℹ️"}</span>
      <div>
        <div className="font-semibold text-[#0f1111]">
          {risk.intervention_type?.replace(/_/g, " ")} · best return = no return
        </div>
        <div className="text-gray-700">{risk.intervention_copy}</div>
        <div className="text-xs text-gray-400 mt-1">
          Return-risk score {(risk.risk_score * 100).toFixed(0)}% · powered by Return Prevention (Module 3)
        </div>
      </div>
    </div>
  );
}

export default function ProductDetail() {
  const { sku } = useParams();
  const product = sku ? skuToProduct(sku) : undefined;
  const { persona } = useSession();
  const navigate = useNavigate();
  const [risk, setRisk] = useState<RiskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const dwellStart = useRef(Date.now());

  useEffect(() => { dwellStart.current = Date.now(); setRisk(null); }, [sku]);

  if (!product) return <div className="card p-6">Product not found. <Link className="link-amz" to="/">Back to shop</Link></div>;

  const checkRisk = async (isBuyNow: boolean) => {
    setLoading(true);
    const dwell = (Date.now() - dwellStart.current) / 1000;
    try {
      const r = await getRiskScore({
        customer_id: persona.customer_id,
        product_id: product.subcategory, // Module 3 keys risk on subcategory
        page_dwell_seconds: dwell,
        is_buy_now: isBuyNow,
        product_price: product.price,
        product_review_rating: product.rating,
        is_sale_active: product.renewed,
      });
      setRisk(r);
    } catch {
      setRisk(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <Link to="/" className="link-amz text-sm">‹ Back to results</Link>
      <div className="card p-5 grid md:grid-cols-[320px_1fr_300px] gap-6">
        {/* Image */}
        <div className="h-72 flex items-center justify-center text-[8rem] bg-gray-50 rounded">
          {product.emoji}
        </div>

        {/* Details */}
        <div className="space-y-3">
          <h1 className="text-xl font-medium">{product.title}</h1>
          <div className="flex items-center gap-2">
            <Stars rating={product.rating} reviews={product.reviews} />
            {product.renewed && <RenewedBadge />}
          </div>
          <hr />
          <Price value={product.price} original={product.original_price} />
          {product.renewed && product.health_score && (
            <div className="text-sm text-amz-green">
              ♻ Certified Renewed · Health score {product.health_score}/100 · Certified by Amazon AI
            </div>
          )}
          <p className="text-sm text-gray-700">{product.blurb}</p>
          <ul className="text-sm text-gray-700 list-disc pl-5 space-y-0.5">
            <li>Brand: <b>{product.brand}</b></li>
            <li>Category: {product.category} · {product.subcategory}</li>
            <li>FREE delivery · A-to-Z Guarantee · Earn Green Coin on Renewed</li>
          </ul>
          {risk && <RiskBanner risk={risk} />}
        </div>

        {/* Buy box */}
        <div className="card p-4 h-fit space-y-3 bg-white">
          <Price value={product.price} original={product.original_price} />
          <div className="text-sm text-amz-green">In stock</div>
          <button className="btn-amz w-full" disabled={loading}
            onClick={() => checkRisk(false)}>
            {loading ? "Checking fit…" : "Add to Cart"}
          </button>
          <button className="btn-amz-orange w-full" disabled={loading}
            onClick={() => checkRisk(true)}>
            Buy Now
          </button>
          <div className="text-[11px] text-gray-500">
            Clicking runs Module 3 return-risk scoring (dwell-aware) before checkout.
          </div>
          <hr />
          <button className="btn-ghost w-full"
            onClick={() => navigate(`/returns/${product.sku_id}`)}>
            Return / Resell this item
          </button>
        </div>
      </div>
    </div>
  );
}
