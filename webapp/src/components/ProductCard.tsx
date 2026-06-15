import { Link } from "react-router-dom";
import type { Product } from "@/lib/catalog";
import { Price, RenewedBadge, Stars } from "@/components/ui";
import { useCart } from "@/state/cart";

export default function ProductCard({ product, reasons }: { product: Product; reasons?: string[] }) {
  const { addItem } = useCart();
  return (
    <div className="card p-3 flex flex-col hover:shadow-lg transition-shadow">
      <Link to={`/product/${product.sku_id}`} className="block">
        <div className="h-36 flex items-center justify-center text-6xl bg-gray-50 rounded mb-2">
          {product.emoji}
        </div>
        <div className="text-sm text-[#0f1111] line-clamp-2 hover:text-amz-link min-h-[2.5rem]">
          {product.title}
        </div>
      </Link>
      <div className="mt-1 flex items-center gap-2">
        <Stars rating={product.rating} reviews={product.reviews} />
      </div>
      <div className="mt-1 flex items-center gap-2">
        <Price value={product.price} original={product.original_price} />
        {product.renewed && <RenewedBadge />}
      </div>
      {product.renewed && product.health_score && (
        <div className="text-xs text-amz-green mt-0.5">Health score {product.health_score}/100 · Certified by Amazon AI</div>
      )}
      {reasons && reasons.length > 0 && (
        <ul className="mt-1.5 text-xs text-gray-600 space-y-0.5">
          {reasons.slice(0, 3).map((r, i) => (
            <li key={i} className="flex gap-1"><span className="text-amz-orange">›</span>{r}</li>
          ))}
        </ul>
      )}
      <div className="mt-auto pt-2 flex gap-2">
        <Link to={`/product/${product.sku_id}`} className="btn-ghost text-center flex-1">View</Link>
        <button onClick={() => addItem(product)} className="btn-amz flex-1"
          aria-label={`Add ${product.title} to cart`}>
          Add to cart
        </button>
      </div>
    </div>
  );
}
