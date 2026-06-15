import { useEffect, useMemo, useState } from "react";
import { useSession } from "@/state/session";
import { getRecommend } from "@/api/client";
import type { Feed as FeedT } from "@/types";
import { CATALOG, skuToProduct, type Product } from "@/lib/catalog";
import ProductCard from "@/components/ProductCard";

interface Rec { product: Product; reasons?: string[] }

// Local fallback so "For You" / Cart recommendations always render, even when
// the recommend service (Module 2) is unavailable or returns no usable items.
function localRecommendations(limit = 8): Rec[] {
  const renewed = CATALOG.filter((p) => p.renewed);
  const fresh = CATALOG.filter((p) => !p.renewed);
  const ordered = [...renewed, ...fresh];
  return ordered.slice(0, limit).map((product) => ({
    product,
    reasons: product.renewed
      ? ["Certified Renewed pick", "Great value — second-life supply", "Earn Green Coin"]
      : ["Popular right now", "Frequently bought", "Top rated"],
  }));
}

export default function Feed() {
  const { persona } = useSession();
  const [feed, setFeed] = useState<FeedT | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getRecommend(persona.recommend_user_id, 8)
      .then((f) => { if (alive) setFeed(f); })
      .catch(() => { if (alive) setFeed(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [persona.recommend_user_id]);

  // Map API feed items to catalog products; fall back to local picks if the API
  // returned nothing displayable.
  const apiRecs = useMemo<Rec[]>(() => {
    return (feed?.items ?? [])
      .map((item): Rec | null => {
        const product = skuToProduct(item.sku_id);
        return product ? { product, reasons: item.reasons } : null;
      })
      .filter((r): r is Rec => r !== null);
  }, [feed]);

  const recs = apiRecs.length ? apiRecs : localRecommendations();
  const showingFallback = !loading && apiRecs.length === 0;

  return (
    <div className="space-y-4">
      <div className="card p-5 bg-gradient-to-r from-amz-slate to-amz-navy text-white">
        <h1 className="text-xl font-bold">Recommended for {persona.name}</h1>
      </div>

      {loading && <div className="card p-6">Loading recommendations…</div>}

      {!loading && showingFallback && (
        <div className="card p-3 text-xs text-gray-600 bg-amber-50 border-amber-200">
          Showing curated picks. Live personalised ranking is unavailable right now.
        </div>
      )}

      {!loading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {recs.map(({ product, reasons }) => (
            <ProductCard key={product.sku_id} product={product} reasons={reasons} />
          ))}
        </div>
      )}
    </div>
  );
}
