import { Link } from "react-router-dom";
import type { Listing } from "@/state/classifieds";
import { ConditionBadge } from "@/components/ui";
import { useCart } from "@/state/cart";

function timeAgo(ts: number): string {
  const mins = Math.round((Date.now() - ts) / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export default function ListingCard({ listing }: { listing: Listing }) {
  const { addItem } = useCart();
  const savings =
    listing.original_price > listing.ask_price
      ? Math.round((1 - listing.ask_price / listing.original_price) * 100)
      : 0;

  return (
    <div className="card p-3 flex flex-col hover:shadow-lg transition-shadow">
      <div className="relative h-36 flex items-center justify-center bg-gray-50 rounded mb-2 overflow-hidden">
        {listing.preview ? (
          <img
            src={listing.preview}
            alt={listing.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <span className="text-6xl">{listing.emoji}</span>
        )}
        <span className="absolute top-1 left-1 pill bg-amz-navy/90 text-white text-[10px]">
          P2P
        </span>
        {listing.mine && (
          <span className="absolute top-1 right-1 pill bg-amz-orange text-[#0f1111] text-[10px]">
            Your listing
          </span>
        )}
      </div>

      <div className="text-sm text-[#0f1111] line-clamp-2 min-h-[2.5rem]">
        {listing.title}
      </div>

      <div className="mt-1 flex items-center gap-2 flex-wrap">
        {listing.condition && <ConditionBadge condition={listing.condition} />}
        {typeof listing.health_score === "number" && (
          <span className="text-xs text-amz-green">
            Health {listing.health_score}/100
          </span>
        )}
      </div>

      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-lg font-medium text-[#0f1111]">
          <span className="text-xs align-top">₹</span>
          {listing.ask_price.toLocaleString()}
        </span>
        {listing.original_price > listing.ask_price && (
          <span className="text-xs text-gray-500 line-through">
            ₹{listing.original_price.toLocaleString()}
          </span>
        )}
        {savings > 0 && (
          <span className="text-xs text-amz-price font-medium">
            -{savings}%
          </span>
        )}
      </div>

      <div className="mt-1 text-xs text-gray-500">
        Sold by <b className="text-gray-700">{listing.seller}</b> ·{" "}
        {listing.brand} · {timeAgo(listing.created_at)}
      </div>
      <div className="text-[11px] text-amz-green mt-0.5">
        ✓ AI-graded · Certified by Amazon AI
      </div>

      <div className="mt-auto pt-2 flex gap-2">
        <Link
          to={`/product/${listing.id}`}
          className="btn-ghost text-center flex-1"
        >
          View
        </Link>
        <button
          onClick={() =>
            addItem({
              sku_id: listing.id,
              title: listing.title,
              emoji: listing.emoji,
              category: listing.category,
              subcategory: listing.category,
              brand: listing.brand,
              price: listing.ask_price,
              original_price: listing.original_price,
              rating: 0,
              reviews: 0,
              renewed: false,
              blurb: listing.condition
                ? `Community resale · ${listing.condition} condition`
                : "Community resale listing",
              health_score: listing.health_score,
            })
          }
          className="btn-amz flex-1"
          aria-label={`Add ${listing.title} to cart`}
        >
          Add to cart
        </button>
      </div>
    </div>
  );
}
