import { useEffect, useState } from "react";
import { useSession } from "@/state/session";
import { getRecommend } from "@/api/client";
import type { Feed as FeedT } from "@/types";
import { skuToProduct } from "@/lib/catalog";
import ProductCard from "@/components/ProductCard";

export default function Feed() {
  const { persona } = useSession();
  const [feed, setFeed] = useState<FeedT | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getRecommend(persona.recommend_user_id, 8)
      .then((f) => { if (alive) { setFeed(f); setErr(""); } })
      .catch(() => { if (alive) setErr("Could not load recommendations."); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [persona.recommend_user_id]);

  return (
    <div className="space-y-4">
      <div className="card p-5 bg-gradient-to-r from-amz-slate to-amz-navy text-white">
        <h1 className="text-xl font-bold">Recommended for {persona.name}</h1>
        <p className="text-sm text-gray-300 mt-1">
          Personalised mix of New &amp; Renewed — refurbished supply injected into the same ranking,
          boosted by Health Card score (Module 2).
        </p>
      </div>

      {loading && <div className="card p-6">Loading recommendations…</div>}
      {err && <div className="card p-6 text-red-700">{err}</div>}

      {feed && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {feed.items.map((item) => {
            const product = skuToProduct(item.sku_id);
            if (!product) return null;
            return <ProductCard key={item.sku_id} product={product} reasons={item.reasons} />;
          })}
        </div>
      )}
    </div>
  );
}
