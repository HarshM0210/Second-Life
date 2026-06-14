import React, { useEffect, useRef } from "react";
import { useDwellTimer } from "./hooks/useDwellTimer";
import { useRiskScore } from "./hooks/useRiskScore";
import { useBannerSession } from "./hooks/useBannerSession";
import { PdpBanner } from "./PdpBanner/PdpBanner";

/** Minimal product shape for the PDP context. */
interface Product {
  id: string;
  name: string;
  price: number;
  seller_id: string;
  is_sale_active: boolean;
}

/** Minimal user shape for the PDP context. */
interface User {
  id: string;
}

interface ProductDetailPageProps {
  product: Product;
  user: User;
}

/**
 * Placeholder for the actual checkout navigation logic.
 * In a real app this would route to the cart or buy-now checkout flow.
 */
function proceedToCheckout(isBuyNow: boolean): void {
  // Stub — navigation to cart/checkout happens here
  void isBuyNow;
}

/**
 * Product Detail Page component.
 *
 * - Starts a dwell timer on mount to measure time-on-page.
 * - On checkout click, fires a non-blocking risk-score request and proceeds immediately.
 * - Renders <PdpBanner> when the risk-score response contains an intervention
 *   and the banner has not been dismissed this session.
 * - Starts a 30-minute avoidance timer when the banner renders; if the user
 *   has not added to cart by expiry, fires a POST to /api/v1/avoidance-signal.
 */
export const ProductDetailPage: React.FC<ProductDetailPageProps> = ({
  product,
  user,
}) => {
  const getDwell = useDwellTimer();
  const { fireRiskScore, data } = useRiskScore();
  const { isDismissed, dismiss } = useBannerSession();

  /** Tracks whether the user has added to cart during this page session. */
  const hasAddedToCartRef = useRef(false);

  /**
   * Handles both "Add to Cart" and "Buy Now" clicks.
   * Fires risk-score request non-blocking and proceeds to checkout immediately.
   */
  function handleCheckoutClick(isBuyNow: boolean): void {
    const dwellSeconds = getDwell();

    // Fire risk-score request — non-blocking (do NOT await)
    fireRiskScore({
      customer_id: user.id,
      product_id: product.id,
      page_dwell_seconds: dwellSeconds,
      is_buy_now: isBuyNow,
      product_price: product.price,
      seller_id: product.seller_id,
      is_sale_active: product.is_sale_active,
    });

    // Mark that user has added to cart (for avoidance-signal logic)
    hasAddedToCartRef.current = true;

    // Proceed immediately — checkout is never blocked by risk scoring
    proceedToCheckout(isBuyNow);
  }

  // Determine whether the banner should render
  const shouldShowBanner =
    data?.intervention_type != null && !isDismissed(user.id, product.id);

  // 30-minute avoidance timer: fires POST /api/v1/avoidance-signal
  // if user has NOT added to cart after banner is shown.
  useEffect(() => {
    if (!shouldShowBanner) return;

    const THIRTY_MINUTES_MS = 1_800_000;

    const timerId = setTimeout(() => {
      if (!hasAddedToCartRef.current) {
        // Fire-and-forget avoidance signal
        fetch("/api/v1/avoidance-signal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            customer_id: user.id,
            product_id: product.id,
            risk_score: data?.risk_score,
            intervention_type: data?.intervention_type,
          }),
        }).catch(() => {
          // Silent failure — avoidance signal is best-effort
        });
      }
    }, THIRTY_MINUTES_MS);

    return () => clearTimeout(timerId);
  }, [shouldShowBanner, user.id, product.id, data]);

  function handleDismiss(): void {
    dismiss(user.id, product.id);
  }

  return (
    <div>
      {/* Product details would render here */}
      <h1>{product.name}</h1>

      {shouldShowBanner &&
        data?.intervention_type &&
        data?.intervention_copy && (
          <PdpBanner
            interventionType={
              data.intervention_type as
                | "SIZE_GUIDANCE"
                | "SOCIAL_PROOF"
                | "COMPARISON_NUDGE"
                | "CLARIFYING_QA"
            }
            interventionCopy={data.intervention_copy}
            onDismiss={handleDismiss}
          />
        )}

      <button onClick={() => handleCheckoutClick(false)} type="button">
        Add to Cart
      </button>
      <button onClick={() => handleCheckoutClick(true)} type="button">
        Buy Now
      </button>
    </div>
  );
};
