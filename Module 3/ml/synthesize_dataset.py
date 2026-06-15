"""
Synthetic dataset generator for the Return Prevention risk scorer.

Label generation logic (return = 1):
  High-weight features (dominate the label):
    - has_size_ambiguity        weight: 0.30
    - product_review_rating     weight: 0.25  (inverted: low rating → high risk)
    - user_category_return_rate weight: 0.25
    - category_return_rate      weight: 0.10

  Low-weight features (minor contribution):
    - in_user_high_return_price_band weight: 0.03
    - is_buy_now                     weight: 0.03
    - is_sale_active                 weight: 0.02
    - seller_return_rate             weight: 0.01
    - page_dwell_seconds             weight: 0.01 (inverted: very short dwell → higher risk)

  Final label = 1 if weighted_sum > threshold (0.45) else 0, with small noise flip.
"""

import numpy as np
import pandas as pd

RANDOM_SEED = 42
N_SAMPLES = 10_000
OUTPUT_PATH = "ml/data/return_prevention_dataset.csv"


def synthesize(n: int = N_SAMPLES, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # ── Feature generation ────────────────────────────────────────────────────

    # Category-level return rate: realistic range 0.05 – 0.55
    category_return_rate = rng.beta(a=2, b=5, size=n).clip(0.05, 0.55)

    # User's personal return rate in this category: correlated with category rate
    # but with individual variance
    user_category_return_rate = (
        category_return_rate
        + rng.normal(loc=0.0, scale=0.10, size=n)
    ).clip(0.0, 1.0)

    # Price-band flag: ~30 % of purchases fall in the user's high-return band
    in_user_high_return_price_band = rng.choice(
        [0, 1], size=n, p=[0.70, 0.30]
    ).astype(bool)

    # Size ambiguity: ~40 % of SKUs are in size-ambiguous subcategories
    has_size_ambiguity = rng.choice(
        [0, 1], size=n, p=[0.60, 0.40]
    ).astype(bool)

    # Page dwell seconds: log-normal, median ~90s; very short dwell → impulsive
    page_dwell_seconds = rng.lognormal(mean=4.5, sigma=0.8, size=n).clip(2, 1800)

    # Buy Now vs Add to Cart: ~25 % use Buy Now (more impulsive)
    is_buy_now = rng.choice([0, 1], size=n, p=[0.75, 0.25]).astype(bool)

    # Product review rating: beta-distributed, most products 3.5–4.8
    product_review_rating = (rng.beta(a=8, b=2, size=n) * 5).clip(1.0, 5.0)

    # Seller return rate: most sellers 0.05–0.25
    seller_return_rate = rng.beta(a=2, b=8, size=n).clip(0.01, 0.50)

    # Sale active: ~20 % of page views during a sale
    is_sale_active = rng.choice([0, 1], size=n, p=[0.80, 0.20]).astype(bool)

    # ── Label construction ────────────────────────────────────────────────────
    # Normalise page_dwell to [0,1] — short dwell is risky, so invert
    dwell_norm = 1.0 - (page_dwell_seconds / page_dwell_seconds.max())

    # Invert review rating to a risk contribution
    review_risk = 1.0 - (product_review_rating - 1.0) / 4.0  # maps [1,5] → [1,0]

    weighted_risk = (
        0.30 * has_size_ambiguity.astype(float)
        + 0.25 * review_risk
        + 0.25 * user_category_return_rate
        + 0.10 * category_return_rate
        + 0.03 * in_user_high_return_price_band.astype(float)
        + 0.03 * is_buy_now.astype(float)
        + 0.02 * is_sale_active.astype(float)
        + 0.01 * seller_return_rate
        + 0.01 * dwell_norm
    )

    # Threshold + small noise flip (2 % chance) to avoid perfectly separable data
    label = (weighted_risk > 0.45).astype(int)
    noise_mask = rng.random(size=n) < 0.02
    label[noise_mask] = 1 - label[noise_mask]

    df = pd.DataFrame({
        "category_return_rate":          category_return_rate,
        "user_category_return_rate":     user_category_return_rate,
        "in_user_high_return_price_band": in_user_high_return_price_band.astype(int),
        "has_size_ambiguity":            has_size_ambiguity.astype(int),
        "page_dwell_seconds":            page_dwell_seconds.round(1),
        "is_buy_now":                    is_buy_now.astype(int),
        "product_review_rating":         product_review_rating.round(2),
        "seller_return_rate":            seller_return_rate.round(4),
        "is_sale_active":                is_sale_active.astype(int),
        "returned":                      label,
    })

    return df


if __name__ == "__main__":
    import os
    os.makedirs("ml/data", exist_ok=True)
    df = synthesize()
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Dataset written → {OUTPUT_PATH}")
    print(f"Shape           : {df.shape}")
    print(f"Return rate     : {df['returned'].mean():.2%}")
    print("\nFeature means:")
    print(df.drop(columns="returned").mean().round(4).to_string())
