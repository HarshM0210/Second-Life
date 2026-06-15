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
            <h1 className="text-2xl font-bold">Second Life — shop new, buy renewed, waste nothing</h1>
            <p className="text-gray-300 text-sm mt-1 max-w-xl">
              Your everyday store with a conscience. Buy brand-new items just like always —
              or grab Certified Renewed returns that are AI-graded, health-scored, and up to 60% off.
              Every order earns Green Coin and gives a great product a second life. 🌍
            </p>
          </div>
          <div className="hidden md:block text-6xl">🛍️</div>
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
