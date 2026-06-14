import { useSearchParams } from "react-router-dom";
import { CATALOG } from "@/lib/catalog";
import ProductCard from "@/components/ProductCard";

export default function Shop() {
  const [params] = useSearchParams();
  const q = (params.get("q") ?? "").toLowerCase();
  const items = q
    ? CATALOG.filter((p) =>
        `${p.title} ${p.brand} ${p.subcategory}`.toLowerCase().includes(q))
    : CATALOG;

  return (
    <div className="space-y-4">
      {/* Hero band */}
      <div className="card overflow-hidden">
        <div className="bg-gradient-to-r from-amz-navy to-amz-slate text-white p-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">The Renewed Store</h1>
            <p className="text-gray-300 text-sm mt-1 max-w-xl">
              Every returned item is graded by AI, given a Product Health Card, and routed to its
              best second life. Buy Renewed, earn Green Coin.
            </p>
          </div>
          <div className="hidden md:block text-6xl">♻️</div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">
          {q ? `Results for “${q}”` : "Featured — New & Renewed"}
        </h2>
        <span className="text-xs text-gray-500">{items.length} items</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {items.map((p) => <ProductCard key={p.sku_id} product={p} />)}
      </div>
    </div>
  );
}
