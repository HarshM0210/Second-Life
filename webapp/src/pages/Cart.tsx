import { Link } from "react-router-dom";
import { CATALOG, type Product } from "@/lib/catalog";
import { Price, RenewedBadge } from "@/components/ui";
import ProductCard from "@/components/ProductCard";
import { useCart } from "@/state/cart";

// Recommendations must include BOTH new and renewed items: take a few of each,
// excluding whatever is already in the cart.
function mixedRecommendations(excludeSkus: Set<string>, perType = 2): Product[] {
  const avail = (renewed: boolean) =>
    CATALOG.filter((p) => p.renewed === renewed && !excludeSkus.has(p.sku_id)).slice(0, perType);
  return [...avail(false), ...avail(true)];
}

export default function Cart() {
  const { lines, subtotal, count, removeItem } = useCart();
  const inCart = new Set(lines.map((l) => l.product.sku_id));
  const recommendations = mixedRecommendations(inCart);

  return (
    <div className="space-y-6">
      {/* Section 1: items in cart */}
      <section>
        <div className="card p-5 flex flex-col md:flex-row gap-6">
          <div className="flex-1">
            <h1 className="text-xl font-bold mb-3">Shopping Cart</h1>
            {lines.length === 0 ? (
              <div className="text-sm text-gray-600">
                Your cart is empty. <Link to="/" className="link-amz">Continue shopping</Link>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {lines.map(({ product: p, qty }) => (
                  <div key={p.sku_id} className="flex items-center gap-4 py-3">
                    <Link to={`/product/${p.sku_id}`}
                      className="h-20 w-20 flex items-center justify-center text-4xl bg-gray-50 rounded shrink-0">
                      {p.emoji}
                    </Link>
                    <div className="flex-1 min-w-0">
                      <Link to={`/product/${p.sku_id}`} className="text-sm font-medium hover:text-amz-link line-clamp-2">
                        {p.title}
                      </Link>
                      <div className="mt-1 flex items-center gap-2">
                        <Price value={p.price} original={p.original_price} />
                        {p.renewed && <RenewedBadge />}
                      </div>
                      <div className="text-xs text-amz-green mt-0.5">In stock · Eligible for FREE delivery</div>
                      <button onClick={() => removeItem(p.sku_id)}
                        className="text-xs text-amz-link hover:underline mt-1">
                        Remove
                      </button>
                    </div>
                    <div className="text-xs text-gray-500">Qty: {qty}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Subtotal box */}
          <div className="card p-4 h-fit w-full md:w-64 space-y-3 bg-white">
            <div className="text-sm">
              Subtotal ({count} {count === 1 ? "item" : "items"}):{" "}
              <span className="font-bold"><Price value={subtotal} /></span>
            </div>
            <button className="btn-amz-orange w-full" disabled={lines.length === 0}>Proceed to Buy</button>
            <div className="text-[11px] text-gray-500">Earn Green Coin on Renewed items in your cart.</div>
          </div>
        </div>
      </section>

      {/* Section 2: recommendations (new + renewed) */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold">Recommended for you — New &amp; Renewed</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {recommendations.map((p) => (
            <ProductCard key={p.sku_id} product={p} />
          ))}
        </div>
      </section>
    </div>
  );
}
